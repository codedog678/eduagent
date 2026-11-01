from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from core.distributed.broker import StreamMessage
from core.distributed.contracts import RunStatus
from core.distributed.models import DistributedRunAttempt, DistributedStep
from core.distributed.promotion_contracts import PolicyExecutionBinding
from core.distributed.repository import DistributedRunRepository, FencingViolation
from core.distributed.result_identity import ProtocolIdentityError
from core.distributed.worker import RunWorker
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_policy_assignment import (
    assignment_repo, candidate_head, token_for,
)

pytestmark = pytest.mark.distributed_integration

IDENTITY_FIELDS = (
    "deployment_id", "effective_policy_hash", "policy_cohort",
    "state_namespace", "rehearsal_id",
)
INVALID_CASES = [
    "no-result", "no-execution", "malformed-execution",
    "legacy-deployment-namespace",
    *[f"missing-{field}" for field in IDENTITY_FIELDS],
    *[f"wrong-{field}" for field in IDENTITY_FIELDS],
]


def invalid_result(binding, case):
    result = business_result(binding, ok=True)
    if case == "no-result":
        return None
    if case == "no-execution":
        return {"ok": True}
    if case == "malformed-execution":
        result["execution"] = []
    elif case == "legacy-deployment-namespace":
        for field in ("deployment_id", "state_namespace"):
            result["execution"].pop(field)
    else:
        action, field = case.split("-", 1)
        if action == "missing":
            result["execution"].pop(field)
        else:
            result["execution"][field] = {
                "deployment_id": "00000000-0000-0000-0000-000000000099",
                "effective_policy_hash": "f" * 64,
                "policy_cohort": "shadow",
                "state_namespace": (
                    "production" if binding.environment == "rehearsal"
                    else "rehearsal-forged"
                ),
                "rehearsal_id": "forged",
            }[field]
    return result


async def admit(repo, environment):
    row = await candidate_head(repo)
    request = spec(request_id="result-identity")
    run, _ = await repo.accept_with_replay(
        request,
        rehearsal_token=token_for(row, request_id=request.request_id)
        if environment == "rehearsal" else None,
    )
    repo._db_now = DistributedRunRepository._db_now
    return run, request, PolicyExecutionBinding.model_validate(run.policy_binding)


async def stored_step(repo, run_id):
    async with repo.session_factory() as session:
        return await session.scalar(select(DistributedStep).where(
            DistributedStep.run_id == run_id,
            DistributedStep.step_id == "business-execution",
        ))


class ResultExecutor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def execute(self, request, authority, binding):
        self.calls += 1
        return self.result


@pytest.mark.parametrize("environment", ["production", "rehearsal"])
@pytest.mark.parametrize("case", INVALID_CASES)
@pytest.mark.parametrize("boundary", ["complete_step", "complete"])
async def test_direct_repository_rejects_result_identity_atomically(
    assignment_repo, environment, case, boundary,
):
    repo = assignment_repo
    run, request, binding = await admit(repo, environment)
    claim = await repo.claim(run.id, "owner", 30)
    await repo.start_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token,
    )
    if boundary == "complete":
        await repo.transition_committing(run.id, claim.fencing_token)
    before = await repo.get(run.id)
    lease_before = await repo.lease(run.id)
    result = invalid_result(binding, case)
    original = deepcopy(result)
    with pytest.raises(ProtocolIdentityError, match="result identity"):
        if boundary == "complete_step":
            await repo.complete_step(
                run.id, "business-execution", request.input_hash,
                claim.fencing_token, result,
            )
        else:
            await repo.complete(run.id, claim.fencing_token, result)
    after = await repo.get(run.id)
    assert after.public_dict() == before.public_dict()
    assert after.policy_binding == run.policy_binding
    assert after.updated_at == before.updated_at
    assert after.result is None
    lease_after = await repo.lease(run.id)
    assert lease_after.owner == lease_before.owner == "owner"
    assert lease_after.expires_at == lease_before.expires_at
    step = await stored_step(repo, run.id)
    assert step.status == RunStatus.RUNNING
    assert step.result is None and step.finished_at is None
    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)
        assert attempt.status == RunStatus.RUNNING
        assert attempt.finished_at is None
    assert result == original


