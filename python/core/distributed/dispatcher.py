from __future__ import annotations

from contextlib import asynccontextmanager, suppress


class OutboxDispatcher:
    def __init__(
        self,
        repository,
        broker,
        batch_size: int = 50,
        *,
        tracer=None,
        metrics=None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.repository = repository
        self.broker = broker
        self.batch_size = batch_size
        self.tracer = tracer
        self.metrics = metrics

    @asynccontextmanager
    async def _publish_span(self, row):
        if self.tracer is None:
            yield None
            return
        run = await self.repository.get(row.payload["run_id"])
        if run is None:
            yield None
            return
        async with self.tracer.span(
            run.id,
            run.trace_id,
            "outbox.publish",
            attributes={"messaging.system": "redis"},
        ) as span:
            yield span

    async def _observe_queue_depth(self) -> None:
        if self.metrics is None:
            return
        gauge = getattr(self.metrics, "queue_depth", None)
        if gauge is None:
            return
        with suppress(Exception):
            gauge.set(await self.broker.pending_count())

    async def dispatch_once(self) -> int:
        rows = await self.repository.pending_outbox(self.batch_size)
        published = 0
        for row in rows:
            async with self._publish_span(row):
                await self.broker.publish(row.event_key, row.payload)
                await self.repository.mark_outbox_published(
                    row.id,
                    row.event_key,
                )
            published += 1
        await self._observe_queue_depth()
        return published
