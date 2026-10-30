"""Publish due expert outbox hints to the expert Redis stream."""

from __future__ import annotations

from contextlib import suppress

from .expert_contracts import ExpertRole
from .expert_repository import ACTIVE_JOB_STATUSES, TERMINAL_JOB_STATUSES


_EXPERT_JOB_STATUSES = ACTIVE_JOB_STATUSES | TERMINAL_JOB_STATUSES


class ExpertDispatcher:
    def __init__(
        self,
        repository,
        broker,
        batch_size: int = 50,
        *,
        metrics=None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.repository = repository
        self.broker = broker
        self.batch_size = batch_size
        self.metrics = metrics

    async def dispatch_once(self) -> int:
        rows = await self.repository.pending_outbox(self.batch_size)
        for row in rows:
            await self.broker.publish(row.event_key, row.payload)
            await self.repository.mark_outbox_published(
                row.id,
                row.event_key,
            )
        if self.metrics is not None:
            gauge = getattr(self.metrics, "expert_queue_depth", None)
            if gauge is not None:
                with suppress(Exception):
                    gauge.set(await self.broker.pending_count())
            jobs = getattr(self.metrics, "expert_jobs", None)
            if jobs is not None:
                with suppress(Exception):
                    counts = await self.repository.status_counts()
                    for role in ExpertRole:
                        for status in _EXPERT_JOB_STATUSES:
                            jobs.labels(
                                role=role.value,
                                status=status,
                            ).set(counts.get((role.value, status), 0))
        return len(rows)
