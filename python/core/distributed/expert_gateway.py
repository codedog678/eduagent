"""Parent-side gateways for bounded expert execution."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import json
from time import monotonic
from typing import Any

from .expert_repository import ExpertBackpressure


class InlineExpertGateway:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    async def execute(self, request):
        return await self.engine.execute(request)


class DurableExpertGateway:
    """Accept once, then use PostgreSQL as the only result authority."""

    def __init__(
        self,
        repository: Any,
        inline: Any | None = None,
        *,
        poll_seconds: float = 0.25,
        cancelled: asyncio.Event | Callable[[], bool] | None = None,
        metrics: Any | None = None,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.repository = repository
        self.inline = inline
        self.poll_seconds = poll_seconds
        self.cancelled = cancelled
        self.metrics = metrics

    async def execute(self, request):
        started = monotonic()
        self._observe_snapshot(request)
        try:
            job, _ = await self.repository.create_or_replay(request)
        except ExpertBackpressure:
            self._increment_backpressure(request.role.value)
            if self.inline is None:
                raise
            return await self.inline.execute(request)

        while True:
            if self._is_cancelled():
                raise asyncio.CancelledError
            terminal = await self.repository.terminal(
                job.id,
                request.authority.run_fencing_token,
            )
            if terminal is not None:
                self._observe_parent_wait(monotonic() - started)
                return terminal
            await self._wait_or_cancel()

    def _is_cancelled(self) -> bool:
        if self.cancelled is None:
            return False
        if isinstance(self.cancelled, asyncio.Event):
            return self.cancelled.is_set()
        return bool(self.cancelled())

    async def _wait_or_cancel(self) -> None:
        if not isinstance(self.cancelled, asyncio.Event):
            await asyncio.sleep(self.poll_seconds)
            return
        try:
            await asyncio.wait_for(
                self.cancelled.wait(),
                timeout=self.poll_seconds,
            )
        except TimeoutError:
            return
        raise asyncio.CancelledError

    def _observe_snapshot(self, request) -> None:
        if self.metrics is None:
            return
        metric = getattr(self.metrics, "expert_snapshot_bytes", None)
        if metric is not None:
            with suppress(Exception):
                size = len(
                    json.dumps(
                        request.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                metric.observe(size)

    def _observe_parent_wait(self, seconds: float) -> None:
        if self.metrics is None:
            return
        metric = getattr(self.metrics, "expert_parent_wait", None)
        if metric is not None:
            with suppress(Exception):
                metric.observe(seconds)

    def _increment_backpressure(self, role: str) -> None:
        if self.metrics is None:
            return
        metric = getattr(self.metrics, "expert_backpressure", None)
        if metric is not None:
            with suppress(Exception):
                metric.labels(role=role).inc()
