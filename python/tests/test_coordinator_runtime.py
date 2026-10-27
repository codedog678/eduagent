"""协调闭环的行为验证；模拟模型计入真实父预算，不访问供应商。"""

import json

import pytest

from config.settings import settings
from core.coordination_models import AgentResult, LearningPlan, PlanStep
from core.coordinator import Coordinator
from core.llm_service import LLMResponse, NativeTurn, get_llm_service
from core.run_context import active_run
from core.specialist_runtime import SpecialistRuntime
from tests.test_memory_coordination import call, context, harness, remote_plan, seed


def plan_steps():
    return [
        {"step_id": "a", "agent": "Assessment", "objective": "定位历史问题"},
        {"step_id": "c", "agent": "Curriculum", "objective": "安排练习", "depends_on": ["a"]},
        {"step_id": "t", "agent": "Tutor", "objective": "解释安排", "depends_on": ["c"]},
    ]


def final(task, **kwargs):
    return NativeTurn(content=json.dumps({
        "task_id": task, "status": "completed", "findings": ["根据可用证据安排复习"], **kwargs}),
        stop_reason="stop")


class Model:
    def __init__(self, handler, ctx=None, revision=None, steps=None):
        self.handler, self.ctx, self.revision = handler, ctx, revision
        self.steps = steps or plan_steps()
        self.plans, self.turns = [], []

    def _has_remote_llm(self):
        return True

    def consume(self):
        (active_run.get() or self.ctx).consume("model")

    async def generate(self, prompt, **kwargs):
        self.consume()
        data = json.loads(prompt)
        self.plans.append(data)
        content = ({"goal": data["request"], "constraints": ["每天十分钟"], "steps": self.steps}
                   if "request" in data else self.revision)
        return LLMResponse(content=json.dumps(content), model="mock")

    async def tool_turn(self, messages, tools, max_tokens):
        self.consume()
        self.turns.append(json.loads(json.dumps(messages)))
        if "专家" not in messages[0]["content"]:
            return NativeTurn(content="根据已核实的信息先复习基础词汇。", stop_reason="stop")
        return self.handler(messages, tools)

    def install(self, monkeypatch):
        service = get_llm_service()
        for name in ("_has_remote_llm", "generate", "tool_turn"):
            monkeypatch.setattr(service, name, getattr(self, name))


@pytest.mark.asyncio
async def test_specialist_selects_search_then_raw_read_and_restores_parent(harness):
    ref = seed(harness.db, text="过去时 mistake 的原始记录")
    ctx = context(harness, text="根据 mistake 安排复习")
    ctx.role, ctx.task_id = "Coordinator", "parent"
    plan = LearningPlan(goal=ctx.input_text, steps=plan_steps())
    observed = []
    def handler(messages, schemas):
        observed.append(messages[-1])
        names = {s["function"]["name"] for s in schemas}
        assert not names & {"ask_student", "propose_memory_update", "prepare_practice"}
        if len(observed) == 1:
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("search_learning_history", query="mistake")])
        if len(observed) == 2:
            assert ref in json.loads(messages[-1]["content"])["source_refs"]
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("read_learning_history", source_ref=ref)])
        assert "原始记录" in json.loads(messages[-1]["content"])["data"]["content"]
        return final("a", source_refs=[ref])
    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[0], plan)
    assert result.source_refs == [ref]
    assert (ctx.role, ctx.task_id, ctx.max_model_calls, ctx.max_tool_calls) == ("Coordinator", "parent", 8, 16)
    assert ctx.model_calls == 3 and ctx.tool_calls == 2
    assert ctx.read_refs == [ref]


@pytest.mark.asyncio
async def test_downstream_can_cite_verified_ancestor_without_requery(harness):
    ref = seed(harness.db)
    ctx = context(harness)
    plan = LearningPlan(goal="review", steps=plan_steps(), results={
        "a": AgentResult(task_id="a", status="completed", findings=["需要短例子"], source_refs=[ref])})
    plan.steps[0].status = "completed"
    def handler(messages, tools):
        assert json.loads(messages[1]["content"])["previous_results"][0]["source_refs"] == [ref]
        return final("c", source_refs=[ref])
    result = await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[1], plan)
    assert result.source_refs == [ref] and ctx.tool_calls == 0


