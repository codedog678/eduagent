from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .contracts import RunStatus
from .expert_contracts import (
    ExpertErrorCode,
    ExpertJobRequest,
    ExpertRole,
    ExpertTerminalEnvelope,
    ExpertUsage,
)
from .expert_models import (
    DistributedExpertJob,
    DistributedExpertLease,
    DistributedExpertOutbox,
    DistributedExpertResult,
)
from .models import (
    DistributedLease,
    DistributedRun,
    DistributedRunAttempt,
    new_id,
)


ACTIVE_JOB_STATUSES = {
    "accepted",
    "queued",
    "running",
    "retryable_failed",
}
TERMINAL_JOB_STATUSES = {
    "completed",
    "terminal_failed",
    "exhausted",
    "cancelled",
    "parent_stale",
}


class ExpertRequestConflict(RuntimeError):
    pass


class ExpertFencingViolation(RuntimeError):
    pass


class ExpertBackpressure(RuntimeError):
    pass


class ExpertCapabilityMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpertClaim:
    job_id: str
    request: ExpertJobRequest
    worker_id: str
    attempt_count: int
    fencing_token: int
    lease_expires_at: datetime

    @property
    def claimed(self) -> bool:
        return True


@dataclass(frozen=True)
class ExpertLeaseView:
    job_id: str
    worker_id: str
    fencing_token: int
    lease_expires_at: datetime


@dataclass(frozen=True)
class ExpertClaimReceipt:
    job_id: str
    claimed: bool
    rejection_code: str
    available_at: datetime | None = None


@dataclass(frozen=True)
class ResultReceipt:
    job_id: str
    accepted: bool
    disposition: str
    rejection_code: str | None


@dataclass(frozen=True)
class ExpertFailure:
    code: ExpertErrorCode
    retryable: bool
    usage: ExpertUsage
    diagnostics: tuple[str, ...] = ()


class ExpertJobRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        queued_limit_per_role: int = 50,
        running_limit_per_role: int = 2,
        queued_payload_bytes_limit: int = 10 * 1024 * 1024,
        max_payload_bytes: int = 256 * 1024,
        max_job_seconds: float = 120,
        retry_base_seconds: float = 1,
        retry_max_seconds: float = 30,
    ) -> None:
        if min(queued_limit_per_role, running_limit_per_role) < 1:
            raise ValueError("expert admission limits must be positive")
        if min(queued_payload_bytes_limit, max_payload_bytes) < 1:
            raise ValueError("expert payload limits must be positive")
        if max_job_seconds <= 0:
            raise ValueError("max_job_seconds must be positive")
        if retry_base_seconds <= 0 or retry_base_seconds > retry_max_seconds:
            raise ValueError("invalid expert retry delay")
        self.session_factory = session_factory
        self.queued_limit_per_role = queued_limit_per_role
        self.running_limit_per_role = running_limit_per_role
        self.queued_payload_bytes_limit = queued_payload_bytes_limit
        self.max_payload_bytes = max_payload_bytes
        self.max_job_seconds = max_job_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    async def create_or_replay(
        self,
        request: ExpertJobRequest,
    ) -> tuple[DistributedExpertJob, bool]:
        payload = request.model_dump(mode="json")
        payload_bytes = len(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if payload_bytes > self.max_payload_bytes:
            raise ExpertBackpressure("expert payload exceeds maximum")

        parent_run_id = str(request.authority.distributed_run_id)
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            run, run_lease = await self._locked_parent(
                session,
                parent_run_id,
            )
            await self._advisory_lock(session, "parent", parent_run_id)
            await self._advisory_lock(session, "queue", "payload-bytes")
            await self._advisory_lock(session, "role", request.role.value)
            attempt = await self._locked_parent_attempt(
                session,
                parent_run_id,
                request.authority.run_fencing_token,
            )
            self._assert_parent_authority(
                run,
                run_lease,
                attempt,
                request.authority.run_fencing_token,
                now,
            )
            if request.authority.attempt_number != attempt.number:
                raise ExpertFencingViolation("parent attempt number is stale")
            if request.authority.worker_id != attempt.worker_id:
                raise ExpertFencingViolation("parent worker identity is stale")
            if request.authority.trace_id != run.trace_id:
                raise ExpertFencingViolation("parent trace identity is stale")
            if request.learner_id != run.learner_id:
                raise ExpertFencingViolation("parent learner scope is stale")
            if request.authority.parent_deadline_at != attempt.deadline_at:
                raise ExpertFencingViolation(
                    "parent deadline does not match persisted attempt"
                )
            if request.budget.deadline_at > attempt.deadline_at:
                raise ExpertFencingViolation(
                    "expert deadline exceeds persisted parent deadline"
                )
            if request.budget.deadline_at > (
                now + timedelta(seconds=self.max_job_seconds)
            ):
                raise ExpertFencingViolation(
                    "expert deadline exceeds configured maximum"
                )
            if request.budget.deadline_at <= now:
                raise ExpertFencingViolation("expert deadline has expired")

            await self._close_old_parent_epochs(
                session,
                parent_run_id,
                request.authority.run_fencing_token,
                now,
            )
            existing = await session.scalar(
                select(DistributedExpertJob)
                .where(
                    DistributedExpertJob.parent_run_id == parent_run_id,
                    DistributedExpertJob.parent_fencing_token
                    == request.authority.run_fencing_token,
                    DistributedExpertJob.logical_key == request.logical_key,
                )
                .with_for_update()
            )
            if existing is not None:
                if existing.input_hash != request.input_hash:
                    raise ExpertRequestConflict(
                        "logical key is already bound to different input"
                    )
                return existing, True

            active_for_parent = await session.scalar(
                select(func.count(DistributedExpertJob.id)).where(
                    DistributedExpertJob.parent_run_id == parent_run_id,
                    DistributedExpertJob.parent_fencing_token
                    == request.authority.run_fencing_token,
                    DistributedExpertJob.status.in_(ACTIVE_JOB_STATUSES),
                )
            )
            if active_for_parent:
                raise ExpertBackpressure(
                    "parent already has an active job"
                )
            queued_for_role = await session.scalar(
                select(func.count(DistributedExpertJob.id)).where(
                    DistributedExpertJob.role == request.role.value,
                    DistributedExpertJob.status.in_({"accepted", "queued"}),
                )
            )
            if int(queued_for_role or 0) >= self.queued_limit_per_role:
                raise ExpertBackpressure("expert role queue is full")
            queued_bytes = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(DistributedExpertJob.payload_bytes),
                        0,
                    )
                ).where(
                    DistributedExpertJob.status.in_({"accepted", "queued"})
                )
            )
            if int(queued_bytes or 0) + payload_bytes > (
                self.queued_payload_bytes_limit
            ):
                raise ExpertBackpressure("expert queued payload limit exceeded")

            job = DistributedExpertJob(
                id=new_id(),
                parent_run_id=parent_run_id,
                parent_fencing_token=request.authority.run_fencing_token,
                logical_key=request.logical_key,
                role=request.role.value,
                input_hash=request.input_hash,
                policy_hash=request.snapshot.effective_policy_hash,
                payload=payload,
                payload_bytes=payload_bytes,
                status="queued",
                attempt_count=0,
                max_attempts=request.budget.max_attempts,
                deadline_at=request.budget.deadline_at,
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            session.add(
                DistributedExpertLease(
                    job_id=job.id,
                    owner=None,
                    fencing_token=0,
                    expires_at=None,
                    updated_at=now,
                )
            )
            session.add(self._outbox(job, "accepted", now, now))
            run.status = RunStatus.WAITING_EXPERT
            run.updated_at = now
            await session.flush()
            return job, False

    async def get(self, job_id: str) -> DistributedExpertJob:
        async with self.session_factory() as session:
            job = await session.get(DistributedExpertJob, job_id)
            if job is None:
                raise LookupError(f"expert job {job_id} does not exist")
            return job

    async def claim(
        self,
        job_id: str,
        worker_id: str,
        roles: set[ExpertRole],
        lease_seconds: float,
    ) -> ExpertClaim | ExpertClaimReceipt:
        async with self.session_factory() as session, session.begin():
            identity = await self._job_identity(session, job_id)
            job_role = ExpertRole(identity.role)
            if job_role not in roles:
                return ExpertClaimReceipt(
                    job_id=job_id,
                    claimed=False,
                    rejection_code="capability_mismatch",
                )
            now = await self._db_now(session)
            run, run_lease = await self._locked_parent(
                session,
                identity.parent_run_id,
            )
            attempt = await self._locked_parent_attempt(
                session,
                identity.parent_run_id,
                identity.parent_fencing_token,
            )
            job, expert_lease = await self._locked_job_and_lease(
                session,
                job_id,
            )
            await self._advisory_lock(session, "role", job.role)
            self._assert_parent_authority(
                run,
                run_lease,
                attempt,
                job.parent_fencing_token,
                now,
            )
            if job.deadline_at <= now:
                raise ExpertFencingViolation("expert deadline has expired")
            if job.status not in {"accepted", "queued", "retryable_failed"}:
                raise ExpertFencingViolation(
                    f"expert job cannot be claimed from {job.status}"
                )
            if (
                expert_lease.owner is not None
                and expert_lease.expires_at is not None
                and expert_lease.expires_at > now
            ):
                raise ExpertFencingViolation("expert job has a live lease")
            running = await session.scalar(
                select(func.count(DistributedExpertJob.id)).where(
                    DistributedExpertJob.role == job.role,
                    DistributedExpertJob.status == "running",
                    DistributedExpertJob.id != job.id,
                )
            )
            if int(running or 0) >= self.running_limit_per_role:
                available_at = now + timedelta(
                    seconds=self._retry_delay(job.id, job.attempt_count + 1)
                )
                session.add(
                    self._outbox(
                        job,
                        f"admission:{new_id()}",
                        now,
                        available_at,
                    )
                )
                return ExpertClaimReceipt(
                    job_id=job.id,
                    claimed=False,
                    rejection_code="running_limit",
                    available_at=available_at,
                )

            job.status = "running"
            job.error_code = None
            job.attempt_count += 1
            job.updated_at = now
            expert_lease.owner = worker_id
            expert_lease.fencing_token += 1
            expert_lease.expires_at = now + timedelta(seconds=lease_seconds)
            expert_lease.updated_at = now
            return ExpertClaim(
                job_id=job.id,
                request=ExpertJobRequest.model_validate(job.payload),
                worker_id=worker_id,
                attempt_count=job.attempt_count,
                fencing_token=expert_lease.fencing_token,
                lease_expires_at=expert_lease.expires_at,
            )

    async def renew(
        self,
        job_id: str,
        worker_id: str,
        token: int,
        lease_seconds: float,
    ) -> ExpertLeaseView:
        async with self.session_factory() as session, session.begin():
            identity = await self._job_identity(session, job_id)
            now = await self._db_now(session)
            run, run_lease = await self._locked_parent(
                session,
                identity.parent_run_id,
            )
            attempt = await self._locked_parent_attempt(
                session,
                identity.parent_run_id,
                identity.parent_fencing_token,
            )
            job, expert_lease = await self._locked_job_and_lease(
                session,
                job_id,
            )
            self._assert_parent_authority(
                run,
                run_lease,
                attempt,
                job.parent_fencing_token,
                now,
            )
            self._assert_expert_authority(
                job,
                expert_lease,
                worker_id,
                token,
                now,
            )
            expert_lease.expires_at = now + timedelta(seconds=lease_seconds)
            expert_lease.updated_at = now
            return ExpertLeaseView(
                job_id=job.id,
                worker_id=worker_id,
                fencing_token=token,
                lease_expires_at=expert_lease.expires_at,
            )

    async def submit_result(
        self,
        job_id: str,
        worker_id: str,
        token: int,
        envelope: ExpertTerminalEnvelope,
    ) -> ResultReceipt:
        async with self.session_factory() as session, session.begin():
            identity = await self._job_identity(session, job_id)
            now = await self._db_now(session)
            run, run_lease = await self._locked_parent(
                session,
                identity.parent_run_id,
            )
            job, expert_lease = await self._locked_job_and_lease(
                session,
                job_id,
            )
            results = await self._locked_results(session, job_id)
            rejection = self._result_rejection(
                run,
                run_lease,
                job,
                expert_lease,
                results,
                worker_id,
                token,
                envelope,
                now,
            )
            disposition = "rejected" if rejection else "accepted"
            session.add(
                DistributedExpertResult(
                    job_id=job.id,
                    expert_fencing_token=token,
                    worker_id=worker_id,
                    disposition=disposition,
                    rejection_code=rejection,
                    draft=(
                        envelope.draft.model_dump(mode="json")
                        if envelope.draft is not None
                        else None
                    ),
                    usage=envelope.usage.model_dump(mode="json"),
                    diagnostics=list(envelope.diagnostics),
                    created_at=now,
                )
            )
            if rejection is not None:
                return ResultReceipt(
                    job_id=job.id,
                    accepted=False,
                    disposition=disposition,
                    rejection_code=rejection,
                )

            job.status = (
                "completed"
                if envelope.outcome == "succeeded"
                else "terminal_failed"
            )
            job.error_code = (
                envelope.error_code.value
                if envelope.error_code is not None
                else None
            )
            job.completed_at = now
            job.updated_at = now
            expert_lease.owner = None
            expert_lease.expires_at = None
            expert_lease.updated_at = now
            await self._restore_parent_running(session, run, job, now)
            return ResultReceipt(
                job_id=job.id,
                accepted=True,
                disposition=disposition,
                rejection_code=None,
            )

    async def fail_attempt(
        self,
        job_id: str,
        worker_id: str,
        token: int,
        failure: ExpertFailure,
    ) -> DistributedExpertJob:
        async with self.session_factory() as session, session.begin():
            identity = await self._job_identity(session, job_id)
            now = await self._db_now(session)
            run, run_lease = await self._locked_parent(
                session,
                identity.parent_run_id,
            )
            attempt = await self._locked_parent_attempt(
                session,
                identity.parent_run_id,
                identity.parent_fencing_token,
            )
            job, expert_lease = await self._locked_job_and_lease(
                session,
                job_id,
            )
            await self._locked_results(session, job_id)
            self._assert_parent_authority(
                run,
                run_lease,
                attempt,
                job.parent_fencing_token,
                now,
            )
            self._assert_expert_authority(
                job,
                expert_lease,
                worker_id,
                token,
                now,
            )
            session.add(
                DistributedExpertResult(
                    job_id=job.id,
                    expert_fencing_token=token,
                    worker_id=worker_id,
                    disposition="rejected",
                    rejection_code=failure.code.value,
                    draft=None,
                    usage=failure.usage.model_dump(mode="json"),
                    diagnostics=list(failure.diagnostics),
                    created_at=now,
                )
            )
            expert_lease.owner = None
            expert_lease.expires_at = None
            expert_lease.updated_at = now
            can_retry = (
                failure.retryable
                and job.attempt_count < job.max_attempts
                and job.deadline_at > now
            )
            if can_retry:
                job.status = "queued"
                job.error_code = failure.code.value
                job.updated_at = now
                available_at = now + timedelta(
                    seconds=self._retry_delay(job.id, job.attempt_count)
                )
                session.add(
                    self._outbox(
                        job,
                        f"retry:{token}",
                        now,
                        available_at,
                    )
                )
            else:
                job.status = (
                    "exhausted"
                    if failure.retryable
                    else "terminal_failed"
                )
                job.error_code = failure.code.value
                job.completed_at = now
                job.updated_at = now
                await self._restore_parent_running(session, run, job, now)
            return job

    async def terminal(
        self,
        job_id: str,
        parent_token: int,
    ) -> ExpertTerminalEnvelope | None:
        async with self.session_factory() as session:
            job = await session.get(DistributedExpertJob, job_id)
            if job is None:
                raise LookupError(f"expert job {job_id} does not exist")
            if job.parent_fencing_token != parent_token:
                raise ExpertFencingViolation("parent fencing token is stale")
            if job.status not in TERMINAL_JOB_STATUSES:
                return None
            rows = list(
                await session.scalars(
                    select(DistributedExpertResult)
                    .where(DistributedExpertResult.job_id == job_id)
                    .order_by(DistributedExpertResult.created_at)
                )
            )
            request = ExpertJobRequest.model_validate(job.payload)
            cumulative = self._cumulative_usage(rows)
            accepted = next(
                (row for row in rows if row.disposition == "accepted"),
                None,
            )
            completed_at = job.completed_at or job.updated_at
            if job.status == "completed" and accepted is not None:
                return ExpertTerminalEnvelope.model_validate(
                    {
                        "step_id": request.step_id,
                        "role": request.role,
                        "input_hash": job.input_hash,
                        "outcome": "succeeded",
                        "draft": accepted.draft,
                        "usage": cumulative.model_dump(mode="json"),
                        "completed_at": completed_at,
                        "diagnostics": accepted.diagnostics,
                    }
                )
            error_code = self._terminal_error_code(job)
            return ExpertTerminalEnvelope(
                step_id=request.step_id,
                role=request.role,
                input_hash=job.input_hash,
                outcome="failed",
                usage=cumulative,
                completed_at=completed_at,
                error_code=error_code,
            )

    async def reap_expired(self) -> list[str]:
        changed: list[str] = []
        async with self.session_factory() as session, session.begin():
            job_ids = list(
                await session.scalars(
                    select(DistributedExpertJob.id)
                    .where(DistributedExpertJob.status.in_(ACTIVE_JOB_STATUSES))
                    .order_by(DistributedExpertJob.id)
                )
            )
            for job_id in job_ids:
                identity = await self._job_identity(session, job_id)
                now = await self._db_now(session)
                run, run_lease = await self._locked_parent(
                    session,
                    identity.parent_run_id,
                )
                job, expert_lease = await self._locked_job_and_lease(
                    session,
                    job_id,
                )
                await self._locked_results(session, job_id)
                if job.status not in ACTIVE_JOB_STATUSES:
                    continue
                parent_valid = (
                    run_lease.fencing_token == job.parent_fencing_token
                    and run_lease.owner is not None
                    and run_lease.expires_at is not None
                    and run_lease.expires_at > now
                    and run.status in {RunStatus.RUNNING, RunStatus.WAITING_EXPERT}
                )
                if not parent_valid:
                    self._close_job(
                        job,
                        expert_lease,
                        "parent_stale",
                        "parent_stale",
                        now,
                    )
                    changed.append(job.id)
                    continue
                if job.deadline_at <= now:
                    self._close_job(
                        job,
                        expert_lease,
                        "terminal_failed",
                        ExpertErrorCode.DEADLINE_EXPIRED.value,
                        now,
                    )
                    await self._restore_parent_running(session, run, job, now)
                    changed.append(job.id)
                    continue
                if (
                    job.status == "running"
                    and expert_lease.expires_at is not None
                    and expert_lease.expires_at <= now
                ):
                    if job.attempt_count >= job.max_attempts:
                        self._close_job(
                            job,
                            expert_lease,
                            "exhausted",
                            "lease_expired",
                            now,
                        )
                        await self._restore_parent_running(
                            session,
                            run,
                            job,
                            now,
                        )
                    else:
                        expert_lease.owner = None
                        expert_lease.expires_at = None
                        expert_lease.updated_at = now
                        job.status = "queued"
                        job.error_code = "lease_expired"
                        job.updated_at = now
                        available_at = now + timedelta(
                            seconds=self._retry_delay(
                                job.id,
                                job.attempt_count,
                            )
                        )
                        session.add(
                            self._outbox(
                                job,
                                f"lease-expired:{expert_lease.fencing_token}",
                                now,
                                available_at,
                            )
                        )
                    changed.append(job.id)
        return changed

    async def result_count(self, job_id: str) -> int:
        async with self.session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count(DistributedExpertResult.id)).where(
                        DistributedExpertResult.job_id == job_id
                    )
                )
                or 0
            )

    async def accepted_result_count(self, job_id: str) -> int:
        async with self.session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count(DistributedExpertResult.id)).where(
                        DistributedExpertResult.job_id == job_id,
                        DistributedExpertResult.disposition == "accepted",
                    )
                )
                or 0
            )

    async def force_lease_expiry(
        self,
        job_id: str,
        at: datetime,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            lease = await session.scalar(
                select(DistributedExpertLease)
                .where(DistributedExpertLease.job_id == job_id)
                .with_for_update()
            )
            if lease is None:
                raise LookupError(f"expert job {job_id} has no lease")
            lease.expires_at = at
            lease.updated_at = await self._db_now(session)

    async def force_job_deadline(
        self,
        job_id: str,
        at: datetime,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            job = await session.scalar(
                select(DistributedExpertJob)
                .where(DistributedExpertJob.id == job_id)
                .with_for_update()
            )
            if job is None:
                raise LookupError(f"expert job {job_id} does not exist")
            job.deadline_at = at

    async def _close_old_parent_epochs(
        self,
        session: AsyncSession,
        parent_run_id: str,
        parent_token: int,
        now: datetime,
    ) -> None:
        jobs = list(
            await session.scalars(
                select(DistributedExpertJob)
                .where(
                    DistributedExpertJob.parent_run_id == parent_run_id,
                    DistributedExpertJob.parent_fencing_token < parent_token,
                    DistributedExpertJob.status.in_(ACTIVE_JOB_STATUSES),
                )
                .order_by(DistributedExpertJob.id)
                .with_for_update()
            )
        )
        for job in jobs:
            lease = await session.scalar(
                select(DistributedExpertLease)
                .where(DistributedExpertLease.job_id == job.id)
                .with_for_update()
            )
            if lease is not None:
                self._close_job(
                    job,
                    lease,
                    "parent_stale",
                    ExpertErrorCode.PARENT_STALE.value,
                    now,
                )

    async def _restore_parent_running(
        self,
        session: AsyncSession,
        run: DistributedRun,
        finished_job: DistributedExpertJob,
        now: datetime,
    ) -> None:
        other_active = await session.scalar(
            select(func.count(DistributedExpertJob.id)).where(
                DistributedExpertJob.parent_run_id == run.id,
                DistributedExpertJob.parent_fencing_token
                == finished_job.parent_fencing_token,
                DistributedExpertJob.id != finished_job.id,
                DistributedExpertJob.status.in_(ACTIVE_JOB_STATUSES),
            )
        )
        if (
            not other_active
            and run.status == RunStatus.WAITING_EXPERT
        ):
            run.status = RunStatus.RUNNING
            run.updated_at = now

    @staticmethod
    def _close_job(
        job: DistributedExpertJob,
        lease: DistributedExpertLease,
        status: str,
        error_code: str,
        now: datetime,
    ) -> None:
        job.status = status
        job.error_code = error_code
        job.completed_at = now
        job.updated_at = now
        lease.owner = None
        lease.expires_at = None
        lease.updated_at = now

    @staticmethod
    def _result_rejection(
        run: DistributedRun,
        run_lease: DistributedLease,
        job: DistributedExpertJob,
        expert_lease: DistributedExpertLease,
        results: list[DistributedExpertResult],
        worker_id: str,
        token: int,
        envelope: ExpertTerminalEnvelope,
        now: datetime,
    ) -> str | None:
        if (
            run_lease.fencing_token != job.parent_fencing_token
            or run_lease.owner is None
            or run_lease.expires_at is None
            or run_lease.expires_at <= now
            or run.status not in {RunStatus.RUNNING, RunStatus.WAITING_EXPERT}
        ):
            return "parent_stale"
        if job.deadline_at <= now:
            return "deadline_expired"
        if (
            job.status != "running"
            or expert_lease.owner != worker_id
            or expert_lease.fencing_token != token
            or expert_lease.expires_at is None
            or expert_lease.expires_at <= now
        ):
            return "expert_token_stale"
        if any(result.disposition == "accepted" for result in results):
            return "result_conflict"
        if (
            envelope.role.value != job.role
            or envelope.step_id != job.payload.get("step_id")
            or envelope.input_hash != job.input_hash
        ):
            return "schema_invalid"
        return None

    @staticmethod
    def _assert_parent_authority(
        run: DistributedRun,
        lease: DistributedLease,
        attempt: DistributedRunAttempt,
        token: int,
        now: datetime,
    ) -> None:
        if lease.fencing_token != token:
            raise ExpertFencingViolation("parent fencing token is stale")
        if lease.owner is None or lease.expires_at is None:
            raise ExpertFencingViolation("parent lease is not owned")
        if lease.expires_at <= now:
            raise ExpertFencingViolation("parent lease has expired")
        if run.status not in {RunStatus.RUNNING, RunStatus.WAITING_EXPERT}:
            raise ExpertFencingViolation(
                f"parent run is not active: {run.status}"
            )
        if attempt.finished_at is not None or attempt.worker_id != lease.owner:
            raise ExpertFencingViolation("parent attempt is not active")
        if attempt.deadline_at <= now:
            raise ExpertFencingViolation("parent deadline has expired")

    @staticmethod
    def _assert_expert_authority(
        job: DistributedExpertJob,
        lease: DistributedExpertLease,
        worker_id: str,
        token: int,
        now: datetime,
    ) -> None:
        if job.status != "running":
            raise ExpertFencingViolation(
                f"expert job is not running: {job.status}"
            )
        if lease.owner != worker_id or lease.fencing_token != token:
            raise ExpertFencingViolation("expert fencing token is stale")
        if lease.expires_at is None or lease.expires_at <= now:
            raise ExpertFencingViolation("expert lease has expired")
        if job.deadline_at <= now:
            raise ExpertFencingViolation("expert deadline has expired")

    @staticmethod
    async def _locked_parent(
        session: AsyncSession,
        run_id: str,
    ) -> tuple[DistributedRun, DistributedLease]:
        run = await session.scalar(
            select(DistributedRun)
            .where(DistributedRun.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise LookupError(f"parent run {run_id} does not exist")
        lease = await session.scalar(
            select(DistributedLease)
            .where(DistributedLease.run_id == run_id)
            .with_for_update()
        )
        if lease is None:
            raise LookupError(f"parent run {run_id} has no lease")
        return run, lease

    @staticmethod
    async def _locked_parent_attempt(
        session: AsyncSession,
        run_id: str,
        token: int,
    ) -> DistributedRunAttempt:
        attempt = await session.scalar(
            select(DistributedRunAttempt)
            .where(
                DistributedRunAttempt.run_id == run_id,
                DistributedRunAttempt.fencing_token == token,
            )
            .with_for_update()
        )
        if attempt is None:
            raise ExpertFencingViolation("parent attempt does not exist")
        return attempt

    @staticmethod
    async def _job_identity(
        session: AsyncSession,
        job_id: str,
    ) -> DistributedExpertJob:
        job = await session.get(DistributedExpertJob, job_id)
        if job is None:
            raise LookupError(f"expert job {job_id} does not exist")
        return job

    @staticmethod
    async def _locked_job_and_lease(
        session: AsyncSession,
        job_id: str,
    ) -> tuple[DistributedExpertJob, DistributedExpertLease]:
        job = await session.scalar(
            select(DistributedExpertJob)
            .where(DistributedExpertJob.id == job_id)
            .with_for_update()
        )
        if job is None:
            raise LookupError(f"expert job {job_id} does not exist")
        lease = await session.scalar(
            select(DistributedExpertLease)
            .where(DistributedExpertLease.job_id == job_id)
            .with_for_update()
        )
        if lease is None:
            raise LookupError(f"expert job {job_id} has no lease")
        return job, lease

    @staticmethod
    async def _locked_results(
        session: AsyncSession,
        job_id: str,
    ) -> list[DistributedExpertResult]:
        return list(
            await session.scalars(
                select(DistributedExpertResult)
                .where(DistributedExpertResult.job_id == job_id)
                .order_by(DistributedExpertResult.id)
                .with_for_update()
            )
        )

    @staticmethod
    async def _advisory_lock(
        session: AsyncSession,
        namespace: str,
        key: str,
    ) -> None:
        await session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"{namespace}:{key}", 0)
                )
            )
        )

    @staticmethod
    async def _db_now(session: AsyncSession) -> datetime:
        return await session.scalar(select(func.clock_timestamp()))

    def _retry_delay(self, job_id: str, attempt_count: int) -> float:
        base = min(
            self.retry_max_seconds,
            self.retry_base_seconds * (2 ** max(0, attempt_count - 1)),
        )
        if base >= self.retry_max_seconds:
            return self.retry_max_seconds
        digest = hashlib.sha256(job_id.encode("ascii")).digest()
        jitter = int.from_bytes(digest[:2], "big") / 65535
        return min(self.retry_max_seconds, base * (1 + jitter * 0.2))

    @staticmethod
    def _outbox(
        job: DistributedExpertJob,
        suffix: str,
        created_at: datetime,
        available_at: datetime,
    ) -> DistributedExpertOutbox:
        return DistributedExpertOutbox(
            job_id=job.id,
            event_key=f"expert:{job.id}:{suffix}",
            topic="expert.queued",
            payload={"job_id": job.id, "role": job.role},
            available_at=available_at,
            created_at=created_at,
            publish_attempts=0,
        )

    @staticmethod
    def _cumulative_usage(
        rows: list[DistributedExpertResult],
    ) -> ExpertUsage:
        usages = [ExpertUsage.model_validate(row.usage) for row in rows]
        if not usages:
            return ExpertUsage(
                model_calls=0,
                tool_calls=0,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=Decimal("0"),
                provider="unknown",
                model="unknown",
                uncertain=True,
            )

        def optional_sum(name: str):
            values = [getattr(item, name) for item in usages]
            if any(value is None for value in values):
                return None
            return sum(values)

        return ExpertUsage(
            model_calls=sum(item.model_calls for item in usages),
            tool_calls=sum(item.tool_calls for item in usages),
            input_tokens=optional_sum("input_tokens"),
            output_tokens=optional_sum("output_tokens"),
            estimated_cost_usd=optional_sum("estimated_cost_usd"),
            provider=usages[-1].provider,
            model=usages[-1].model,
            uncertain=any(item.uncertain for item in usages),
        )

    @staticmethod
    def _terminal_error_code(
        job: DistributedExpertJob,
    ) -> ExpertErrorCode:
        aliases = {
            "lease_expired": ExpertErrorCode.LEASE_LOST,
            "parent_stale": ExpertErrorCode.PARENT_STALE,
        }
        if job.error_code in aliases:
            return aliases[job.error_code]
        try:
            return ExpertErrorCode(job.error_code)
        except (TypeError, ValueError):
            return ExpertErrorCode.EXPERT_FAILED
