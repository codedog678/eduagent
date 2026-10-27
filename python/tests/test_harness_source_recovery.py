"""普通计划简化、候选来源隔离和原预算内草稿修复的行为回归。"""

import json

import pytest

from config.settings import settings
from core.agent_errors import AgentExecutionError
from core.coordination_models import LearningPlan, PlanStep
from core.coordinator import Coordinator
from core.llm_service import get_llm_service
from core.planning_policy import assessment_requested, simplify_initial_plan
from core.specialist_runtime import SpecialistRuntime
from core.tool_executor import ToolExecutor
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_harness_bounded_delivery import curriculum_plan
from tests.test_harness_plan_gate import planner_question
from tests.test_memory_coordination import call, context, harness, seed


@pytest.mark.asyncio
async def test_ordinary_plan_keeps_clarification_and_resumes_without_diagnosis(harness, monkeypatch):
    text = "安排下周写作学习计划，缺每天时长和改善方向，请先问我"
    roles = []
    def handler(messages, tools):
        data = json.loads(messages[1]["content"])
        roles.append(data["task"]["step_id"])
        assert data["student_inputs"] == ["每天二十分钟，主题句和支撑句"]
        return final(data["task"]["step_id"], findings=["每天二十分钟，练主题句和支撑句。"])
    model = Model(handler)
    planner_question(model, monkeypatch, "每天可投入多久，最想改善哪类写作？")
    first = await harness.converse("a", "simple-start", "writing_paragraph", text)
    assert first["learning_plan"]["outcome"] == "awaiting_student" and model.turns == []
    assert [s["agent"] for s in first["learning_plan"]["steps"]] == ["Curriculum", "Tutor"]
    pending = first["execution"]["pending_question_id"]
    second = await harness.converse("a", "simple-resume", "writing_paragraph",
                                    "每天二十分钟，主题句和支撑句", session_id="next-session")
    assert second["learning_plan"]["plan_id"] == first["learning_plan"]["plan_id"]
    assert second["execution"]["answered_question_id"] == pending
    assert second["learning_plan"]["outcome"] == "completed"
    assert roles == ["c"] and len(model.turns) == 2 and len(model.plans) == 1
    assert not harness.history.pending("a", second["execution"]["thread_id"])
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0
    steps = harness.history.trace("a", "simple-start")["attempts"][0]["steps"]
    assert any(s["kind"] == "plan_simplified" and s.get("reason") == "unnecessary_assessment"
               for s in steps)


@pytest.mark.asyncio
async def test_ordinary_plan_with_preference_history_only_uses_curriculum(harness, monkeypatch):
    seed(harness.db, text="我喜欢短例子")
    roles = []
    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        roles.append(task)
        return final(task)
    model = Model(handler)
    model.install(monkeypatch)
    result = await harness.converse("a", "simple-history", "vocab_basic", "制定学习计划")
    assert result["learning_plan"]["outcome"] == "completed" and roles == ["c"]
    assert model.plans[0]["assessment_policy"] == {"dedicated_assessment_required": False}


@pytest.mark.parametrize("text,required", [
    ("诊断后安排学习计划", True),
    ("结合过去错误安排学习计划", True),
    ("评估我的水平，再安排", True),
    ("根据上次作答制定计划", True),
    ("不需要诊断，只安排复习", False),
    ("制定学习计划", False),
])
def test_assessment_policy_comes_from_student_request(text, required):
    assert bool(assessment_requested(text)) is required


def test_simplification_reconnects_dependencies_and_preserves_question(harness):
    ctx = context(harness)
    plan = LearningPlan(goal="安排", needs_input="每天多久？", steps=[
        PlanStep(step_id="a1", agent="Assessment", objective="诊断"),
        PlanStep(step_id="c", agent="Curriculum", objective="安排", depends_on=["a1"]),
        PlanStep(step_id="a2", agent="Assessment", objective="再诊断", depends_on=["c"]),
        PlanStep(step_id="t", agent="Tutor", objective="表达", depends_on=["a2"]),
    ])
    result = simplify_initial_plan(ctx, plan, False)
    assert [s.step_id for s in result.steps] == ["c", "t"]
    assert result.steps[0].depends_on == [] and result.steps[1].depends_on == ["c"]
    assert result.needs_input == "每天多久？"
    LearningPlan.model_validate(result.model_dump())


