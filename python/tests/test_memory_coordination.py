"""记忆、共享工具和协调者的行为验证；供应商调用全部使用模拟响应。"""

import asyncio
import json
import sqlite3
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from api.orchestrator import AgentOrchestrator
from config.settings import Settings, settings
from core.coordinator import LearningPlan
from core.harness import LearningHarness
from core.harness_migrations import migrate
from core.llm_service import LLMResponse, NativeToolCall, NativeTurn, get_llm_service
from core.memory_retrieval import MemoryRetrieval, MemoryWorker, SiliconFlowEmbedding
from core.memory_store import MemoryStore, digest
from core.run_context import RunContext, RunExhausted, active_run
from core.tool_executor import ToolExecutor


@pytest.fixture
def harness(tmp_path, monkeypatch):
    from core.memory_manager import MemoryManager
    async def no_db(*args):
        return None
    monkeypatch.setattr(MemoryManager, "_load_learner_from_db", no_db)
    monkeypatch.setattr(settings, "memory_embedding_api_key", "")
    monkeypatch.setattr(settings, "siliconflow_api_key", "")
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    orch = AgentOrchestrator()
    store = LearningHarness(orch, str(tmp_path / "state.db"))
    orch.harness = store
    yield store
    store.close()


def seed(db, learner="a", identifier="one", text="I prefer short examples", knowledge="vocab_basic"):
    with db:
        db.execute("INSERT OR IGNORE INTO learning_threads VALUES (?,?,?)",
                   (learner + knowledge, learner, knowledge))
        db.execute("INSERT INTO conversation_messages VALUES (?,?,?,?,?,?,?,?)",
                   (identifier, learner, learner, learner + knowledge, "seed", "user", text, time.time()))
        MemoryStore(db).index(learner, "message:" + identifier)
    return "message:" + identifier


def context(harness, learner="a", text=""):
    return RunContext(learner, "run", "attempt", time.monotonic()+20,
                      knowledge_id="vocab_basic", history=harness.history,
                      knowledge_graph=harness.orch.curriculum.knowledge_graph, input_text=text)


def call(name, **args):
    return NativeToolCall(id=name, name=name, arguments=json.dumps(args))


@pytest.mark.asyncio
async def test_embedding_exact_protocol_and_index_order():
    requests = []
    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}],
            "usage": {"total_tokens": 2}})
    config = Settings(_env_file=None, llm_provider="template", siliconflow_api_key="test-only")
    provider = SiliconFlowEmbedding(config, httpx.MockTransport(handler))
    assert await provider.embed(["one", "two"]) == [[1, 0], [0, 1]]
    assert requests == [{"model": "BAAI/bge-m3", "input": ["one", "two"], "encoding_format": "float"}]
    assert provider.last_usage == {"total_tokens": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [
    [{"index": 1, "embedding": [1, 0]}],
    [{"index": 0, "embedding": [0, 0]}],
    [{"index": 0, "embedding": [True, 1]}],
    [{"index": 0, "embedding": []}],
])
async def test_embedding_rejects_invalid_response(data):
    provider = SiliconFlowEmbedding(
        Settings(_env_file=None, llm_provider="template", siliconflow_api_key="test-only"),
        httpx.MockTransport(lambda req: httpx.Response(200, json={"data": data})))
    with pytest.raises(ValueError):
        await provider.embed(["one"])


def test_lexical_scope_empty_and_unindexed_history(harness):
    seed(harness.db, text="我喜欢短例子，先观察动词")
    seed(harness.db, "b", "secret", "我喜欢短例子 SECRET")
    assert harness.history.search("a", "vocab_basic", "例子")["items"]
    assert not harness.history.search("a", "vocab_basic", "unrelated_xyz")["items"]
    assert not harness.history.search("a", "grammar_tenses", "例子")["items"]
    found = harness.history.search("a", "vocab_basic", "例子")
    assert "SECRET" not in json.dumps(found)
    with harness.db:
        harness.db.execute("DELETE FROM memory_fts")
        harness.db.execute("DELETE FROM memory_chunks")
    assert harness.history.search("a", "vocab_basic", "例子")["items"]


