from pathlib import Path
from datetime import UTC, datetime
from uuid import uuid4
import json
import os

import pytest
from sqlalchemy import select

from core.distributed.ops_queries import OpsQueries
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_models import PolicyArtifactRecord, PolicyGateReceiptRecord
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_ops_health_binding import append_receipt
from tests.distributed.test_policy_health import health_repo, fill_window
from tests.distributed.test_policy_health_corrections import real_active_fixture

OWN = Path(__file__).parent
OWN = OWN / os.environ["EVIDENCE_RUN"]
OWN.mkdir(exist_ok=True)
pytestmark = pytest.mark.distributed_integration


async def genuine_malformed_latest(fixture):
    prepared, _, _ = await real_active_fixture(
        fixture, command_prefix="independent-genuine-" + uuid4().hex)
    repo, promotion, active = prepared
    async with repo.session_factory() as session:
        approval = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.gate_type == "promotion_approval",
            PolicyGateReceiptRecord.details["command_id"].as_string() == active.command_id))
        assert approval is not None
    newer = await append_receipt(repo, approval, details=[], created_at=datetime.now(UTC))
    return repo, active, approval.receipt_id, newer


async def test_genuine_command_chain_malformed_latest_does_not_restore_green(health_repo):
    repo, active, original, newer = await genuine_malformed_latest(health_repo)
    body = (await OpsQueries(repo.session_factory).get_policy_deployment(
        str(active.deployment_id))).model_dump(mode="json")
    (OWN / "corroboration-final-genuine.json").write_text(json.dumps({
        "role": "synthetic real command/evaluator chain; no model requests",
        "original_approval": original, "newer_malformed_approval": newer,
        "body": body}, indent=2) + "\n")
    assert not [r for r in body["gate_receipts"] if r["health_source"]]


@pytest.mark.parametrize("field", ["sample_count", "cost"])
async def test_frozen_metadata_disagreement_with_authority_is_unavailable(health_repo, field):
    repo, promotion, deployment = health_repo
    await fill_window(health_repo)
    window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
    async with repo.session_factory() as session:
        original = await session.scalar(select(PolicyGateReceiptRecord))
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        positive = await PromotionRepository._validated_health_window(
            session, artifact=artifact, deployment=deployment,
            gate_type="canary_health", receipt=original)
        assert positive is not None
    latest_id = await append_receipt(repo, original, **{field: 0})
    async with repo.session_factory() as session:
        latest = await session.get(PolicyGateReceiptRecord, latest_id)
        validated = await PromotionRepository._validated_health_window(
            session, artifact=artifact, deployment=deployment,
            gate_type="canary_health", receipt=latest)
        assert validated is None
    body = (await OpsQueries(repo.session_factory).get_policy_deployment(
        deployment.deployment_id)).model_dump(mode="json")
    (OWN / ("corroboration-final-" + field + ".json")).write_text(json.dumps({
        "role": "synthetic engineering; original evidence authentic evaluator",
        "original_sample_count": original.sample_count,
        "original_cost": str(original.cost), "original_id": original.receipt_id,
        "latest_id": latest_id, "window": {
            "window_id": window.window_id, "decision": window.decision,
            "observation_keys": window.observation_keys,
            "candidate_stats": window.candidate_stats, "stable_stats": window.stable_stats},
        "authority_before": "valid", "authority_after": "unavailable",
        "body": body}, indent=2) + "\n")
    assert not [r for r in body["gate_receipts"] if r["health_source"]]
