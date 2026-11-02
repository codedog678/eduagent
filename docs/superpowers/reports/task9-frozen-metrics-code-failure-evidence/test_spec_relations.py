from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
import json
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from types import SimpleNamespace

from api.distributed_main import create_app
from core.distributed.ops_queries import OpsQueries
from core.distributed.promotion_contracts import PromotionCommand, canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyGateReceiptRecord, PolicyEnvironmentHeadRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_policy_health import health_repo, fill_window
from tests.distributed.test_policy_health_corrections import real_active_fixture
from tests.distributed.test_ops_health_binding import append_receipt
from core.distributed.policy_health import PolicyHealthEvaluator

OWN = Path(__file__).parent
OWN = OWN / os.environ["EVIDENCE_RUN"]
OWN.mkdir(exist_ok=True)
pytestmark = pytest.mark.distributed_integration


async def synthetic_active(fixture, breakage):
    prepared, _, _ = await real_active_fixture(
        fixture, stop_at="canary", command_prefix="independent-" + uuid4().hex)
    repo, promotion, canary = prepared
    now = datetime.now(UTC)
    command = PromotionCommand(
        command_id="independent-active-" + uuid4().hex, environment="rehearsal",
        expected_version=canary.version, current_state="canary", target_state="active",
        traffic_basis_points=10000, actor="test", reason="synthetic exact chain validation")
    actual_hash = canonical_hash({"command_type": "transition", "command": command.model_dump(mode="json")})
    stored_hash = "a" * 64 if breakage == "matching_wrong_command_hash" else actual_hash
    async with repo.session_factory() as session:
        persisted = await session.get(PolicyDeploymentRecord, str(canary.deployment_id))
        values = {c.name: getattr(persisted, c.name) for c in PolicyDeploymentRecord.__table__.columns}
        health = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == "canary_health",
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(canary.deployment_id)))
        artifact = await session.get(PolicyArtifactRecord, canary.candidate_policy_hash)
    required = ["shadow_health", "canary_health", "promotion_approval"]
    values.update(deployment_id=str(uuid4()), version=canary.version + 1, state="active",
                  command_id=command.command_id, created_at=now, traffic_basis_points=10000,
                  actor=command.actor, reason=command.reason, required_receipts=required)
    active = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(active)
        await session.flush()
        details = {"from_state": "canary", "to_state": "active",
                   "from_version": canary.version, "to_version": active.version,
                   "command_hash": stored_hash, "required_receipts": required}
        if breakage == "audit_missing_required":
            details["required_receipts"] = []
        session.add(PolicyAuditEventRecord(
            event_id=str(uuid4()), command_id=active.command_id, deployment_id=active.deployment_id,
            environment="rehearsal", event_type="promotion_transitioned",
            actor="different-principal" if breakage == "audit_wrong_actor" else command.actor,
            reason=command.reason, created_at=now, details=details))
        await PromotionRepository._create_promotion_approval(
            session, command=command, artifact=artifact, canary_health=health,
            command_hash=stored_hash, now=now)
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        head.current_deployment_id, head.current_version = active.deployment_id, active.version
    if breakage in {"approval_wrong_issuer", "approval_wrong_model", "approval_wrong_role",
                    "approval_malformed_latest"}:
        async with repo.session_factory() as session:
            original = await session.scalar(select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.details["command_id"].as_string() == active.command_id))
        changes = {"created_at": now + timedelta(microseconds=1)}
        if breakage == "approval_wrong_issuer":
            changes["issuer"] = "different-principal"
        elif breakage == "approval_wrong_model":
            changes["model_identity"] = "not-authenticated-command"
        elif breakage == "approval_wrong_role":
            changes["data_role"] = "simulation"
        else:
            changes["details"] = []
        await append_receipt(repo, original, **changes)
    return repo, active, actual_hash, stored_hash


@pytest.mark.parametrize("breakage", [
    "valid", "matching_wrong_command_hash", "audit_missing_required", "audit_wrong_actor",
    "approval_wrong_issuer", "approval_wrong_model", "approval_wrong_role",
    "approval_malformed_latest",
])
async def test_exact_active_relation_fails_closed(health_repo, breakage):
    repo, active, actual_hash, stored_hash = await synthetic_active(health_repo, breakage)
    queries = OpsQueries(repo.session_factory)
    app = create_app()
    app.state.distributed = SimpleNamespace(
        ops_queries=queries, settings=SimpleNamespace(ops_api_token=""))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ops/policies/deployments/" + active.deployment_id)
    assert response.status_code == 200
    body = response.json()
    health = [r for r in body["gate_receipts"] if r["health_source"]]
    (OWN / ("relation-" + breakage + ".json")).write_text(json.dumps({
        "role": "synthetic engineering only; append-only real PG and evaluator; model calls zero",
        "breakage": breakage, "actual_command_hash": actual_hash,
        "stored_command_hash": stored_hash, "body": body}, indent=2) + "\n")
    assert bool(health) == (breakage == "valid"), (
        "broken approval/audit binding must not be labelled consumed-chain passed")


@pytest.mark.parametrize("field", ["sample_count", "cost"])
async def test_health_receipt_summary_matches_frozen_source(health_repo, field):
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord))
    await append_receipt(repo, original, **{field: 0})
    body = (await OpsQueries(repo.session_factory).get_policy_deployment(
        deployment.deployment_id)).model_dump(mode="json")
    (OWN / ("summary-" + field + ".json")).write_text(json.dumps(body, indent=2) + "\n")
    assert not [r for r in body["gate_receipts"] if r["health_source"]], (
        "inconsistent latest receipt metadata must not get green source attribution")


async def test_valid_real_chain_is_not_hidden(health_repo):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="positive-" + uuid4().hex)
    repo, _, active = fixture
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(str(active.deployment_id))
    health = [r for r in detail.gate_receipts if r.health_source]
    assert {r.gate_type for r in health} == {"shadow_health", "canary_health"}
    assert all(r.health_source.relation == "consumed_chain" and r.status == "passed" for r in health)
