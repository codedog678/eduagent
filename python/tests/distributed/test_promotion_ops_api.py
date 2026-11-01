"""Real PostgreSQL evidence for Task9; synthetic, non-release fixtures only."""

import base64
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import event, select, text, update

from api.distributed_main import create_app
from core.distributed import ops_contracts
from core.distributed.models import DistributedRun
from core.distributed.ops_queries import OpsQueries, encode_cursor
from core.distributed.promotion_contracts import PolicyThresholds
from core.distributed.promotion_models import (
    PolicyArtifactRecord,
    PolicyAuditEventRecord,
    PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord,
    PolicyHealthWindowRecord,
    PolicyShadowExecutionRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.helpers import spec
from tests.distributed.test_policy_health import (
    admitted, candidate_head, fill_window, health_repo,
)

pytestmark = pytest.mark.distributed_integration
NOW = datetime(2026, 10, 30, tzinfo=UTC)
SENSITIVE = "Bearer abc.def.private nonce learner request privateprompt output artifact"
PATHS = [
    "/ops/policies/deployments",
    "/ops/policies/health-windows",
    "/ops/policies/audit",
]


@pytest_asyncio.fixture
async def policy_ops(repo):
    thresholds = PolicyThresholds()
    deployments, windows, audits = [], [], []
    async with repo.session_factory() as session, session.begin():
        for index, state in enumerate(("shadow", "canary", "rolled_back"), 1):
            deployment = PolicyDeploymentRecord(
                deployment_id=str(uuid4()), environment="rehearsal",
                version=index, state=state, candidate_policy_hash="b" * 64,
                stable_policy_hash="a" * 64, previous_stable_deployment_id=None,
                traffic_basis_points=5000 if state == "canary" else 0,
                assignment_salt_id=SENSITIVE, thresholds=thresholds.model_dump(mode="json"),
                thresholds_hash=thresholds.digest, required_receipts=["shadow_health"],
                command_id=f"fixture-{index}", actor=SENSITIVE, reason=SENSITIVE,
                created_at=NOW,
            )
            session.add(deployment)
            await session.flush()
            deployments.append(deployment)
            window = PolicyHealthWindowRecord(
                window_id=f"{index:064x}", deployment_id=deployment.deployment_id,
                deployment_version=index, metric_contract_version=1,
                thresholds_hash=thresholds.digest,
                observation_keys={"innocent": SENSITIVE},
                observation_start_key="a" * 64, observation_end_key="b" * 64,
                candidate_stats={
                    "run_count": 20, "mean_cost": ".01", "p95_latency": "1.25",
                    "commit_failure_rate": ".05", "unknown_rate": None,
                    "natural_failure_count": 0, "fault_injected_count": 1,
                    "innocent": SENSITIVE,
                },
                stable_stats={"run_count": 20, "mean_cost": None, "innocent": SENSITIVE},
                decision="fail" if index == 3 else "hold",
                triggered_thresholds=["commit_failure_rate", SENSITIVE],
                evaluated_at=NOW, created_at=NOW,
            )
            session.add(window)
            windows.append(window)
            audit = PolicyAuditEventRecord(
                event_id=str(uuid4()), environment="rehearsal",
                deployment_id=deployment.deployment_id, event_type="health_rollback",
                command_id=f"audit-{index}", actor=SENSITIVE, reason=SENSITIVE,
                details={"innocent": SENSITIVE, "window_id": window.window_id},
                created_at=NOW,
            )
            session.add(audit)
            audits.append(audit)
        session.add(PolicyEnvironmentHeadRecord(
            environment="rehearsal", current_deployment_id=deployments[-1].deployment_id,
            current_version=3, updated_at=NOW,
        ))
        for index, status in enumerate(("passed", "unknown"), 1):
            session.add(PolicyGateReceiptRecord(
                receipt_id=str(uuid4()), policy_hash="b" * 64, gate_type="shadow_health",
                status=status, evidence_hash=f"{index:064x}", protocol_hash="b" * 64,
                runtime_hash="b" * 64, source_revision="test", model_identity=SENSITIVE,
                data_role="private-role", sample_count=20, cost=Decimal(".02"),
                details={"innocent": SENSITIVE}, issued_at=NOW + timedelta(seconds=index),
                issuer=SENSITIVE, created_at=NOW,
            ))
    app = create_app()
    app.state.distributed = SimpleNamespace(
        repository=repo, ops_queries=OpsQueries(repo.session_factory),
        settings=SimpleNamespace(ops_api_token=SecretStr("")),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(
            client=client, app=app, repo=repo, deployments=deployments,
            windows=windows, audits=audits,
        )


@pytest.mark.parametrize("path,key", zip(PATHS, ("deployment_id", "window_id", "event_id")))
async def test_policy_keyset_ties_are_complete_unique_and_bounded(policy_ops, path, key):
    cursor, seen = None, []
    while True:
        params = {"limit": 1, "environment": "rehearsal"}
        if cursor:
            params["cursor"] = cursor
        response = await policy_ops.client.get(path, params=params)
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        seen.append(body["items"][0][key])
        cursor = body["next_cursor"]
        if not cursor:
            break
        assert len(seen) < 4
    assert len(seen) == len(set(seen)) == 3
    assert seen == sorted(seen, reverse=True)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"limit": "private-secret"},
    {"environment": "private-secret"}, {"unused-private-secret": SENSITIVE},
    {"cursor": ""}, {"cursor": "private-secret"}, {"cursor": "a" * 513},
    {"limit": 1, "limit_again": 2},
])
async def test_policy_rejections_do_not_echo_input(policy_ops, path, params):
    response = await policy_ops.client.get(path, params=params)
    assert response.status_code == 422
    assert "private-secret" not in response.text
    assert SENSITIVE not in response.text


