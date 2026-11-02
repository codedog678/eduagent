"""Fresh SPEC-only transport/schema evidence; never written to product source."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.distributed_main import create_app
from core.distributed.ops_contracts import OpsPolicyDeploymentDetail
from tests.distributed.test_policy_health import health_repo
from tests.distributed.test_policy_health_corrections import real_active_fixture

E = Path(os.environ["REVIEW_OWN"]) / os.environ["EVIDENCE_RUN"]
E.mkdir(exist_ok=True)
pytestmark = pytest.mark.distributed_integration


@pytest.mark.parametrize("kind", ["database", "dto"])
@pytest.mark.parametrize("path,method", [
    ("/ops/policies/deployments", "list_policy_deployments"),
    ("/ops/policies/deployments/11111111-1111-1111-1111-111111111111", "get_policy_deployment"),
    ("/ops/policies/health-windows", "list_policy_health_windows"),
    ("/ops/policies/audit", "list_policy_audit"),
])
async def test_sanitized_retryable_503_for_every_policy_get(kind, path, method):
    async def fail(**kwargs):
        if kind == "database":
            raise SQLAlchemyError("private-db-diagnostic-not-public")
        OpsPolicyDeploymentDetail.model_validate({"private": "private-dto-not-public"})

    app = create_app()
    app.state.distributed = SimpleNamespace(
        ops_queries=SimpleNamespace(**{method: fail}),
        settings=SimpleNamespace(ops_api_token=""),
    )
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get(path)
    proof = dict(method="GET", path=path, kind=kind,
                 status=response.status_code, body=response.json())
    (E / (method + "-" + kind + ".json")).write_text(json.dumps(proof, indent=2) + "\n")
    assert response.status_code == 503
    assert response.json() == {"detail": "policy evidence temporarily unavailable"}
    assert "private" not in response.text


async def test_real_migrated_health_fixture_has_fk_and_append_only_triggers(health_repo):
    prepared, _, _ = await real_active_fixture(health_repo, command_prefix="spec-schema")
    repo, _, deployment = prepared
    async with repo.session_factory() as session:
        db = await session.scalar(text("SELECT current_database()"))
        constraints = (await session.execute(text("""
            SELECT rel.relname, con.conname, CAST(con.contype AS text) AS contype, con.convalidated,
                   pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid=con.conrelid
            WHERE rel.relname IN (
                'policy_observations', 'policy_deployments', 'policy_gate_receipts',
                'policy_health_windows', 'policy_audit_events'
            ) ORDER BY rel.relname, con.conname
        """))).mappings().all()
        triggers = (await session.execute(text("""
            SELECT rel.relname, tr.tgname, CAST(tr.tgenabled AS text) AS tgenabled,
                   tr.tgtype AS trigger_type, pg_get_triggerdef(tr.oid) AS definition
            FROM pg_trigger tr JOIN pg_class rel ON rel.oid=tr.tgrelid
            WHERE NOT tr.tgisinternal AND rel.relname IN (
                'policy_artifacts', 'policy_deployments', 'policy_gate_receipts',
                'policy_observations', 'policy_health_windows', 'policy_audit_events'
            ) ORDER BY rel.relname, tr.tgname
        """))).mappings().all()
        internal_types = (await session.execute(text("""
            SELECT contype FROM pg_constraint
            WHERE conrelid='policy_observations'::regclass
        """))).scalars().all()
    (E / "real-schema-before-assertions.json").write_text(json.dumps(dict(
        db=db, constraints=[dict(c) for c in constraints], triggers=[dict(t) for t in triggers],
        internal_types=[dict(type=type(v).__name__, repr=repr(v)) for v in internal_types]),
        indent=2, default=str) + "\n")
    assert db.startswith("m3_t9_codee8c530_")
    assert any(c["relname"] == "policy_observations" and c["contype"] == "f"
               and "distributed_runs" in c["definition"] and c["convalidated"] for c in constraints)
    required = {"policy_artifacts", "policy_deployments", "policy_gate_receipts",
                "policy_observations", "policy_health_windows", "policy_audit_events"}
    assert required <= {t["relname"] for t in triggers if t["tgenabled"] == "O"
                        and t["trigger_type"] & 27 == 27}
    failures = []
    for table in sorted(required):
        async with repo.session_factory() as session, session.begin():
            with pytest.raises(SQLAlchemyError, match="append-only") as error:
                async with session.begin_nested():
                    await session.execute(text(
                        f"DELETE FROM {table} WHERE ctid=(SELECT ctid FROM {table} LIMIT 1)"
                    ))
            failures.append(dict(table=table, error_class=type(error.value).__name__,
                                 rejected=True, existing_row_targeted=True, savepoint_rolled_back=True))
    (E / "real-schema-and-write-rejection.json").write_text(json.dumps(dict(
        db=db, deployment_id=str(deployment.deployment_id), constraints=[dict(c) for c in constraints],
        triggers=[dict(t) for t in triggers], write_rejections=failures), indent=2) + "\n")
