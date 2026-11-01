from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from core.distributed.contracts import canonical_hash
from core.distributed.policy_health import (
    PolicyObservationRecorder,
    evaluate_window,
    nearest_rank,
    observation_key,
    PolicyHealthEvaluator,
    PolicyHealthProcess,
)
from core.distributed.promotion_contracts import PolicyObservation, PolicyThresholds
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord, PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord, PolicyHealthWindowRecord, PolicyObservationRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from core.distributed.runtime import migrate_schema
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_policy_assignment import assigner, token_for


NOW = datetime(2026, 11, 1, tzinfo=UTC)
DEPLOYMENT = UUID("11111111-1111-1111-1111-111111111111")


def sample(number, cohort="candidate", **updates):
    run_id = UUID(int=number + 1)
    values = {
        "observation_key": observation_key(str(run_id), str(DEPLOYMENT), cohort, 1),
        "run_id": run_id,
        "deployment_id": DEPLOYMENT,
        "policy_hash": ("a" if cohort == "stable" else "b") * 64,
        "cohort": cohort,
        "state_namespace": "rehearsal-health",
        "metric_contract_version": 1,
        "terminal_status": "completed",
        "latency_seconds": Decimal("1"),
        "input_tokens": 10,
        "output_tokens": 5,
        "cost": Decimal("0.01"),
        "commit_outcome": "succeeded",
        "permission_outcome": "allowed",
        "structured_result": "valid",
        "structured_decision_count": 10,
        "unknown_decision_count": 0,
        "injected": False,
        "fault_injected": False,
        "observed_at": NOW + timedelta(seconds=number),
        "source_trace_id": "c" * 32,
        "rehearsal_id": "health",
        "operation": "learning_task",
        "server_error_code": None,
    }
    values.update(updates)
    return PolicyObservation.model_validate(values)


def cohorts(**candidate_updates):
    return (
        [sample(i, **candidate_updates) for i in range(20)],
        [sample(i + 100, "stable") for i in range(20)],
    )


def evaluate(candidate, stable):
    return evaluate_window(candidate, stable, PolicyThresholds())


def test_key_is_canonical_and_paired_shadow_coexists():
    run = str(UUID(int=1))
    expected = canonical_hash({
        "run_id": run, "deployment_id": str(DEPLOYMENT),
        "cohort": "stable", "metric_contract_version": 1,
    })
    assert observation_key(run, str(DEPLOYMENT), "stable", 1) == expected
    assert expected != observation_key(run, str(DEPLOYMENT), "shadow", 1)


def test_nearest_rank_is_decimal_and_order_independent():
    values = [Decimal(i) for i in range(1, 21)]
    assert nearest_rank(values[::-1], Decimal(".95")) == Decimal(19)
    assert nearest_rank([Decimal("1.2")], Decimal(".95")) == Decimal("1.2")
    with pytest.raises(ValueError):
        nearest_rank([], Decimal(".95"))


@pytest.mark.parametrize("candidate_count,stable_count", [(19, 20), (20, 19), (0, 0)])
def test_normal_metrics_hold_below_both_minima(candidate_count, stable_count):
    candidate, stable = cohorts()
    result = evaluate(candidate[:candidate_count], stable[:stable_count])
    assert result.decision == "hold"


def test_healthy_exact_minimum_and_decimal_mean_pass():
    candidate, stable = cohorts(cost=Decimal("0.012"))
    result = evaluate(candidate, stable)
    assert result.decision == "pass"
    assert result.candidate_stats["mean_cost"] == "0.012"
    assert result.stable_stats["mean_cost"] == "0.01"


@pytest.mark.parametrize("metric", [
    "commit_failure_rate", "terminal_failure_rate", "latency_increase_rate",
    "mean_cost_increase_rate", "unknown_rate",
])
def test_maximum_equal_threshold_fails(metric):
    candidate, stable = cohorts()
    if metric == "commit_failure_rate":
        candidate[0] = sample(0, terminal_status="commit_failed", commit_outcome="failed")
    elif metric == "terminal_failure_rate":
        candidate[:2] = [sample(i, terminal_status="terminal_failed") for i in range(2)]
    elif metric == "latency_increase_rate":
        candidate = [sample(i, latency_seconds=Decimal("1.5")) for i in range(20)]
    elif metric == "mean_cost_increase_rate":
        candidate = [sample(i, cost=Decimal("0.013")) for i in range(20)]
    else:
        candidate = [sample(i, unknown_decision_count=1) for i in range(20)]
    result = evaluate(candidate, stable)
    assert result.decision == "fail"
    assert metric in result.reasons


def test_unknown_rate_uses_decisions_not_completed_runs():
    candidate, stable = cohorts()
    candidate[0] = sample(0, unknown_decision_count=10)
    assert evaluate(candidate, stable).decision == "pass"  # 10 / 200 < .10


