"""Strict, content-free projections for the read-only operations surface."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OpsContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpsUsage(OpsContract):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    uncertain: bool


class OpsRunSummary(OpsContract):
    run_id: str
    operation: str
    status: str
    trace_id: str
    attempt_count: int = Field(ge=0)
    owner: str | None
    fencing_token: int = Field(ge=0)
    lease_expires_at: datetime | None
    lease_fresh: bool
    expert_job_count: int = Field(ge=0)
    usage: OpsUsage
    latency_ms: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class OpsRunAttempt(OpsContract):
    number: int = Field(ge=1)
    worker_id: str
    fencing_token: int = Field(ge=1)
    status: str
    reason: str | None
    started_at: datetime
    deadline_at: datetime
    finished_at: datetime | None
    duration_ms: int = Field(ge=0)


class OpsExpertJobSummary(OpsContract):
    job_id: str
    parent_run_id: str
    role: str
    status: str
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    error_code: str | None
    deadline_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class OpsRunDetail(OpsRunSummary):
    attempts: list[OpsRunAttempt]
    expert_jobs: list[OpsExpertJobSummary]


class OpsTraceSpan(OpsContract):
    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    status: str
    attributes: dict[str, str | int | float | bool]
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int = Field(ge=0)


class OpsTrace(OpsContract):
    run_id: str
    trace_id: str
    spans: list[OpsTraceSpan]


class OpsExpertBudget(OpsContract):
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_output_tokens: int = Field(ge=0)
    max_context_tokens: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    deadline_at: datetime


class OpsExpertAttempt(OpsContract):
    worker_id: str
    fencing_token: int = Field(ge=0)
    disposition: str
    rejection_code: str | None
    usage: OpsUsage
    source_refs: list[str]
    created_at: datetime


class OpsExpertJobDetail(OpsContract):
    job_id: str
    parent_run_id: str
    logical_key: str
    role: str
    status: str
    input_hash: str
    policy_hash: str
    budget: OpsExpertBudget
    usage: OpsUsage
    source_refs: list[str]
    attempts: list[OpsExpertAttempt]
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class OpsWorker(OpsContract):
    worker_id: str
    instance_id: str
    process_type: str
    status: str
    health: str
    fresh: bool
    capabilities: list[str]
    current_run_id: str | None
    current_job_id: str | None
    heartbeat_age_seconds: float = Field(ge=0)
    started_at: datetime
    last_heartbeat_at: datetime
    stopped_at: datetime | None


class OpsRunPage(OpsContract):
    items: list[OpsRunSummary]
    next_cursor: str | None


class OpsExpertJobPage(OpsContract):
    items: list[OpsExpertJobSummary]
    next_cursor: str | None


class OpsWorkerPage(OpsContract):
    items: list[OpsWorker]
    next_cursor: str | None
