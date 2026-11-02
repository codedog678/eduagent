from uuid import uuid4

import pytest
from sqlalchemy import select

from core.distributed.promotion_models import PolicyGateReceiptRecord
from tests.distributed.test_ops_health_binding import append_receipt
from tests.distributed.test_ops_source_integrity import api_detail
from tests.distributed.test_policy_health import health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture
from test_independent_integrity import record, transition_fixture

pytestmark = pytest.mark.distributed_integration


@pytest.mark.parametrize("target", ["canary", "active"])
@pytest.mark.parametrize("field,value", [
    ("issuer", "foreign-issuer"), ("model_identity", "foreign-model"),
    ("data_role", "simulation"), ("policy_hash", "f" * 64),
    ("runtime_hash", "e" * 64), ("source_revision", "foreign-source"),
])
async def test_referenced_health_metadata_is_a_real_chain_requirement(health_repo, target, field, value):
    if field == "policy_hash":
        value = health_repo[2].stable_policy_hash
    repo, deployment, proof = await transition_fixture(health_repo, target, health_poison={field: value})
    body = await api_detail(repo, deployment)
    shown = [r for r in body["gate_receipts"] if r["health_source"]]
    record("metadata-" + target + "-" + field, {**proof, "body": body, "poison": {field: value}})
    if target == "canary" and field in {"policy_hash", "runtime_hash", "source_revision"}:
        assert len(shown) == 1
    else:
        assert not shown, "a broken exact receipt must not authenticate any Active consumed chain"


@pytest.mark.parametrize("field,value", [
    ("issuer", "foreign-issuer"), ("model_identity", "foreign-model"),
    ("data_role", "simulation"), ("status", "failed"), ("status", "unknown"),
])
async def test_approval_metadata_masks_earlier_genuine_approval(health_repo, field, value):
    fixture, _, _ = await real_active_fixture(health_repo, command_prefix="fresh-meta-" + uuid4().hex)
    repo, _, deployment = fixture
    before = await api_detail(repo, deployment)
    assert len([r for r in before["gate_receipts"] if r["health_source"]]) == 2
    async with repo.session_factory() as session:
        approval = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
        ))
    newer = await append_receipt(repo, approval, **{field: value})
    body = await api_detail(repo, deployment)
    record("approval-meta-" + field + "-" + value, {"before": before, "body": body, "newer": newer})
    assert not [r for r in body["gate_receipts"] if r["health_source"]]
