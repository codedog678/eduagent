import copy
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from core.distributed.ops_queries import OpsQueries
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_contracts import PolicyThresholds, PromotionCommand, canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
    PolicyHealthWindowRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_ops_health_binding import append_receipt
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture
from tests.distributed.test_ops_source_integrity import api_detail

pytestmark = pytest.mark.distributed_integration
OWN = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
OWN.mkdir(exist_ok=True)


def record(name, data):
    path = OWN / (name + ".json")
    assert not path.exists()
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


async def transition_fixture(fixture, target, command_poison=None, health_poison=None):
    prepared, _, _ = await real_active_fixture(
        fixture, stop_at="shadow" if target == "canary" else "canary",
        command_prefix="fresh-wholespec-" + uuid4().hex,
    )
    repo, _, predecessor = prepared
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == ("shadow_health" if target == "canary" else "canary_health"),
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == str(predecessor.deployment_id),
        ))
        artifact = await session.get(PolicyArtifactRecord, predecessor.candidate_policy_hash)
        source = await session.get(PolicyDeploymentRecord, str(predecessor.deployment_id))
        values = {c.name: copy.deepcopy(getattr(source, c.name)) for c in source.__table__.columns}
    health = original
    if health_poison:
        ident = await append_receipt(repo, original, **health_poison)
        async with repo.session_factory() as session:
            health = await session.get(PolicyGateReceiptRecord, ident)
    now = datetime.now(UTC)
    command = PromotionCommand(
        command_id="fresh-command-" + uuid4().hex, environment="rehearsal",
        expected_version=predecessor.version, current_state=predecessor.state, target_state=target,
        traffic_basis_points=5000 if target == "canary" else 10000,
        actor="fresh-spec-principal", reason="fresh immutable relationship validation",
    )
    actual = canonical_hash({"command_type": "transition", "command": command.model_dump(mode="json")})
    poisoned = command.model_dump(mode="json")
    if command_poison:
        poisoned.update(command_poison)
    stored = canonical_hash({"command_type": "transition", "command": poisoned})
    required = ["shadow_health"] if target == "canary" else [
        "canary_health", "shadow_health", "promotion_approval",
    ]
    values.update(deployment_id=str(uuid4()), version=predecessor.version + 1,
                  state=target, command_id=command.command_id, actor=command.actor,
                  reason=command.reason, created_at=now,
                  traffic_basis_points=command.traffic_basis_points, required_receipts=required)
    deployed = PolicyDeploymentRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(deployed)
        await session.flush()
        session.add(PolicyAuditEventRecord(
            event_id=str(uuid4()), command_id=command.command_id, deployment_id=deployed.deployment_id,
            environment=command.environment, event_type="promotion_transitioned",
            actor=command.actor, reason=command.reason, created_at=now,
            details={"command_hash": stored, "from_state": predecessor.state, "to_state": target,
                     "from_version": predecessor.version, "to_version": deployed.version,
                     "required_receipts": required},
        ))
        if target == "active":
            await PromotionRepository._create_promotion_approval(
                session, command=command, artifact=artifact, canary_health=health,
                command_hash=stored, now=now,
            )
    return repo, deployed, {"canonical_command": command.model_dump(mode="json"),
                            "actual_hash": actual, "stored_hash": stored,
                            "referenced_health": health.receipt_id,
                            "original_health": original.receipt_id}


@pytest.mark.parametrize("target", ["canary", "active"])
@pytest.mark.parametrize("field", [
    "command_id", "environment", "expected_version", "current_state", "target_state",
    "traffic_basis_points", "actor", "reason", "valid",
])
async def test_every_canonical_command_field_is_actually_consumed(health_repo, target, field):
    bad = {
        "command_id": "other-explicit-command", "environment": "production", "expected_version": 999,
        "current_state": "registered", "target_state": "frozen", "traffic_basis_points": 1234,
        "actor": "other-principal", "reason": "different-reason",
    }
    repo, deployed, proof = await transition_fixture(
        health_repo, target, None if field == "valid" else {field: bad[field]},
    )
    body = await api_detail(repo, deployed)
    record("canonical-" + target + "-" + field, {**proof, "body": body})
    shown = [r for r in body["gate_receipts"] if r["health_source"]]
    assert bool(shown) == (field == "valid")


