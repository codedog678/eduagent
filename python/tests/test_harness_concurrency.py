"""通过同步屏障验证真实交错执行，不依赖性能计时猜测并发。"""

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from api.orchestrator import AgentOrchestrator
from api.routes import router
from core.event_bus import Event, EventType
from core.harness import LearningHarness
from core.run_context import active_run


@pytest.fixture
def store(tmp_path):
    orch = AgentOrchestrator()
    orch.harness = LearningHarness(orch, str(tmp_path / "concurrent.sqlite3"), queue_timeout=.05)
    yield orch.harness
    orch.harness.close()


@asynccontextmanager
async def running(*coroutines):
    tasks = [asyncio.create_task(c) for c in coroutines]
    try:
        yield tasks
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_real_tutor_handlers_overlap_and_contexts_stay_isolated(store, monkeypatch):
    tutor = store.orch.tutor
    original = tutor.handle_event
    entered = {name: asyncio.Event() for name in ("alice", "bob")}

    async def handle(event):
        entered[event.learner_id].set()
        other = "bob" if event.learner_id == "alice" else "alice"
        await asyncio.wait_for(entered[other].wait(), 1)
        assert tutor.get_status()["active_tasks"] == 2
        assert active_run.get().learner == event.learner_id
        # 等双方都检查完状态后再开始真正的处理。
        await asyncio.sleep(0)
        return await original(event)

    monkeypatch.setattr(tutor, "handle_event", handle)
    async with running(*[
        store.converse(name, "same-request", "vocab_basic", f"{name} 询问词汇")
        for name in entered
    ]) as tasks:
        results = await asyncio.wait_for(asyncio.gather(*tasks), 2)
    assert all(r["execution"]["status"] == "completed" for r in results)
    assert results[0]["execution"]["run_id"] != results[1]["execution"]["run_id"]
    for name, result in zip(entered, results):
        rows = store.history.messages(name)["items"]
        assert len(rows) == 2 and rows[0]["content"] == f"{name} 询问词汇"
        assert all(e.learner_id == name for e in store.orch.event_bus.get_correlation_chain(
            result["execution"]["run_id"]))
    assert tutor.get_status()["active_tasks"] == 0
    assert tutor.get_status()["state"] == "idle"
    assert not store.learner_locks._entries and not tutor._learner_locks._entries
    assert active_run.get() is None


@pytest.mark.asyncio
async def test_same_learner_serialization_and_duplicate_replay(store):
    store.queue_timeout = 1
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def first():
        calls.append("first")
        entered.set()
        await release.wait()
        store.orch.learner_models["alice"].metadata["value"] = 1
        return {"value": 1}, None

    async def second():
        calls.append("second")
        assert store.orch.learner_models["alice"].metadata["value"] == 1
        return {"value": 2}, None

    async with running(store.run("alice", "a", {}, first)) as initial:
        await entered.wait()
        async with running(
            store.run("alice", "a", {}, first),
            store.run("alice", "b", {}, second),
        ) as pending:
            await asyncio.sleep(0)
            assert calls == ["first"]
            release.set()
            results = await asyncio.gather(*initial, *pending)
    assert results[0] == results[1] and calls == ["first", "second"]
    assert store.db.execute("SELECT count(*) FROM run_attempts").fetchone()[0] == 2
    with pytest.raises(HTTPException) as conflict:
        await store.run("alice", "a", {"changed": True}, first)
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exception", "cancel", "commit"])
async def test_failure_or_cancel_rolls_back_only_its_learner(store, failure):
    entered, bob_done = asyncio.Event(), asyncio.Event()
    store.orch.get_learner_model_sync("alice")
    before = json.loads(json.dumps(store.capture("alice")))
    if failure == "commit":
        store.db.execute(
            "CREATE TRIGGER reject_alice BEFORE INSERT ON checkpoints "
            "WHEN NEW.learner='alice' BEGIN SELECT RAISE(ABORT, 'injected'); END")

    async def alice():
        store.orch.learner_models["alice"].metadata["temporary"] = True
        entered.set()
        await bob_done.wait()
        if failure == "exception":
            raise ValueError("injected")
        if failure == "cancel":
            await asyncio.Event().wait()
        return {"value": "alice"}, None

    async def bob():
        store.orch.learner_models["bob"].metadata["committed"] = True
        return {"value": "bob"}, None

    async with running(store.run("alice", "a", {}, alice)) as tasks:
        await entered.wait()
        result = await asyncio.wait_for(store.run("bob", "b", {}, bob), 1)
        bob_done.set()
        if failure == "cancel":
            tasks[0].cancel()
        with pytest.raises(asyncio.CancelledError if failure == "cancel" else HTTPException):
            await tasks[0]
    assert result["value"] == "bob"
    assert store.capture("alice") == before
    assert store.capture("bob")["metadata"]["committed"]
    checkpoint = store.db.execute("SELECT state FROM checkpoints WHERE learner='bob'").fetchone()
    assert json.loads(checkpoint[0])["metadata"]["committed"]
    assert store.run_status("bob", "b")["status"] == "completed"
    assert store.run_status("alice", "a")["status"] == (
        "cancelled" if failure == "cancel" else "failed")
    assert not store.db.in_transaction and not store.learner_locks._entries


