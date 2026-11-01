"""Real PostgreSQL publication barriers; actual server store-boundary diagnostics."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from core.distributed.broker import StreamMessage
from core.distributed.models import DistributedRun
from core.distributed.policy_health import PolicyHealthEvaluator, PolicyObservationRecorder
from core.distributed.promotion_contracts import PromotionCommand
from core.distributed.promotion_models import PolicyAuditEventRecord, PolicyObservationRecord
from core.distributed.promotion_repository import PromotionCommandRejected, PromotionVersionConflict
from tests.distributed.helpers import business_result
from tests.distributed.test_policy_health import fill_window, health_repo
from tests.distributed.test_policy_health_corrections import admitted, real_active_fixture

pytestmark = pytest.mark.distributed_integration


def advance(deployment):
    target = "canary" if deployment.state == "shadow" else "active"
    return PromotionCommand(
        command_id=f"publication-{target}", environment="rehearsal",
        expected_version=deployment.version, current_state=deployment.state,
        target_state=target, traffic_basis_points=5000 if target == "canary" else 10000,
        actor="test", reason="fixture-only publication barrier, not release evidence",
    )


async def terminal_permission(fixture, tmp_path, monkeypatch, broker):
    """Persist a typed terminal through the real worker, without publishing yet."""
    from core.distributed import executor as executor_module
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker
    from core.distributed.worker import RunWorker

    repo, promotion, deployment = fixture
    parent, _ = await admitted(
        fixture, "publication-terminal",
        cohort="stable" if deployment.state == "shadow" else "candidate")
    original = executor_module.LearningHarness
    outside = tmp_path / "outside-authorized.sqlite3"

    def wrong_server_store(orchestrator, path, *args, **kwargs):
        return original(orchestrator, str(outside), *args, **kwargs)

    monkeypatch.setattr(executor_module, "LearningHarness", wrong_server_store)
    if deployment.state == "shadow":
        claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
        await repo.transition_committing(parent.id, claim.fencing_token)
        await repo.complete(parent.id, claim.fencing_token, business_result(claim.policy_binding))
        router = ShadowStoreRouter(tmp_path / "shadow")
        worker = ShadowWorker(
            "shadow", promotion,
            executor_module.LearningTaskExecutor(None, shadow_store_router=router),
            router, policy_assigner=repo.policy_assigner)
        assert await worker.run_once()
        job = await promotion.enqueue_shadow(parent.id)
        assert job.error_code == "ConfirmedPermissionViolation"
        source_id = job.shadow_id
    else:
        worker = RunWorker(
            "primary", repo, broker,
            executor_module.LearningTaskExecutor(
                str(tmp_path / "production.sqlite3"), allowed_environment="rehearsal",
                rehearsal_store_root=str(tmp_path / "rehearsal"),
                usage_recorder=repo.record_attempt_usage),
            lease_seconds=30, heartbeat_seconds=.01, max_attempts=3,
            allowed_environment="rehearsal")
        await worker.handle(StreamMessage("0-0", "publication-diagnostic", {"run_id": parent.id}))
        source_id = parent.id
        async with repo.session_factory() as session:
            terminal = await session.get(DistributedRun, parent.id)
            assert terminal.error_code == "ConfirmedPermissionViolation"
            assert terminal.status == "terminal_failed"
    assert outside.exists()
    return source_id


async def publish(recorder, deployment, source_id, entry):
    if entry == "recover":
        return await recorder.recover()
    if deployment.state == "shadow":
        return await recorder.record_shadow(source_id)
    return await recorder.record_run(source_id)


async def blocking_or_done(observer, blocker_pid, task):
    async with asyncio.timeout(5):
        while True:
            blocked = await observer.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks "
                "WHERE NOT granted AND :blocker=ANY(pg_blocking_pids(pid)))"
            ), {"blocker": blocker_pid})
            if blocked or task.done():
                return blocked
            await asyncio.sleep(.01)


@pytest.mark.parametrize("stage", ["shadow", "canary"])
@pytest.mark.parametrize("entry", ["direct", "recover"])
async def test_terminal_publication_serializes_after_gate_query(
    health_repo, tmp_path, monkeypatch, broker, stage, entry,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    repo, promotion, deployment = fixture
    source_id = await terminal_permission(fixture, tmp_path, monkeypatch, broker)
    recorder = PolicyObservationRecorder(repo.session_factory)
    queried, release = asyncio.Event(), asyncio.Event()
    gate_check = promotion._bound_gate_receipts
    barrier = {}

    async def paused_gate(session, **kwargs):
        result = await gate_check(session, **kwargs)
        assert not result[0]
        barrier["pid"] = await session.scalar(select(func.pg_backend_pid()))
        barrier["at"] = await session.scalar(select(func.clock_timestamp()))
        queried.set()
        await release.wait()
        return result

    monkeypatch.setattr(promotion, "_bound_gate_receipts", paused_gate)
    transition = asyncio.create_task(promotion.transition(advance(deployment)))
    publication = None
    try:
        await asyncio.wait_for(queried.wait(), 5)
        publication = asyncio.create_task(publish(recorder, deployment, source_id, entry))
        async with repo.session_factory() as observer:
            blocked = await blocking_or_done(observer, barrier["pid"], publication)
            now = await observer.scalar(select(func.clock_timestamp()))
            assert now >= barrier["at"]
            # This assertion is RED if publication commits in the gate/head transaction gap.
            assert blocked, "terminal observation committed after gate query while head was locked"
            assert not publication.done()
        release.set()
        successor = await asyncio.wait_for(transition, 5)
        await asyncio.wait_for(publication, 5)
        async with repo.session_factory() as session:
            hard = await session.scalar(select(PolicyObservationRecord).where(
                PolicyObservationRecord.deployment_id == str(deployment.deployment_id),
                PolicyObservationRecord.server_error_code == "ConfirmedPermissionViolation"))
            assert hard.created_at >= successor.created_at
        # Inherit the actual consumed predecessor, even though the event published later.
        window = await PolicyHealthEvaluator(promotion).evaluate(successor.deployment_id)
        assert window.decision == "fail"
        assert window.observation_keys["hard_failures"] == [hard.observation_key]
        assert (await promotion.get_head("rehearsal")).state == "rolled_back"
        fresh, _ = await admitted((repo, promotion, await promotion.get_head("rehearsal")), "new")
        assert fresh.policy_cohort == "stable"
    finally:
        release.set()
        await asyncio.gather(
            *(task for task in (transition, publication) if task is not None),
            return_exceptions=True)


@pytest.mark.parametrize("stage", ["shadow", "canary"])
async def test_committed_terminal_permission_rejects_transition(
    health_repo, tmp_path, monkeypatch, broker, stage,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    repo, promotion, deployment = fixture
    source_id = await terminal_permission(fixture, tmp_path, monkeypatch, broker)
    observation = await publish(
        PolicyObservationRecorder(repo.session_factory), deployment, source_id, "direct")
    assert observation.permission_outcome == "confirmed_violation"
    with pytest.raises(PromotionCommandRejected):
        await promotion.transition(advance(deployment))
    assert (await promotion.get_head("rehearsal")).deployment_id == deployment.deployment_id
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == advance(deployment).command_id,
            PolicyAuditEventRecord.event_type == "promotion_rejected")) == 1


@pytest.mark.parametrize("source_stage", ["shadow", "canary"])
async def test_late_consumed_predecessor_permission_invalidates_existing_active_pass(
    health_repo, tmp_path, monkeypatch, broker, source_stage,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=source_stage)
    repo, promotion, source = fixture
    source_id = await terminal_permission(fixture, tmp_path, monkeypatch, broker)
    canary = source
    if source_stage == "shadow":
        canary = await promotion.transition(advance(source))
        await fill_window(
            (repo, promotion, canary),
            changes={"observed_at": datetime.now(UTC)},
            stable_changes={"observed_at": datetime.now(UTC)})
        assert (await PolicyHealthEvaluator(promotion).evaluate(canary.deployment_id)).decision == "pass"
    active = await promotion.transition(advance(canary))
    await fill_window(
        (repo, promotion, active), state="active", stable_count=0,
        changes={"observed_at": datetime.now(UTC) + timedelta(seconds=1)})
    evaluator = PolicyHealthEvaluator(promotion)
    assert (await evaluator.evaluate(active.deployment_id)).decision == "pass"
    observation = await publish(
        PolicyObservationRecorder(repo.session_factory), source, source_id, "direct")
    assert observation.deployment_id == source.deployment_id
    window = await evaluator.evaluate(active.deployment_id)
    assert window.decision == "fail", "Active must not reuse PASS after its consumed predecessor hard event"
    assert window.observation_keys["hard_failures"] == [observation.observation_key]
    assert (await promotion.get_head("rehearsal")).state == "rolled_back"


@pytest.mark.parametrize("stage", ["shadow", "canary"])
async def test_publication_first_blocks_promotion_and_advisory_health_without_deadlock(
    health_repo, tmp_path, monkeypatch, broker, stage,
):
    fixture, _, _ = await real_active_fixture(health_repo, stop_at=stage)
    repo, promotion, deployment = fixture
    source_id = await terminal_permission(fixture, tmp_path, monkeypatch, broker)
    recorder = PolicyObservationRecorder(repo.session_factory)
    inserted, release = asyncio.Event(), asyncio.Event()
    original_insert = recorder._insert
    barrier = {}

    async def paused_insert(session, observation):
        result = await original_insert(session, observation)
        barrier["pid"] = await session.scalar(select(func.pg_backend_pid()))
        inserted.set()
        await release.wait()
        return result

    monkeypatch.setattr(recorder, "_insert", paused_insert)
    publication = asyncio.create_task(publish(recorder, deployment, source_id, "direct"))
    transition = evaluation = None
    try:
        await asyncio.wait_for(inserted.wait(), 5)
        transition = asyncio.create_task(promotion.transition(advance(deployment)))
        async with repo.session_factory() as observer:
            assert await blocking_or_done(observer, barrier["pid"], transition)
            evaluation = asyncio.create_task(PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id))
            async with asyncio.timeout(5):
                while await observer.scalar(text(
                    "SELECT count(DISTINCT waiting.pid) FROM pg_locks waiting "
                    "WHERE NOT waiting.granted AND ("
                    ":blocker=ANY(pg_blocking_pids(waiting.pid)) OR EXISTS ("
                    "SELECT 1 FROM unnest(pg_blocking_pids(waiting.pid)) AS dependency(pid) "
                    "WHERE :blocker=ANY(pg_blocking_pids(dependency.pid))))"
                ), {"blocker": barrier["pid"]}) < 2:
                    assert not evaluation.done()
                    await asyncio.sleep(.01)
            assert not publication.done() and not transition.done() and not evaluation.done()
        release.set()
        observation = await asyncio.wait_for(publication, 5)
        assert observation.permission_outcome == "confirmed_violation"
        with pytest.raises((PromotionCommandRejected, PromotionVersionConflict)):
            await asyncio.wait_for(transition, 5)
        assert (await asyncio.wait_for(evaluation, 5)).decision == "fail"
        assert (await promotion.get_head("rehearsal")).state == (
            "shadow" if stage == "shadow" else "rolled_back")
        # Retry after the terminal transaction is durable remains idempotent.
        assert await publish(recorder, deployment, source_id, "direct") == observation
    finally:
        release.set()
        await asyncio.gather(
            *(task for task in (publication, transition, evaluation) if task is not None),
            return_exceptions=True)


@pytest.mark.parametrize("new_state", ["active", "frozen"])
async def test_late_old_canary_cannot_poison_separate_chain_even_with_same_policy(
    health_repo, tmp_path, monkeypatch, broker, new_state,
):
    old_fixture, _, _ = await real_active_fixture(health_repo, stop_at="canary")
    repo, promotion, old_canary = old_fixture
    source_id = await terminal_permission(old_fixture, tmp_path, monkeypatch, broker)
    old_active = await promotion.transition(advance(old_canary))
    # Re-register the SAME artifact. Hash equality alone must not imply causality.
    new_fixture, new_canary, _ = await real_active_fixture(
        health_repo, command_prefix="independent")
    _, _, new_active = new_fixture
    assert old_active.candidate_policy_hash == new_active.candidate_policy_hash
    assert old_canary.deployment_id != new_canary.deployment_id
    await fill_window(
        new_fixture, state="active", stable_count=0,
        changes={"observed_at": datetime.now(UTC) + timedelta(seconds=1)})
    if new_state == "frozen":
        head = await promotion.transition(PromotionCommand(
            command_id="independent-freeze", environment="rehearsal",
            expected_version=new_active.version, current_state="active",
            target_state="frozen", traffic_basis_points=0,
            actor="test", reason="fixture-only unrelated stable head"))
    else:
        head = new_active
    observation = await PolicyObservationRecorder(repo.session_factory).record_run(source_id)
    evaluator = PolicyHealthEvaluator(promotion)
    assert (await evaluator.evaluate(old_canary.deployment_id)).decision == "fail"
    assert (await evaluator.evaluate(old_active.deployment_id)).decision == "fail"
    window = await evaluator.evaluate(new_active.deployment_id)
    assert window.decision == "pass"
    assert observation.observation_key not in window.observation_keys.get("hard_failures", [])
    assert (await promotion.get_head("rehearsal")).deployment_id == head.deployment_id
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.event_type == "health_rollback")) == 0
    fresh, _ = await admitted((repo, promotion, head), "independent-new")
    assert fresh.policy_cohort == ("candidate" if new_state == "active" else "stable")