@pytest.mark.parametrize("environment", ["production", "rehearsal"])
@pytest.mark.parametrize("case", INVALID_CASES)
@pytest.mark.parametrize("cached", [False, True])
async def test_worker_identity_failure_is_terminal_without_public_commit_or_retry(
    assignment_repo, broker, monkeypatch, environment, case, cached,
):
    repo = assignment_repo
    run, request, binding = await admit(repo, environment)
    result = invalid_result(binding, case)
    original = deepcopy(result)
    if cached:
        first = await repo.claim(run.id, "dead-owner", 30)
        await repo.start_step(
            run.id, "business-execution", request.input_hash, first.fencing_token,
        )
        # Model historical/forged PostgreSQL evidence, not a trusted new commit.
        async with repo.session_factory() as session, session.begin():
            step = await session.scalar(select(DistributedStep).where(
                DistributedStep.run_id == run.id,
            ).with_for_update())
            step.status = RunStatus.COMPLETED
            step.result = result
            step.finished_at = datetime(2026, 11, 1, tzinfo=UTC)
        await repo.force_lease_expiry(
            run.id, datetime.now(UTC) - timedelta(seconds=1),
        )
        assert await repo.requeue_expired(datetime.now(UTC)) == [run.id]
    outbox_before = [row.event_key for row in await repo.pending_outbox(10)]
    commit_calls = []
    for method_name in ("complete_step", "transition_committing", "complete"):
        original_method = getattr(repo, method_name)

        async def record_commit(*args, _name=method_name, _method=original_method, **kwargs):
            commit_calls.append(_name)
            return await _method(*args, **kwargs)

        monkeypatch.setattr(repo, method_name, record_commit)
    executor = ResultExecutor(result)
    worker = RunWorker(
        "owner", repo, broker, executor, allowed_environment=environment,
        lease_seconds=30, heartbeat_seconds=1, max_attempts=3,
    )
    await worker.handle(StreamMessage("1-0", "identity-check", {"run_id": run.id}))
    failed = await repo.get(run.id)
    assert failed.status == RunStatus.TERMINAL_FAILED
    assert failed.error_code == "ProtocolIdentityError"
    assert failed.result is None and failed.public_dict()["result"] is None
    assert failed.policy_binding == run.policy_binding
    assert failed.attempt_count == (2 if cached else 1)
    assert executor.calls == (0 if cached else 1)
    assert commit_calls == []
    assert [row.event_key for row in await repo.pending_outbox(10)] == outbox_before
    lease = await repo.lease(run.id)
    assert lease.owner is None and lease.expires_at is None
    step = await stored_step(repo, run.id)
    assert step.result == (original if cached else None)
    assert step.status == (RunStatus.COMPLETED if cached else RunStatus.RUNNING)
    assert result == original
    # Duplicate delivery cannot retry or duplicate the business commit.
    await worker.handle(StreamMessage("2-0", "identity-duplicate", {"run_id": run.id}))
    assert executor.calls == (0 if cached else 1)
    assert (await repo.get(run.id)).attempt_count == failed.attempt_count


@pytest.mark.parametrize("case", INVALID_CASES)
@pytest.mark.parametrize("invalid_source", ["caller", "cache"])
async def test_completed_step_replay_validates_both_caller_and_cached_identity(
    assignment_repo, case, invalid_source,
):
    repo = assignment_repo
    run, request, binding = await admit(repo, "rehearsal")
    claim = await repo.claim(run.id, "owner", 30)
    await repo.start_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token,
    )
    valid = business_result(binding, ok=True)
    await repo.complete_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token, valid,
    )
    invalid = invalid_result(binding, case)
    if invalid_source == "cache":
        async with repo.session_factory() as session, session.begin():
            step = await session.scalar(select(DistributedStep).where(
                DistributedStep.run_id == run.id,
            ).with_for_update())
            step.result = invalid
    before = await stored_step(repo, run.id)
    with pytest.raises(ProtocolIdentityError, match="result identity"):
        await repo.complete_step(
            run.id, "business-execution", request.input_hash, claim.fencing_token,
            invalid if invalid_source == "caller" else valid,
        )
    after = await stored_step(repo, run.id)
    assert after.result == before.result
    assert after.finished_at == before.finished_at
    assert (await repo.get(run.id)).result is None


async def test_valid_completed_step_replay_does_not_replace_business_result(repo):
    run = await repo.accept(spec())
    claim = await repo.claim(run.id, "owner", 30)
    request = claim.to_request()
    await repo.start_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token,
    )
    original = business_result(claim.policy_binding, business_commit="original")
    first = await repo.complete_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token, original,
    )
    replay = await repo.complete_step(
        run.id, "business-execution", request.input_hash, claim.fencing_token,
        business_result(claim.policy_binding, business_commit="replacement"),
    )
    assert replay.result == original
    assert replay.id == first.id
    assert replay.finished_at == first.finished_at


async def test_unclaimed_running_step_still_rejects_stale_token_before_identity(repo):
    run = await repo.accept(spec())
    first = await repo.claim(run.id, "first", 30)
    request = first.to_request()
    await repo.start_step(
        run.id, "business-execution", request.input_hash, first.fencing_token,
    )
    await repo.fail(run.id, first.fencing_token, "interrupted", retryable=True)
    second = await repo.claim(run.id, "second", 30)
    with pytest.raises(FencingViolation, match="stale token"):
        await repo.complete_step(
            run.id, "business-execution", request.input_hash, second.fencing_token, {},
        )
    step = await stored_step(repo, run.id)
    assert step.fencing_token == first.fencing_token
    assert step.result is None and step.finished_at is None


async def test_valid_cached_takeover_uses_frozen_binding_after_head_change(
    assignment_repo, broker,
):
    repo = assignment_repo
    run, request, binding = await admit(repo, "rehearsal")
    first = await repo.claim(run.id, "dead-owner", 30)
    await repo.start_step(
        run.id, "business-execution", request.input_hash, first.fencing_token,
    )
    result = business_result(binding, ok=True)
    completed_step = await repo.complete_step(
        run.id, "business-execution", request.input_hash, first.fencing_token, result,
    )
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    await repo.force_lease_expiry(
        run.id, datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await repo.requeue_expired(datetime.now(UTC)) == [run.id]
    executor = ResultExecutor(None)
    worker = RunWorker(
        "takeover", repo, broker, executor, allowed_environment="rehearsal",
        lease_seconds=30, heartbeat_seconds=1, max_attempts=3,
    )
    await worker.handle(StreamMessage("1-0", "valid-cache", {"run_id": run.id}))
    completed = await repo.get(run.id)
    assert completed.status == RunStatus.COMPLETED
    assert completed.result == result
    assert completed.policy_binding == run.policy_binding
    assert completed.attempt_count == 2
    assert executor.calls == 0
    unchanged = await stored_step(repo, run.id)
    assert unchanged.finished_at == completed_step.finished_at
    assert unchanged.fencing_token == first.fencing_token
    await worker.handle(StreamMessage("2-0", "valid-duplicate", {"run_id": run.id}))
    assert executor.calls == 0
    replay, hit = await repo.accept_with_replay(request, rehearsal_token="ignored")
    assert hit and replay.result == result
