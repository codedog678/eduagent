"""优化边界：错误归因、预算内修正、发现隔离、动作与业务评分。"""

import json
from pathlib import Path

import pytest

from core.agent_errors import AgentExecutionError
from core.coordination_models import LearningPlan, PlanDraft
from core.coordinator import Coordinator
from core.llm_service import LLMResponse, NativeTurn
from core.specialist_drafts import adapter, parse_result
from core.specialist_runtime import SpecialistRuntime
from core.tool_executor import ToolExecutor
from evals.long_task_models import load_long_task_cases
from evals.long_task_scorers import score_long_task
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_memory_coordination import call, context, harness, seed


@pytest.mark.parametrize(("payload", "code"), [
    ({"status": "completed"}, "expert_findings_missing"),
    ({"status": "needs_input"}, "expert_question_missing"),
    ({"status": "mystery"}, "expert_status_invalid"),
    ({"status": "completed", "findings": ["观察"], "task_id": "wrong"}, "expert_task_mismatch"),
    ({"status": "completed", "findings": ["观察"], "source_refs": ["message:foreign"]},
     "expert_sources_unverified"),
    ({"status": "completed", "findings": ["观察"],
      "proposed_actions": [{"knowledge_id": "vocab_basic"}]}, "expert_action_not_allowed"),
])
def test_draft_rejects_precise_error_without_raw_input(harness, payload, code):
    ctx = context(harness)
    step = LearningPlan(goal="review", steps=plan_steps()).steps[0]
    with pytest.raises(AgentExecutionError) as caught:
        parse_result(json.dumps(payload), step, set(), ctx.history, ctx.learner)
    assert caught.value.code == code
    assert all(set(item) <= {"field", "type"} for item in caught.value.details)
    assert "task_id" not in adapter("Assessment").json_schema().get("properties", {})
    assert "plan_id" not in PlanDraft.model_json_schema()["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [1, 2])
async def test_draft_repair_consumes_existing_budget_only(harness, available):
    ctx = context(harness)
    plan = LearningPlan(goal="review", steps=plan_steps())
    # Assessment还要给Curriculum一次、Tutor两次调用。
    ctx.max_model_calls = available + 3
    turns = 0
    def handler(messages, tools):
        nonlocal turns
        turns += 1
        if turns == 1:
            return NativeTurn(content='{"status":"completed"}', stop_reason="stop")
        assert tools == []
        assert json.loads(messages[-1]["content"])["error_code"] == "expert_findings_missing"
        return final("a")
    if available == 1:
        with pytest.raises(AgentExecutionError, match="expert_findings_missing"):
            await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    else:
        result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
        assert result.status == "completed"
    assert ctx.model_calls == available and turns == available and ctx.tool_calls == 0


@pytest.mark.asyncio
async def test_discovery_is_bounded_scoped_not_read_and_empty_query_stays_empty(harness):
    own = seed(harness.db, text="与查询没有共同词")
    seed(harness.db, "b", "foreign", "PRIVATE")
    seed(harness.db, identifier="other-topic", knowledge="grammar_tenses", text="OTHER")
    ctx = context(harness)
    executor = ToolExecutor(ctx)
    empty = await executor.execute(call("search_learning_history", query=""))
    assert not empty["data"]["items"] and not ctx.history_discovery_used
    discovery = await executor.execute(call("search_learning_history", query="unmatched_xyz"))
    assert discovery["data"]["discovery_only"]
    assert discovery["source_refs"] == [own] and ctx.read_refs == []
    assert "PRIVATE" not in json.dumps(discovery) and "OTHER" not in json.dumps(discovery)
    again = await executor.execute(call("search_learning_history", query="unmatched_other"))
    assert again["status"] == "empty"
    await executor.execute(call("read_learning_history", source_ref=own))
    assert ctx.read_refs == [own]


@pytest.mark.asyncio
async def test_generic_error_expansion_finds_literal_history(harness):
    ref = seed(harness.db, text="我误判了完成时，忽略动作持续到现在")
    ctx = context(harness)
    result = await ToolExecutor(ctx).execute(call("search_learning_history", query="过去时态错误"))
    assert ref in result["source_refs"] and result["data"]["query_expanded"]
    assert ctx.read_refs == []


@pytest.mark.parametrize(("constraint", "conflict"), [
    ("不能声称偏好缺失", False), ("不得说没有偏好", False),
    ("偏好缺失，需要重新提供", True), ("没有学习偏好", True),
])
def test_evidence_conflict_respects_negation(harness, constraint, conflict):
    ref = seed(harness.db, text="我喜欢短例子")
    ctx = context(harness)
    ctx.history.memory.propose(ctx, "preference", "我喜欢短例子", ref)
    with harness.db:
        ctx.history.memory.commit(ctx, ref)
    plan = LearningPlan(goal="制定计划", constraints=[constraint], steps=plan_steps())
    if conflict:
        with pytest.raises(ValueError, match="planner_evidence_conflict"):
            Coordinator(ctx, None).bind_evidence(plan)
    else:
        Coordinator(ctx, None).bind_evidence(plan)
        assert plan.evidence[0].status == "available"


@pytest.mark.asyncio
async def test_optional_action_preserves_findings_and_receipt(harness, monkeypatch):
    steps = plan_steps()[1:]
    steps[0]["depends_on"] = []
    Model(lambda *_: final("c", findings=["先限时略读三分钟，再自查主题句"], proposed_actions=[
        {"knowledge_id": "reading_skimming", "difficulty": .3}]), steps=steps).install(monkeypatch)
    result = await harness.converse("a", "optional", "reading_skimming", "制定一个略读训练计划")
    plan = result["learning_plan"]
    assert plan["outcome"] == "completed" and plan["results"]["c"]["status"] == "completed"
    assert plan["results"]["c"]["findings"] == ["先限时略读三分钟，再自查主题句"]
    assert plan["action_receipts"]["c"]["error_code"] == "practice_prerequisites_missing"
    assert "练习未生成" in plan["results"]["c"]["uncertainty"]
    assert not harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0]


