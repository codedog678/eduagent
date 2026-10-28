"""单事件循环内的学习者互斥与远程模型准入。"""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from core.run_context import RunExhausted, active_run


class QueueTimeout(RunExhausted):
    """排队未获得执行权；没有发出远程请求。"""


@dataclass
class _LockEntry:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class KeyedLocks:
    def __init__(self):
        self._entries: dict[str, _LockEntry] = {}

    @asynccontextmanager
    async def hold(self, key, timeout=None):
        entry = self._entries.setdefault(key, _LockEntry())
        entry.users += 1
        acquired = False
        started = time.monotonic()
        try:
            # 超时仅覆盖排队，不能误把业务自身的 TimeoutError 当作排队失败。
            try:
                async with asyncio.timeout(timeout):
                    await entry.lock.acquire()
            except TimeoutError:
                raise QueueTimeout("learner_queue_timeout") from None
            acquired = True
            yield round((time.monotonic() - started) * 1000)
        finally:
            if acquired:
                entry.lock.release()
            entry.users -= 1
            if not entry.users:
                del self._entries[key]


class ModelLimiter:
    def __init__(self, limit, queue_timeout):
        self.limit = limit
        self.queue_timeout = queue_timeout
        self._semaphore = asyncio.Semaphore(limit)
        self.active = 0
        self.waiting = 0
        self.queue_timeouts = 0

    def snapshot(self):
        return {"limit": self.limit, "active": self.active, "waiting": self.waiting,
                "queue_timeout_seconds": self.queue_timeout,
                "queue_timeouts": self.queue_timeouts}

    @asynccontextmanager
    async def slot(self, kind):
        ctx = active_run.get()
        timeout = min(self.queue_timeout, ctx.remaining()) if ctx else self.queue_timeout
        started = time.monotonic()
        self.waiting += 1
        acquired = False
        status = "cancelled"
        try:
            try:
                async with asyncio.timeout(timeout):
                    await self._semaphore.acquire()
                acquired = True
                status = "acquired"
            except TimeoutError:
                self.queue_timeouts += 1
                status = "timeout"
                if ctx:
                    ctx.remaining()
                raise QueueTimeout("model_queue_timeout") from None
            finally:
                self.waiting -= 1
                if ctx:
                    ctx.record("model_queue", ctx.role, resource=kind, status=status,
                               wait_ms=round((time.monotonic() - started) * 1000),
                               limit=self.limit, task_id=ctx.task_id)
            if ctx:
                ctx.remaining()
            self.active += 1
            try:
                yield
            finally:
                self.active -= 1
        finally:
            if acquired:
                self._semaphore.release()


def get_model_limiter():
    """同一服务循环共享额度；loop 关闭后一起回收，不跨 loop 复用信号量。"""
    from config.settings import settings
    loop = asyncio.get_running_loop()
    limiter = getattr(loop, "_eduagent_model_limiter", None)
    if limiter is None:
        limiter = ModelLimiter(settings.llm_max_concurrency, settings.llm_queue_timeout_seconds)
        loop._eduagent_model_limiter = limiter
    return limiter


@asynccontextmanager
async def model_slot(kind):
    async with get_model_limiter().slot(kind):
        yield
