"""可选备题门槛不阻塞学习安排；必要澄清仍可跨会话恢复。"""

import json

import pytest

from core.coordinator import Coordinator
from core.llm_service import get_llm_service
from tests.test_coordinator_runtime import Model, final
from tests.test_harness_bounded_delivery import curriculum_steps
from tests.test_memory_coordination import context, harness, seed


GATE_QUESTION = "当前知识点尚不可备题，且缺基础前置。你希望先补基础，还是先由诊断确认水平？"


def planner_question(model, monkeypatch, question):
    model.install(monkeypatch)
    original = model.generate

    async def generate(prompt, **kwargs):
        response = await original(prompt, **kwargs)
        data = json.loads(response.content)
        data["needs_input"] = question
        return response.model_copy(update={"content": json.dumps(data, ensure_ascii=False)})

    monkeypatch.setattr(get_llm_service(), "generate", generate)


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledge", ["reading_skimming", "writing_paragraph"])
async def test_optional_practice_gate_falls_back_and_delivers_saved_preference(harness, monkeypatch, knowledge):
    text = "按保存偏好安排下周学习计划"
    ref = seed(harness.db, text="我喜欢先自己限时完成，再看提示", knowledge=knowledge)
    ctx = context(harness)
    harness.history.memory.propose(ctx, "preference", "我喜欢先自己限时完成，再看提示", ref)
    with harness.db:
        harness.history.memory.commit(ctx, ref)

    def handler(messages, tools):
        data = json.loads(messages[1]["content"])
        assert any("先自己限时完成" in item for item in data["constraints"])
        return final(data["task"]["step_id"], findings=["每天先自己限时完成短文，再看提示并检查。"])

    model = Model(handler, steps=curriculum_steps())
    planner_question(model, monkeypatch, GATE_QUESTION)
    result = await harness.converse("a", "plan-gate", knowledge, text)
    plan = result["learning_plan"]
    assert plan["outcome"] == "completed" and plan["needs_input"] is None
    assert plan["original_request"] == text
    assert "先自己限时完成" in plan["results"]["step-1"]["findings"][0]
    assert model.plans[0]["practice_policy"]["required"] is False
    assert "required=false" in model.plans[0]["instructions"]
    assert not harness.history.pending("a", result["execution"]["thread_id"])
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0
    trace = harness.history.trace("a", "plan-gate")["attempts"][0]["steps"]
    assert any(s["kind"] == "plan_fallback" and s.get("reason") == "nonblocking_practice_clarification"
               for s in trace)
    assert len(model.plans) == 1 and len(model.turns) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("text,question,knowledge", [
    ("安排下周学习计划", "每天可投入多久，最想改善哪类写作？", "writing_paragraph"),
    ("安排学习计划", "当前不可备题且缺前置，你每天可投入多久，是否先补基础？", "reading_skimming"),
    ("先诊断水平再安排学习计划", GATE_QUESTION, "reading_skimming"),
    ("安排学习计划并准备一道题", GATE_QUESTION, "reading_skimming"),
    ("安排学习计划", GATE_QUESTION, "vocab_basic"),
])
async def test_real_input_required_practice_and_explicit_diagnosis_still_wait(harness, monkeypatch, text, question, knowledge):
    model = Model(lambda *_: final("c"), steps=curriculum_steps())
    planner_question(model, monkeypatch, question)
    result = await harness.converse("a", "keep-question", knowledge, text)
    assert result["learning_plan"]["outcome"] == "awaiting_student"
    assert result["learning_plan"]["needs_input"] == question
    assert model.turns == []
    assert result["execution"]["pending_question_id"]
    trace = harness.history.trace("a", "keep-question")["attempts"][0]["steps"]
    assert not any(s.get("reason") == "nonblocking_practice_clarification" for s in trace)


@pytest.mark.asyncio
async def test_optional_gate_with_negated_diagnosis_does_not_force_diagnosis(harness):
    from core.coordination_budget import practice_policy
    from tests.test_harness_bounded_delivery import curriculum_plan
    text = "不需要诊断，按偏好安排学习"
    ctx = context(harness, text=text)
    ctx.knowledge_id = "reading_skimming"
    policy = practice_policy(ctx, curriculum_plan(text))
    assert Coordinator(ctx, get_llm_service()).nonblocking_practice_clarification(
        text, GATE_QUESTION, policy)
