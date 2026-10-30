import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.distributed.expert_contracts import (
    ExpertErrorCode,
    ExpertRole,
    ExpertTerminalEnvelope,
)
from core.distributed.expert_dispatcher import ExpertDispatcher
from core.distributed.expert_reaper import ExpertReaper
from core.distributed.expert_repository import (
    ExpertClaimReceipt,
    ExpertFencingViolation,
)
from core.distributed.expert_worker import ExpertWorker
from tests.distributed.test_expert_repository import (
    envelope,
    make_expert_outbox_due,
    parent_claim,
    request_for,
)

pytestmark = pytest.mark.distributed_integration


class Message:
    redis_id = "1-0"
    event_key = "expert:job-1:accepted"
    payload = {"job_id": "job-1", "role": "Assessment"}


class RecordingBroker:
    def __init__(self):
        self.acked = []

    async def ack(self, redis_id):
        self.acked.append(redis_id)
        return True


class BlockingEngine:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def execute(self, request, consumed=None):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class ImmediateEngine:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def execute(self, request, consumed=None):
        self.calls += 1
        return self.result


class WorkerRepository:
    def __init__(self, request, result):
        self.request = request
        self.result = result
        self.renew_error = None
        self.submitted = []
        self.failed = []
        self.inbox = []
        self.claim_result = SimpleNamespace(
            job_id="job-1",
            request=request,
            worker_id="expert-a",
            attempt_count=1,
            fencing_token=7,
        )

    async def record_inbox(self, consumer, event_key):
        self.inbox.append((consumer, event_key))
        return True

    async def claim(self, job_id, worker_id, roles, lease_seconds):
        return self.claim_result

    async def renew(self, job_id, worker_id, token, lease_seconds):
        if self.renew_error is not None:
            raise self.renew_error

    async def consumed_usage(self, job_id):
        return None

    async def submit_result(self, job_id, worker_id, token, result):
        self.submitted.append(result)
        return SimpleNamespace(
            accepted=True,
            disposition="accepted",
            rejection_code=None,
        )

    async def fail_attempt(self, job_id, worker_id, token, failure):
        self.failed.append(failure)
        return SimpleNamespace(status="queued")


async def test_worker_acks_only_after_repository_result_decision():
    request = request_for_stub()
    result = envelope(request)
    repository = WorkerRepository(request, result)
    decision = asyncio.Event()

    async def blocked_submit(*args):
        await decision.wait()
        return SimpleNamespace(
            accepted=True,
            disposition="accepted",
            rejection_code=None,
        )

    repository.submit_result = blocked_submit
    broker = RecordingBroker()
    worker = ExpertWorker(
        "expert-a",
        repository,
        broker,
        ImmediateEngine(result),
        roles={ExpertRole.ASSESSMENT},
        lease_seconds=5,
        heartbeat_seconds=0.1,
    )

    task = asyncio.create_task(worker.handle(Message()))
    await asyncio.sleep(0.02)
    assert broker.acked == []
    decision.set()
    await asyncio.wait_for(task, timeout=1)
    assert broker.acked == ["1-0"]


async def test_worker_heartbeat_loss_cancels_engine_and_leaves_unacked():
    request = request_for_stub()
    repository = WorkerRepository(request, envelope(request))
    repository.renew_error = ExpertFencingViolation("parent lease lost")
    broker = RecordingBroker()
    engine = BlockingEngine()
    worker = ExpertWorker(
        "expert-a",
        repository,
        broker,
        engine,
        roles={ExpertRole.ASSESSMENT},
        lease_seconds=1,
        heartbeat_seconds=0.01,
    )

    await asyncio.wait_for(worker.handle(Message()), timeout=1)

    assert engine.cancelled.is_set()
    assert broker.acked == []
    assert repository.submitted == []


async def test_capability_rejection_is_left_for_compatible_worker():
    request = request_for_stub()
    result = envelope(request)
    repository = WorkerRepository(request, result)
    repository.claim_result = ExpertClaimReceipt(
        job_id="job-1",
        claimed=False,
        rejection_code="capability_mismatch",
        available_at=datetime.now(UTC) + timedelta(seconds=0.1),
    )
    engine = ImmediateEngine(result)
    broker = RecordingBroker()
    worker = ExpertWorker(
        "expert-a",
        repository,
        broker,
        engine,
        roles={ExpertRole.CURRICULUM},
        lease_seconds=5,
        heartbeat_seconds=0.1,
    )

    await worker.handle(Message())

    assert engine.calls == 0
    assert broker.acked == ["1-0"]


