"""Real cleanup store checks retain their cause chains through durable workers."""
import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.orchestrator import AgentOrchestrator
from core.distributed import executor as executor_module
from core.distributed.executor import LearningTaskExecutor
from core.distributed.models import DistributedRunAttempt
from core.distributed.policy_health import (
    ConfirmedPermissionViolation, PolicyHealthEvaluator, PolicyObservationRecorder,
    server_diagnostic_code,
)
from core.distributed.promotion_repository import PromotionCommandRejected
from core.distributed.rehearsal_store import ShadowStoreRouter
from core.distributed.shadow_worker import ShadowWorker
from core.distributed.worker import RunWorker
from core.harness import LearningHarness, MemoryWorker
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_executor_exception_lifecycle import capability, unwrapped
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import admitted, real_active_fixture
from tests.distributed.test_policy_health_publication import advance


def permission_error(database, expected, outside, depth):
    database.execute("ATTACH DATABASE ? AS outside", (str(outside),))
    with database:
        database.execute("CREATE TABLE outside.marker (value TEXT)")
        database.execute("INSERT INTO outside.marker VALUES ('committed')")
    try:
        executor_module.assert_open_store_capability(database, expected)
    except ConfirmedPermissionViolation as hard:
        chain = [hard]
        for _ in range(depth):
            wrapper = RuntimeError("fixture cleanup wrapper")
            wrapper.__cause__ = chain[-1]
            chain.append(wrapper)
        return chain
    pytest.fail("actual outside attachment must fail the capability check")


def instrument(monkeypatch, tmp_path, *, cleanup, depth, hard=True, source=None,
               execution_hard=False, later_failures=False):
    source = ValueError("fixture ordinary execution failure") if source is None else source
    opened, events, chains, markers = [], [], [], []
    expected = []
    original_stop = MemoryWorker.stop
    original_close = LearningHarness.close
    original_database_close = AgentOrchestrator.close_database

    def checked_error(database):
        outside = tmp_path / f"outside-{len(markers)}.sqlite3"
        chain = permission_error(database, expected[0], outside, depth)
        chains.append(chain)
        markers.append(outside)
        return chain[-1]

    def cleanup_error(step):
        if step == cleanup:
            if not hard:
                return RuntimeError("fixture ordinary cleanup failure")
            if step in {"stop", "close"} and not execution_hard:
                return checked_error(opened[0].db)
            # Harness 已关闭；后续清理使用真实连接和同一固定路径做检查。
            with sqlite3.connect(expected[0]) as database:
                return checked_error(database)
        if later_failures:
            return ValueError("fixture later cleanup failure")
        return None

    async def converse(self, learner, request_id, knowledge, question, *args, **kwargs):
        opened.append(self)
        expected.append(Path(self.db.execute("PRAGMA database_list").fetchone()[2]).resolve())

        async def operation():
            if execution_hard:
                raise checked_error(self.db)
            raise source

        try:
            return await self.run(
                learner, request_id,
                {"kind": "task", "knowledge_id": knowledge, "text": question}, operation,
            )
        except HTTPException as exc:
            if exc.__cause__ is source or (
                exc.__cause__ is not None
                and server_diagnostic_code(exc.__cause__) == "ConfirmedPermissionViolation"
            ):
                raise exc.__cause__
            raise

    async def stop(self):
        events.append("stop")
        await original_stop(self)
        error = cleanup_error("stop")
        if error is not None:
            raise error

    def close(self):
        events.append("close")
        try:
            error = cleanup_error("close")
        finally:
            original_close(self)
        if error is not None:
            raise error

    async def database_close(self):
        events.append("database")
        await original_database_close(self)
        error = cleanup_error("database")
        if error is not None:
            raise error

    async def usage(run_id, token, summary):
        events.append("usage")
        error = cleanup_error("usage")
        if error is not None:
            raise error

    monkeypatch.setattr(LearningHarness, "converse", converse)
    monkeypatch.setattr(MemoryWorker, "stop", stop)
    monkeypatch.setattr(LearningHarness, "close", close)
    monkeypatch.setattr(AgentOrchestrator, "close_database", database_close)
    return source, opened, events, chains, markers, usage


def assert_chains(chains, markers):
    for chain in chains:
        assert chain[0].__cause__ is None
        for cause, wrapper in zip(chain, chain[1:]):
            assert wrapper.__cause__ is cause
    for outside in markers:
        with sqlite3.connect(outside) as database:
            assert database.execute("SELECT value FROM marker").fetchall() == [("committed",)]