def test_missing_cost_holds_without_inventing_zero():
    candidate, stable = cohorts(cost=None)
    result = evaluate(candidate, stable)
    assert result.decision == "hold"
    assert result.candidate_stats["mean_cost"] is None
    assert "cost_unavailable" in result.reasons


def test_unknown_cost_does_not_mask_confirmed_hard_failure():
    candidate = [sample(0, cost=None, terminal_status="confirmed_permission_violation",
                        permission_outcome="confirmed_violation",
                        server_error_code="ConfirmedPermissionViolation")]
    assert evaluate(candidate, []).decision == "fail"


def test_unknown_cost_does_not_mask_known_normal_failure_at_minimum():
    candidate, stable = cohorts(cost=None)
    candidate[0] = sample(0, cost=None, terminal_status="commit_failed", commit_outcome="failed")
    result = evaluate(candidate, stable)
    assert result.decision == "fail"
    assert "cost_unavailable" in result.reasons


def test_tool_denial_and_isolation_are_not_permission_violations():
    candidate, stable = cohorts(permission_outcome="denied")
    assert evaluate(candidate, stable).decision == "pass"
    candidate = [sample(i, permission_outcome="isolated") for i in range(20)]
    assert evaluate(candidate, stable).decision == "pass"


def test_unavailable_structured_data_holds_not_fake_valid():
    candidate, stable = cohorts(structured_decision_count=None, unknown_decision_count=None,
                                structured_result="unavailable")
    assert evaluate(candidate, stable).decision == "hold"


def test_recorder_api_accepts_no_caller_policy_identity():
    import inspect

    assert list(inspect.signature(PolicyObservationRecorder.record_run).parameters) == [
        "self", "run_id",
    ]


@pytest_asyncio.fixture
async def health_repo(raw_repo):
    await migrate_schema(raw_repo.session_factory.kw["bind"])
    raw_repo.policy_assigner = assigner(
        runtime_hash="f" * 64, source_revision="test-source", allow_fault_injection=True,
        settings_obj=SimpleNamespace(promotion_injected_latency_seconds=.05),
    )
    deployment = await candidate_head(raw_repo, state="canary", traffic=5000)
    return raw_repo, PromotionRepository(raw_repo.session_factory), deployment


async def candidate_head(repo, *, state="active", traffic=10000, version=2):
    from core.policy_store import artifact
    from core.distributed.runtime import BUILTIN_POLICY_HASH, REHEARSAL_DEPLOYMENT_ID

    value = artifact({"retrieval_rules": "synthetic health retrieval"},
        parent=BUILTIN_POLICY_HASH, protocol="b" * 64, runtime="f" * 64,
        source="test-source", proposer="c" * 64,
        evidence={"evidence_role": "test_fixture", "release_eligible": False})
    async with repo.session_factory() as session, session.begin():
        if await session.get(PolicyArtifactRecord, value["policy_hash"]) is None:
            session.add(PolicyArtifactRecord(**{
                key: value[key] for key in ("policy_hash", "parent_policy_hash",
                "components", "fixed_components_hash", "runtime_hash", "source_revision",
                "protocol_hash", "proposer_hash", "data_role")},
                evidence_bindings=value["evidence_paths"],
                created_at=datetime.fromisoformat(value["created_at"])))
            await session.flush()
        old = await session.get(PolicyDeploymentRecord, REHEARSAL_DEPLOYMENT_ID)
        row = PolicyDeploymentRecord(deployment_id=str(uuid4()), environment="rehearsal",
            version=version, state=state, candidate_policy_hash=value["policy_hash"],
            stable_policy_hash=BUILTIN_POLICY_HASH, previous_stable_deployment_id=old.deployment_id,
            traffic_basis_points=traffic, assignment_salt_id="test", thresholds=old.thresholds,
            thresholds_hash=old.thresholds_hash, required_receipts=[], command_id=f"test-{version}",
            reason="synthetic engineering fixture, not release evidence", actor="test", created_at=NOW)
        session.add(row)
        await session.flush()
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        head.current_deployment_id, head.current_version = row.deployment_id, version
        return row


async def admitted(fixture, request_id, *, cohort=None, fault="none"):
    repo, _, deployment = fixture
    from core.distributed.policy_assignment import assignment_bucket, select_cohort
    from tests.distributed.test_policy_assignment import SECRET

    for index in range(1000):
        name = f"{request_id}-{index}"
        bucket = assignment_bucket(secret=SECRET, environment="rehearsal",
            deployment_id=deployment.deployment_id, learner_id="student", request_id=name)
        actual = select_cohort(deployment.state, deployment.traffic_basis_points, bucket)
        if cohort is None or actual == cohort:
            break
    now = datetime.now(UTC)
    return await repo.accept_with_replay(spec(name), rehearsal_token=token_for(
        deployment, name, nonce=uuid4().hex, fault_profile=fault,
        issued_at=now.isoformat(), expires_at=(now + timedelta(minutes=5)).isoformat(),
    ))


