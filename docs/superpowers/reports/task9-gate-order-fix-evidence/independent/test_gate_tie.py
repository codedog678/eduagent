from datetime import timedelta
from decimal import Decimal

import pytest

from tests.distributed.conftest import raw_repo, repo
from tests.distributed.test_promotion_ops_api import policy_ops, NOW, PATHS
from core.distributed.promotion_models import PolicyArtifactRecord, PolicyGateReceiptRecord
from core.distributed.promotion_repository import PromotionRepository

pytestmark = pytest.mark.distributed_integration


async def test_newer_failed_receipt_with_same_issued_at_invalidates_older_pass_in_ops(policy_ops):
    receipts = [
        ("ffffffff-ffff-ffff-ffff-ffffffffffff", "passed", NOW, "7" * 64),
        ("00000000-0000-0000-0000-000000000001", "failed", NOW + timedelta(seconds=60), "8" * 64),
    ]
    async with policy_ops.repo.session_factory() as session, session.begin():
        for receipt_id, status, created_at, evidence_hash in receipts:
            session.add(PolicyGateReceiptRecord(
                receipt_id=receipt_id, policy_hash="b" * 64, gate_type="formal_holdout",
                status=status, evidence_hash=evidence_hash, protocol_hash="b" * 64,
                runtime_hash="b" * 64, source_revision="test", model_identity="test-fixture",
                data_role="holdout_validated", sample_count=20, cost=Decimal(".1"),
                details={"evidence_role": "test_fixture", "release_eligible": False},
                issuer="test-fixture", issued_at=NOW, created_at=created_at,
            ))
    async with policy_ops.repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, "b" * 64)
        missing, accepted = await PromotionRepository._bound_gate_receipts(
            session, artifact=artifact, required={"formal_holdout"}, health_bindings={},
        )
    response = await policy_ops.client.get(
        f"{PATHS[0]}/{policy_ops.deployments[1].deployment_id}",
    )
    assert response.status_code == 200
    shown = next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")
    print("gate_verifier_missing=", missing, "gate_verifier_accepted=", list(accepted))
    print("ops_display=", shown)
    assert missing == ["formal_holdout"] and accepted == {}
    assert shown["status"] == "failed", (
        "Ops displays older passed receipt while authoritative gate rejects the newer failed receipt"
    )
