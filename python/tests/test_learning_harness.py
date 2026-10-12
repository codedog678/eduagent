"""真实执行边界测试：权威判分、重放、回滚与检查点恢复。"""

import asyncio
import json
import sqlite3

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from api.orchestrator import AgentOrchestrator
from api.routes import router
from core.event_bus import Event, EventBus, EventType, ExecutionError
from core.harness import LearningHarness
from core.llm_service import get_llm_service


@pytest.fixture
def harness(tmp_path, monkeypatch):
    orch = AgentOrchestrator()
    orch.harness = LearningHarness(orch, str(tmp_path / "store.sqlite3"))
    # 测试执行日志不依赖 PostgreSQL；生产可从已有数据库导入。
    async def empty(learner, session=None):
        return None
    monkeypatch.setattr(orch.memory_manager, "_load_learner_from_db", empty)
    yield orch.harness
    orch.harness.close()


async def issue(harness, request="issue"):
    result = await harness.generate("student", request, "vocab_basic", 0.5)
    quiz_id = result["quiz"]["quiz_id"]
    quiz = harness.quiz("student", quiz_id)
    return quiz_id, quiz


@pytest.mark.asyncio
async def test_independent_retry_and_restart(harness):
    quiz_id, quiz = await issue(harness)
    right = quiz["correct_index"]
    first = await harness.answer("student", "first", quiz_id, (right + 1) % len(quiz["options"]), 10, 0.75)
    assert first["learning_evidence"]["mastery_updated"]
    assert "correct_answer" not in json.dumps(first)
    state = harness.capture("student")
    second = await harness.answer("student", "second", quiz_id, right, 20, None)
    assert second["evaluation"]["is_correct"]
    assert not second["learning_evidence"]["mastery_updated"]
    assert harness.capture("student")["knowledge"] == state["knowledge"]
    assert harness.capture("student")["reviews"] == state["reviews"]
    completed = harness.capture("student")
    path = str(harness.db.execute("PRAGMA database_list").fetchone()[2])
    harness.close()
    orch = AgentOrchestrator()
    restored = LearningHarness(orch, path)
    orch.harness = restored
    try:
        restored.load("student")
        assert restored.capture("student") == completed
        assert await restored.answer("student", "second", quiz_id, right, 20, None) == second
        with pytest.raises(HTTPException) as exc:
            await restored.answer("student", "third", quiz_id, right, 20, None)
        assert exc.value.status_code == 409
    finally:
        restored.close()
        # fixture 仍拥有资源，重新连接供其释放。
        harness.db = sqlite3.connect(path)
        harness._owner = open(path + ".lock", "a")


@pytest.mark.asyncio
async def test_concurrent_duplicate_and_conflict(harness):
    quiz_id, quiz = await issue(harness)
    results = await asyncio.gather(*[
        harness.answer("student", "same", quiz_id, quiz["correct_index"], 10, None)
        for _ in range(8)])
    assert all(result == results[0] for result in results)
    assert harness.orch.learner_models["student"].get_state("vocab_basic").attempts == 1
    with pytest.raises(HTTPException) as exc:
        await harness.answer("student", "same", quiz_id, 99, 10, None)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_hint_and_reveal_do_not_measure_mastery(harness):
    quiz_id, quiz = await issue(harness)
    hint = await harness.support("student", "hint", quiz_id, "hint")
    assert "correct_index" not in json.dumps(hint)
    assert quiz["options"][quiz["correct_index"]] not in hint["support"]["text"]
    result = await harness.answer("student", "answer", quiz_id, quiz["correct_index"], 10, None)
    assert not result["learning_evidence"]["mastery_updated"]
    assert harness.orch.learner_models["student"].get_state("vocab_basic").attempts == 0
    second_id, second = await issue(harness, "another")
    reveal = await harness.support("student", "reveal", second_id, "reveal")
    assert second["options"][second["correct_index"]] in reveal["support"]["text"]
    with pytest.raises(HTTPException):
        await harness.answer("student", "after-reveal", second_id, second["correct_index"], 1, None)


@pytest.mark.asyncio
async def test_handler_failure_rolls_back_and_can_retry(harness):
    quiz_id, quiz = await issue(harness)
    before = harness.capture("student")
    async def broken(event):
        raise ValueError("injected failure")
    harness.orch.event_bus.subscribe(EventType.ASSESSMENT_COMPLETE, broken)
    with pytest.raises(HTTPException) as exc:
        await harness.answer("student", "retry", quiz_id, quiz["correct_index"], 10, None)
    assert exc.value.status_code == 503
    assert harness.capture("student") == before
    assert harness.quiz("student", quiz_id)["attempts"] == 0
    harness.orch.event_bus.unsubscribe(EventType.ASSESSMENT_COMPLETE, broken)
    result = await harness.answer("student", "retry", quiz_id, quiz["correct_index"], 10, None)
    assert result["execution"]["status"] == "completed"
    assert harness.orch.learner_models["student"].get_state("vocab_basic").attempts == 1


