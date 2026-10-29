import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.distributed_main import create_app
from core.distributed.metrics import DistributedMetrics
from core.distributed.models import DistributedBase
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import DistributedRuntime

pytestmark = pytest.mark.distributed_integration


class FakeBroker:
    def __init__(self):
        self.redis = self
        self.group_ready = False
        self.closed = False

    async def ensure_group(self):
        self.group_ready = True

    async def ping(self):
        return True

    async def aclose(self):
        self.closed = True


def run_payload(request_id, question="安排十分钟复习"):
    return {
        "learner_id": "student",
        "request_id": request_id,
        "operation": "learning_task",
        "payload": {
            "learner_id": "student",
            "request_id": request_id,
            "knowledge_id": "grammar_tenses",
            "question": question,
        },
    }


@pytest_asyncio.fixture
async def distributed_app():
    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    runtime = DistributedRuntime(
        engine,
        factory,
        DistributedRunRepository(factory),
        FakeBroker(),
        metrics=DistributedMetrics(),
    )
    app = create_app(lambda: runtime)
    async with app.router.lifespan_context(app):
        yield app
    assert runtime.broker.closed


@pytest_asyncio.fixture
async def distributed_client(distributed_app):
    async with AsyncClient(
        transport=ASGITransport(app=distributed_app),
        base_url="http://test",
    ) as client:
        yield client


async def test_submit_returns_202_and_replay_returns_same_run(
    distributed_client,
):
    payload = run_payload("api-1")
    first = await distributed_client.post("/api/distributed/runs", json=payload)
    second = await distributed_client.post("/api/distributed/runs", json=payload)

    assert first.status_code == second.status_code == 202
    assert first.json()["run_id"] == second.json()["run_id"]
    status = await distributed_client.get(first.json()["status_url"])
    metrics = await distributed_client.get("/metrics")
    assert status.json()["status"] == "accepted"
    assert (
        'eduagent_distributed_idempotency_hits_total{scope="request"} 1.0'
        in metrics.text
    )


async def test_conflicting_request_id_returns_explicit_409(distributed_client):
    first = run_payload("api-conflict", question="问题一")
    second = run_payload("api-conflict", question="问题二")

    assert (
        await distributed_client.post("/api/distributed/runs", json=first)
    ).status_code == 202
    response = await distributed_client.post(
        "/api/distributed/runs",
        json=second,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "request_id is already bound to different input"
    )


async def test_cancel_is_idempotent_and_metrics_are_exposed(
    distributed_client,
):
    created = await distributed_client.post(
        "/api/distributed/runs",
        json=run_payload("cancel"),
    )
    run_id = created.json()["run_id"]

    first = await distributed_client.post(
        f"/api/distributed/runs/{run_id}/cancel"
    )
    second = await distributed_client.post(
        f"/api/distributed/runs/{run_id}/cancel"
    )
    metrics = await distributed_client.get("/metrics")

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "cancelled"
    assert "eduagent_distributed_runs_total" in metrics.text
    assert (
        'eduagent_distributed_runs_total{outcome="cancelled"} 1.0'
        in metrics.text
    )


async def test_missing_run_resources_return_404(distributed_client):
    status = await distributed_client.get("/api/distributed/runs/missing")
    trace = await distributed_client.get(
        "/api/distributed/runs/missing/trace"
    )
    cancel = await distributed_client.post(
        "/api/distributed/runs/missing/cancel"
    )

    assert status.status_code == 404
    assert trace.status_code == 404
    assert cancel.status_code == 404
