from __future__ import annotations


class OutboxDispatcher:
    def __init__(
        self,
        repository,
        broker,
        batch_size: int = 50,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.repository = repository
        self.broker = broker
        self.batch_size = batch_size

    async def dispatch_once(self) -> int:
        rows = await self.repository.pending_outbox(self.batch_size)
        published = 0
        for row in rows:
            await self.broker.publish(row.event_key, row.payload)
            await self.repository.mark_outbox_published(
                row.id,
                row.event_key,
            )
            published += 1
        return published
