import copy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update

from tests.distributed.conftest import raw_repo, repo
from tests.distributed.test_promotion_ops_api import policy_ops, NOW, PATHS
from core.distributed.ops_queries import OpsQueries
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyGateReceiptRecord, PolicyHealthWindowRecord,
)

pytestmark = pytest.mark.distributed_integration
CANARY = 1
ARBITRARY = "violet meadow 7391 <img onerror=alert(1)> 汉字 🧪"


@pytest.mark.parametrize("dimension", ["policy_hash", "protocol_hash", "runtime_hash", "source_revision"])
async def test_receipt_binding_all_four_dimensions_and_new_failure(policy_ops, dimension):
    fixture = policy_ops
    async with fixture.repo.session_factory() as s, s.begin():
        correct = PolicyGateReceiptRecord(
            receipt_id=str(uuid4()), policy_hash="b" * 64, gate_type="formal_holdout",
            status="passed", evidence_hash="4" * 64, protocol_hash="b" * 64,
            runtime_hash="b" * 64, source_revision="test", model_identity=ARBITRARY,
            data_role="test_fixture", sample_count=27, cost=Decimal(".1"),
            details={"bland": ARBITRARY}, issuer=ARBITRARY, issued_at=NOW,
            created_at=NOW,
        )
        s.add(correct)
        mismatch = {name: getattr(correct, name) for name in (
            "policy_hash", "gate_type", "status", "evidence_hash", "protocol_hash",
            "runtime_hash", "source_revision", "model_identity", "data_role",
            "sample_count", "cost", "details", "issuer", "created_at",
        )}
        mismatch[dimension] = "a" * 64 if dimension != "source_revision" else ARBITRARY
        mismatch["evidence_hash"] = "5" * 64
        s.add(PolicyGateReceiptRecord(
            **mismatch, receipt_id=str(uuid4()), issued_at=NOW + timedelta(seconds=10),
        ))
    path = f"{PATHS[0]}/{fixture.deployments[CANARY].deployment_id}"
    response = await fixture.client.get(path)
    assert response.status_code == 200
    receipt = next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")
    assert receipt["receipt_id"] == correct.receipt_id
    assert ARBITRARY not in response.text
    async with fixture.repo.session_factory() as s, s.begin():
        s.add(PolicyGateReceiptRecord(
            **{**mismatch, dimension: getattr(correct, dimension), "status": "failed",
               "evidence_hash": "6" * 64},
            receipt_id=str(uuid4()), issued_at=NOW + timedelta(seconds=20),
        ))
    response = await fixture.client.get(path)
    receipt = next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")
    assert receipt["status"] == "failed"


async def test_arbitrary_payloads_closed_labels_and_bad_numeric_values(policy_ops):
    async with policy_ops.repo.session_factory() as s, s.begin():
        await s.execute(update(PolicyDeploymentRecord).values(actor=ARBITRARY, reason=ARBITRARY))
        await s.execute(update(PolicyAuditEventRecord).values(
            actor=ARBITRARY, reason=ARBITRARY, event_type=ARBITRARY,
            details={"from_state": ARBITRARY, "to_state": ARBITRARY, "bland": ARBITRARY},
        ))
        await s.execute(update(PolicyHealthWindowRecord).values(
            candidate_stats={"mean_cost": ARBITRARY, "run_count": False, "p95_latency": "Infinity",
                             "unknown_rate": {"bland": ARBITRARY}, "mean_cost_increase_rate": "-.5"},
            stable_stats={"mean_cost": ".125", "run_count": 23, "p95_latency": "1e-3"},
            triggered_thresholds=[ARBITRARY],
        ))
    for path in [*PATHS, f"{PATHS[0]}/{policy_ops.deployments[1].deployment_id}"]:
        response = await policy_ops.client.get(path)
        assert response.status_code == 200
        assert ARBITRARY not in response.text
        assert '"details"' not in response.text and '"components"' not in response.text
    health = (await policy_ops.client.get(PATHS[1])).json()["items"][0]
    assert health["triggered_thresholds"] == ["redacted"]
    assert health["candidate_stats"]["mean_cost"] is None
    assert health["candidate_stats"]["run_count"] is None
    assert health["candidate_stats"]["p95_latency"] is None
    assert health["candidate_stats"]["unknown_rate"] is None
    assert Decimal(health["candidate_stats"]["mean_cost_increase_rate"]) == Decimal("-.5")
    assert Decimal(health["stable_stats"]["mean_cost"]) == Decimal(".125")
    audit = (await policy_ops.client.get(PATHS[2])).json()["items"][0]
    assert audit["event_type"] == "redacted"
    assert audit["from_state"] is None and audit["to_state"] is None


