"""Fresh Task8 SPEC failures, using real services and fixture-only evidence."""
import copy
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from core.distributed.contracts import canonical_hash
from core.distributed.models import DistributedRun
from core.distributed.policy_health import (
    PolicyHealthEvaluator, PolicyObservationRecorder, proportional_baseline,
)
from core.distributed.promotion_contracts import PolicyArtifact, PolicyThresholds, PromotionCommand
from core.distributed.promotion_repository import PromotionRepository
from core.distributed.promotion_service import QualificationMaterial
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyGateReceiptRecord,
    PolicyHealthWindowRecord, PolicyObservationRecord, PolicyShadowExecutionRecord,
)
from core.distributed.runtime import (
    migrate_schema, PRODUCTION_DEPLOYMENT_ID, BUILTIN_FIXED_COMPONENTS_HASH,
)
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_policy_health import (
    NOW, admitted as _admitted, fill_window, health_repo, observation_key, sample, usage,
)
from tests.distributed.test_policy_assignment import assigner
from tests.distributed.test_promotion_schema_upgrade import _material

pytestmark = pytest.mark.distributed_integration


async def admitted(fixture, *args, **kwargs):
    repo, promotion, deployment = fixture
    if not isinstance(deployment.deployment_id, str):
        deployment = deployment.model_copy(update={"deployment_id": str(deployment.deployment_id)})
    return await _admitted((repo, promotion, deployment), *args, **kwargs)


@pytest.mark.parametrize("kind", ["run", "shadow"])
async def test_migrated_two_hundred_unbound_terminals_do_not_starve_recovery(health_repo, kind):
    repo, promotion, deployment = health_repo
    engine = repo.session_factory.kw["bind"]
    # Reproduce pre-M3 legacy hashes with no registered artifact, then run actual backfill.
    async with engine.begin() as connection:
        await connection.execute(text(
            "ALTER TABLE distributed_runs DROP CONSTRAINT fk_distributed_run_effective_policy"))
    async with repo.session_factory() as session, session.begin():
        for i in range(205):
            run = DistributedRun(
                id=str(uuid4()), learner_id="legacy", request_id=f"legacy-{i}",
                operation="learning_task", input_hash="a" * 64, payload={},
                status="completed", trace_id="c" * 32,
                effective_policy_hash="9" * 64, created_at=NOW, updated_at=NOW,
                deployment_id=PRODUCTION_DEPLOYMENT_ID, policy_cohort="stable",
                assignment_key_hash="a" * 64, assignment_reason="legacy_backfill",
                state_namespace="production", rehearsal_fault_profile="none",
            )
            session.add(run)
            if kind == "shadow":
                await session.flush()
                session.add(PolicyShadowExecutionRecord(
                    shadow_id=str(uuid4()), parent_run_id=run.id,
                    deployment_id=deployment.deployment_id, policy_hash=deployment.candidate_policy_hash,
                    status="completed", created_at=NOW, updated_at=NOW, policy_binding=None,
                ))
    await migrate_schema(engine)
    await migrate_schema(engine)
    parent, _ = await admitted(health_repo, "new-valid", cohort="candidate")
    claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
    await repo.record_attempt_usage(parent.id, claim.fencing_token, usage())
    await repo.transition_committing(parent.id, claim.fencing_token)
    await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
    if kind == "shadow":
        async with repo.session_factory() as session, session.begin():
            session.add(PolicyShadowExecutionRecord(
                shadow_id=str(uuid4()), parent_run_id=parent.id,
                deployment_id=deployment.deployment_id, policy_hash=deployment.candidate_policy_hash,
                status="completed", policy_binding={"state_namespace": "rehearsal-health"},
                result=usage(), created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))
    recorder = PolicyObservationRecorder(repo.session_factory)
    counts = [await recorder.recover() for _ in range(3)]
    async with repo.session_factory() as session:
        rows = (await session.scalars(select(PolicyObservationRecord))).all()
        legacy = (await session.scalars(select(DistributedRun).where(
            DistributedRun.learner_id == "legacy"))).all()
        artifact = await session.get(PolicyArtifactRecord, "9" * 64)
    assert all(row.policy_binding is None for row in legacy)
    assert artifact.data_role == "legacy" and artifact.evidence_bindings["release_eligible"] is False
    assert len(rows) == (2 if kind == "shadow" else 1), counts
    assert sum(counts) == len(rows) and counts[-1] == 0


