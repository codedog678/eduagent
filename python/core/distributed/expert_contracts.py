from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from core.tool_executor import PracticeParams

from .contracts import Identifier, canonical_hash


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be aware UTC")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_aware_utc)]
BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]
Finding = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
SourceRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExpertRole(StrEnum):
    ASSESSMENT = "Assessment"
    CURRICULUM = "Curriculum"
    TUTOR = "Tutor"


class ExpertErrorCode(StrEnum):
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    DEADLINE_EXPIRED = "deadline_expired"
    DELEGATE_UNAVAILABLE = "delegate_unavailable"
    EXPERT_ACTION_INVALID = "expert_action_invalid"
    EXPERT_ACTION_NOT_ALLOWED = "expert_action_not_allowed"
    EXPERT_BACKPRESSURE = "expert_backpressure"
    EXPERT_FAILED = "expert_failed"
    EXPERT_FINDINGS_MISSING = "expert_findings_missing"
    EXPERT_FINDINGS_TOO_LONG = "expert_findings_too_long"
    EXPERT_OUTPUT_INCOMPLETE = "expert_output_incomplete"
    EXPERT_QUESTION_MISSING = "expert_question_missing"
    EXPERT_RESULT_INVALID = "expert_result_invalid"
    EXPERT_SCHEMA_INVALID = "expert_schema_invalid"
    EXPERT_SOURCES_UNVERIFIED = "expert_sources_unverified"
    EXPERT_STATUS_INVALID = "expert_status_invalid"
    EXPERT_TASK_MISMATCH = "expert_task_mismatch"
    LEASE_LOST = "lease_lost"
    PARENT_STALE = "parent_stale"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    QUESTION_NOT_CREATED = "question_not_created"
    SOURCE_UNAVAILABLE = "source_unavailable"
    TOOL_ARGUMENT_INVALID = "tool_argument_invalid"
    UNSUPPORTED_ROLE = "unsupported_role"


class RunExecutionAuthority(FrozenContract):
    distributed_run_id: UUID
    run_fencing_token: int = Field(ge=1)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    attempt_number: int = Field(ge=1)
    worker_id: Identifier
    parent_deadline_at: UtcDateTime


class ExpertBudget(FrozenContract):
    max_model_calls: int = Field(ge=1, le=6)
    max_tool_calls: int = Field(ge=0, le=10)
    max_output_tokens: int = Field(ge=100, le=2000)
    max_context_tokens: int = Field(ge=1000, le=32000)
    max_attempts: int = Field(ge=1, le=5)
    deadline_at: UtcDateTime


class ExpertUsage(FrozenContract):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)
    uncertain: bool = False


class HistoryRecord(FrozenContract):
    source_ref: SourceRef
    role: str = Field(min_length=1, max_length=32)
    recorded_at: UtcDateTime
    knowledge_id: Identifier | None = None
    content: str = Field(max_length=16000)


class ExpertSnapshot(FrozenContract):
    protocol_version: Literal[1] = 1
    learner_id: Identifier
    knowledge_id: Identifier
    current_input: str = Field(max_length=4000)
    student_inputs: list[str] = Field(default_factory=list, max_length=8)
    goal: BoundedText
    constraints: list[str] = Field(default_factory=list, max_length=8)
    effective_policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    practice_policy: dict[str, Any] = Field(default_factory=dict)
    knowledge_state: dict[str, Any] = Field(default_factory=dict)
    learner_profile: dict[str, Any] = Field(default_factory=dict)
    review_queue: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_context: dict[str, Any] = Field(default_factory=dict)
    quiz_context: dict[str, Any] | None = None
    stable_memories: list[dict[str, Any]] = Field(default_factory=list)
    history_records: list[HistoryRecord] = Field(default_factory=list)
    verified_source_refs: list[SourceRef] = Field(default_factory=list, max_length=64)

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class ExpertJobRequest(FrozenContract):
    logical_key: Identifier
    learner_id: Identifier
    step_id: Identifier
    role: ExpertRole
    objective: BoundedText
    plan_id: Identifier
    plan_version: int = Field(ge=1)
    ancestor_results: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    snapshot: ExpertSnapshot
    budget: ExpertBudget
    authority: RunExecutionAuthority
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def validate_scope_and_deadline(self) -> ExpertJobRequest:
        if self.learner_id != self.snapshot.learner_id:
            raise ValueError("learner_id must match snapshot learner_id")
        if self.budget.deadline_at > self.authority.parent_deadline_at:
            raise ValueError("expert deadline must not exceed parent deadline")
        return self

    @property
    def input_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class ExpertDraft(FrozenContract):
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=16)
    uncertainty: str = Field(default="", max_length=1000)


class AssessmentCompleted(ExpertDraft):
    status: Literal["completed"]
    findings: list[Finding] = Field(min_length=1, max_length=8)


class CurriculumCompleted(AssessmentCompleted):
    proposed_actions: list[PracticeParams] = Field(default_factory=list, max_length=1)


class ExpertNeedsInput(ExpertDraft):
    status: Literal["needs_input"]
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    needs_input: Finding


class ExpertFailed(ExpertDraft):
    status: Literal["failed"]
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    error_code: ExpertErrorCode


AssessmentDraft: TypeAlias = Annotated[
    AssessmentCompleted | ExpertNeedsInput | ExpertFailed,
    Field(discriminator="status"),
]
CurriculumDraft: TypeAlias = Annotated[
    CurriculumCompleted | ExpertNeedsInput | ExpertFailed,
    Field(discriminator="status"),
]


class TutorDraft(ExpertDraft):
    status: Literal["completed", "needs_input", "failed"]
    content: str | None = Field(default=None, max_length=8000)
    needs_input: str | None = Field(default=None, max_length=1000)
    error_code: ExpertErrorCode | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> TutorDraft:
        if self.status == "completed":
            if not self.content or not self.content.strip():
                raise ValueError("completed Tutor draft requires content")
            if self.needs_input is not None or self.error_code is not None:
                raise ValueError("completed Tutor draft has incompatible fields")
        elif self.status == "needs_input":
            if not self.needs_input or not self.needs_input.strip():
                raise ValueError("needs_input Tutor draft requires needs_input")
            if self.content is not None or self.error_code is not None:
                raise ValueError("needs_input Tutor draft has incompatible fields")
        else:
            if not self.error_code or not self.error_code.strip():
                raise ValueError("failed Tutor draft requires error_code")
            if self.content is not None or self.needs_input is not None:
                raise ValueError("failed Tutor draft has incompatible fields")
        return self


class ExpertTerminalEnvelope(FrozenContract):
    step_id: Identifier
    role: ExpertRole
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["succeeded", "failed"]
    draft: AssessmentDraft | CurriculumDraft | TutorDraft | None = None
    usage: ExpertUsage
    completed_at: UtcDateTime
    diagnostics: list[str] = Field(default_factory=list, max_length=8)
    error_code: ExpertErrorCode | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> ExpertTerminalEnvelope:
        if self.outcome == "succeeded":
            if self.draft is None:
                raise ValueError("succeeded envelope requires draft")
            if self.error_code is not None:
                raise ValueError("succeeded envelope cannot include error_code")
        else:
            if not self.error_code:
                raise ValueError("failed envelope requires error_code")
            if self.draft is not None:
                raise ValueError("failed envelope cannot include draft")
        return self
