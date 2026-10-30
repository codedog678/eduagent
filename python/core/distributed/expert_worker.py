"""Durable worker for one bounded, snapshot-only expert attempt."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from time import monotonic

from .expert_contracts import ExpertErrorCode, ExpertRole
from .expert_repository import (
    ExpertClaimReceipt,
    ExpertFailure,
    ExpertFencingViolation,
)


class ExpertLeaseLost(RuntimeError):
    pass


_RETRYABLE_ERRORS = {
    ExpertErrorCode.PROVIDER_TIMEOUT,
    ExpertErrorCode.PROVIDER_UNAVAILABLE,
}


class ExpertWorker:
    def __init__(
        self,
        worker_id,
        repository,
        broker,
        engine,
        *,
        roles: set[ExpertRole],
        lease_seconds: float,
        heartbeat_seconds: float,
        pending_idle_ms: int | None = None,
        poll_block_ms: int = 100,
        pause_before_result_seconds: float = 0,
        metrics=None,
    ) -> None:
        if not roles:
            raise ValueError("expert worker requires at least one role")
        if lease_seconds <= 0 or heartbeat_seconds <= 0:
            raise ValueError("expert lease intervals must be positive")
        if heartbeat_seconds >= lease_seconds:
            raise ValueError("heartbeat_seconds must be shorter than lease_seconds")
        if poll_block_ms < 1:
            raise ValueError("poll_block_ms must be positive")
        self.worker_id = worker_id
        self.repository = repository
        self.broker = broker
        self.engine = engine
        self.roles = roles
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.pending_idle_ms = (
            max(1, int(lease_seconds * 1000))
            if pending_idle_ms is None
            else pending_idle_ms
        )
        self.poll_block_ms = poll_block_ms
        self.pause_before_result_seconds = pause_before_result_seconds
        self.metrics = metrics

    async def _heartbeat(self, claim) -> None:
        try:
            while True:
                await asyncio.sleep(self.heartbeat_seconds)
                await self.repository.renew(
                    claim.job_id,
                    self.worker_id,
                    claim.fencing_token,
                    self.lease_seconds,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ExpertLeaseLost(
                f"expert lease heartbeat failed for {claim.job_id}"
            ) from exc

    @staticmethod
    async def _await_execution(execution, heartbeat):
        done, _ = await asyncio.wait(
            {execution, heartbeat},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            await heartbeat
        return await execution

    async def _execute_attempt(self, claim):
        consumed = await self.repository.consumed_usage(claim.job_id)
        return await self.engine.execute(
            claim.request,
            consumed=consumed,
        )

    async def handle(self, message) -> None:
        job_id = message.payload["job_id"]
        await self.repository.record_inbox(
            self.worker_id,
            message.event_key,
        )
        try:
            claim = await self.repository.claim(
                job_id,
                self.worker_id,
                self.roles,
                self.lease_seconds,
            )
        except ExpertFencingViolation:
            await self.broker.ack(message.redis_id)
            return
        if isinstance(claim, ExpertClaimReceipt):
            if (
                claim.rejection_code != "capability_mismatch"
                or claim.available_at is not None
            ):
                await self.broker.ack(message.redis_id)
            return

        execution = None
        heartbeat = None
        started = monotonic()
        try:
            execution = asyncio.create_task(
                self._execute_attempt(claim)
            )
            heartbeat = asyncio.create_task(self._heartbeat(claim))
            terminal = await self._await_execution(execution, heartbeat)
            if self.pause_before_result_seconds:
                await asyncio.sleep(self.pause_before_result_seconds)

            if (
                terminal.outcome == "failed"
                and terminal.error_code in _RETRYABLE_ERRORS
            ):
                await self.repository.fail_attempt(
                    job_id,
                    self.worker_id,
                    claim.fencing_token,
                    ExpertFailure(
                        code=terminal.error_code,
                        retryable=True,
                        usage=terminal.usage,
                        diagnostics=tuple(terminal.diagnostics),
                    ),
                )
                self._increment_retry(claim.request.role.value)
            else:
                receipt = await self.repository.submit_result(
                    job_id,
                    self.worker_id,
                    claim.fencing_token,
                    terminal,
                )
                self._increment_result(receipt)
            await self.broker.ack(message.redis_id)
            self._observe_attempt(monotonic() - started)
        except ExpertLeaseLost:
            return
        except ExpertFencingViolation:
            return
        except asyncio.CancelledError:
            raise
        finally:
            if execution is not None and not execution.done():
                execution.cancel()
                with suppress(asyncio.CancelledError):
                    await execution
            if heartbeat is not None and not heartbeat.done():
                heartbeat.cancel()
            if heartbeat is not None:
                with suppress(asyncio.CancelledError, ExpertLeaseLost):
                    await heartbeat

    def _observe_attempt(self, seconds: float) -> None:
        if self.metrics is None:
            return
        histogram = getattr(self.metrics, "expert_attempt_duration", None)
        if histogram is not None:
            with suppress(Exception):
                histogram.observe(seconds)

    def _increment_retry(self, role: str) -> None:
        if self.metrics is None:
            return
        counter = getattr(self.metrics, "expert_retries", None)
        if counter is not None:
            with suppress(Exception):
                counter.labels(role=role).inc()

    def _increment_result(self, receipt) -> None:
        if self.metrics is None:
            return
        counter = getattr(self.metrics, "expert_results", None)
        if counter is not None:
            with suppress(Exception):
                counter.labels(
                    disposition=receipt.disposition,
                    rejection_code=receipt.rejection_code or "",
                ).inc()

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
                block_ms=self.poll_block_ms,
            )
        if not messages:
            return False
        await self.handle(messages[0])
        return True