@pytest.mark.parametrize("path", PATHS)
async def test_policy_cursor_requires_exact_typed_identity(policy_ops, path):
    for body in (
        {"created_at": NOW.isoformat(), "id": SENSITIVE},
        {"created_at": NOW.replace(tzinfo=None).isoformat(), "id": str(uuid4())},
        {"created_at": NOW.isoformat(), "id": str(uuid4()), "innocent": SENSITIVE},
        [],
    ):
        cursor = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
        response = await policy_ops.client.get(path, params={"cursor": cursor})
        assert response.status_code == 422
        assert SENSITIVE not in response.text


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("timestamp", [
    "0001-01-01T00:00:00+23:59",
    "9999-12-31T23:59:59-23:59",
])
async def test_policy_cursor_timezone_overflow_is_safe_422(policy_ops, path, timestamp):
    row_id = "1" * 64 if path.endswith("health-windows") else "11111111-1111-1111-1111-111111111111"
    cursor = base64.urlsafe_b64encode(json.dumps({
        "created_at": timestamp, "id": row_id,
    }).encode()).decode().rstrip("=")
    response = await policy_ops.client.get(path, params={"cursor": cursor})
    assert response.status_code == 422
    assert timestamp not in response.text
    assert cursor not in response.text


async def test_policy_filters_and_ids_are_meaningful_and_strict(policy_ops):
    client = policy_ops.client
    response = await client.get(PATHS[0], params={"state": "canary"})
    assert response.status_code == 200
    assert [row["state"] for row in response.json()["items"]] == ["canary"]
    deployment_id = policy_ops.deployments[1].deployment_id
    for path in PATHS[1:]:
        response = await client.get(path, params={"deployment_id": deployment_id})
        assert response.status_code == 200
        assert {row["deployment_id"] for row in response.json()["items"]} == {deployment_id}
    for path, params in [
        (PATHS[0], {"state": SENSITIVE}),
        (PATHS[1], {"decision": SENSITIVE}),
        (PATHS[2], {"event_type": SENSITIVE}),
        (PATHS[1], {"deployment_id": SENSITIVE}),
        (PATHS[0], {"state": ""}),
    ]:
        response = await client.get(path, params=params)
        assert response.status_code == 422
        assert SENSITIVE not in response.text
    for value, status in (("invalid-private-secret", 422), (str(uuid4()), 404)):
        response = await client.get(f"{PATHS[0]}/{value}")
        assert response.status_code == status
        assert "private-secret" not in response.text
    response = await client.get(PATHS[0], params=[("limit", "1"), ("limit", "2")])
    assert response.status_code == 422


