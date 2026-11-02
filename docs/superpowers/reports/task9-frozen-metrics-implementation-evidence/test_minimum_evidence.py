import copy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.distributed.ops_queries import OpsQueries
from core.distributed.promotion_contracts import PromotionCommand, canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyGateReceiptRecord, PolicyHealthWindowRecord, PolicyObservationRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_ops_source_integrity import api_detail
from tests.distributed.test_policy_health import health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture
from test_independent_integrity import record

pytestmark = pytest.mark.distributed_integration


async def minimum_fixture(fixture, candidate_count, stable_count):
    prepared, _, _ = await real_active_fixture(
        fixture, stop_at="canary", command_prefix="fresh-minimum-" + uuid4().hex)
    repo, promotion, canary = prepared
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == "canary_health",
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(canary.deployment_id)))
        window = await session.get(PolicyHealthWindowRecord, original.details["window_id"])
        artifact = await session.get(PolicyArtifactRecord, canary.candidate_policy_hash)
        source = await session.get(PolicyDeploymentRecord, str(canary.deployment_id))
        values = {c.name: copy.deepcopy(getattr(source, c.name)) for c in source.__table__.columns}
        wvalues = {c.name: copy.deepcopy(getattr(window, c.name)) for c in window.__table__.columns}
        rvalues = {c.name: copy.deepcopy(getattr(original, c.name)) for c in original.__table__.columns}
        flat = original.details["observation_keys"]["candidate"][:candidate_count] + \
            original.details["observation_keys"]["stable"][:stable_count]
        rows = list(await session.scalars(select(PolicyObservationRecord).where(
            PolicyObservationRecord.observation_key.in_(flat))))
    receipt = original
    if (candidate_count, stable_count) != (20, 20):
        now = datetime.now(UTC)
        keys = {"candidate": original.details["observation_keys"]["candidate"][:candidate_count],
                "stable": original.details["observation_keys"]["stable"][:stable_count]}
        identity = {k: copy.deepcopy(original.details[k]) for k in (
            "deployment_id", "deployment_version", "metric_contract_version", "thresholds_hash")}
        identity["observation_keys"] = keys
        wid = canonical_hash(identity)
        candidate_stats = {**wvalues["candidate_stats"], "run_count": candidate_count}
        stable_stats = {**wvalues["stable_stats"], "run_count": stable_count}
        details = {**copy.deepcopy(original.details), **identity, "window_id": wid,
                   "candidate_stats": candidate_stats, "stable_stats": stable_stats}
        wvalues.update(window_id=wid, observation_keys=keys, candidate_stats=candidate_stats,
                       stable_stats=stable_stats, evaluated_at=now, created_at=now,
                       observation_start_key=flat[0] if flat else canonical_hash([]),
                       observation_end_key=flat[-1] if flat else canonical_hash([]))
        rvalues.update(receipt_id=str(uuid4()), details=details, evidence_hash=canonical_hash(details),
                       sample_count=candidate_count, cost=sum((r.cost for r in rows), Decimal(0)),
                       issued_at=now, created_at=now)
        receipt = PolicyGateReceiptRecord(**rvalues)
        async with repo.session_factory() as session, session.begin():
            session.add(PolicyHealthWindowRecord(**wvalues))
            await session.flush()
            session.add(receipt)
    async with repo.session_factory() as session:
        authoritative = await promotion._validated_health_window(
            session, artifact=artifact, deployment=source, gate_type="canary_health", receipt=receipt)
    local = await api_detail(repo, canary)
    now = datetime.now(UTC)
    command = PromotionCommand(
        command_id="minimum-active-" + uuid4().hex, environment="rehearsal",
        expected_version=canary.version, current_state="canary", target_state="active",
        traffic_basis_points=10000, actor="fresh-spec", reason="append-only minimum-evidence probe")
    chash = canonical_hash({"command_type": "transition", "command": command.model_dump(mode="json")})
    required = ["canary_health", "shadow_health", "promotion_approval"]
    values.update(deployment_id=str(uuid4()), version=canary.version + 1, state="active",
                  command_id=command.command_id, actor=command.actor, reason=command.reason,
                  traffic_basis_points=10000, required_receipts=required, created_at=now)
    active = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(active)
        await session.flush()
        session.add(PolicyAuditEventRecord(
            event_id=str(uuid4()), command_id=command.command_id, deployment_id=active.deployment_id,
            environment="rehearsal", event_type="promotion_transitioned",
            actor=command.actor, reason=command.reason, created_at=now,
            details={"command_hash": chash, "from_state": "canary", "to_state": "active",
                     "from_version": canary.version, "to_version": active.version,
                     "required_receipts": required}))
        await PromotionRepository._create_promotion_approval(
            session, command=command, artifact=artifact, canary_health=receipt,
            command_hash=chash, now=now)
    body = await api_detail(repo, active)
    return repo, active, {"candidate_count": candidate_count, "stable_count": stable_count,
                         "thresholds": source.thresholds, "exact_receipt": receipt.receipt_id,
                         "exact_evidence": receipt.evidence_hash, "exact_cost": str(receipt.cost),
                         "canonical_command": command.model_dump(mode="json"), "command_hash": chash,
                         "repository_accepts": authoritative is not None, "local": local, "active": body}


@pytest.mark.parametrize("candidate_count,stable_count", [(0, 0), (19, 20), (20, 19), (20, 20)])
async def test_under_minimum_frozen_pass_cannot_authenticate_chain(health_repo, candidate_count, stable_count):
    _, _, proof = await minimum_fixture(health_repo, candidate_count, stable_count)
    valid = candidate_count >= 20 and stable_count >= 20
    record(f"minimum-{candidate_count}-{stable_count}", {**proof, "expected_trusted": valid})
    assert proof["repository_accepts"] == valid
    shown = [r for r in proof["active"]["gate_receipts"] if r["health_source"]]
    assert bool(shown) == valid, "under-minimum exact Canary evidence must break entire Active chain"
    local = [r for r in proof["local"]["gate_receipts"]
             if r["gate_type"] == "canary_health" and r["health_source"] and r["status"] == "passed"]
    assert bool(local) == valid, "under-minimum local evidence cannot be a trusted passed source"
    shadow = [r for r in proof["local"]["gate_receipts"]
              if r["gate_type"] == "shadow_health" and r["health_source"]]
    assert len(shadow) == 1 and shadow[0]["status"] == "passed"