@pytest.mark.parametrize("cleanup", ["stop", "close", "database", "usage"])
@pytest.mark.parametrize("depth", [0, 1, 3])
@pytest.mark.parametrize("source_kind", ["value", "cancel"])
async def test_cleanup_hard_keeps_actual_cause_chain_and_source_note(
    capability, tmp_path, monkeypatch, cleanup, depth, source_kind,
):
    executor, pinned, granted, mode = capability
    source = asyncio.CancelledError() if source_kind == "cancel" else ValueError("execution failed")
    source, _, events, chains, markers, usage = instrument(
        monkeypatch, tmp_path, cleanup=cleanup, depth=depth, source=source,
        later_failures=True,
    )
    if mode == "primary":
        executor.usage_recorder = usage
    with pytest.raises(BaseException) as caught:
        await executor.execute(spec(), granted, pinned)
    if cleanup == "usage" and mode == "shadow":
        # Shadow 没有 primary 用量通知，仍须保留原失败或取消。
        assert unwrapped(caught.value) is source
        assert not chains
    else:
        assert server_diagnostic_code(caught.value) == "ConfirmedPermissionViolation"
        assert unwrapped(caught.value) is chains[0][-1]
        assert any(type(source).__name__ in note for note in chains[0][-1].__notes__)
    assert events == ["stop", "close", "database"] + (["usage"] if mode == "primary" else [])
    assert_chains(chains, markers)


@pytest.mark.parametrize("cleanup", ["stop", "close", "database", "usage"])
async def test_existing_execution_hard_remains_prioritized_over_cleanup_hard(
    capability, tmp_path, monkeypatch, cleanup,
):
    executor, pinned, granted, mode = capability
    _, _, events, chains, markers, usage = instrument(
        monkeypatch, tmp_path, cleanup=cleanup, depth=2, execution_hard=True,
        later_failures=True,
    )
    if mode == "primary":
        executor.usage_recorder = usage
    with pytest.raises(Exception) as caught:
        await executor.execute(spec(), granted, pinned)
    assert unwrapped(caught.value) is chains[0][-1]
    assert server_diagnostic_code(caught.value) == "ConfirmedPermissionViolation"
    assert events == ["stop", "close", "database"] + (["usage"] if mode == "primary" else [])
    assert_chains(chains, markers)