@pytest.mark.asyncio
async def test_curriculum_write_attempt_is_denied_even_when_not_advertised(harness):
    ctx = context(harness)
    touched = []
    async def prepare(**kwargs):
        touched.append(kwargs)
    ctx.prepare_practice = prepare
    plan = LearningPlan(goal="review", steps=plan_steps())
    count = 0
    def handler(messages, tools):
        nonlocal count
        count += 1
        if count == 1:
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("prepare_practice", knowledge_id="vocab_basic")])
        assert json.loads(messages[-1]["content"])["status"] == "denied"
        return final("c")
    await SpecialistRuntime(ctx, Model(handler, ctx)).run(plan.steps[1], plan)
    assert touched == []


@pytest.mark.asyncio
async def test_revision_replaces_failed_dependency_and_executes_new_steps(harness, monkeypatch):
    roles = []
    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]
        roles.append(task["step_id"])
        return final(task["step_id"], status="failed") if task["step_id"] == "a" else final(task["step_id"])
    model = Model(handler, revision={"reason": "无法诊断，改为只读课程安排", "steps": [
        {"step_id": "new-c", "agent": "Curriculum", "objective": "根据当前知识安排"},
        {"step_id": "new-t", "agent": "Tutor", "objective": "解释剩余缺口", "depends_on": ["new-c"]}]})
    model.install(monkeypatch)
    result = await harness.converse("a", "repair", "vocab_basic", "根据错误安排复习")
    plan = result["learning_plan"]
    assert roles == ["a", "new-c"]
    assert [s["step_id"] for s in plan["steps"]] == ["a", "new-c", "new-t"]
    assert plan["outcome"] == "partial" and plan["status"] == "completed"
    assert len(plan["revisions"]) == 1 and len(model.plans) == 2
    assert plan["results"]["new-c"]["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_steps", [
    [{"step_id": "t2", "agent": "Tutor", "objective": "错误依赖", "depends_on": ["a"]}],
    [{"step_id": "a", "agent": "Tutor", "objective": "覆盖保留步骤"}],
    [{"step_id": "x", "agent": "Assessment", "objective": "诊断"},
     {"step_id": "y", "agent": "Curriculum", "objective": "规划"},
     {"step_id": "z", "agent": "Tutor", "objective": "讲解"}],
])
async def test_invalid_revision_blocks_downstream(harness, monkeypatch, bad_steps):
    model = Model(lambda messages, tools: final("a", status="failed"),
                  revision={"reason": "无效修订", "steps": bad_steps})
    model.install(monkeypatch)
    result = await harness.converse("a", "bad-revision", "vocab_basic", "安排复习")
    assert len(model.turns) == 1
    assert result["learning_plan"]["outcome"] == "partial"
    assert [s["status"] for s in result["learning_plan"]["steps"]] == ["failed", "blocked", "blocked"]
    assert result["learning_plan"]["revisions"] == []


@pytest.mark.asyncio
async def test_resume_reuses_results_and_preserves_goal_constraints(harness, monkeypatch):
    counts = {"a": 0, "c": 0}
    def handler(messages, tools):
        data = json.loads(messages[1]["content"])
        task = data["task"]["step_id"]
        counts[task] += 1
        if task == "c" and counts[task] == 1:
            return final("c", status="needs_input", needs_input="需要复习哪个单元？")
        if task == "c":
            assert data["student_inputs"] == ["基础词汇"]
            assert data["constraints"] == ["每天十分钟"]
            assert data["previous_results"][0]["task_id"] == "a"
        return final(task)
    model = Model(handler)
    model.install(monkeypatch)
    first = await harness.converse("a", "wait", "vocab_basic", "根据错误安排复习")
    second = await harness.converse("a", "resume", "vocab_basic", "基础词汇", session_id="another")
    assert counts == {"a": 1, "c": 2} and len(model.plans) == 1
    assert second["learning_plan"]["goal"] == first["learning_plan"]["goal"]
    assert second["learning_plan"]["version"] == 2
    assert second["learning_plan"]["outcome"] == "completed"
    stored = json.loads(harness.db.execute("SELECT body FROM learning_plans").fetchone()[0])
    assert stored["results"]["a"]["status"] == "completed"


