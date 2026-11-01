"""Read-only, bounded HTTP projections for distributed operations."""

from __future__ import annotations

import secrets
import re
from ipaddress import ip_address
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

from core.distributed.contracts import RunOperation, RunStatus
from core.distributed.ops_contracts import (
    OpsExpertJobDetail,
    OpsExpertJobPage,
    OpsRunDetail,
    OpsRunPage,
    OpsTrace,
    OpsWorkerPage,
    OpsAuditEventPage, OpsHealthWindowPage, OpsPolicyDeploymentDetail,
    OpsPolicyDeploymentPage,
)
from core.distributed.ops_queries import InvalidOpsCursor
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

async def require_ops_access(request: Request) -> None:
    runtime = request.app.state.distributed
    settings_obj = getattr(runtime, "settings", None)
    configured = getattr(settings_obj, "ops_api_token", "")
    if hasattr(configured, "get_secret_value"):
        configured = configured.get_secret_value()
    configured = str(configured or "")

    if configured:
        authorization = request.headers.get("authorization", "")
        scheme, _, supplied = authorization.partition(" ")
        if (
            scheme.lower() != "bearer"
            or not supplied
            or not secrets.compare_digest(supplied, configured)
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "valid Ops bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return

    host = request.client.host if request.client is not None else ""
    try:
        is_loopback = ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "testclient"
    if not is_loopback:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Ops API is loopback-only until OPS_API_TOKEN is configured",
        )


router = APIRouter(
    prefix="/ops",
    tags=["operations"],
    dependencies=[Depends(require_ops_access)],
)

_EXPERT_ROLES = {"assessment", "curriculum", "tutor"}
_EXPERT_STATUSES = {
    "accepted",
    "queued",
    "running",
    "retryable_failed",
    "completed",
    "terminal_failed",
    "exhausted",
    "cancelled",
    "parent_stale",
}
_PROCESS_TYPES = {
    "api",
    "dispatcher",
    "reaper",
    "run-worker",
    "expert-dispatcher",
    "expert-reaper",
    "expert-worker",
}
_WORKER_STATUSES = {"running", "stopped"}


def _reject_unknown(request: Request, allowed: set[str]) -> None:
    unknown = set(request.query_params) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unsupported query parameter: {names}",
        )


def _validate_filter(
    name: str,
    value: str | None,
    allowed: set[str],
) -> str | None:
    if value is not None and value not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unsupported {name}: {value}",
        )
    return value


@router.get("/runs", response_model=OpsRunPage)
async def list_runs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    run_status: str | None = Query(default=None, alias="status"),
    operation: str | None = Query(default=None),
):
    _reject_unknown(request, {"limit", "cursor", "status", "operation"})
    run_status = _validate_filter(
        "status",
        run_status,
        {item.value for item in RunStatus},
    )
    operation = _validate_filter(
        "operation",
        operation,
        {item.value for item in RunOperation},
    )
    try:
        return await request.app.state.distributed.ops_queries.list_runs(
            limit=limit,
            cursor=cursor,
            status=run_status,
            operation=operation,
        )
    except InvalidOpsCursor as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            str(exc),
        ) from exc


@router.get("/runs/{run_id}", response_model=OpsRunDetail)
async def run_detail(run_id: str, request: Request):
    _reject_unknown(request, set())
    value = await request.app.state.distributed.ops_queries.get_run(run_id)
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return value


@router.get("/runs/{run_id}/trace", response_model=OpsTrace)
async def run_trace(run_id: str, request: Request):
    _reject_unknown(request, set())
    value = await request.app.state.distributed.ops_queries.get_run_trace(
        run_id
    )
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return value