def usage(**changes):
    return {"input_tokens": 10, "output_tokens": 5, "model_calls": 1, "tool_calls": 0,
            "cost": ".01", "structured_decision_count": 1, "unknown_decision_count": 0, **changes}


async def fill_window(fixture, *, state="canary", count=20, stable_count=None,
                      changes=None, stable_changes=None, paired=False):
    """Synthetic engineering observations; no formal qualification or student evidence."""
    repo, _, deployment = fixture
    if state != deployment.state:
        deployment = await candidate_head(repo, state=state, traffic=0 if state == "shadow" else 10000, version=3)
        fixture = repo, fixture[1], deployment
    rows = []
    parents = []
    for cohort in ("shadow" if state == "shadow" else "candidate", "stable"):
        for number in range(stable_count if cohort == "stable" and stable_count is not None else count):
            if cohort == "stable" and paired:
                parent = parents[number]
            else:
                parent, _ = await repo.accept_with_replay(spec(f"fixture-{cohort}-{number}"))
                if cohort != "stable":
                    parents.append(parent)
            values = sample(number + (100 if cohort == "stable" else 0),
                "stable" if cohort == "stable" else "candidate").model_dump(mode="python")
            values.update(
                observation_key=observation_key(parent.id, deployment.deployment_id, cohort, 1),
                run_id=parent.id, deployment_id=deployment.deployment_id, cohort=cohort,
                policy_hash=deployment.stable_policy_hash if cohort == "stable" else deployment.candidate_policy_hash,
            )
            overrides = stable_changes if cohort == "stable" else changes
            values.update(overrides(number) if callable(overrides) else overrides or {})
            rows.append(PolicyObservation.model_validate(values))
    async with repo.session_factory() as session, session.begin():
        for row in rows:
            values = row.model_dump(mode="python")
            values["run_id"], values["deployment_id"] = str(row.run_id), str(row.deployment_id)
            session.add(PolicyObservationRecord(**values, created_at=NOW))
    return fixture, rows


@pytest.mark.distributed_integration
async def test_terminal_retry_usage_one_observation_and_replay(health_repo):
    repo, _, _ = health_repo
    parent, _ = await admitted(health_repo, "retry", cohort="candidate")
    first = await repo.claim(parent.id, "first", 30, allowed_environment="rehearsal")
    await repo.record_attempt_usage(parent.id, first.fencing_token, usage())
    await repo.fail(parent.id, first.fencing_token, "TransientProviderFailure", True)
    recorder = PolicyObservationRecorder(repo.session_factory)
    assert await recorder.record_run(parent.id) is None
    second = await repo.claim(parent.id, "second", 30, allowed_environment="rehearsal")
    await repo.record_attempt_usage(parent.id, second.fencing_token, usage())
    await repo.transition_committing(parent.id, second.fencing_token)
    await repo.complete(parent.id, second.fencing_token, business_result(second.policy_binding))
    rows = await asyncio.gather(*(recorder.record_run(parent.id) for _ in range(8)))
    assert len({row.observation_key for row in rows}) == 1
    assert rows[0].cost == Decimal(".02")
    assert rows[0].input_tokens == 20
    assert rows[0].structured_decision_count == 2
    assert not rows[0].fault_injected
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyObservationRecord)) == 1


@pytest.mark.distributed_integration
async def test_missing_primary_ledger_does_not_invent_known_cost(health_repo):
    repo, _, _ = health_repo
    parent, _ = await admitted(health_repo, "missing")
    claim = await repo.claim(parent.id, "worker", 30, allowed_environment="rehearsal")
    await repo.transition_committing(parent.id, claim.fencing_token)
    await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
    observation = await PolicyObservationRecorder(repo.session_factory).record_run(parent.id)
    assert observation.cost is None
    assert observation.structured_result == "unavailable"