async def test_strict_redacted_policy_projections_and_latest_gate(policy_ops):
    deployment = policy_ops.deployments[1]
    response = await policy_ops.client.get(f"{PATHS[0]}/{deployment.deployment_id}")
    assert response.status_code == 200
    body = response.json()
    detail_model = getattr(ops_contracts, "OpsPolicyDeploymentDetail")
    detail_model.model_validate(body)
    assert body["stable_policy_hash"] == "a" * 64
    assert body["candidate_policy_hash"] == "b" * 64
    assert body["is_current"] is False
    assert body["cohort_counts"] == {"stable": 0, "candidate": 0, "shadow": 0}
    assert body["gate_receipts"][0]["status"] == "unknown"
    assert body["latest_health_window"]["candidate_stats"]["mean_cost"] == "0.01"
    assert body["latest_health_window"]["stable_stats"]["mean_cost"] is None
    assert body["latest_health_window"]["stable_stats"]["p95_latency"] is None
    assert body["actor"] == "redacted"
    assert body["reason"] == "redacted"
    with pytest.raises(ValidationError):
        detail_model.model_validate({**body, "details": {"innocent": SENSITIVE}})
    for path in [*PATHS, f"{PATHS[0]}/{deployment.deployment_id}"]:
        result = await policy_ops.client.get(path)
        assert result.status_code == 200
        serialized = result.text
        for value in ("abc.def.private", "nonce", "learner", "request", "privateprompt", "artifact"):
            assert value not in serialized
        assert '"details"' not in serialized
        assert '"components"' not in serialized
    page = (await policy_ops.client.get(PATHS[0])).json()
    assert all(len(item["stable_policy_hash"]) == 12 for item in page["items"])


def _external_gate_receipt(receipt_id, status, created_at, evidence_hash, **changes):
    return PolicyGateReceiptRecord(**{
        "receipt_id": receipt_id, "policy_hash": "b" * 64,
        "gate_type": "formal_holdout", "status": status,
        "evidence_hash": evidence_hash, "protocol_hash": "b" * 64,
        "runtime_hash": "b" * 64, "source_revision": "test",
        "model_identity": "test-fixture", "data_role": "holdout_validated",
        "sample_count": 20, "cost": Decimal(".1"),
        "details": {"evidence_role": "test_fixture", "release_eligible": False},
        "issuer": "test-fixture", "issued_at": NOW, "created_at": created_at,
        **changes,
    })


@pytest.mark.parametrize("status", ["failed", "unknown"])
@pytest.mark.parametrize("tie_key", ["created_at", "receipt_id"])
async def test_gate_tie_order_matches_publish_authority(policy_ops, status, tie_key):
    high_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    low_id = "00000000-0000-0000-0000-000000000001"
    old_id, new_id = (high_id, low_id) if tie_key == "created_at" else (low_id, high_id)
    new_created = NOW + timedelta(minutes=1) if tie_key == "created_at" else NOW
    async with policy_ops.repo.session_factory() as session, session.begin():
        session.add_all([
            _external_gate_receipt(old_id, "passed", NOW, "7" * 64),
            _external_gate_receipt(new_id, status, new_created, "8" * 64),
        ])
    async with policy_ops.repo.session_factory() as session:
        artifact = await session.get(PolicyArtifactRecord, "b" * 64)
        missing, accepted = await PromotionRepository._bound_gate_receipts(
            session, artifact=artifact, required={"formal_holdout"}, health_bindings={},
        )
    assert missing == ["formal_holdout"] and accepted == {}
    path = f"{PATHS[0]}/{policy_ops.deployments[1].deployment_id}"
    response = await policy_ops.client.get(path)
    assert response.status_code == 200
    shown = next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")
    print("synthetic_gate_tie", tie_key, status, "authority_missing", missing, "ops", shown)
    assert shown["status"] == status
    assert shown["receipt_id"] == new_id
    # A later append may restore pass even when its UUID sorts below the old pass.
    restored_id = "00000000-0000-0000-0000-000000000002"
    async with policy_ops.repo.session_factory() as session, session.begin():
        session.add(_external_gate_receipt(
            restored_id, "passed", NOW + timedelta(minutes=2), "9" * 64,
        ))
    async with policy_ops.repo.session_factory() as session:
        missing, accepted = await PromotionRepository._bound_gate_receipts(
            session, artifact=artifact, required={"formal_holdout"}, health_bindings={},
        )
    assert missing == [] and accepted["formal_holdout"].receipt_id == restored_id
    restored = next(r for r in (await policy_ops.client.get(path)).json()["gate_receipts"]
                    if r["gate_type"] == "formal_holdout")
    assert restored["status"] == "passed" and restored["receipt_id"] == restored_id


