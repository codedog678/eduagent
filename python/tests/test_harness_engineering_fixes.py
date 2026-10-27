"""长任务工程缺陷回归；全部采用脚本模型，不访问远程供应商。"""

import json

import httpx
import pytest
from fastapi import HTTPException

from config.settings import settings
from core.coordination_models import LearningPlan
from core.coordinator import Coordinator
from core.llm_service import LLMResponse, NativeTurn, get_llm_service
from core.specialist_runtime import SpecialistRuntime
from tests.test_coordinator_runtime import Model, final, plan_steps
from tests.test_memory_coordination import call, context, harness, seed


def steps_for(harness, learner, request):
    return harness.history.trace(learner, request)["attempts"][-1]["steps"]


@pytest.mark.asyncio
async def test_last_expert_request_closes_tools_and_completes_chain(harness, monkeypatch):
    count = 0

    def handler(messages, tools):
        nonlocal count
        count += 1
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        if count <= 2:
            tool = call("get_knowledge_context")
            tool.id = f"context-{count}"
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                tool,
            ])
        if count == 3:
            assert tools == []
        return final(task)

    model = Model(handler)
    model.install(monkeypatch)
    result = await harness.converse("a", "final-budget", "vocab_basic", "诊断后安排复习")
    assert result["learning_plan"]["outcome"] == "completed"
    trace = steps_for(harness, "a", "final-budget")
    used = [step for step in trace if step["kind"] == "budget_used" and step["resource"] == "model"]
    assert len(used) == 6
    allocation = [step for step in trace if step["kind"] == "agent_budget_allocated"]
    assert allocation[0]["model_calls_available"] == 3
    assert allocation[1]["model_calls_available"] >= 1
    assert len(model.plans) == 1