@pytest.mark.distributed_integration
@pytest.mark.parametrize("fault", ["latency", "commit_failure", "none"])
async def test_worker_signed_fault_frozen_and_server_observed(health_repo, broker, fault):
    from core.distributed.broker import StreamMessage
    from core.distributed.worker import RunWorker

    repo, _, _ = health_repo
    parent, _ = await admitted(health_repo, fault, cohort="candidate", fault=fault)
    repo.policy_assigner.settings.promotion_injected_latency_seconds = 99

    class Executor:
        async def execute(self, request, authority, binding):
            assert binding.injected_latency_seconds == (Decimal(".05") if fault == "latency" else 0)
            await repo.record_attempt_usage(str(authority.distributed_run_id), authority.run_fencing_token, usage())
            return business_result(binding)

    recorder = PolicyObservationRecorder(repo.session_factory)
    worker = RunWorker("health", repo, broker, Executor(), lease_seconds=30,
                       heartbeat_seconds=.01, max_attempts=3, allowed_environment="rehearsal",
                       observation_recorder=recorder)
    await worker.handle(StreamMessage("0-0", "health-event", {"run_id": parent.id}))
    observation = await recorder.record_run(parent.id)
    assert observation.fault_injected == (fault != "none")
    assert observation.injected == observation.fault_injected
    assert observation.terminal_status == ("commit_failed" if fault == "commit_failure" else "completed")
    if fault == "latency":
        assert observation.latency_seconds >= Decimal(".05")
    if fault == "commit_failure":
        assert observation.server_error_code == "RehearsalInjectedCommitFailure"


@pytest.mark.distributed_integration
async def test_evaluator_freezes_exact_keys_receipt_binding_and_idempotence(health_repo):
    fixture, rows = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    evaluator = PolicyHealthEvaluator(promotion)
    first = await evaluator.evaluate(deployment.deployment_id)
    second = await evaluator.evaluate(deployment.deployment_id)
    assert first.window_id == second.window_id
    assert first.decision == "pass"
    assert first.thresholds_hash == deployment.thresholds_hash
    assert first.observation_keys == {
        "candidate": [row.observation_key for row in rows[:20]],
        "stable": [row.observation_key for row in rows[20:]],
    }
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyHealthWindowRecord)) == 1
        receipt = await session.scalar(select(PolicyGateReceiptRecord))
        assert receipt.details["window_id"] == first.window_id
        assert receipt.details["deployment_version"] == deployment.version
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        missing, bound = await promotion._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": deployment},
        )
        assert not missing and bound["canary_health"].receipt_id == receipt.receipt_id


@pytest.mark.distributed_integration
@pytest.mark.parametrize("stable_changes", [
    {"rehearsal_id": None}, {"rehearsal_id": "other"}, {"operation": "other_operation"},
])
async def test_twenty_wrong_baseline_samples_hold_without_rollback(health_repo, stable_changes):
    fixture, _ = await fill_window(health_repo, stable_changes=stable_changes)
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "hold"
    assert (await promotion.get_head("rehearsal")).deployment_id == UUID(deployment.deployment_id)
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyGateReceiptRecord)) == 0


@pytest.mark.distributed_integration
async def test_fifty_candidates_twenty_stable_missing_bucket_hold(health_repo):
    fixture, rows = await fill_window(health_repo, count=50, stable_count=20,
        changes=lambda i: {"operation": "bucket-b" if i >= 40 else "learning_task"})
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.candidate_stats["run_count"] == 50
    assert window.stable_stats["run_count"] == 20
    assert window.decision == "hold"
    assert "matched_window_incomplete" in window.triggered_thresholds


@pytest.mark.distributed_integration
async def test_two_evaluators_one_atomic_rollback_old_run_pinned_and_late_window(health_repo):
    fixture, _ = await fill_window(health_repo, changes={"latency_seconds": Decimal("2")})
    repo, promotion, deployment = fixture
    accepted, _ = await admitted(fixture, "old-pinned", cohort="candidate")
    evaluator = PolicyHealthEvaluator(promotion)
    windows = await asyncio.gather(*(evaluator.evaluate(deployment.deployment_id) for _ in range(2)))
    assert windows[0].window_id == windows[1].window_id
    head = await promotion.get_head("rehearsal")
    assert head.state == "rolled_back"
    assert head.version == deployment.version + 1
    assert head.traffic_basis_points == 0
    assert head.stable_policy_hash == deployment.stable_policy_hash
    assert head.candidate_policy_hash == deployment.candidate_policy_hash
    claim = await repo.claim(accepted.id, "old", 30, allowed_environment="rehearsal")
    assert claim.policy_binding.policy_cohort == "candidate"
    new_head = await promotion.get_head("rehearsal")
    new, _ = await admitted((repo, promotion, new_head.model_copy(update={
        "deployment_id": str(new_head.deployment_id)
    })), "new-stable")
    assert new.policy_cohort == "stable"
    assert new.effective_policy_hash == deployment.stable_policy_hash
    async with repo.session_factory() as session, session.begin():
        values = sample(99, latency_seconds=Decimal("2")).model_dump(mode="python")
        values.update(run_id=accepted.id, deployment_id=deployment.deployment_id,
            observation_key=observation_key(accepted.id, deployment.deployment_id, "candidate", 1),
            policy_hash=deployment.candidate_policy_hash)
        session.add(PolicyObservationRecord(**values, created_at=NOW))
    late = await evaluator.evaluate(deployment.deployment_id)
    assert late.window_id != windows[0].window_id
    assert (await promotion.get_head("rehearsal")).deployment_id == head.deployment_id
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.event_type == "health_rollback")) == 1


