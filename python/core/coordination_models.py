"""协调协议；结果随父事务保存，旧版计划字段保持兼容。"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.tool_executor import PracticeParams


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(min_length=1, max_length=80)
    agent: Literal["Assessment", "Curriculum", "Tutor"]
    objective: str = Field(min_length=1, max_length=1000)
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    expected_output: str = Field(default="结构化证据与建议", max_length=200)
    status: Literal["pending", "completed", "failed", "waiting", "blocked"] = "pending"
    source_refs: list[str] = Field(default_factory=list)


class StepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(min_length=1, max_length=80)
    agent: Literal["Assessment", "Curriculum", "Tutor"]
    objective: str = Field(min_length=1, max_length=1000)
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    expected_output: str = Field(default="结构化证据与建议", max_length=200)


class PlanDraft(BaseModel):
    """模型只负责意图；身份、来源、执行状态均由服务端生成。"""
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=2000)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    needs_input: str | None = Field(default=None, max_length=1000)
    steps: list[StepDraft] = Field(min_length=1, max_length=12)


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    status: Literal["completed", "needs_input", "failed"]
    findings: list[str] = Field(default_factory=list, max_length=8)
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    proposed_actions: list[PracticeParams] = Field(default_factory=list, max_length=1)
    needs_input: str | None = Field(default=None, max_length=1000)
    uncertainty: str = Field(default="", max_length=1000)
    error_code: Literal[
        "budget_exhausted", "expert_schema_invalid", "expert_result_invalid",
        "expert_task_mismatch", "expert_sources_unverified", "expert_status_invalid",
        "expert_findings_missing", "expert_findings_too_long", "expert_question_missing", "expert_action_not_allowed",
        "expert_output_incomplete",
        "tool_argument_invalid", "source_unavailable", "expert_failed",
        "expert_action_invalid", "delegate_unavailable", "question_not_created",
    ] | None = None


class PlanEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["preference", "goal"]
    status: Literal["available", "missing"]
    source_refs: list[str] = Field(default_factory=list, max_length=16)


class LearningPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effective_policy_hash: str = ""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = Field(default=1, ge=1)
    goal: str = Field(min_length=1, max_length=2000)
    constraints: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[PlanEvidence] = Field(default_factory=list, max_length=2)
    original_request: str = Field(default="", max_length=2000)
    needs_input: str | None = Field(default=None, max_length=1000)
    steps: list[PlanStep] = Field(min_length=1, max_length=12)
    status: Literal["running", "awaiting_student", "completed"] = "running"
    outcome: Literal["running", "completed", "partial", "awaiting_student"] = "running"
    practice_quiz_id: str | None = None
    results: dict[str, AgentResult] = Field(default_factory=dict)
    action_receipts: dict[str, dict] = Field(default_factory=dict)
    student_inputs: list[str] = Field(default_factory=list, max_length=8)
    checks: list[str] = Field(default_factory=list, max_length=16)
    revisions: list[dict] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_dag(self):
        seen = set()
        for step in self.steps:
            if step.step_id in seen or not set(step.depends_on) <= seen:
                raise ValueError("steps_must_be_unique_and_topologically_sorted")
            seen.add(step.step_id)
        if sum(s.agent == "Tutor" for s in self.steps) != 1 or self.steps[-1].agent != "Tutor":
            raise ValueError("plan_requires_one_final_tutor")
        if not set(self.results) <= seen:
            raise ValueError("unknown_result_task")
        return self


class PlanRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)
    steps: list[PlanStep] = Field(min_length=1, max_length=6)
