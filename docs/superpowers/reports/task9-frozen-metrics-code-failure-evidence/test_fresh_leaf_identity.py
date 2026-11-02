"""Independent WHOLE CODE counterexamples, append-only PG fixtures only."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
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


async def altered_leaf(fixture, state, poison):
    prepared, _, _ = await real_active_fixture(
        fixture, stop_at=state, command_prefix="fresh-code-leaf-" + uuid4().hex)
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
        by_key = {r.observation_key: r for r in records}
        selected = by_key[window.observation_keys["candidate"][0]]
        values = {c.name: deepcopy(getattr(selected, c.name)) for c in selected.__table__.columns}
        original_key = selected.observation_key
    parent, _ = await repo.accept_with_replay(spec("fresh-leaf-parent-" + uuid4().hex))
    values["run_id"] = parent.id
    values["observation_key"] = observation_key(parent.id, source.deployment_id, values["cohort"], 1)
    if poison == "noncanonical_key":
        values["observation_key"] = canonical_hash({"unrelated_uuid": uuid4().hex})
    elif poison == "production_namespace":
        values["state_namespace"] = "production"
    elif poison == "wrong_distribution":
        values["rehearsal_id"] = "unmatched-rehearsal-" + uuid4().hex
    elif poison not in {"valid", "unpaired_shadow", "start_key", "triggered_pass"}:
        raise ValueError(poison)
    replacement = PolicyObservationRecord(**values)
    now = datetime.now(UTC)
    keys = deepcopy(window.observation_keys)
    keys["candidate"] = sorted(
        [key for key in keys["candidate"] if key != original_key] + [replacement.observation_key],
        key=lambda key: (replacement.observed_at if key == replacement.observation_key else by_key[key].observed_at, key))
    new_records = [replacement if key == replacement.observation_key else by_key[key]
                   for key in keys["candidate"] + keys["stable"]]
    # Valid Shadow control must retain the exact parent pairing in its stable half.
    if state == "shadow" and poison != "unpaired_shadow":
        old_stable = next(r for r in records if r.cohort == "stable" and r.run_id == selected.run_id)
        stable_values = {c.name: deepcopy(getattr(old_stable, c.name)) for c in old_stable.__table__.columns}
        stable_values["run_id"] = parent.id
        stable_values["observation_key"] = observation_key(parent.id, source.deployment_id, "stable", 1)
        stable = PolicyObservationRecord(**stable_values)
        keys["stable"] = sorted(
            [key for key in keys["stable"] if key != old_stable.observation_key] + [stable.observation_key],
            key=lambda key: (stable.observed_at if key == stable.observation_key else by_key[key].observed_at, key))
    else:
        stable = None
    identity = {key: deepcopy(original.details[key]) for key in (
        "deployment_id", "deployment_version", "metric_contract_version", "thresholds_hash")}
    identity["observation_keys"] = keys
    wid = canonical_hash(identity)
    details = {**deepcopy(original.details), **identity, "window_id": wid}
    flat = keys["candidate"] + keys["stable"]
    wvalues.update(window_id=wid, observation_keys=keys, evaluated_at=now, created_at=now,
                   observation_start_key=flat[0], observation_end_key=flat[-1])
    if poison == "start_key":
        wvalues["observation_start_key"] = "e" * 64
    elif poison == "triggered_pass":
        wvalues["triggered_thresholds"] = ["confirmed_permission_violation"]
    rvalues.update(receipt_id=str(uuid4()), details=details, evidence_hash=canonical_hash(details),
                   issued_at=now, created_at=now)
    receipt = PolicyGateReceiptRecord(**rvalues)
    async with repo.session_factory() as session, session.begin():
        session.add(replacement)
        if stable is not None:
            session.add(stable)
        session.add(PolicyHealthWindowRecord(**wvalues))
        await session.flush()
        session.add(receipt)
    async with repo.session_factory() as session:
        authority = await promotion._validated_health_window(
            session, artifact=artifact, deployment=source, gate_type=gate, receipt=receipt)
    local = await api_detail(repo, source)
    active = None
    if state == "canary":
        active_deployment = await append_active(repo, source, artifact, receipt)
        active = await api_detail(repo, active_deployment)
    return {
        "poison": poison, "state": state, "authority_accepts": authority is not None,
        "receipt_id": receipt.receipt_id, "window_id": wid, "original_receipt": original.receipt_id,
        "replacement": {c.name: getattr(replacement, c.name) for c in replacement.__table__.columns},
        "expected_canonical_key": observation_key(parent.id, source.deployment_id, values["cohort"], 1),
        "local": local, "active": active,
        "role": "append-only engineering fixture; not a successful write promotion or model run",
        "cost_usd_live": "0", "model_calls_live": 0,
    }


@pytest.mark.parametrize("state,poison", [
    ("canary", "valid"), ("shadow", "valid"),
    ("canary", "noncanonical_key"), ("shadow", "noncanonical_key"),
    ("canary", "production_namespace"), ("canary", "wrong_distribution"),
    ("shadow", "unpaired_shadow"), ("canary", "start_key"), ("canary", "triggered_pass"),
])
async def test_fresh_complete_get_requires_valid_leaf_identity(health_repo, state, poison):
    proof = await altered_leaf(health_repo, state, poison)
    directory = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
    directory.mkdir(exist_ok=True)
    with (directory / f"{state}-{poison}.json").open("x") as out:
        json.dump(proof, out, indent=2, default=str)
        out.write("\n")
    valid = poison == "valid"
    assert proof["authority_accepts"] == valid, "counterexample/control must reach authority validation"
    gate = "shadow_health" if state == "shadow" else "canary_health"
    local = sources(proof["local"])
    assert (gate in local) == valid, "invalid frozen leaf must not receive a trusted local passed source"
    if state == "canary":
        assert "shadow_health" in local, "independent legal Shadow history must remain"
        assert len(sources(proof["active"])) == (2 if valid else 0), "invalid exact Canary must break Active chain"