def test_memory_lifecycle_and_source_deletion(harness):
    first = seed(harness.db, text="我喜欢先看例子")
    ctx = context(harness)
    store = harness.history.memory
    store.propose(ctx, "preference", "我喜欢先看例子", first)
    with harness.db:
        store.commit(ctx, first)
    memory = store.profile("a")[0]
    identifier = memory["source_ref"].split(":")[1]
    second = seed(harness.db, identifier="two", text="我现在喜欢先看规则")
    ctx.memory_proposals.clear()
    store.propose(ctx, "preference", "我现在喜欢先看规则", second, identifier)
    with harness.db:
        store.commit(ctx, second)
    assert not store.source("a", memory["source_ref"])
    assert store.profile("a")[0]["version"] == 2
    assert not store.source("b", store.profile("a")[0]["source_ref"])
    with harness.db:
        harness.db.execute("DELETE FROM conversation_messages WHERE id='two'")
    assert not store.profile("a")


def test_memory_conflict_is_candidate_and_not_mastery(harness):
    store = harness.history.memory
    for i, text in enumerate(["我喜欢例子", "我已经完全掌握"]):
        ref = seed(harness.db, identifier=str(i), text=text)
        ctx = context(harness)
        store.propose(ctx, "preference", text, ref)
        with harness.db:
            store.commit(ctx, ref)
    assert len(store.profile("a")) == 1
    assert harness.db.execute("SELECT count(*) FROM memory_items WHERE status='candidate'").fetchone()[0] == 1
    assert harness.orch.get_learner_model_sync("a").get_state("vocab_basic").mastery == .1
    with pytest.raises(ValueError):
        store.propose(context(harness), "goal", "捏造目标", "message:0")


def test_raw_read_paginates_without_losing_tail(harness):
    text = "start" + "x"*4000 + "end"
    ref = seed(harness.db, text=text)
    first = harness.history.read("a", ref)
    second = harness.history.read("a", ref, first["next_cursor"])
    assert first["truncated"] and second["next_cursor"] is None
    assert first["content"] + second["content"] == text


@pytest.mark.asyncio
async def test_hybrid_rrf_scope_hash_and_degrade(harness):
    ref = seed(harness.db, text="I prefer concise examples")
    foreign = seed(harness.db, "b", "foreign", "private preference")
    for source_ref, learner in [(ref, "a"), (foreign, "b")]:
        source = harness.history.memory.source(learner, source_ref)
        with harness.db:
            harness.db.execute("INSERT INTO memory_embeddings VALUES (?,?,?,?,?,?)",
                               (digest(source_ref), "siliconflow", "BAAI/bge-m3", 2,
                                digest(source["content"]), "[1,0]"))
    class Provider:
        key = "fake"
        last_usage = {"total_tokens": 1}
        async def embed(self, texts):
            return [[1, 0]]
    config = Settings(_env_file=None, llm_provider="template")
    retrieval = MemoryRetrieval(harness.db, config, Provider())
    found = await retrieval.search("a", "vocab_basic", "简短教学", ctx=context(harness))
    assert [i["source_ref"] for i in found["items"]] == [ref]
    with harness.db:
        harness.db.execute("UPDATE memory_embeddings SET content_hash='stale'")
    assert not (await retrieval.search("a", "vocab_basic", "简短教学"))["items"]
    async def unavailable(texts):
        raise httpx.ConnectError("not logged")
    retrieval.provider.embed = unavailable
    found = await retrieval.search("a", "vocab_basic", "concise")
    assert found["items"] and found["retrieval_mode"] == "lexical"
    assert retrieval.health()["degraded_reason"] == "ConnectError"


@pytest.mark.asyncio
async def test_worker_retry_and_restart_without_repeating_teaching(harness):
    ref = seed(harness.db)
    class Provider:
        key = "fake"
        async def embed(self, texts):
            raise httpx.ConnectError("unavailable")
    path = harness.db.execute("PRAGMA database_list").fetchone()[2]
    worker = MemoryWorker(path, provider=Provider())
    await worker.process_once()
    assert harness.db.execute("SELECT attempts FROM memory_jobs WHERE job_kind='embed'").fetchone()[0] == 1
    async def good(texts):
        return [[1, 0]]
    worker.provider.embed = good
    with harness.db:
        harness.db.execute("UPDATE memory_jobs SET next_retry_at=0")
    await worker.process_once()
    assert harness.db.execute("SELECT count(*) FROM memory_embeddings").fetchone()[0] == 1
    assert harness.db.execute("SELECT status FROM memory_jobs WHERE job_kind='embed'").fetchone()[0] == "completed"
    assert len(harness.history.messages("a")["items"]) == 1


