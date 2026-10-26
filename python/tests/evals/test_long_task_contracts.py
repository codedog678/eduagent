"""D01-D08：长任务真实模型执行前的确定性 Harness 合同。"""

from __future__ import annotations

import json
import sqlite3
import time

import httpx
import pytest
from fastapi import HTTPException

from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.coordination_models import AgentResult, LearningPlan
from core.coordinator import Coordinator
from core.harness import LearningHarness
from core.llm_service import NativeToolCall, get_llm_service
from core.run_context import active_run
from core.tool_executor import ToolExecutor
from tests.test_coordinator_runtime import Model, final
from tests.test_memory_coordination import context, remote_plan, seed


@pytest.fixture
def store(tmp_path, monkeypatch):
    from core.memory_manager import MemoryManager

    async def no_database(*args):
        return None

    monkeypatch.setattr(MemoryManager, "_load_learner_from_db", no_database)
    monkeypatch.setattr(settings, "memory_embedding_api_key", "")
    monkeypatch.setattr(settings, "siliconflow_api_key", "")
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    orchestrator = AgentOrchestrator()
    harness = LearningHarness(orchestrator, str(tmp_path / "contracts.sqlite3"))
    orchestrator.harness = harness
    yield harness
    if getattr(harness, "db", None):
        harness.close()


def _steps(store, learner, request):
    return store.history.trace(learner, request)["attempts"][-1]["steps"]


@pytest.mark.asyncio
async def test_d01_atomic_three_agent_chain(store, monkeypatch):
    roles = []

    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        roles.append(task)
        return final(task)

    model = Model(handler)
    model.install(monkeypatch)
    result = await store.converse(
        "d01", "d01-request", "vocab_basic", "结合上次错误制定复习计划"
    )
    plan = result["learning_plan"]
    assert roles == ["a", "c"]
    assert [step["status"] for step in plan["steps"]] == ["completed"] * 3
    assert plan["outcome"] == "completed"
    assert store.db.execute(
        "SELECT count(*) FROM learning_plans WHERE learner_id='d01'"
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT count(*) FROM checkpoints WHERE learner='d01'"
    ).fetchone()[0] == 1
    persisted = _steps(store, "d01", "d01-request")
    completed = [step.get("task_id") for step in persisted if step["kind"] == "agent_completed"]
    assert completed == ["a", "c", "t"]
    assert persisted[-1]["kind"] == "run_completed"


@pytest.mark.asyncio
async def test_d02_bounded_replan(store, monkeypatch):
    roles = []

    def handler(messages, tools):
        task = json.loads(messages[1]["content"])["task"]["step_id"]
        roles.append(task)
        return final(task, status="failed") if task == "a" else final(task)

    model = Model(handler, revision={
        "reason": "诊断失败，改为保守课程安排",
        "steps": [
            {"step_id": "new-c", "agent": "Curriculum", "objective": "按当前知识安排"},
            {"step_id": "new-t", "agent": "Tutor", "objective": "说明证据缺口",
             "depends_on": ["new-c"]},
        ],
    })
    model.install(monkeypatch)
    result = await store.converse(
        "d02", "d02-request", "vocab_basic", "根据错误制定复习计划"
    )
    plan = result["learning_plan"]
    assert roles == ["a", "new-c"]
    assert len(plan["revisions"]) == 1
    assert plan["steps"][0]["status"] == "failed"
    assert plan["results"]["new-c"]["status"] == "completed"
    trace = _steps(store, "d02", "d02-request")
    assert len([step for step in trace if step["kind"] == "plan_revised"]) == 1
    assert trace[-1]["kind"] == "run_completed"