@pytest.mark.distributed_integration
async def test_shadow_uses_same_parent_not_unpaired_stable(health_repo):
    fixture, _ = await fill_window(health_repo, state="shadow")
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "hold"  # same count, unrelated parents


@pytest.mark.distributed_integration
async def test_shadow_confirmed_server_permission_is_immediate_failure(health_repo, tmp_path):
    from core.distributed.policy_health import ConfirmedPermissionViolation
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker

    repo, promotion, _ = health_repo
    deployment = await candidate_head(repo, state="shadow", traffic=0, version=3)
    parent, _ = await admitted((repo, promotion, deployment), "permission")
    claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
    await repo.transition_committing(parent.id, claim.fencing_token)
    await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))

    class Executor:
        async def execute(self, *args):
            raise ConfirmedPermissionViolation()

    router = ShadowStoreRouter(tmp_path / "shadow")
    recorder = PolicyObservationRecorder(repo.session_factory)
    worker = ShadowWorker("shadow", promotion, Executor(), router,
                          policy_assigner=repo.policy_assigner, observation_recorder=recorder)
    assert await worker.run_once()
    await recorder.record_run(parent.id)
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "fail"
    assert "confirmed_permission_violation" in window.triggered_thresholds
    assert (await promotion.get_head("rehearsal")).state == "shadow"


@pytest.mark.distributed_integration
async def test_disabled_health_process_does_not_poll(health_repo):
    _, promotion, _ = health_repo
    process = PolicyHealthProcess(promotion, enabled=False)
    process.recorder.recover = lambda: pytest.fail("disabled process queried observations")
    assert await process.poll_once() == []


@pytest.mark.parametrize("cost", ["NaN", "Infinity", "-1", None, "invalid"])
def test_usage_combination_rejects_unknown_and_nonfinite_cost(cost):
    from core.distributed.shadow_usage import combine_usage
    assert combine_usage([usage(cost=cost)])["cost"] is None


@pytest.mark.distributed_integration
async def test_paired_shadow_passes_and_wrong_distribution_holds(health_repo):
    fixture, _ = await fill_window(health_repo, state="shadow", paired=True)
    _, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "pass"
    assert len(window.observation_keys["stable"]) == 20


@pytest.mark.distributed_integration
async def test_unequal_bucket_proportions_with_twenty_each_hold(health_repo):
    fixture, _ = await fill_window(health_repo, count=20,
        changes=lambda i: {"operation": "bucket-b" if i >= 15 else "learning_task"},
        stable_changes=lambda i: {"operation": "bucket-b" if i >= 10 else "learning_task"})
    _, promotion, deployment = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "hold"


@pytest.mark.distributed_integration
@pytest.mark.parametrize("write", ["usage", "fault"])
@pytest.mark.parametrize("change", ["deadline", "terminal", "lease"])
async def test_attempt_lock_wait_reauthorizes_after_all_blocking_locks(health_repo, write, change):
    from core.distributed.repository import FencingViolation

    repo, _, _ = health_repo
    parent, _ = await admitted(health_repo, "blocked", cohort="candidate", fault="latency")
    claim = await repo.claim(parent.id, "worker", 30, allowed_environment="rehearsal")
    engine = repo.session_factory.kw["bind"]
    async with engine.connect() as blocker, engine.connect() as observer:
        transaction = await blocker.begin()
        blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))
        table = "distributed_leases" if change == "lease" else "distributed_run_attempts"
        await blocker.execute(text(
            f"SELECT run_id FROM {table} WHERE run_id=:id FOR UPDATE"
        ), {"id": parent.id})
        if change == "lease":
            await blocker.execute(text(
                "UPDATE distributed_leases SET expires_at=clock_timestamp()+interval '.03 seconds' "
                "WHERE run_id=:id"
            ), {"id": parent.id})
        task = asyncio.create_task(
            repo.record_attempt_usage(parent.id, claim.fencing_token, usage()) if write == "usage"
            else repo.mark_fault_injected(parent.id, claim.fencing_token)
        )
        blocked = False
        for _ in range(300):
            blocked = bool(await observer.scalar(text(
                "SELECT EXISTS(SELECT 1 FROM pg_locks "
                "WHERE :pid = ANY(pg_blocking_pids(pid)))"
            ), {"pid": blocker_pid}))
            if blocked:
                break
            await asyncio.sleep(.01)
        if not blocked:
            task.cancel()
            results = await asyncio.gather(task, return_exceptions=True)
            pytest.fail(f"must observe actual PostgreSQL lock contention; writer={results}")
        if change == "deadline":
            await blocker.execute(text(
                "UPDATE distributed_run_attempts SET deadline_at=clock_timestamp()-interval '1 second' "
                "WHERE run_id=:id"
            ), {"id": parent.id})
        elif change == "terminal":
            await blocker.execute(text(
                "UPDATE distributed_run_attempts SET status='terminal_failed' WHERE run_id=:id"
            ), {"id": parent.id})
        else:
            # 数据库 lease 真实到期，而非用调用者时钟模拟授权失败。
            await asyncio.sleep(.05)
        await transaction.commit()
        with pytest.raises(FencingViolation):
            await task
    async with repo.session_factory() as session:
        from core.distributed.models import DistributedRunAttempt
        attempt = await session.scalar(select(DistributedRunAttempt).where(
            DistributedRunAttempt.run_id == parent.id))
        assert attempt.usage_summary is None
        assert not attempt.fault_injected


