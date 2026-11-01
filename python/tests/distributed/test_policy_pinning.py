import json
import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.distributed.promotion_contracts import PolicyExecutionBinding
from core.distributed.runtime import PRODUCTION_DEPLOYMENT_ID
from core.harness import LearningHarness
from core.policy_store import BUILTIN_HASH, builtin_components
from core.run_context import active_run
from core.tutor_policy import current_retrieval_rules
from tests.distributed.helpers import authority, spec
from tests.distributed.test_policy_assignment import (
    assignment_repo, candidate_head, token_for,
)


def binding(**changes):
    return PolicyExecutionBinding(
        **{
            "deployment_id": PRODUCTION_DEPLOYMENT_ID,
            "environment": "production",
            "effective_policy_hash": BUILTIN_HASH,
            "components": builtin_components(),
            "policy_cohort": "stable",
            "assignment_key_hash": "c" * 64,
            "assignment_reason": "test",
            "state_namespace": "production",
            **changes,
        }
    )


async def test_harness_executes_pinned_components_without_file_registry(
    tmp_path, monkeypatch,
):
    pinned = binding(
        effective_policy_hash="d" * 64,
        components={"retrieval_rules": "frozen candidate rules"},
    )
    monkeypatch.setattr(settings, "policy_loading_enabled", True)
    monkeypatch.setattr(settings, "policy_registry_path", str(tmp_path / "missing"))
    harness = LearningHarness(
        AgentOrchestrator(), str(tmp_path / "pinned.sqlite3"),
        pinned_policy=pinned, state_namespace="production",
    )

    async def operation():
        ctx = active_run.get()
        assert ctx.effective_policy_hash == pinned.effective_policy_hash
        assert ctx.deployment_id == pinned.deployment_id
        assert ctx.state_namespace == "production"
        assert current_retrieval_rules() == "frozen candidate rules"
        return {}, None

    try:
        result = await harness.run(
            "student", "pinned", {"kind": "task", "knowledge_id": "general"}, operation,
        )
        assert result["execution"]["deployment_id"] == str(pinned.deployment_id)
        assert result["execution"]["state_namespace"] == "production"
        assert not hasattr(harness, "_policy_registry")
    finally:
        await harness.memory_worker.stop()
        harness.close()


async def test_pending_quiz_conflicts_with_trusted_binding(tmp_path):
    harness = LearningHarness(
        AgentOrchestrator(), str(tmp_path / "conflict.sqlite3"),
        pinned_policy=binding(), state_namespace="production",
    )
    try:
        with pytest.raises(HTTPException) as raised:
            harness.resolve_policy(
                "student", "thread", {"effective_policy_hash": "e" * 64},
                "general", {"kind": "task"},
            )
        assert raised.value.status_code == 409
    finally:
        await harness.memory_worker.stop()
        harness.close()


