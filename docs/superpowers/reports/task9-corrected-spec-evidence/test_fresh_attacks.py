"""Fresh SPEC attacks; all data synthetic, non-release-eligible."""
import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from tests.distributed.conftest import raw_repo, repo
from tests.distributed.test_promotion_ops_api import policy_ops, NOW, PATHS
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyGateReceiptRecord, PolicyHealthWindowRecord,
)
from core.distributed.promotion_repository import PromotionRepository

pytestmark = pytest.mark.distributed_integration
LOW = "00000000-0000-0000-0000-000000000040"
HIGH = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"


def receipt(identity, status, created, evidence, **changes):
    return PolicyGateReceiptRecord(**{
        "receipt_id": identity, "policy_hash": "b" * 64,
        "gate_type": "formal_holdout", "status": status,
        "evidence_hash": evidence, "protocol_hash": "b" * 64,
        "runtime_hash": "b" * 64, "source_revision": "test",
        "model_identity": "synthetic-independent-spec", "data_role": "holdout_validated",
        "sample_count": 29, "cost": Decimal(".13"),
        "details": {"evidence_role": "test_fixture", "release_eligible": False},
        "issuer": "synthetic-independent-spec", "issued_at": NOW, "created_at": created,
        **changes,
    })


async def projection(f):
    response = await f.client.get(f"{PATHS[0]}/{f.deployments[1].deployment_id}")
    assert response.status_code == 200
    return next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")


async def authority(f):
    async with f.repo.session_factory() as s:
        artifact = await s.get(PolicyArtifactRecord, "b" * 64)
        return await PromotionRepository._bound_gate_receipts(
            s, artifact=artifact, required={"formal_holdout"}, health_bindings={})


@pytest.mark.parametrize("status", ["failed", "unknown"])
@pytest.mark.parametrize("tie", ["different_created_reverse_uuid", "same_created_uuid_third_key"])
async def test_fresh_f1_and_later_recovery(policy_ops, status, tie):
    different = tie == "different_created_reverse_uuid"
    old_id, new_id = (HIGH, LOW) if different else (LOW, HIGH)
    created = NOW + timedelta(seconds=77) if different else NOW
    async with policy_ops.repo.session_factory() as s, s.begin():
        s.add_all([receipt(old_id, "passed", NOW, "c" * 64),
                   receipt(new_id, status, created, "d" * 64)])
    missing, accepted = await authority(policy_ops)
    shown = await projection(policy_ops)
    assert missing == ["formal_holdout"] and accepted == {}
    assert (shown["status"], shown["receipt_id"]) == (status, new_id)
    restored_id = "00000000-0000-0000-0000-000000000003"
    async with policy_ops.repo.session_factory() as s, s.begin():
        s.add(receipt(restored_id, "passed", NOW + timedelta(seconds=155), "e" * 64))
    missing, accepted = await authority(policy_ops)
    shown = await projection(policy_ops)
    assert missing == [] and accepted["formal_holdout"].receipt_id == restored_id
    assert (shown["status"], shown["receipt_id"]) == ("passed", restored_id)
    print("FRESH_F1", tie, status, "rejected_then_restored", restored_id)


@pytest.mark.parametrize("dimension", ["policy_hash", "protocol_hash", "runtime_hash", "source_revision"])
async def test_fresh_exact_four_binding(policy_ops, dimension):
    changes = {dimension: "a" * 64 if dimension != "source_revision" else "synthetic-wrong-revision"}
    async with policy_ops.repo.session_factory() as s, s.begin():
        s.add_all([receipt(LOW, "unknown", NOW, "c" * 64),
                   receipt(HIGH, "passed", NOW + timedelta(seconds=90), "d" * 64, **changes)])
    missing, accepted = await authority(policy_ops)
    shown = await projection(policy_ops)
    assert missing == ["formal_holdout"] and accepted == {}
    assert (shown["status"], shown["receipt_id"]) == ("unknown", LOW)


async def test_fresh_future_pass_not_current_evidence(policy_ops):
    async with policy_ops.repo.session_factory() as s, s.begin():
        s.add_all([receipt(LOW, "failed", NOW, "c" * 64),
                   receipt(HIGH, "passed", NOW + timedelta(seconds=90), "d" * 64,
                           issued_at=datetime.now(UTC) + timedelta(days=30))])
    shown = await projection(policy_ops)
    assert (shown["status"], shown["receipt_id"]) == ("failed", LOW)
    # The private authority helper is not the complete time-validating verifier.


@pytest.mark.parametrize("value", [
    "cedar parcel 8642", "<script>synthetic</script>", "NaN", "Infinity", "-Infinity",
    True, {"value": "cedar parcel 8642"}, ["1"], "0x10", " 0.3 ", "1; SELECT 1",
])
async def test_fresh_numeric_and_closed_threshold_labels(policy_ops, value):
    async with policy_ops.repo.session_factory() as s, s.begin():
        await s.execute(update(PolicyHealthWindowRecord).values(
            candidate_stats={"mean_cost": value, "run_count": False, "unknown_rate": "1.1"},
            stable_stats={"run_count": 25, "mean_cost": "1.30e-2", "latency_increase_rate": "-.25"},
            triggered_thresholds=["cedar parcel 8642"] * 25))
    response = await policy_ops.client.get(PATHS[1])
    assert response.status_code == 200
    shown = response.json()["items"][0]
    assert shown["candidate_stats"]["mean_cost"] is None
    assert shown["candidate_stats"]["run_count"] is None
    assert shown["candidate_stats"]["unknown_rate"] is None
    assert shown["triggered_thresholds"] == ["redacted"] * 16
    assert Decimal(shown["stable_stats"]["mean_cost"]) == Decimal(".013")
    assert Decimal(shown["stable_stats"]["latency_increase_rate"]) == Decimal("-.25")
    assert shown["stable_stats"]["run_count"] == 25
    assert "cedar parcel" not in response.text


@pytest.mark.parametrize("path", PATHS)
async def test_fresh_cursor_type_confusion_and_duplicate_filters(policy_ops, path):
    wrong_id = str(uuid4()) if path.endswith("health-windows") else "c" * 64
    encoded = base64.urlsafe_b64encode(json.dumps(
        {"created_at": NOW.isoformat(), "id": wrong_id}).encode()).decode().rstrip("=")
    for params in (
        {"cursor": encoded},
        [("environment", "rehearsal"), ("environment", "production")],
        {"environment": "cedar parcel 8642"},
        {"cedar parcel 8642": "1"},
        {"limit": "1.0"},
    ):
        response = await policy_ops.client.get(path, params=params)
        assert response.status_code == 422
        assert "cedar parcel" not in response.text and encoded not in response.text