@pytest.mark.parametrize("invalid", ["deleted", "foreign", "upstream", "legacy"])
def test_restore_invalidates_unusable_result_and_dependents(harness, invalid):
    own = seed(harness.db)
    other = seed(harness.db, "b", "foreign")
    plan = LearningPlan(goal="original", constraints=["ten minutes"], steps=plan_steps())
    for step in plan.steps[:2]:
        step.status = "completed"
        plan.results[step.step_id] = AgentResult(
            task_id=step.step_id, status="completed", findings=["观察"], source_refs=[own])
    if invalid == "deleted":
        with harness.db:
            harness.db.execute("DELETE FROM conversation_messages WHERE id='one'")
    elif invalid == "foreign":
        plan.results["a"].source_refs = [other]
    else:
        plan.results.pop("a")
    plan.steps[-1].status = "waiting"
    raw = plan.model_dump()
    if invalid == "legacy":
        raw.pop("results")
    resumed = Coordinator(context(harness), None).restore_plan(raw, "补充")
    assert [s.status for s in resumed.steps] == ["pending"] * 3
    assert resumed.results == {}


@pytest.mark.asyncio
async def test_expert_budget_keeps_tutor_reserve_and_restores_scope_on_failure(harness):
    ctx = context(harness)
    ctx.model_calls, ctx.role, ctx.task_id = 5, "Coordinator", "outer"
    plan = LearningPlan(goal="review", steps=plan_steps())
    model = Model(lambda messages, tools: NativeTurn(stop_reason="tool_calls", tool_calls=[
        call("get_knowledge_context")]), ctx)
    with pytest.raises(ValueError, match="budget_exhausted"):
        await SpecialistRuntime(ctx, model).run(plan.steps[0], plan)
    # 除 Tutor 的两次调用，还须给后续 Curriculum 留一次结论，当前专家不可再请求。
    assert ctx.model_calls == 5 and ctx.max_model_calls == 8
    assert model.turns == []
    assert (ctx.role, ctx.task_id) == ("Coordinator", "outer")


@pytest.mark.asyncio
async def test_no_planner_call_when_only_tutor_budget_remains(harness, monkeypatch):
    ctx = context(harness, text="安排复习")
    ctx.model_calls = 6
    model = Model(lambda *_: final("a"), ctx)
    monkeypatch.setattr(settings, "coordinator_max_delegations", 1)
    result = await Coordinator(ctx, model).run(ctx.input_text)
    assert model.plans == []
    assert result["learning_plan"]["outcome"] == "completed"
    assert ctx.model_calls == 7


