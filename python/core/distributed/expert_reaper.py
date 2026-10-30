"""Recovery wrapper for authoritative expert-job reaping."""

from __future__ import annotations


class ExpertReaper:
    def __init__(self, repository, *, metrics=None) -> None:
        self.repository = repository
        self.metrics = metrics

    async def reap_once(self) -> list[str]:
        job_ids = await self.repository.reap_expired()
        if self.metrics is not None:
            counter = getattr(self.metrics, "expert_takeovers", None)
            if counter is not None:
                for _ in job_ids:
                    counter.inc()
        return job_ids
