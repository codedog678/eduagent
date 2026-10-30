from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .contracts import Identifier, canonical_hash


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be aware UTC")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_aware_utc)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Environment = Literal["production", "rehearsal"]
PolicyCohort = Literal["stable", "candidate", "shadow"]
FaultProfile = Literal["none", "latency", "commit_failure"]
GateType = Literal[
    "artifact_integrity",
    "campaign_eligibility",
    "judge_calibration",
    "formal_holdout",
    "harness_qualification",
    "shadow_health",
    "canary_health",
    "promotion_approval",
]


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeploymentState(StrEnum):
    REGISTERED = "registered"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"
    FROZEN = "frozen"
    ROLLED_BACK = "rolled_back"

    def can_transition_to(self, target: DeploymentState) -> bool:
        allowed = {
            self.REGISTERED: {self.SHADOW, self.FROZEN},
            self.SHADOW: {self.CANARY, self.FROZEN},
            self.CANARY: {
                self.ACTIVE,
                self.FROZEN,
                self.ROLLED_BACK,
            },
            self.ACTIVE: {self.FROZEN, self.ROLLED_BACK},
            self.FROZEN: set(),
            self.ROLLED_BACK: set(),
        }
        return target in allowed[self]


class PolicyThresholds(FrozenContract):
    candidate_min_runs: int = Field(default=20, ge=1, le=10000)
    stable_min_runs: int = Field(default=20, ge=1, le=10000)
    window_max_runs: int = Field(default=50, ge=1, le=10000)
    commit_failure_rate: Decimal = Field(
        default=Decimal("0.05"), gt=0, le=1
    )
    terminal_failure_rate: Decimal = Field(
        default=Decimal("0.10"), gt=0, le=1
    )
    latency_increase_rate: Decimal = Field(
        default=Decimal("0.50"), gt=0
    )
    mean_cost_increase_rate: Decimal = Field(
        default=Decimal("0.30"), gt=0
    )
    unknown_rate: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    relative_epsilon: Decimal = Field(
        default=Decimal("0.000001"), gt=0
    )

    @property
    def digest(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class PolicyComponents(FrozenContract):
    retrieval_rules: str = Field(min_length=1, max_length=6000)


class PolicyArtifact(FrozenContract):
    policy_hash: Sha256
    parent_policy_hash: Sha256 | None = None
    components: PolicyComponents
    fixed_components_hash: Sha256
    runtime_hash: Sha256
    source_revision: str = Field(min_length=1, max_length=128)
    protocol_hash: Sha256
    proposer_hash: Sha256
    data_role: Literal[
        "builtin",
        "legacy",
        "development",
        "holdout_validated",
    ]
    evidence_bindings: dict[str, Any] = Field(default_factory=dict)
    created_at: UtcDateTime


class GateReceipt(FrozenContract):
    receipt_id: UUID
    policy_hash: Sha256
    gate_type: GateType
    status: Literal["passed", "failed", "unknown"]
    evidence_hash: Sha256
    protocol_hash: Sha256
    runtime_hash: Sha256
    source_revision: str = Field(min_length=1, max_length=128)
    model_identity: str = Field(min_length=1, max_length=256)
    data_role: str = Field(min_length=1, max_length=64)
    sample_count: int = Field(ge=0)
    cost: Decimal = Field(ge=0)
    details: dict[str, Any] = Field(default_factory=dict)
    issued_at: UtcDateTime
    issuer: Identifier


class DeploymentSnapshot(FrozenContract):
    deployment_id: UUID
    environment: Environment
    version: int = Field(ge=1)
    state: DeploymentState
    candidate_policy_hash: Sha256 | None = None
    stable_policy_hash: Sha256
    previous_stable_deployment_id: UUID | None = None
    traffic_basis_points: int = Field(ge=0, le=10000)
    assignment_salt_id: Identifier
    thresholds: PolicyThresholds
    required_receipts: list[GateType] = Field(default_factory=list)
    command_id: Identifier
    reason: str = Field(min_length=1, max_length=1000)
    actor: Identifier
    created_at: UtcDateTime

    @property
    def thresholds_hash(self) -> str:
        return self.thresholds.digest


class PolicyExecutionBinding(FrozenContract):
    deployment_id: UUID
    environment: Environment
    effective_policy_hash: Sha256
    components: PolicyComponents
    policy_cohort: PolicyCohort
    assignment_key_hash: Sha256
    assignment_reason: str = Field(min_length=1, max_length=128)
    state_namespace: str = Field(min_length=1, max_length=128)
    rehearsal_id: str | None = Field(default=None, max_length=128)
    rehearsal_fault_profile: FaultProfile = "none"


class PromotionCommand(FrozenContract):
    command_id: Identifier
    environment: Environment
    expected_version: int = Field(ge=1)
    current_state: DeploymentState
    target_state: DeploymentState
    traffic_basis_points: int = Field(default=0, ge=0, le=10000)
    actor: Identifier
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_transition(self) -> PromotionCommand:
        if not self.current_state.can_transition_to(self.target_state):
            raise ValueError("invalid deployment transition")
        if self.target_state == DeploymentState.CANARY:
            if not 1 <= self.traffic_basis_points <= 9999:
                raise ValueError("canary traffic must be between 1 and 9999")
        elif self.target_state == DeploymentState.ACTIVE:
            if self.traffic_basis_points != 10000:
                raise ValueError("active traffic must be 10000")
        elif self.traffic_basis_points != 0:
            raise ValueError("non-serving deployment traffic must be zero")
        return self


class PolicyObservation(FrozenContract):
    observation_key: Sha256
    run_id: UUID
    deployment_id: UUID
    policy_hash: Sha256
    cohort: PolicyCohort
    state_namespace: str = Field(min_length=1, max_length=128)
    metric_contract_version: Literal[1] = 1
    terminal_status: str = Field(min_length=1, max_length=32)
    latency_seconds: Decimal = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    commit_outcome: Literal["succeeded", "failed", "not_attempted"]
    permission_outcome: Literal["allowed", "denied", "not_applicable"]
    structured_result: Literal["valid", "invalid", "unknown", "not_applicable"]
    injected: bool = False
    observed_at: UtcDateTime
    source_trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class HealthDecision(FrozenContract):
    decision: Literal["pass", "hold", "rollback"]
    reasons: list[str] = Field(default_factory=list, max_length=16)
    candidate_run_count: int = Field(ge=0)
    stable_run_count: int = Field(ge=0)
    evaluated_at: UtcDateTime


class RehearsalClaims(FrozenContract):
    rehearsal_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")]
    deployment_id: UUID
    deployment_version: int = Field(ge=1)
    learner_id: Identifier
    request_id: Identifier
    namespace: str = Field(
        pattern=r"^rehearsal-[a-z0-9][a-z0-9-]{0,62}$"
    )
    operations: list[Literal["learning_task"]] = Field(
        min_length=1,
        max_length=8,
    )
    fault_profile: FaultProfile = "none"
    nonce: Identifier
    issued_at: UtcDateTime
    expires_at: UtcDateTime

    @model_validator(mode="after")
    def validate_expiry(self) -> RehearsalClaims:
        if self.expires_at <= self.issued_at:
            raise ValueError("rehearsal token must expire after issuance")
        return self