@pytest.mark.asyncio
async def test_tool_permissions_errors_cache_and_budget(harness):
    ctx = context(harness)
    executor = ToolExecutor(ctx, role="Assessment")
    denied = await executor.execute(call("prepare_practice", knowledge_id="vocab_basic"))
    invalid = await executor.execute(call("search_learning_history", limit="5"))
    empty = await executor.execute(call("search_learning_history", query="absent"))
    assert [denied["status"], invalid["status"], empty["status"]] == ["denied", "invalid_arguments", "empty"]
    assert "learner_id" not in executor.schemas()[0]["function"]["parameters"].get("properties", {})
    again = await executor.execute(call("search_learning_history", query="absent"))
    assert again["cached"]
    ctx.max_tool_calls = ctx.tool_calls
    with pytest.raises(RunExhausted):
        await executor.execute(call("get_knowledge_context"))


@pytest.mark.asyncio
async def test_read_tool_retries_only_transient_once(harness, monkeypatch):
    ctx = context(harness)
    executor = ToolExecutor(ctx)
    calls = 0
    async def transient(name, params):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("private details")
    monkeypatch.setattr(executor, "dispatch", transient)
    result = await executor.execute(call("get_knowledge_context"))
    assert calls == 2 and result["status"] == "transient_error"
    assert "private details" not in json.dumps(ctx.steps)


def test_plan_rejects_cycles_roles_and_duplicate_ids():
    with pytest.raises(ValueError):
        LearningPlan(goal="review", steps=[
            {"step_id": "a", "agent": "Tutor", "objective": "teach", "depends_on": ["a"]}])
    with pytest.raises(ValueError):
        LearningPlan(goal="review", steps=[
            {"step_id": "a", "agent": "Shell", "objective": "teach"}])


@pytest.mark.asyncio
async def test_local_coordinator_selects_roles_and_replays(harness):
    result = await harness.converse("a", "plan", "vocab_basic", "结合上次错误安排十分钟复习")
    assert [s["agent"] for s in result["learning_plan"]["steps"]] == ["Assessment", "Curriculum", "Tutor"]
    assert "暂无匹配" in result["agent_insights"]["specialists"][0]["findings"][0]
    assert await harness.converse("a", "plan", "vocab_basic", "结合上次错误安排十分钟复习") == result
    assert harness.db.execute("SELECT count(*) FROM learning_plans").fetchone()[0] == 1
    assert harness.orch.get_learner_model_sync("a").get_state("vocab_basic").mastery == .1


def remote_plan(monkeypatch, needs_input=False, practice=False, fail_tutor=False):
    service = get_llm_service()
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    async def generate(prompt, system_prompt, **kwargs):
        data = json.loads(prompt)
        if "request" in data:
            content = {"goal": data["request"], "steps": [
                {"step_id": "c", "agent": "Curriculum", "objective": "安排复习"},
                {"step_id": "t", "agent": "Tutor", "objective": "提供练习", "depends_on": ["c"]}]}
        else:
            content = {"reason": "诊断不可用，先说明缺口", "steps": [
                {"step_id": "revised-tutor", "agent": "Tutor", "objective": "说明未完成部分"}]}
        return LLMResponse(content=json.dumps(content), model="fake")
    async def turn(messages, tools, max_tokens):
        if "Curriculum专家" in messages[0]["content"]:
            return NativeTurn(content=json.dumps({
                "task_id": "c", "status": "needs_input" if needs_input else "completed",
                "findings": ["先练习基础词汇"], "source_refs": [],
                "needs_input": "今天有几分钟？" if needs_input else None,
                "proposed_actions": [{"knowledge_id": "vocab_basic", "difficulty": .5}] if practice else []
            }), stop_reason="stop")
        if fail_tutor:
            raise RuntimeError("injected")
        return NativeTurn(content="请完成刚准备的练习，再检查词义线索。", stop_reason="stop")
    monkeypatch.setattr(service, "generate", generate)
    monkeypatch.setattr(service, "tool_turn", turn)


