"""Bounded, query-only projections for the distributed operations API."""

from __future__ import annotations

import base64
import binascii
import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .expert_contracts import ExpertUsage
from .expert_models import (
    DistributedExpertJob,
    DistributedExpertResult,
    DistributedWorkerRegistry,
)
from .models import (
    DistributedLease,
    DistributedRun,
    DistributedRunAttempt,
    DistributedTraceSpan,
)
from .ops_contracts import (
    OpsExpertAttempt,
    OpsExpertBudget,
    OpsExpertJobDetail,
    OpsExpertJobPage,
    OpsExpertJobSummary,
    OpsRunAttempt,
    OpsRunDetail,
    OpsRunPage,
    OpsRunSummary,
    OpsTrace,
    OpsTraceSpan,
    OpsUsage,
    OpsWorker,
    OpsWorkerPage,
)

_SAFE_TRACE_ATTRIBUTES = frozenset(
    {
        "duration_ms",
        "error.type",
        "expert.attempt",
        "expert.fencing_token",
        "expert.job_id",
        "expert.role",
        "job_id",
        "messaging.system",
        "process.type",
        "run.attempt",
        "run.fencing_token",
        "run.operation",
        "worker.id",
        "worker_id",
    }
)
_MAX_DETAIL_ATTEMPTS = 100
_MAX_DETAIL_JOBS = 100
_MAX_DETAIL_RESULTS = 100
_MAX_TRACE_SPANS = 500


class InvalidOpsCursor(ValueError):
    pass


