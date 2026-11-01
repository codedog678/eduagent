"""Shared executor exception precedence and cleanup, with real SQLite stores."""
import asyncio
import sqlite3
from uuid import uuid4

import pytest

from api.orchestrator import AgentOrchestrator
from core.distributed import executor as executor_module
from core.distributed.executor import LearningTaskExecutor, ShadowExecutionError
from core.distributed.policy_health import ConfirmedPermissionViolation, server_diagnostic_code
from core.distributed.rehearsal_store import ShadowStoreRouter
from core.harness import LearningHarness, MemoryWorker
from tests.distributed.helpers import authority, spec
from tests.distributed.test_policy_pinning import binding


@pytest.fixture(params=["primary", "shadow"])
def capability(request, tmp_path):
    pinned = binding()
    granted = authority()
    lock = None
    if request.param == "shadow":
        pinned = pinned.model_copy(update={
            "policy_cohort": "shadow",
            "state_namespace": f"shadow-{pinned.deployment_id}-{uuid4()}",
        })
        granted = granted.model_copy(update={
            "execution_mode": "shadow", "policy_cohort": "shadow",
            "state_namespace": pinned.state_namespace,
        })
        router = ShadowStoreRouter(tmp_path / "shadow")
        lock = router.try_lock(pinned)
        executor = LearningTaskExecutor(None, shadow_store_router=router)
    else:
        executor = LearningTaskExecutor(str(tmp_path / "primary.sqlite3"))
    try:
        yield executor, pinned, granted, request.param
    finally:
        if lock is not None:
            lock.cleanup()
            lock.close()


def unwrapped(exc):
    return exc.__cause__ if isinstance(exc, ShadowExecutionError) else exc


@pytest.mark.parametrize("cleanup", [None, "stop", "close", "database"])
@pytest.mark.parametrize("kind", ["value", "cancel", "unavailable", "constructor"])
async def test_clean_exception_and_unknown_capability_do_not_invent_hard_failure(
    capability, monkeypatch, kind, cleanup,
):
    executor, pinned, granted, mode = capability
    source = asyncio.CancelledError() if kind == "cancel" else ValueError("ordinary failure")
    closed = []
    original_close = LearningHarness.close
    original_stop = MemoryWorker.stop
    original_database_close = AgentOrchestrator.close_database

    async def converse(self, *args, **kwargs):
        if kind == "unavailable":
            self.db.close()
        raise source

    def close(self):
        closed.append(self)
        original_close(self)
        if cleanup == "close":
            raise ValueError("ordinary close failure")

    async def stop(self):
        await original_stop(self)
        if cleanup == "stop":
            raise asyncio.CancelledError()

    async def close_database(self):
        await original_database_close(self)
        if cleanup == "database":
            raise ValueError("ordinary database cleanup failure")

    def failed_constructor(*args, **kwargs):
        raise source

    monkeypatch.setattr(LearningHarness, "converse", converse)
    monkeypatch.setattr(LearningHarness, "close", close)
    monkeypatch.setattr(MemoryWorker, "stop", stop)
    monkeypatch.setattr(AgentOrchestrator, "close_database", close_database)
    if kind == "constructor":
        monkeypatch.setattr(executor_module, "LearningHarness", failed_constructor)
    with pytest.raises(BaseException) as caught:
        await executor.execute(spec(), granted, pinned)
    assert unwrapped(caught.value) is source
    assert server_diagnostic_code(caught.value) != "ConfirmedPermissionViolation"
    assert len(closed) == (0 if kind == "constructor" else 1)
    if kind == "cancel":
        assert isinstance(caught.value, asyncio.CancelledError)
    else:
        assert isinstance(caught.value, ShadowExecutionError if mode == "shadow" else ValueError)


async def test_initial_wrong_store_check_still_blocks_execution(capability, tmp_path, monkeypatch):
    executor, pinned, granted, _ = capability
    original = executor_module.LearningHarness
    called = []

    def wrong_store(orchestrator, path, *args, **kwargs):
        return original(orchestrator, str(tmp_path / "wrong.sqlite3"), *args, **kwargs)

    async def converse(self, *args, **kwargs):
        called.append(self)

    monkeypatch.setattr(executor_module, "LearningHarness", wrong_store)
    monkeypatch.setattr(LearningHarness, "converse", converse)
    with pytest.raises(Exception) as caught:
        await executor.execute(spec(), granted, pinned)
    assert server_diagnostic_code(caught.value) == "ConfirmedPermissionViolation"
    assert not called


