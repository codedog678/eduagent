import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.distributed.expert_gateway import DurableExpertGateway
from core.distributed.expert_repository import ExpertBackpressure
from tests.distributed.test_expert_repository import (
    envelope,
    parent_claim,
    request_for,
)

pytestmark = pytest.mark.distributed_integration


class InlineGateway:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def execute(self, request):
        self.calls += 1
        return self.result


class GatewayRepository:
    def __init__(self, request, *, create_error=None, terminals=()):
        self.job = SimpleNamespace(id="job-1")
        self.request = request
        self.create_error = create_error
        self.terminals = list(terminals)
        self.create_calls = 0
        self.terminal_calls = 0

    async def create_or_replay(self, request):
        self.create_calls += 1
        if self.create_error is not None:
            raise self.create_error
        return self.job, False

    async def terminal(self, job_id, parent_token):
        assert job_id == self.job.id
        assert parent_token == self.request.authority.run_fencing_token
        self.terminal_calls += 1
        if self.terminals:
            return self.terminals.pop(0)
        return None


async def test_pre_accept_failure_can_fall_back_inline():
    request = request_for_stub()
    expected = envelope(request)
    inline = InlineGateway(expected)
    repository = GatewayRepository(
        request,
        create_error=ExpertBackpressure("queue full before accept"),
    )

    actual = await DurableExpertGateway(
        repository,
        inline,
        poll_seconds=0.001,
    ).execute(request)

    assert actual == expected
    assert inline.calls == 1


async def test_durable_accept_never_falls_back_and_polls_postgres():
    request = request_for_stub()
    expected = envelope(request)
    inline = InlineGateway(expected)
    repository = GatewayRepository(
        request,
        terminals=(None, None, expected),
    )

    actual = await DurableExpertGateway(
        repository,
        inline,
        poll_seconds=0.001,
    ).execute(request)

    assert actual == expected
    assert repository.terminal_calls == 3
    assert inline.calls == 0


async def test_error_after_durable_accept_does_not_fall_back():
    request = request_for_stub()
    inline = InlineGateway(envelope(request))

    class FailingPollRepository(GatewayRepository):
        async def terminal(self, job_id, parent_token):
            raise ConnectionError("poll failed after durable accept")

    with pytest.raises(ConnectionError, match="poll failed"):
        await DurableExpertGateway(
            FailingPollRepository(request),
            inline,
            poll_seconds=0.001,
        ).execute(request)
    assert inline.calls == 0


async def test_parent_cancellation_interrupts_postgres_wait():
    request = request_for_stub()
    cancelled = asyncio.Event()
    repository = GatewayRepository(request)
    gateway = DurableExpertGateway(
        repository,
        InlineGateway(envelope(request)),
        poll_seconds=0.001,
        cancelled=cancelled,
    )

    task = asyncio.create_task(gateway.execute(request))
    async with asyncio.timeout(1):
        while repository.terminal_calls == 0:
            await asyncio.sleep(0)
    cancelled.set()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_gateway_uses_real_postgres_terminal_truth(repo, expert_repo):
    _, claim = await parent_claim(repo, "gateway-pg-truth")
    request = request_for(claim)
    expected = envelope(request)
    inline = InlineGateway(expected)
    gateway = DurableExpertGateway(
        expert_repo,
        inline,
        poll_seconds=0.001,
    )

    task = asyncio.create_task(gateway.execute(request))
    async with asyncio.timeout(2):
        while True:
            jobs = await expert_repo.pending_outbox(1)
            if jobs:
                job_id = jobs[0].job_id
                break
            await asyncio.sleep(0.001)
    expert_claim = await expert_repo.claim(
        job_id,
        "expert-a",
        {request.role},
        lease_seconds=30,
    )
    receipt = await expert_repo.submit_result(
        job_id,
        "expert-a",
        expert_claim.fencing_token,
        expected,
    )

    assert receipt.accepted
    actual = await asyncio.wait_for(task, timeout=2)
    assert actual.input_hash == expected.input_hash
    assert actual.draft == expected.draft
    assert actual.usage == expected.usage
    assert actual.completed_at >= expected.completed_at
    assert inline.calls == 0


async def test_gateway_rejects_terminal_result_after_parent_lease_loss(
    repo,
    expert_repo,
):
    run, claim = await parent_claim(repo, "gateway-parent-stale")
    request = request_for(claim)
    expected = envelope(request)
    job, _ = await expert_repo.create_or_replay(request)
    expert_claim = await expert_repo.claim(
        job.id,
        "expert-a",
        {request.role},
        lease_seconds=30,
    )
    receipt = await expert_repo.submit_result(
        job.id,
        "expert-a",
        expert_claim.fencing_token,
        expected,
    )
    assert receipt.accepted
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    from core.distributed.expert_repository import ExpertFencingViolation

    class AcceptedRepository:
        async def create_or_replay(self, replay):
            assert replay == request
            return job, True

        async def terminal(self, job_id, parent_token):
            return await expert_repo.terminal(job_id, parent_token)

    with pytest.raises(ExpertFencingViolation, match="expired"):
        await DurableExpertGateway(
            AcceptedRepository(),
            InlineGateway(expected),
            poll_seconds=0.001,
        ).execute(request)


def request_for_stub():
    from tests.distributed.test_expert_engine import request

    return request()