@pytest.mark.asyncio
async def test_d03_read_retry_write_no_retry(store, monkeypatch):
    attempts = {"read": 0, "write": 0}

    async def read_operation():
        ctx = active_run.get()
        executor = ToolExecutor(ctx)

        async def transient(name, params):
            attempts["read"] += 1
            raise httpx.ConnectError("injected")

        monkeypatch.setattr(executor, "dispatch", transient)
        result = await executor.execute(NativeToolCall(
            id="read", name="get_knowledge_context", arguments="{}"
        ))
        return {"status": result["status"]}, None

    result = await store.run(
        "d03", "d03-read", {"kind": "contract", "knowledge": "vocab_basic"},
        read_operation,
    )
    assert result["status"] == "transient_error" and attempts["read"] == 2
    read_steps = _steps(store, "d03", "d03-read")
    assert len([step for step in read_steps if step["kind"] == "tool_retry"]) == 1

    async def write_operation():
        ctx = active_run.get()

        async def prepare(**kwargs):
            return {"quiz_id": "never"}

        ctx.prepare_practice = prepare
        executor = ToolExecutor(ctx, role="Coordinator")

        async def transient(name, params):
            attempts["write"] += 1
            raise httpx.ConnectError("injected")

        monkeypatch.setattr(executor, "dispatch", transient)
        result = await executor.execute(NativeToolCall(
            id="write", name="prepare_practice",
            arguments='{"knowledge_id":"vocab_basic","difficulty":0.5}',
        ))
        return {"status": result["status"]}, None

    result = await store.run(
        "d03", "d03-write", {"kind": "contract-write", "knowledge": "vocab_basic"},
        write_operation,
    )
    assert result["status"] == "transient_error" and attempts["write"] == 1
    assert not [step for step in _steps(store, "d03", "d03-write")
                if step["kind"] == "tool_retry"]


@pytest.mark.asyncio
async def test_d04_commit_failure_zero_residue(store, monkeypatch):
    Model(lambda messages, tools: final(
        json.loads(messages[1]["content"])["task"]["step_id"]
    )).install(monkeypatch)
    before = store.capture("d04") if "d04" in store.orch.learner_models else None
    original = store.history.commit_conversation

    def fail(*args):
        original(*args)
        raise OSError("injected")

    monkeypatch.setattr(store.history, "commit_conversation", fail)
    with pytest.raises(HTTPException):
        await store.converse("d04", "d04-request", "vocab_basic", "安排复习计划")
    for table, field in (
        ("learning_plans", "learner_id"), ("conversation_messages", "learner"),
        ("quizzes", "learner"), ("learning_evidence", "learner"),
    ):
        assert store.db.execute(
            f"SELECT count(*) FROM {table} WHERE {field}='d04'"
        ).fetchone()[0] == 0
    assert store.db.execute(
        "SELECT status FROM run_attempts WHERE learner='d04'"
    ).fetchone()[0] == "failed"
    assert _steps(store, "d04", "d04-request")[-1]["kind"] == "run_failed"
    if before is not None:
        assert store.capture("d04") == before


@pytest.mark.asyncio
async def test_d05_idempotent_replay_and_conflict(store):
    payload = ("d05", "d05-request", "vocab_basic", "结合上次错误安排复习")
    first = await store.converse(*payload)
    counts = {
        table: store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("learning_plans", "conversation_messages", "run_attempts", "run_steps")
    }
    assert await store.converse(*payload) == first
    assert counts == {
        table: store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in counts
    }
    with pytest.raises(HTTPException) as conflict:
        await store.converse(
            "d05", "d05-request", "vocab_basic", "给同一 request_id 不同内容"
        )
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_d06_restart_marks_interruption_and_resumes_plan(store, monkeypatch):
    remote_plan(monkeypatch, needs_input=True)
    first = await store.converse("d06", "d06-start", "vocab_basic", "安排复习计划")
    assert first["learning_plan"]["status"] == "awaiting_student"
    checkpoint = store.db.execute(
        "SELECT state FROM checkpoints WHERE learner='d06'"
    ).fetchone()[0]
    with store.db:
        store.db.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            ("d06", "interrupted", "fingerprint", "running", None, None, time.time()),
        )
        store.db.execute(
            "INSERT INTO run_attempts "
            "(id,learner,request,run,status,started) VALUES (?,?,?,?,?,?)",
            ("interrupted-attempt", "d06", "interrupted", "interrupted-run",
             "running", time.time()),
        )
    path = store.db.execute("PRAGMA database_list").fetchone()[2]
    store.close()
    store.db = None
    orchestrator = AgentOrchestrator()
    restored = LearningHarness(orchestrator, path)
    orchestrator.harness = restored
    try:
        assert restored.db.execute(
            "SELECT status,reason FROM run_attempts WHERE id='interrupted-attempt'"
        ).fetchone() == ("failed", "interrupted")
        assert restored.db.execute(
            "SELECT state FROM checkpoints WHERE learner='d06'"
        ).fetchone()[0] == checkpoint
        remote_plan(monkeypatch)
        second = await restored.converse(
            "d06", "d06-resume", "vocab_basic", "每天十分钟", session_id="new-session"
        )
        assert second["learning_plan"]["plan_id"] == first["learning_plan"]["plan_id"]
        assert second["learning_plan"]["version"] == 2
        assert second["execution"]["thread_id"] == first["execution"]["thread_id"]
    finally:
        restored.close()
        store.db = sqlite3.connect(path)
        store._owner = open(path + ".lock", "a")