@pytest.mark.asyncio
async def test_timeout_cancels_handler_and_rolls_back(harness):
    quiz_id, quiz = await issue(harness)
    cancelled = asyncio.Event()
    async def stalled(event):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    harness.orch.event_bus.subscribe(EventType.ASSESSMENT_COMPLETE, stalled)
    harness.timeout = 0.03
    before = harness.capture("student")
    with pytest.raises(HTTPException):
        await harness.answer("student", "timeout", quiz_id, quiz["correct_index"], 10, None)
    assert cancelled.is_set()
    assert harness.capture("student") == before


@pytest.mark.asyncio
async def test_event_cycle_budget_and_priority():
    bus = EventBus(max_steps=4)
    async def recurse(event):
        await bus.publish(Event(type=event.type, source="cycle", learner_id=event.learner_id))
    bus.subscribe(EventType.STUDENT_MESSAGE, recurse)
    with pytest.raises(ExecutionError, match="budget"):
        await bus.publish(Event(type=EventType.STUDENT_MESSAGE, source="test", learner_id="student"))
    assert len(bus.get_history()) == 4

    from core.event_bus import EventPriority
    ordered = EventBus()
    seen = []
    async def enqueue(event):
        for priority in (EventPriority.LOW, EventPriority.HIGH):
            await ordered.publish(Event(type=EventType.TEACHING_RESPONSE, source="test",
                                        learner_id="student", priority=priority))
    async def observe(event):
        seen.append(event.priority)
    ordered.subscribe(EventType.STUDENT_MESSAGE, enqueue)
    ordered.subscribe(EventType.TEACHING_RESPONSE, observe)
    await ordered.publish(Event(type=EventType.STUDENT_MESSAGE, source="test", learner_id="student"))
    assert seen == [EventPriority.HIGH, EventPriority.LOW]


@pytest.mark.asyncio
async def test_api_rejects_tampering_and_cross_learner(harness):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.orchestrator = harness.orch
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        issued = await client.post("/api/quiz/generate", json={
            "learner_id": "student", "request_id": "issue", "knowledge_id": "vocab_basic"})
        assert issued.status_code == 200
        public = issued.json()["quiz"]
        assert "correct_index" not in public and "explanation" not in public
        body = {"learner_id": "student", "request_id": "answer",
                "quiz_id": public["quiz_id"], "selected_index": 0}
        assert (await client.post("/api/quiz/answer", json={**body, "correct_answer": "forged"})).status_code == 422
        assert (await client.post("/api/quiz/answer", json={**body, "learner_id": "other"})).status_code == 404
        assert (await client.post("/api/quiz/answer", json={**body, "selected_index": 99})).status_code == 422
        assert (await client.post("/api/quiz/answer", json={**body, "request_id": "valid"})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [
    {"question": "test", "options": ["x", "y"], "correct_index": 8},
    {"question": "test", "options": ["x", "x"], "correct_index": 0},
    {"question": "test", "options": ["x", "y"], "correct_index": True},
])
async def test_malformed_question_does_not_get_issued(harness, monkeypatch, raw):
    async def malformed(*args):
        return raw
    monkeypatch.setattr(get_llm_service(), "generate_question", malformed)
    with pytest.raises(HTTPException):
        await issue(harness)
    assert harness.db.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0] == 0


def test_store_rejects_second_worker(harness):
    path = harness.db.execute("PRAGMA database_list").fetchone()[2]
    with pytest.raises(RuntimeError, match="one server worker"):
        LearningHarness(AgentOrchestrator(), path)


@pytest.mark.asyncio
async def test_advance_requires_prerequisites(harness):
    with pytest.raises(HTTPException) as exc:
        await harness.generate("student", "advance", "vocab_intermediate", 0.5, "advance")
    assert exc.value.status_code == 409
    assert harness.db.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["[]", '{"strategy":"delete"}', '{"summary":42}'])
async def test_malformed_teaching_decision_uses_policy(harness, monkeypatch, content):
    from types import SimpleNamespace
    from config.settings import settings
    monkeypatch.setattr(settings, "enable_agent_llm_decisions", True)
    async def malformed(*args):
        return SimpleNamespace(content=content)
    monkeypatch.setattr(get_llm_service(), "generate_teaching_decision", malformed)
    result = await harness.orch._build_teaching_decision("student", "vocab_basic", "submission", {})
    assert result["generation_mode"] == "local_policy"
