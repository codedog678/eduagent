from datetime import UTC, datetime


class LeaseReaper:
    def __init__(self, repository) -> None:
        self.repository = repository

    async def reap_once(self) -> list[str]:
        return await self.repository.requeue_expired(
            datetime.now(UTC)
        )
