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
    template_case_id: str | None = None
    evaluation_role: Literal["agent_primary", "teaching_auxiliary"] | None = None
    capability: str | None = None
    difficulty: Literal["basic", "intermediate", "advanced"] | None = None
    tool_decision_criteria: dict[str, list[str]] = Field(default_factory=dict)
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
        return CASE_IDS.index(self.template_case_id or self.case_id) + 1

    @property
    def role(self) -> str:
        return self.evaluation_role or (
            "agent_primary" if self.number >= 5 else "teaching_auxiliary"
        )

    @property
    def history_source_refs(self) -> set[str]:
        return {"message:" + item["message_id"] for item in self.initial_facts.get("history", [])}

    @property
    def target_source_ref(self) -> str:
        return "message:" + self.initial_facts["history_recipe"]["target"]["message_id"]

    @property
    def retrieval_expectations(self) -> tuple[str, str]:
        private = self.initial_facts.get("evaluator_only", {})
        if isinstance(private, dict):
            return private["search_query"], private["expected_quote"]
        return "R08", "先圈时间，再看是否到现在"

    @property
    def foreign_expectations(self) -> tuple[str, str]:
        foreign = self.initial_facts["foreign_history"][0]
        private = self.initial_facts.get("evaluator_only", {})
        marker = private["private_marker"] if isinstance(private, dict) else "EVAL_PRIVATE_Z9"
        return "message:" + foreign["message_id"], marker

    def validate_contract(self):
        if (self.template_case_id or self.case_id) not in CASE_IDS:
            raise ValueError(f"unsupported live case: {self.case_id}")
        if self.case_id in CASE_IDS and self.template_case_id not in (None, self.case_id):
            raise ValueError("legacy case cannot change its contract")
        if self.case_id not in CASE_IDS:
            if not all((self.template_case_id, self.evaluation_role, self.capability, self.difficulty)):
                raise ValueError("variant requires explicit contract and evaluation metadata")
            converse_ids = {step.id for step in self.steps if step.action == "converse"}
            if (set(self.tool_decision_criteria) != converse_ids
                    or any(not rules for rules in self.tool_decision_criteria.values())):
                raise ValueError("variant requires tool decision criteria for every model turn")
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
        if self.number == 7 and not self.history_source_refs:
            raise ValueError("grounded continuation requires history")
        if self.number == 8:
            query, quote = self.retrieval_expectations
            if not query or not quote:
                raise ValueError("retrieval requires query and expected quote")
        if self.number == 10:
            _, marker = self.foreign_expectations
            foreign = self.initial_facts["foreign_history"][0]
            if foreign["owner"] == self.learner_id or marker not in foreign["content"]:
                raise ValueError("foreign fixture requires another learner and private marker")


def load_live_cases(path: str | Path) -> list[LiveCase]:
    cases, seen, learners = [], set(), set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = LiveCase.model_validate(json.loads(line))
            case.validate_contract()
            if case.case_id in seen:
                raise ValueError("duplicate case_id")
            if case.learner_id in learners:
                raise ValueError("duplicate learner_id")
        except (ValueError, ValidationError, KeyError, IndexError, TypeError) as exc:
            # 不回显任意输入值，以免用户错误传入凭据。
            raise DatasetError(f"{path}:{number}: invalid live case ({type(exc).__name__})") from exc
        seen.add(case.case_id)
        learners.add(case.learner_id)
        cases.append(case)
    if not cases:
        raise DatasetError("empty live dataset")
    return cases
