from datetime import UTC, datetime


class LeaseReaper:
    def __init__(
        self,
        repository,
        *,
        tracer=None,
        metrics=None,
    ) -> None:
        self.repository = repository
        self.tracer = tracer
        self.metrics = metrics

    async def reap_once(self) -> list[str]:
        run_ids = await self.repository.requeue_expired(
            datetime.now(UTC)
        )
        for run_id in run_ids:
            if self.metrics is not None:
                counter = getattr(
                    self.metrics,
                    "lease_takeovers",
                    None,
                )
                if counter is not None:
                    counter.inc()
            if self.tracer is not None:
                run = await self.repository.get(run_id)
                if run is not None:
                    async with self.tracer.span(
                        run.id,
                        run.trace_id,
                        "lease.reap",
                        attributes={"run.id": run.id},
                    ):
                        pass
        return run_ids