@pytest.mark.parametrize("cleanup", ["stop", "close", "database", "usage"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_ordinary_cleanup_does_not_invent_hard_or_replace_source(
    capability, tmp_path, monkeypatch, cleanup, cancel,
):
    executor, pinned, granted, mode = capability
    source = asyncio.CancelledError() if cancel else ValueError("ordinary execution")
    _, _, events, chains, markers, usage = instrument(
        monkeypatch, tmp_path, cleanup=cleanup, depth=3, hard=False, source=source,
    )
    if mode == "primary":
        executor.usage_recorder = usage
    with pytest.raises(BaseException) as caught:
        await executor.execute(spec(), granted, pinned)
    assert unwrapped(caught.value) is source
    assert server_diagnostic_code(caught.value) != "ConfirmedPermissionViolation"
    assert not chains and not markers
    assert events == ["stop", "close", "database"] + (["usage"] if mode == "primary" else [])


async def run_cleanup_terminal(
    health_repo, tmp_path, monkeypatch, broker, stage, max_attempts, cleanup, depth, hard,
    *, publish=True,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    repo, promotion, deployment = fixture
    source, opened, events, chains, markers, usage = instrument(
        monkeypatch, tmp_path, cleanup=cleanup, depth=depth, hard=hard,
    )
    parent, _ = await admitted(
        fixture, "cleanup-cause", cohort="stable" if stage == "shadow" else "candidate",
    )
    recorder = PolicyObservationRecorder(repo.session_factory) if publish else None
    if stage == "shadow":
        claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
        await repo.transition_committing(parent.id, claim.fencing_token)
        primary = await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
        router = ShadowStoreRouter(tmp_path / "shadow")
        worker = ShadowWorker(
            "shadow", promotion, LearningTaskExecutor(None, shadow_store_router=router),
            router, policy_assigner=repo.policy_assigner, observation_recorder=recorder,
        )
        assert await worker.run_once()
        terminal = await promotion.enqueue_shadow(parent.id)
        assert terminal.status == "failed"
        code, ledger = terminal.error_code, terminal.result
        source_id = terminal.shadow_id
        observation = await recorder.record_shadow(source_id) if publish else None
        assert (await repo.get(parent.id)).public_dict() == primary.public_dict()
        assert not router._locks
        assert not router.path_for(opened[0].pinned_policy).exists()
    else:
        async def record_usage(run_id, token, summary):
            await repo.record_attempt_usage(run_id, token, summary)
            await usage(run_id, token, summary)

        worker = RunWorker(
            "primary", repo, broker,
            LearningTaskExecutor(
                str(tmp_path / "production.sqlite3"), allowed_environment="rehearsal",
                rehearsal_store_root=str(tmp_path / "rehearsal"), usage_recorder=record_usage,
            ),
            lease_seconds=30, heartbeat_seconds=.01, max_attempts=max_attempts,
            allowed_environment="rehearsal", observation_recorder=recorder,
        )
        await broker.publish("cleanup-cause", {"run_id": parent.id})
        assert await worker.run_once()
        terminal = await repo.get(parent.id)
        assert terminal.status == "terminal_failed"
        code = terminal.error_code
        async with repo.session_factory() as session:
            attempts = (await session.scalars(select(DistributedRunAttempt).where(
                DistributedRunAttempt.run_id == parent.id,
            ))).all()
        assert len(attempts) == 1
        assert attempts[0].status == "terminal_failed" and attempts[0].reason == code
        ledger = attempts[0].usage_summary
        source_id = parent.id
        observation = await recorder.record_run(source_id) if publish else None
    assert len(opened) == 1
    assert events == ["stop", "close", "database"] + (["usage"] if stage == "canary" else [])
    assert ledger["model_calls"] == ledger["tool_calls"] == 0
    assert ledger["input_tokens"] == ledger["output_tokens"] == 0
    assert ledger["cost"] is None
    assert ledger["structured_decision_count"] == ledger["unknown_decision_count"] == 0
    assert code == (
        "ConfirmedPermissionViolation" if hard and not (stage == "shadow" and cleanup == "usage")
        else "execution_failed" if stage == "shadow" else type(source).__name__
    )
    assert_chains(chains, markers)
    return fixture, source_id, opened[0].pinned_policy, observation


@pytest.mark.distributed_integration
@pytest.mark.parametrize("stage,max_attempts", [("canary", 1), ("canary", 3), ("shadow", 3)])
@pytest.mark.parametrize("cleanup", ["stop", "close", "database", "usage"])
@pytest.mark.parametrize("depth,hard", [(0, True), (1, True), (3, True), (3, False)])
async def test_live_cleanup_permission_terminal_rejects_promotion_without_retry(
    health_repo, tmp_path, monkeypatch, broker, stage, max_attempts, cleanup, depth, hard,
):
    fixture, _, _, observation = await run_cleanup_terminal(
        health_repo, tmp_path, monkeypatch, broker, stage, max_attempts, cleanup, depth, hard,
    )
    _, promotion, deployment = fixture
    if hard and not (stage == "shadow" and cleanup == "usage"):
        assert observation.terminal_status == "confirmed_permission_violation"
        assert observation.permission_outcome == "confirmed_violation"
        with pytest.raises(PromotionCommandRejected):
            await promotion.transition(advance(deployment))
        window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
        assert window.decision == "fail"
        assert observation.observation_key in window.observation_keys["candidate"]
        assert (await promotion.get_head("rehearsal")).state == (
            "shadow" if stage == "shadow" else "rolled_back"
        )
    else:
        assert observation.terminal_status == "terminal_failed"
        assert observation.permission_outcome == ("isolated" if stage == "shadow" else "not_applicable")
        assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "hold"


@pytest.mark.distributed_integration
@pytest.mark.parametrize("stage", ["canary", "shadow"])
@pytest.mark.parametrize("cleanup", ["stop", "close"])
async def test_recovered_nested_cleanup_hard_invalidates_consumed_active_pass(
    health_repo, tmp_path, monkeypatch, broker, stage, cleanup,
):
    fixture, source_id, old_binding, observation = await run_cleanup_terminal(
        health_repo, tmp_path, monkeypatch, broker, stage, 3, cleanup, 3, True, publish=False,
    )
    assert observation is None
    repo, promotion, source = fixture
    canary = source
    if stage == "shadow":
        canary = await promotion.transition(advance(source))
        await fill_window(
            (repo, promotion, canary), changes={"observed_at": datetime.now(UTC)},
            stable_changes={"observed_at": datetime.now(UTC)},
        )
        assert (await PolicyHealthEvaluator(promotion).evaluate(canary.deployment_id)).decision == "pass"
    active = await promotion.transition(advance(canary))
    pinned, _ = await admitted((repo, promotion, active), "old-active", cohort="candidate")
    await fill_window(
        (repo, promotion, active), state="active", stable_count=0,
        changes={"observed_at": datetime.now(UTC) + timedelta(seconds=1)},
    )
    evaluator = PolicyHealthEvaluator(promotion)
    assert (await evaluator.evaluate(active.deployment_id)).decision == "pass"
    recorder = PolicyObservationRecorder(repo.session_factory)
    assert await recorder.recover() >= 1
    assert await recorder.recover() == 0
    observation = await (recorder.record_shadow(source_id) if stage == "shadow"
                         else recorder.record_run(source_id))
    assert observation.deployment_id == old_binding.deployment_id
    assert observation.permission_outcome == "confirmed_violation"
    window = await evaluator.evaluate(active.deployment_id)
    assert window.decision == "fail"
    assert window.observation_keys["hard_failures"] == [observation.observation_key]
    head = await promotion.get_head("rehearsal")
    assert head.state == "rolled_back"
    claim = await repo.claim(pinned.id, "old", 30, allowed_environment="rehearsal")
    assert claim.policy_binding.deployment_id == active.deployment_id
    assert claim.policy_binding.policy_cohort == "candidate"
    fresh, _ = await admitted((repo, promotion, head), "new-stable")
    assert fresh.policy_cohort == "stable"
    assert fresh.effective_policy_hash == active.stable_policy_hash