@router.get("/expert-jobs", response_model=OpsExpertJobPage)
async def list_expert_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    role: str | None = Query(default=None),
    job_status: str | None = Query(default=None, alias="status"),
    parent_run_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=36,
    ),
):
    _reject_unknown(
        request,
        {"limit", "cursor", "role", "status", "parent_run_id"},
    )
    role = _validate_filter("role", role, _EXPERT_ROLES)
    job_status = _validate_filter(
        "status",
        job_status,
        _EXPERT_STATUSES,
    )
    try:
        return (
            await request.app.state.distributed.ops_queries.list_expert_jobs(
                limit=limit,
                cursor=cursor,
                role=role,
                status=job_status,
                parent_run_id=parent_run_id,
            )
        )
    except InvalidOpsCursor as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            str(exc),
        ) from exc


@router.get(
    "/expert-jobs/{job_id}",
    response_model=OpsExpertJobDetail,
)
async def expert_job_detail(job_id: str, request: Request):
    _reject_unknown(request, set())
    value = (
        await request.app.state.distributed.ops_queries.get_expert_job(job_id)
    )
    if value is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "expert job not found",
        )
    return value


@router.get("/workers", response_model=OpsWorkerPage)
async def list_workers(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=512),
    worker_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=128,
    ),
    process_type: str | None = Query(default=None),
    worker_status: str | None = Query(default=None, alias="status"),
):
    _reject_unknown(
        request,
        {
            "limit",
            "cursor",
            "worker_id",
            "process_type",
            "status",
        },
    )
    process_type = _validate_filter(
        "process_type",
        process_type,
        _PROCESS_TYPES,
    )
    worker_status = _validate_filter(
        "status",
        worker_status,
        _WORKER_STATUSES,
    )
    try:
        return await request.app.state.distributed.ops_queries.list_workers(
            limit=limit,
            cursor=cursor,
            worker_id=worker_id,
            process_type=process_type,
            status=worker_status,
        )
    except InvalidOpsCursor as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            str(exc),
        ) from exc


def _policy_params(request: Request, allowed: set[str]) -> dict:
    params = request.query_params
    if set(params) - allowed or len(params.multi_items()) != len(params):
        raise HTTPException(422, "invalid policy query")
    values = dict(params)
    limit = values.get("limit", "50")
    if not re.fullmatch(r"[0-9]{1,3}", limit) or not 1 <= int(limit) <= 100:
        raise HTTPException(422, "invalid policy limit")
    values["limit"] = int(limit)
    if any(value == "" or len(str(value)) > 512 for value in values.values()):
        raise HTTPException(422, "invalid policy query")
    return values


async def _policy_query(request: Request, method: str, **params):
    try:
        return await getattr(request.app.state.distributed.ops_queries, method)(**params)
    except InvalidOpsCursor as exc:
        raise HTTPException(422, "invalid policy query") from exc
    except (ValidationError, SQLAlchemyError) as exc:
        raise HTTPException(503, "policy evidence temporarily unavailable") from exc


@router.get("/policies/deployments", response_model=OpsPolicyDeploymentPage)
async def policy_deployments(request: Request):
    params = _policy_params(request, {"limit", "cursor", "environment", "state"})
    return await _policy_query(request, "list_policy_deployments", **params)


@router.get("/policies/deployments/{deployment_id}", response_model=OpsPolicyDeploymentDetail)
async def policy_deployment_detail(request: Request, deployment_id: str):
    if request.query_params:
        raise HTTPException(422, "invalid policy query")
    value = await _policy_query(request, "get_policy_deployment", deployment_id=deployment_id)
    if value is None:
        raise HTTPException(404, "policy deployment not found")
    return value


@router.get("/policies/health-windows", response_model=OpsHealthWindowPage)
async def policy_health_windows(request: Request):
    params = _policy_params(request, {
        "limit", "cursor", "environment", "deployment_id", "decision",
    })
    return await _policy_query(request, "list_policy_health_windows", **params)


@router.get("/policies/audit", response_model=OpsAuditEventPage)
async def policy_audit(request: Request):
    params = _policy_params(request, {
        "limit", "cursor", "environment", "deployment_id", "event_type",
    })
    return await _policy_query(request, "list_policy_audit", **params)
