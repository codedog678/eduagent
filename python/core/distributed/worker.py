from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import HTTPException

from core.distributed.contracts import RunStatus
from core.distributed.executor import BusinessStoreBusy
from core.distributed.repository import FencingViolation
from core.run_context import RunExhausted


class LeaseLost(RuntimeError):
    pass


class RunWorker:
    def __init__(
        self,
        worker_id,
        repository,
        broker,
        executor,
        *,
        lease_seconds: float,
        heartbeat_seconds: float,
        max_attempts: int,
        pause_before_commit_seconds: float = 0,
        pending_idle_ms: int | None = None,
        tracer=None,
        metrics=None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        if heartbeat_seconds >= lease_seconds:
            raise ValueError(
                "heartbeat_seconds must be shorter than lease_seconds"
            )
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.worker_id = worker_id
        self.repository = repository
        self.broker = broker
        self.executor = executor
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.max_attempts = max_attempts
        self.pause_before_commit_seconds = pause_before_commit_seconds
        self.tracer = tracer
        self.metrics = metrics
        self.pending_idle_ms = (
            max(1, int(lease_seconds * 1000))
            if pending_idle_ms is None
            else pending_idle_ms
        )

    @asynccontextmanager
    async def _span(
        self,
        run_id: str,
        trace_id: str,
        name: str,
        *,
        parent_span_id: str | None = None,
        attributes: dict | None = None,
    ):
        if self.tracer is None:
            yield None
            return
        async with self.tracer.span(
            run_id,
            trace_id,
            name,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        ) as span:
            yield span

    def _increment_metric(
        self,
        name: str,
        *,
        labels: dict | None = None,
    ) -> None:
        if self.metrics is None:
            return
        metric = getattr(self.metrics, name, None)
        if metric is None:
            return
        with suppress(Exception):
            if labels:
                metric = metric.labels(**labels)
            metric.inc()

    def _count_status(self, status) -> None:
        outcome = getattr(status, "value", status)
        self._increment_metric(
            "runs",
            labels={"outcome": str(outcome)},
        )

    async def _heartbeat(
        self,
        run_id: str,
        token: int,
        lease_lost: asyncio.Event,
    ) -> None:
        try:
            while True:
                await asyncio.sleep(self.heartbeat_seconds)
                await self.repository.renew(
                    run_id,
                    self.worker_id,
                    token,
                    self.lease_seconds,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            lease_lost.set()
            raise LeaseLost(
                f"lease heartbeat failed for run {run_id}"
            ) from exc

    async def _renew_or_raise(
        self,
        run_id: str,
        token: int,
        lease_lost: asyncio.Event,
        heartbeat: asyncio.Task | None,
    ) -> None:
        if lease_lost.is_set() or (
            heartbeat is not None and heartbeat.done()
        ):
            await self._raise_heartbeat_failure(heartbeat)
        try:
            await self.repository.renew(
                run_id,
                self.worker_id,
                token,
                self.lease_seconds,
            )
        except Exception as exc:
            lease_lost.set()
            raise LeaseLost(
                f"lease validation failed for run {run_id}"
            ) from exc

    @staticmethod
    async def _raise_heartbeat_failure(
        heartbeat: asyncio.Task | None,
    ) -> None:
        if heartbeat is not None:
            try:
                await heartbeat
            except LeaseLost:
                raise
        raise LeaseLost("lease heartbeat stopped")

    @staticmethod
    async def _await_execution(
        execution: asyncio.Task,
        heartbeat: asyncio.Task,
    ) -> dict:
        done, _ = await asyncio.wait(
            {execution, heartbeat},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            await RunWorker._raise_heartbeat_failure(heartbeat)
        return await execution

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        current: BaseException | None = exc
        while current is not None:
            if isinstance(current, RunExhausted):
                return False
            current = current.__cause__
        if isinstance(exc, HTTPException):
            return (
                exc.status_code in {408, 425, 429}
                or exc.status_code >= 500
            )
        return not isinstance(
            exc,
            (PermissionError, ValueError),
        )

    async def _fail(
        self,
        run_id: str,
        token: int,
        code: str,
        retryable: bool,
        lease_lost: asyncio.Event,
        heartbeat: asyncio.Task | None,
    ):
        await self._renew_or_raise(
            run_id,
            token,
            lease_lost,
            heartbeat,
        )
        return await self.repository.fail(
            run_id,
            token,
            code,
            retryable=retryable,
        )

    async def handle(self, message) -> None:
        run_id = message.payload["run_id"]
        await self.repository.record_inbox(
            self.worker_id,
            message.event_key,
        )
        try:
            claim = await self.repository.claim(
                run_id,
                self.worker_id,
                self.lease_seconds,
            )
        except FencingViolation:
            await self.broker.ack(message.redis_id)
            return

        lease_lost = asyncio.Event()
        execution: asyncio.Task | None = None
        heartbeat: asyncio.Task | None = None
        try:
            async with self._span(
                run_id,
                claim.trace_id,
                "run.attempt",
                attributes={
                    "worker.id": self.worker_id,
                    "run.attempt": claim.attempt_count,
                    "run.fencing_token": claim.fencing_token,
                },
            ) as attempt_span:
                parent_span_id = getattr(
                    attempt_span,
                    "span_id",
                    None,
                )
                await self._renew_or_raise(
                    run_id,
                    claim.fencing_token,
                    lease_lost,
                    heartbeat,
                )
                request = claim.to_request()
                step = await self.repository.start_step(
                    run_id,
                    "business-execution",
                    request.input_hash,
                    claim.fencing_token,
                )
                async with self._span(
                    run_id,
                    claim.trace_id,
                    "business.execute",
                    parent_span_id=parent_span_id,
                    attributes={"run.operation": request.operation},
                ):
                    if step.status == RunStatus.COMPLETED:
                        if step.result is None:
                            raise RuntimeError(
                                "completed step has no result"
                            )
                        result = step.result
                        self._increment_metric(
                            "idempotency_hits",
                            labels={"scope": "step"},
                        )
                    else:
                        execution = asyncio.create_task(
                            self.executor.execute(request)
                        )
                        heartbeat = asyncio.create_task(
                            self._heartbeat(
                                run_id,
                                claim.fencing_token,
                                lease_lost,
                            )
                        )
                        result = await self._await_execution(
                            execution,
                            heartbeat,
                        )

                async with self._span(
                    run_id,
                    claim.trace_id,
                    "run.commit",
                    parent_span_id=parent_span_id,
                    attributes={
                        "run.fencing_token": claim.fencing_token
                    },
                ):
                    await self._renew_or_raise(
                        run_id,
                        claim.fencing_token,
                        lease_lost,
                        heartbeat,
                    )
                    await self.repository.complete_step(
                        run_id,
                        "business-execution",
                        request.input_hash,
                        claim.fencing_token,
                        result,
                    )
                    await self._renew_or_raise(
                        run_id,
                        claim.fencing_token,
                        lease_lost,
                        heartbeat,
                    )
                    await self.repository.transition_committing(
                        run_id,
                        claim.fencing_token,
                    )
                    if self.pause_before_commit_seconds:
                        await asyncio.sleep(
                            self.pause_before_commit_seconds
                        )
                    await self._renew_or_raise(
                        run_id,
                        claim.fencing_token,
                        lease_lost,
                        heartbeat,
                    )
                    completed = await self.repository.complete(
                        run_id,
                        claim.fencing_token,
                        result,
                    )
                    self._count_status(completed.status)
            await self.broker.ack(message.redis_id)
        except BusinessStoreBusy:
            try:
                failed = await self._fail(
                    run_id,
                    claim.fencing_token,
                    "business_store_busy",
                    True,
                    lease_lost,
                    heartbeat,
                )
            except FencingViolation:
                self._increment_metric("fencing_rejections")
                return
            except LeaseLost:
                return
            self._count_status(failed.status)
            await self.broker.ack(message.redis_id)
        except FencingViolation:
            self._increment_metric("fencing_rejections")
            return
        except LeaseLost:
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                failed = await self._fail(
                    run_id,
                    claim.fencing_token,
                    type(exc).__name__,
                    (
                        claim.attempt_count < self.max_attempts
                        and self._is_retryable(exc)
                    ),
                    lease_lost,
                    heartbeat,
                )
            except FencingViolation:
                self._increment_metric("fencing_rejections")
                return
            except LeaseLost:
                return
            self._count_status(failed.status)
            await self.broker.ack(message.redis_id)
        finally:
            if execution is not None and not execution.done():
                execution.cancel()
                with suppress(asyncio.CancelledError):
                    await execution
            if heartbeat is not None and not heartbeat.done():
                heartbeat.cancel()
            if heartbeat is not None:
                with suppress(asyncio.CancelledError, LeaseLost):
                    await heartbeat

    async def run_once(self) -> bool:
        messages = await self.broker.reclaim(
            self.worker_id,
            min_idle_ms=self.pending_idle_ms,
            count=1,
        )
        if not messages:
            messages = await self.broker.read(
                self.worker_id,
                count=1,
                block_ms=100,
            )
        if not messages:
            return False
        await self.handle(messages[0])
        return True
