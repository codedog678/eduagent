"""Task9 S1-S3: append-only real PG, canonical commands and frozen evaluator evidence."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.distributed_main import create_app
from core.distributed.ops_queries import OpsQueries
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_contracts import PolicyThresholds, PromotionCommand, canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_ops_health_binding import append_receipt
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture

pytestmark = pytest.mark.distributed_integration


async def synthetic_transition(fixture, target, breakage="valid"):
    fixture, _, _ = await real_active_fixture(
        fixture, stop_at="shadow" if target == "canary" else "canary",
        command_prefix="ops-integrity-" + uuid4().hex,
    )
    repo, _, predecessor = fixture
    now = datetime.now(UTC)
    command = PromotionCommand(
        command_id="ops-integrity-" + uuid4().hex, environment="rehearsal",
        expected_version=predecessor.version, current_state=predecessor.state, target_state=target,
        traffic_basis_points=5000 if target == "canary" else 10000,
        actor="test", reason="append-only exact relationship",
    )
    command_hash = canonical_hash({"command_type": "transition", "command": command.model_dump(mode="json")})
    stored_hash = "a" * 64 if breakage == "matching_wrong_hash" else command_hash
    required = ["shadow_health"] if target == "canary" else [
        "shadow_health", "canary_health", "promotion_approval",
    ]
    async with repo.session_factory() as session:
        source = await session.get(PolicyDeploymentRecord, str(predecessor.deployment_id))
        values = {c.name: getattr(source, c.name) for c in PolicyDeploymentRecord.__table__.columns}
        artifact = await session.get(PolicyArtifactRecord, predecessor.candidate_policy_hash)
        health = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(predecessor.deployment_id),
        ))
    values.update(
        deployment_id=str(uuid4()), command_id=command.command_id, state=target,
        version=predecessor.version + 1, traffic_basis_points=command.traffic_basis_points,
        actor=command.actor, reason=command.reason, required_receipts=required, created_at=now,
    )
    deployed = PolicyDeploymentRecord(**values)
    details = {
        "from_state": predecessor.state, "to_state": target,
        "from_version": predecessor.version, "to_version": deployed.version,
        "required_receipts": required, "command_hash": stored_hash,
    }
    audit = dict(
        event_id=str(uuid4()), command_id=command.command_id, deployment_id=deployed.deployment_id,
        environment="rehearsal", event_type="promotion_transitioned",
        actor=command.actor, reason=command.reason, created_at=now, details=details,
    )
    if breakage.startswith("audit_"):
        field = breakage.removeprefix("audit_")
        if field == "required":
            details["required_receipts"] = []
        elif field in {"from_version", "to_version"}:
            details[field] = True
        elif field == "command_hash":
            details[field] = "0" * 64
        elif field == "created_at":
            audit[field] = now - timedelta(microseconds=1)
        elif field == "environment":
            audit[field] = "production"
        elif field == "deployment_id":
            audit[field] = str(predecessor.deployment_id)
        else:
            audit[field] = "other-identity"
    async with repo.session_factory() as session, session.begin():
        session.add(deployed)
        await session.flush()
        session.add(PolicyAuditEventRecord(**audit))
        if target == "active":
            await PromotionRepository._create_promotion_approval(
                session, command=command, artifact=artifact, canary_health=health,
                command_hash=stored_hash, now=now,
            )
    return repo, deployed


async def api_detail(repo, deployment):
    app = create_app()
    app.state.distributed = SimpleNamespace(
        ops_queries=OpsQueries(repo.session_factory), settings=SimpleNamespace(ops_api_token=""),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ops/policies/deployments/" + str(deployment.deployment_id))
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("target", ["canary", "active"])
@pytest.mark.parametrize("breakage", [
    "valid", "matching_wrong_hash", "audit_required", "audit_actor", "audit_reason",
    "audit_environment", "audit_deployment_id", "audit_command_id", "audit_event_type",
    "audit_created_at", "audit_from_version", "audit_to_version", "audit_command_hash",
])
async def test_canonical_transition_and_audit_identity(health_repo, target, breakage):
    repo, deployment = await synthetic_transition(health_repo, target, breakage)
    body = await api_detail(repo, deployment)
    health = [r for r in body["gate_receipts"] if r["health_source"]]
    assert bool(health) == (breakage == "valid")
    if health:
        assert all(r["health_source"]["relation"] == "consumed_chain" for r in health)
    assert "append-only exact relationship" not in str(body)


@pytest.mark.parametrize("field,value", [
    ("issuer", "other-principal"), ("model_identity", "not-authenticated"),
    ("data_role", "simulation"), ("cost", Decimal("0.00000001")),
    ("sample_count", 0), ("status", "failed"), ("status", "unknown"),
])
async def test_latest_approval_metadata_is_not_consumption(health_repo, field, value):
    repo, deployment = await synthetic_transition(health_repo, "active")
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
        ))
    await append_receipt(repo, original, **{field: value})
    assert not [r for r in (await api_detail(repo, deployment))["gate_receipts"] if r["health_source"]]


@pytest.mark.parametrize("details", [
    [], None, {}, {"command_id": None}, {"command_id": True}, {"command_id": 12},
    {"command_id": []}, {"command_id": {}}, {"command_id": ""},
    {"command_id": "invalid command"}, {"command_id": "x" * 129},
])
async def test_genuine_chain_latest_unidentifiable_approval_masks_old_pass(health_repo, details):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="ops-latest-" + uuid4().hex)
    repo, _, deployment = fixture
    before = await api_detail(repo, deployment)
    assert len([r for r in before["gate_receipts"] if r["health_source"]]) == 2
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
        ))
    await append_receipt(repo, original, details=details)
    after = await api_detail(repo, deployment)
    assert not [r for r in after["gate_receipts"] if r["health_source"]]
    assert next(r for r in after["gate_receipts"] if r["gate_type"] == "promotion_approval")["status"] == "passed"


@pytest.mark.parametrize("other", ["identified-command", "future-issued", "wrong-protocol"])
async def test_unrelated_approval_does_not_replace_exact_consumption(health_repo, other):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="ops-unrelated-" + uuid4().hex)
    repo, _, deployment = fixture
    before = await api_detail(repo, deployment)
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
        ))
    changes = {"details": {**original.details, "command_id": "identified-other-command"}}
    if other == "future-issued":
        changes = {"details": [], "issued_at": datetime.now(UTC) + timedelta(days=1)}
    elif other == "wrong-protocol":
        changes = {"details": [], "protocol_hash": "0" * 64}
    await append_receipt(repo, original, **changes)
    after = await api_detail(repo, deployment)
    assert [r for r in after["gate_receipts"] if r["health_source"]] == [
        r for r in before["gate_receipts"] if r["health_source"]
    ]


@pytest.mark.parametrize("state", ["shadow", "canary"])
@pytest.mark.parametrize("field,value", [
    ("sample_count", 0), ("sample_count", 19), ("sample_count", 51),
    ("cost", Decimal(0)), ("cost", Decimal("0.40000001")),
])
async def test_latest_health_summary_must_match_frozen_keys(health_repo, state, field, value):
    fixture, _ = await fill_window(health_repo, state=state, paired=state == "shadow")
    repo, promotion, deployment = fixture
    assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "pass"
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord))
    assert original.sample_count == 20 and original.cost == Decimal(".4")
    await append_receipt(repo, original, **{field: value})
    assert not [r for r in (await api_detail(repo, deployment))["gate_receipts"] if r["health_source"]]


@pytest.mark.parametrize("state", ["shadow", "canary"])
async def test_exact_decimal_cost_is_not_rounded_mean_times_count(health_repo, state):
    fixture, rows = await fill_window(
        health_repo, state=state, paired=state == "shadow", count=21,
        changes=lambda i: {"cost": Decimal(".01000001") if i == 0 else Decimal(".01")},
    )
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "pass"
    body = await api_detail(repo, deployment)
    shown = next(r for r in body["gate_receipts"] if r["health_source"])
    actual = sum((row.cost for row in rows), Decimal(0))
    rounded = sum((Decimal(stats["mean_cost"]) * stats["run_count"]
                   for stats in (window.candidate_stats, window.stable_stats)), Decimal(0))
    assert actual != rounded and Decimal(shown["cost"]) == actual


@pytest.mark.parametrize("gate", ["shadow_health", "canary_health"])
@pytest.mark.parametrize("field", ["sample_count", "cost"])
async def test_inconsistent_consumed_summary_is_unavailable(health_repo, gate, field):
    fixture, _, _ = await real_active_fixture(
        health_repo, stop_at="shadow" if gate == "shadow_health" else "canary",
        command_prefix="ops-consumed-summary-" + uuid4().hex,
    )
    repo, _, predecessor = fixture
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == gate,
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(predecessor.deployment_id),
        ))
    # 在消费前 append，不篡改旧 immutable fixture，也不重跑授权 gate。
    await append_receipt(repo, original, **{field: 0})
    # 前序关系本身可规范验证，收据仍必须精确匹配冻结窗口。
    async with repo.session_factory() as session:
        predecessor = await session.get(PolicyDeploymentRecord, str(predecessor.deployment_id))
        latest = await OpsQueries._latest_health_receipt(
            session, await session.get(PolicyArtifactRecord, predecessor.candidate_policy_hash),
            predecessor, gate, datetime.now(UTC),
        )
        result = await OpsQueries(repo.session_factory)._project_health_sources(
            session, await session.get(PolicyArtifactRecord, predecessor.candidate_policy_hash),
            [(predecessor, gate, "consumed_chain", datetime.now(UTC), latest.receipt_id)],
        )
    assert not result


@pytest.mark.parametrize("poison", ["bool_count", "negative_count", "missing_count", "unknown_cost"])
async def test_frozen_summary_strict_unknown_and_numeric_boundaries(health_repo, poison):
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session:
        receipt = await session.scalar(select(PolicyGateReceiptRecord))
        values = {c.name: getattr(receipt, c.name) for c in PolicyGateReceiptRecord.__table__.columns}
        if poison == "unknown_cost":
            values["cost"] = None
        else:
            values["sample_count"] = {"bool_count": True, "negative_count": -1, "missing_count": None}[poison]
        assert not await OpsQueries._frozen_summary_matches(
            session, deployment, "canary_health", window, SimpleNamespace(**values), PolicyThresholds(),
        )
