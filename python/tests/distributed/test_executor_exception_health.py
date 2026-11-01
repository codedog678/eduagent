"""Actual SQLite outside writes on exceptional exits, through durable workers."""
import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.orchestrator import AgentOrchestrator
from core.distributed import executor as executor_module
from core.distributed.models import DistributedRunAttempt
from core.distributed.policy_health import PolicyHealthEvaluator, PolicyObservationRecorder
from core.distributed.promotion_repository import PromotionCommandRejected
from core.distributed.rehearsal_store import ShadowStoreRouter
from core.distributed.shadow_worker import ShadowWorker
from core.distributed.worker import RunWorker
from core.harness import LearningHarness, MemoryWorker
from tests.distributed.helpers import business_result
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import admitted, real_active_fixture
from tests.distributed.test_policy_health_publication import advance

pytestmark = pytest.mark.distributed_integration


def server_operation(monkeypatch, outside, *, write=True, exit_kind="value", cleanup=None):
    opened, closed = [], []
    original_close = LearningHarness.close
    original_stop = MemoryWorker.stop
    original_database_close = AgentOrchestrator.close_database

    async def converse(self, learner, request_id, knowledge, question, *args, **kwargs):
        opened.append(self)

        async def operation():
            if write:
                self.db.execute("ATTACH DATABASE ? AS outside", (str(outside),))
                with self.db:
                    self.db.execute("CREATE TABLE outside.marker (value TEXT)")
                    self.db.execute("INSERT INTO outside.marker VALUES ('committed')")
            if exit_kind == "value":
                raise ValueError("fixture execution failed after store operation")
            if exit_kind == "cancel":
                raise asyncio.CancelledError()
            return business_result(self.pinned_policy), None

        # Keep real Harness failure handling and finally-exported usage. No model calls.
        try:
            return await self.run(
                learner, request_id,
                {"kind": "task", "knowledge_id": knowledge, "text": question}, operation,
            )
        except HTTPException as exc:
            if isinstance(exc.__cause__, ValueError):
                raise exc.__cause__
            raise

    def close(self):
        # The exit check must still be able to query this actual live connection.
        closed.append(list(self.db.execute("PRAGMA database_list")))
        original_close(self)
        if cleanup == "close":
            raise ValueError("fixture harness close failed")

    async def stop(self):
        await original_stop(self)
        if cleanup == "stop":
            raise asyncio.CancelledError()

    async def close_database(self):
        await original_database_close(self)
        if cleanup == "database":
            raise ValueError("fixture orchestrator cleanup failed")

    monkeypatch.setattr(LearningHarness, "converse", converse)
    monkeypatch.setattr(LearningHarness, "close", close)
    monkeypatch.setattr(MemoryWorker, "stop", stop)
    monkeypatch.setattr(AgentOrchestrator, "close_database", close_database)
    return opened, closed


async def run_terminal(fixture, tmp_path, monkeypatch, broker, *,
                       write=True, exit_kind="value", cleanup=None, publish=True):
    repo, promotion, deployment = fixture
    outside = tmp_path / "outside.sqlite3"
    opened, closed = server_operation(
        monkeypatch, outside, write=write, exit_kind=exit_kind, cleanup=cleanup)
    parent, _ = await admitted(
        fixture, "exception-terminal",
        cohort="stable" if deployment.state == "shadow" else "candidate")
    recorder = PolicyObservationRecorder(repo.session_factory) if publish else None
    if deployment.state == "shadow":
        claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
        await repo.transition_committing(parent.id, claim.fencing_token)
        primary = await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
        router = ShadowStoreRouter(tmp_path / "shadow")
        worker = ShadowWorker(
            "shadow", promotion,
            executor_module.LearningTaskExecutor(None, shadow_store_router=router),
            router, policy_assigner=repo.policy_assigner, observation_recorder=recorder,
        )
        assert await worker.run_once()
        terminal = await promotion.enqueue_shadow(parent.id)
        source_id, code = terminal.shadow_id, terminal.error_code
        assert terminal.status == "failed"
        ledger = terminal.result
        assert (await repo.get(parent.id)).public_dict() == primary.public_dict()
        assert not router._locks
        assert not router.path_for(opened[0].pinned_policy).exists()
    else:
        async def record_usage(run_id, token, usage):
            await repo.record_attempt_usage(run_id, token, usage)
            if cleanup == "usage":
                raise ValueError("fixture usage notification failed after persistence")

        worker = RunWorker(
            "primary", repo, broker,
            executor_module.LearningTaskExecutor(
                str(tmp_path / "production.sqlite3"), allowed_environment="rehearsal",
                rehearsal_store_root=str(tmp_path / "rehearsal"), usage_recorder=record_usage),
            lease_seconds=30, heartbeat_seconds=.01, max_attempts=3,
            allowed_environment="rehearsal", observation_recorder=recorder,
        )
        await broker.publish("exception-terminal", {"run_id": parent.id})
        assert await worker.run_once()
        terminal = await repo.get(parent.id)
        source_id, code = parent.id, terminal.error_code
        assert terminal.status == "terminal_failed"
        async with repo.session_factory() as session:
            attempts = (await session.scalars(select(DistributedRunAttempt).where(
                DistributedRunAttempt.run_id == parent.id))).all()
        assert len(attempts) == 1 and attempts[0].reason == code
        assert attempts[0].status == "terminal_failed"
        ledger = attempts[0].usage_summary
    assert len(opened) == len(closed) == 1
    if write:
        with sqlite3.connect(outside) as database:
            assert database.execute("SELECT value FROM marker").fetchall() == [("committed",)]
        assert any(filename == str(outside) for _, _, filename in closed[0])
    else:
        assert not outside.exists()
    # Actual no-model context accounting, not invented provider cost or diagnostics.
    assert ledger["model_calls"] == ledger["tool_calls"] == 0
    assert ledger["input_tokens"] == ledger["output_tokens"] == 0
    assert ledger["cost"] is None
    assert ledger["structured_decision_count"] == ledger["unknown_decision_count"] == 0
    return source_id, code, opened[0].pinned_policy