async def test_distributed_replay_rejects_legacy_sqlite_identity_without_rebinding(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    payload = {"kind": "task", "knowledge_id": "general"}
    local = LearningHarness(AgentOrchestrator(), path)

    async def operation():
        return {}, None

    try:
        first = await local.run("student", "legacy", payload, operation)
        first["execution"].pop("deployment_id")
        first["execution"].pop("state_namespace")
        with local.db:
            local.db.execute(
                "UPDATE runs SET result=? WHERE learner='student' AND request='legacy'",
                (json.dumps(first),),
            )
        assert await local.run("student", "legacy", payload, operation) == first
    finally:
        await local.memory_worker.stop()
        local.close()
    pinned = LearningHarness(
        AgentOrchestrator(), path, pinned_policy=binding(), state_namespace="production",
    )
    try:
        with pytest.raises(HTTPException) as raised:
            await pinned.run("student", "legacy", payload, operation)
        assert raised.value.status_code == 409
        assert json.loads(pinned.db.execute("SELECT result FROM runs").fetchone()[0]) == first
    finally:
        await pinned.memory_worker.stop()
        pinned.close()


@pytest.mark.parametrize("field", ["policy_cohort", "rehearsal_id"])
@pytest.mark.parametrize("missing", [True, False])
async def test_pinned_sqlite_replay_rejects_cohort_and_rehearsal_identity(
    tmp_path, field, missing,
):
    harness = LearningHarness(
        AgentOrchestrator(), str(tmp_path / "identity.sqlite3"),
        pinned_policy=binding(), state_namespace="production",
    )

    async def operation():
        return {}, None

    try:
        payload = {"kind": "task", "knowledge_id": "general"}
        first = await harness.run("student", "identity", payload, operation)
        if missing:
            first["execution"].pop(field)
        else:
            first["execution"][field] = "forged"
        with harness.db:
            harness.db.execute(
                "UPDATE runs SET result=? WHERE learner='student' AND request='identity'",
                (json.dumps(first),),
            )
        with pytest.raises(HTTPException) as raised:
            await harness.run("student", "identity", payload, operation)
        assert raised.value.status_code == 409
        assert json.loads(harness.db.execute("SELECT result FROM runs").fetchone()[0]) == first
    finally:
        await harness.memory_worker.stop()
        harness.close()


@pytest.mark.parametrize("namespace", [
    "../production", "rehearsal-a/b", "rehearsal-a\\b", "rehearsal-Ａ",
    "rehearsal-a\n", "rehearsal-", "production/../production",
])
def test_router_rejects_untrusted_namespace(tmp_path, namespace):
    from core.distributed.rehearsal_store import RehearsalStoreRouter

    router = RehearsalStoreRouter(
        tmp_path / "production.sqlite3", tmp_path / "rehearsal",
        allowed_environment="rehearsal",
    )
    with pytest.raises(ValueError):
        router.path_for(binding(
            environment="rehearsal", state_namespace=namespace, rehearsal_id="a",
        ))
    assert not (tmp_path / "rehearsal").exists()


def test_router_capability_and_symlink_escape(tmp_path):
    from core.distributed.rehearsal_store import RehearsalStoreRouter

    root = tmp_path / "rehearsal"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "rehearsal-a").symlink_to(outside, target_is_directory=True)
    router = RehearsalStoreRouter(
        tmp_path / "production.sqlite3", root, allowed_environment="rehearsal",
    )
    with pytest.raises(ValueError):
        router.path_for(binding())
    with pytest.raises(ValueError):
        router.path_for(binding(
            environment="rehearsal", state_namespace="rehearsal-a", rehearsal_id="a",
        ))
    assert not list(outside.iterdir())


async def test_claim_environment_rejection_is_atomic(repo):
    from core.distributed.repository import FencingViolation

    run = await repo.accept(spec(request_id="wrong-environment"))
    with pytest.raises(FencingViolation, match="environment"):
        await repo.claim(run.id, "rehearsal-worker", 30, allowed_environment="rehearsal")
    unchanged = await repo.get(run.id)
    lease = await repo.lease(run.id)
    assert unchanged.attempt_count == 0
    assert lease.fencing_token == 0
    assert lease.owner is None


async def test_executor_rejects_binding_mismatch_before_store_write(tmp_path):
    from core.distributed.executor import LearningTaskExecutor

    path = tmp_path / "never-created.sqlite3"
    executor = LearningTaskExecutor(str(path))
    with pytest.raises(ValueError, match="binding"):
        await executor.execute(spec(), authority(), binding(deployment_id=uuid4()))
    assert not path.exists()
    assert not path.with_suffix(".sqlite3.lock").exists()


