from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST

from core.distributed.contracts import DistributedRunRequest
from core.distributed.repository import RequestConflict

router = APIRouter()
metrics_router = APIRouter()


@router.post("/distributed/runs", status_code=status.HTTP_202_ACCEPTED)
async def submit_run(spec: DistributedRunRequest, request: Request):
    runtime = request.app.state.distributed
    try:
        run, replayed = await runtime.repository.accept_with_replay(spec)
    except RequestConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if replayed:
        runtime.metrics.idempotency_hits.labels(scope="request").inc()
    return {
        "run_id": run.id,
        "status": run.status,
        "status_url": f"/api/distributed/runs/{run.id}",
        "trace_url": f"/api/distributed/runs/{run.id}/trace",
    }


@router.get("/distributed/runs/{run_id}")
async def run_status(run_id: str, request: Request):
    run = await request.app.state.distributed.repository.get(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return run.public_dict()


@router.get("/distributed/runs/{run_id}/trace")
async def run_trace(run_id: str, request: Request):
    repository = request.app.state.distributed.repository
    if await repository.get(run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return {
        "run_id": run_id,
        "spans": [
            span.public_dict()
            for span in await repository.trace(run_id)
        ],
    }


@router.post("/distributed/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request):
    runtime = request.app.state.distributed
    if await runtime.repository.get(run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    run, transitioned = (
        await runtime.repository.cancel_with_transition(run_id)
    )
    if transitioned:
        runtime.metrics.runs.labels(outcome=run.status).inc()
        elapsed = datetime.now(UTC) - run.created_at
        runtime.metrics.run_latency.observe(
            max(0, elapsed.total_seconds())
        )
    return run.public_dict()


@router.get("/health")
async def health(request: Request):
    return await request.app.state.distributed.health()


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    runtime = request.app.state.distributed
    runtime.metrics.observe_status_counts(
        await runtime.repository.status_counts()
    )
    return Response(
        runtime.metrics.render(),
        media_type=CONTENT_TYPE_LATEST,
    )