@pytest.mark.asyncio
async def test_required_action_failure_retains_findings_and_missing_delivery(harness, monkeypatch):
    steps = plan_steps()[1:]
    steps[0]["depends_on"] = []
    Model(lambda *_: final("c", findings=["有效安排"], proposed_actions=[
        {"knowledge_id": "reading_skimming"}]), steps=steps).install(monkeypatch)
    result = await harness.converse("a", "required", "reading_skimming", "安排略读并准备一道题")
    plan = result["learning_plan"]
    assert plan["outcome"] == "partial" and plan["results"]["c"]["findings"] == ["有效安排"]
    assert "required_practice_missing" in plan["checks"]


def test_l02_completed_partial_is_not_business_success():
    dataset = Path(__file__).resolve().parents[1] / "evals/datasets/harness_long_tasks_v1.jsonl"
    case = load_long_task_cases(dataset)[1]
    observed = {"stages": {s.id: {"status": "completed"} for s in case.stages},
                "final": {"plans": [{"status": "completed", "outcome": "partial"}]}}
    score = score_long_task(case, observed)
    assert not score["task_success"]
    assert not next(a["passed"] for a in score["assertions"] if a["id"] == "business_plan_resolved")


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["[]", "null"])
async def test_non_object_plan_output_falls_back_without_crash(harness, content):
    ctx = context(harness, text="安排复习")
    model = Model(lambda *_: final("a"), ctx)
    async def generate(**kwargs):
        ctx.consume("model")
        return LLMResponse(content=content, model="mock")
    model.generate = generate
    plan = await Coordinator(ctx, model).create_plan(ctx.input_text)
    assert plan.original_request == ctx.input_text
    assert any(step["kind"] == "plan_fallback" for step in ctx.steps)