@pytest.mark.parametrize("resume", ["first", "retry", "takeover"])
async def test_actual_worker_executor_harness_keeps_binding_after_head_change(
    assignment_repo, broker, tmp_path, monkeypatch, resume,
):
    from core.distributed.broker import StreamMessage
    from core.distributed.executor import LearningTaskExecutor
    from core.distributed.reaper import LeaseReaper
    from core.distributed.worker import RunWorker
    from core.distributed.contracts import RunStatus

    repo = assignment_repo
    row = await candidate_head(repo)
    from core.distributed.repository import DistributedRunRepository

    repo._db_now = DistributedRunRepository._db_now
    now = datetime.now(UTC)
    run, _ = await repo.accept_with_replay(
        spec(request_id=f"actual-{resume}"),
        rehearsal_token=token_for(
            row, request_id=f"actual-{resume}",
            issued_at=now.isoformat(), expires_at=(now + timedelta(minutes=5)).isoformat(),
        ),
    )
    expected = PolicyExecutionBinding.model_validate(run.policy_binding)
    started, release = asyncio.Event(), asyncio.Event()
    seen = []
    original = LearningHarness.converse

    async def paused(harness, *args, **kwargs):
        # This wrapper pauses the actual executor before the real business run.
        seen.append(harness.pinned_policy)
        assert harness.state_namespace == expected.state_namespace
        if len(seen) == 1:
            started.set()
            await release.wait()
        return await original(harness, *args, **kwargs)

    monkeypatch.setattr(LearningHarness, "converse", paused)
    monkeypatch.setattr(settings, "policy_loading_enabled", True)
    monkeypatch.setattr(settings, "policy_registry_path", str(tmp_path / "missing-registry"))
    production = tmp_path / "production.sqlite3"
    root = tmp_path / "rehearsal"

    def worker(name):
        return RunWorker(
            name, repo, broker,
            LearningTaskExecutor(
                str(production), allowed_environment="rehearsal",
                rehearsal_store_root=str(root),
            ),
            allowed_environment="rehearsal",
            lease_seconds=30, heartbeat_seconds=1, max_attempts=3,
        )

    task = asyncio.create_task(worker("rehearsal-a").handle(
        StreamMessage("1-0", f"first:{run.id}", {"run_id": run.id}),
    ))
    try:
        await asyncio.wait_for(started.wait(), 3)
        await candidate_head(repo, state="frozen", traffic=0, version=3)
        if resume == "first":
            release.set()
            await task
        elif resume == "retry":
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await repo.fail(run.id, 1, "interrupted", retryable=True)
        else:
            await repo.force_lease_expiry(
                run.id, datetime(2026, 10, 31, tzinfo=UTC),
            )
            assert await LeaseReaper(repo).reap_once() == [run.id]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if resume != "first":
            release.set()
            await worker("rehearsal-b").handle(
                StreamMessage("2-0", f"resume:{run.id}", {"run_id": run.id}),
            )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    completed = await repo.get(run.id)
    assert completed.status == RunStatus.COMPLETED
    assert completed.attempt_count == (1 if resume == "first" else 2)
    assert seen == ([expected] if resume == "first" else [expected, expected])
    execution = completed.result["execution"]
    assert execution["effective_policy_hash"] == expected.effective_policy_hash
    assert execution["deployment_id"] == str(expected.deployment_id)
    assert execution["state_namespace"] == expected.state_namespace
    assert not production.exists()
    with sqlite3.connect(root / expected.state_namespace / "harness.sqlite3") as db:
        stored = json.loads(db.execute("SELECT result FROM runs WHERE status='completed'").fetchone()[0])
        assert stored == completed.result
        steps = [json.loads(body) for body, in db.execute("SELECT body FROM run_steps")]
        assert steps
        assert all(item["deployment_id"] == str(expected.deployment_id) for item in steps)


@pytest.mark.parametrize("allowed", ["production", "rehearsal"])
async def test_worker_rejects_cross_environment_before_claim(
    assignment_repo, broker, allowed,
):
    from core.distributed.broker import StreamMessage
    from core.distributed.worker import RunWorker
    from tests.distributed.test_worker import ImmediateExecutor

    repo = assignment_repo
    row = await candidate_head(repo)
    run, _ = await repo.accept_with_replay(
        spec(), rehearsal_token=token_for(row) if allowed == "production" else None,
    )
    executor = ImmediateExecutor()
    worker = RunWorker(
        "wrong-worker", repo, broker, executor, allowed_environment=allowed,
        lease_seconds=30, heartbeat_seconds=1, max_attempts=3,
    )
    await worker.handle(StreamMessage("1-0", "wrong-env", {"run_id": run.id}))
    assert executor.calls == 0
    assert (await repo.get(run.id)).attempt_count == 0
    assert (await repo.lease(run.id)).fencing_token == 0


