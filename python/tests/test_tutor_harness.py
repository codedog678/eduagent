"""跨会话 → 原生工具 → 终止 → 持久化的实际 Harness 集成测试。"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from api.orchestrator import AgentOrchestrator
from api.routes import router
from core.event_bus import EventType
from core.harness import LearningHarness
from core.llm_service import LLMService, NativeToolCall, NativeTurn, get_llm_service


@pytest.fixture
def store(tmp_path, monkeypatch):
    async def no_database(self, learner, session=None):
        return None
    from core.memory_manager import MemoryManager
    monkeypatch.setattr(MemoryManager, "_load_learner_from_db", no_database)
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    orch = AgentOrchestrator()
    orch.harness = LearningHarness(orch, str(tmp_path / "learning.sqlite3"))
    yield orch.harness
    orch.harness.close()


def scripted(monkeypatch, turns):
    service = get_llm_service()
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    observed = []
    async def turn(messages, tools, max_tokens):
        observed.append(json.loads(json.dumps(messages)))
        assert all("learner" not in json.dumps(tool) for tool in tools)
        if not turns:
            raise AssertionError("unexpected model request")
        return turns.pop(0)
    monkeypatch.setattr(service, "tool_turn", turn)
    return observed


def call(identifier, name, **arguments):
    return NativeTurn(stop_reason="tool_calls", tool_calls=[
        NativeToolCall(id=identifier, name=name, arguments=json.dumps(arguments))])


@pytest.mark.asyncio
async def test_cross_session_sources_replay_and_restart(store, monkeypatch):
    first = await store.converse("student", "q1", "grammar_tenses",
                                 "现在完成时与过去时怎么区分？", session_id="s1")
    second = await store.converse("student", "q2", "grammar_tenses",
                                  "继续解释上次的时态问题", session_id="s2")
    assert second["execution"]["thread_id"] == first["execution"]["thread_id"]
    assert second["execution"]["source_refs"]
    assert await store.converse("student", "q2", "grammar_tenses",
                                "继续解释上次的时态问题", session_id="s2") == second
    assert len(store.history.messages("student")["items"]) == 4
    # 用另一进程生命周期恢复全部事实；原 fixture 的 store 仅负责释放。
    path = store.db.execute("PRAGMA database_list").fetchone()[2]
    store.close()
    orch = AgentOrchestrator()
    restored = LearningHarness(orch, path)
    orch.harness = restored
    try:
        assert await restored.converse("student", "q2", "grammar_tenses",
                                       "继续解释上次的时态问题", session_id="s2") == second
        third = await restored.converse("student", "q3", "grammar_tenses",
                                        "再举个例子", session_id="s3")
        assert third["execution"]["source_refs"]
        assert len(restored.history.messages("student")["items"]) == 6
    finally:
        restored.close()
        import sqlite3
        store.db = sqlite3.connect(path)
        store._owner = open(path + ".lock", "a")


@pytest.mark.asyncio
async def test_search_read_final_and_durable_trace(store, monkeypatch):
    await store.converse("student", "seed", "grammar_tenses", "since 表示什么？")
    ref = store.history.messages("student")["items"][0]["source_ref"]
    observed = scripted(monkeypatch, [
        call("c1", "search_learning_history", query="since"),
        call("c2", "read_learning_history", source_ref=ref),
        NativeTurn(content="结合上次的 since 例句，看动作是否持续到现在。", stop_reason="stop"),
    ])
    result = await store.converse("student", "native", "grammar_tenses", "接着上次讲")
    assert result["teaching_response"]["generation_mode"] == "native_tools"
    assert ref in result["execution"]["source_refs"]
    assert observed[1][-1]["role"] == "tool"
    assert json.loads(observed[1][-1]["content"])["status"] == "ok"
    assert observed[2][-1]["tool_call_id"] == "c2"
    steps = store.history.trace("student", "native")["attempts"][0]["steps"]
    assert [s["tool"] for s in steps if s["kind"] == "after_tool"] == [
        "search_learning_history", "read_learning_history"]
    assert all(event.correlation_id == result["execution"]["run_id"]
               for event in store.orch.event_bus.get_correlation_chain(result["correlation_id"]))


@pytest.mark.asyncio
async def test_deepseek_reasoning_replayed_only_within_current_tool_loop(store, monkeypatch):
    service = get_llm_service()
    monkeypatch.setattr(service, "provider", "deepseek")
    monkeypatch.setattr(service, "thinking", "enabled")
    monkeypatch.setattr(service, "api_key", "test-only")
    monkeypatch.setattr(service, "_has_remote_llm", lambda: True)
    observed = []
    async def create(**kwargs):
        observed.append(json.loads(json.dumps(kwargs)))
        model_no = len(observed)
        tool_calls = [] if model_no in {3, 4} else [
            SimpleNamespace(id=f"c{model_no}", function=SimpleNamespace(
                name="get_knowledge_context", arguments="{}"))]
        return SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="tool_calls" if tool_calls else "stop",
                message=SimpleNamespace(
                    content=None if tool_calls else "根据时间线索判断。",
                    reasoning_content=f"private-reasoning-{model_no}", tool_calls=tool_calls))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
        )
    monkeypatch.setattr(service, "_client", SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = await store.converse("student", "deepseek", "grammar_tenses", "怎么判断？")
    assert result["teaching_response"]["generation_mode"] == "native_tools"
    assert observed[1]["messages"][-2]["reasoning_content"] == "private-reasoning-1"
    assistants = [m for m in observed[2]["messages"] if m["role"] == "assistant"]
    assert [m["reasoning_content"] for m in assistants] == [
        "private-reasoning-1", "private-reasoning-2"]
    public = {
        "reply": result,
        "history": store.history.messages("student"),
        "trace": store.history.trace("student", "deepseek"),
        "events": [e.model_dump(mode="json") for e in store.orch.event_bus.get_history()],
    }
    assert "private-reasoning" not in json.dumps(public)
    assert "test-only" not in json.dumps(public)
    await store.converse("student", "next", "grammar_tenses", "再举个例子", session_id="next")
    assert "private-reasoning" not in json.dumps(observed[3]["messages"])


@pytest.mark.asyncio
async def test_deepseek_reasoning_still_counts_toward_context_budget(store, monkeypatch):
    first = call("c", "get_knowledge_context")
    first.reasoning_content = "private-reasoning" * 3000
    observed = scripted(monkeypatch, [first])
    with pytest.raises(HTTPException) as failed:
        await store.converse("student", "large-reasoning", "vocab_basic", "讲解")
    assert failed.value.status_code == 503
    assert len(observed) == 1
    trace = store.history.trace("student", "large-reasoning")["attempts"][0]
    assert trace["status"] == "exhausted" and trace["stop_reason"] == "context_budget"
    assert store.history.messages("student")["items"] == []
    assert "private-reasoning" not in json.dumps(trace)


@pytest.mark.asyncio
async def test_ask_student_stops_and_next_session_answers(store, monkeypatch):
    observed = scripted(monkeypatch, [
        call("ask", "ask_student", question="这句是否有明确的过去时间？"),
        NativeTurn(content="对，明确的过去时间是区分线索。", stop_reason="stop"),
    ])
    first = await store.converse("student", "ask", "grammar_tenses", "这里为什么不用完成时？")
    assert len(observed) == 1
    assert first["execution"]["status"] == "completed"
    assert first["execution"]["dialogue_state"] == "awaiting_student"
    pending_id = first["execution"]["pending_question_id"]
    second = await store.converse("student", "answer", "grammar_tenses", "有 yesterday", session_id="new")
    assert second["execution"]["answered_question_id"] == pending_id
    assert store.history.pending("student", second["execution"]["thread_id"]) is None
    assert "这句是否有明确的过去时间" in json.dumps(observed[1], ensure_ascii=False)


@pytest.mark.asyncio
async def test_history_owner_and_session_scope(store, monkeypatch):
    first = await store.converse("alice", "a", "vocab_basic", "讨论词汇", session_id="alice-session")
    ref = store.history.messages("alice")["items"][0]["source_ref"]
    with pytest.raises(HTTPException) as missing:
        store.history.read("bob", ref)
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as invalid_session:
        await store.converse("bob", "b", "vocab_basic", "读取", session_id="alice-session")
    assert invalid_session.value.status_code == 404
    observed = scripted(monkeypatch, [
        call("foreign", "read_learning_history", source_ref=ref),
        NativeTurn(content="没有可用的旧记录，请说明你的问题。", stop_reason="stop"),
    ])
    result = await store.converse("bob", "tool", "vocab_basic", "继续")
    assert json.loads(observed[1][-1]["content"])["status"] == "denied"
    assert not result["execution"]["source_refs"]
    assert store.history.messages("bob", first["execution"]["thread_id"])["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,args", [
    ("update_mastery", {"mastery": 1}),
    ("search_learning_history", {"learner_id": "other"}),
    ("search_learning_history", {"limit": "10"}),
    ("read_learning_history", {"source_ref": "message:missing"}),
])
async def test_tool_gate_rejects_unregistered_or_invalid(store, monkeypatch, tool, args):
    observed = scripted(monkeypatch, [
        call("bad", tool, **args),
        NativeTurn(content="请给出一个例句，我来讲解。", stop_reason="stop"),
    ])
    await store.converse("student", "denied", "vocab_basic", "帮我")
    assert json.loads(observed[1][-1]["content"])["status"] == "denied"
    trace = store.history.trace("student", "denied")["attempts"][0]["steps"]
    assert any(step.get("status") == "denied" for step in trace)
    assert store.orch.learner_models["student"].get_state("vocab_basic").mastery < 1


@pytest.mark.asyncio
@pytest.mark.parametrize("turns,reason", [
    ([call("same", "get_knowledge_context"), call("same", "get_knowledge_context")], "duplicate_tool_call"),
    ([call("1", "get_knowledge_context"), call("2", "get_knowledge_context"),
      call("3", "get_knowledge_context")], "model_call_budget"),
    ([NativeTurn(content="partial", stop_reason="length")], "output_token_limit"),
])
async def test_exhaustion_keeps_attempts_and_rolls_back(store, monkeypatch, turns, reason):
    scripted(monkeypatch, turns)
    with pytest.raises(HTTPException) as failed:
        await store.converse("student", "retry", "vocab_basic", "讲一下")
    assert failed.value.status_code == 503
    trace = store.history.trace("student", "retry")["attempts"][0]
    assert trace["status"] == "exhausted" and trace["stop_reason"] == reason
    assert store.history.messages("student")["items"] == []
    scripted(monkeypatch, [NativeTurn(content="这次完整讲解。", stop_reason="stop")])
    result = await store.converse("student", "retry", "vocab_basic", "讲一下")
    attempts = store.history.trace("student", "retry")["attempts"]
    assert len(attempts) == 2 and attempts[1]["status"] == "completed"
    assert attempts[0]["run_id"] == result["execution"]["run_id"]
    assert attempts[0]["attempt_id"] != result["execution"]["attempt_id"]


@pytest.mark.asyncio
async def test_plain_question_and_legacy_api_mark_assistance(store):
    quiz_result = await store.generate("student", "issue", "vocab_basic", 0.5)
    quiz_id = quiz_result["quiz"]["quiz_id"]
    answer_index = store.quiz("student", quiz_id)["correct_index"]
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.orchestrator = store.orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = {"learner_id": "student", "request_id": "help", "knowledge_id": "vocab_basic",
                "question": "解释这道题"}
        response = await client.post("/api/question", json=body)
        assert response.status_code == 200
        assert response.json()["assistance"]["recorded"]
        assert (await client.post("/api/question", json=body)).json() == response.json()
    result = await store.answer("student", "answer", quiz_id, answer_index, 10, None)
    assert result["learning_evidence"]["assisted"]
    assert not result["learning_evidence"]["independent"]
    assert store.orch.learner_models["student"].get_state("vocab_basic").attempts == 0
    evidence = store.db.execute("SELECT kind FROM learning_evidence").fetchall()
    assert evidence == [("assistance",), ("assessment",)]


@pytest.mark.asyncio
async def test_failed_conversation_does_not_commit_assistance_or_history(store):
    issued = await store.generate("student", "issue", "vocab_basic", 0.5)
    quiz_id = issued["quiz"]["quiz_id"]
    before = store.capture("student")
    async def fail(event):
        raise RuntimeError("injected")
    store.orch.event_bus.subscribe(EventType.TEACHING_RESPONSE, fail)
    with pytest.raises(HTTPException):
        await store.converse("student", "fail", "vocab_basic", "帮我", quiz_id=quiz_id)
    assert store.capture("student") == before
    assert not store.quiz("student", quiz_id)["assisted"]
    assert store.history.messages("student")["items"] == []
    assert store.db.execute("SELECT COUNT(*) FROM learning_evidence").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_pending_transport_timeout_cancels_and_cannot_write_late(store, monkeypatch):
    cancelled = asyncio.Event()
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: True)
    async def blocked(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    monkeypatch.setattr(get_llm_service(), "tool_turn", blocked)
    store.timeout = 0.02
    with pytest.raises(HTTPException):
        await store.converse("student", "timeout", "vocab_basic", "讲一下")
    assert cancelled.is_set()
    assert store.run_status("student", "timeout")["status"] == "exhausted"
    assert store.history.messages("student")["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_native_provider_serialization_without_network(provider):
    observed = []
    async def create(**kwargs):
        observed.append(kwargs)
        if provider == "openai":
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="tool_calls", message=SimpleNamespace(content=None, tool_calls=[
                    SimpleNamespace(id="x", function=SimpleNamespace(
                        name="get_knowledge_context", arguments="{}"))]))], usage=None)
        return SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="x", name="get_knowledge_context", input={})],
            usage=SimpleNamespace(input_tokens=12, output_tokens=4))
    service = LLMService(provider=provider, api_key="test-only")
    service._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        messages=SimpleNamespace(create=create))
    messages = [{"role": "system", "content": "teacher"},
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "prior", "function": {"name": "get_knowledge_context", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "prior", "content": '{"status":"ok"}'}]
    tools = [{"type": "function", "function": {
        "name": "get_knowledge_context", "description": "read", "parameters": {"type": "object"}}}]
    result = await service.tool_turn(messages, tools, 100)
    assert result.tool_calls[0].id == "x"
    if provider == "anthropic":
        assert observed[0]["messages"][-1]["content"][0]["tool_use_id"] == "prior"
        assert observed[0]["messages"][-2]["content"][0]["type"] == "tool_use"
    else:
        assert observed[0]["messages"][-1]["tool_call_id"] == "prior"


@pytest.mark.asyncio
async def test_previous_wrong_answer_is_searchable_public_evidence(store, monkeypatch):
    issued = await store.generate("student", "issue", "vocab_basic", 0.5)
    quiz_id = issued["quiz"]["quiz_id"]
    quiz = store.quiz("student", quiz_id)
    await store.answer("student", "wrong", quiz_id,
                       (quiz["correct_index"] + 1) % len(quiz["options"]), 10, None)
    found = store.history.search("student", "vocab_basic", "wrong")
    refs = [row["source_ref"] for row in found["items"] if row["source_ref"].startswith("evidence:")]
    assert refs
    evidence = store.history.read("student", refs[0])
    assert not evidence["data"]["is_correct"]
    assert evidence["data"]["question"] == quiz["question"]
    assert evidence["data"]["student_answer"]
    assert "correct_index" not in json.dumps(evidence)
    observed = scripted(monkeypatch, [
        call("read", "read_learning_history", source_ref=refs[0]),
        NativeTurn(content="上次你选错了词义，这次先看上下文。", stop_reason="stop"),
    ])
    result = await store.converse("student", "review", "vocab_basic", "上次哪里做错了？", session_id="new")
    assert refs[0] in result["execution"]["source_refs"]
    assert json.loads(observed[1][-1]["content"])["data"]["data"]["is_correct"] is False


@pytest.mark.asyncio
async def test_protected_quiz_denies_help_but_reveal_ends_measurement(store):
    issued = await store.generate("student", "advance", "vocab_basic", 0.5, mode="advance")
    quiz_id = issued["quiz"]["quiz_id"]
    with pytest.raises(HTTPException) as blocked:
        await store.converse("student", "help", "vocab_basic", "提示", quiz_id=quiz_id)
    assert blocked.value.status_code == 403
    with pytest.raises(HTTPException):
        await store.support("student", "hint", quiz_id, "hint")
    assert store.history.messages("student")["items"] == []
    await store.support("student", "reveal", quiz_id, "reveal")
    with pytest.raises(HTTPException):
        await store.answer("student", "answer", quiz_id, 0, 1, None)


@pytest.mark.asyncio
async def test_ask_student_in_batch_does_not_set_pending_state(store, monkeypatch):
    batched = NativeTurn(stop_reason="tool_calls", tool_calls=[
        NativeToolCall(id="ask", name="ask_student", arguments='{"question":"你怎么想？"}'),
        NativeToolCall(id="read", name="get_knowledge_context", arguments="{}"),
    ])
    observed = scripted(monkeypatch, [
        batched, NativeTurn(content="先根据词义分析。", stop_reason="stop"),
    ])
    result = await store.converse("student", "batch", "vocab_basic", "继续")
    assert result["execution"]["dialogue_state"] == "answered"
    assert store.history.pending("student", result["execution"]["thread_id"]) is None
    assert json.loads(observed[1][-2]["content"])["status"] == "denied"


@pytest.mark.asyncio
async def test_context_and_tool_budgets_are_enforced(store, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "tutor_context_budget_tokens", 2000)
    observed = scripted(monkeypatch, [])
    with pytest.raises(HTTPException):
        await store.converse("student", "too-large", "vocab_basic", "大量上下文" * 1000)
    assert not observed
    assert store.run_status("student", "too-large")["error"] == "context_budget"
    monkeypatch.setattr(settings, "tutor_context_budget_tokens", 6000)
    monkeypatch.setattr(settings, "tutor_max_tool_calls", 1)
    scripted(monkeypatch, [call("one", "get_knowledge_context"),
                           call("two", "get_knowledge_context")])
    with pytest.raises(HTTPException):
        await store.converse("student", "too-many-tools", "vocab_basic", "讲一下")
    assert store.run_status("student", "too-many-tools")["error"] == "tool_call_budget"


@pytest.mark.asyncio
async def test_history_pagination_and_trace_api_owner_filter(store):
    for index in range(3):
        await store.converse("student", f"q{index}", "vocab_basic", f"讲解词汇 {index}")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.orchestrator = store.orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        latest = (await client.get("/api/history/student?limit=2")).json()
        older = (await client.get(f"/api/history/student?limit=2&before={latest['next_cursor']}")).json()
        assert len(latest["items"]) == len(older["items"]) == 2
        assert not {row["source_ref"] for row in latest["items"]} & {
            row["source_ref"] for row in older["items"]}
        assert (await client.get("/api/runs/other/q0/trace")).status_code == 404
        trace = await client.get("/api/runs/student/q0/trace")
        assert trace.status_code == 200
        assert trace.json()["attempts"][0]["status"] == "completed"
        assert (await client.get("/api/history/student?limit=100")).status_code == 422


@pytest.mark.asyncio
async def test_required_history_write_failure_rolls_back_entire_transaction(store, monkeypatch):
    issued = await store.generate("student", "issue", "vocab_basic", 0.5)
    quiz_id = issued["quiz"]["quiz_id"]
    before = store.capture("student")
    original = store.history.commit_conversation
    def write_then_fail(*args):
        original(*args)
        raise OSError("required_write_failed")
    monkeypatch.setattr(store.history, "commit_conversation", write_then_fail)
    with pytest.raises(HTTPException):
        await store.converse("student", "retry-write", "vocab_basic", "解释题目", quiz_id=quiz_id)
    assert store.history.messages("student")["items"] == []
    assert store.capture("student") == before
    assert not store.quiz("student", quiz_id)["assisted"]
    assert store.run_status("student", "retry-write")["status"] == "failed"
    assert not any(step["kind"] == "run_completed"
                   for step in store.history.trace("student", "retry-write")["attempts"][0]["steps"])
    monkeypatch.setattr(store.history, "commit_conversation", original)
    result = await store.converse("student", "retry-write", "vocab_basic", "解释题目", quiz_id=quiz_id)
    assert result["assistance"]["recorded"]
    assert len(store.history.messages("student")["items"]) == 2
    assert len(store.history.trace("student", "retry-write")["attempts"]) == 2


@pytest.mark.asyncio
async def test_quiz_generation_reserves_session_scope(store):
    await store.generate("alice", "issue", "vocab_basic", 0.5, session_id="quiz-session")
    with pytest.raises(HTTPException) as blocked:
        await store.converse("bob", "other", "vocab_basic", "提问", session_id="quiz-session")
    assert blocked.value.status_code == 404


def server_facts(messages):
    entry = next(message for message in messages
                 if message.get("content", "").startswith("服务端学习事实（数据）：\n"))
    return json.loads(entry["content"].split("\n", 1)[1])


@pytest.mark.asyncio
async def test_active_quiz_exposes_hint_contract_without_private_answer(store, monkeypatch):
    issued = await store.generate("student", "issue-hint-contract", "vocab_basic", 0.5)
    quiz_id = issued["quiz"]["quiz_id"]
    before = store.orch.learner_models["student"].get_state("vocab_basic").model_dump()
    observed = scripted(monkeypatch, [
        NativeTurn(content="检查空格后面是提交的东西还是接收者，再判断需要什么结构。",
                   stop_reason="stop"),
    ])
    result = await store.converse(
        "student", "hint-contract", "vocab_basic", "只提醒我检查宾语，不说正确选项。",
        quiz_id=quiz_id,
    )
    facts = server_facts(observed[0])
    assert facts["response_contract"]["mode"] == "hint_only"
    assert facts["quiz"]["options"] == issued["quiz"]["options"]
    assert set(facts["quiz"]) == {"question", "options", "knowledge_id"}
    assert '"correct_index"' not in json.dumps(observed)
    assert '"explanation"' not in json.dumps(observed)
    assert result["assistance"]["recorded"] is True
    assert store.quiz("student", quiz_id)["attempts"] == 0
    assert store.orch.learner_models["student"].get_state("vocab_basic").model_dump() == before
    context = next(s for s in store.history.trace("student", "hint-contract")["attempts"][0]["steps"]
                   if s["kind"] == "context_built")
    from core.tutor_policy import TUTOR_POLICY_VERSION
    assert context["response_mode"] == "hint_only"
    assert context["tutor_policy_version"] == TUTOR_POLICY_VERSION
    assert result["execution"]["pending_question_id"] is None


@pytest.mark.asyncio
async def test_completed_quiz_does_not_restrict_public_explanations(store, monkeypatch):
    issued = await store.generate("student", "issue-finished", "vocab_basic", 0.5)
    quiz_id = issued["quiz"]["quiz_id"]
    correct_index = store.quiz("student", quiz_id)["correct_index"]
    await store.answer("student", "finish", quiz_id, correct_index, 10, None)
    observed = scripted(monkeypatch, [
        NativeTurn(content="submit a report 表示提交报告；submit a report to the teacher 指交给老师。",
                   stop_reason="stop"),
    ])
    result = await store.converse("student", "public-example", "vocab_basic",
                                  "解释 submit 的搭配并给完整例子。", quiz_id=quiz_id)
    facts = server_facts(observed[0])
    assert facts["response_contract"]["mode"] == "explanation"
    assert "quiz" not in facts
    assert "当前未结束练习" not in observed[0][0]["content"]
    assert "assistance" not in result
    assert result["execution"]["dialogue_state"] == "answered"


@pytest.mark.asyncio
async def test_cross_session_followup_contract_resolves_only_existing_question(store, monkeypatch):
    observed = scripted(monkeypatch, [
        call("goal", "ask_student", question="这次是找主旨还是具体细节？"),
        NativeTurn(content="先用目标里的关键词扫描定位，再读附近句子核对具体信息。",
                   stop_reason="stop"),
    ])
    first = await store.converse("student", "clarify-goal", "reading_skimming",
                                 "先问我阅读目标，再给方法。", session_id="before")
    second = await store.converse("student", "provide-goal", "reading_skimming",
                                  "这次只找某项具体信息。", session_id="after")
    facts = server_facts(observed[1])
    assert facts["response_contract"] == {
        "mode": "explanation", "continuation": "student_reply_to_pending_question",
    }
    assert facts["pending_question"]["id"] == first["execution"]["pending_question_id"]
    assert second["execution"]["answered_question_id"] == first["execution"]["pending_question_id"]
    assert second["execution"]["dialogue_state"] == "answered"
    assert second["execution"]["pending_question_id"] is None
    assert store.history.pending("student", second["execution"]["thread_id"]) is None


def test_prompt_policy_changes_configuration_fingerprint(monkeypatch):
    import core.versions as versions
    from config.settings import settings
    before = versions.config_fingerprint(settings)
    monkeypatch.setattr(versions, "TUTOR_POLICY_VERSION", "test-next-policy")
    assert versions.config_fingerprint(settings) != before


@pytest.mark.asyncio
async def test_missing_material_then_supplied_sentence_keeps_knowledge_unchanged(store, monkeypatch):
    before = store.orch.get_learner_model_sync("student").get_state("grammar_tenses").model_dump()
    observed = scripted(monkeypatch, [
        call("missing-material", "ask_student", question="请发来需要分析的原句。"),
        NativeTurn(content="since 指出过去的起点；你说明她现在仍住在这里，因此用现在完成时。",
                   stop_reason="stop"),
    ])
    first = await store.converse("student", "need-sentence", "grammar_tenses",
                                 "这句话为什么用这个时态？")
    second = await store.converse(
        "student", "sentence-provided", "grammar_tenses",
        "原句是 She has lived here since 2020. 她现在仍住在这里。",
    )
    assert first["execution"]["dialogue_state"] == "awaiting_student"
    assert first["execution"]["pending_question_id"]
    assert second["execution"]["dialogue_state"] == "answered"
    assert second["execution"]["answered_question_id"] == first["execution"]["pending_question_id"]
    assert server_facts(observed[0])["response_contract"]["continuation"] == "current_request"
    assert server_facts(observed[1])["response_contract"]["continuation"] == "student_reply_to_pending_question"
    assert store.orch.learner_models["student"].get_state("grammar_tenses").model_dump() == before