def test_restoring_existing_failed_assessment_does_not_simplify_history(harness):
    ctx = context(harness, text="继续原计划")
    plan = LearningPlan(goal="安排", original_request="安排", steps=plan_steps())
    plan.steps[0].status = "failed"
    plan.status = plan.outcome = "awaiting_student"
    restored = Coordinator(ctx, get_llm_service()).restore_plan(plan.model_dump(), ctx.input_text)
    assert restored.steps[0].agent == "Assessment" and restored.steps[0].status == "failed"
    assert len(restored.steps) == 3
    assert len(simplify_initial_plan(ctx, restored, False).steps) == 3


@pytest.mark.asyncio
async def test_unread_candidate_is_repaired_without_quoting_old_draft_or_promoting_evidence(harness):
    ref = seed(harness.db, text="历史词汇自述")
    ctx = context(harness, text="每天二十分钟，安排复习")
    plan = curriculum_plan(ctx.input_text)
    calls = []
    def handler(messages, tools):
        calls.append(messages)
        data = json.loads(messages[1]["content"])
        assert data["history_candidates"]["citable_without_read"] is False
        assert data["history_candidates"]["items"][0]["citation_status"] == "unread_candidate"
        assert data["verified_source_refs"] == []
        if len(calls) == 1:
            return final("c", source_refs=[ref], findings=["PRIVATE-INVALID-SOURCE-DRAFT"])
        assert tools == [] and "PRIVATE-INVALID-SOURCE-DRAFT" not in json.dumps(messages)
        correction = json.loads(messages[-1]["content"])
        assert correction["verified_source_refs"] == []
        assert "不能仅删除引用" in correction["source_correction"]
        return final("c", source_refs=[], findings=["每天二十分钟基础复习，这是通用安排。"],
                     uncertainty="没有已读历史，不能诊断具体薄弱点。")
    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert result.status == "completed" and result.source_refs == []
    assert "通用安排" in result.findings[0]
    assert ctx.model_calls == 2 and ctx.tool_calls == 0 and ctx.read_refs == []
    assert any(s["kind"] == "expert_draft_rejected" for s in ctx.steps)
    assert sum(s["kind"] == "expert_draft_repair" and s.get("reason") == "unread_source"
               for s in ctx.steps) == 1
    assert "PRIVATE-INVALID-SOURCE-DRAFT" not in json.dumps(ctx.steps)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["foreign", "missing", "nonhistory", "mixed", "expired"])
async def test_unavailable_or_forged_source_does_not_receive_repair(harness, kind):
    ctx = context(harness, text="安排复习")
    plan = curriculum_plan(ctx.input_text)
    known = set()
    if kind == "foreign":
        refs = [seed(harness.db, "b", "foreign", "PRIVATE")]
    elif kind == "nonhistory":
        refs = ["knowledge:vocab_basic"]
    elif kind == "mixed":
        refs = [seed(harness.db), "message:missing-private"]
    elif kind == "expired":
        ref = seed(harness.db)
        known.add(ref)
        harness.db.execute("DELETE FROM conversation_messages WHERE id='one'")
        refs = [ref]
    else:
        refs = ["message:missing-private"]
    model = Model(lambda *_: final("c", source_refs=refs), ctx)
    with pytest.raises(AgentExecutionError):
        await SpecialistRuntime(ctx, model).native(
            plan.steps[0], plan, ToolExecutor(ctx), [], known)
    assert ctx.model_calls == 1 and not any(s["kind"] == "expert_draft_repair" for s in ctx.steps)
    assert not any(ref in json.dumps(ctx.steps) for ref in refs)


@pytest.mark.asyncio
async def test_second_unread_source_failure_is_retained_without_third_request(harness):
    ref = seed(harness.db)
    ctx = context(harness, text="安排复习")
    plan = curriculum_plan(ctx.input_text)
    with pytest.raises(AgentExecutionError, match="expert_sources_unverified"):
        await SpecialistRuntime(ctx, Model(lambda *_: final("c", source_refs=[ref]), ctx)).run(
            plan.steps[0], plan)
    assert ctx.model_calls == 2 and ctx.tool_calls == 0
    assert sum(s["kind"] == "expert_draft_rejected" for s in ctx.steps) == 2
    assert sum(s["kind"] == "expert_draft_repair" for s in ctx.steps) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["parent", "role"])
