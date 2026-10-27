"""交付与前置路径回归：动作失败保留安排，来源失败不能借机进入回复。"""

import json

import pytest

from core.agent_errors import AgentExecutionError
from core.coordination_models import AgentResult, LearningPlan
from core.coordinator import Coordinator
from core.knowledge_graph import KnowledgeGraph, KnowledgeNode
from core.specialist_drafts import parse_result
from core.tool_executor import ToolExecutor
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_memory_coordination import context, harness, seed


@pytest.mark.asyncio
async def test_failed_required_practice_delivers_all_valid_schedule(harness, monkeypatch):
    steps = plan_steps()[1:]
    steps[0]["depends_on"] = []
    schedule = [f"第{i}天：先看短例子，再练习，总计十五分钟。" for i in range(1, 8)]
    Model(lambda *_: final("c", findings=schedule, proposed_actions=[
        {"knowledge_id": "reading_skimming"}]), steps=steps).install(monkeypatch)
    result = await harness.converse("a", "delivery", "reading_skimming", "安排一周复习并准备一道题")
    plan, response = result["learning_plan"], result["teaching_response"]["response"]
    assert all(item in response for item in schedule)
    assert plan["results"]["c"]["status"] == "failed" and plan["outcome"] == "partial"
    assert plan["action_receipts"]["c"]["error_code"] == "practice_prerequisites_missing"
    assert "没有成功准备" in response and "required_practice_missing" in plan["checks"]
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0


def test_partial_cannot_publish_failed_draft_findings(harness):
    ctx = context(harness)
    plan = LearningPlan(goal="安排", steps=plan_steps(), results={
        "a": AgentResult(task_id="a", status="failed", error_code="expert_sources_unverified",
                         findings=["未校验的诊断不得交付"])})
    plan.steps[0].status = "failed"
    response = Coordinator(ctx, None).partial_reply(plan, "source_failure")
    assert "未校验的诊断不得交付" not in response.response
    assert plan.results["a"].findings and plan.steps[0].status == "failed"


def test_late_findings_keep_verified_citation(harness):
    ctx = context(harness)
    ref = seed(harness.db)
    ctx.source_refs = [ref]
    plan = LearningPlan(goal="安排", steps=plan_steps(), results={
        "a": AgentResult(task_id="a", status="completed", source_refs=[ref],
                         findings=["观察"] * 4 + [f"第七天自查，依据 {ref}"])})
    plan.steps[0].status = "completed"
    reply = Coordinator(ctx, None).partial_reply(plan, "partial")
    assert "第七天自查" in reply.response and ctx.cited_refs == [ref]


def test_nested_prerequisites_expose_only_actual_eligible_candidates(harness):
    ctx = context(harness)
    ctx.model_state = {"mastery": .1}
    ctx.profile_state = {"knowledge_states": [{"knowledge_id": "base", "mastery": .1}]}
    graph = KnowledgeGraph()
    for node in (KnowledgeNode(id="base", name="基础"),
                 KnowledgeNode(id="middle", name="中间", prerequisites=["base"]),
                 KnowledgeNode(id="target", name="目标", prerequisites=["middle"])):
        graph.add_node(node)
    executor = ToolExecutor(ctx, graph)
    snapshot = executor.knowledge_context("target")
    by_id = {item["knowledge_id"]: item for item in snapshot["prerequisite_context"]}
    assert not snapshot["practice_allowed"] and not by_id["middle"]["practice_allowed"]
    assert by_id["base"]["practice_allowed"] and not snapshot["prerequisite_context_truncated"]
    assert ctx.model_state["mastery"] == .1
    ctx.profile_state["knowledge_states"][0]["mastery"] = .6
    snapshot = executor.knowledge_context("target")
    assert snapshot["prerequisite_context"][0]["practice_allowed"]
    assert not snapshot["practice_allowed"]


@pytest.mark.asyncio
async def test_empty_history_planning_guidance_does_not_fake_sources(harness):
    ctx = context(harness, text="安排一次基础复习并准备一道题")
    model = Model(lambda *_: final("c"), ctx, steps=[
        {"step_id": "c", "agent": "Curriculum", "objective": "基础安排"},
        {"step_id": "t", "agent": "Tutor", "objective": "交付", "depends_on": ["c"]}])
    plan = await Coordinator(ctx, model).create_plan(ctx.input_text)
    assert model.plans[0]["facts"]["history_availability"]["items"] == []
    assert "直接安排Curriculum→Tutor" in model.plans[0]["instructions"]
    assert "限定目标知识点时不得静默替换" in model.plans[0]["instructions"]
    assert [step.agent for step in plan.steps] == ["Curriculum", "Tutor"]
    assert all(slot.status == "missing" for slot in plan.evidence)


@pytest.mark.parametrize(("kind", "expected"), [
    ("snapshot", "non_history_reference"),
    ("unread", "unread_source"),
    ("foreign", "unavailable_source"),
])
def test_invalid_source_categories_exclude_original_values(harness, kind, expected):
    ctx = context(harness)
    ref = ("knowledge_state:PRIVATE-SNAPSHOT" if kind == "snapshot" else
           seed(harness.db, learner="b", identifier="PRIVATE-FOREIGN") if kind == "foreign" else
           seed(harness.db, identifier="PRIVATE-UNREAD"))
    step = LearningPlan(goal="安排", steps=plan_steps()).steps[0]
    with pytest.raises(AgentExecutionError) as caught:
        parse_result(json.dumps({"status": "completed", "findings": ["观察"], "source_refs": [ref]}),
                     step, set(), ctx.history, ctx.learner)
    assert caught.value.code == "expert_sources_unverified"
    assert caught.value.details == [{"field": "source_refs", "type": expected}]
    assert ref not in json.dumps(caught.value.details)
