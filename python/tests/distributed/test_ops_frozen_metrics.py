"""PG-backed GET attacks: frozen metrics must describe the exact stored rows."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from core.distributed.promotion_contracts import canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
    PolicyHealthWindowRecord, PolicyObservationRecord,
)
from tests.distributed.helpers import spec
from tests.distributed.test_ops_complete_chain import sources
from tests.distributed.test_ops_minimum_evidence import append_active
from tests.distributed.test_ops_source_integrity import api_detail
from tests.distributed.test_policy_health import fill_window, health_repo, observation_key
from tests.distributed.test_policy_health_corrections import real_active_fixture
from core.distributed.policy_health import PolicyHealthEvaluator, _observation, evaluate_window
from core.distributed.promotion_contracts import PolicyThresholds

pytestmark = pytest.mark.distributed_integration


def record(name, proof):
    if os.environ.get("REVIEW_OWN"):
        directory = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
        directory.mkdir(exist_ok=True)
        with (directory / ("metrics-" + name + ".json")).open("x") as out:
            json.dump(proof, out, indent=2, default=str)
            out.write("\n")


async def append_altered_leaf(fixture, state, poison, label="candidate", *,
                              row_changes=None, summary_change=None,
                              window_changes=None, receipt_changes=None, replacements=1):
    prepared, _, _ = await real_active_fixture(
        fixture, stop_at=state, command_prefix="leaf-get-" + uuid4().hex)
    repo, promotion, deployment = prepared
    gate = "shadow_health" if state == "shadow" else "canary_health"
    async with repo.session_factory() as session:
        source = await session.get(PolicyDeploymentRecord, str(deployment.deployment_id))
        artifact = await session.get(PolicyArtifactRecord, source.candidate_policy_hash)
        original = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == gate,
            PolicyGateReceiptRecord.details["deployment_id"].as_string() == source.deployment_id))
        window = await session.get(PolicyHealthWindowRecord, original.details["window_id"])
        wvalues = {c.name: deepcopy(getattr(window, c.name)) for c in window.__table__.columns}
        rvalues = {c.name: deepcopy(getattr(original, c.name)) for c in original.__table__.columns}
        flat = window.observation_keys["candidate"] + window.observation_keys["stable"]
        records = list(await session.scalars(select(PolicyObservationRecord).where(
            PolicyObservationRecord.observation_key.in_(flat))))
        by_key = {row.observation_key: row for row in records}
        selected = by_key[window.observation_keys[label][0]]
        values = {c.name: deepcopy(getattr(selected, c.name)) for c in selected.__table__.columns}
    parent, _ = await repo.accept_with_replay(spec("leaf-parent-" + uuid4().hex))
    values.update(run_id=parent.id, observation_key=observation_key(
        parent.id, source.deployment_id, values["cohort"], 1))
    if poison == "commit_failed":
        values.update(commit_outcome="failed", terminal_status="commit_failed")
    elif poison == "terminal_failed":
        values.update(terminal_status="terminal_failed")
    elif poison == "permission_violation":
        values.update(permission_outcome="confirmed_violation",
                      terminal_status="confirmed_permission_violation",
                      server_error_code="ConfirmedPermissionViolation")
    elif poison == "unknown_counter":
        values.update(structured_decision_count=100, unknown_decision_count=100,
                      structured_result="unknown")
    elif poison == "invalid_counter":
        values.update(structured_decision_count=1, unknown_decision_count=2)
    elif poison in {"stats_claim", "valid", "custom"}:
        pass
    elif poison == "noncanonical_key":
        values["observation_key"] = canonical_hash({"unrelated_uuid": uuid4().hex})
    elif poison == "production_namespace":
        values["state_namespace"] = "production"
    elif poison == "rehearsal":
        values["rehearsal_id"] = "unmatched-" + uuid4().hex
    elif poison in {"operation", "valid_mixed_operation"}:
        values["operation"] = "quiz_answer"
    elif poison == "missing_rehearsal":
        values["rehearsal_id"] = None
    elif poison == "valid_namespace":
        values["state_namespace"] = "rehearsal-other-fixture"
    elif poison not in {"valid", "unpaired_shadow", "start_key", "end_key", "triggered_pass"}:
        raise ValueError(poison)
    values.update(row_changes or {})
    replacement = PolicyObservationRecord(**values)
    added = [replacement]
    keys = deepcopy(window.observation_keys)

    def replace_key(which, old, new):
        by_key[new.observation_key] = new
        keys[which] = sorted(
            [key for key in keys[which] if key != old.observation_key] + [new.observation_key],
            key=lambda key: (by_key[key].observed_at, key))

    replace_key(label, selected, replacement)
    other = "stable" if label == "candidate" else "candidate"
    # Shadow 的合法替换必须同时替换配对 parent；Canary 操作混合按等比例配对。
    if (state == "shadow" and poison != "unpaired_shadow") or poison == "valid_mixed_operation":
        counterpart = next(row for row in records if row.observation_key in keys[other]
                           and (state != "shadow" or row.run_id == selected.run_id))
        paired_values = {c.name: deepcopy(getattr(counterpart, c.name))
                         for c in counterpart.__table__.columns}
        paired_values.update(run_id=parent.id, observation_key=observation_key(
            parent.id, source.deployment_id, counterpart.cohort, 1))
        if poison == "valid_mixed_operation":
            paired_values["operation"] = values["operation"]
        paired = PolicyObservationRecord(**paired_values)
        replace_key(other, counterpart, paired)
        added.append(paired)
    for index in range(1, replacements):
        old = by_key[window.observation_keys[label][index]]
        new_parent, _ = await repo.accept_with_replay(spec("metrics-parent-" + uuid4().hex))
        extra_values = {c.name: deepcopy(getattr(old, c.name)) for c in old.__table__.columns}
        extra_values.update(row_changes or {})
        extra_values.update(run_id=new_parent.id, observation_key=observation_key(
            new_parent.id, source.deployment_id, old.cohort, 1))
        extra = PolicyObservationRecord(**extra_values)
        replace_key(label, old, extra)
        added.append(extra)
        if state == "shadow":
            paired_old = next(row for row in records
                              if row.observation_key in keys[other] and row.run_id == old.run_id)
            paired_values = {c.name: deepcopy(getattr(paired_old, c.name))
                             for c in paired_old.__table__.columns}
            paired_values.update(run_id=new_parent.id, observation_key=observation_key(
                new_parent.id, source.deployment_id, paired_old.cohort, 1))
            extra_pair = PolicyObservationRecord(**paired_values)
            replace_key(other, paired_old, extra_pair)
            added.append(extra_pair)
    now = datetime.now(UTC)
    identity = {key: deepcopy(original.details[key]) for key in (
        "deployment_id", "deployment_version", "metric_contract_version", "thresholds_hash")}
    identity["observation_keys"] = keys
    wid = canonical_hash(identity)
    details = {**deepcopy(original.details), **identity, "window_id": wid}
    if poison == "stats_claim":
        wvalues["candidate_stats"]["commit_failure_rate"] = "0.01"
        details["candidate_stats"] = deepcopy(wvalues["candidate_stats"])
    flat = keys["candidate"] + keys["stable"]
    wvalues.update(window_id=wid, observation_keys=keys, evaluated_at=now, created_at=now,
                   observation_start_key=flat[0], observation_end_key=flat[-1])
    if poison in {"start_key", "end_key"}:
        wvalues["observation_" + poison] = "e" * 64
    elif poison == "triggered_pass":
        wvalues["triggered_thresholds"] = ["confirmed_permission_violation"]
    if summary_change:
        summary_change(wvalues[label + "_stats"])
        details[label + "_stats"] = deepcopy(wvalues[label + "_stats"])
    wvalues.update(window_changes or {})
    rvalues.update(receipt_id=str(uuid4()), details=details, evidence_hash=canonical_hash(details),
                   issued_at=now, created_at=now)
    rvalues.update(receipt_changes or {})
    receipt = PolicyGateReceiptRecord(**rvalues)
    async with repo.session_factory() as session, session.begin():
        session.add_all(added)
        session.add(PolicyHealthWindowRecord(**wvalues))
        await session.flush()
        session.add(receipt)
    # 权威先验证同一精确叶子；GET/setup 错误不作为业务 RED。
    async with repo.session_factory() as session:
        authority = await promotion._validated_health_window(
            session, artifact=artifact, deployment=source, gate_type=gate, receipt=receipt)
        exact_rows = list(await session.scalars(select(PolicyObservationRecord).where(
            PolicyObservationRecord.observation_key.in_(flat))))
        actual_by_key = {row.observation_key: row for row in exact_rows}
        try:
            evaluation = evaluate_window(
                [_observation(actual_by_key[key]) for key in keys["candidate"]],
                [_observation(actual_by_key[key]) for key in keys["stable"]],
                PolicyThresholds.model_validate(source.thresholds),
            )
            evaluation_proof = {
                "decision": evaluation.decision, "reasons": evaluation.reasons,
                "candidate_stats": evaluation.candidate_stats,
                "stable_stats": evaluation.stable_stats,
            }
        except ValueError as exc:
            evaluation_proof = {"schema_rejected": type(exc).__name__}
        assert await session.get(PolicyGateReceiptRecord, original.receipt_id) is not None
        assert await session.get(PolicyObservationRecord, selected.observation_key) is not None
    return repo, source, artifact, receipt, {
        "poison": poison, "state": state, "label": label,
        "authority_accepts": authority is not None, "http_status": 200,
        "receipt_id": receipt.receipt_id, "window_id": wid,
        "original_receipt_id": original.receipt_id,
        "stored_window_stats": {
            "candidate_stats": wvalues["candidate_stats"],
            "stable_stats": wvalues["stable_stats"],
        },
        "independent_exact_row_evaluation": evaluation_proof,
        "original_rows_retained": True,
        "added_observations": [{c.name: getattr(row, c.name) for c in row.__table__.columns}
                               for row in added],
        "role": "append-only engineering fixture; not write-promotion success",
        "actual_model_calls": 0, "actual_model_cost_usd": "0",
    }


LOCAL_CASES = [(state, label, poison)
               for state in ("canary", "shadow")
               for label in ("candidate", "stable")
               for poison in ("valid", "commit_failed", "terminal_failed",
                              "permission_violation", "unknown_counter",
                              "invalid_counter", "stats_claim")]
ACTIVE_CASES = [(label, poison) for state, label, poison in LOCAL_CASES if state == "canary"]


@pytest.mark.parametrize("state,label,poison", LOCAL_CASES)
async def test_local_get_authenticates_entire_frozen_leaf(health_repo, state, label, poison):
    repo, source, _, receipt, proof = await append_altered_leaf(health_repo, state, poison, label)
    valid = poison.startswith("valid")
    assert proof["authority_accepts"] == valid
    body = await api_detail(repo, source)
    record(f"local-{state}-{label}-{poison}", {**proof, "body": body})
    gate = "shadow_health" if state == "shadow" else "canary_health"
    shown = sources(body)
    assert (gate in shown) == valid
    if valid:
        assert shown[gate]["receipt_id"] == receipt.receipt_id
        assert shown[gate]["health_source"]["relation"] == "local"
    if state == "canary":
        assert shown["shadow_health"]["health_source"]["relation"] == "consumed_chain"


@pytest.mark.parametrize("label,poison", ACTIVE_CASES)
async def test_active_get_rejects_invalid_exact_leaf_without_fallback(health_repo, label, poison):
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", poison, label)
    valid = poison.startswith("valid")
    assert proof["authority_accepts"] == valid
    active = await append_active(repo, source, artifact, receipt)
    body = await api_detail(repo, active)
    record(f"active-{label}-{poison}", {**proof, "body": body})
    shown = sources(body)
    assert set(shown) == ({"canary_health", "shadow_health"} if valid else set())
    if valid:
        assert shown["canary_health"]["receipt_id"] == receipt.receipt_id
        assert all(row["health_source"]["relation"] == "consumed_chain" for row in shown.values())


METRICS = [
    "commit_failure_rate", "terminal_failure_rate", "p95_latency", "mean_cost",
    "structured_decision_count", "unknown_decision_count", "unknown_rate",
    "fault_injected_count", "injected_commit_failure_count", "natural_failure_count",
]
CLAIMS = [(field, mode) for field in METRICS for mode in ("missing", "type", "value")] + [
    ("extra", "extra"),
]


@pytest.mark.parametrize("label", ["candidate", "stable"])
@pytest.mark.parametrize("field,mode", CLAIMS)
async def test_complete_summaries_not_two_matching_claims(health_repo, label, field, mode):
    def alter(stats):
        if mode == "missing":
            stats.pop(field)
        elif mode == "extra":
            stats["unrecognized_metric"] = 0
        elif mode == "type":
            stats[field] = True if isinstance(stats[field], int) else 0
        else:
            stats[field] = stats[field] + 1 if isinstance(stats[field], int) else "0.987654321"
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", "custom", label, summary_change=alter)
    assert not proof["authority_accepts"]
    local = await api_detail(repo, source)
    active = await append_active(repo, source, artifact, receipt)
    body = await api_detail(repo, active)
    record(f"summary-{label}-{field}-{mode}", {**proof, "local": local, "active": body})
    assert "canary_health" not in sources(local)
    assert "shadow_health" in sources(local)
    assert not sources(body)


SCHEMA_ATTACKS = [
    {"structured_decision_count": -1}, {"unknown_decision_count": -1},
    {"structured_decision_count": None, "unknown_decision_count": 1},
    {"unknown_decision_count": 999},
    {"terminal_status": "unrecognized"}, {"commit_outcome": "unrecognized"},
    {"permission_outcome": "unrecognized"}, {"structured_result": "unrecognized"},
    {"source_trace_id": "not-a-trace"}, {"operation": ""},
    {"state_namespace": ""}, {"latency_seconds": Decimal("-1")},
    {"latency_seconds": Decimal("NaN")}, {"latency_seconds": Decimal("Infinity")},
    {"cost": Decimal("-1")}, {"cost": Decimal("NaN")}, {"cost": Decimal("Infinity")},
    {"input_tokens": -1}, {"output_tokens": -1},
]


@pytest.mark.parametrize("label", ["candidate", "stable"])
@pytest.mark.parametrize("changes", SCHEMA_ATTACKS)
async def test_actual_observation_schema_is_authenticated(health_repo, label, changes):
    if any(isinstance(value, Decimal) and value.is_infinite() for value in changes.values()):
        with pytest.raises(DBAPIError, match="cannot hold an infinite value"):
            await append_altered_leaf(
                health_repo, "canary", "custom", label, row_changes=changes)
        record(f"schema-db-reject-{label}-" + next(iter(changes)), {
            "database_rejected_infinite_numeric": True, "no_get_authenticity_claim": True,
            "role": "database boundary control", "changes": changes,
        })
        return
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", "custom", label, row_changes=changes)
    assert not proof["authority_accepts"]
    local = await api_detail(repo, source)
    active = await append_active(repo, source, artifact, receipt)
    body = await api_detail(repo, active)
    record(f"schema-{label}-" + next(iter(changes)) + "-" + str(next(iter(changes.values()))),
           {**proof, "local": local, "active": body})
    assert "canary_health" not in sources(local)
    assert "shadow_health" in sources(local)
    assert not sources(body)


@pytest.mark.parametrize("changes,count,reason", [
    ({"latency_seconds": Decimal("1.5")}, 2, "latency_increase_rate"),
    ({"cost": Decimal(".07")}, 1, "mean_cost_increase_rate"),
    ({"commit_outcome": "failed", "terminal_status": "commit_failed"}, 1, "commit_failure_rate"),
    ({"terminal_status": "terminal_failed"}, 2, "terminal_failure_rate"),
    ({"structured_decision_count": 100, "unknown_decision_count": 100}, 1, "unknown_rate"),
])
async def test_actual_threshold_failure_cannot_claim_pass(health_repo, changes, count, reason):
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", "custom", row_changes=changes, replacements=count)
    assert not proof["authority_accepts"]
    assert proof["independent_exact_row_evaluation"]["decision"] == "fail"
    assert reason in proof["independent_exact_row_evaluation"]["reasons"]
    active = await append_active(repo, source, artifact, receipt)
    body = await api_detail(repo, active)
    record(f"threshold-{reason}", {**proof, "body": body})
    assert not sources(body)


@pytest.mark.parametrize("changes", [
    {"triggered_thresholds": ["unknown_rate"]},
    {"triggered_thresholds": [True]},
    {"decision": "hold"},
    {"decision": "fail"},
])
async def test_frozen_decision_and_triggered_thresholds_are_exact(health_repo, changes):
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", "custom", window_changes=changes)
    assert not proof["authority_accepts"]
    active = await append_active(repo, source, artifact, receipt)
    body = await api_detail(repo, active)
    record("decision-" + canonical_hash(changes), {**proof, "body": body})
    assert not sources(body)


@pytest.mark.parametrize("state", ["shadow", "canary"])
@pytest.mark.parametrize("diagnostic", ["unmatched", "unknown_cost", "unknown_decisions"])
async def test_real_worker_nonpass_and_unknown_metrics_survive_get(health_repo, state, diagnostic):
    changes = (
        {"cost": None} if diagnostic == "unknown_cost" else
        {"structured_decision_count": None, "unknown_decision_count": None,
         "structured_result": "unavailable"} if diagnostic == "unknown_decisions" else {}
    )
    fixture, rows = await fill_window(
        health_repo, state=state, count=20,
        stable_count=19 if diagnostic == "unmatched" else 20,
        paired=state == "shadow", changes=changes,
    )
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "hold"
    if diagnostic == "unmatched":
        assert window.triggered_thresholds == [
            "baseline_shortage", "cost_unavailable", "matched_window_incomplete",
        ]
    elif diagnostic == "unknown_cost":
        assert window.candidate_stats["mean_cost"] is None
        assert window.triggered_thresholds == ["cost_unavailable"]
    else:
        assert window.candidate_stats["unknown_rate"] is None
        assert window.triggered_thresholds == ["structured_decisions_unavailable"]
    receipt = None
    if diagnostic != "unknown_cost":
        # worker 不签发 nonpass receipt；仅追加诊断展示 fixture，不伪称正式发布。
        async with repo.session_factory() as session, session.begin():
            artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
            details = {
                "deployment_id": str(deployment.deployment_id),
                "deployment_version": deployment.version, "metric_contract_version": 1,
                "thresholds_hash": deployment.thresholds_hash,
                "observation_keys": window.observation_keys, "window_id": window.window_id,
                "gate_cohort": "shadow" if state == "shadow" else "candidate",
                "candidate_stats": window.candidate_stats, "stable_stats": window.stable_stats,
            }
            now = datetime.now(UTC)
            receipt = PolicyGateReceiptRecord(
                receipt_id=str(uuid4()), policy_hash=artifact.policy_hash,
                gate_type="shadow_health" if state == "shadow" else "canary_health",
                status="unknown", evidence_hash=canonical_hash(details),
                protocol_hash=artifact.protocol_hash, runtime_hash=artifact.runtime_hash,
                source_revision=artifact.source_revision, data_role=artifact.data_role,
                issuer="policy-health", model_identity="server-policy-health-v1",
                sample_count=20, cost=sum((row.cost for row in rows), Decimal(0)),
                details=details, issued_at=now, created_at=now,
            )
            session.add(receipt)
    body = await api_detail(repo, deployment)
    record(f"worker-{state}-{diagnostic}", {
        "body": body, "worker_reasons": window.triggered_thresholds,
        "role": "real worker window; optional append-only nonpass display receipt",
        "actual_model_calls": 0, "actual_model_cost_usd": "0",
    })
    assert body["latest_health_window"]["decision"] == "hold"
    if diagnostic == "unknown_cost":
        assert body["latest_health_window"]["candidate_stats"]["mean_cost"] is None
        assert not sources(body)
    else:
        shown = sources(body)["shadow_health" if state == "shadow" else "canary_health"]
        assert shown["status"] == "unknown" and shown["receipt_id"] == receipt.receipt_id
        assert shown["health_source"]["window_decision"] == "hold"


@pytest.mark.parametrize("state", ["shadow", "canary"])
@pytest.mark.parametrize("changes", [
    {"permission_outcome": "denied"},
    {"permission_outcome": "isolated"},
    {"fault_injected": True, "injected": True},
    {"unknown_decision_count": 0, "structured_decision_count": 20},
])
async def test_genuine_legal_metrics_are_not_blanket_deleted(health_repo, state, changes):
    fixture, _ = await fill_window(health_repo, state=state, count=20,
                                   paired=state == "shadow", changes=changes)
    repo, promotion, deployment = fixture
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    assert window.decision == "pass" and window.triggered_thresholds == []
    body = await api_detail(repo, deployment)
    record(f"legal-{state}-" + canonical_hash(changes), {"body": body, "changes": changes})
    shown = sources(body)["shadow_health" if state == "shadow" else "canary_health"]
    assert shown["status"] == "passed"
    assert shown["health_source"]["relation"] == "local"


@pytest.mark.parametrize("label", ["candidate", "stable"])
@pytest.mark.parametrize("field", ["unknown_decision_count", "fault_injected_count"])
async def test_receipt_summary_same_value_wrong_type_is_not_authentic(health_repo, label, field):
    repo, source, artifact, receipt, proof = await append_altered_leaf(
        health_repo, "canary", "valid", label)
    values = {c.name: deepcopy(getattr(receipt, c.name)) for c in receipt.__table__.columns}
    assert values["details"][label + "_stats"][field] == 0
    values["details"][label + "_stats"][field] = False
    values.update(receipt_id=str(uuid4()), issued_at=datetime.now(UTC), created_at=datetime.now(UTC),
                  evidence_hash=canonical_hash(values["details"]))
    typed = PolicyGateReceiptRecord(**values)
    async with repo.session_factory() as session, session.begin():
        session.add(typed)
    local = await api_detail(repo, source)
    active = await append_active(repo, source, artifact, typed)
    body = await api_detail(repo, active)
    record(f"receipt-type-{label}-{field}", {**proof, "local": local, "active": body})
    assert "canary_health" not in sources(local)
    assert "shadow_health" in sources(local)
    assert not sources(body)
