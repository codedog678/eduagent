import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from core.distributed.contracts import RunStatus
from core.distributed.expert_contracts import (
    AssessmentCompleted,
    ExpertBudget,
    ExpertErrorCode,
    ExpertJobRequest,
    ExpertRole,
    ExpertSnapshot,
    ExpertTerminalEnvelope,
    ExpertUsage,
    RunExecutionAuthority,
)
from core.distributed.expert_models import (
    DistributedExpertJob,
    DistributedExpertOutbox,
    DistributedExpertResult,
)
from core.distributed.expert_repository import (
    ExpertBackpressure,
    ExpertFailure,
    ExpertFencingViolation,
    ExpertJobRepository,
    ExpertRequestConflict,
)
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


def usage(
    *,
    model_calls: int = 1,
    tool_calls: int = 0,
    input_tokens: int | None = 10,
    output_tokens: int | None = 5,
    cost: str | None = "0.01",
) -> ExpertUsage:
    return ExpertUsage(
        model_calls=model_calls,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=Decimal(cost) if cost is not None else None,
        provider="test-provider",
        model="test-model",
    )


def request_for(
    claim,
    *,
    logical_key: str = "plan:1:assessment",
    role: ExpertRole = ExpertRole.ASSESSMENT,
    objective: str = "Assess current understanding",
    deadline_at: datetime | None = None,
) -> ExpertJobRequest:
    now = datetime.now(UTC)
    deadline = deadline_at or min(
        claim.deadline_at,
        now + timedelta(minutes=1),
    )
    snapshot = ExpertSnapshot(
        learner_id=claim.learner_id,
        knowledge_id="knowledge-1",
        current_input="Explain the concept",
        goal="Assess understanding",
        effective_policy_hash="a" * 64,
    )
    return ExpertJobRequest(
        logical_key=logical_key,
        learner_id=claim.learner_id,
        step_id=f"step-{role.value.lower()}",
        role=role,
        objective=objective,
        plan_id="plan-1",
        plan_version=1,
        snapshot=snapshot,
        budget=ExpertBudget(
            max_model_calls=3,
            max_tool_calls=4,
            max_output_tokens=800,
            max_context_tokens=6000,
            max_attempts=3,
            deadline_at=deadline,
        ),
        authority=RunExecutionAuthority(
            distributed_run_id=claim.run_id,
            run_fencing_token=claim.fencing_token,
            trace_id=claim.trace_id,
            attempt_number=claim.attempt_count,
            worker_id="parent-worker",
            parent_deadline_at=claim.deadline_at,
        ),
    )


def envelope(request: ExpertJobRequest, *, consumed=None):
    return ExpertTerminalEnvelope(
        step_id=request.step_id,
        role=request.role,
        input_hash=request.input_hash,
        outcome="succeeded",
        draft=AssessmentCompleted(
            status="completed",
            findings=["Understands the core concept"],
        ),
        usage=consumed or usage(),
        completed_at=datetime.now(UTC),
    )


async def parent_claim(repo, request_id: str = "expert-parent"):
    run = await repo.accept(spec(request_id=request_id))
    claim = await repo.claim(run.id, "parent-worker", lease_seconds=120)
    return run, claim


async def test_create_is_idempotent_and_hash_conflict_is_rejected(repo, expert_repo):
    run, claim = await parent_claim(repo)
    request = request_for(claim)

    first, replayed = await expert_repo.create_or_replay(request)
    second, replayed_again = await expert_repo.create_or_replay(request)

    assert first.id == second.id
    assert not replayed
    assert replayed_again
    with pytest.raises(ExpertRequestConflict):
        await expert_repo.create_or_replay(
            request_for(claim, objective="Different objective")
        )
    waiting = await repo.get(run.id)
    assert waiting is not None
    assert waiting.status == RunStatus.WAITING_EXPERT