@pytest.mark.asyncio
async def test_tool_overflow_returns_budget_feedback_without_execution(harness):
    ctx = context(harness)
    plan = LearningPlan(goal="review", steps=plan_steps())
    observed = []

    def handler(messages, tools):
        observed.append(messages)
        if len(observed) == 1:
            calls = [
                call("get_knowledge_context"),
                call("get_learner_profile"),
                call("search_learning_history", query="unknown"),
                call("read_learning_history", source_ref="message:unknown"),
                call("get_knowledge_context"),
            ]
            for index, item in enumerate(calls):
                item.id = f"read-{index}"
            return NativeTurn(stop_reason="tool_calls", tool_calls=calls)
        assert tools == []
        feedback = [json.loads(item["content"]) for item in messages if item["role"] == "tool"]
        assert feedback[-1]["status"] == "exhausted"
        assert feedback[-1]["error_code"] == "budget_exhausted"
        return final("a", uncertainty="没有足够来源，保守诊断")

    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert result.status == "completed"
    assert ctx.tool_calls == 4 and ctx.model_calls == 2
    assert len([step for step in ctx.steps if step["kind"] == "tool_skipped"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["budget", "schema"])
async def test_delegate_failure_code_reaches_plan_and_trace(harness, monkeypatch, kind):
    monkeypatch.setattr(settings, "coordinator_max_replans", 0)
    count = 0

    def handler(messages, tools):
        nonlocal count
        count += 1
        if kind == "schema":
            return NativeTurn(content='{"task_id":"a","status":"completed","extra":"private"}',
                              stop_reason="stop")
        tool = call("get_knowledge_context")
        tool.id = f"context-{count}"
        return NativeTurn(stop_reason="tool_calls", tool_calls=[tool])

    model = Model(handler)
    model.install(monkeypatch)
    result = await harness.converse("a", f"failure-{kind}", "vocab_basic", "诊断后安排复习")
    expected = "budget_exhausted" if kind == "budget" else "expert_schema_invalid"
    assert result["learning_plan"]["results"]["a"]["error_code"] == expected
    trace = steps_for(harness, "a", f"failure-{kind}")
    delegate = next(step for step in trace if step.get("tool") == "delegate_assessment"
                    and step["kind"] == "after_tool")
    assert delegate["error_code"] == expected
    failed = next(step for step in trace if step["kind"] == "plan_step_failed")
    assert failed["reason"] == expected
    assert "private" not in json.dumps(trace)


@pytest.mark.asyncio
async def test_chain_rejected_before_any_expert_when_delegates_exceed_tool_budget(harness):
    ctx = context(harness, text="诊断后安排复习")
    ctx.max_tool_calls = settings.coordinator_tutor_tool_reserve + 2
    model = Model(lambda *_: final("a"), ctx)
    result = await Coordinator(ctx, model).run(ctx.input_text)
    assert result["learning_plan"]["outcome"] == "partial"
    assert model.turns == []
    assert ctx.tool_calls == 0 and ctx.model_calls == 1
    assert "plan_execution_budget" in result["learning_plan"]["checks"]


@pytest.mark.asyncio
async def test_one_request_curriculum_uses_upstream_when_preparation_budget_reserved(harness, monkeypatch):
    count = 0

    def handler(messages, tools):
        nonlocal count
        count += 1
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        if task == "a" and count < 3:
            tool = call("get_knowledge_context")
            tool.id = f"context-{count}"
            return NativeTurn(stop_reason="tool_calls", tool_calls=[tool])
        if task == "c":
            assert tools == []
            assert json.loads(messages[1]["content"])["previous_results"][0]["task_id"] == "a"
            return final("c", proposed_actions=[{"knowledge_id": "vocab_basic", "difficulty": .5}])
        return final(task)

    model = Model(handler)
    model.install(monkeypatch)
    # 题目生成实际消耗一次父模型预算，确保不是模拟器漏计导致通过。
    async def generate_question(*args, **kwargs):
        model.consume()
        return {"question": "Choose a basic word", "options": ["cat", "car"],
                "correct_index": 0, "explanation": "private"}

    monkeypatch.setattr(get_llm_service(), "generate_question", generate_question)
    result = await harness.converse(
        "a", "with-practice", "vocab_basic", "诊断后安排复习并准备一道练习题")
    assert result["learning_plan"]["outcome"] == "awaiting_student"
    assert result["prepared_practice"]["quiz_id"]
    trace = steps_for(harness, "a", "with-practice")
    allocation = [step for step in trace if step["kind"] == "agent_budget_allocated"]
    assert [step["model_calls_available"] for step in allocation] == [3, 1]
    used = [step for step in trace if step["kind"] == "budget_used" and step["resource"] == "model"]
    assert len(used) == 7
    assert "correct_index" not in json.dumps(result)


@pytest.mark.asyncio
async def test_planner_clarification_resumes_same_plan_in_new_session(harness, monkeypatch):
    model = Model(lambda messages, tools: final(
        json.loads(messages[1]["content"])["task"]["step_id"]))
    model.install(monkeypatch)
    original = model.generate

    async def generate(prompt, **kwargs):
        response = await original(prompt, **kwargs)
        data = json.loads(response.content)
        data["needs_input"] = "每天可投入多久，最想改善哪类写作？"
        return response.model_copy(update={"content": json.dumps(data)})

    monkeypatch.setattr(get_llm_service(), "generate", generate)
    first = await harness.converse("a", "clarify", "vocab_basic", "安排下周学习计划")
    assert first["learning_plan"]["outcome"] == "awaiting_student"
    assert model.turns == []
    pending = first["execution"]["pending_question_id"]
    resumed = await harness.converse(
        "a", "clarify-resume", "vocab_basic", "每天20分钟，段落写作", session_id="new-session")
    assert resumed["learning_plan"]["plan_id"] == first["learning_plan"]["plan_id"]
    assert resumed["learning_plan"]["outcome"] == "completed"
    assert resumed["execution"]["answered_question_id"] == pending
    assert resumed["learning_plan"]["student_inputs"] == ["每天20分钟，段落写作"]
    assert len(model.plans) == 1
    assert not harness.history.pending("a", resumed["execution"]["thread_id"])


@pytest.mark.asyncio
async def test_pending_without_plan_routes_to_tutor_even_for_explicit_task(harness, monkeypatch):
    service = get_llm_service()
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    count = 0

    async def turn(messages, tools, max_tokens):
        nonlocal count
        count += 1
        if count == 1:
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("ask_student", question="请给出你想看的原题")])
        facts = json.loads(messages[1]["content"].split("\n", 1)[1])
        assert facts["pending_question"]["question"] == "请给出你想看的原题"
        return NativeTurn(content="收到原题，我们继续。", stop_reason="stop")

    async def forbidden_plan(*args, **kwargs):
        raise AssertionError("must not create a new plan for pending answer")

    monkeypatch.setattr(service, "tool_turn", turn)
    monkeypatch.setattr(service, "generate", forbidden_plan)
    first = await harness.converse("a", "ask", "vocab_basic", "这个题怎么理解")
    resumed = await harness.converse("a", "answer", "vocab_basic", "请安排这个题的讲解",
                                     session_id="new", kind="task")
    assert "learning_plan" not in resumed
    assert resumed["execution"]["answered_question_id"] == first["execution"]["pending_question_id"]
    assert not harness.history.pending("a", resumed["execution"]["thread_id"])