async def test_unread_source_with_no_repair_budget_sends_one_request(harness, monkeypatch, limit):
    ref = seed(harness.db)
    ctx = context(harness, text="安排复习")
    if limit == "parent":
        ctx.max_model_calls = 1
    else:
        monkeypatch.setattr(settings, "specialist_max_model_calls", 1)
    plan = curriculum_plan(ctx.input_text)
    with pytest.raises(AgentExecutionError, match="expert_sources_unverified"):
        await SpecialistRuntime(ctx, Model(lambda *_: final("c", source_refs=[ref]), ctx)).native(
            plan.steps[0], plan, ToolExecutor(ctx), [], set())
    assert ctx.model_calls == 1
    assert not any(s["kind"] == "expert_draft_repair" for s in ctx.steps)


@pytest.mark.asyncio
async def test_schema_then_unread_source_share_one_repair_opportunity(harness):
    ref = seed(harness.db)
    ctx = context(harness, text="安排复习")
    plan = curriculum_plan(ctx.input_text)
    count = 0
    def handler(*args):
        nonlocal count
        count += 1
        return final("c", extra=True) if count == 1 else final("c", source_refs=[ref])
    with pytest.raises(AgentExecutionError, match="expert_sources_unverified"):
        await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert ctx.model_calls == 2
    assert sum(s["kind"] == "expert_draft_repair" for s in ctx.steps) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["search_only", "truncated_read"])
async def test_search_or_truncated_read_does_not_promote_candidate_to_evidence(harness, mode):
    from core.llm_service import NativeTurn
    ref = seed(harness.db, text="词汇 mistake " * 100)
    ctx = context(harness, text="诊断词汇并安排复习")
    plan = curriculum_plan(ctx.input_text)
    count = 0
    def handler(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            tool = (call("search_learning_history", query="mistake") if mode == "search_only"
                    else call("read_learning_history", source_ref=ref, limit=100))
            return NativeTurn(stop_reason="tool_calls", tool_calls=[tool])
        if count == 2:
            return final("c", source_refs=[ref])
        assert tools == [] and json.loads(messages[-1]["content"])["verified_source_refs"] == []
        return final("c", source_refs=[], uncertainty="未完成原文读取，不能诊断，只给通用安排。")
    result = await SpecialistRuntime(ctx, Model(handler, ctx)).native(
        plan.steps[0], plan, ToolExecutor(ctx), [], set())
    assert result.source_refs == [] and not ctx.read_evidence
    assert ctx.model_calls == 3 and ctx.tool_calls == 1
    rejection = [s for s in ctx.steps if s["kind"] == "expert_draft_rejected"]
    assert rejection[0]["errors"] == [{"field": "source_refs", "type": "unread_source"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_source_repair_commits_only_valid_result_or_keeps_failed_plan(harness, monkeypatch, repair_succeeds):
    ref = seed(harness.db, text="历史词汇自述")
    monkeypatch.setattr(settings, "coordinator_max_replans", 0)
    count = 0
    def handler(messages, tools):
        nonlocal count
        count += 1
        if count == 1 or not repair_succeeds:
            return final("c", source_refs=[ref], findings=["PRIVATE-REJECTED-DRAFT"])
        return final("c", source_refs=[], findings=["先做十五分钟基础词汇复习，这是通用安排。"],
                     uncertainty="没有已读历史，不能诊断具体薄弱点。")
    model = Model(handler)
    model.install(monkeypatch)
    result = await harness.converse("a", "commit-source-repair", "vocab_basic", "安排基础词汇复习")
    plan = result["learning_plan"]
    assert plan["outcome"] == ("completed" if repair_succeeds else "partial")
    assert plan["results"]["c"]["status"] == ("completed" if repair_succeeds else "failed")
    if not repair_succeeds:
        assert plan["results"]["c"]["error_code"] == "expert_sources_unverified"
        assert plan["steps"][0]["status"] == "failed"
    assert "PRIVATE-REJECTED-DRAFT" not in json.dumps(result)
    trace = harness.history.trace("a", "commit-source-repair")["attempts"][0]["steps"]
    assert sum(s["kind"] == "expert_draft_repair" for s in trace) == 1
    assert sum(s["kind"] == "expert_draft_rejected" for s in trace) == (1 if repair_succeeds else 2)
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0