async def test_parent_token_and_persisted_deadline_are_authoritative(repo, expert_repo):
    _, claim = await parent_claim(repo, "authority")
    stale = request_for(claim).model_copy(
        update={
            "authority": request_for(claim).authority.model_copy(
                update={"run_fencing_token": claim.fencing_token + 1}
            )
        }
    )
    with pytest.raises(ExpertFencingViolation):
        await expert_repo.create_or_replay(stale)

    after_parent = request_for(claim).model_copy(
        update={
            "budget": request_for(claim).budget.model_copy(
                update={"deadline_at": claim.deadline_at + timedelta(seconds=1)}
            )
        }
    )
    with pytest.raises(ExpertFencingViolation, match="deadline"):
        await expert_repo.create_or_replay(after_parent)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("worker_id", "forged-parent", "worker identity"),
        ("trace_id", "f" * 32, "trace identity"),
    ],
)
async def test_parent_identity_fields_are_authoritative(
    repo,
    expert_repo,
    field,
    value,
    message,
):
    _, claim = await parent_claim(repo, f"identity-{field}")
    request = request_for(claim)
    forged = request.model_copy(
        update={
            "authority": request.authority.model_copy(
                update={field: value}
            )
        }
    )

    with pytest.raises(ExpertFencingViolation, match=message):
        await expert_repo.create_or_replay(forged)


async def test_parent_learner_scope_is_authoritative(repo, expert_repo):
    _, claim = await parent_claim(repo, "learner-scope")
    request = request_for(claim)
    foreign_snapshot = request.snapshot.model_copy(
        update={"learner_id": "foreign-learner"}
    )
    forged = request.model_copy(
        update={
            "learner_id": "foreign-learner",
            "snapshot": foreign_snapshot,
        }
    )

    with pytest.raises(ExpertFencingViolation, match="learner scope"):
        await expert_repo.create_or_replay(forged)


async def test_one_active_job_per_parent_and_role_queue_limit(repo):
    limited = ExpertJobRepository(
        repo.session_factory,
        queued_limit_per_role=1,
    )
    _, first_claim = await parent_claim(repo, "limit-a")
    _, second_claim = await parent_claim(repo, "limit-b")
    await limited.create_or_replay(request_for(first_claim))

    with pytest.raises(ExpertBackpressure, match="role queue"):
        await limited.create_or_replay(
            request_for(second_claim, logical_key="second")
        )
    with pytest.raises(ExpertBackpressure, match="active job"):
        await limited.create_or_replay(
            request_for(first_claim, logical_key="same-parent-second")
        )