@pytest.mark.parametrize("invalid_binding", [
    "policy_hash", "protocol_hash", "runtime_hash", "source_revision", "future_issued_at",
])
async def test_gate_order_excludes_unbound_or_future_pass(policy_ops, invalid_binding):
    changes = {"issued_at": datetime.now(UTC) + timedelta(days=1)} if invalid_binding == "future_issued_at" else {
        invalid_binding: "wrong-source" if invalid_binding == "source_revision" else "a" * 64,
    }
    valid_id = "00000000-0000-0000-0000-000000000001"
    async with policy_ops.repo.session_factory() as session, session.begin():
        session.add_all([
            _external_gate_receipt(valid_id, "failed", NOW, "7" * 64),
            _external_gate_receipt(
                "ffffffff-ffff-ffff-ffff-ffffffffffff", "passed",
                NOW + timedelta(minutes=1), "8" * 64, **changes,
            ),
        ])
    # The private authority helper selects bindings; Ops independently excludes future issuance.
    if invalid_binding != "future_issued_at":
        async with policy_ops.repo.session_factory() as session:
            artifact = await session.get(PolicyArtifactRecord, "b" * 64)
            missing, accepted = await PromotionRepository._bound_gate_receipts(
                session, artifact=artifact, required={"formal_holdout"}, health_bindings={},
            )
        assert missing == ["formal_holdout"] and accepted == {}
    response = await policy_ops.client.get(f"{PATHS[0]}/{policy_ops.deployments[1].deployment_id}")
    assert response.status_code == 200
    shown = next(r for r in response.json()["gate_receipts"] if r["gate_type"] == "formal_holdout")
    assert shown["status"] == "failed" and shown["receipt_id"] == valid_id


@pytest.mark.parametrize("path", PATHS + ["/ops/policies/deployments/11111111-1111-1111-1111-111111111111"])
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_policy_paths_never_accept_mutations(policy_ops, path, method):
    response = await policy_ops.client.request(method, path, json={"state": "active"})
    assert response.status_code == 405


@pytest.mark.parametrize("path", PATHS + ["/ops/policies/deployments/11111111-1111-1111-1111-111111111111"])
async def test_policy_auth_reuses_ops_bearer_and_loopback(policy_ops, path):
    async with AsyncClient(
        transport=ASGITransport(app=policy_ops.app, client=("203.0.113.10", 1)),
        base_url="http://test",
    ) as client:
        assert (await client.get(path)).status_code == 403
        policy_ops.app.state.distributed.settings.ops_api_token = SecretStr("ops-fixture")
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers={"Authorization": "Bearer wrong"})).status_code == 401
        assert (await client.get(path, headers={"Authorization": "Bearer ops-fixture"})).status_code in {200, 404}


async def test_policy_detail_queries_are_rejected_without_echo_and_limits_100_work(policy_ops):
    path = f"{PATHS[0]}/{policy_ops.deployments[0].deployment_id}"
    for params in ({"cursor": SENSITIVE}, {"limit": 1}, {"innocent": SENSITIVE}):
        response = await policy_ops.client.get(path, params=params)
        assert response.status_code == 422 and SENSITIVE not in response.text
    for path in PATHS:
        response = await policy_ops.client.get(path, params={"limit": 100, "environment": "rehearsal"})
        assert response.status_code == 200 and len(response.json()["items"]) == 3
    for path, params, expected in (
        (PATHS[1], {"decision": "fail"}, 1),
        (PATHS[2], {"event_type": "qualification_registered"}, 0),
        (PATHS[2], {"deployment_id": str(uuid4())}, 0),
    ):
        response = await policy_ops.client.get(path, params=params)
        assert response.status_code == 200 and len(response.json()["items"]) == expected