async def test_large_tied_keysets_three_endpoints_and_bounded_detail(policy_ops):
    dep = policy_ops.deployments[1]
    async with policy_ops.repo.session_factory() as s, s.begin():
        for i in range(4, 110):
            s.add(PolicyDeploymentRecord(
                **{c.name: copy.deepcopy(getattr(dep, c.name)) for c in dep.__table__.columns
                   if c.name not in {"deployment_id", "version", "command_id"}},
                deployment_id=str(uuid4()), version=i, command_id=f"independent-{i}",
            ))
            win = policy_ops.windows[1]
            s.add(PolicyHealthWindowRecord(
                **{c.name: copy.deepcopy(getattr(win, c.name)) for c in win.__table__.columns
                   if c.name != "window_id"},
                window_id=f"{i:064x}",
            ))
            audit = policy_ops.audits[1]
            s.add(PolicyAuditEventRecord(
                **{c.name: copy.deepcopy(getattr(audit, c.name)) for c in audit.__table__.columns
                   if c.name not in {"event_id", "command_id"}},
                event_id=str(uuid4()), command_id=f"independent-audit-{i}",
            ))
    for path, key in zip(PATHS, ("deployment_id", "window_id", "event_id")):
        seen, cursor, pages = [], None, []
        while True:
            params = {"limit": 100, "environment": "rehearsal"}
            if cursor:
                params["cursor"] = cursor
            response = await policy_ops.client.get(path, params=params)
            assert response.status_code == 200
            body = response.json()
            pages.append(len(body["items"]))
            seen += [r[key] for r in body["items"]]
            cursor = body["next_cursor"]
            if not cursor:
                break
            assert len(pages) < 4
        assert pages == [100, 9]
        assert len(seen) == len(set(seen)) == 109
        assert seen == sorted(seen, reverse=True)
    detail = (await policy_ops.client.get(f"{PATHS[0]}/{dep.deployment_id}")).json()
    assert len(detail["audit_events"]) == 100
    assert detail["latest_health_window"]["window_id"] == f"{109:064x}"


async def test_repeatable_read_snapshot_with_concurrent_append(policy_ops):
    queries = OpsQueries(policy_ops.repo.session_factory)
    async with queries._policy_read_session() as s:
        assert await s.scalar(text("SHOW transaction_read_only")) == "on"
        assert await s.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        before = list(await s.scalars(select(PolicyAuditEventRecord.event_id)))
        async with policy_ops.repo.session_factory() as writer, writer.begin():
            writer.add(PolicyAuditEventRecord(
                event_id=str(uuid4()), environment="rehearsal",
                deployment_id=policy_ops.deployments[1].deployment_id,
                event_type="promotion_rejected", command_id="concurrent-independent",
                actor=ARBITRARY, reason=ARBITRARY, details={}, created_at=NOW,
            ))
        after = list(await s.scalars(select(PolicyAuditEventRecord.event_id)))
        assert before == after
        with pytest.raises(Exception, match="read-only"):
            await s.execute(text("INSERT INTO policy_audit_events SELECT * FROM policy_audit_events WHERE false"))
    page = await queries.list_policy_audit(limit=100)
    assert len(page.items) == len(before) + 1
