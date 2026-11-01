"""Task9 health source regressions using real immutable PG/evaluator fixtures."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from core.distributed.ops_contracts import OpsGateReceipt, OpsPolicyDeploymentDetail
from core.distributed.ops_queries import OpsQueries
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_contracts import canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord, PolicyGateReceiptRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture

pytestmark = pytest.mark.distributed_integration


async def health_pair(fixture, current_healthy=False):
    repo, promotion, previous = fixture
    await fill_window(fixture)
    old_window = await PolicyHealthEvaluator(promotion).evaluate(previous.deployment_id)
    assert old_window.decision == "pass"
    values = {c.name: getattr(previous, c.name) for c in PolicyDeploymentRecord.__table__.columns}
    values.update(deployment_id=str(uuid4()), version=previous.version + 1,
                  command_id=f"ops-health-same-artifact-{uuid4().hex}")
    current = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(current)
        await session.flush()
        head = await session.get(PolicyEnvironmentHeadRecord, current.environment)
        head.current_deployment_id, head.current_version = current.deployment_id, current.version
    assert current.candidate_policy_hash == previous.candidate_policy_hash
    if current_healthy:
        await fill_window((repo, promotion, current))
    new_window = await PolicyHealthEvaluator(promotion).evaluate(current.deployment_id)
    assert new_window.decision == ("pass" if current_healthy else "hold")
    async with repo.session_factory() as session:
        receipts = list(await session.scalars(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.policy_hash == previous.candidate_policy_hash,
            PolicyGateReceiptRecord.gate_type == "canary_health",
        )))
    return previous, current, old_window, new_window, receipts


async def test_current_health_gate_must_not_borrow_previous_deployment_pass(health_repo):
    repo, promotion, _ = health_repo
    _, current, _, _, _ = await health_pair(health_repo)
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, current.candidate_policy_hash)
        missing, accepted = await PromotionRepository._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": current},
        )
    assert missing == ["canary_health"] and not accepted
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(current.deployment_id)
    assert detail.is_current and detail.latest_health_window.decision == "hold"
    assert not [r for r in detail.gate_receipts if r.gate_type == "canary_health"]


async def test_historical_health_gate_must_not_be_replaced_by_new_deployment(health_repo):
    repo, _, _ = health_repo
    old, current, old_window, _, receipts = await health_pair(health_repo, current_healthy=True)
    original = next(r for r in receipts if r.details["deployment_id"] == old.deployment_id)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(old.deployment_id)
    shown = next(r for r in detail.gate_receipts if r.gate_type == "canary_health")
    assert not detail.is_current
    assert str(shown.receipt_id) == original.receipt_id
    assert str(shown.health_source.deployment_id) == old.deployment_id != current.deployment_id
    assert shown.health_source.relation == "local"
    assert shown.health_source.window_id == old_window.window_id


async def append_receipt(repo, original, **changes):
    values = {c.name: getattr(original, c.name) for c in PolicyGateReceiptRecord.__table__.columns}
    if "details" not in changes:
        changes["details"] = {**original.details, "fixture_revision": uuid4().hex}
    if "evidence_hash" not in changes:
        changes["evidence_hash"] = canonical_hash(changes["details"])
    values.update({"receipt_id": str(uuid4()), "created_at": datetime.now(UTC), **changes})
    async with repo.session_factory() as session, session.begin():
        session.add(PolicyGateReceiptRecord(**values))
    return values["receipt_id"]


@pytest.mark.parametrize("state", ["shadow", "canary"])
@pytest.mark.parametrize("status", ["failed", "unknown"])
async def test_local_latest_nonpass_never_falls_back_to_old_pass(health_repo, state, status):
    fixture, _ = await fill_window(health_repo, state=state, paired=state == "shadow")
    repo, promotion, deployment = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "pass"
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord))
    receipt_id = await append_receipt(repo, original, status=status)
    shown = (await OpsQueries(repo.session_factory).get_policy_deployment(deployment.deployment_id)).gate_receipts
    assert len(shown) == 1 and shown[0].status == status
    assert str(shown[0].receipt_id) == receipt_id and shown[0].health_source.relation == "local"


@pytest.mark.parametrize("poison", [
    "deployment_version", "thresholds_hash", "window_id", "metric_contract_version",
    "gate_cohort", "candidate_stats", "observation_keys", "evidence_hash",
    "bool_version", "missing_window", "list_details", "window_from_other_deployment",
])
async def test_malformed_latest_local_relation_is_unavailable_not_old_pass(health_repo, poison):
    repo, _, _ = health_repo
    old, current, old_window, _, receipts = await health_pair(health_repo, current_healthy=True)
    original = next(r for r in receipts if r.details["deployment_id"] == current.deployment_id)
    details = dict(original.details)
    changes = {}
    if poison == "bool_version":
        details["deployment_version"] = True
    elif poison == "missing_window":
        details.pop("window_id")
    elif poison == "list_details":
        details = []
    elif poison == "window_from_other_deployment":
        details["window_id"] = old_window.window_id
    elif poison != "evidence_hash":
        details[poison] = "invalid-private-value"
    changes.update(details=details, evidence_hash=canonical_hash(details))
    if poison == "evidence_hash":
        changes["evidence_hash"] = "0" * 64
    await append_receipt(repo, original, **changes)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(current.deployment_id)
    assert detail.gate_receipts == []
    assert "invalid-private-value" not in detail.model_dump_json()
    assert str(old.deployment_id) != current.deployment_id


async def test_same_deployment_old_pass_is_distinguished_from_latest_hold(health_repo):
    from core.distributed.promotion_models import PolicyHealthWindowRecord
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    first = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session, session.begin():
        values = {c.name: getattr(first, c.name) for c in PolicyHealthWindowRecord.__table__.columns}
        values.update(window_id="9" * 64, decision="hold", evaluated_at=datetime.now(UTC),
                      created_at=datetime.now(UTC))
        session.add(PolicyHealthWindowRecord(**values))
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(deployment.deployment_id)
    assert detail.latest_health_window.decision == "hold"
    source = detail.gate_receipts[0].health_source
    assert source.window_id == first.window_id and not source.is_latest_window


@pytest.mark.parametrize("stop_at", ["shadow", "canary", "active"])
async def test_real_command_chain_has_explicit_local_and_consumed_sources(health_repo, stop_at):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stop_at, command_prefix="ops-binding")
    repo, _, deployment = fixture
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(str(deployment.deployment_id))
    health = {r.gate_type: r.health_source for r in detail.gate_receipts if r.health_source}
    assert health["shadow_health"].relation == ("local" if stop_at == "shadow" else "consumed_chain")
    if stop_at != "shadow":
        assert health["canary_health"].relation == ("local" if stop_at == "canary" else "consumed_chain")
    assert all(source.thresholds_hash == deployment.thresholds_hash for source in health.values())
    OpsPolicyDeploymentDetail.model_validate(detail.model_dump(mode="json"))


@pytest.mark.parametrize("breakage", [
    "no_audit", "wrong_thresholds", "wrong_version", "wrong_window",
])
async def test_adjacent_same_artifact_is_not_a_consumed_chain(health_repo, breakage):
    fixture, _ = await fill_window(health_repo, state="shadow", paired=True)
    repo, promotion, shadow = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(shadow.deployment_id)).decision == "pass"
    now = datetime.now(UTC)
    values = {c.name: getattr(shadow, c.name) for c in PolicyDeploymentRecord.__table__.columns}
    values.update(deployment_id=str(uuid4()), version=shadow.version + 1, state="canary",
                  created_at=now, command_id=f"ops-broken-chain-{uuid4().hex}")
    if breakage == "wrong_thresholds":
        thresholds = dict(shadow.thresholds)
        thresholds["candidate_min_runs"] += 1
        from core.distributed.promotion_contracts import PolicyThresholds
        values.update(thresholds=thresholds, thresholds_hash=PolicyThresholds(**thresholds).digest)
    canary = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(canary)
        await session.flush()
        if breakage != "no_audit":
            session.add(PolicyAuditEventRecord(
                event_id=str(uuid4()), environment="rehearsal", deployment_id=canary.deployment_id,
                event_type="promotion_transitioned", command_id=canary.command_id,
                actor="test", reason="synthetic", created_at=now,
                details={"from_state": "shadow", "to_state": "canary",
                         "from_version": shadow.version + (1 if breakage == "wrong_version" else 0),
                         "to_version": canary.version, "required_receipts": ["shadow_health"]},
            ))
    if breakage == "wrong_window":
        async with repo.session_factory() as session:
            original = await session.scalar(select(PolicyGateReceiptRecord))
        details = {**original.details, "window_id": "8" * 64}
        # New invalid receipt existed before the synthetic consumption instant.
        await append_receipt(repo, original, details=details, evidence_hash=canonical_hash(details),
                             created_at=now - timedelta(microseconds=1))
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(canary.deployment_id)
    assert not [r for r in detail.gate_receipts if r.health_source]


@pytest.mark.parametrize("field,value", [
    ("relation", "inferred"), ("deployment_version", True), ("window_id", "private"),
    ("details", {"private": "value"}),
])
async def test_health_source_contract_is_closed_and_strict(health_repo, field, value):
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(deployment.deployment_id)
    body = detail.gate_receipts[0].model_dump(mode="json")
    body["health_source"][field] = value
    with pytest.raises(ValidationError):
        OpsGateReceipt.model_validate(body)


@pytest.mark.parametrize("details", [None, {}, {"deployment_id": True},
                                      {"deployment_id": "not-a-deployment"}])
async def test_unidentifiable_latest_does_not_revive_local_pass(health_repo, details):
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord))
    await append_receipt(repo, original, details=details)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(deployment.deployment_id)
    assert not detail.gate_receipts


@pytest.mark.parametrize("status", ["failed", "unknown"])
async def test_active_local_nonpass_blocks_consumed_canary_fallback(health_repo, status):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="ops-active-local")
    repo, promotion, active = fixture
    await fill_window(fixture, state="active", stable_count=0,
                      changes={"observed_at": active.created_at + timedelta(microseconds=1)})
    assert (await PolicyHealthEvaluator(promotion).evaluate(active.deployment_id)).decision == "pass"
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(active.deployment_id),
        ))
    receipt_id = await append_receipt(repo, original, status=status)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(str(active.deployment_id))
    shown = next(r for r in detail.gate_receipts if r.gate_type == "canary_health")
    assert str(shown.receipt_id) == receipt_id and shown.status == status
    assert shown.health_source.relation == "local"


async def test_later_canary_receipt_does_not_replace_exact_consumed_evidence(health_repo):
    fixture, canary, _ = await real_active_fixture(health_repo, command_prefix="ops-consumed-exact")
    repo, _, active = fixture
    before = await OpsQueries(repo.session_factory).get_policy_deployment(str(active.deployment_id))
    expected = next(r for r in before.gate_receipts if r.gate_type == "canary_health")
    async with repo.session_factory() as session:
        original = await session.get(PolicyGateReceiptRecord, str(expected.receipt_id))
    await append_receipt(repo, original, status="unknown", issued_at=datetime.now(UTC))
    after = await OpsQueries(repo.session_factory).get_policy_deployment(str(active.deployment_id))
    shown = next(r for r in after.gate_receipts if r.gate_type == "canary_health")
    assert shown == expected and str(shown.health_source.deployment_id) == str(canary.deployment_id)


@pytest.mark.parametrize("breakage", ["valid", "no_audit", "no_approval", "wrong_command_hash", "bool_version"])
async def test_active_without_exact_approval_audit_relation_is_unavailable(health_repo, breakage):
    from core.distributed.promotion_contracts import PromotionCommand
    fixture, _, _ = await real_active_fixture(health_repo, stop_at="canary", command_prefix="ops-active-broken")
    repo, _, canary = fixture
    now = datetime.now(UTC)
    command = PromotionCommand(
        command_id=f"ops-active-invalid-{uuid4().hex}", environment="rehearsal",
        expected_version=canary.version, current_state="canary", target_state="active",
        traffic_basis_points=10000, actor="test", reason="synthetic active relationship",
    )
    async with repo.session_factory() as session:
        persisted = await session.get(PolicyDeploymentRecord, str(canary.deployment_id))
        values = {c.name: getattr(persisted, c.name) for c in PolicyDeploymentRecord.__table__.columns}
        values.update(deployment_id=str(uuid4()), command_id=command.command_id,
                      version=canary.version + 1, state="active", created_at=now,
                      traffic_basis_points=10000, actor=command.actor, reason=command.reason)
        health = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == "canary_health",
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(canary.deployment_id),
        ))
        artifact = await session.get(PolicyArtifactRecord, canary.candidate_policy_hash)
    forged = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(forged)
        await session.flush()
        if breakage != "no_audit":
            session.add(PolicyAuditEventRecord(
                event_id=str(uuid4()), command_id=forged.command_id, deployment_id=forged.deployment_id,
                environment="rehearsal", event_type="promotion_transitioned", actor=command.actor,
                reason=command.reason, created_at=now,
                details={"from_state": "canary", "to_state": "active", "from_version": canary.version,
                         "to_version": forged.version, "command_hash": "a" * 64},
            ))
        if breakage != "no_approval":
            await PromotionRepository._create_promotion_approval(
                session, command=command, artifact=artifact, canary_health=health,
                command_hash="0" * 64 if breakage == "wrong_command_hash" else "a" * 64, now=now,
            )
    if breakage == "bool_version":
        async with repo.session_factory() as session:
            approval = await session.scalar(select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.details["command_id"].as_string() == forged.command_id,
            ))
        await append_receipt(repo, approval, details={**approval.details, "canary_deployment_version": True},
                             created_at=now + timedelta(microseconds=1))
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(forged.deployment_id)
    health_sources = [r for r in detail.gate_receipts if r.health_source]
    assert bool(health_sources) == (breakage == "valid")
