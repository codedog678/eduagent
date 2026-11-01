import base64
from datetime import UTC, datetime
import json
from pathlib import Path
import os
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from core.distributed.ops_queries import OpsQueries, _health_stats, encode_cursor
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_models import PolicyArtifactRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_policy_health import candidate_head, fill_window
from tests.distributed.test_promotion_ops_api import PATHS

OWN = Path(os.environ["REVIEW_OWN"])


async def health_pair(health_repo, current_healthy=False):
    repo, promotion, previous = health_repo
    await fill_window(health_repo)
    first_window = await PolicyHealthEvaluator(promotion).evaluate(previous.deployment_id)
    assert first_window.decision == "pass"
    current = await candidate_head(repo, state="canary", traffic=5000, version=3)
    if current_healthy:
        await fill_window((repo, promotion, current))
    current_window = await PolicyHealthEvaluator(promotion).evaluate(current.deployment_id)
    assert current_window.decision == ("pass" if current_healthy else "hold")
    async with repo.session_factory() as session:
        receipts = list(await session.scalars(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.policy_hash == previous.candidate_policy_hash,
            PolicyGateReceiptRecord.gate_type == "canary_health",
        )))
    return previous, current, first_window, current_window, receipts


async def test_current_health_gate_must_not_borrow_previous_deployment_pass(health_repo):
    repo, promotion, _ = health_repo
    old, current, old_window, new_window, receipts = await health_pair(health_repo)
    async with repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, current.candidate_policy_hash)
        missing, accepted = await PromotionRepository._bound_gate_receipts(
            session, artifact=artifact, required={"canary_health"},
            health_bindings={"canary_health": current},
        )
    assert missing == ["canary_health"] and not accepted
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(current.deployment_id)
    assert detail.is_current and detail.latest_health_window.decision == "hold"
    shown = [r for r in detail.gate_receipts if r.gate_type == "canary_health"]
    proof = {
        "role": "synthetic engineering fixture; no model or release qualification",
        "old_deployment": old.deployment_id, "current_deployment": current.deployment_id,
        "old_window": old_window.window_id, "current_window": new_window.window_id,
        "authority_missing": missing, "detail": detail.model_dump(mode="json"),
        "receipt_actual_bindings": [{"receipt_id": r.receipt_id, "details": r.details} for r in receipts],
    }
    (OWN / "health-cross-current.json").write_text(json.dumps(proof, indent=2) + "\n")
    assert not shown, "current hold deployment displays another deployment's green canary_health receipt"


async def test_historical_health_gate_must_not_be_replaced_by_new_deployment(health_repo):
    repo, _, _ = health_repo
    old, current, _, _, receipts = await health_pair(health_repo, current_healthy=True)
    original = next(r for r in receipts if r.details["deployment_id"] == old.deployment_id)
    newer = next(r for r in receipts if r.details["deployment_id"] == current.deployment_id)
    detail = await OpsQueries(repo.session_factory).get_policy_deployment(old.deployment_id)
    shown = next(r for r in detail.gate_receipts if r.gate_type == "canary_health")
    assert not detail.is_current
    (OWN / "health-cross-history.json").write_text(json.dumps({
        "old_deployment": old.deployment_id, "current_deployment": current.deployment_id,
        "original_receipt": original.receipt_id, "newer_receipt": newer.receipt_id,
        "shown_receipt": str(shown.receipt_id), "detail": detail.model_dump(mode="json"),
    }, indent=2) + "\n")
    assert str(shown.receipt_id) == original.receipt_id, "old detail was replaced by receipt from a different deployment"


@pytest.mark.parametrize("path", PATHS)
async def test_cursor_typed_extremes_and_noncanonical_base64(policy_ops, path):
    now = datetime(2026, 11, 1, tzinfo=UTC)
    row_id = "abcdef" * 10 + "abcd" if "health-windows" in path else str(uuid4())
    valid = encode_cursor(now, row_id)
    for value in (
        valid + "=", valid + "\n",
        encode_cursor(now, str(uuid4()) if "health-windows" in path else "9" * 64),
        base64.urlsafe_b64encode(json.dumps({"id": row_id, "created_at": "infinity"}).encode()).decode().rstrip("="),
        encode_cursor(now, row_id.upper()),
    ):
        response = await policy_ops.client.get(path, params={"cursor": value})
        assert response.status_code == 422
        assert value not in response.text


@pytest.mark.parametrize("path", PATHS)
async def test_all_duplicate_empty_and_overflow_queries_before_io(policy_ops, path):
    for params in (
        [("limit", "1"), ("limit", "1")],
        [("environment", "production"), ("environment", "rehearsal")],
        {"limit": "9" * 512}, {"limit": "+1"}, {"limit": " 1"},
        {"limit": "1e2"}, {"environment": ""}, {"cursor": "\x00"},
        {"private_field": "never-echo-this"}, {"limit": "１００"},
    ):
        response = await policy_ops.client.get(path, params=params)
        assert response.status_code == 422
        assert "never-echo-this" not in response.text


@pytest.mark.parametrize("value", [
    True, False, {}, [], "NaN", "Infinity", "-Infinity", "-1", "1.2.3",
    "<script>private-anything</script>", "1; SELECT 1", "\u202e123",
])
def test_numeric_poison_is_null_not_echoed(value):
    body = _health_stats({
        "mean_cost": value, "run_count": value, "p95_latency": value, "unknown_rate": value,
        "private_anything": "not-allowed",
    }).model_dump(mode="json")
    assert all(body[name] is None for name in ("mean_cost", "run_count", "p95_latency", "unknown_rate"))
    assert "private_anything" not in body


def test_finite_numbers_and_missing_fields_are_distinct():
    body = _health_stats({"run_count": 0, "mean_cost": ".0000001", "unknown_rate": "0"}).model_dump(mode="json")
    assert body["run_count"] == 0 and body["unknown_rate"] == "0"
    assert body["mean_cost"] == "1E-7" and body["p95_latency"] is None