@pytest.mark.distributed_integration
async def test_explicit_migration_upgrades_actual_old_m3_columns_and_marker(health_repo):
    from core.distributed.runtime import check_schema_version, schema_contract_hash, SchemaVersionMismatch

    repo, _, _ = health_repo
    _, observations = await fill_window(health_repo, count=1,
        changes={"injected": True, "fault_injected": True, "operation": "historical-fixture"})
    engine = repo.session_factory.kw["bind"]
    old_columns = {
        "distributed_run_attempts": ["usage_summary", "fault_injected"],
        "policy_observations": ["structured_decision_count", "unknown_decision_count",
                                "rehearsal_id", "operation", "server_error_code", "fault_injected"],
        "policy_health_windows": ["deployment_version", "thresholds_hash", "observation_keys"],
    }
    async with engine.begin() as connection:
        for table, columns in old_columns.items():
            for column in columns:
                await connection.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
        await connection.execute(text("DROP TABLE distributed_schema_version"))
    with pytest.raises(SchemaVersionMismatch):
        await check_schema_version(engine)
    await migrate_schema(engine)
    await check_schema_version(engine)
    async with engine.connect() as connection:
        for table, columns in old_columns.items():
            actual = (await connection.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() "
                "AND table_name=:table"
            ), {"table": table})).scalars().all()
            assert set(columns) <= set(actual)
        marker = (await connection.execute(text(
            "SELECT version,schema_hash FROM distributed_schema_version WHERE id=1"
        ))).one()
        assert tuple(marker) == (3, schema_contract_hash())
        row = (await connection.execute(text(
            "SELECT structured_decision_count,unknown_decision_count,fault_injected,operation,cost,rehearsal_id "
            "FROM policy_observations WHERE observation_key=:key"
        ), {"key": observations[0].observation_key})).one()
        assert tuple(row) == (None, None, True, "learning_task", Decimal(".01"), None)