@pytest.mark.asyncio
async def test_learner_queue_timeout_is_http_503_and_can_retry(store):
    entered, release = asyncio.Event(), asyncio.Event()

    async def block():
        entered.set()
        await release.wait()
        return {}, None

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.orchestrator = store.orch
    body = {"learner_id": "alice", "request_id": "queued",
            "knowledge_id": "vocab_basic", "question": "词汇怎么学？"}
    async with running(store.run("alice", "first", {}, block)) as tasks:
        await entered.wait()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/question", json=body)
            assert response.status_code == 503
            assert "learner_queue_timeout" in response.json()["detail"]
            assert response.headers["retry-after"] == "1"
            assert store.db.execute(
                "SELECT count(*) FROM runs WHERE request='queued'").fetchone()[0] == 0
            release.set()
            await tasks[0]
            assert (await client.post("/api/question", json=body)).status_code == 200
    assert not store.learner_locks._entries


@pytest.mark.asyncio
async def test_cancelled_learner_waiter_does_not_execute_or_leak_lock(store):
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def block():
        entered.set()
        await release.wait()
        return {}, None

    async def queued():
        calls.append("called")
        return {}, None

    async with running(store.run("alice", "first", {}, block)) as initial:
        await entered.wait()
        async with running(store.run("alice", "queued", {}, queued)) as pending:
            await asyncio.sleep(0)
            pending[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending[0]
        assert not calls
        release.set()
        await initial[0]
    await store.run("alice", "queued", {}, queued)
    assert calls == ["called"] and not store.learner_locks._entries


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["session_id", "thread_id"])
async def test_concurrent_new_scope_collision_rechecked_at_commit(store, scope):
    arrived = 0
    both = asyncio.Event()

    async def operation():
        nonlocal arrived
        ctx = active_run.get()
        ctx.conversation = True
        arrived += 1
        if arrived == 2:
            both.set()
        await asyncio.wait_for(both.wait(), 1)
        return {"teaching_response": {"response": f"reply-{ctx.learner}"}}, None

    payload = {scope: "shared-new-id", "knowledge_id": "vocab_basic", "text": "question"}
    async with running(*[
        store.run(name, "request", payload, operation) for name in ("alice", "bob")
    ]) as tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1
    rejected = next(r for r in results if isinstance(r, HTTPException))
    assert rejected.status_code == 404
    table = "learning_sessions" if scope == "session_id" else "learning_threads"
    owner = store.db.execute(f"SELECT learner FROM {table} WHERE id='shared-new-id'").fetchone()[0]
    assert store.db.execute(
        "SELECT DISTINCT learner FROM conversation_messages").fetchall() == [(owner,)]


@pytest.mark.asyncio
async def test_current_events_survive_other_learners_history_eviction(store):
    store.orch.event_bus.MAX_HISTORY = 1
    emitted, other_done = asyncio.Event(), asyncio.Event()

    async def operation(name):
        await store.orch.event_bus.publish(Event(
            type=EventType.SESSION_START, learner_id=name, source="test"))
        if name == "alice":
            emitted.set()
            await other_done.wait()
        events = await store.orch._get_interaction_events(name, active_run.get().run_id)
        assert len(events) == 1 and events[0].learner_id == name
        return {}, None

    async with running(store.run("alice", "a", {}, lambda: operation("alice"))) as tasks:
        await emitted.wait()
        await asyncio.wait_for(store.run("bob", "b", {}, lambda: operation("bob")), 1)
        other_done.set()
        await tasks[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_tutor_failure_keeps_other_learners_committed_history(store, monkeypatch, cancel):
    entered, release = asyncio.Event(), asyncio.Event()
    original = store.orch.tutor.handle_event

    async def handle(event):
        if event.learner_id == "alice":
            await original(event)
            entered.set()
            await release.wait()
            raise ValueError("injected after local state mutation")
        return await original(event)

    monkeypatch.setattr(store.orch.tutor, "handle_event", handle)
    async with running(store.converse("alice", "failed", "vocab_basic", "alice 问词义")) as tasks:
        await asyncio.wait_for(entered.wait(), 1)
        result = await asyncio.wait_for(
            store.converse("bob", "ok", "vocab_basic", "bob 问词义"), 1)
        if cancel:
            tasks[0].cancel()
        else:
            release.set()
        with pytest.raises(asyncio.CancelledError if cancel else HTTPException):
            await tasks[0]
    assert result["execution"]["status"] == "completed"
    assert store.history.messages("alice")["items"] == []
    assert len(store.history.messages("bob")["items"]) == 2
    assert not store.orch.tutor._get_history("alice")
    assert store.orch.tutor._get_history("bob")
    trace = store.run_status("alice", "failed")["result"]["events"]
    assert trace and all(e["learner_id"] == "alice" for e in trace)
    assert not store.learner_locks._entries
    assert not store.orch.tutor._learner_locks._entries


def test_learner_ids_with_colon_cannot_overlap_tutor_checkpoint_scope(store):
    tutor = store.orch.tutor
    alice_key = tutor._build_attempt_key("alice", "vocab_basic", "question", "answer")
    bob_key = tutor._build_attempt_key("alice:team", "vocab_basic", "question", "answer")
    tutor._student_attempts.update({alice_key: 1, bob_key: 3})
    tutor._hint_history.update({alice_key: 1, bob_key: 2})
    before = json.loads(json.dumps(store.capture("alice")))
    assert tutor.get_hint_usage("alice") == 1
    assert tutor.get_hint_usage("alice:team") == 2
    assert len(before["agents"]["TutorAgent"]["student_attempts"]) == 1
    tutor._student_attempts[alice_key] = 9
    store.restore("alice", before)
    assert tutor._student_attempts[alice_key] == 1
    assert tutor._student_attempts[bob_key] == 3
    assert tutor._hint_history[bob_key] == 2
    # 持久化结构沿用旧版题目后缀，恢复旧检查点不需要迁移。
    assert before["agents"]["TutorAgent"]["student_attempts"] == {
        "vocab_basic:question:answer": 1}