async def test_policy_queries_use_sql_readonly_and_never_commands(policy_ops, monkeypatch):
    from core.distributed.promotion_service import PromotionCommandService, PromotionService

    def forbidden(*args, **kwargs):
        raise AssertionError("Ops must never call promotion commands")

    for service, names in (
        (PromotionCommandService, ("transition", "register_campaign", "show_head", "show_snapshot")),
        (PromotionService, ("register_campaign",)),
    ):
        for name in names:
            assert hasattr(service, name)
            monkeypatch.setattr(service, name, forbidden)
    engine = policy_ops.repo.session_factory.kw["bind"]
    statements, readonly = [], []

    def inspect_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if statement.lstrip().upper().startswith("SELECT"):
            cursor.execute("SHOW transaction_read_only")
            readonly.append(cursor.fetchone()[0])

    event.listen(engine.sync_engine, "before_cursor_execute", inspect_sql)
    try:
        for path in [*PATHS, f"{PATHS[0]}/{policy_ops.deployments[1].deployment_id}"]:
            assert (await policy_ops.client.get(path)).status_code == 200
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", inspect_sql)
    assert readonly and set(readonly) == {"on"}
    assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "MERGE"))
                   for sql in statements)
    queries = policy_ops.app.state.distributed.ops_queries
    async with queries._policy_read_session() as session:
        with pytest.raises(Exception, match="read-only"):
            await session.execute(text("DELETE FROM policy_environment_heads WHERE false"))


async def test_run_and_trace_identity_is_stored_and_historical_null_stays_null(policy_ops):
    repo = policy_ops.repo
    run, _ = await repo.accept_with_replay(spec("task9-pinned"))
    old = (run.deployment_id, run.effective_policy_hash, run.policy_cohort, "production")
    for version in (99, 100):
        async with repo.session_factory() as session, session.begin():
            head = await session.get(PolicyEnvironmentHeadRecord, "production")
            head.current_deployment_id = policy_ops.deployments[-1].deployment_id
            head.current_version = version
        for suffix in ("", "/trace"):
            body = (await policy_ops.client.get(f"/ops/runs/{run.id}{suffix}")).json()
            assert tuple(body[name] for name in (
                "deployment_id", "effective_policy_hash", "policy_cohort", "namespace_class",
            )) == old
            assert "state_namespace" not in body
        summary = (await policy_ops.client.get("/ops/runs")).json()["items"][0]
        assert summary["effective_policy_hash"] == old[1]
    async with repo.session_factory() as session, session.begin():
        await session.execute(update(DistributedRun).where(DistributedRun.id == run.id).values(
            deployment_id=None, effective_policy_hash=None, policy_cohort=None,
            state_namespace=None,
        ))
    for suffix in ("", "/trace"):
        body = (await policy_ops.client.get(f"/ops/runs/{run.id}{suffix}")).json()
        assert all(body[name] is None for name in (
            "deployment_id", "effective_policy_hash", "policy_cohort", "namespace_class",
        ))


