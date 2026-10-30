import asyncio
from types import SimpleNamespace

import pytest

from core.distributed.contracts import RunStatus
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.expert_dispatcher import ExpertDispatcher
from core.distributed.expert_gateway import DurableExpertGateway
from core.distributed.expert_worker import ExpertWorker
from core.distributed.worker import RunWorker
from tests.distributed.test_expert_repository import envelope, request_for
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


class AuthorityExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.authority = None

    async def execute(self, request, authority):
        self.authority = authority
        self.started.set()
        await self.release.wait()
        return {"ok": True}


class GatewayExecutor:
    def __init__(self, gateway):
        self.gateway = gateway
        self.request = None
        self.envelope = None

    async def execute(self, run_request, authority):
        claim = SimpleNamespace(
            run_id=str(authority.distributed_run_id),
            fencing_token=authority.run_fencing_token,
            trace_id=authority.trace_id,
            attempt_count=authority.attempt_number,
            worker_id=authority.worker_id,
            deadline_at=authority.parent_deadline_at,
            learner_id=run_request.learner_id,
        )
        self.request = request_for(claim)
        self.envelope = await self.gateway.execute(self.request)
        return {"expert_outcome": self.envelope.outcome}


class ImmediateExpertEngine:
    async def execute(self, request, consumed=None):
        return envelope(request)


async def test_run_worker_passes_current_claim_authority_and_renews_wait(
    repo,
    broker,
):
    run = await repo.accept(spec(request_id="authority-injection"))
    assert await OutboxDispatcher(repo, broker).dispatch_once() == 1
    executor = AuthorityExecutor()
    worker = RunWorker(
        "parent-worker",
        repo,
        broker,
        executor,
        lease_seconds=2,
        heartbeat_seconds=0.05,
        max_attempts=3,
    )

    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(executor.started.wait(), timeout=2)
    authority = executor.authority
    assert str(authority.distributed_run_id) == run.id
    assert authority.worker_id == "parent-worker"
    assert authority.run_fencing_token == 1
    assert authority.attempt_number == 1
    first = await repo.lease(run.id)
    await asyncio.sleep(0.15)
    second = await repo.lease(run.id)
    assert second.expires_at > first.expires_at

    executor.release.set()
    assert await asyncio.wait_for(task, timeout=2)
    assert (await repo.get(run.id)).status == RunStatus.COMPLETED


async def test_parent_waits_durably_then_completes_after_expert_result(
    repo,
    expert_repo,
    broker,
    expert_broker,
):
    run = await repo.accept(spec(request_id="durable-expert-wait"))
    assert await OutboxDispatcher(repo, broker).dispatch_once() == 1
    executor = GatewayExecutor(
        DurableExpertGateway(
            expert_repo,
            poll_seconds=0.005,
        )
    )
    parent = RunWorker(
        "parent-worker",
        repo,
        broker,
        executor,
        lease_seconds=2,
        heartbeat_seconds=0.05,
        max_attempts=3,
    )

    parent_task = asyncio.create_task(parent.run_once())
    async with asyncio.timeout(2):
        while (await repo.get(run.id)).status != RunStatus.WAITING_EXPERT:
            await asyncio.sleep(0.005)
    first = await repo.lease(run.id)
    await asyncio.sleep(0.15)
    second = await repo.lease(run.id)
    assert second.expires_at > first.expires_at

    assert await ExpertDispatcher(
        expert_repo,
        expert_broker,
    ).dispatch_once() == 1
    expert = ExpertWorker(
        "assessment-worker",
        expert_repo,
        expert_broker,
        ImmediateExpertEngine(),
        roles={executor.request.role},
        lease_seconds=1,
        heartbeat_seconds=0.1,
    )
    assert await expert.run_once()
    assert await asyncio.wait_for(parent_task, timeout=2)

    completed = await repo.get(run.id)
    assert completed.status == RunStatus.COMPLETED
    assert completed.result == {"expert_outcome": "succeeded"}
