import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update

from api.distributed_main import create_app
from core.distributed import ops_queries as ops_queries_module
from core.distributed import worker_registry as worker_registry_module
from core.distributed.expert_contracts import (
    AssessmentCompleted,
    ExpertRole,
    ExpertTerminalEnvelope,
)
from core.distributed.expert_models import (
    DistributedExpertResult,
    DistributedWorkerRegistry,
)
from core.distributed.models import DistributedRun
from core.distributed.ops_queries import OpsQueries
from core.distributed.worker_registry import RegistryProcess, WorkerRegistry
from tests.distributed.test_expert_repository import (
    parent_claim,
    request_for,
    usage,
)

pytestmark = pytest.mark.distributed_integration

FORBIDDEN_KEY_PARTS = {
    "payload",
    "draft",
    "history",
    "prompt",
    "reasoning",
    "secret",
    "diagnostic",
    "objective",
    "finding",
    "content",
}
SEEDED_SECRETS = {
    "run-payload-secret",
    "run-result-secret",
    "expert-objective-secret",
    "expert-draft-secret",
    "expert-diagnostic-secret",
    "trace-attribute-secret",
    "worker-metadata-secret",
}


def assert_recursively_redacted(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            assert not any(
                part in normalized for part in FORBIDDEN_KEY_PARTS
            ), f"forbidden Ops response key: {key}"
            assert_recursively_redacted(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            assert_recursively_redacted(item)
        return
    if isinstance(value, str):
        assert not any(secret in value for secret in SEEDED_SECRETS)


class SkewedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(1999, 1, 1, tzinfo=tz or UTC)


async def _db_now(session_factory):
    async with session_factory() as session:
        return await session.scalar(select(func.now()))


async def _worker_row(session_factory, worker_id, instance_id):
    async with session_factory() as session:
        return await session.scalar(
            select(DistributedWorkerRegistry).where(
                DistributedWorkerRegistry.worker_id == worker_id,
                DistributedWorkerRegistry.instance_id == instance_id,
            )
        )


async def _seed_expert_graph(repo, expert_repo, index):
    run, claim = await parent_claim(repo, f"ops-run-{index}")
    request = request_for(
        claim,
        logical_key=f"ops:{index}:assessment",
        objective=f"expert-objective-secret-{index}",
    )
    request = request.model_copy(
        update={
            "snapshot": request.snapshot.model_copy(
                update={"verified_source_refs": [f"source-{index}"]}
            )
        }
    )
    job, _ = await expert_repo.create_or_replay(request)
    expert_claim = await expert_repo.claim(
        job.id,
        f"expert-worker-{index}",
        {ExpertRole.ASSESSMENT},
        lease_seconds=30,
    )
    envelope = ExpertTerminalEnvelope(
        step_id=request.step_id,
        role=request.role,
        input_hash=request.input_hash,
        outcome="succeeded",
        draft=AssessmentCompleted(
            status="completed",
            findings=[f"expert-draft-secret-{index}"],
            source_refs=[f"source-{index}"],
        ),
        usage=usage(model_calls=index + 1, tool_calls=index),
        diagnostics=[f"expert-diagnostic-secret-{index}"],
        completed_at=datetime.now(UTC),
    )
    receipt = await expert_repo.submit_result(
        job.id,
        f"expert-worker-{index}",
        expert_claim.fencing_token,
        envelope,
    )
    assert receipt.accepted

    root_span_id = f"{index + 1:016x}"
    child_span_id = f"{index + 101:016x}"
    await repo.start_span(
        run.id,
        run.trace_id,
        root_span_id,
        None,
        "run.attempt",
        {
            "worker_id": f"run-worker-{index}",
            "prompt": f"trace-attribute-secret-{index}",
        },
    )
    await repo.finish_span(root_span_id, "ok", {"duration_ms": 11 + index})
    await repo.start_span(
        run.id,
        run.trace_id,
        child_span_id,
        root_span_id,
        "expert.wait",
        {"job_id": job.id},
    )
    await repo.finish_span(child_span_id, "ok", {"duration_ms": 7 + index})

    async with repo.session_factory() as session, session.begin():
        await session.execute(
            update(DistributedRun)
            .where(DistributedRun.id == run.id)
            .values(
                result={
                    "secret": f"run-result-secret-{index}",
                    "history": ["must-not-leak"],
                }
            )
        )
        session.add(
            DistributedExpertResult(
                job_id=job.id,
                expert_fencing_token=expert_claim.fencing_token - 1,
                worker_id=f"stale-expert-worker-{index}",
                disposition="rejected",
                rejection_code="expert_token_stale",
                draft={
                    "content": f"expert-draft-secret-{index}",
                    "source_refs": [
                        f"source-{index}",
                        f"expert-draft-secret-{index}",
                    ],
                },
                usage=usage(model_calls=1).model_dump(mode="json"),
                diagnostics=[f"expert-diagnostic-secret-{index}"],
                created_at=await session.scalar(select(func.now())),
            )
        )
    return run, job


@pytest_asyncio.fixture
async def ops_state(repo, expert_repo):
    registry = WorkerRegistry(repo.session_factory)
    graphs = [
        await _seed_expert_graph(repo, expert_repo, index)
        for index in range(3)
    ]
    process_types = ["run-worker", "expert-worker", "dispatcher"]
    for index, process_type in enumerate(process_types):
        await registry.register(
            worker_id=f"ops-worker-{index}",
            instance_id=f"instance-{index}",
            process_type=process_type,
            capabilities=["assessment"] if index == 1 else [],
            metadata={"secret": f"worker-metadata-secret-{index}"},
        )
        if index == 0:
            await registry.assign(
                f"ops-worker-{index}",
                f"instance-{index}",
                run_id=graphs[index][0].id,
            )
        elif index == 1:
            await registry.assign(
                f"ops-worker-{index}",
                f"instance-{index}",
                job_id=graphs[index][1].id,
            )

    queries = OpsQueries(repo.session_factory)
    app = create_app()
    app.state.distributed = SimpleNamespace(
        repository=repo,
        ops_queries=queries,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield SimpleNamespace(
            client=client,
            registry=registry,
            graphs=graphs,
        )


async def test_worker_registry_upserts_heartbeats_assigns_and_stops_with_db_time(
    repo,
    monkeypatch,
):
    monkeypatch.setattr(worker_registry_module, "datetime", SkewedDateTime)
    registry = WorkerRegistry(repo.session_factory)

    first = await registry.register(
        worker_id="registry-worker",
        instance_id="registry-instance",
        process_type="run-worker",
        capabilities=["runs"],
        metadata={"version": "one"},
    )
    first_db_now = await _db_now(repo.session_factory)
    assert abs((first_db_now - first.started_at).total_seconds()) < 5
    assert first.started_at.year != SkewedDateTime.now(UTC).year

    second = await registry.register(
        worker_id="registry-worker",
        instance_id="registry-instance",
        process_type="expert-worker",
        capabilities=["assessment", "curriculum"],
        metadata={"version": "two"},
    )
    assert second.id == first.id
    assert second.process_type == "expert-worker"
    assert second.capabilities == ["assessment", "curriculum"]
    assert second.registry_metadata == {"version": "two"}
    assert second.status == "running"

    prior_heartbeat = second.last_heartbeat_at
    heartbeated = await registry.heartbeat(
        "registry-worker",
        "registry-instance",
    )
    assert heartbeated.last_heartbeat_at >= prior_heartbeat

    assigned = await registry.assign(
        "registry-worker",
        "registry-instance",
        run_id="run-assignment",
        job_id="job-assignment",
    )
    assert assigned.current_run_id == "run-assignment"
    assert assigned.current_job_id == "job-assignment"

    stopped = await registry.stop(
        "registry-worker",
        "registry-instance",
    )
    assert stopped.status == "stopped"
    assert stopped.stopped_at is not None
    assert stopped.current_run_id is None
    assert stopped.current_job_id is None

    stored = await _worker_row(
        repo.session_factory,
        "registry-worker",
        "registry-instance",
    )
    assert stored.id == first.id
    assert stored.status == "stopped"


@pytest.mark.parametrize(
    ("path", "identity_key"),
    [
        ("/ops/runs", "run_id"),
        ("/ops/expert-jobs", "job_id"),
        ("/ops/workers", "worker_id"),
    ],
)
async def test_ops_lists_use_bounded_opaque_cursor_pagination(
    ops_state,
    path,
    identity_key,
):
    too_large = await ops_state.client.get(path, params={"limit": 101})
    assert too_large.status_code == 422

    first = await ops_state.client.get(path, params={"limit": 1})
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 1
    assert first_body["next_cursor"]
    assert first_body["next_cursor"] != first_body["items"][0][identity_key]

    second = await ops_state.client.get(
        path,
        params={"limit": 1, "cursor": first_body["next_cursor"]},
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    assert (
        second.json()["items"][0][identity_key]
        != first_body["items"][0][identity_key]
    )
    assert_recursively_redacted(first_body)
    assert_recursively_redacted(second.json())

    invalid = await ops_state.client.get(path, params={"cursor": "not-opaque"})
    assert invalid.status_code == 422


@pytest.mark.parametrize(
    ("path", "allowed_filter", "expected_key", "expected_value"),
    [
        ("/ops/runs", {"operation": "learning_task"}, "operation", "learning_task"),
        (
            "/ops/expert-jobs",
            {"role": "assessment"},
            "role",
            "assessment",
        ),
        (
            "/ops/workers",
            {"process_type": "expert-worker"},
            "process_type",
            "expert-worker",
        ),
    ],
)
async def test_ops_lists_accept_only_allow_listed_filters(
    ops_state,
    path,
    allowed_filter,
    expected_key,
    expected_value,
):
    response = await ops_state.client.get(path, params=allowed_filter)
    assert response.status_code == 200
    assert response.json()["items"]
    assert {
        item[expected_key] for item in response.json()["items"]
    } == {expected_value}

    unknown = await ops_state.client.get(
        path,
        params={"unknown_filter": "ignored-is-unsafe"},
    )
    assert unknown.status_code == 422


async def test_run_detail_and_trace_are_bounded_redacted_projections(ops_state):
    run, job = ops_state.graphs[0]

    detail = await ops_state.client.get(f"/ops/runs/{run.id}")
    trace = await ops_state.client.get(f"/ops/runs/{run.id}/trace")

    assert detail.status_code == trace.status_code == 200
    detail_body = detail.json()
    assert detail_body["run_id"] == run.id
    assert detail_body["expert_jobs"][0]["job_id"] == job.id
    assert detail_body["attempts"]
    trace_body = trace.json()
    assert trace_body["run_id"] == run.id
    assert {span["name"] for span in trace_body["spans"]} == {
        "run.attempt",
        "expert.wait",
    }
    child = next(
        span for span in trace_body["spans"]
        if span["name"] == "expert.wait"
    )
    assert child["parent_span_id"] is not None
    assert_recursively_redacted(detail_body)
    assert_recursively_redacted(trace_body)


async def test_expert_job_detail_exposes_only_bounded_audit_metadata(ops_state):
    _, job = ops_state.graphs[0]

    response = await ops_state.client.get(f"/ops/expert-jobs/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "job_id",
        "parent_run_id",
        "logical_key",
        "role",
        "status",
        "input_hash",
        "policy_hash",
        "budget",
        "usage",
        "source_refs",
        "attempts",
        "error_code",
        "created_at",
        "updated_at",
        "completed_at",
    }
    assert body["input_hash"] == job.input_hash
    assert body["policy_hash"] == job.policy_hash
    assert body["budget"]["max_model_calls"] == 3
    assert body["usage"]["model_calls"] >= 1
    assert body["source_refs"] == ["source-0"]
    assert {
        (attempt["disposition"], attempt["rejection_code"])
        for attempt in body["attempts"]
    } == {
        ("accepted", None),
        ("rejected", "expert_token_stale"),
    }
    assert all(
        set(attempt)
        <= {
            "worker_id",
            "fencing_token",
            "disposition",
            "rejection_code",
            "usage",
            "source_refs",
            "created_at",
        }
        for attempt in body["attempts"]
    )
    assert_recursively_redacted(body)


async def test_workers_use_database_time_for_freshness(ops_state, repo, monkeypatch):
    monkeypatch.setattr(ops_queries_module, "datetime", SkewedDateTime)
    worker_id = "ops-worker-0"
    instance_id = "instance-0"
    async with repo.session_factory() as session, session.begin():
        await session.execute(
            update(DistributedWorkerRegistry)
            .where(
                DistributedWorkerRegistry.worker_id == worker_id,
                DistributedWorkerRegistry.instance_id == instance_id,
            )
            .values(last_heartbeat_at=func.now() - timedelta(seconds=120))
        )

    response = await ops_state.client.get(
        "/ops/workers",
        params={"worker_id": worker_id},
    )

    assert response.status_code == 200
    worker = response.json()["items"][0]
    assert worker["worker_id"] == worker_id
    assert 115 <= worker["heartbeat_age_seconds"] <= 125
    assert worker["fresh"] is False
    assert worker["current_run_id"] == ops_state.graphs[0][0].id
    assert_recursively_redacted(response.json())


@pytest.mark.parametrize(
    "path",
    [
        "/ops/runs/missing",
        "/ops/runs/missing/trace",
        "/ops/expert-jobs/missing",
    ],
)
async def test_missing_ops_details_return_404(ops_state, path):
    response = await ops_state.client.get(path)
    assert response.status_code == 404


async def test_every_ops_response_omits_forbidden_keys_and_seeded_values(
    ops_state,
):
    run, job = ops_state.graphs[0]
    paths = [
        "/ops/runs",
        f"/ops/runs/{run.id}",
        f"/ops/runs/{run.id}/trace",
        "/ops/expert-jobs",
        f"/ops/expert-jobs/{job.id}",
        "/ops/workers",
    ]

    for path in paths:
        response = await ops_state.client.get(path)
        assert response.status_code == 200, path
        assert_recursively_redacted(response.json())


async def test_registry_process_failures_never_escape_into_business_loop():
    class FailingRegistry:
        async def register(self, **_):
            raise RuntimeError("registry unavailable")

        async def assign(self, *_args, **_kwargs):
            raise AssertionError("inactive process must not assign")

        async def clear_assignment(self, *_args, **_kwargs):
            raise AssertionError("inactive process must not clear")

        async def stop(self, *_args, **_kwargs):
            raise AssertionError("inactive process must not stop")

    process = RegistryProcess(
        registry=FailingRegistry(),
        worker_id="best-effort-worker",
        instance_id="best-effort-instance",
        process_type="run-worker",
        heartbeat_seconds=1,
        capabilities=[],
        metadata={},
    )

    await process.start()
    await process.assign(run_id="run-that-must-continue")
    await process.clear_assignment()
    await process.close()

    assert process.active is False


async def test_registry_process_retries_and_converges_assignment():
    class FlakyRegistry:
        def __init__(self):
            self.register_calls = 0
            self.assign_calls = 0
            self.assigned = None

        async def register(self, **_):
            self.register_calls += 1
            if self.register_calls == 1:
                raise RuntimeError("temporary register failure")

        async def assign(self, *_args, **kwargs):
            self.assign_calls += 1
            if self.assign_calls == 1:
                raise RuntimeError("temporary assignment failure")
            self.assigned = (
                kwargs.get("run_id"),
                kwargs.get("job_id"),
            )

        async def heartbeat(self, *_args):
            return None

        async def stop(self, *_args):
            return None

    registry = FlakyRegistry()
    process = RegistryProcess(
        registry=registry,
        worker_id="eventual-worker",
        instance_id="eventual-instance",
        process_type="run-worker",
        heartbeat_seconds=0.01,
        io_timeout_seconds=0.05,
        capabilities=[],
        metadata={},
    )

    await process.start()
    await process.assign(run_id="eventual-run")
    for _ in range(20):
        if registry.assigned == ("eventual-run", None):
            break
        await asyncio.sleep(0.01)
    await process.close()

    assert registry.register_calls >= 2
    assert registry.assign_calls >= 2
    assert registry.assigned == ("eventual-run", None)


async def test_registry_assignment_writes_cannot_finish_out_of_order():
    class OrderedRegistry:
        def __init__(self):
            self.old_started = asyncio.Event()
            self.release_old = asyncio.Event()
            self.assigned = None

        async def assign(self, *_args, **kwargs):
            value = (kwargs.get("run_id"), kwargs.get("job_id"))
            if value == ("old-run", None):
                self.old_started.set()
                await self.release_old.wait()
            self.assigned = value

    registry = OrderedRegistry()
    process = RegistryProcess(
        registry=registry,
        worker_id="ordered-worker",
        instance_id="ordered-instance",
        process_type="run-worker",
        heartbeat_seconds=1,
        io_timeout_seconds=1,
        capabilities=[],
        metadata={},
        active=True,
    )

    old_write = asyncio.create_task(process.assign(run_id="old-run"))
    await registry.old_started.wait()
    clear = asyncio.create_task(process.clear_assignment())
    await asyncio.sleep(0)
    registry.release_old.set()
    await asyncio.gather(old_write, clear)

    assert registry.assigned == (None, None)
    assert process._assignment_dirty is False


async def test_ops_access_requires_token_away_from_loopback():
    async def missing_run(_run_id):
        return None

    app = create_app()
    app.state.distributed = SimpleNamespace(
        settings=SimpleNamespace(ops_api_token=SecretStr("")),
        ops_queries=SimpleNamespace(get_run=missing_run),
    )
    async with AsyncClient(
        transport=ASGITransport(
            app=app,
            client=("203.0.113.10", 4312),
        ),
        base_url="http://test",
    ) as client:
        response = await client.get("/ops/runs/missing")
    assert response.status_code == 403

    app.state.distributed.settings.ops_api_token = SecretStr("ops-test-token")
    async with AsyncClient(
        transport=ASGITransport(
            app=app,
            client=("203.0.113.10", 4312),
        ),
        base_url="http://test",
    ) as client:
        missing = await client.get("/ops/runs/missing")
        authorized = await client.get(
            "/ops/runs/missing",
            headers={"Authorization": "Bearer ops-test-token"},
        )
    assert missing.status_code == 401
    assert authorized.status_code == 404


def test_ops_router_exposes_no_mutation_methods():
    app = create_app()
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/ops")
    ]

    assert {route.path for route in routes} == {
        "/ops/runs",
        "/ops/runs/{run_id}",
        "/ops/runs/{run_id}/trace",
        "/ops/expert-jobs",
        "/ops/expert-jobs/{job_id}",
        "/ops/workers",
    }
    assert all(route.methods <= {"GET", "HEAD"} for route in routes)
