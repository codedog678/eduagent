import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from core.distributed.contracts import RunStatus
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.executor import BusinessStoreBusy
from core.distributed.reaper import LeaseReaper
from core.distributed.repository import FencingViolation
from core.distributed.worker import RunWorker
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


class BlockingExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.calls = 0

    async def execute(self, request):
        self.calls += 1
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return {"ok": True}


class ImmediateExecutor:
    def __init__(self):
        self.calls = 0

    async def execute(self, request):
        self.calls += 1
        return {"request_id": request.request_id}


class BusyExecutor:
    async def execute(self, request):
        raise BusinessStoreBusy("business_store_busy")


class ForbiddenExecutor:
    async def execute(self, request):
        raise PermissionError("forbidden")


async def dispatch(repo, broker, request_id="worker"):
    run = await repo.accept(spec(request_id=request_id))
    assert await OutboxDispatcher(repo, broker).dispatch_once() == 1
    return run


async def wait_for_status(repo, run_id, status):
    async with asyncio.timeout(2):
        while True:
            run = await repo.get(run_id)
            if run is not None and run.status == status:
                return run
            await asyncio.sleep(0.01)


async def test_worker_renews_lease_while_executor_runs(repo, broker):
    run = await dispatch(repo, broker)
    executor = BlockingExecutor()
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        executor,
        lease_seconds=2,
        heartbeat_seconds=0.1,
        max_attempts=3,
    )

    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(executor.started.wait(), timeout=2)
    first = await repo.lease(run.id)
    await asyncio.sleep(0.35)
    second = await repo.lease(run.id)
    assert second.expires_at > first.expires_at
    executor.release.set()
    assert await asyncio.wait_for(task, timeout=2)

    completed = await repo.get(run.id)
    assert completed is not None
    assert completed.status == RunStatus.COMPLETED


async def test_inbox_is_observation_not_permission_to_skip(repo, broker):
    run = await dispatch(repo, broker, request_id="observed")
    event_key = f"run:{run.id}:accepted"
    assert await repo.record_inbox("worker-a", event_key)
    executor = ImmediateExecutor()
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        executor,
        lease_seconds=5,
        heartbeat_seconds=0.1,
        max_attempts=3,
    )

    assert await worker.run_once()
    completed = await repo.get(run.id)
    assert completed is not None
    assert completed.status == RunStatus.COMPLETED
    assert executor.calls == 1


async def test_worker_reclaims_pending_delivery(repo, broker):
    run = await dispatch(repo, broker, request_id="pending")
    delivered = await broker.read("dead-worker", count=1, block_ms=10)
    assert len(delivered) == 1
    await asyncio.sleep(0.01)
    executor = ImmediateExecutor()
    worker = RunWorker(
        "worker-b",
        repo,
        broker,
        executor,
        lease_seconds=5,
        heartbeat_seconds=0.1,
        max_attempts=3,
        pending_idle_ms=1,
    )

    assert await worker.run_once()
    completed = await repo.get(run.id)
    assert completed is not None
    assert completed.status == RunStatus.COMPLETED
    assert executor.calls == 1


async def test_heartbeat_lease_loss_cancels_execution_and_blocks_commit(
    repo,
    broker,
):
    run = await dispatch(repo, broker, request_id="cancelled")
    executor = BlockingExecutor()
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        executor,
        lease_seconds=2,
        heartbeat_seconds=0.05,
        max_attempts=3,
    )

    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(executor.started.wait(), timeout=2)
    await repo.cancel(run.id)
    assert await asyncio.wait_for(task, timeout=2)
    await asyncio.wait_for(executor.cancelled.wait(), timeout=2)

    cancelled = await repo.get(run.id)
    assert cancelled is not None
    assert cancelled.status == RunStatus.CANCELLED
    assert cancelled.result is None


async def test_lease_loss_after_execution_blocks_final_commit(repo, broker):
    run = await dispatch(repo, broker, request_id="cancel-commit")
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        ImmediateExecutor(),
        lease_seconds=2,
        heartbeat_seconds=0.05,
        max_attempts=3,
        pause_before_commit_seconds=0.25,
    )

    task = asyncio.create_task(worker.run_once())
    await wait_for_status(repo, run.id, RunStatus.COMMITTING)
    await repo.cancel(run.id)
    assert await asyncio.wait_for(task, timeout=2)

    cancelled = await repo.get(run.id)
    assert cancelled is not None
    assert cancelled.status == RunStatus.CANCELLED
    assert cancelled.result is None


async def test_busy_store_is_retryable_and_delivery_is_acked(repo, broker):
    run = await dispatch(repo, broker, request_id="busy")
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        BusyExecutor(),
        lease_seconds=5,
        heartbeat_seconds=0.1,
        max_attempts=3,
    )

    assert await worker.run_once()
    failed = await repo.get(run.id)
    assert failed is not None
    assert failed.status == RunStatus.RETRYABLE_FAILED
    assert failed.error_code == "business_store_busy"
    assert await broker.reclaim(
        "worker-b",
        min_idle_ms=0,
        count=10,
    ) == []


async def test_permission_failure_is_not_retried(repo, broker):
    run = await dispatch(repo, broker, request_id="forbidden")
    worker = RunWorker(
        "worker-a",
        repo,
        broker,
        ForbiddenExecutor(),
        lease_seconds=5,
        heartbeat_seconds=0.1,
        max_attempts=3,
    )

    assert await worker.run_once()
    failed = await repo.get(run.id)
    assert failed is not None
    assert failed.status == RunStatus.TERMINAL_FAILED
    assert failed.error_code == "PermissionError"
    assert await broker.reclaim(
        "worker-b",
        min_idle_ms=0,
        count=10,
    ) == []


async def test_stale_worker_cannot_commit_after_reap(repo):
    run = await repo.accept(spec(request_id="stale"))
    first = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await LeaseReaper(repo).reap_once() == [run.id]
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)

    with pytest.raises(FencingViolation):
        await repo.complete(
            run.id,
            first.fencing_token,
            {"owner": "a"},
        )
    await repo.transition_committing(run.id, second.fencing_token)
    completed = await repo.complete(
        run.id,
        second.fencing_token,
        {"owner": "b"},
    )
    assert completed.status == RunStatus.COMPLETED