@pytest.mark.asyncio
async def test_plan_wait_resume_and_atomic_practice(harness, monkeypatch):
    remote_plan(monkeypatch, needs_input=True)
    first = await harness.converse("a", "p1", "vocab_basic", "安排复习")
    assert first["learning_plan"]["status"] == "awaiting_student"
    pending = first["execution"]["pending_question_id"]
    remote_plan(monkeypatch)
    second = await harness.converse("a", "p2", "vocab_basic", "十分钟", session_id="new")
    assert second["learning_plan"]["plan_id"] == first["learning_plan"]["plan_id"]
    assert second["learning_plan"]["version"] == 2
    assert second["execution"]["answered_question_id"] == pending
    assert not harness.history.pending("a", second["execution"]["thread_id"])


@pytest.mark.asyncio
async def test_prepared_practice_commits_once_and_failure_rolls_back(harness, monkeypatch):
    remote_plan(monkeypatch, practice=True)
    async def question(*args):
        return {"question": "Which means abundant?", "options": ["plenty", "rare"],
                "correct_index": 0, "explanation": "private"}
    monkeypatch.setattr(get_llm_service(), "generate_question", question)
    result = await harness.converse("a", "p", "vocab_basic", "安排一题复习")
    public = result["prepared_practice"]
    assert "correct_index" not in json.dumps(result)
    assert harness.quiz("a", public["quiz_id"])["correct_index"] == 0
    assert await harness.converse("a", "p", "vocab_basic", "安排一题复习") == result
    remote_plan(monkeypatch, practice=True, fail_tutor=True)
    with pytest.raises(HTTPException):
        await harness.converse("b", "fail", "vocab_basic", "安排一题复习")
    for table, field in [("quizzes", "learner"), ("learning_plans", "learner_id"),
                         ("conversation_messages", "learner"), ("memory_chunks", "learner_id")]:
        assert harness.db.execute(f"SELECT count(*) FROM {table} WHERE {field}='b'").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_global_model_budget_includes_legacy_generate(harness, monkeypatch):
    service = get_llm_service()
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                               usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))
    monkeypatch.setattr(service, "provider", "openai")
    monkeypatch.setattr(service, "_client", SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    ctx = context(harness)
    ctx.max_model_calls = 1
    token = active_run.set(ctx)
    try:
        await service.generate("one")
        with pytest.raises(RunExhausted):
            await service.generate("two")
    finally:
        active_run.reset(token)


@pytest.mark.asyncio
async def test_explicit_memory_rollback_then_commit_and_extract(harness, monkeypatch):
    original = harness.history.commit_conversation
    def fail(*args):
        original(*args)
        raise OSError("commit_failed")
    monkeypatch.setattr(harness.history, "commit_conversation", fail)
    with pytest.raises(HTTPException):
        await harness.converse("a", "remember", "vocab_basic", "请记住：我喜欢先看短例子")
    for table in ("memory_items", "memory_chunks", "memory_jobs", "conversation_messages"):
        assert harness.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    monkeypatch.setattr(harness.history, "commit_conversation", original)
    await harness.converse("a", "remember", "vocab_basic", "请记住：我喜欢先看短例子")
    assert harness.history.memory.profile("a")[0]["content"] == "请记住：我喜欢先看短例子"
    await harness.memory_worker.process_once()
    assert harness.db.execute("SELECT count(*) FROM memory_items WHERE kind='episode'").fetchone()[0] == 1
    assert harness.orch.get_learner_model_sync("a").get_state("vocab_basic").attempts == 0


def test_long_source_tail_and_expiration(harness):
    ref = seed(harness.db, text="opening " + "filler " * 1000 + "tailkeyword")
    assert harness.history.search("a", "vocab_basic", "tailkeyword")["items"][0]["source_ref"] == ref
    assert harness.db.execute("SELECT count(*) FROM memory_chunks").fetchone()[0] > 1
    ctx = context(harness)
    harness.history.memory.propose(ctx, "episode", "opening", ref)
    with harness.db:
        harness.history.memory.commit(ctx, ref)
        harness.db.execute("UPDATE memory_items SET valid_until=0")
    assert not any(i["source_ref"].startswith("memory:") for i in
                   harness.history.search("a", "vocab_basic", "opening")["items"])


@pytest.mark.asyncio
async def test_practice_answer_completes_matching_plan(harness, monkeypatch):
    remote_plan(monkeypatch, practice=True)
    result = await harness.converse("a", "prepare", "vocab_basic", "安排一题练习")
    quiz_id = result["prepared_practice"]["quiz_id"]
    assert result["learning_plan"]["status"] == "awaiting_student"
    assert harness.quiz("a", quiz_id)["assisted"]
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    answer = await harness.answer("a", "solve", quiz_id, harness.quiz("a", quiz_id)["correct_index"], 3, None)
    assert not answer["learning_evidence"]["independent"]
    row = harness.db.execute("SELECT status FROM learning_plans").fetchone()
    assert row[0] == "completed"
    assert not harness.history.pending("a", result["execution"]["thread_id"])


@pytest.mark.asyncio
async def test_expert_invalid_source_replans_once(harness, monkeypatch):
    remote_plan(monkeypatch)
    original = get_llm_service().tool_turn
    async def ungrounded(messages, tools, max_tokens):
        if "Curriculum专家" in messages[0]["content"]:
            return NativeTurn(content=json.dumps({
                "task_id": "c", "status": "completed", "source_refs": ["message:foreign"]}), stop_reason="stop")
        return await original(messages, tools, max_tokens)
    monkeypatch.setattr(get_llm_service(), "tool_turn", ungrounded)
    result = await harness.converse("a", "replan", "vocab_basic", "安排复习")
    assert result["learning_plan"]["steps"][0]["status"] == "failed"
    trace = harness.history.trace("a", "replan")["attempts"][0]["steps"]
    assert len([s for s in trace if s["kind"] == "plan_revised"]) == 1
    assert "message:foreign" not in result["execution"]["source_refs"]


@pytest.mark.asyncio
async def test_history_question_is_not_new_plan(harness):
    from core.coordinator import Coordinator
    ctx = context(harness)
    assert not Coordinator.should_route(ctx, "上次我计划每天复习多少词？")
    assert Coordinator.should_route(ctx, "帮我制定十分钟复习计划")


@pytest.mark.asyncio
async def test_rerank_failure_keeps_fused_candidates(harness, monkeypatch):
    seed(harness.db, identifier="one", text="example one")
    seed(harness.db, identifier="two", text="example two")
    config = Settings(_env_file=None, llm_provider="template",
                      memory_retrieval_mode="lexical", memory_rerank_enabled=True)
    retrieval = MemoryRetrieval(harness.db, config)
    async def fail(*args):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(retrieval, "rerank", fail)
    ctx = context(harness)
    result = await retrieval.search("a", "vocab_basic", "example", limit=1, ctx=ctx)
    assert len(result["items"]) == 1
    assert ctx.steps[-1]["rerank_error"] == "rerank_unavailable"


@pytest.mark.asyncio
async def test_write_tool_not_retried_and_prerequisites_enforced(harness, monkeypatch):
    ctx = context(harness)
    count = 0
    async def prepare(**kwargs):
        nonlocal count
        count += 1
        raise httpx.ConnectError("offline")
    ctx.prepare_practice = prepare
    executor = ToolExecutor(ctx, role="Coordinator")
    result = await executor.execute(call("prepare_practice", knowledge_id="vocab_basic"))
    assert count == 1 and not result["retryable"]
    harness.orch.get_learner_model_sync("a")
    advanced = next(n.id for n in ctx.knowledge_graph.nodes.values() if n.prerequisites)
    with pytest.raises(HTTPException):
        await harness.prepare_question("a", advanced, .5, "practice", require_prerequisites=True)


@pytest.mark.asyncio
async def test_worker_model_change_reindexes_and_no_key_does_not_starve_extract(harness):
    seed(harness.db)
    class Provider:
        key = "fake"
        async def embed(self, texts):
            return [[1, 0] for _ in texts]
    path = harness.db.execute("PRAGMA database_list").fetchone()[2]
    worker = MemoryWorker(path, provider=Provider())
    await worker.process_once()
    config = Settings(_env_file=None, llm_provider="template", memory_embedding_model="test-model")
    worker = MemoryWorker(path, config, Provider())
    await worker.process_once()
    assert harness.db.execute("SELECT count(DISTINCT model) FROM memory_embeddings").fetchone()[0] == 2
    worker.provider.key = ""
    with harness.db:
        harness.history.memory.enqueue("message:one", kind="extract")
    await worker.process_once()
    assert harness.db.execute("SELECT status FROM memory_jobs WHERE job_kind='extract'").fetchone()[0] == "completed"


@pytest.mark.asyncio
async def test_cross_knowledge_practice_completes_original_thread_plan(harness, monkeypatch):
    remote_plan(monkeypatch, practice=True)
    result = await harness.converse("a", "prepare-cross", "grammar_tenses", "安排基础词汇复习")
    quiz_id = result["prepared_practice"]["quiz_id"]
    original_thread = result["execution"]["thread_id"]
    assert harness.quiz("a", quiz_id)["thread_id"] != original_thread
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    await harness.answer("a", "answer-cross", quiz_id, harness.quiz("a", quiz_id)["correct_index"], 2, None)
    assert harness.db.execute("SELECT status,thread_id FROM learning_plans").fetchone() == ("completed", original_thread)
    assert not harness.history.pending("a", original_thread)


@pytest.mark.asyncio
async def test_memory_error_keeps_accepted_state_for_first_reply(harness, monkeypatch):
    service = get_llm_service()
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    text = "请记住：我喜欢先看两个简短例句，然后再归纳规则。"
    observed = []
    async def turn(messages, tools, max_tokens):
        observed.append(json.loads(json.dumps(messages)))
        if len(observed) == 1:
            facts = json.loads(next(m["content"] for m in messages
                                    if m["content"] and m["content"].startswith("服务端学习事实")).split("\n", 1)[1])
            assert facts["memory_write_state"]["state"] == "pending_commit"
            assert facts["memory_write_state"]["accepted_count"] == 1
            assert "不能据此声称整轮保存失败" in messages[0]["content"]
            # 模拟实际故障：模型改写原话而被严格校验拒绝。
            return NativeTurn(stop_reason="tool_calls", tool_calls=[
                call("propose_memory_update", kind="preference", content="用户偏好先例句后规则")])
        result = json.loads(messages[-1]["content"])
        assert result["status"] == "invalid_arguments"
        assert result["error_code"] == "memory_requires_verbatim_student_statement"
        state = result["data"]["memory_write_state"]
        assert state["state"] == "pending_commit" and state["accepted_count"] == 1
        assert state["items"][0]["content"] == text
        return NativeTurn(content="好的，以后先给两个简短例句，再归纳规则。", stop_reason="stop")
    monkeypatch.setattr(service, "tool_turn", turn)
    result = await harness.converse("a", "first-memory", "vocab_basic", text)
    assert "保存失败" not in result["teaching_response"]["response"]
    assert harness.history.memory.profile("a")[0]["content"] == text
    assert harness.db.execute("SELECT count(*) FROM memory_items").fetchone()[0] == 1
    assert await harness.converse("a", "first-memory", "vocab_basic", text) == result
    assert len(observed) == 2


@pytest.mark.asyncio
async def test_duplicate_quote_does_not_create_conflicting_memory(harness):
    text = "请记住：我喜欢先看两个简短例句，然后再归纳规则。"
    ctx = context(harness, text=text)
    store = harness.history.memory
    store.propose(ctx, "preference", text, "current")
    result = await ToolExecutor(ctx).execute(call(
        "propose_memory_update", kind="preference", content="我喜欢先看两个简短例句"))
    assert result["status"] == "ok" and result["data"]["already_staged"]
    assert len(ctx.memory_proposals) == 1
    ref = seed(harness.db, text=text)
    with harness.db:
        store.commit(ctx, ref)
    assert harness.db.execute("SELECT count(*) FROM memory_items").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_memory_status_does_not_claim_unaccepted_or_conflicting_updates(harness):
    ctx = context(harness, text="我喜欢例子")
    bad = await ToolExecutor(ctx).execute(call(
        "propose_memory_update", kind="preference", content="伪造的新偏好"))
    assert bad["status"] == "invalid_arguments"
    assert bad["data"]["memory_write_state"]["state"] == "not_staged"
    first = seed(harness.db, text=ctx.input_text)
    store = harness.history.memory
    store.propose(ctx, "preference", ctx.input_text, first)
    with harness.db:
        store.commit(ctx, first)
    ctx.memory_proposals.clear()
    ctx.input_text = "我现在喜欢先看规则"
    store.propose(ctx, "preference", ctx.input_text, "current")
    state = store.write_state(ctx)
    assert state["items"][0]["requires_confirmation"]
    assert store.profile("a")[0]["content"] == "我喜欢例子"