@pytest.mark.parametrize("bad", [False, True])
@pytest.mark.parametrize("buckets", [False, True])
async def test_fifty_twenty_proportional_distribution_qualifies(health_repo, bad, buckets):
    fixture, _ = await fill_window(
        health_repo, count=50, stable_count=20,
        changes=lambda i: {
            "operation": "bucket-b" if buckets and i >= 40 else "learning_task",
            "latency_seconds": Decimal("1.5") if bad else Decimal("1"),
        },
        stable_changes=lambda i: {
            "operation": "bucket-b" if buckets and i >= 16 else "learning_task",
        },
    )
    _, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.candidate_stats["run_count"] == 50
    assert window.stable_stats["run_count"] == 20
    assert window.decision == ("fail" if bad else "pass")
    assert (await promotion.get_head("rehearsal")).state == ("rolled_back" if bad else "canary")


@pytest.mark.parametrize("stable_count,split", [(19, 15), (20, 15), (20, 20)])
async def test_proportional_shortage_mismatch_or_missing_bucket_holds(health_repo, stable_count, split):
    fixture, _ = await fill_window(
        health_repo, count=50, stable_count=stable_count,
        changes=lambda i: {"operation": "bucket-b" if i >= 40 else "learning_task"},
        stable_changes=lambda i: {"operation": "bucket-b" if i >= split else "learning_task"},
    )
    _, promotion, deployment = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "hold"


def test_proportional_selection_is_exact_bounded_and_deterministic():
    candidate = [sample(i, operation="b" if i >= 40 else "learning_task") for i in range(50)]
    pool = [sample(i + 100, "stable", operation="b" if i >= 30 else "learning_task")
            for i in range(40)]
    selected, matched = proportional_baseline(candidate, pool, PolicyThresholds())
    reversed_selection, reverse_matched = proportional_baseline(candidate, pool[::-1], PolicyThresholds())
    assert matched and reverse_matched and selected == reversed_selection
    assert len(selected) == 35  # 28/7 is the largest available exact 4:1 baseline.
    assert len([row for row in selected if row.operation == "b"]) == 7
    assert selected == sorted(selected, key=lambda row: (row.observed_at, row.observation_key))
    assert min(row.observed_at for row in selected if row.operation == "b") == pool[33].observed_at


async def test_stable_pool_remains_last_fifty_bounded(health_repo):
    fixture, rows = await fill_window(health_repo, count=50, stable_count=80)
    _, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "pass"
    assert window.observation_keys["stable"] == [row.observation_key for row in rows[-50:]]


@pytest.mark.parametrize("missing", ["window_id", "metric_contract_version", "observation_keys",
                                    "candidate_stats", "stable_stats", "gate_cohort"])
async def test_missing_frozen_receipt_identity_fails_closed(health_repo, missing):
    fixture, _ = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session, session.begin():
        original = await session.scalar(select(PolicyGateReceiptRecord))
        values = {c.name: copy.deepcopy(getattr(original, c.name))
                  for c in PolicyGateReceiptRecord.__table__.columns}
        values["details"].pop(missing)
        values.update(receipt_id=str(uuid4()), evidence_hash=canonical_hash(values["details"]),
                      issued_at=original.issued_at + timedelta(seconds=1))
        session.add(PolicyGateReceiptRecord(**values))
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        missing_gates, bound = await promotion._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": deployment})
    assert missing_gates == ["canary_health"] and not bound


async def test_latest_nonpass_window_blocks_old_pass_before_receipt_selection(health_repo):
    fixture, _ = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    evaluator = PolicyHealthEvaluator(promotion)
    assert (await evaluator.evaluate(deployment.deployment_id)).decision == "pass"
    parent, _ = await repo.accept_with_replay(spec("new-unknown-cost"))
    async with repo.session_factory() as session, session.begin():
        values = sample(999, cost=None).model_dump(mode="python")
        values.update(
            run_id=parent.id, deployment_id=deployment.deployment_id,
            policy_hash=deployment.candidate_policy_hash,
            observation_key=observation_key(parent.id, deployment.deployment_id, "candidate", 1))
        session.add(PolicyObservationRecord(**values, created_at=NOW))
    assert (await evaluator.evaluate(deployment.deployment_id)).decision == "hold"
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        missing, bound = await promotion._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": deployment})
    assert missing == ["canary_health"] and not bound