@pytest.mark.parametrize("text,expected", [
    ("请检索我的几段历史，再给出薄弱点诊断和分阶段复习计划。", True),
    ("阅读历史并生成一个分阶段学习路径", True),
    ("Review my history and provide a phased study plan", True),
    ("上次我计划每天复习多少词？", False),
    ("之前制定的计划是什么？", False),
    ("请告诉我之前制定的计划是什么？", False),
    ("之前的计划是什么？现在请重新制定新计划", True),
    ("上次做错了，请重新制定学习计划", True),
])
def test_compound_task_route_and_historical_query(harness, text, expected):
    assert Coordinator.should_route(context(harness), text) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [False, True])
async def test_known_preference_cannot_be_declared_missing(harness, monkeypatch, structured):
    ref = seed(harness.db, text="我喜欢先自己限时完成")
    ctx = context(harness)
    harness.history.memory.propose(ctx, "preference", "我喜欢先自己限时完成", ref)
    with harness.db:
        harness.history.memory.commit(ctx, ref)
    other = seed(harness.db, "b", "foreign-pref", "PRIVATE")
    model = Model(lambda messages, tools: final(
        json.loads(messages[1]["content"])["task"]["step_id"]))
    model.install(monkeypatch)

    async def generate(prompt, **kwargs):
        model.consume()
        facts = json.loads(prompt)["facts"]
        assert facts["stable_memories"][0]["content"] == "我喜欢先自己限时完成"
        assert other not in json.dumps(facts)
        content = {"goal": "安排复习", "steps": plan_steps()}
        if structured:
            content["evidence"] = [{"kind": "preference", "status": "missing"}]
        else:
            content["constraints"] = ["学生未提供具体学习偏好记录"]
        return LLMResponse(content=json.dumps(content), model="mock")

    monkeypatch.setattr(get_llm_service(), "generate", generate)
    result = await harness.converse("a", "pref-conflict", "vocab_basic", "按我的偏好安排复习")
    assert "我喜欢先自己限时完成" in "；".join(result["learning_plan"]["constraints"])
    assert result["learning_plan"]["evidence"][0]["status"] == "available"
    assert result["learning_plan"]["outcome"] == "completed"
    fallback = next(step for step in steps_for(harness, "a", "pref-conflict")
                    if step["kind"] == "plan_fallback")
    assert fallback["reason"] == "planner_evidence_conflict"