@pytest.mark.asyncio
async def test_d07_stale_source_invalidates_dependents(store):
    valid = seed(store.db, "d07", "valid", "有效来源")
    stale = seed(store.db, "d07", "stale", "即将删除的来源")
    plan = LearningPlan(goal="复习", steps=[
        {"step_id": "a", "agent": "Assessment", "objective": "诊断"},
        {"step_id": "c", "agent": "Curriculum", "objective": "安排", "depends_on": ["a"]},
        {"step_id": "t", "agent": "Tutor", "objective": "总结", "depends_on": ["c"],
         "status": "waiting"},
    ])
    for step, refs in zip(plan.steps[:2], ([valid], [stale])):
        step.status = "completed"
        plan.results[step.step_id] = AgentResult(
            task_id=step.step_id, status="completed", findings=["完成"], source_refs=refs
        )
    with store.db:
        store.db.execute("DELETE FROM conversation_messages WHERE id='stale'")

    async def operation():
        ctx = active_run.get()
        ctx.history = store.history
        resumed = Coordinator(ctx, None).restore_plan(plan.model_dump(), "继续")
        return {"statuses": [step.status for step in resumed.steps],
                "results": sorted(resumed.results)}, None

    result = await store.run(
        "d07", "d07-restore", {"kind": "restore", "knowledge": "vocab_basic"},
        operation,
    )
    assert result["statuses"] == ["completed", "pending", "pending"]
    assert result["results"] == ["a"]
    kinds = [step["kind"] for step in _steps(store, "d07", "d07-restore")]
    assert "agent_result_reused" in kinds and "agent_result_invalidated" in kinds


@pytest.mark.asyncio
async def test_d08_cross_knowledge_practice_completes_plan(store, monkeypatch):
    remote_plan(monkeypatch, practice=True)
    first = await store.converse(
        "d08", "d08-prepare", "grammar_tenses", "安排基础词汇练习"
    )
    quiz_id = first["prepared_practice"]["quiz_id"]
    quiz = store.quiz("d08", quiz_id)
    assert quiz["knowledge_id"] == "vocab_basic"
    monkeypatch.setattr(get_llm_service(), "_has_remote_llm", lambda: False)
    answer = await store.answer(
        "d08", "d08-answer", quiz_id, quiz["correct_index"], 10, None
    )
    assert not answer["learning_evidence"]["independent"]
    plan = json.loads(store.db.execute(
        "SELECT body FROM learning_plans WHERE learner_id='d08'"
    ).fetchone()[0])
    assert plan["status"] == "completed"
    evidence = store.db.execute(
        "SELECT thread,body FROM learning_evidence "
        "WHERE learner='d08' AND kind='assessment'"
    ).fetchone()
    assert evidence[0] == quiz["thread_id"]
    assert json.loads(evidence[1])["knowledge_id"] == "vocab_basic"
    assert _steps(store, "d08", "d08-answer")[-1]["kind"] == "run_completed"
