"""Harness 长任务评测的冻结数据协议。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evals.io import DatasetError


CASE_ACTIONS = {
    "L01": ["converse"],
    "L02": ["converse", "restart", "converse"],
    "L03": ["converse"],
    "L04": ["converse", "process_memory", "restart", "converse"],
    "L05": ["converse", "hint", "answer_wrong", "answer_correct"],
    "L06": ["converse"],
}


class SeedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    session_id: str
    knowledge_id: str
    role: Literal["user", "assistant"] = "user"
    content: str = Field(min_length=1, max_length=12000)


class SeedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["preference", "goal"]
    content: str = Field(min_length=1, max_length=1000)
    source_message_id: str


class InitialFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    history: list[SeedMessage] = Field(default_factory=list)
    memories: list[SeedMemory] = Field(default_factory=list)
    forbidden_markers: list[str] = Field(default_factory=list)


class LongTaskStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    action: Literal[
        "converse", "restart", "process_memory", "hint", "answer_wrong", "answer_correct"
    ]
    request_id: str | None = None
    session_id: str | None = None
    student_input: str | None = None


class LongTaskCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["eduagent.harness-long-task.v1"] = Field(alias="schema")
    case_id: str
    title: str
    learner_id: str = Field(pattern=r"^eval-long-")
    knowledge_id: str
    initial_facts: InitialFacts
    stages: list[LongTaskStage] = Field(min_length=1, max_length=8)
    required_source_ids: list[str] = Field(default_factory=list)
    success_contract: list[str] = Field(min_length=1)
    expected_model_requests_max: int = Field(default=20, gt=0, le=20)

    def validate_contract(self) -> None:
        expected = CASE_ACTIONS.get(self.case_id)
        if expected is None or [stage.action for stage in self.stages] != expected:
            raise ValueError("unsupported long-task script")
        if [stage.id for stage in self.stages] != [
            f"s{index}" for index in range(1, len(self.stages) + 1)
        ]:
            raise ValueError("stage identifiers must be sequential")
        message_ids = {message.message_id for message in self.initial_facts.history}
        if len(message_ids) != len(self.initial_facts.history):
            raise ValueError("duplicate seed message")
        if not set(self.required_source_ids) <= message_ids:
            raise ValueError("required source is not seeded")
        for memory in self.initial_facts.memories:
            source = next(
                (item for item in self.initial_facts.history
                 if item.message_id == memory.source_message_id),
                None,
            )
            if source is None or source.role != "user" or memory.content not in source.content:
                raise ValueError("memory must quote a seeded user message")
        for stage in self.stages:
            if stage.action == "converse":
                if not all((stage.request_id, stage.session_id, stage.student_input)):
                    raise ValueError("converse stage requires request, session and input")
            elif stage.action in {"hint", "answer_wrong", "answer_correct"}:
                if not stage.request_id:
                    raise ValueError("quiz stage requires request")
            elif any((stage.request_id, stage.session_id, stage.student_input)):
                raise ValueError("local lifecycle stage cannot carry request input")

    @property
    def required_source_refs(self) -> set[str]:
        return {"message:" + identifier for identifier in self.required_source_ids}


def load_long_task_cases(path: str | Path) -> list[LongTaskCase]:
    cases: list[LongTaskCase] = []
    seen_cases: set[str] = set()
    seen_learners: set[str] = set()
    source = Path(path)
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"cannot read long-task dataset {source}") from exc
    for line_no, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            case = LongTaskCase.model_validate(json.loads(raw))
            case.validate_contract()
            if case.case_id in seen_cases or case.learner_id in seen_learners:
                raise ValueError("duplicate case or learner")
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise DatasetError(
                f"{source}:{line_no}: invalid long-task case ({type(exc).__name__})"
            ) from exc
        seen_cases.add(case.case_id)
        seen_learners.add(case.learner_id)
        cases.append(case)
    if [case.case_id for case in cases] != list(CASE_ACTIONS):
        raise DatasetError("long-task dataset must contain L01-L06 in fixed order")
    return cases


def public_case(case: LongTaskCase) -> dict[str, Any]:
    """报告保留合同，移除可能被误当作模型答案的内部字段。"""
    return case.model_dump(mode="json", by_alias=True)