def test_usage_counts_inline_expert_only_once_and_incomplete_coordinator_holds():
    from core.distributed.shadow_usage import summarize_shadow_usage

    ctx = SimpleNamespace(model_calls=2, tool_calls=0, steps=[
        {"kind": "model_usage", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": ".01"}},
        {"kind": "structured_decision", "valid": True},
        {"kind": "model_usage", "usage": {"prompt_tokens": 7, "completion_tokens": 4, "cost": ".02"}},
        {"kind": "expert_usage_charged", "model_calls": 1, "observed_model_calls": 1,
         "input_tokens": 7, "output_tokens": 4, "estimated_cost_usd": ".02",
         "structured_decision_count": 1, "unknown_decision_count": 1, "uncertain": False},
    ])
    summary = summarize_shadow_usage(ctx)
    assert Decimal(summary["cost"]) == Decimal(".03")
    assert summary["input_tokens"] == 12
    assert summary["structured_decision_count"] == 2
    assert summary["unknown_decision_count"] == 1
    ctx.steps[0]["usage"].pop("cost")
    assert summarize_shadow_usage(ctx)["cost"] is None


@pytest.mark.distributed_integration
async def test_recovery_uses_full_contract_deployment_identity(health_repo):
    repo, _, deployment = health_repo
    parent, _ = await admitted(health_repo, "contract-recovery", cohort="candidate")
    claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
    await repo.transition_committing(parent.id, claim.fencing_token)
    await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
    async with repo.session_factory() as session, session.begin():
        # A historical contract row must not suppress the v1 canonical terminal.
        values = sample(0).model_dump(mode="python")
        values.update(run_id=parent.id, deployment_id=deployment.deployment_id,
            policy_hash=deployment.candidate_policy_hash, metric_contract_version=2,
            observation_key=observation_key(parent.id, deployment.deployment_id, "candidate", 2))
        session.add(PolicyObservationRecord(**values, created_at=NOW))
    recorder = PolicyObservationRecorder(repo.session_factory)
    assert await recorder.recover() == 1
    observation = await recorder.record_run(parent.id)
    assert observation.metric_contract_version == 1
    assert observation.observation_key != values["observation_key"]


@pytest.mark.distributed_integration
@pytest.mark.parametrize("signed", [True, False])
async def test_stable_or_unsigned_run_cannot_inject_fault(health_repo, broker, signed):
    from core.distributed.broker import StreamMessage
    from core.distributed.worker import RunWorker

    repo, _, _ = health_repo
    parent, _ = (await admitted(health_repo, "stable-no-fault", cohort="stable", fault="commit_failure")
                 if signed else await repo.accept_with_replay(spec("unsigned-no-fault")))

    class Executor:
        async def execute(self, request, authority, binding):
            assert binding.rehearsal_fault_profile == "none"
            assert binding.injected_latency_seconds == 0
            return business_result(binding)

    recorder = PolicyObservationRecorder(repo.session_factory)
    worker = RunWorker("stable", repo, broker, Executor(), lease_seconds=30,
        heartbeat_seconds=.01, max_attempts=3,
        allowed_environment="rehearsal" if signed else "production", observation_recorder=recorder)
    await worker.handle(StreamMessage("0-0", "stable-health", {"run_id": parent.id}))
    observation = await recorder.record_run(parent.id)
    assert observation.terminal_status == "completed" and not observation.fault_injected


def test_server_diagnostic_is_type_based_and_survives_exception_wrapping():
    from core.distributed.policy_health import ConfirmedPermissionViolation, server_diagnostic_code

    denied = PermissionError("ConfirmedPermissionViolation")
    assert server_diagnostic_code(denied) == "PermissionError"
    try:
        try:
            raise ConfirmedPermissionViolation()
        except ConfirmedPermissionViolation as exc:
            raise RuntimeError("redacted wrapper") from exc
    except RuntimeError as exc:
        assert server_diagnostic_code(exc) == "ConfirmedPermissionViolation"


@pytest.mark.distributed_integration
async def test_authoritative_metrics_cross_process_and_bounded_labels(health_repo):
    from core.distributed.metrics import DistributedMetrics

    fixture, _ = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    emitter = DistributedMetrics()
    await PolicyHealthEvaluator(promotion, metrics=emitter).evaluate(deployment.deployment_id)
    observer = DistributedMetrics()
    await observer.refresh_policy_counts(repo.session_factory)
    text_metrics = observer.render().decode()
    assert 'eduagent_policy_health_windows_persisted{decision="pass",environment="rehearsal"} 1.0' in text_metrics
    assert 'eduagent_policy_gate_receipts_persisted{gate="canary_health",status="passed"} 1.0' in text_metrics
    assert deployment.deployment_id not in text_metrics
    assert deployment.candidate_policy_hash not in text_metrics
    assert emitter.policy_health_decisions.labels(environment="rehearsal", decision="pass")._value.get() == 1
    for family in observer.registry.collect():
        for item in family.samples:
            assert not ({"learner", "request", "run", "deployment", "policy_hash"} & item.labels.keys())


@pytest.mark.distributed_integration
async def test_migration_failure_cannot_publish_new_marker(health_repo, monkeypatch):
    from core.distributed import runtime

    repo, _, _ = health_repo
    engine = repo.session_factory.kw["bind"]
    async with engine.connect() as conn:
        old = (await conn.execute(text(
            "SELECT version,schema_hash,migrated_at FROM distributed_schema_version WHERE id=1"
        ))).one()

    async def fail(connection):
        await connection.execute(text("ALTER TABLE policy_observations ADD COLUMN rollback_probe INTEGER"))
        raise RuntimeError("controlled upgrade failure")

    monkeypatch.setattr(runtime, "upgrade_m3_schema", fail)
    with pytest.raises(RuntimeError, match="controlled upgrade failure"):
        await runtime.migrate_schema(engine)
    async with engine.connect() as conn:
        current = (await conn.execute(text(
            "SELECT version,schema_hash,migrated_at FROM distributed_schema_version WHERE id=1"
        ))).one()
        assert tuple(current) == tuple(old)
        assert not await conn.scalar(text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='policy_observations' "
            "AND table_schema=current_schema() AND column_name='rollback_probe')"
        ))


@pytest.mark.distributed_integration
async def test_last_fifty_frozen_candidates_exclude_older_bad_cost(health_repo):
    fixture, rows = await fill_window(health_repo, count=60,
        changes=lambda i: {"cost": None} if i < 10 else {})
    _, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "pass"
    assert window.observation_keys["candidate"] == [row.observation_key for row in rows[10:60]]
    assert window.observation_keys["stable"] == [row.observation_key for row in rows[70:]]


def test_rehearsal_latency_tag_does_not_hide_natural_failure_origin():
    candidate, stable = cohorts()
    candidate[0] = sample(0, terminal_status="terminal_failed", fault_injected=True,
                          injected=True, server_error_code="TransientProviderFailure")
    result = evaluate(candidate, stable)
    assert result.candidate_stats["fault_injected_count"] == 1
    assert result.candidate_stats["natural_failure_count"] == 1
    assert result.candidate_stats["injected_commit_failure_count"] == 0


