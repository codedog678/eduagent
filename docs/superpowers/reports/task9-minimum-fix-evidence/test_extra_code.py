from uuid import uuid4
import pytest
from sqlalchemy import func, select, text
from core.distributed.promotion_models import (
    PolicyAuditEventRecord, PolicyDeploymentRecord, PolicyHealthWindowRecord,
)
from tests.distributed.test_promotion_ops_api import PATHS, NOW


@pytest.mark.parametrize("path,model,key,fixture_name", [
    (PATHS[0], PolicyDeploymentRecord, "deployment_id", "deployments"),
    (PATHS[1], PolicyHealthWindowRecord, "window_id", "windows"),
    (PATHS[2], PolicyAuditEventRecord, "event_id", "audits"),
])
async def test_113_equal_time_rows_have_exact_maximum_page_and_typed_tiebreak(policy_ops, path, model, key, fixture_name):
    originals = getattr(policy_ops, fixture_name)
    expected = [getattr(row, key) for row in originals]
    base = originals[0]
    async with policy_ops.repo.session_factory() as session, session.begin():
        for index in range(110):
            values = {column.name: getattr(base, column.name) for column in model.__table__.columns}
            identity = f"{index + 1000:064x}" if key == "window_id" else str(uuid4())
            values[key] = identity
            if model is PolicyDeploymentRecord:
                values.update(version=index + 4, command_id=f"code-113-{index}")
            if model is PolicyAuditEventRecord:
                values["command_id"] = f"code-audit-113-{index}"
            session.add(model(**values))
            expected.append(identity)
    first = await policy_ops.client.get(path, params={"environment": "rehearsal", "limit": 100})
    assert first.status_code == 200 and len(first.json()["items"]) == 100
    second = await policy_ops.client.get(path, params={
        "environment": "rehearsal", "limit": 100, "cursor": first.json()["next_cursor"],
    })
    assert second.status_code == 200 and len(second.json()["items"]) == 13
    assert second.json()["next_cursor"] is None
    got = [row[key] for row in first.json()["items"] + second.json()["items"]]
    assert got == sorted(expected, reverse=True)
    assert len(got) == len(set(got)) == 113
    if model is PolicyAuditEventRecord:
        detail = await policy_ops.app.state.distributed.ops_queries.get_policy_deployment(base.deployment_id)
        assert len(detail.audit_events) == 100
    if model is PolicyHealthWindowRecord:
        detail = await policy_ops.app.state.distributed.ops_queries.get_policy_deployment(base.deployment_id)
        assert detail.latest_health_window.window_id == max(expected)


async def test_readonly_repeatable_read_hides_concurrent_append(policy_ops):
    queries = policy_ops.app.state.distributed.ops_queries
    base = policy_ops.deployments[0]
    async with queries._policy_read_session() as reader:
        assert await reader.scalar(text("SHOW transaction_read_only")) == "on"
        assert await reader.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        before = await reader.scalar(select(func.count()).select_from(PolicyDeploymentRecord))
        values = {column.name: getattr(base, column.name) for column in PolicyDeploymentRecord.__table__.columns}
        values.update(deployment_id=str(uuid4()), version=1000, command_id="code-concurrent-append")
        async with policy_ops.repo.session_factory() as writer, writer.begin():
            writer.add(PolicyDeploymentRecord(**values))
        assert await reader.scalar(select(func.count()).select_from(PolicyDeploymentRecord)) == before
        with pytest.raises(Exception, match="read-only"):
            await reader.execute(text("DELETE FROM policy_deployments WHERE false"))
    async with queries._policy_read_session() as fresh:
        assert await fresh.scalar(select(func.count()).select_from(PolicyDeploymentRecord)) == before + 1