async def test_rehearsal_run_identity_survives_real_head_advance_and_health_rollback(health_repo):
    from core.distributed.policy_health import PolicyHealthEvaluator

    repo, promotion, deployment = health_repo
    run, _ = await admitted(health_repo, "task9-candidate", cohort="candidate")
    queries = OpsQueries(repo.session_factory)
    expected = (str(run.deployment_id), run.effective_policy_hash, "candidate", "rehearsal")

    async def pinned():
        for result in (await queries.get_run(run.id), await queries.get_run_trace(run.id)):
            body = result.model_dump(mode="json")
            assert tuple(body[name] for name in (
                "deployment_id", "effective_policy_hash", "policy_cohort", "namespace_class",
            )) == expected
            assert run.state_namespace not in json.dumps(body)

    await pinned()
    advanced = await candidate_head(repo, state="canary", traffic=5000, version=3)
    fixture, _ = await fill_window((repo, promotion, advanced), changes={
        "commit_outcome": "failed", "terminal_status": "commit_failed",
    })
    window = await PolicyHealthEvaluator(promotion).evaluate(advanced.deployment_id)
    assert window.decision == "fail"
    head = await promotion.get_head("rehearsal")
    assert head.state.value == "rolled_back"
    assert str(head.deployment_id) != advanced.deployment_id
    detail = await queries.get_policy_deployment(advanced.deployment_id)
    assert len(detail.audit_events) == 1
    audit = detail.audit_events[0]
    assert audit.event_type == "health_rollback"
    assert str(audit.deployment_id) == str(head.deployment_id)
    assert str(audit.failed_deployment_id) == advanced.deployment_id
    assert audit.health_window_id == window.window_id
    filtered = await queries.list_policy_audit(limit=1, deployment_id=advanced.deployment_id)
    assert filtered.items == detail.audit_events
    await pinned()


async def test_policy_cohort_counts_include_pinned_runs_and_shadow_jobs(policy_ops):
    repo = policy_ops.repo
    deployment_id = policy_ops.deployments[1].deployment_id
    candidate, _ = await repo.accept_with_replay(spec("task9-count-candidate"))
    stable, _ = await repo.accept_with_replay(spec("task9-count-stable"))
    async with repo.session_factory() as session, session.begin():
        for run, cohort in ((candidate, "candidate"), (stable, "stable")):
            await session.execute(update(DistributedRun).where(DistributedRun.id == run.id).values(
                deployment_id=deployment_id, policy_cohort=cohort,
            ))
        session.add(PolicyShadowExecutionRecord(
            shadow_id=str(uuid4()), parent_run_id=stable.id, deployment_id=deployment_id,
            policy_hash="b" * 64, status="completed", created_at=NOW, updated_at=NOW,
        ))
    detail = (await policy_ops.client.get(f"{PATHS[0]}/{deployment_id}")).json()
    assert detail["cohort_counts"] == {"stable": 1, "candidate": 1, "shadow": 1}


async def test_audit_closed_transition_and_typed_relations_never_expose_details(policy_ops):
    audit = policy_ops.audits[0]
    async with policy_ops.repo.session_factory() as session, session.begin():
        await session.execute(update(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.event_id == audit.event_id,
        ).values(event_type="promotion_transitioned", details={
            "from_state": "canary", "to_state": "frozen",
            "failed_deployment_id": SENSITIVE, "window_id": SENSITIVE,
            "innocent": SENSITIVE,
        }))
    page = (await policy_ops.client.get(PATHS[2])).json()
    body = next(row for row in page["items"] if row["event_id"] == audit.event_id)
    assert body["from_state"] == "canary" and body["to_state"] == "frozen"
    assert body["failed_deployment_id"] is None and body["health_window_id"] is None
    assert SENSITIVE not in json.dumps(body)


async def test_health_numeric_allowlist_does_not_echo_known_field_freeform(policy_ops):
    window = policy_ops.windows[0]
    async with policy_ops.repo.session_factory() as session, session.begin():
        await session.execute(update(PolicyHealthWindowRecord).where(
            PolicyHealthWindowRecord.window_id == window.window_id,
        ).values(candidate_stats={
            "mean_cost": SENSITIVE, "unknown_rate": "2", "run_count": True,
            "p95_latency": "NaN", "natural_failure_count": 0,
        }))
    body = (await policy_ops.client.get(PATHS[1], params={
        "deployment_id": window.deployment_id,
    })).json()["items"][0]
    assert SENSITIVE not in json.dumps(body)
    assert body["candidate_stats"]["mean_cost"] is None
    assert body["candidate_stats"]["unknown_rate"] is None
    assert body["candidate_stats"]["run_count"] is None
    assert body["candidate_stats"]["p95_latency"] is None
    assert body["candidate_stats"]["natural_failure_count"] == 0
