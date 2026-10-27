"""原预算内补交付与学生目标授权的业务回归。"""

import json

import pytest
from fastapi import HTTPException

from config.settings import settings
from core.coordination_budget import practice_policy
from core.coordination_models import LearningPlan
from core.llm_service import NativeTurn, get_llm_service
from core.run_context import active_run
from core.specialist_runtime import SpecialistRuntime
from core.tool_executor import ToolExecutor
from core.tutor_runtime import TutorRuntime
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_memory_coordination import context, harness


def curriculum_plan(text):
    steps = plan_steps()[1:]
    steps[0]["depends_on"] = []
    return LearningPlan(goal=text, original_request=text, steps=steps)


def curriculum_steps():
    return [{key: value for key, value in step.model_dump().items()
             if key not in {"status", "source_refs"}} for step in curriculum_plan("安排").steps]


@pytest.mark.parametrize("text", [
    "制定复习计划并准备一道最优先知识点的练习题",
    "安排复习，先练基础前置，准备一道题",
])
def test_priority_request_authorizes_eligible_ancestor_without_mastery_change(harness, text):
    ctx = context(harness, text=text)
    ctx.knowledge_id = "reading_skimming"
    policy = practice_policy(ctx, curriculum_plan(text))
    assert policy["required"] and policy["allow_prerequisite_selection"]
    assert policy["allowed_knowledge_ids"] == ["vocab_basic"]
    assert ctx.model_state == {} and ctx.profile_state == {}


@pytest.mark.parametrize("text", [
    "制定写作强化计划",
    "只练当前知识点，准备一道题，不要切换到基础前置",
    "不要选择最优先知识点，安排目标复习",
])
def test_default_and_explicit_lock_do_not_authorize_prerequisite(harness, text):
    ctx = context(harness, text=text)
    ctx.knowledge_id = "writing_paragraph"
    policy = practice_policy(ctx, curriculum_plan(text))
    assert not policy["allow_prerequisite_selection"]
    assert policy["authorized_knowledge_ids"] == ["writing_paragraph"]
    assert policy["allowed_knowledge_ids"] == []


def test_model_goal_does_not_create_user_selection_permission(harness):
    ctx = context(harness, text="安排写作复习")
    ctx.knowledge_id = "writing_paragraph"
    plan = LearningPlan(goal="准备一道最优先知识点的题，先练基础词汇", steps=plan_steps())
    policy = practice_policy(ctx, plan)
    assert not policy["required"] and not policy["allow_prerequisite_selection"]
    assert policy["authorized_knowledge_ids"] == ["writing_paragraph"]
    plan.student_inputs = ["我选择先练基础前置，请准备一道题"]
    assert practice_policy(ctx, plan)["allowed_knowledge_ids"] == ["vocab_basic"]


@pytest.mark.asyncio
async def test_required_missing_action_is_repaired_with_existing_permission(harness):
    text = "安排复习并准备一道最优先知识点的练习题"
    ctx = context(harness, text=text)
    ctx.knowledge_id = "grammar_tenses"
    plan = curriculum_plan(text)
    calls = []
    def handler(messages, tools):
        calls.append(messages)
        if len(calls) == 1:
            assert json.loads(messages[1]["content"])["practice_policy"]["allowed_knowledge_ids"] == ["vocab_basic"]
            return final("c", findings=["每天十五分钟，先看短例子再练习。"])
        assert tools == [] and "已有选择授权" in messages[-1]["content"]
        return final("c", findings=["每天十五分钟，先看短例子再练习；先练基础词汇以满足时态前置。"],
                     proposed_actions=[{"knowledge_id": "vocab_basic"}])
    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert result.proposed_actions[0].knowledge_id == "vocab_basic"
    assert ctx.model_calls == 2 and ctx.tool_calls == 0
    assert sum(s["kind"] == "expert_draft_repair" for s in ctx.steps) == 1


@pytest.mark.asyncio
async def test_missing_action_with_no_extra_budget_keeps_valid_schedule(harness):
    ctx = context(harness, text="安排复习并准备一道题")
    plan = curriculum_plan(ctx.input_text)
    ctx.model_calls = 5
    # 不申请新额度；调用native复现最后一次结论，父运行还会做其余可行性检查。
    ctx.max_model_calls = 6
    result = await SpecialistRuntime(ctx, Model(lambda *_: final("c"), ctx)).native(
        plan.steps[0], plan, ToolExecutor(ctx), [], set())
    assert result.status == "completed" and result.proposed_actions == []
    assert ctx.model_calls == 6 and not any(s["kind"] == "expert_draft_repair" for s in ctx.steps)