@pytest.mark.parametrize(
    ("code", "retryable"),
    [
        (ExpertErrorCode.PROVIDER_TIMEOUT, True),
        (ExpertErrorCode.PROVIDER_UNAVAILABLE, True),
        (ExpertErrorCode.EXPERT_SCHEMA_INVALID, False),
        (ExpertErrorCode.BUDGET_EXHAUSTED, False),
        (ExpertErrorCode.EXPERT_ACTION_NOT_ALLOWED, False),
    ],
)
async def test_worker_applies_frozen_retry_taxonomy(code, retryable):
    request = request_for_stub()
    failed = ExpertTerminalEnvelope(
        step_id=request.step_id,
        role=request.role,
        input_hash=request.input_hash,
        outcome="failed",
        usage=envelope(request).usage,
        completed_at=datetime.now(UTC),
        error_code=code,
    )
    repository = WorkerRepository(request, failed)
    broker = RecordingBroker()
    worker = ExpertWorker(
        "expert-a",
        repository,
        broker,
        ImmediateEngine(failed),
        roles={ExpertRole.ASSESSMENT},
        lease_seconds=5,
        heartbeat_seconds=0.1,
    )

    await worker.handle(Message())

    if retryable:
        assert len(repository.failed) == 1
        assert repository.failed[0].retryable
        assert repository.submitted == []
    else:
        assert repository.failed == []
        assert repository.submitted == [failed]
    assert broker.acked == ["1-0"]


async def test_delayed_outbox_is_not_published_early(
    repo,
    expert_repo,
    expert_broker,
):
    _, parent = await parent_claim(repo, "delayed-outbox")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    claim = await expert_repo.claim(
        job.id,
        "expert-a",
        {request.role},
        lease_seconds=30,
    )
    await expert_repo.force_lease_expiry(
        job.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await ExpertReaper(expert_repo).reap_once() == [job.id]

    dispatcher = ExpertDispatcher(expert_repo, expert_broker)
    assert await dispatcher.dispatch_once() == 1
    messages = await expert_broker.read("expert-b", count=10, block_ms=10)
    assert len(messages) == 1
    assert messages[0].event_key.endswith(":accepted")
    assert claim.fencing_token == 1

    await make_expert_outbox_due(repo, job.id)
    assert await dispatcher.dispatch_once() == 1
    retry = await expert_broker.read("expert-b", count=10, block_ms=10)
    assert len(retry) == 1
    assert ":lease-expired:" in retry[0].event_key


async def test_capability_mismatch_is_requeued_for_compatible_worker(
    repo,
    expert_repo,
    expert_broker,
):
    _, parent = await parent_claim(repo, "capability-requeue")
    request = request_for(parent)
    expected = envelope(request)
    job, _ = await expert_repo.create_or_replay(request)
    dispatcher = ExpertDispatcher(expert_repo, expert_broker)
    assert await dispatcher.dispatch_once() == 1

    incompatible = ExpertWorker(
        "tutor-only",
        expert_repo,
        expert_broker,
        ImmediateEngine(expected),
        roles={ExpertRole.TUTOR},
        lease_seconds=5,
        heartbeat_seconds=0.1,
        pending_idle_ms=1,
    )
    assert await incompatible.run_once()
    assert (await expert_repo.get(job.id)).attempt_count == 0

    await make_expert_outbox_due(repo, job.id)
    assert await dispatcher.dispatch_once() == 1
    engine = ImmediateEngine(expected)
    compatible = ExpertWorker(
        "assessment-worker",
        expert_repo,
        expert_broker,
        engine,
        roles={ExpertRole.ASSESSMENT},
        lease_seconds=5,
        heartbeat_seconds=0.1,
        pending_idle_ms=1,
    )
    assert await compatible.run_once()

    assert engine.calls == 1
    assert await expert_repo.accepted_result_count(job.id) == 1


async def test_duplicate_redis_delivery_produces_one_accepted_result(
    repo,
    expert_repo,
    expert_broker,
):
    _, parent = await parent_claim(repo, "duplicate-delivery")
    request = request_for(parent)
    expected = envelope(request)
    job, _ = await expert_repo.create_or_replay(request)
    row = (await expert_repo.pending_outbox(1))[0]
    await expert_broker.publish(row.event_key, row.payload)
    await expert_broker.publish(row.event_key, row.payload)
    engine = ImmediateEngine(expected)
    worker = ExpertWorker(
        "expert-a",
        expert_repo,
        expert_broker,
        engine,
        roles={request.role},
        lease_seconds=30,
        heartbeat_seconds=1,
        pending_idle_ms=1,
    )

    assert await worker.run_once()
    assert await worker.run_once()

    assert await expert_repo.accepted_result_count(job.id) == 1
    assert engine.calls == 1


async def test_stale_result_is_retained_and_acked(
    repo,
    expert_repo,
    expert_broker,
):
    _, parent = await parent_claim(repo, "stale-result-worker")
    request = request_for(parent)
    expected = envelope(request)
    job, _ = await expert_repo.create_or_replay(request)
    row = (await expert_repo.pending_outbox(1))[0]
    await expert_broker.publish(row.event_key, row.payload)
    worker = ExpertWorker(
        "expert-a",
        expert_repo,
        expert_broker,
        ImmediateEngine(expected),
        roles={request.role},
        lease_seconds=30,
        heartbeat_seconds=1,
        pause_before_result_seconds=0.1,
    )

    task = asyncio.create_task(worker.run_once())
    async with asyncio.timeout(1):
        while (await expert_repo.get(job.id)).status != "running":
            await asyncio.sleep(0.001)
    await repo.cancel(str(request.authority.distributed_run_id))
    assert await asyncio.wait_for(task, timeout=2)

    assert await expert_repo.result_count(job.id) == 1
    assert await expert_repo.accepted_result_count(job.id) == 0
    assert await expert_broker.pending_count() == 0


def request_for_stub():
    from tests.distributed.test_expert_engine import request

    return request()