@pytest.mark.distributed_integration
@pytest.mark.parametrize("unavailable", [False, True])
async def test_old_permission_violation_survives_over_fifty_healthy_candidates(health_repo, unavailable):
    def candidate_changes(index):
        values = {"cost": None} if unavailable else {}
        if index == 0:
            values.update(terminal_status="confirmed_permission_violation",
                permission_outcome="confirmed_violation", server_error_code="ConfirmedPermissionViolation")
        return values

    fixture, rows = await fill_window(health_repo, count=60,
        stable_count=0 if unavailable else 60, changes=candidate_changes)
    _, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "fail"
    assert window.observation_keys["hard_failures"] == [rows[0].observation_key]
    assert rows[0].observation_key not in window.observation_keys["candidate"]
    assert "confirmed_permission_violation" in window.triggered_thresholds
    assert (await promotion.get_head("rehearsal")).state == "rolled_back"


@pytest.mark.distributed_integration
async def test_committed_hard_violation_blocks_older_pass_receipt_before_poll(health_repo):
    fixture, _ = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "pass"
    parent, _ = await repo.accept_with_replay(spec("late-hard-fixture"))
    async with repo.session_factory() as session, session.begin():
        values = sample(0).model_dump(mode="python")
        values.update(run_id=parent.id, deployment_id=deployment.deployment_id,
            policy_hash=deployment.candidate_policy_hash, cost=None,
            observation_key=observation_key(parent.id, deployment.deployment_id, "candidate", 1),
            terminal_status="confirmed_permission_violation", permission_outcome="confirmed_violation",
            server_error_code="ConfirmedPermissionViolation", observed_at=NOW - timedelta(seconds=1))
        session.add(PolicyObservationRecord(**values, created_at=NOW))
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        missing, gates = await promotion._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": deployment})
        assert missing == ["canary_health"] and not gates


@pytest.mark.distributed_integration
@pytest.mark.parametrize("mode", ["primary", "shadow"])
async def test_real_opened_database_mismatch_emits_server_permission_diagnostic(
    health_repo, broker, tmp_path, monkeypatch, mode,
):
    from core.distributed import executor as executor_module
    from core.distributed.broker import StreamMessage
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker
    from core.distributed.worker import RunWorker

    repo, promotion, deployment = health_repo
    if mode == "shadow":
        deployment = await candidate_head(repo, state="shadow", traffic=0, version=3)
    parent, _ = await admitted((repo, promotion, deployment), "actual-store-check",
                               cohort="candidate" if mode == "primary" else "stable")
    if mode == "shadow":
        claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
        await repo.transition_committing(parent.id, claim.fencing_token)
        await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
    original = executor_module.LearningHarness
    outside = tmp_path / "outside-authorized-namespace.sqlite3"

    def wrong_server_store(orchestrator, path, *args, **kwargs):
        # 注入服务端连接选址错误；不直接抛模拟的权限异常。
        return original(orchestrator, str(outside), *args, **kwargs)

    monkeypatch.setattr(executor_module, "LearningHarness", wrong_server_store)
    recorder = PolicyObservationRecorder(repo.session_factory)
    if mode == "shadow":
        router = ShadowStoreRouter(tmp_path / "shadow-root")
        executor = executor_module.LearningTaskExecutor(None, shadow_store_router=router)
        worker = ShadowWorker("shadow", promotion, executor, router,
            policy_assigner=repo.policy_assigner, observation_recorder=recorder)
        assert await worker.run_once()
        job = await promotion.enqueue_shadow(parent.id)
        observation = await recorder.record_shadow(job.shadow_id)
    else:
        executor = executor_module.LearningTaskExecutor(
            str(tmp_path / "production.sqlite3"), allowed_environment="rehearsal",
            rehearsal_store_root=str(tmp_path / "rehearsal"), usage_recorder=repo.record_attempt_usage,
        )
        worker = RunWorker("primary", repo, broker, executor, lease_seconds=30,
            heartbeat_seconds=.01, max_attempts=3, allowed_environment="rehearsal",
            observation_recorder=recorder)
        await worker.handle(StreamMessage("0-0", "actual-diagnostic", {"run_id": parent.id}))
        observation = await recorder.record_run(parent.id)
    assert outside.exists()
    assert observation.server_error_code == "ConfirmedPermissionViolation"
    assert observation.permission_outcome == "confirmed_violation"
    assert observation.terminal_status == "confirmed_permission_violation"
    assert observation.cost is None
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "fail"
    assert (await promotion.get_head("rehearsal")).state == ("shadow" if mode == "shadow" else "rolled_back")