def test_router_valid_paths_are_server_derived(tmp_path):
    from core.distributed.rehearsal_store import RehearsalStoreRouter

    production = tmp_path / "configured.sqlite3"
    root = tmp_path / "rehearsal"
    assert RehearsalStoreRouter(
        production, root, allowed_environment="production",
    ).path_for(binding()) == production
    path = RehearsalStoreRouter(
        production, root, allowed_environment="rehearsal",
    ).path_for(binding(
        environment="rehearsal", rehearsal_id="a", state_namespace="rehearsal-a",
    ))
    assert path == root / "rehearsal-a" / "harness.sqlite3"


@pytest.mark.parametrize("source", ["plan", "history"])
@pytest.mark.parametrize("matching", [True, False])
async def test_pending_plan_and_history_validate_trusted_pin(tmp_path, source, matching):
    pinned = binding()
    policy_hash = pinned.effective_policy_hash if matching else "f" * 64
    harness = LearningHarness(
        AgentOrchestrator(), str(tmp_path / "pending.sqlite3"),
        pinned_policy=pinned, state_namespace="production",
    )
    try:
        with harness.db:
            if source == "plan":
                harness.db.execute(
                    "INSERT INTO learning_plans "
                "(id,learner_id,thread_id,version,status,body,updated) "
                    "VALUES ('plan','student','thread',1,'awaiting_student',?,0)",
                    (json.dumps({"effective_policy_hash": policy_hash}),),
                )
            else:
                harness.db.execute(
                    "INSERT INTO pending_questions (id,learner,thread,run,question) "
                    "VALUES ('pending','student','thread','past-run','Explain')",
                )
                harness.db.execute(
                    "INSERT INTO runs (learner,request,status,result) VALUES "
                    "('student','past','completed',?)",
                    (json.dumps({"execution": {"effective_policy_hash": policy_hash}}),),
                )
                harness.db.execute(
                    "INSERT INTO run_attempts (id,learner,request,run,status,started) "
                    "VALUES ('attempt','student','past','past-run','completed',0)",
                )
        if matching:
            assert harness.resolve_policy(
                "student", "thread", {}, "general", {"kind": "task"},
            )["policy_hash"] == policy_hash
        else:
            with pytest.raises(HTTPException) as raised:
                harness.resolve_policy(
                    "student", "thread", {}, "general", {"kind": "task"},
                )
            assert raised.value.status_code == 409
    finally:
        await harness.memory_worker.stop()
        harness.close()


async def test_runtime_starts_dedicated_groups_and_routes_worker(repo, broker):
    from core.distributed.runtime import DistributedRuntime
    from tests.distributed.test_worker import ImmediateExecutor

    settings_obj = settings.model_copy(update={
        "promotion_rehearsal_stream": broker.stream + ":rehearsal",
        "promotion_rehearsal_consumer_group": "rehearsal-test",
        "distributed_stream": broker.stream,
        "distributed_experts_enabled": False,
    })
    runtime = DistributedRuntime(
        repo.session_factory.kw["bind"], repo.session_factory, repo, broker,
        settings_obj=settings_obj,
    )
    try:
        await runtime.start()
        groups = await broker.redis.xinfo_groups(runtime.rehearsal_broker.stream)
        assert groups[0]["name"] == "rehearsal-test"
        assert await broker.redis.xinfo_groups(runtime.deployment_broker.stream)
        production = runtime.worker("prod", ImmediateExecutor())
        rehearsal = runtime.worker("rehearsal", ImmediateExecutor(), allowed_environment="rehearsal")
        assert production.broker is broker
        assert production.allowed_environment == "production"
        assert rehearsal.broker is runtime.rehearsal_broker
        assert rehearsal.allowed_environment == "rehearsal"
        dispatcher = runtime.dispatcher()
        assert dispatcher.routes["run.rehearsal.accepted"] is runtime.rehearsal_broker
    finally:
        await broker.redis.delete(runtime.rehearsal_broker.stream, runtime.deployment_broker.stream)