def encode_cursor(created_at: datetime, row_id: str) -> str:
    raw = json.dumps(
        {"created_at": created_at.isoformat(), "id": row_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str]:
    try:
        padded = value + "=" * (-len(value) % 4)
        body = json.loads(base64.urlsafe_b64decode(padded).decode())
        if set(body) != {"created_at", "id"}:
            raise ValueError
        created_at = datetime.fromisoformat(body["created_at"])
        row_id = body["id"]
        if created_at.tzinfo is None or not isinstance(row_id, str) or not row_id:
            raise ValueError
        return created_at.astimezone(UTC), row_id
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise InvalidOpsCursor("invalid operations cursor") from exc


def _usage(value: ExpertUsage) -> OpsUsage:
    return OpsUsage(
        model_calls=value.model_calls,
        tool_calls=value.tool_calls,
        input_tokens=value.input_tokens,
        output_tokens=value.output_tokens,
        estimated_cost_usd=value.estimated_cost_usd,
        uncertain=value.uncertain,
    )


def _zero_usage() -> ExpertUsage:
    return ExpertUsage(
        model_calls=0,
        tool_calls=0,
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=Decimal("0"),
        provider="unknown",
        model="unknown",
        uncertain=False,
    )


def _sum_usage(values: list[ExpertUsage]) -> ExpertUsage:
    if not values:
        return _zero_usage()

    def optional_sum(name: str):
        parts = [getattr(item, name) for item in values]
        if any(item is None for item in parts):
            return None
        return sum(parts)

    return ExpertUsage(
        model_calls=sum(item.model_calls for item in values),
        tool_calls=sum(item.tool_calls for item in values),
        input_tokens=optional_sum("input_tokens"),
        output_tokens=optional_sum("output_tokens"),
        estimated_cost_usd=optional_sum("estimated_cost_usd"),
        provider=values[-1].provider,
        model=values[-1].model,
        uncertain=any(item.uncertain for item in values),
    )


def _cumulative_job_usage(
    rows: list[DistributedExpertResult],
) -> ExpertUsage:
    by_attempt: dict[int, list[DistributedExpertResult]] = defaultdict(list)
    for row in rows:
        by_attempt[row.expert_fencing_token].append(row)
    billable: list[DistributedExpertResult] = []
    for attempt_rows in by_attempt.values():
        accepted = next(
            (row for row in attempt_rows if row.disposition == "accepted"),
            None,
        )
        real = next(
            (
                row
                for row in attempt_rows
                if row.worker_id != "__expert_reaper__"
            ),
            None,
        )
        billable.append(accepted or real or attempt_rows[0])
    return _sum_usage(
        [ExpertUsage.model_validate(row.usage) for row in billable]
    )


def _source_refs(draft: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft, dict):
        return []
    refs = draft.get("source_refs")
    if not isinstance(refs, list):
        return []
    return [
        value
        for value in refs
        if isinstance(value, str) and 0 < len(value) <= 256
    ][:16]


class OpsQueries:
    """Read-only database access used exclusively by the Ops API."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        worker_stale_seconds: float = 15,
    ) -> None:
        if worker_stale_seconds <= 0:
            raise ValueError("worker_stale_seconds must be positive")
        self.session_factory = session_factory
        self.worker_stale_seconds = worker_stale_seconds

    async def list_runs(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        status: str | None = None,
        operation: str | None = None,
    ) -> OpsRunPage:
        async with self.session_factory() as session:
            now = await self._db_now(session)
            statement = (
                select(DistributedRun, DistributedLease)
                .join(
                    DistributedLease,
                    DistributedLease.run_id == DistributedRun.id,
                )
                .order_by(
                    DistributedRun.created_at.desc(),
                    DistributedRun.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedRun.created_at < created_at,
                        and_(
                            DistributedRun.created_at == created_at,
                            DistributedRun.id < row_id,
                        ),
                    )
                )
            if status:
                statement = statement.where(DistributedRun.status == status)
            if operation:
                statement = statement.where(
                    DistributedRun.operation == operation
                )
            rows = list(await session.execute(statement))
            visible = rows[:limit]
            run_ids = [run.id for run, _ in visible]
            job_counts = await self._job_counts(session, run_ids)
            run_usage = await self._run_usage(session, run_ids)
            items = [
                self._run_summary(
                    run,
                    lease,
                    now,
                    job_counts.get(run.id, 0),
                    run_usage.get(run.id, _zero_usage()),
                )
                for run, lease in visible
            ]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1][0].created_at,
                    visible[-1][0].id,
                )
            return OpsRunPage(items=items, next_cursor=next_cursor)

    async def get_run(self, run_id: str) -> OpsRunDetail | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(DistributedRun, DistributedLease)
                    .join(
                        DistributedLease,
                        DistributedLease.run_id == DistributedRun.id,
                    )
                    .where(DistributedRun.id == run_id)
                )
            ).one_or_none()
            if row is None:
                return None
            run, lease = row
            now = await self._db_now(session)
            attempts = list(
                await session.scalars(
                    select(DistributedRunAttempt)
                    .where(DistributedRunAttempt.run_id == run_id)
                    .order_by(DistributedRunAttempt.number)
                    .limit(_MAX_DETAIL_ATTEMPTS)
                )
            )
            jobs = list(
                await session.scalars(
                    select(DistributedExpertJob)
                    .where(DistributedExpertJob.parent_run_id == run_id)
                    .order_by(
                        DistributedExpertJob.created_at,
                        DistributedExpertJob.id,
                    )
                    .limit(_MAX_DETAIL_JOBS)
                )
            )
            usage_by_run = await self._run_usage(session, [run_id])
            summary = self._run_summary(
                run,
                lease,
                now,
                len(jobs),
                usage_by_run.get(run_id, _zero_usage()),
            )
            return OpsRunDetail(
                **summary.model_dump(),
                attempts=[
                    self._run_attempt(item, now)
                    for item in attempts
                ],
                expert_jobs=[self._job_summary(item) for item in jobs],
            )

    async def get_run_trace(self, run_id: str) -> OpsTrace | None:
        async with self.session_factory() as session:
            run = await session.get(DistributedRun, run_id)
            if run is None:
                return None
            now = await self._db_now(session)
            spans = list(
                await session.scalars(
                    select(DistributedTraceSpan)
                    .where(DistributedTraceSpan.run_id == run_id)
                    .order_by(
                        DistributedTraceSpan.started_at,
                        DistributedTraceSpan.span_id,
                    )
                    .limit(_MAX_TRACE_SPANS)
                )
            )
            return OpsTrace(
                run_id=run.id,
                trace_id=run.trace_id,
                spans=[self._trace_span(span, now) for span in spans],
            )

    async def list_expert_jobs(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        role: str | None = None,
        status: str | None = None,
        parent_run_id: str | None = None,
    ) -> OpsExpertJobPage:
        async with self.session_factory() as session:
            statement = (
                select(DistributedExpertJob)
                .order_by(
                    DistributedExpertJob.created_at.desc(),
                    DistributedExpertJob.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedExpertJob.created_at < created_at,
                        and_(
                            DistributedExpertJob.created_at == created_at,
                            DistributedExpertJob.id < row_id,
                        ),
                    )
                )
            if role:
                statement = statement.where(
                    func.lower(DistributedExpertJob.role) == role.lower()
                )
            if status:
                statement = statement.where(
                    DistributedExpertJob.status == status
                )
            if parent_run_id:
                statement = statement.where(
                    DistributedExpertJob.parent_run_id == parent_run_id
                )
            rows = list(await session.scalars(statement))
            visible = rows[:limit]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1].created_at,
                    visible[-1].id,
                )
            return OpsExpertJobPage(
                items=[self._job_summary(job) for job in visible],
                next_cursor=next_cursor,
            )

    async def get_expert_job(
        self,
        job_id: str,
    ) -> OpsExpertJobDetail | None:
        async with self.session_factory() as session:
            job = await session.get(DistributedExpertJob, job_id)
            if job is None:
                return None
            latest_results = list(
                await session.scalars(
                    select(DistributedExpertResult)
                    .where(DistributedExpertResult.job_id == job_id)
                    .order_by(
                        DistributedExpertResult.created_at.desc(),
                        DistributedExpertResult.id.desc(),
                    )
                    .limit(_MAX_DETAIL_RESULTS)
                )
            )
            accepted = await session.scalar(
                select(DistributedExpertResult).where(
                    DistributedExpertResult.job_id == job_id,
                    DistributedExpertResult.disposition == "accepted",
                )
            )
            by_id = {row.id: row for row in latest_results}
            if accepted is not None:
                by_id[accepted.id] = accepted
            if len(by_id) > _MAX_DETAIL_RESULTS:
                newest = sorted(
                    (
                        row
                        for row in by_id.values()
                        if accepted is None or row.id != accepted.id
                    ),
                    key=lambda row: (row.created_at, row.id),
                    reverse=True,
                )
                kept = newest[: _MAX_DETAIL_RESULTS - 1]
                if accepted is not None:
                    kept.append(accepted)
                by_id = {row.id: row for row in kept}
            results = sorted(
                by_id.values(),
                key=lambda row: (row.created_at, row.id),
            )
            verified_refs = self._verified_source_refs(job.payload)
            attempts = [
                self._expert_attempt(row, verified_refs)
                for row in results
            ]
            billable = await self._billable_job_results(session, job_id)
            refs = sorted(
                {
                    ref
                    for attempt in attempts
                    for ref in attempt.source_refs
                }
            )
            budget = job.payload.get("budget", {})
            return OpsExpertJobDetail(
                job_id=job.id,
                parent_run_id=job.parent_run_id,
                logical_key=job.logical_key,
                role=job.role.lower(),
                status=job.status,
                input_hash=job.input_hash,
                policy_hash=job.policy_hash,
                budget=OpsExpertBudget.model_validate(budget),
                usage=_usage(_cumulative_job_usage(billable)),
                source_refs=refs,
                attempts=attempts,
                error_code=job.error_code,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
            )

    async def list_workers(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        worker_id: str | None = None,
        process_type: str | None = None,
        status: str | None = None,
    ) -> OpsWorkerPage:
        async with self.session_factory() as session:
            now = await self._db_now(session)
            statement = (
                select(DistributedWorkerRegistry)
                .order_by(
                    DistributedWorkerRegistry.started_at.desc(),
                    DistributedWorkerRegistry.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedWorkerRegistry.started_at < created_at,
                        and_(
                            DistributedWorkerRegistry.started_at == created_at,
                            DistributedWorkerRegistry.id < row_id,
                        ),
                    )
                )
            if worker_id:
                statement = statement.where(
                    DistributedWorkerRegistry.worker_id == worker_id
                )
            if process_type:
                statement = statement.where(
                    DistributedWorkerRegistry.process_type == process_type
                )
            if status:
                statement = statement.where(
                    DistributedWorkerRegistry.status == status
                )
            rows = list(await session.scalars(statement))
            visible = rows[:limit]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1].started_at,
                    visible[-1].id,
                )
            return OpsWorkerPage(
                items=[self._worker(row, now) for row in visible],
                next_cursor=next_cursor,
            )

    async def _job_counts(
        self,
        session: AsyncSession,
        run_ids: list[str],
    ) -> dict[str, int]:
        if not run_ids:
            return {}
        rows = await session.execute(
            select(
                DistributedExpertJob.parent_run_id,
                func.count(DistributedExpertJob.id),
            )
            .where(DistributedExpertJob.parent_run_id.in_(run_ids))
            .group_by(DistributedExpertJob.parent_run_id)
        )
        return {run_id: int(count) for run_id, count in rows}

    async def _run_usage(
        self,
        session: AsyncSession,
        run_ids: list[str],
    ) -> dict[str, ExpertUsage]:
        if not run_ids:
            return {}
        priority = case(
            (DistributedExpertResult.disposition == "accepted", 0),
            (
                DistributedExpertResult.worker_id
                != "__expert_reaper__",
                1,
            ),
            else_=2,
        )
        ranked = (
            select(
                DistributedExpertJob.parent_run_id.label("run_id"),
                DistributedExpertJob.id.label("job_id"),
                DistributedExpertResult.usage.label("usage"),
                func.row_number()
                .over(
                    partition_by=(
                        DistributedExpertJob.id,
                        DistributedExpertResult.expert_fencing_token,
                    ),
                    order_by=(
                        priority,
                        DistributedExpertResult.created_at,
                        DistributedExpertResult.id,
                    ),
                )
                .label("usage_rank"),
            )
            .join(
                DistributedExpertResult,
                DistributedExpertResult.job_id
                == DistributedExpertJob.id,
            )
            .where(DistributedExpertJob.parent_run_id.in_(run_ids))
            .subquery()
        )
        rows = await session.execute(
            select(ranked.c.run_id, ranked.c.usage).where(
                ranked.c.usage_rank == 1
            )
        )
        per_run: dict[str, list[ExpertUsage]] = defaultdict(list)
        for run_id, usage in rows:
            per_run[run_id].append(ExpertUsage.model_validate(usage))
        return {
            run_id: _sum_usage(usages)
            for run_id, usages in per_run.items()
        }

    @staticmethod
    async def _billable_job_results(
        session: AsyncSession,
        job_id: str,
    ) -> list[DistributedExpertResult]:
        priority = case(
            (DistributedExpertResult.disposition == "accepted", 0),
            (
                DistributedExpertResult.worker_id
                != "__expert_reaper__",
                1,
            ),
            else_=2,
        )
        rows = await session.scalars(
            select(DistributedExpertResult)
            .where(DistributedExpertResult.job_id == job_id)
            .order_by(
                DistributedExpertResult.expert_fencing_token,
                priority,
                DistributedExpertResult.created_at,
                DistributedExpertResult.id,
            )
            .distinct(DistributedExpertResult.expert_fencing_token)
        )
        return list(rows)

    @staticmethod
    async def _db_now(session: AsyncSession) -> datetime:
        return await session.scalar(select(func.now()))

    @staticmethod
    def _run_summary(
        run: DistributedRun,
        lease: DistributedLease,
        now: datetime,
        job_count: int,
        usage: ExpertUsage,
    ) -> OpsRunSummary:
        end = (
            run.updated_at
            if run.status
            in {
                "completed",
                "terminal_failed",
                "cancelled",
                "exhausted",
            }
            else now
        )
        return OpsRunSummary(
            run_id=run.id,
            operation=run.operation,
            status=run.status,
            trace_id=run.trace_id,
            attempt_count=run.attempt_count,
            owner=lease.owner,
            fencing_token=lease.fencing_token,
            lease_expires_at=lease.expires_at,
            lease_fresh=bool(
                lease.owner
                and lease.expires_at
                and lease.expires_at > now
            ),
            expert_job_count=job_count,
            usage=_usage(usage),
            latency_ms=max(
                0,
                int((end - run.created_at).total_seconds() * 1000),
            ),
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _run_attempt(
        attempt: DistributedRunAttempt,
        now: datetime,
    ) -> OpsRunAttempt:
        end = attempt.finished_at or now
        return OpsRunAttempt(
            number=attempt.number,
            worker_id=attempt.worker_id,
            fencing_token=attempt.fencing_token,
            status=attempt.status,
            reason=attempt.reason,
            started_at=attempt.started_at,
            deadline_at=attempt.deadline_at,
            finished_at=attempt.finished_at,
            duration_ms=max(
                0,
                int((end - attempt.started_at).total_seconds() * 1000),
            ),
        )

    @staticmethod
    def _job_summary(
        job: DistributedExpertJob,
    ) -> OpsExpertJobSummary:
        return OpsExpertJobSummary(
            job_id=job.id,
            parent_run_id=job.parent_run_id,
            role=job.role.lower(),
            status=job.status,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            error_code=job.error_code,
            deadline_at=job.deadline_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _trace_span(
        span: DistributedTraceSpan,
        now: datetime,
    ) -> OpsTraceSpan:
        attributes = {
            key: value
            for key, value in span.attributes.items()
            if key in _SAFE_TRACE_ATTRIBUTES
            and isinstance(value, (str, int, float, bool))
        }
        end = span.ended_at or now
        return OpsTraceSpan(
            span_id=span.span_id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            status=span.status,
            attributes=attributes,
            started_at=span.started_at,
            ended_at=span.ended_at,
            duration_ms=max(
                0,
                int((end - span.started_at).total_seconds() * 1000),
            ),
        )

    @staticmethod
    def _verified_source_refs(payload: dict[str, Any]) -> set[str]:
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            return set()
        refs = snapshot.get("verified_source_refs")
        if not isinstance(refs, list):
            return set()
        return {
            value
            for value in refs
            if isinstance(value, str) and 0 < len(value) <= 256
        }

    @staticmethod
    def _expert_attempt(
        result: DistributedExpertResult,
        verified_refs: set[str],
    ) -> OpsExpertAttempt:
        return OpsExpertAttempt(
            worker_id=result.worker_id,
            fencing_token=result.expert_fencing_token,
            disposition=result.disposition,
            rejection_code=result.rejection_code,
            usage=_usage(ExpertUsage.model_validate(result.usage)),
            source_refs=[
                ref
                for ref in _source_refs(result.draft)
                if ref in verified_refs
            ],
            created_at=result.created_at,
        )

    def _worker(
        self,
        row: DistributedWorkerRegistry,
        now: datetime,
    ) -> OpsWorker:
        age = max(
            0.0,
            (now - row.last_heartbeat_at).total_seconds(),
        )
        fresh = row.status == "running" and age <= self.worker_stale_seconds
        health = (
            "stopped"
            if row.status == "stopped"
            else "healthy"
            if fresh
            else "stale"
        )
        capabilities = [
            value
            for value in row.capabilities
            if isinstance(value, str) and 0 < len(value) <= 128
        ][:32]
        return OpsWorker(
            worker_id=row.worker_id,
            instance_id=row.instance_id,
            process_type=row.process_type,
            status=row.status,
            health=health,
            fresh=fresh,
            capabilities=capabilities,
            current_run_id=row.current_run_id,
            current_job_id=row.current_job_id,
            heartbeat_age_seconds=round(age, 3),
            started_at=row.started_at,
            last_heartbeat_at=row.last_heartbeat_at,
            stopped_at=row.stopped_at,
        )