@pytest.mark.parametrize("tamper", [
    "missing_window", "window_id", "metric_contract_version", "observation_keys",
    "candidate_stats", "stable_stats", "evidence_hash", "deployment_version",
    "thresholds_hash", "sample_count", "cost", "gate_type",
    "protocol_hash", "runtime_hash", "source_revision", "window_decision",
    "window_keys", "window_stats", "window_contract",
])
async def test_forged_or_inconsistent_health_receipt_is_not_consumable(health_repo, tamper):
    fixture, _ = await fill_window(health_repo)
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session, session.begin():
        original = await session.scalar(select(PolicyGateReceiptRecord))
        values = {c.name: copy.deepcopy(getattr(original, c.name))
                  for c in PolicyGateReceiptRecord.__table__.columns}
        values.update(receipt_id=str(uuid4()), issued_at=original.issued_at + timedelta(seconds=1))
        if tamper in {"missing_window", "window_decision", "window_keys", "window_stats", "window_contract"}:
            # Simulate corrupted persisted evidence without disabling append-only protection.
            await session.execute(text("ALTER TABLE policy_health_windows DISABLE TRIGGER USER"))
            if tamper == "missing_window":
                await session.delete(await session.get(PolicyHealthWindowRecord, window.window_id))
                await session.flush()
            else:
                frozen = await session.get(PolicyHealthWindowRecord, window.window_id)
                if tamper == "window_decision":
                    frozen.decision = "hold"
                elif tamper == "window_keys":
                    frozen.observation_keys = {"candidate": [], "stable": []}
                elif tamper == "window_stats":
                    frozen.candidate_stats = {**frozen.candidate_stats, "mean_cost": "0"}
                else:
                    frozen.metric_contract_version = 2
                await session.flush()
            await session.execute(text("ALTER TABLE policy_health_windows ENABLE TRIGGER USER"))
        elif tamper in {"window_id", "metric_contract_version", "observation_keys",
                        "candidate_stats", "stable_stats", "deployment_version", "thresholds_hash"}:
            values["details"][tamper] = {
                "window_id": "f" * 64, "metric_contract_version": 2,
                "observation_keys": {"candidate": [], "stable": []},
                "candidate_stats": {}, "stable_stats": {}, "deployment_version": 999,
                "thresholds_hash": "e" * 64,
            }[tamper]
            values["evidence_hash"] = canonical_hash(values["details"])
        else:
            values[tamper] = {
                "evidence_hash": "e" * 64, "sample_count": 0, "cost": Decimal(0),
                "gate_type": "shadow_health", "protocol_hash": "e" * 64,
                "runtime_hash": "e" * 64, "source_revision": "wrong",
            }[tamper]
        # Remove the valid receipt so artifact-scoped mismatch tests cannot fall back to it.
        await session.execute(text("ALTER TABLE policy_gate_receipts DISABLE TRIGGER USER"))
        await session.delete(original)
        await session.flush()
        await session.execute(text("ALTER TABLE policy_gate_receipts ENABLE TRIGGER USER"))
        session.add(PolicyGateReceiptRecord(**values))
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        missing, bound = await promotion._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": deployment})
    assert missing == ["canary_health"] and not bound


async def real_active_fixture(health_repo):
    repo, promotion, _ = health_repo
    # Real command chain; all campaign/provider data remains deterministic test fixtures.
    material = _material()
    body = material.model_dump(mode="json")
    body["artifact"]["fixed_components_hash"] = BUILTIN_FIXED_COMPONENTS_HASH
    body["artifact"]["policy_hash"] = PromotionRepository._artifact_hash(
        PolicyArtifact.model_validate(body["artifact"]))
    for receipt in body["receipts"]:
        receipt["policy_hash"] = body["artifact"]["policy_hash"]
    material = QualificationMaterial.model_validate(body)
    repo.policy_assigner = assigner(runtime_hash=material.artifact.runtime_hash,
                                   source_revision=material.artifact.source_revision)
    registered = await promotion.register_qualification(
        material, actor="test", command_id="correction-register")

    async def move(snapshot, target, traffic):
        return await promotion.transition(PromotionCommand(
            command_id=f"correction-{target}", environment="rehearsal",
            expected_version=snapshot.version, current_state=snapshot.state,
            target_state=target, traffic_basis_points=traffic, actor="test",
            reason="fixture-only health chain, not formal release evidence"))

    shadow = await move(registered, "shadow", 0)
    fixture, _ = await fill_window(
        (repo, promotion, shadow), state="shadow", paired=True,
        changes=lambda i: {"observed_at": datetime.now(UTC)},
        stable_changes=lambda i: {"observed_at": datetime.now(UTC)})
    assert (await PolicyHealthEvaluator(promotion).evaluate(shadow.deployment_id)).decision == "pass"
    canary = await move(shadow, "canary", 5000)
    fixture, rows = await fill_window(
        (repo, promotion, canary),
        changes=lambda i: {"observed_at": datetime.now(UTC)},
        stable_changes=lambda i: {"observed_at": datetime.now(UTC)})
    assert (await PolicyHealthEvaluator(promotion).evaluate(canary.deployment_id)).decision == "pass"
    active = await move(canary, "active", 10000)
    return (repo, promotion, active), canary, rows


