"""Task9 P1: authentic frozen leaves through complete, read-only HTTP GETs."""

from copy import deepcopy
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.distributed.promotion_contracts import canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
    PolicyHealthWindowRecord, PolicyObservationRecord,
)
from tests.distributed.helpers import spec
from tests.distributed.test_ops_complete_chain import sources
from tests.distributed.test_ops_minimum_evidence import append_active
from tests.distributed.test_ops_source_integrity import api_detail
from tests.distributed.test_policy_health import health_repo, observation_key
from tests.distributed.test_policy_health_corrections import real_active_fixture

pytestmark = pytest.mark.distributed_integration


def record(name, proof):
    if os.environ.get("REVIEW_OWN"):
        directory = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
        directory.mkdir(exist_ok=True)
        with (directory / (name + ".json")).open("x") as out:
            json.dump(proof, out, indent=2, default=str)
            out.write("\n")


async def append_altered_leaf(fixture, state, poison, label="candidate"):
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
    if poison == "noncanonical_key":
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
    now = datetime.now(UTC)
    identity = {key: deepcopy(original.details[key]) for key in (
        "deployment_id", "deployment_version", "metric_contract_version", "thresholds_hash")}
    identity["observation_keys"] = keys
    wid = canonical_hash(identity)
    details = {**deepcopy(original.details), **identity, "window_id": wid}
    flat = keys["candidate"] + keys["stable"]
    wvalues.update(window_id=wid, observation_keys=keys, evaluated_at=now, created_at=now,
                   observation_start_key=flat[0], observation_end_key=flat[-1])
    if poison in {"start_key", "end_key"}:
        wvalues["observation_" + poison] = "e" * 64
    elif poison == "triggered_pass":
        wvalues["triggered_thresholds"] = ["confirmed_permission_violation"]
    rvalues.update(receipt_id=str(uuid4()), details=details, evidence_hash=canonical_hash(details),
                   issued_at=now, created_at=now)
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
        assert await session.get(PolicyGateReceiptRecord, original.receipt_id) is not None
        assert await session.get(PolicyObservationRecord, selected.observation_key) is not None
    return repo, source, artifact, receipt, {
        "poison": poison, "state": state, "label": label,
        "authority_accepts": authority is not None, "http_status": 200,
        "receipt_id": receipt.receipt_id, "window_id": wid,
        "original_receipt_id": original.receipt_id,
        "added_observations": [{c.name: getattr(row, c.name) for c in row.__table__.columns}
                               for row in added],
        "role": "append-only engineering fixture; not write-promotion success",
        "actual_model_calls": 0, "actual_model_cost_usd": "0",
    }


LOCAL_CASES = [
    (state, label, poison)
    for state in ("canary", "shadow") for label in ("candidate", "stable")
    for poison in ("valid", "noncanonical_key")
] + [
    ("canary", label, poison)
    for label in ("candidate", "stable")
    for poison in ("production_namespace", "rehearsal", "missing_rehearsal",
                   "operation", "valid_mixed_operation", "valid_namespace")
] + [
    ("shadow", label, "unpaired_shadow") for label in ("candidate", "stable")
] + [
    (state, "candidate", poison)
    for state in ("canary", "shadow")
    for poison in ("start_key", "end_key", "triggered_pass")
]
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
