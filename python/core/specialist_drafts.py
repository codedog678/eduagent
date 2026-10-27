"""角色和状态约束的专家草稿；兼容旧身份字段，但不能接受矛盾身份。"""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from core.agent_errors import AgentExecutionError
from core.coordination_models import AgentResult
from core.tool_executor import PracticeParams


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    uncertainty: str = Field(default="", max_length=1000)


Finding = Annotated[str, Field(max_length=1000)]


class Completed(Draft):
    status: Literal["completed"]
    findings: list[Finding] = Field(min_length=1, max_length=8)


class CurriculumCompleted(Completed):
    proposed_actions: list[PracticeParams] = Field(default_factory=list, max_length=1)


class NeedsInput(Draft):
    status: Literal["needs_input"]
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    needs_input: str = Field(min_length=1, max_length=1000)


class Failed(Draft):
    status: Literal["failed"]
    findings: list[Finding] = Field(default_factory=list, max_length=8)
    error_code: str | None = None


def adapter(role):
    complete = CurriculumCompleted if role == "Curriculum" else Completed
    return TypeAdapter(Annotated[complete | NeedsInput | Failed, Field(discriminator="status")])


def parse_result(content, step, refs, history, learner, last_failure=None):
    try:
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError
    except (ValueError, TypeError):
        raise AgentExecutionError("expert_schema_invalid", "json_invalid")
    if raw.get("task_id", step.step_id) != step.step_id:
        raise AgentExecutionError("expert_task_mismatch", "identity_mismatch",
                                  [{"field": "task_id", "type": "identity_mismatch"}])
    raw.pop("task_id", None)
    # 旧结果的空可选字段兼容；非空矛盾字段继续交给角色/status校验拒绝。
    for key in ("needs_input", "error_code", "proposed_actions"):
        if raw.get(key) in (None, "", []):
            raw.pop(key, None)
    try:
        draft = adapter(step.agent).validate_python(raw)
    except ValidationError as exc:
        errors = [{"field": ".".join(map(str, e["loc"])), "type": e["type"]}
                  for e in exc.errors(include_input=False, include_url=False)]
        fields = {e["field"].split(".")[-1] for e in errors}
        code = ("expert_action_not_allowed" if "proposed_actions" in fields else
                "expert_schema_invalid" if any(e["type"] == "extra_forbidden" for e in errors) else
                "expert_findings_too_long" if any("findings" in e["field"].split(".")
                    and e["type"] in {"too_long", "string_too_long"} for e in errors) else
                "expert_findings_missing" if "findings" in fields else
                "expert_question_missing" if "needs_input" in fields and raw.get("status") == "needs_input" else
                "expert_status_invalid" if any(e["type"].startswith("union_tag") for e in errors) else
                "expert_schema_invalid")
        raise AgentExecutionError(code, "ValidationError", errors) from exc
    if (any(not item.strip() for item in getattr(draft, "findings", []))
            or (isinstance(draft, NeedsInput) and not draft.needs_input.strip())):
        raise AgentExecutionError("expert_result_invalid", "blank_required_field")
    if not set(draft.source_refs) <= refs:
        raise AgentExecutionError("expert_sources_unverified", "unverified_sources",
                                  [{"field": "source_refs", "type": "unverified_sources"}])
    if any(not history.memory.source(learner, ref)
           for ref in draft.source_refs):
        raise AgentExecutionError("source_unavailable", "expired_sources")
    body = draft.model_dump()
    if draft.status == "failed":
        body["error_code"] = body.get("error_code") or last_failure or "expert_failed"
    try:
        return AgentResult(task_id=step.step_id, **body)
    except ValidationError as exc:
        raise AgentExecutionError("expert_schema_invalid", "ValidationError",
                                  [{"field": "error_code", "type": "invalid_code"}]) from exc