@pytest.mark.asyncio
async def test_expert_transport_error_rolls_back_parent_not_replanned(harness, monkeypatch):
    async def failing_expert(self, step, plan):
        raise httpx.ConnectError("private transport details")

    model = Model(lambda *_: final("a"))
    model.install(monkeypatch)
    monkeypatch.setattr(Coordinator, "expert", failing_expert)
    with pytest.raises(HTTPException) as error:
        await harness.converse("a", "transport", "vocab_basic", "安排复习")
    assert error.value.status_code == 503
    assert len(model.plans) == 1
    assert harness.db.execute("SELECT count(*) FROM learning_plans").fetchone()[0] == 0
    assert "private transport details" not in json.dumps(steps_for(harness, "a", "transport"))


@pytest.mark.asyncio
async def test_invalid_tool_arguments_identified_when_expert_cannot_recover(harness, monkeypatch):
    monkeypatch.setattr(settings, "coordinator_max_replans", 0)
    count = 0

    def handler(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("search_learning_history", limit="five")])
        assert json.loads(messages[-1]["content"])["status"] == "invalid_arguments"
        return final("a", status="failed")

    Model(handler).install(monkeypatch)
    result = await harness.converse("a", "invalid-tool", "vocab_basic", "诊断后安排复习")
    assert result["learning_plan"]["results"]["a"]["error_code"] == "tool_argument_invalid"


def test_practice_reservation_uses_original_input_when_planner_omits_it(harness):
    from core.coordination_budget import practice_reserve
    ctx = context(harness, text="安排复习并准备一道练习题")
    plan = LearningPlan(goal="复习", steps=plan_steps())
    assert practice_reserve(ctx, plan) == 1
    plan.practice_quiz_id = "already-prepared"
    assert practice_reserve(ctx, plan) == 0


@pytest.mark.asyncio
async def test_replan_receives_failure_code_and_keeps_final_request_for_curriculum(harness, monkeypatch):
    count = 0

    def handler(messages, tools):
        nonlocal count
        count += 1
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        if task == "a":
            if count < 3:
                tool = call("get_knowledge_context")
                tool.id = f"context-{count}"
                return NativeTurn(stop_reason="tool_calls", tool_calls=[tool])
            return final("a", status="failed", error_code="budget_exhausted")
        assert tools == []
        return final(task)

    model = Model(handler, revision={"reason": "跳过预算不足的诊断", "steps": [
        {"step_id": "c2", "agent": "Curriculum", "objective": "保守安排"},
        {"step_id": "t2", "agent": "Tutor", "objective": "解释缺口", "depends_on": ["c2"]},
    ]})
    model.install(monkeypatch)
    result = await harness.converse("a", "coded-replan", "vocab_basic", "诊断后安排复习")
    assert model.plans[1]["failed_result"]["error_code"] == "budget_exhausted"
    assert result["learning_plan"]["results"]["c2"]["status"] == "completed"
    assert result["learning_plan"]["outcome"] == "partial"
    allocations = [step for step in steps_for(harness, "a", "coded-replan")
                   if step["kind"] == "agent_budget_allocated"]
    assert allocations[-1]["model_calls_available"] == 1


@pytest.mark.asyncio
async def test_read_retry_cannot_spend_final_tool_budget(harness, monkeypatch):
    monkeypatch.setattr(settings, "specialist_max_tool_calls", 1)
    ctx = context(harness)
    plan = LearningPlan(goal="review", steps=plan_steps())
    ref = seed(harness.db)
    reads, turns = [], []

    def unavailable(*args):
        reads.append(args)
        raise httpx.ConnectError("private")

    monkeypatch.setattr(harness.history, "read", unavailable)

    def handler(messages, tools):
        turns.append(messages)
        if len(turns) == 1:
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("read_learning_history", source_ref=ref)])
        assert tools == []
        assert json.loads(messages[-1]["content"])["error_code"] == "budget_exhausted"
        return final("a", status="failed")

    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert result.error_code == "budget_exhausted"
    assert ctx.tool_calls == 1 and len(reads) == 1
    assert ctx.model_calls == 2
