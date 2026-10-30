from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .contracts import DistributedRunRequest, RunStatus
from .models import (
    DistributedInbox,
    DistributedLease,
    DistributedOutbox,
    DistributedRun,
    DistributedRunAttempt,
    DistributedStep,
    DistributedTraceSpan,
    new_id,
)


class RequestConflict(RuntimeError):
    pass


class FencingViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class RunClaim:
    attempt_id: str
    run_id: str
    learner_id: str
    request_id: str
    operation: str
    payload: dict
    input_hash: str
    trace_id: str
    attempt_count: int
    fencing_token: int
    deadline_at: datetime

    def to_request(self) -> DistributedRunRequest:
        return DistributedRunRequest(
            learner_id=self.learner_id,
            request_id=self.request_id,
            operation=self.operation,
            payload=self.payload,
        )


class DistributedRunRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        clock: Callable[[], datetime] | None = None,
        max_attempts: int = 3,
        parent_timeout_seconds: float = 120,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if parent_timeout_seconds <= 0:
            raise ValueError("parent_timeout_seconds must be positive")
        self.session_factory = session_factory
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_attempts = max_attempts
        self.parent_timeout_seconds = parent_timeout_seconds

    async def accept(self, spec: DistributedRunRequest) -> DistributedRun:
        run, _ = await self.accept_with_replay(spec)
        return run

    async def accept_with_replay(
        self,
        spec: DistributedRunRequest,
    ) -> tuple[DistributedRun, bool]:
        run_id = new_id()
        trace_id = uuid4().hex
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            inserted_id = await session.scalar(
                pg_insert(DistributedRun)
                .values(
                    id=run_id,
                    learner_id=spec.learner_id,
                    request_id=spec.request_id,
                    operation=spec.operation,
                    input_hash=spec.input_hash,
                    payload=spec.payload.model_dump(mode="json"),
                    status=RunStatus.ACCEPTED,
                    trace_id=trace_id,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["learner_id", "request_id"]
                )
                .returning(DistributedRun.id)
            )
            if inserted_id is None:
                existing = await session.scalar(
                    select(DistributedRun).where(
                        DistributedRun.learner_id == spec.learner_id,
                        DistributedRun.request_id == spec.request_id,
                    )
                )
                if existing is None or existing.input_hash != spec.input_hash:
                    raise RequestConflict(
                        "request_id is already bound to different input"
                    )
                return existing, True

            run = await self._locked_run(session, run_id)
            session.add(
                DistributedLease(
                    run_id=run_id,
                    owner=None,
                    fencing_token=0,
                    expires_at=None,
                    updated_at=now,
                )
            )
            session.add(
                self._outbox(
                    run_id,
                    "accepted",
                    "run.accepted",
                    now,
                )
            )
            return run, False

    async def get(self, run_id: str) -> DistributedRun | None:
        async with self.session_factory() as session:
            return await session.get(DistributedRun, run_id)

    async def get_by_request(
        self,
        learner_id: str,
        request_id: str,
    ) -> DistributedRun | None:
        async with self.session_factory() as session:
            return await session.scalar(
                select(DistributedRun).where(
                    DistributedRun.learner_id == learner_id,
                    DistributedRun.request_id == request_id,
                )
            )

    async def claim(
        self,
        run_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> RunClaim:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            allowed = {
                RunStatus.ACCEPTED,
                RunStatus.QUEUED,
                RunStatus.RETRYABLE_FAILED,
            }
            if run.status not in allowed:
                raise FencingViolation(
                    f"run {run_id} cannot be claimed from {run.status}"
                )
            if (
                lease.owner is not None
                and lease.expires_at is not None
                and lease.expires_at > now
            ):
                raise FencingViolation(f"run {run_id} already has a live lease")

            run.attempt_count += 1
            run.status = RunStatus.RUNNING
            run.error_code = None
            run.updated_at = now
            lease.owner = worker_id
            lease.fencing_token += 1
            lease.expires_at = now + timedelta(seconds=lease_seconds)
            lease.updated_at = now
            attempt = DistributedRunAttempt(
                run_id=run_id,
                number=run.attempt_count,
                worker_id=worker_id,
                fencing_token=lease.fencing_token,
                status=RunStatus.RUNNING,
                started_at=now,
                deadline_at=now + timedelta(seconds=self.parent_timeout_seconds),
            )
            session.add(attempt)
            await session.flush()
            return self._claim_from(run, lease, attempt)

    async def renew(
        self,
        run_id: str,
        worker_id: str,
        token: int,
        lease_seconds: float,
    ) -> DistributedLease:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
                worker_id,
            )
            if run.status not in {
                RunStatus.RUNNING,
                RunStatus.WAITING_EXPERT,
                RunStatus.COMMITTING,
            }:
                raise FencingViolation(
                    f"run {run_id} cannot renew from {run.status}"
                )
            lease.expires_at = now + timedelta(seconds=lease_seconds)
            lease.updated_at = now
            return lease

    async def lease(self, run_id: str) -> DistributedLease:
        async with self.session_factory() as session:
            lease = await session.get(DistributedLease, run_id)
            if lease is None:
                raise LookupError(f"run {run_id} has no lease")
            return lease

    async def start_step(
        self,
        run_id: str,
        step_id: str,
        input_hash: str,
        token: int,
    ) -> DistributedStep:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
            )
            self._assert_active(run)
            existing = await self._locked_step(session, run_id, step_id)
            if existing is not None:
                self._assert_step_hash(existing, input_hash)
                if existing.status == RunStatus.RUNNING:
                    existing.fencing_token = token
                return existing
            step = DistributedStep(
                run_id=run_id,
                step_id=step_id,
                input_hash=input_hash,
                status=RunStatus.RUNNING,
                fencing_token=token,
                started_at=now,
            )
            session.add(step)
            await session.flush()
            return step

    async def complete_step(
        self,
        run_id: str,
        step_id: str,
        input_hash: str,
        token: int,
        result: dict,
    ) -> DistributedStep:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
            )
            self._assert_active(run)
            step = await self._locked_step(session, run_id, step_id)
            if step is None:
                raise RequestConflict(
                    f"step {step_id} has not been started for run {run_id}"
                )

            self._assert_step_hash(step, input_hash)
            if step.status == RunStatus.COMPLETED:
                return step
            if step.fencing_token != token:
                raise FencingViolation(
                    f"step {step_id} is owned by stale token "
                    f"{step.fencing_token}"
                )
            step.status = RunStatus.COMPLETED
            step.fencing_token = token
            step.result = result
            step.finished_at = now
            return step

    async def transition_committing(
        self,
        run_id: str,
        token: int,
    ) -> DistributedRun:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
            )
            if run.status == RunStatus.COMMITTING:
                return run
            if run.status != RunStatus.RUNNING:
                raise FencingViolation(
                    f"run {run_id} cannot commit from {run.status}"
                )
            run.status = RunStatus.COMMITTING
            run.updated_at = now
            return run

    async def complete(
        self,
        run_id: str,
        token: int,
        result: dict,
    ) -> DistributedRun:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
            )
            updated = await session.execute(
                update(DistributedRun)
                .where(
                    DistributedRun.id == run_id,
                    DistributedRun.status == RunStatus.COMMITTING,
                    exists().where(
                        DistributedLease.run_id == run_id,
                        DistributedLease.fencing_token == token,
                        DistributedLease.owner.is_not(None),
                        DistributedLease.expires_at
                        > func.clock_timestamp(),
                    ),
                )
                .values(
                    status=RunStatus.COMPLETED,
                    result=result,
                    error_code=None,
                    updated_at=now,
                )
            )
            if updated.rowcount != 1:
                raise FencingViolation(
                    f"run {run_id} cannot be completed by token {token}"
                )
            await self._finish_attempt(
                session,
                run_id,
                token,
                RunStatus.COMPLETED,
                now,
            )
            lease.owner = None
            lease.expires_at = None
            lease.updated_at = now
            await session.refresh(run)
            return run

    async def fail(
        self,
        run_id: str,
        token: int,
        code: str,
        retryable: bool,
    ) -> DistributedRun:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            await self._assert_active_lease(
                session,
                run,
                lease,
                token,
                now,
            )
            self._assert_active(run)
            if retryable and run.attempt_count >= self.max_attempts:
                status = RunStatus.EXHAUSTED
            elif retryable:
                status = RunStatus.RETRYABLE_FAILED
            else:
                status = RunStatus.TERMINAL_FAILED
            run.status = status
            run.error_code = code
            run.updated_at = now
            await self._finish_attempt(
                session,
                run_id,
                token,
                status,
                now,
                reason=code,
            )
            lease.owner = None
            lease.expires_at = None
            lease.updated_at = now
            if status == RunStatus.RETRYABLE_FAILED:
                session.add(
                    self._outbox(
                        run_id,
                        f"retry:{token}",
                        "run.retry",
                        now,
                    )
                )
            return run

    async def cancel(self, run_id: str) -> DistributedRun:
        run, _ = await self.cancel_with_transition(run_id)
        return run

    async def cancel_with_transition(
        self,
        run_id: str,
    ) -> tuple[DistributedRun, bool]:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, lease = await self._locked_run_and_lease(session, run_id)
            if RunStatus(run.status).terminal:
                return run, False
            run.status = RunStatus.CANCELLED
            run.updated_at = now
            await self._close_expert_jobs_for_cancel(session, run_id, now)
            if lease.owner is not None:
                await self._finish_attempt(
                    session,
                    run_id,
                    lease.fencing_token,
                    RunStatus.CANCELLED,
                    now,
                    reason="cancelled",
                )
            lease.owner = None
            lease.expires_at = None
            lease.updated_at = now
            session.add(
                self._outbox(
                    run_id,
                    "cancelled",
                    "run.cancelled",
                    now,
                )
            )
            return run, True

    async def pending_outbox(
        self,
        limit: int,
    ) -> list[DistributedOutbox]:
        async with self.session_factory() as session, session.begin():
            rows = await session.scalars(
                select(DistributedOutbox)
                .where(DistributedOutbox.published_at.is_(None))
                .order_by(DistributedOutbox.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            outboxes = list(rows)
            for outbox in outboxes:
                outbox.publish_attempts += 1
            return outboxes

    async def mark_outbox_published(
        self,
        outbox_id: str,
        event_key: str,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            outbox = await session.scalar(
                select(DistributedOutbox)
                .where(DistributedOutbox.id == outbox_id)
                .with_for_update()
            )
            if outbox is None:
                raise LookupError(f"outbox {outbox_id} does not exist")
            if outbox.event_key != event_key:
                raise RequestConflict(
                    f"outbox {outbox_id} event key does not match"
                )
            if outbox.published_at is None:
                outbox.published_at = await self._db_now(session)

    async def record_inbox(
        self,
        consumer: str,
        event_key: str,
    ) -> bool:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            inserted_id = await session.scalar(
                pg_insert(DistributedInbox)
                .values(
                    id=new_id(),
                    consumer=consumer,
                    message_key=event_key,
                    received_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["consumer", "message_key"]
                )
                .returning(DistributedInbox.id)
            )
            return inserted_id is not None

    async def requeue_expired(self, now: datetime) -> list[str]:
        del now
        requeued: list[str] = []
        async with self.session_factory() as session, session.begin():
            database_now = await self._db_now(session)
            run_ids = list(
                await session.scalars(
                    select(DistributedLease.run_id)
                    .where(
                        DistributedLease.owner.is_not(None),
                        DistributedLease.expires_at <= database_now,
                    )
                    .order_by(DistributedLease.run_id)
                )
            )
            for run_id in run_ids:
                run, lease = await self._locked_run_and_lease(
                    session,
                    run_id,
                )
                database_now = await self._db_now(session)
                if (
                    lease.owner is None
                    or lease.expires_at is None
                    or lease.expires_at > database_now
                ):
                    continue
                if run.status not in {
                    RunStatus.RUNNING,
                    RunStatus.WAITING_EXPERT,
                    RunStatus.COMMITTING,
                }:
                    lease.owner = None
                    lease.expires_at = None
                    lease.updated_at = database_now
                    continue
                token = lease.fencing_token
                exhausted = run.attempt_count >= self.max_attempts
                run.status = (
                    RunStatus.EXHAUSTED
                    if exhausted
                    else RunStatus.QUEUED
                )
                run.error_code = "lease_expired"
                run.updated_at = database_now
                await self._finish_attempt(
                    session,
                    run.id,
                    token,
                    (
                        RunStatus.EXHAUSTED
                        if exhausted
                        else RunStatus.RETRYABLE_FAILED
                    ),
                    database_now,
                    reason="lease_expired",
                )
                lease.owner = None
                lease.expires_at = None
                lease.updated_at = database_now
                if not exhausted:
                    session.add(
                        self._outbox(
                            run.id,
                            f"retry:{token}",
                            "run.retry",
                            database_now,
                        )
                    )
                    requeued.append(run.id)
        return requeued

    async def force_lease_expiry(
        self,
        run_id: str,
        at: datetime,
    ) -> None:
        await self._force_lease_expiry_for_tests(run_id, at)

    async def _force_lease_expiry_for_tests(
        self,
        run_id: str,
        at: datetime,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            lease = await session.scalar(
                select(DistributedLease)
                .where(DistributedLease.run_id == run_id)
                .with_for_update()
            )
            if lease is None:
                raise LookupError(f"run {run_id} has no lease")
            lease.expires_at = at
            lease.updated_at = await self._db_now(session)

    async def start_span(
        self,
        run_id: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        name: str,
        attributes: dict,
    ) -> DistributedTraceSpan:
        async with self.session_factory() as session, session.begin():
            run = await self._locked_run(session, run_id)
            if run.trace_id != trace_id:
                raise RequestConflict(
                    f"trace {trace_id} does not belong to run {run_id}"
                )
            existing = await session.get(DistributedTraceSpan, span_id)
            if existing is not None:
                if existing.run_id != run_id:
                    raise RequestConflict(
                        f"span {span_id} belongs to another run"
                    )
                return existing
            span = DistributedTraceSpan(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                run_id=run_id,
                name=name,
                status="running",
                attributes=attributes,
                started_at=await self._db_now(session),
            )
            session.add(span)
            await session.flush()
            return span

    async def finish_span(
        self,
        span_id: str,
        status: str,
        attributes: dict,
    ) -> DistributedTraceSpan:
        async with self.session_factory() as session, session.begin():
            span = await session.scalar(
                select(DistributedTraceSpan)
                .where(DistributedTraceSpan.span_id == span_id)
                .with_for_update()
            )
            if span is None:
                raise LookupError(f"span {span_id} does not exist")
            span.status = status
            span.attributes = {**span.attributes, **attributes}
            span.ended_at = await self._db_now(session)
            return span

    async def trace(self, run_id: str) -> list[DistributedTraceSpan]:
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(DistributedTraceSpan)
                .where(DistributedTraceSpan.run_id == run_id)
                .order_by(DistributedTraceSpan.started_at)
            )
            return list(rows)

    async def status_counts(self) -> dict[str, int]:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(
                    DistributedRun.status,
                    func.count(DistributedRun.id),
                ).group_by(DistributedRun.status)
            )
            return {
                str(status): int(count)
                for status, count in rows
            }

    async def _locked_run(
        self,
        session: AsyncSession,
        run_id: str,
    ) -> DistributedRun:
        run = await session.scalar(
            select(DistributedRun)
            .where(DistributedRun.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise LookupError(f"run {run_id} does not exist")
        return run

    async def _locked_run_and_lease(
        self,
        session: AsyncSession,
        run_id: str,
    ) -> tuple[DistributedRun, DistributedLease]:
        run = await self._locked_run(session, run_id)
        lease = await session.scalar(
            select(DistributedLease)
            .where(DistributedLease.run_id == run_id)
            .with_for_update()
        )
        if lease is None:
            raise LookupError(f"run {run_id} has no lease")
        return run, lease

    async def _locked_step(
        self,
        session: AsyncSession,
        run_id: str,
        step_id: str,
    ) -> DistributedStep | None:
        return await session.scalar(
            select(DistributedStep)
            .where(
                DistributedStep.run_id == run_id,
                DistributedStep.step_id == step_id,
            )
            .with_for_update()
        )

    async def _finish_attempt(
        self,
        session: AsyncSession,
        run_id: str,
        token: int,
        status: RunStatus,
        finished_at: datetime,
        reason: str | None = None,
    ) -> None:
        attempt = await session.scalar(
            select(DistributedRunAttempt)
            .where(
                DistributedRunAttempt.run_id == run_id,
                DistributedRunAttempt.fencing_token == token,
            )
            .with_for_update()
        )
        if attempt is None:
            raise FencingViolation(
                f"run {run_id} has no attempt for token {token}"
            )
        attempt.status = status
        attempt.reason = reason
        attempt.finished_at = finished_at

    def _outbox(
        self,
        run_id: str,
        suffix: str,
        topic: str,
        created_at: datetime,
    ) -> DistributedOutbox:
        return DistributedOutbox(
            event_key=f"run:{run_id}:{suffix}",
            topic=topic,
            payload={"run_id": run_id},
            created_at=created_at,
            publish_attempts=0,
        )

    @staticmethod
    async def _db_now(session: AsyncSession) -> datetime:
        return await session.scalar(select(func.clock_timestamp()))

    async def _assert_active_lease(
        self,
        session: AsyncSession,
        run: DistributedRun,
        lease: DistributedLease,
        token: int,
        now: datetime,
        worker_id: str | None = None,
    ) -> None:
        run_id = run.id
        if lease.fencing_token != token:
            raise FencingViolation(
                f"stale fencing token for run {run_id}"
            )
        if lease.owner is None:
            raise FencingViolation(f"run {run_id} has no lease owner")
        if worker_id is not None and lease.owner != worker_id:
            raise FencingViolation(
                f"worker {worker_id} does not own run {run_id}"
            )
        if lease.expires_at is None or lease.expires_at <= now:
            raise FencingViolation(f"lease for run {run_id} has expired")
        attempt = await session.scalar(
            select(DistributedRunAttempt)
            .where(
                DistributedRunAttempt.run_id == run.id,
                DistributedRunAttempt.fencing_token == token,
            )
            .with_for_update()
        )
        if (
            attempt is None
            or attempt.finished_at is not None
            or attempt.worker_id != lease.owner
        ):
            raise FencingViolation(
                f"lease owner and attempt do not match for run {run_id}"
            )

    @staticmethod
    def _assert_active(run: DistributedRun) -> None:
        if run.status not in {
            RunStatus.RUNNING,
            RunStatus.WAITING_EXPERT,
            RunStatus.COMMITTING,
        }:
            raise FencingViolation(
                f"run {run.id} is not active: {run.status}"
            )

    @staticmethod
    def _assert_step_hash(
        step: DistributedStep,
        input_hash: str,
    ) -> None:
        if step.input_hash != input_hash:
            raise RequestConflict(
                f"step {step.step_id} is bound to different input"
            )

    @staticmethod
    def _claim_from(
        run: DistributedRun,
        lease: DistributedLease,
        attempt: DistributedRunAttempt,
    ) -> RunClaim:
        return RunClaim(
            attempt_id=attempt.id,
            run_id=run.id,
            learner_id=run.learner_id,
            request_id=run.request_id,
            operation=run.operation,
            payload=run.payload,
            input_hash=run.input_hash,
            trace_id=run.trace_id,
            attempt_count=run.attempt_count,
            fencing_token=lease.fencing_token,
            deadline_at=attempt.deadline_at,
        )

    @staticmethod
    async def _close_expert_jobs_for_cancel(
        session: AsyncSession,
        run_id: str,
        now: datetime,
    ) -> None:
        from .expert_models import DistributedExpertJob, DistributedExpertLease

        jobs = list(
            await session.scalars(
                select(DistributedExpertJob)
                .where(
                    DistributedExpertJob.parent_run_id == run_id,
                    DistributedExpertJob.status.in_(
                        {
                            "accepted",
                            "queued",
                            "running",
                            "retryable_failed",
                        }
                    ),
                )
                .order_by(DistributedExpertJob.id)
                .with_for_update()
            )
        )
        for job in jobs:
            expert_lease = await session.scalar(
                select(DistributedExpertLease)
                .where(DistributedExpertLease.job_id == job.id)
                .with_for_update()
            )
            job.status = "cancelled"
            job.error_code = "cancelled"
            job.completed_at = now
            job.updated_at = now
            if expert_lease is not None:
                expert_lease.owner = None
                expert_lease.expires_at = None
                expert_lease.updated_at = now