async def observation_for(fixture, source_id):
    repo, _, deployment = fixture
    recorder = PolicyObservationRecorder(repo.session_factory)
    return await (recorder.record_shadow(source_id) if deployment.state == "shadow"
                  else recorder.record_run(source_id))


@pytest.mark.parametrize("stage", ["canary", "shadow"])
@pytest.mark.parametrize("write,exit_kind", [(True, "value"), (True, "success"), (False, "value")])
async def test_actual_attach_exit_durable_diagnostic_and_promotion_controls(
    health_repo, tmp_path, monkeypatch, broker, stage, write, exit_kind,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    _, promotion, deployment = fixture
    source_id, code, _ = await run_terminal(
        fixture, tmp_path, monkeypatch, broker, write=write, exit_kind=exit_kind)
    observation = await observation_for(fixture, source_id)
    if write:
        assert code == "ConfirmedPermissionViolation"
        assert observation.terminal_status == "confirmed_permission_violation"
        assert observation.permission_outcome == "confirmed_violation"
        with pytest.raises(PromotionCommandRejected):
            await promotion.transition(advance(deployment))
        window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
        assert window.decision == "fail"
        assert observation.observation_key in window.observation_keys["candidate"]
        assert (await promotion.get_head("rehearsal")).state == (
            "shadow" if stage == "shadow" else "rolled_back")
    else:
        assert code == ("execution_failed" if stage == "shadow" else "ValueError")
        assert observation.terminal_status == "terminal_failed"
        assert observation.permission_outcome == ("isolated" if stage == "shadow" else "not_applicable")
        # One ordinary failure, unknown cost, and no confirmed hard event cannot fabricate FAIL.
        assert (await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)).decision == "hold"


@pytest.mark.parametrize("stage", ["canary", "shadow"])
@pytest.mark.parametrize("cleanup", ["stop", "close", "database"])
async def test_cleanup_cannot_erase_confirmed_store_violation_or_usage(
    health_repo, tmp_path, monkeypatch, broker, stage, cleanup,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    source_id, code, _ = await run_terminal(
        fixture, tmp_path, monkeypatch, broker, cleanup=cleanup)
    assert code == "ConfirmedPermissionViolation"
    assert (await observation_for(fixture, source_id)).permission_outcome == "confirmed_violation"


async def test_primary_usage_notification_failure_cannot_erase_hard_diagnostic(
    health_repo, tmp_path, monkeypatch, broker,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at="canary")
    source_id, code, _ = await run_terminal(
        fixture, tmp_path, monkeypatch, broker, cleanup="usage")
    assert code == "ConfirmedPermissionViolation"
    assert (await observation_for(fixture, source_id)).permission_outcome == "confirmed_violation"


@pytest.mark.parametrize("stage", ["canary", "shadow"])
async def test_source_cancellation_cannot_erase_actual_store_violation(
    health_repo, tmp_path, monkeypatch, broker, stage,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    source_id, code, _ = await run_terminal(
        fixture, tmp_path, monkeypatch, broker, exit_kind="cancel")
    assert code == "ConfirmedPermissionViolation"
    assert (await observation_for(fixture, source_id)).permission_outcome == "confirmed_violation"


@pytest.mark.parametrize("stage", ["canary", "shadow"])
async def test_exception_terminal_recovery_invalidates_consumed_active_pass_and_pinning(
    health_repo, tmp_path, monkeypatch, broker, stage,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    repo, promotion, source = fixture
    source_id, code, old_binding = await run_terminal(
        fixture, tmp_path, monkeypatch, broker, publish=False)
    assert code == "ConfirmedPermissionViolation"
    canary = source
    if stage == "shadow":
        canary = await promotion.transition(advance(source))
        await fill_window(
            (repo, promotion, canary), changes={"observed_at": datetime.now(UTC)},
            stable_changes={"observed_at": datetime.now(UTC)})
        assert (await PolicyHealthEvaluator(promotion).evaluate(canary.deployment_id)).decision == "pass"
    active = await promotion.transition(advance(canary))
    pinned, _ = await admitted((repo, promotion, active), "old-active", cohort="candidate")
    await fill_window(
        (repo, promotion, active), state="active", stable_count=0,
        changes={"observed_at": datetime.now(UTC) + timedelta(seconds=1)})
    evaluator = PolicyHealthEvaluator(promotion)
    assert (await evaluator.evaluate(active.deployment_id)).decision == "pass"
    recorder = PolicyObservationRecorder(repo.session_factory)
    assert await recorder.recover() >= 1
    assert await recorder.recover() == 0
    observation = await observation_for(fixture, source_id)
    assert observation.deployment_id == old_binding.deployment_id
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