@pytest.mark.asyncio
async def test_optional_unauthorized_action_does_not_prepare_or_block_schedule(harness, monkeypatch):
    model = Model(lambda *_: final("c", findings=["每天二十分钟练主题句与支撑句。"],
                                   proposed_actions=[{"knowledge_id": "vocab_basic"}]),
                  steps=curriculum_steps())
    model.install(monkeypatch)
    result = await harness.converse("a", "locked-write", "writing_paragraph", "安排写作强化计划")
    plan = result["learning_plan"]
    assert plan["outcome"] == "completed"
    assert plan["results"]["c"]["findings"] == ["每天二十分钟练主题句与支撑句。"]
    assert plan["action_receipts"]["c"]["error_code"] == "practice_target_not_authorized"
    assert plan["results"]["c"]["proposed_actions"] == []
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0
    assert "prepared_practice" not in result


@pytest.mark.asyncio
async def test_required_unauthorized_action_keeps_failure_and_schedule(harness, monkeypatch):
    Model(lambda *_: final("c", findings=["七天都先看时态例句。"],
                           proposed_actions=[{"knowledge_id": "vocab_basic"}]),
          steps=curriculum_steps()).install(monkeypatch)
    result = await harness.converse("a", "required-lock", "grammar_tenses",
                                    "只练当前知识点，安排复习并准备一道题")
    plan = result["learning_plan"]
    assert plan["outcome"] == "partial" and plan["steps"][0]["status"] == "failed"
    assert plan["action_receipts"]["c"]["error_code"] == "practice_target_not_authorized"
    assert "七天都先看时态例句" in result["teaching_response"]["response"]
    assert "required_practice_missing" in plan["checks"]
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0


class TruncatedTutor(Model):
    def __init__(self, ctx=None, succeeds=True):
        super().__init__(None, ctx, steps=curriculum_steps())
        self.succeeds, self.tutor_turns, self.output_limits = succeeds, [], []

    async def tool_turn(self, messages, tools, max_tokens):
        self.consume()
        if messages[0]["content"].startswith("你是教育系统的Curriculum专家"):
            return final("c", proposed_actions=[{"knowledge_id": "vocab_basic"}])
        self.tutor_turns.append(json.loads(json.dumps(messages)))
        self.output_limits.append(max_tokens)
        if len(self.tutor_turns) == 1 or not self.succeeds:
            return NativeTurn(content="PRIVATE-TRUNCATED-DRAFT", reasoning_content="PRIVATE-REASONING",
                              stop_reason="length")
        assert tools == []
        assert "PRIVATE-TRUNCATED-DRAFT" not in json.dumps(messages)
        assert "PRIVATE-REASONING" not in json.dumps(messages)
        return NativeTurn(content="先看短例子，再做已准备的基础词汇题，最后检查搭配。", stop_reason="stop")


@pytest.mark.asyncio
async def test_truncated_reply_regenerates_once_and_commits_practice_atomically(harness, monkeypatch):
    model = TruncatedTutor()
    model.install(monkeypatch)
    async def question(*args):
        active_run.get().consume("model")
        return {"question": "Which means abundant?", "options": ["plenty", "rare"],
                "correct_index": 0, "explanation": "private"}
    monkeypatch.setattr(get_llm_service(), "generate_question", question)
    result = await harness.converse("a", "bounded-success", "vocab_basic", "安排复习并准备一道题")
    assert len(model.tutor_turns) == 2 and model.output_limits == [800, 800]
    assert result["learning_plan"]["outcome"] == "awaiting_student"
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 1
    trace = harness.history.trace("a", "bounded-success")["attempts"][0]["steps"]
    assert sum(s["kind"] == "budget_used" and s.get("resource") == "model" for s in trace) == 5
    assert "PRIVATE-" not in json.dumps(result)


@pytest.mark.asyncio
async def test_second_truncation_rolls_back_plan_practice_and_messages(harness, monkeypatch):
    model = TruncatedTutor(succeeds=False)
    model.install(monkeypatch)
    with pytest.raises(HTTPException):
        await harness.converse("a", "bounded-failure", "vocab_basic", "安排复习并准备一道题")
    assert len(model.tutor_turns) == 2
    for table in ("learning_plans", "quizzes", "conversation_messages"):
        assert harness.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    trace = harness.history.trace("a", "bounded-failure")["attempts"][0]
    assert trace["stop_reason"] == "output_token_limit"
    assert "PRIVATE-" not in json.dumps(trace)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["parent", "role"])
async def test_truncation_without_budget_does_not_send_extra_request(harness, monkeypatch, limit):
    ctx = context(harness)
    if limit == "parent":
        ctx.max_model_calls = 1
    else:
        monkeypatch.setattr(settings, "tutor_max_model_calls", 1)
    model = TruncatedTutor(ctx)
    from core.run_context import RunExhausted
    with pytest.raises(RunExhausted, match="output_token_limit"):
        await TutorRuntime(ctx, model, ctx.knowledge_graph).run("复习")
    assert len(model.tutor_turns) == 1 and ctx.model_calls == 1
