"""Strict, content-free projections for the read-only operations surface."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from .promotion_contracts import (
    DeploymentState, Environment, GateType, PolicyCohort, PolicyThresholds, Sha256,
)


class OpsContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpsUsage(OpsContract):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    uncertain: bool


class OpsPolicyBinding(OpsContract):
    deployment_id: UUID | None
    effective_policy_hash: Sha256 | None
    policy_cohort: PolicyCohort | None
    namespace_class: Environment | None


class OpsRunSummary(OpsPolicyBinding):
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


class OpsTrace(OpsPolicyBinding):
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


ShortPolicyHash = Annotated[str, Field(pattern=r"^[0-9a-f]{12}$")]
RedactedIdentity = Literal["redacted"]
OpsAuditType = Literal[
    "qualification_registered", "promotion_transitioned", "promotion_rejected",
    "health_rollback", "admission_artifact_rejected", "redacted",
]
OpsThresholdCode = Literal[
    "confirmed_permission_violation", "baseline_shortage", "cost_unavailable",
    "structured_decisions_unavailable", "commit_failure_rate", "terminal_failure_rate",
    "unknown_rate", "latency_increase_rate", "mean_cost_increase_rate",
    "matched_window_incomplete", "redacted",
]


class OpsCohortCounts(OpsContract):
    stable: int = Field(ge=0)
    candidate: int = Field(ge=0)
    shadow: int = Field(ge=0)


class OpsHealthStats(OpsContract):
    run_count: int | None = Field(default=None, ge=0)
    commit_failure_rate: Decimal | None = Field(default=None, ge=0, le=1)
    terminal_failure_rate: Decimal | None = Field(default=None, ge=0, le=1)
    p95_latency: Decimal | None = Field(default=None, ge=0)
    mean_cost: Decimal | None = Field(default=None, ge=0)
    structured_decision_count: int | None = Field(default=None, ge=0)
    unknown_decision_count: int | None = Field(default=None, ge=0)
    unknown_rate: Decimal | None = Field(default=None, ge=0, le=1)
    fault_injected_count: int | None = Field(default=None, ge=0)
    injected_commit_failure_count: int | None = Field(default=None, ge=0)
    natural_failure_count: int | None = Field(default=None, ge=0)
    latency_increase_rate: Decimal | None = None
    mean_cost_increase_rate: Decimal | None = None


class OpsGateReceipt(OpsContract):
    receipt_id: UUID
    policy_hash: Sha256
    gate_type: GateType
    status: Literal["passed", "failed", "unknown"]
    evidence_hash: Sha256
    sample_count: int = Field(ge=0)
    cost: Decimal = Field(ge=0)
    issuer: RedactedIdentity
    issued_at: datetime


class OpsHealthWindow(OpsContract):
    window_id: Sha256
    deployment_id: UUID
    deployment_version: int | None = Field(ge=1)
    environment: Environment
    metric_contract_version: int = Field(ge=1)
    thresholds_hash: Sha256 | None
    candidate_stats: OpsHealthStats
    stable_stats: OpsHealthStats
    decision: Literal["pass", "hold", "fail"]
    triggered_thresholds: list[OpsThresholdCode] = Field(max_length=16)
    evaluated_at: datetime
    created_at: datetime


class OpsAuditEvent(OpsContract):
    event_id: UUID
    environment: Environment
    deployment_id: UUID | None
    failed_deployment_id: UUID | None
    health_window_id: Sha256 | None
    from_state: DeploymentState | None
    to_state: DeploymentState | None
    event_type: OpsAuditType
    actor: RedactedIdentity
    reason: RedactedIdentity
    created_at: datetime


class OpsPolicyDeployment(OpsContract):
    deployment_id: UUID
    environment: Environment
    version: int = Field(ge=1)
    state: DeploymentState
    candidate_policy_hash: ShortPolicyHash | None
    stable_policy_hash: ShortPolicyHash
    is_current: bool
    current_deployment_id: UUID | None
    current_version: int | None = Field(ge=1)
    traffic_basis_points: int = Field(ge=0, le=10000)
    cohort_counts: OpsCohortCounts
    thresholds: PolicyThresholds
    thresholds_hash: Sha256
    required_receipts: list[GateType] = Field(max_length=8)
    actor: RedactedIdentity
    reason: RedactedIdentity
    created_at: datetime


class OpsPolicyDeploymentDetail(OpsPolicyDeployment):
    candidate_policy_hash: Sha256 | None
    stable_policy_hash: Sha256
    gate_receipts: list[OpsGateReceipt] = Field(max_length=8)
    latest_health_window: OpsHealthWindow | None
    audit_events: list[OpsAuditEvent] = Field(max_length=100)


class OpsPolicyDeploymentPage(OpsContract):
    items: list[OpsPolicyDeployment] = Field(max_length=100)
    next_cursor: str | None


class OpsHealthWindowPage(OpsContract):
    items: list[OpsHealthWindow] = Field(max_length=100)
    next_cursor: str | None


class OpsAuditEventPage(OpsContract):
    items: list[OpsAuditEvent] = Field(max_length=100)
    next_cursor: str | None
