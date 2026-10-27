"""新语义门禁、默认提示兼容和专家紧凑输出的离线回归。"""

import asyncio
import json
from pathlib import Path

import pytest

from core.agent_errors import AgentExecutionError
from core.coordination_models import LearningPlan
from core.llm_service import NativeTurn
from core.specialist_runtime import SpecialistRuntime
from core.tutor_policy import (
    BASE_RULES, QUIZ_RULES, TURN_RULES, RETRIEVAL_RULES, system_prompt, use_retrieval_rules,
)
from evals.live_cases import load_live_cases
from evals.optimization.protocol import prepare_protocol, validate_candidate
from evals.optimization.calibration import GROUPS, calibration_report
from evals.optimization.scoring import score_with_judge, validate_judgment
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_memory_coordination import context, harness

DATA = Path(__file__).resolve().parents[2] / "evals/datasets"


def test_old_artifacts_remain_readable_but_cannot_start_new_rsi():
    old = DATA / "tutor_agent50_review.jsonl"
    assert len(load_live_cases(old)) == 50
    with pytest.raises(ValueError, match="v2 semantic"):
        prepare_protocol(old)


@pytest.mark.parametrize("number,dimension", [
    (8, "retrieval_source"), (8, "retrieval_answer"), (8, "retrieval_consistency"),
    (11, "hint_direct"), (11, "hint_paraphrase"), (11, "hint_elimination"),
])
def test_v2_rejects_missing_frozen_dimension(number, dimension):
    case = next(c for c in load_live_cases(DATA / "tutor_agent50_rsi_v2.jsonl")
                if c.number == number)
    case.hard_checks = [c for c in case.hard_checks if c.path != dimension]
    with pytest.raises(ValueError, match="semantic checks"):
        case.validate_contract()


@pytest.mark.asyncio
@pytest.mark.parametrize("number,failed_dimension,response", [
    (8, "retrieval_consistency", "先圈时间，再看是否到现在。但历史中没有这条信息。"),
    (11, "hint_elimination", "A、C、D 都不符合，剩下的由你选择。"),
    (11, "hint_paraphrase", "目标词的意思就是选项 B 的完整同义表达。"),
])
async def test_false_positive_cannot_pass_when_semantic_dimension_fails(number, failed_dimension, response):
    case = next(c for c in load_live_cases(DATA / "tutor_agent50_rsi_v2.jsonl")
                if c.number == number)
    observed = {"fixture_validation": {"valid": True}, "steps": {
        "s1": {"status": "completed", "action": "converse",
               "result": {"teaching_response": {"response": response}}}}}
    class FrozenJudge:
        async def complete(self, messages, *, role):
            payload = json.loads(messages[-1]["content"])
            return json.dumps({
                "semantic": [{"id": c["id"], "passed": c["path"] != failed_dimension,
                              "reason": "测试标注，不代表真实裁判质量", "evidence": response}
                             for c in payload["semantic_checks"]],
                "decisions": [{"step_id": "s1", "required_tools_present": True,
                               "calls": [], "reason": "测试", "evidence": ""}],
            })
    scored = await score_with_judge(case, observed, {
        "execution_outcome": "completed", "automatic_passed": True,
    }, FrozenJudge())
    assert scored["score"] == 0 and not scored["task_success"]
    with pytest.raises(ValueError, match="coverage"):
        validate_judgment('{"semantic":[],"decisions":[]}', case, observed)


@pytest.mark.asyncio
async def test_retrieval_override_keeps_fixed_rules_and_async_isolation():
    original = BASE_RULES + TURN_RULES + QUIZ_RULES
    assert system_prompt(True) == original
    with use_retrieval_rules(RETRIEVAL_RULES):
        assert system_prompt(True) == original
    async def read(text):
        with use_retrieval_rules(text):
            await asyncio.sleep(0)
            assert TURN_RULES in system_prompt(True) and QUIZ_RULES in system_prompt(True)
            return system_prompt(True)
    a, b = await asyncio.gather(read("检索策略甲"), read("检索策略乙"))
    assert "检索策略甲" in a and "检索策略乙" not in a
    assert "检索策略乙" in b and "检索策略甲" not in b
    with pytest.raises(RuntimeError):
        with use_retrieval_rules("临时"):
            raise RuntimeError()
    assert system_prompt(True) == original
    with pytest.raises(ValueError):
        validate_candidate({"turn_rules": "改写澄清规则"})


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_expert_compacts_by_regeneration_and_never_truncates(harness, repair_succeeds):
    ctx = context(harness)
    ctx.max_model_calls = 5
    plan = LearningPlan(goal="诊断", steps=plan_steps())
    turns = 0
    def handler(messages, tools):
        nonlocal turns
        turns += 1
        assert "findings最多8条" in messages[0]["content"]
        if turns == 2:
            assert tools == [] and "按主题合并" in messages[-1]["content"]
            if repair_succeeds:
                return final("a", findings=["按主题合并保留全部必要结论"])
        return NativeTurn(content=json.dumps({"status": "completed",
            "findings": [f"观察{i}" for i in range(9)]}), stop_reason="stop")
    if repair_succeeds:
        result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
        assert result.findings == ["按主题合并保留全部必要结论"]
    else:
        with pytest.raises(AgentExecutionError, match="expert_findings_too_long"):
            await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert turns == 2 and ctx.model_calls == 2


def test_calibration_requires_actual_distinct_cases_and_discloses_assistant_labels():
    rows = [{"group": group, "response": f"{group} response {i}",
             "reference_passed": group in {"retrieval_correct", "hint_compliant"},
             "judge_passed": group in {"retrieval_correct", "hint_compliant"},
             "reviewer_kind": "assistant", "reviewer": "test"}
            for group in GROUPS for i in range(5)]
    assert calibration_report(rows)["passed"]
    assert not calibration_report(rows)["independent_human_gold"]
    assert calibration_report(rows[:-1])["status"] == "incomplete"
    with pytest.raises(ValueError, match="duplicate"):
        calibration_report(rows + rows[:1])
    rows[5]["judge_passed"] = True
    assert not calibration_report(rows)["passed"]
    rows[5]["disputed"] = True
    assert calibration_report(rows)["status"] == "incomplete"
