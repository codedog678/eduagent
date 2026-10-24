"""首批审阅场景的数据读取；不将评分定义传入模型。"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evals.io import DatasetError


CASE_IDS = (
    "live-01-tense-contrast", "live-02-passive-explanation",
    "live-03-participle-hint", "live-04-submit-object-hint",
    "live-05-missing-sentence-followup", "live-06-reading-goal-cross-session",
    "live-07-grounded-history-continuation", "live-08-retrieve-full-old-note",
    "live-09-injection-and-mastery", "live-10-foreign-source-isolation",
    "live-11-assisted-correct-not-independent", "live-12-fresh-quiz-independent-control",
)

# 固定脚本协议；拒绝未知场景，防止错误复用某条的硬检查映射。
CHECK_METHODS = (
    ("automatic",) * 3 + ("semantic_review",),
    ("automatic",) * 2 + ("semantic_review",),
    ("automatic",) * 3 + ("semantic_review",),
    ("automatic",) * 3 + ("semantic_review",),
    ("automatic",) * 4 + ("semantic_review",),
    ("automatic",) * 4 + ("semantic_review",),
    ("automatic",) * 3 + ("semantic_review",),
    ("fixture_validation",) + ("automatic",) * 4,
    ("automatic",) * 3 + ("semantic_review",),
    ("fixture_validation",) + ("automatic",) * 3 + ("semantic_review",),
    ("automatic",) * 5 + ("semantic_review",),
    ("automatic",) * 5 + ("semantic_review",),
)


class LiveStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    action: Literal["converse", "answer", "seed_new_quiz_local"]
    session_id: str | None = None
    student_input: str | None = None
    quiz_id: str | None = None
    api_input: dict[str, Any] | None = None
    followup_policy: str | None = None
    input_delivery: str | None = None
    instruction: str | None = None


class HardCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    method: Literal["automatic", "semantic_review", "fixture_validation"]
    path: str
    rule: str


class LiveCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["eduagent.tutor-live-review.v1"] = Field(alias="schema")
    review_status: str
    case_id: str
    category: str
    title: str
    knowledge_id: str
    learner_id: str = Field(pattern=r"^eval-live-")
    initial_facts: dict[str, Any]
    steps: list[LiveStep]
    expected_behavior: list[str]
    acceptable_tool_paths: list[str]
    hard_checks: list[HardCheck]
    quality_anchors: dict[str, str]
    failure_examples: list[str]
    expected_model_requests_max: int = Field(gt=0, le=6)

    @property
    def number(self) -> int:
        return CASE_IDS.index(self.case_id) + 1

    def validate_contract(self):
        if self.case_id not in CASE_IDS:
            raise ValueError(f"unsupported live case: {self.case_id}")
        expected = CHECK_METHODS[self.number - 1]
        if (tuple(check.method for check in self.hard_checks) != expected
                or [check.id for check in self.hard_checks] !=
                [f"H{i}" for i in range(1, len(expected) + 1)]):
            raise ValueError("unsupported hard-check contract")
        actions = (["converse", "converse"] if self.number in (5, 6) else
                   ["converse", "answer"] if self.number == 11 else
                   ["converse", "answer", "seed_new_quiz_local", "answer"]
                   if self.number == 12 else ["converse"])
        if [step.action for step in self.steps] != actions:
            raise ValueError("unsupported script order")
        if [step.id for step in self.steps] != [f"s{i}" for i in range(1, len(actions) + 1)]:
            raise ValueError("invalid step identifiers")
        if self.expected_model_requests_max != actions.count("converse") * 3:
            raise ValueError("invalid per-case model request cap")
        for step in self.steps:
            if step.action == "converse" and (not step.student_input or not step.session_id):
                raise ValueError("converse requires input and session")
            if step.action == "answer" and (not step.quiz_id or not step.api_input):
                raise ValueError("answer requires quiz and API input")


def load_live_cases(path: str | Path) -> list[LiveCase]:
    cases, seen = [], set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = LiveCase.model_validate(json.loads(line))
            case.validate_contract()
            if case.case_id in seen:
                raise ValueError("duplicate case_id")
        except (ValueError, ValidationError) as exc:
            # 不回显任意输入值，以免用户错误传入凭据。
            raise DatasetError(f"{path}:{number}: invalid live case ({type(exc).__name__})") from exc
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise DatasetError("empty live dataset")
    return cases