@pytest.mark.parametrize("source_kind", ["value", "cancel"])
@pytest.mark.parametrize("cleanup", [None, "stop", "close", "database"])
async def test_confirmed_violation_keeps_source_cause_before_all_cleanup(
    capability, tmp_path, monkeypatch, source_kind, cleanup,
):
    executor, pinned, granted, mode = capability
    outside = tmp_path / "outside.sqlite3"
    source = ValueError("execution failed") if source_kind == "value" else asyncio.CancelledError()
    events = []
    original_check = executor_module.assert_open_store_capability
    original_stop, original_close = MemoryWorker.stop, LearningHarness.close
    original_database_close = AgentOrchestrator.close_database

    def check(database, expected):
        events.append("check")
        original_check(database, expected)

    async def converse(self, *args, **kwargs):
        self.db.execute("ATTACH DATABASE ? AS outside", (str(outside),))
        with self.db:
            self.db.execute("CREATE TABLE outside.marker (value TEXT)")
            self.db.execute("INSERT INTO outside.marker VALUES ('committed')")
        raise source

    async def stop(self):
        events.append("stop")
        await original_stop(self)
        if cleanup == "stop":
            raise asyncio.CancelledError()

    def close(self):
        events.append("close")
        original_close(self)
        if cleanup == "close":
            raise ValueError("close failed")

    async def close_database(self):
        events.append("database")
        await original_database_close(self)
        if cleanup == "database":
            raise ValueError("database cleanup failed")

    monkeypatch.setattr(executor_module, "assert_open_store_capability", check)
    monkeypatch.setattr(LearningHarness, "converse", converse)
    monkeypatch.setattr(MemoryWorker, "stop", stop)
    monkeypatch.setattr(LearningHarness, "close", close)
    monkeypatch.setattr(AgentOrchestrator, "close_database", close_database)
    with pytest.raises(Exception) as caught:
        await executor.execute(spec(), granted, pinned)
    hard = unwrapped(caught.value)
    assert isinstance(hard, ConfirmedPermissionViolation)
    assert hard.__cause__ is source
    assert isinstance(caught.value, ShadowExecutionError if mode == "shadow" else ConfirmedPermissionViolation)
    assert events == ["check", "check", "stop", "close", "database"]
    with sqlite3.connect(outside) as database:
        assert database.execute("SELECT value FROM marker").fetchall() == [("committed",)]


@pytest.mark.parametrize("write", [False, True])
async def test_external_cancellation_checks_live_store_before_close(
    capability, tmp_path, monkeypatch, write,
):
    executor, pinned, granted, _ = capability
    started = asyncio.Event()
    outside = tmp_path / "external-cancel.sqlite3"
    cancelled = []
    closed = []
    original_close = LearningHarness.close

    async def converse(self, *args, **kwargs):
        if write:
            self.db.execute("ATTACH DATABASE ? AS outside", (str(outside),))
            with self.db:
                self.db.execute("CREATE TABLE outside.marker (value TEXT)")
                self.db.execute("INSERT INTO outside.marker VALUES ('committed')")
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError as exc:
            cancelled.append(exc)
            raise

    def close(self):
        closed.append(list(self.db.execute("PRAGMA database_list")))
        original_close(self)

    monkeypatch.setattr(LearningHarness, "converse", converse)
    monkeypatch.setattr(LearningHarness, "close", close)
    task = asyncio.create_task(executor.execute(spec(), granted, pinned))
    try:
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        with pytest.raises(BaseException) as caught:
            await task
        assert len(cancelled) == len(closed) == 1
        if write:
            hard = unwrapped(caught.value)
            assert isinstance(hard, ConfirmedPermissionViolation)
            assert hard.__cause__ is cancelled[0]
            assert any(filename == str(outside) for _, _, filename in closed[0])
        else:
            assert isinstance(caught.value, asyncio.CancelledError)
            assert caught.value is cancelled[0]
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