async def test_concurrent_role_admission_obeys_advisory_queue_limit(repo):
    limited = ExpertJobRepository(
        repo.session_factory,
        queued_limit_per_role=1,
    )
    _, parent_a = await parent_claim(repo, "advisory-a")
    _, parent_b = await parent_claim(repo, "advisory-b")

    outcomes = await asyncio.gather(
        limited.create_or_replay(
            request_for(parent_a, logical_key="advisory-a")
        ),
        limited.create_or_replay(
            request_for(parent_b, logical_key="advisory-b")
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(item, tuple) for item in outcomes) == 1
    assert sum(isinstance(item, ExpertBackpressure) for item in outcomes) == 1


async def test_concurrent_cross_role_admission_obeys_global_payload_limit(repo):
    _, parent_a = await parent_claim(repo, "bytes-a")
    _, parent_b = await parent_claim(repo, "bytes-b")
    assessment = request_for(parent_a, logical_key="bytes-a")
    tutor = request_for(
        parent_b,
        logical_key="bytes-b",
        role=ExpertRole.TUTOR,
    )
    assessment_bytes = len(
        assessment.model_dump_json().encode("utf-8")
    )
    tutor_bytes = len(tutor.model_dump_json().encode("utf-8"))
    limited = ExpertJobRepository(
        repo.session_factory,
        queued_payload_bytes_limit=max(assessment_bytes, tutor_bytes) + 32,
    )

    outcomes = await asyncio.gather(
        limited.create_or_replay(assessment),
        limited.create_or_replay(tutor),
        return_exceptions=True,
    )

    assert sum(isinstance(item, tuple) for item in outcomes) == 1
    assert sum(isinstance(item, ExpertBackpressure) for item in outcomes) == 1


async def test_capability_mismatch_does_not_consume_attempt(repo, expert_repo):
    _, parent = await parent_claim(repo, "capability")
    job, _ = await expert_repo.create_or_replay(request_for(parent))

    receipt = await expert_repo.claim(
        job.id,
        "tutor-only",
        {ExpertRole.TUTOR},
        lease_seconds=30,
    )

    assert not receipt.claimed
    assert receipt.rejection_code == "capability_mismatch"
    stored = await expert_repo.get(job.id)
    assert stored.attempt_count == 0
    assert stored.status == "queued"


async def test_claim_renew_and_running_admission_are_fenced(repo):
    limited = ExpertJobRepository(
        repo.session_factory,
        running_limit_per_role=1,
    )
    _, parent_a = await parent_claim(repo, "running-a")
    _, parent_b = await parent_claim(repo, "running-b")
    first, _ = await limited.create_or_replay(request_for(parent_a))
    second, _ = await limited.create_or_replay(
        request_for(parent_b, logical_key="running-second")
    )

    claim = await limited.claim(
        first.id,
        "expert-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    assert claim.fencing_token == 1
    renewed = await limited.renew(
        first.id,
        "expert-a",
        claim.fencing_token,
        lease_seconds=45,
    )
    assert renewed.fencing_token == claim.fencing_token
    denied = await limited.claim(
        second.id,
        "expert-b",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    assert not denied.claimed
    assert denied.rejection_code == "running_limit"
    assert denied.available_at is not None
    assert (await limited.get(second.id)).attempt_count == 0


async def test_result_race_retains_rejected_stale_attempt(repo, expert_repo):
    _, parent = await parent_claim(repo, "result-race")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    first = await expert_repo.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    await expert_repo.force_lease_expiry(
        job.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    await expert_repo.reap_expired()
    second = await expert_repo.claim(
        job.id,
        "worker-b",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )

    receipts = await asyncio.gather(
        expert_repo.submit_result(
            job.id,
            "worker-a",
            first.fencing_token,
            envelope(request),
        ),
        expert_repo.submit_result(
            job.id,
            "worker-b",
            second.fencing_token,
            envelope(request),
        ),
    )

    assert sum(item.accepted for item in receipts) == 1
    assert await expert_repo.accepted_result_count(job.id) == 1
    assert await expert_repo.result_count(job.id) == 2


async def test_late_result_is_append_only_and_does_not_mutate_job(repo, expert_repo):
    _, parent = await parent_claim(repo, "late")
    deadline = datetime.now(UTC) + timedelta(seconds=2)
    request = request_for(parent, deadline_at=deadline)
    job, _ = await expert_repo.create_or_replay(request)
    claim = await expert_repo.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    await expert_repo.force_job_deadline(
        job.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    receipt = await expert_repo.submit_result(
        job.id,
        "worker-a",
        claim.fencing_token,
        envelope(request),
    )

    assert not receipt.accepted
    assert receipt.rejection_code == "deadline_expired"
    assert (await expert_repo.get(job.id)).status == "running"
    assert await expert_repo.result_count(job.id) == 1


async def test_mismatched_step_result_is_rejected_append_only(repo, expert_repo):
    _, parent = await parent_claim(repo, "step-mismatch")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    claim = await expert_repo.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    mismatched = envelope(request).model_copy(
        update={"step_id": "different-step"}
    )

    receipt = await expert_repo.submit_result(
        job.id,
        "worker-a",
        claim.fencing_token,
        mismatched,
    )

    assert not receipt.accepted
    assert receipt.rejection_code == "schema_invalid"
    assert (await expert_repo.get(job.id)).status == "running"
    assert await expert_repo.result_count(job.id) == 1


async def test_retry_usage_is_cumulative_and_outbox_is_delayed(repo):
    configured = ExpertJobRepository(
        repo.session_factory,
        retry_base_seconds=10,
        retry_max_seconds=10,
    )
    _, parent = await parent_claim(repo, "cumulative")
    request = request_for(parent)
    job, _ = await configured.create_or_replay(request)
    claim = await configured.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    failed = await configured.fail_attempt(
        job.id,
        "worker-a",
        claim.fencing_token,
        ExpertFailure(
            code=ExpertErrorCode.PROVIDER_TIMEOUT,
            retryable=True,
            usage=usage(model_calls=1, input_tokens=None, cost=None),
        ),
    )

    assert failed.status == "queued"
    async with repo.session_factory() as session:
        outbox = await session.scalar(
            select(DistributedExpertOutbox)
            .where(DistributedExpertOutbox.job_id == job.id)
            .order_by(DistributedExpertOutbox.created_at.desc())
        )
    assert outbox is not None
    assert outbox.available_at >= outbox.created_at + timedelta(seconds=9)

    second = await configured.claim(
        job.id,
        "worker-b",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    await configured.submit_result(
        job.id,
        "worker-b",
        second.fencing_token,
        envelope(request, consumed=usage(model_calls=2, input_tokens=20)),
    )
    terminal = await configured.terminal(job.id, parent.fencing_token)

    assert terminal is not None
    assert terminal.usage.model_calls == 3
    assert terminal.usage.input_tokens is None
    assert terminal.usage.estimated_cost_usd is None


async def test_non_retryable_failure_is_terminal(repo, expert_repo):
    _, parent = await parent_claim(repo, "terminal-failure")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    claim = await expert_repo.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    failed = await expert_repo.fail_attempt(
        job.id,
        "worker-a",
        claim.fencing_token,
        ExpertFailure(
            code=ExpertErrorCode.EXPERT_SCHEMA_INVALID,
            retryable=False,
            usage=usage(),
        ),
    )

    assert failed.status == "terminal_failed"
    terminal = await expert_repo.terminal(job.id, parent.fencing_token)
    assert terminal is not None
    assert terminal.outcome == "failed"
    assert terminal.error_code == ExpertErrorCode.EXPERT_SCHEMA_INVALID


async def test_reaper_expires_deadline_and_retries_expired_lease(repo, expert_repo):
    _, expired_parent = await parent_claim(repo, "deadline-expired")
    expired_request = request_for(expired_parent)
    expired_job, _ = await expert_repo.create_or_replay(expired_request)
    await expert_repo.force_job_deadline(
        expired_job.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    _, retry_parent = await parent_claim(repo, "lease-expired")
    retry_job, _ = await expert_repo.create_or_replay(
        request_for(retry_parent, logical_key="retry")
    )
    await expert_repo.claim(
        retry_job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    await expert_repo.force_lease_expiry(
        retry_job.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    changed = await expert_repo.reap_expired()

    assert expired_job.id in changed
    assert retry_job.id in changed
    assert (await expert_repo.get(expired_job.id)).status == "terminal_failed"
    assert (await expert_repo.get(retry_job.id)).status == "queued"


async def test_new_parent_epoch_closes_old_active_job(repo, expert_repo):
    run, first_parent = await parent_claim(repo, "epoch")
    old_job, _ = await expert_repo.create_or_replay(request_for(first_parent))
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    await repo.requeue_expired(datetime.now(UTC))
    second_parent = await repo.claim(run.id, "parent-worker", lease_seconds=120)

    new_job, _ = await expert_repo.create_or_replay(
        request_for(second_parent, logical_key="new-epoch")
    )

    assert new_job.parent_fencing_token == second_parent.fencing_token
    assert (await expert_repo.get(old_job.id)).status == "parent_stale"


async def test_parent_cancellation_closes_active_jobs(repo, expert_repo):
    run, parent = await parent_claim(repo, "cancel-experts")
    queued, _ = await expert_repo.create_or_replay(request_for(parent))

    await repo.cancel(run.id)

    assert (await expert_repo.get(queued.id)).status == "cancelled"
    async with repo.session_factory() as session:
        active_count = await session.scalar(
            select(func.count(DistributedExpertJob.id)).where(
                DistributedExpertJob.parent_run_id == run.id,
                DistributedExpertJob.status.in_(
                    ["accepted", "queued", "running", "retryable_failed"]
                ),
            )
        )
    assert active_count == 0


async def test_terminal_rejects_stale_parent_epoch(repo, expert_repo):
    run, parent = await parent_claim(repo, "terminal-parent")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    claim = await expert_repo.claim(
        job.id,
        "worker-a",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    await expert_repo.submit_result(
        job.id,
        "worker-a",
        claim.fencing_token,
        envelope(request),
    )

    with pytest.raises(ExpertFencingViolation):
        await expert_repo.terminal(job.id, parent.fencing_token + 1)


def test_accepted_result_partial_unique_index_is_declared():
    indexes = {
        index.name: index
        for index in DistributedExpertResult.__table__.indexes
    }
    accepted = indexes["uq_expert_result_accepted"]
    assert accepted.unique
    assert "disposition" in str(
        accepted.dialect_options["postgresql"]["where"]
    )