@pytest.mark.parametrize("field,value", [
    ("command_hash", "f" * 64), ("actor", "wrong-actor"), ("reason", "wrong-reason"),
    ("canary_deployment_id", "00000000-0000-0000-0000-000000000000"),
    ("canary_health_receipt_id", "00000000-0000-0000-0000-000000000000"),
    ("canary_deployment_version", True), ("canary_thresholds_hash", "e" * 64),
    ("canary_health_evidence_hash", "d" * 64),
])
async def test_latest_approval_relation_fields_mask_old_pass(health_repo, field, value):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="fresh-approval-" + uuid4().hex)
    repo, _, deployed = fixture
    before = await api_detail(repo, deployed)
    assert len([r for r in before["gate_receipts"] if r["health_source"]]) == 2
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployed.command_id,
        ))
    await append_receipt(repo, original, details={**original.details, field: value})
    body = await api_detail(repo, deployed)
    record("approval-" + field, {"body": body, "expected": "no consumed sources"})
    assert not [r for r in body["gate_receipts"] if r["health_source"]]


@pytest.mark.parametrize("target", ["canary", "active"])
@pytest.mark.parametrize("field,value", [
    ("sample_count", 0), ("cost", Decimal(0)), ("status", "unknown"),
    ("protocol_hash", "e" * 64), ("gate_type", "formal_holdout"),
])
async def test_poisoned_referenced_health_cannot_prove_complete_consumption(health_repo, target, field, value):
    repo, deployed, proof = await transition_fixture(health_repo, target, health_poison={field: value})
    body = await api_detail(repo, deployed)
    record("referenced-" + target + "-" + field, {**proof, "poison": {field: value}, "body": body})
    gate = "shadow_health" if target == "canary" else "canary_health"
    # A foreign artifact/gate is outside latest's scope; it may not be consumed by Active approval.
    if target == "canary" and field in {"protocol_hash", "gate_type"}:
        assert any(r["gate_type"] == gate for r in body["gate_receipts"])
    else:
        assert not any(r["gate_type"] == gate for r in body["gate_receipts"])
    if target == "active":
        assert not [r for r in body["gate_receipts"] if r["health_source"]], (
            "invalid exact canary health must not authenticate an Active consumed chain")


@pytest.mark.parametrize("poison", [
    "valid", "extra_key", "duplicate", "missing", "reversed", "overbound",
    "bool_run_count", "wrong_run_count", "nan_fee", "infinite_fee", "negative_fee",
])
async def test_frozen_key_validation_and_bounded_sql(health_repo, poison):
    fixture, rows = await fill_window(health_repo)
    repo, promotion, deployed = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployed.deployment_id)
    async with repo.session_factory() as session:
        receipt = await session.scalar(select(PolicyGateReceiptRecord))
        window = await session.get(PolicyHealthWindowRecord, window.window_id)
        frozen = SimpleNamespace(**{c.name: copy.deepcopy(getattr(window, c.name))
                                    for c in window.__table__.columns})
        summary = SimpleNamespace(**{c.name: getattr(receipt, c.name)
                                     for c in receipt.__table__.columns})
        if poison == "extra_key":
            frozen.observation_keys["extra"] = []
        elif poison == "duplicate":
            frozen.observation_keys["candidate"][0] = frozen.observation_keys["candidate"][1]
        elif poison == "missing":
            frozen.observation_keys["candidate"][0] = "f" * 64
        elif poison == "reversed":
            frozen.observation_keys["candidate"].reverse()
        elif poison == "overbound":
            frozen.observation_keys["candidate"] *= 3
        elif poison == "bool_run_count":
            frozen.candidate_stats["run_count"] = True
        elif poison == "wrong_run_count":
            frozen.candidate_stats["run_count"] = 19
        elif poison in {"nan_fee", "infinite_fee", "negative_fee"}:
            summary.cost = {"nan_fee": Decimal("NaN"), "infinite_fee": Decimal("Infinity"),
                            "negative_fee": Decimal("-1")}[poison]
        statements = []
        engine = repo.session_factory.kw["bind"].sync_engine

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append({"sql": statement, "parameters": parameters})

        event.listen(engine, "before_cursor_execute", capture)
        try:
            actual = await OpsQueries._frozen_summary_matches(
                session, deployed, "canary_health", frozen, summary, PolicyThresholds(),
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)
    record("frozen-" + poison, {"actual": actual, "expected": poison == "valid",
                                "statements": statements, "actual_fee": sum((r.cost for r in rows), Decimal(0))})
    assert actual == (poison == "valid")
    for query in statements:
        assert "policy_observations.observation_key IN" in query["sql"]
        assert "LIMIT" in query["sql"]
        assert len(query["parameters"]) <= 101