@pytest.mark.asyncio
async def test_rejected_practice_marks_partial_and_does_not_store_quiz(harness, monkeypatch):
    advanced = next(n.id for n in harness.orch.curriculum.knowledge_graph.nodes.values() if n.prerequisites)
    model = Model(lambda messages, tools: final("c", proposed_actions=[
        {"knowledge_id": advanced, "difficulty": .5}]), steps=plan_steps()[1:])
    model.steps[0]["depends_on"] = []
    model.install(monkeypatch)
    monkeypatch.setattr(settings, "coordinator_max_replans", 0)
    result = await harness.converse("a", "denied-practice", "vocab_basic", "安排进阶练习并准备一道练习题")
    assert result["learning_plan"]["outcome"] == "partial"
    assert result["learning_plan"]["results"]["c"]["status"] == "failed"
    assert result["learning_plan"]["action_receipts"]["c"]["status"] == "denied"
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_second_failure_stops_without_unbounded_revision(harness, monkeypatch):
    model = Model(lambda messages, tools: final(
        json.loads(messages[1]["content"])["task"]["step_id"], status="failed"),
        revision={"reason": "尝试另一路径", "steps": [
            {"step_id": "c2", "agent": "Curriculum", "objective": "重试"},
            {"step_id": "t2", "agent": "Tutor", "objective": "总结", "depends_on": ["c2"]}]})
    model.install(monkeypatch)
    result = await harness.converse("a", "second-fail", "vocab_basic", "安排复习")
    assert len(model.plans) == 2 and len(model.turns) == 2
    assert result["learning_plan"]["outcome"] == "partial"


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_plan_results_and_conversation(harness, monkeypatch):
    Model(lambda messages, tools: final(
        json.loads(messages[1]["content"])["task"]["step_id"])).install(monkeypatch)
    original = harness.history.commit_conversation
    def fail(*args):
        original(*args)
        raise OSError("injected")
    monkeypatch.setattr(harness.history, "commit_conversation", fail)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await harness.converse("a", "rollback", "vocab_basic", "安排复习")
    for table in ("learning_plans", "conversation_messages", "quizzes"):
        assert harness.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_revision_reexecutes_same_role_objective_without_delegate_cache(harness, monkeypatch):
    tasks = []
    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        tasks.append(task)
        return final(task, status="failed" if task == "a" else "completed")
    model = Model(handler, revision={"reason": "用新任务重新检查", "steps": [
        {"step_id": "a2", "agent": "Assessment", "objective": "定位历史问题"},
        {"step_id": "t2", "agent": "Tutor", "objective": "总结", "depends_on": ["a2"]}]})
    model.install(monkeypatch)
    result = await harness.converse("a", "same-objective", "vocab_basic", "安排复习")
    assert tasks == ["a", "a2"]
    assert result["learning_plan"]["results"]["a2"]["status"] == "completed"


@pytest.mark.asyncio
async def test_revision_preserves_already_completed_expert(harness, monkeypatch):
    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        return final(task, status="failed" if task == "c" else "completed")
    model = Model(handler, revision={"reason": "保留诊断，说明课程缺口", "steps": [
        {"step_id": "t2", "agent": "Tutor", "objective": "说明缺口", "depends_on": ["a"]}]})
    model.install(monkeypatch)
    result = await harness.converse("a", "preserve", "vocab_basic", "安排复习")
    assert result["learning_plan"]["results"]["a"]["status"] == "completed"
    assert result["learning_plan"]["steps"][0]["step_id"] == "a"
    assert result["learning_plan"]["outcome"] == "partial"


@pytest.mark.asyncio
async def test_resume_cross_topic_practice_preserves_hint_contract(harness, monkeypatch):
    remote_plan(monkeypatch, practice=True)
    first = await harness.converse("a", "cross-prepare", "grammar_tenses", "安排基础词汇练习")
    observed = []
    async def turn(messages, tools, max_tokens):
        facts = json.loads(next(m["content"].split("\n", 1)[1] for m in messages
                               if (m.get("content") or "").startswith("服务端学习事实")))
        observed.append(facts)
        assert facts["quiz"]["knowledge_id"] == "vocab_basic"
        assert facts["quiz_bound"]
        assert "correct_index" not in json.dumps(facts)
        return NativeTurn(content="先根据题干中的词义线索判断。", stop_reason="stop")
    monkeypatch.setattr(get_llm_service(), "tool_turn", turn)
    result = await harness.converse("a", "cross-resume", "grammar_tenses", "给我一个提示")
    assert len(observed) == 1
    assert result["learning_plan"]["practice_quiz_id"] == first["prepared_practice"]["quiz_id"]
    assert result["learning_plan"]["outcome"] == "awaiting_student"
    assert harness.db.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 1