@pytest.mark.parametrize("bad", [False, True])
async def test_real_canary_to_active_historical_baseline_and_old_new_pinning(health_repo, bad):
    fixture, canary, rows = await real_active_fixture(health_repo)
    repo, promotion, active = fixture
    accepted, _ = await admitted(fixture, "active-old", cohort="candidate")
    assert accepted.deployment_id == str(active.deployment_id)
    # Only candidate observations are legitimate under Active's 100% assignment.
    fixture, _ = await fill_window(
        fixture, state="active", stable_count=0,
        changes={"latency_seconds": Decimal("1.5") if bad else Decimal(1),
                 "observed_at": active.created_at + timedelta(seconds=1)})
    window = await PolicyHealthEvaluator(promotion).evaluate(active.deployment_id)
    assert window.decision == ("fail" if bad else "pass")
    assert window.observation_keys["stable"] == [r.observation_key for r in rows[20:]]
    claim = await repo.claim(accepted.id, "old", 30, allowed_environment="rehearsal")
    assert claim.policy_binding.policy_cohort == "candidate"
    assert claim.policy_binding.deployment_id == active.deployment_id
    head = await promotion.get_head("rehearsal")
    assert head.state == ("rolled_back" if bad else "active")
    fresh, _ = await admitted((repo, promotion, head), "active-new")
    assert fresh.policy_cohort == ("stable" if bad else "candidate")
    assert fresh.effective_policy_hash == (active.stable_policy_hash if bad else active.candidate_policy_hash)
    if bad:
        async with repo.session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord).where(
                PolicyAuditEventRecord.event_type == "health_rollback")) == 1


@pytest.mark.parametrize("tamper", [
    "unrelated_deployment", "production", "wrong_stable_policy", "wrong_rehearsal",
    "wrong_operation", "wrong_contract", "future_observation", "late_persistence",
    "missing_approval", "forged_approval",
    "wrong_predecessor",
])
async def test_active_never_uses_unqualified_historical_baseline(health_repo, tamper):
    fixture, canary, rows = await real_active_fixture(health_repo)
    repo, promotion, active = fixture
    async with repo.session_factory() as session, session.begin():
        if tamper == "wrong_predecessor":
            await session.execute(text("ALTER TABLE policy_deployments DISABLE TRIGGER USER"))
            from core.distributed.promotion_models import PolicyDeploymentRecord
            predecessor = await session.get(PolicyDeploymentRecord, str(canary.deployment_id))
            predecessor.stable_policy_hash = active.candidate_policy_hash
            await session.flush()
            await session.execute(text("ALTER TABLE policy_deployments ENABLE TRIGGER USER"))
        await session.execute(text("ALTER TABLE policy_observations DISABLE TRIGGER USER"))
        for source in rows[20:]:
            row = await session.get(PolicyObservationRecord, source.observation_key)
            if tamper == "unrelated_deployment":
                row.deployment_id = str(active.deployment_id)
            elif tamper == "production":
                row.state_namespace = "production"
                row.rehearsal_id = None
            elif tamper == "wrong_stable_policy":
                row.policy_hash = active.candidate_policy_hash
            elif tamper == "wrong_rehearsal":
                row.rehearsal_id = "other"
            elif tamper == "wrong_operation":
                row.operation = "other"
            elif tamper == "wrong_contract":
                row.metric_contract_version = 2
            elif tamper == "future_observation":
                row.observed_at = active.created_at + timedelta(seconds=1)
            elif tamper == "late_persistence":
                row.created_at = active.created_at + timedelta(seconds=1)
        await session.flush()
        await session.execute(text("ALTER TABLE policy_observations ENABLE TRIGGER USER"))
        if tamper in {"missing_approval", "forged_approval"}:
            await session.execute(text("ALTER TABLE policy_gate_receipts DISABLE TRIGGER USER"))
            approval = await session.scalar(select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.gate_type == "promotion_approval"))
            if tamper == "missing_approval":
                await session.delete(approval)
            else:
                approval.details = {**approval.details, "canary_health_receipt_id": str(uuid4())}
                approval.evidence_hash = canonical_hash(approval.details)
            await session.flush()
            await session.execute(text("ALTER TABLE policy_gate_receipts ENABLE TRIGGER USER"))
    fixture, _ = await fill_window(
        fixture, state="active", stable_count=0,
        changes={"observed_at": active.created_at + timedelta(seconds=2)})
    assert (await PolicyHealthEvaluator(promotion).evaluate(active.deployment_id)).decision == "hold"
