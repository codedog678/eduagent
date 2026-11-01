"""Task7 engineering fixtures, not qualification receipts or student evidence."""
import asyncio
from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from core.distributed.promotion_models import PolicyShadowExecutionRecord
from core.distributed.promotion_contracts import PolicyExecutionBinding
from core.distributed.promotion_repository import PromotionRepository
from core.distributed.runtime import migrate_schema
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_policy_assignment import assigner, candidate_head, token_for

pytestmark = pytest.mark.distributed_integration


@pytest_asyncio.fixture
async def shadow_repo(raw_repo):
    await migrate_schema(raw_repo.session_factory.kw["bind"])
    raw_repo.policy_assigner = assigner(runtime_hash="f" * 64, source_revision="test-source")
    deployment = await candidate_head(raw_repo, state="shadow", traffic=0)
    return raw_repo, PromotionRepository(raw_repo.session_factory), deployment


async def parent_for(fixture, request_id="shadow-parent"):
    repo, _, deployment = fixture
    now = datetime.now(UTC)
    request = spec(request_id, question="synthetic private input")
    parent, _ = await repo.accept_with_replay(request, rehearsal_token=token_for(
        deployment, request_id, nonce=uuid4().hex, issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
    ))
    return parent


async def finish_parent(repo, parent):
    claim = await repo.claim(parent.id, "primary", 30, allowed_environment="rehearsal")
    await repo.transition_committing(parent.id, claim.fencing_token)
    return await repo.complete(parent.id, claim.fencing_token,
                               business_result(claim.policy_binding, public="stable result"))


async def shadow_count(repo):
    async with repo.session_factory() as session:
        return await session.scalar(select(func.count()).select_from(PolicyShadowExecutionRecord))


async def expire(repo, shadow_id):
    async with repo.session_factory() as session, session.begin():
        await session.execute(text(
            "UPDATE policy_shadow_executions SET lease_expires_at = "
            "clock_timestamp() - interval '1 second' WHERE shadow_id = :id"
        ), {"id": shadow_id})


async def test_enqueue_only_after_completion_and_duplicate_is_idempotent(shadow_repo):
    repo, promotion, deployment = shadow_repo
    parent = await parent_for(shadow_repo)
    assert await promotion.enqueue_shadow(parent.id) is None
    assert await shadow_count(repo) == 0
    await finish_parent(repo, parent)
    assert await shadow_count(repo) == 1
    jobs = await asyncio.gather(*(promotion.enqueue_shadow(parent.id) for _ in range(8)))
    assert len({job.shadow_id for job in jobs}) == 1
    assert jobs[0].deployment_id == deployment.deployment_id
    assert jobs[0].input_hash == parent.input_hash
    assert jobs[0].payload_reference["run_id"] == parent.id
    assert await shadow_count(repo) == 1


async def test_head_change_does_not_change_frozen_shadow_decision(shadow_repo):
    repo, promotion, deployment = shadow_repo
    parent = await parent_for(shadow_repo)
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    await finish_parent(repo, parent)
    job = await promotion.enqueue_shadow(parent.id)
    assert job.deployment_id == deployment.deployment_id
    assert job.policy_hash == deployment.candidate_policy_hash
    nonshadow = await parent_for((repo, promotion, await candidate_head(
        repo, state="registered", traffic=0, version=4)), "not-shadow")
    await candidate_head(repo, state="shadow", traffic=0, version=5)
    await finish_parent(repo, nonshadow)
    assert await promotion.enqueue_shadow(nonshadow.id) is None
    assert await shadow_count(repo) == 1


@pytest.mark.parametrize("operation", ["renew", "complete", "fail"])
async def test_expired_takeover_rejects_stale_owner_and_token(shadow_repo, operation):
    from core.distributed.shadow_repository import ShadowFencingViolation

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    first = await promotion.claim_shadow("old", 30)
    await expire(repo, first.shadow_id)
    second = await promotion.claim_shadow("new", 30)
    assert second.shadow_id == first.shadow_id
    assert second.fencing_token == first.fencing_token + 1
    assert second.attempt_count == 2
    if operation == "renew":
        stale_call = promotion.renew_shadow(first.shadow_id, "old", first.fencing_token, 30)
    elif operation == "complete":
        stale_call = promotion.complete_shadow(first.shadow_id, "old", first.fencing_token, {})
    else:
        stale_call = promotion.fail_shadow(first.shadow_id, "old", first.fencing_token, "execution_failed")
    with pytest.raises(ShadowFencingViolation):
        await stale_call
    with pytest.raises(ShadowFencingViolation):
        await promotion.renew_shadow(second.shadow_id, "old", second.fencing_token, 30)
    await promotion.renew_shadow(second.shadow_id, "new", second.fencing_token, 30)


@pytest.mark.parametrize("failure", [False, True])
async def test_candidate_uses_frozen_request_and_redacts_result(shadow_repo, tmp_path, failure):
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker

    repo, promotion, deployment = shadow_repo
    parent = await parent_for(shadow_repo)
    completed = await finish_parent(repo, parent)
    primary_path = tmp_path / "primary.sqlite3"
    primary_path.write_bytes(b"untouched primary fixture")
    router = ShadowStoreRouter(tmp_path / "isolated")
    calls = []

    class Executor:
        async def execute(self, request, authority, binding):
            authority.validate_binding(binding)
            assert authority.execution_mode == "shadow"
            assert str(authority.distributed_run_id) != parent.id
            assert request.input_hash == parent.input_hash
            assert binding.effective_policy_hash == deployment.candidate_policy_hash
            assert binding.components.retrieval_rules == "qualified retrieval"
            assert binding.policy_cohort == "shadow"
            assert binding.state_namespace == f"shadow-{deployment.deployment_id}-{parent.id}"
            path = router.path_for(binding)
            assert path == tmp_path / "isolated" / "shadow" / deployment.deployment_id / parent.id / "harness.sqlite3"
            path.write_bytes(b"disposable private candidate body")
            calls.append(path)
            if failure:
                raise RuntimeError("secret model body must not persist")
            return business_result(binding, response="secret model body", usage={
                "input_tokens": 13, "output_tokens": 7, "cost": "0.002",
                "model_calls": 1, "tool_calls": 0, "private": "never persist",
            })

    worker = ShadowWorker("shadow-test", promotion, Executor(), router,
                          policy_assigner=repo.policy_assigner)
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    assert await worker.run_once()
    assert not await worker.run_once()
    job = await promotion.enqueue_shadow(parent.id)
    assert job.status == ("failed" if failure else "completed")
    assert job.finished_at is not None
    assert job.result["commit_outcome"] == "not_attempted"
    assert "private" not in json.dumps(job.result)
    assert "secret" not in json.dumps(job.result)
    assert calls and not calls[0].exists()
    assert primary_path.read_bytes() == b"untouched primary fixture"
    after = await repo.get(parent.id)
    assert after.status == completed.status and after.result == completed.result


async def wait_until(check):
    async with asyncio.timeout(5):
        while not await check():
            await asyncio.sleep(0.01)


async def test_claim_skips_pg_locked_row_and_has_single_owner(shadow_repo):
    repo, promotion, _ = shadow_repo
    first = await parent_for(shadow_repo, "first")
    second = await parent_for(shadow_repo, "second")
    await finish_parent(repo, first)
    await finish_parent(repo, second)
    async with repo.session_factory() as blocker, blocker.begin():
        locked = await blocker.scalar(select(PolicyShadowExecutionRecord).where(
            PolicyShadowExecutionRecord.parent_run_id == first.id,
        ).with_for_update())
        claims = await asyncio.wait_for(asyncio.gather(*(
            promotion.claim_shadow(f"worker-{i}", 30) for i in range(6)
        )), 3)
        claimed = [item for item in claims if item is not None]
        assert len(claimed) == 1 and claimed[0].parent_run_id == second.id
        assert claimed[0].shadow_id != locked.shadow_id
    assert (await promotion.claim_shadow("unblocked", 30)).parent_run_id == first.id


async def test_reaper_retries_then_exhausts_and_rejects_expired_owner(shadow_repo):
    from core.distributed.shadow_repository import ShadowFencingViolation

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    for attempt in range(1, 4):
        claim = await promotion.claim_shadow("worker", 30)
        assert claim.attempt_count == attempt
        await expire(repo, claim.shadow_id)
        with pytest.raises(ShadowFencingViolation):
            await promotion.complete_shadow(claim.shadow_id, "worker", claim.fencing_token, {})
        assert await promotion.reap_shadow(datetime(2099, 1, 1, tzinfo=UTC)) == [claim.shadow_id]
        with pytest.raises(ShadowFencingViolation):
            await promotion.fail_shadow(claim.shadow_id, "worker", claim.fencing_token, "execution_failed")
    terminal = await promotion.get_shadow(claim.shadow_id)
    assert terminal.status == "exhausted" and terminal.error_code == "attempts_exhausted"
    assert terminal.result["commit_outcome"] == "not_attempted"
    assert terminal.finished_at is not None
    assert await promotion.claim_shadow("worker", 30) is None


async def test_renew_cannot_extend_attempt_deadline_or_caller_clock_reap(shadow_repo):
    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    claim = await promotion.claim_shadow("worker", 10, attempt_timeout_seconds=20)
    await promotion.renew_shadow(claim.shadow_id, "worker", claim.fencing_token, 200)
    renewed = await promotion.get_shadow(claim.shadow_id)
    assert renewed.lease_expires_at == claim.deadline_at
    assert await promotion.reap_shadow(datetime(2099, 1, 1, tzinfo=UTC)) == []


async def test_real_redis_outbox_duplicate_delivery_only_executes_one_primary(shadow_repo, broker):
    from core.distributed.dispatcher import OutboxDispatcher
    from core.distributed.worker import RunWorker

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    calls = []

    class PrimaryExecutor:
        async def execute(self, request, authority, binding):
            calls.append(request)
            return business_result(binding, public="primary")

    dispatcher = OutboxDispatcher(repo, broker, rehearsal_broker=broker)
    assert await dispatcher.dispatch_once() == 1
    assert await shadow_count(repo) == 0
    await broker.publish(f"run:{parent.id}:accepted", {"run_id": parent.id})
    await broker.publish("duplicate-outbox-delivery", {"run_id": parent.id})
    worker = RunWorker("primary", repo, broker, PrimaryExecutor(),
                       allowed_environment="rehearsal", lease_seconds=30, heartbeat_seconds=1,
                       max_attempts=3)
    for _ in range(3):
        assert await worker.run_once()
    assert len(calls) == 1 and await shadow_count(repo) == 1
    assert (await promotion.enqueue_shadow(parent.id)).status == "queued"


@pytest.mark.parametrize("failure", [False, True])
async def test_real_learning_executor_harness_isolated_and_bound(shadow_repo, tmp_path, monkeypatch, failure):
    import sqlite3
    from api.orchestrator import AgentOrchestrator
    from config.settings import settings
    from core.distributed.executor import LearningTaskExecutor
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker
    from core.harness import LearningHarness

    repo, promotion, deployment = shadow_repo
    parent = await parent_for(shadow_repo)
    completed = await finish_parent(repo, parent)
    primary = tmp_path / "production.sqlite3"
    with sqlite3.connect(primary) as database:
        database.execute("CREATE TABLE learner_evidence (content TEXT)")
        database.execute("INSERT INTO learner_evidence VALUES ('primary evidence')")
    before = primary.read_bytes()
    router = ShadowStoreRouter(tmp_path / "isolated")
    original = LearningHarness.converse
    seen = []

    async def inspected(harness, *args, **kwargs):
        assert isinstance(harness.orch, AgentOrchestrator)
        assert harness.execution_authority.execution_mode == "shadow"
        assert harness.expert_gateway is None
        assert harness.pinned_policy.effective_policy_hash == deployment.candidate_policy_hash
        assert harness.pinned_policy.components.retrieval_rules == "qualified retrieval"
        path = router.path_for(harness.pinned_policy)
        assert path.exists() and path != primary
        assert args[3] == parent.payload["question"]
        seen.append(path)
        result = await original(harness, *args, **kwargs)
        if failure:
            raise RuntimeError("private exception after real harness writes")
        assert result["execution"]["effective_policy_hash"] == deployment.candidate_policy_hash
        return result

    monkeypatch.setattr(LearningHarness, "converse", inspected)
    monkeypatch.setattr(settings, "memory_worker_enabled", False)
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    executor = LearningTaskExecutor(None, shadow_store_router=router)
    assert executor.store_path is None
    assert await ShadowWorker("real-shadow", promotion, executor, router,
                              policy_assigner=repo.policy_assigner).run_once()
    job = await promotion.enqueue_shadow(parent.id)
    assert job.status == ("failed" if failure else "completed")
    assert seen and not seen[0].exists()
    assert primary.read_bytes() == before
    assert (await repo.get(parent.id)).public_dict() == completed.public_dict()
    assert "synthetic private input" not in json.dumps(job.result)


async def test_summary_transaction_rollback_preserves_store_until_terminal(shadow_repo, tmp_path):
    from sqlalchemy.exc import DBAPIError
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker, ShadowReaper

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    router = ShadowStoreRouter(tmp_path / "isolated")
    paths = []

    class Executor:
        async def execute(self, request, authority, binding):
            path = router.path_for(binding)
            path.write_bytes(b"private candidate")
            paths.append(path)
            return business_result(binding)

    async with repo.session_factory() as session, session.begin():
        await session.execute(text(
            "CREATE FUNCTION fail_shadow_summary() RETURNS trigger AS $$ BEGIN "
            "IF NEW.status = 'completed' THEN RAISE EXCEPTION 'injected summary rollback'; "
            "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
        ))
        await session.execute(text(
            "CREATE TRIGGER injected_summary_failure BEFORE UPDATE ON policy_shadow_executions "
            "FOR EACH ROW EXECUTE FUNCTION fail_shadow_summary()"
        ))
    worker = ShadowWorker("worker", promotion, Executor(), router, policy_assigner=repo.policy_assigner)
    try:
        with pytest.raises(DBAPIError, match="injected summary rollback"):
            await worker.run_once()
        job = await promotion.enqueue_shadow(parent.id)
        assert job.status == "running" and job.result is None
        assert paths[0].exists()
        await ShadowReaper(promotion, router).reap_once()
        assert paths[0].exists()
    finally:
        async with repo.session_factory() as session, session.begin():
            await session.execute(text("DROP TRIGGER injected_summary_failure ON policy_shadow_executions"))
            await session.execute(text("DROP FUNCTION fail_shadow_summary()"))
    await expire(repo, job.shadow_id)
    assert await worker.run_once()
    assert not paths[0].exists()
    assert (await promotion.get_shadow(job.shadow_id)).status == "completed"


async def test_takeover_waits_for_cancelled_old_worker_fs_lock(shadow_repo, tmp_path):
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker, ShadowReaper

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    router_old = ShadowStoreRouter(tmp_path / "isolated")
    router_new = ShadowStoreRouter(tmp_path / "isolated")
    started, cancelling, allow_cancel, new_started, new_release = [asyncio.Event() for _ in range(5)]
    path = None

    class OldExecutor:
        async def execute(self, request, authority, binding):
            nonlocal path
            path = router_old.path_for(binding)
            path.write_bytes(b"old private candidate")
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelling.set()
                await allow_cancel.wait()
                raise

    class NewExecutor:
        async def execute(self, request, authority, binding):
            assert router_new.path_for(binding) == path
            path.write_bytes(b"new live store")
            new_started.set()
            await new_release.wait()
            assert path.read_bytes() == b"new live store"
            return business_result(binding)

    def worker(name, executor, router):
        return ShadowWorker(name, promotion, executor, router, policy_assigner=repo.policy_assigner,
                            lease_seconds=2, heartbeat_seconds=0.05)

    old_task = asyncio.create_task(worker("old", OldExecutor(), router_old).run_once())
    new_task = None
    try:
        await asyncio.wait_for(started.wait(), 3)
        job = await promotion.enqueue_shadow(parent.id)
        await expire(repo, job.shadow_id)
        new_task = asyncio.create_task(worker("new", NewExecutor(), router_new).run_once())
        await asyncio.wait_for(cancelling.wait(), 3)
        async def claimed():
            return (await promotion.get_shadow(job.shadow_id)).owner == "new"
        await wait_until(claimed)
        assert not new_started.is_set() and path.exists()
        await ShadowReaper(promotion, router_new).reap_once()
        assert path.read_bytes() == b"old private candidate"
        allow_cancel.set()
        await asyncio.wait_for(old_task, 3)
        await asyncio.wait_for(new_started.wait(), 3)
        assert path.read_bytes() == b"new live store"
        new_release.set()
        assert await asyncio.wait_for(new_task, 3)
        assert not path.exists()
        assert (await promotion.get_shadow(job.shadow_id)).attempt_count == 2
    finally:
        allow_cancel.set()
        new_release.set()
        for task in (old_task, new_task):
            if task:
                task.cancel()
        await asyncio.gather(*(task for task in (old_task, new_task) if task), return_exceptions=True)


async def test_terminal_cleanup_skips_live_lock_then_covers_more_than_100(shadow_repo, tmp_path):
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowReaper

    repo, promotion, deployment = shadow_repo
    router = ShadowStoreRouter(tmp_path / "isolated")
    jobs = []
    for index in range(103):
        parent = await parent_for(shadow_repo, f"cleanup-{index}")
        await finish_parent(repo, parent)
        claim = await promotion.claim_shadow("fixture-worker", 30)
        await promotion.complete_shadow(claim.shadow_id, "fixture-worker", claim.fencing_token, {})
        binding = PolicyExecutionBinding.model_validate(claim.policy_binding)
        path = router.path_for(binding)
        path.write_bytes(b"orphaned temporary store")
        jobs.append((binding, path))
    held = router.try_lock(jobs[0][0])
    try:
        await ShadowReaper(promotion, ShadowStoreRouter(router.root)).reap_once()
        assert jobs[0][1].exists()
        assert all(not path.exists() for _, path in jobs[1:])
    finally:
        held.close()
    await ShadowReaper(promotion, router).reap_once()
    assert all(not path.exists() for _, path in jobs)


@pytest.mark.parametrize("failure", ["identity", "artifact"])
async def test_fail_closed_shadow_protocol_or_artifact_no_primary_change(shadow_repo, tmp_path, failure):
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    completed = await finish_parent(repo, parent)
    router = ShadowStoreRouter(tmp_path / "isolated")
    calls = []
    class Executor:
        async def execute(self, request, authority, binding):
            calls.append(request)
            return {"response": "raw private body"}
    if failure == "artifact":
        repo.policy_assigner.runtime_hash = "e" * 64
    await ShadowWorker("worker", promotion, Executor(), router,
                       policy_assigner=repo.policy_assigner).run_once()
    job = await promotion.enqueue_shadow(parent.id)
    assert job.status == "failed"
    assert job.error_code == ("artifact_unavailable" if failure == "artifact" else "protocol_identity_invalid")
    assert bool(calls) == (failure == "identity")
    assert (await repo.get(parent.id)).result == completed.result


async def test_repository_summary_allowlist_rejects_raw_values(shadow_repo):
    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    job = await promotion.claim_shadow("worker", 30)
    await promotion.complete_shadow(job.shadow_id, "worker", job.fencing_token, {
        "response": "secret", "terminal_status": "secret", "cost": "secret",
        "input_tokens": True, "output_tokens": -1, "model_calls": 2,
        "latency_seconds": "NaN", "permission_outcome": "secret",
    })
    terminal = await promotion.get_shadow(job.shadow_id)
    assert "secret" not in json.dumps(terminal.result)
    assert terminal.result["input_tokens"] is None
    assert terminal.result["output_tokens"] is None
    assert terminal.result["cost"] is None
    assert terminal.result["model_calls"] == 2


async def test_shadow_authority_and_executor_capabilities_fail_closed(shadow_repo, tmp_path):
    from core.distributed.executor import LearningTaskExecutor
    from core.distributed.expert_contracts import RunExecutionAuthority
    from core.distributed.expert_gateway import DurableExpertGateway
    from core.distributed.expert_repository import ExpertJobRepository, ExpertFencingViolation
    from core.distributed.rehearsal_store import RehearsalStoreRouter, ShadowStoreRouter
    from tests.distributed.test_expert_contracts import request as expert_request, snapshot, budget
    from api.orchestrator import AgentOrchestrator
    from core.harness import LearningHarness

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    job = await promotion.claim_shadow("worker", 30)
    binding = PolicyExecutionBinding.model_validate(job.policy_binding)
    authority = RunExecutionAuthority(
        distributed_run_id=job.shadow_id, run_fencing_token=job.fencing_token,
        trace_id="a" * 32, attempt_number=job.attempt_count, worker_id="worker",
        parent_deadline_at=job.deadline_at, deployment_id=binding.deployment_id,
        effective_policy_hash=binding.effective_policy_hash, policy_cohort="shadow",
        state_namespace=binding.state_namespace, rehearsal_id=binding.rehearsal_id,
        execution_mode="shadow",
    )
    router = ShadowStoreRouter(tmp_path / "isolated")
    production = tmp_path / "production.sqlite3"
    with pytest.raises(ValueError, match="primary store or durable gateway"):
        LearningTaskExecutor(str(production), shadow_store_router=router)
    with pytest.raises(ValueError, match="primary store or durable gateway"):
        LearningTaskExecutor(None, expert_gateway=object(), shadow_store_router=router)
    with pytest.raises(ValueError, match="database logging"):
        LearningTaskExecutor(None, enable_db_logging=True, shadow_store_router=router)
    with pytest.raises(ValueError, match="store capability"):
        await LearningTaskExecutor(str(production)).execute(spec(), authority, binding)
    with pytest.raises(ValueError, match="filesystem lock"):
        await LearningTaskExecutor(None, shadow_store_router=router).execute(spec(), authority, binding)
    with pytest.raises(ValueError, match="explicit isolated"):
        authority.model_copy(update={"execution_mode": "distributed"}).validate_binding(binding)
    with pytest.raises(ValueError, match="shadow"):
        RehearsalStoreRouter(production, tmp_path / "rehearsal",
                            allowed_environment="rehearsal").path_for(binding)
    with pytest.raises(ValueError, match="inline experts"):
        LearningHarness(AgentOrchestrator(), str(production), execution_authority=authority,
                        pinned_policy=binding, state_namespace=binding.state_namespace,
                        expert_gateway=object())
    request = expert_request(
        learner_id="student-1", authority=authority,
        snapshot=snapshot(execution_mode="shadow", deployment_id=binding.deployment_id,
                          effective_policy_hash=binding.effective_policy_hash,
                          state_namespace=binding.state_namespace),
        budget=budget(deadline_at=job.deadline_at),
    )
    with pytest.raises(ValueError, match="primary run authority"):
        await DurableExpertGateway(object()).execute(request)
    with pytest.raises(ExpertFencingViolation, match="primary run authority"):
        await ExpertJobRepository(repo.session_factory).create_or_replay(request)
    assert not production.exists()


@pytest.mark.parametrize("path_kind", ["namespace", "deployment", "root_symlink", "child_symlink", "file_symlink"])
async def test_shadow_router_rejects_untrusted_paths(shadow_repo, tmp_path, path_kind):
    from core.distributed.rehearsal_store import ShadowStoreRouter

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    binding = PolicyExecutionBinding.model_validate((await promotion.enqueue_shadow(parent.id)).policy_binding)
    root = tmp_path / "isolated"
    outside = tmp_path / "outside"
    outside.mkdir()
    router = ShadowStoreRouter(root)
    if path_kind == "namespace":
        binding = binding.model_copy(update={"state_namespace": "shadow-../../production"})
    elif path_kind == "deployment":
        binding = binding.model_copy(update={"deployment_id": uuid4()})
    elif path_kind == "root_symlink":
        root.symlink_to(outside, target_is_directory=True)
    elif path_kind == "child_symlink":
        root.mkdir()
        (root / "shadow").symlink_to(outside, target_is_directory=True)
    else:
        path = router.path_for(binding)
        path.symlink_to(outside / "primary.sqlite3")
    with pytest.raises(ValueError):
        router.path_for(binding)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("unknown_tokens,failure", [
    (False, False), (True, False), (False, True), (False, "provider"),
])
async def test_real_executor_stub_provider_usage_reaches_pg_without_bodies(
    shadow_repo, tmp_path, monkeypatch, unknown_tokens, failure,
):
    from types import SimpleNamespace as NS
    from core import llm_service
    from config.settings import settings
    from core.distributed.executor import LearningTaskExecutor
    from core.distributed.rehearsal_store import ShadowStoreRouter
    from core.distributed.shadow_worker import ShadowWorker
    from core.harness import LearningHarness

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    primary = await finish_parent(repo, parent)
    calls = []
    native_count = 0

    async def create(**kwargs):
        nonlocal native_count
        calls.append(kwargs)
        if "tools" not in kwargs:
            body = json.dumps({"goal": "synthetic learning task", "steps": [
                {"step_id": "step-1", "agent": "Tutor", "objective": "provide a reply", "depends_on": []},
            ]})
            message = NS(content=body, tool_calls=[])
            usage = NS(prompt_tokens=11, completion_tokens=5)
        else:
            native_count += 1
            if native_count == 1:
                message = NS(content="", tool_calls=[NS(
                    id="lookup", function=NS(name="get_quiz_context", arguments="{}"),
                )])
                usage = NS(prompt_tokens=13, completion_tokens=7)
            else:
                if failure == "provider":
                    raise RuntimeError("private provider failure")
                message = NS(content="private stub tutor response", tool_calls=[])
                usage = None if unknown_tokens else NS(prompt_tokens=17, completion_tokens=9)
        return NS(choices=[NS(message=message, finish_reason="tool_calls" if message.tool_calls else "stop")], usage=usage)

    service = llm_service.LLMService(provider="openai", api_key="synthetic-unused", model="stub-model")
    service._client = NS(chat=NS(completions=NS(create=create)))
    monkeypatch.setattr(llm_service, "get_llm_service", lambda: service)
    # The SDK is fully stubbed; exercise generate's real accounting past its test guard.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(settings, "tutor_context_budget_tokens", 32000)
    if failure is True:
        original = LearningHarness.converse
        async def fail_after_real_execution(harness, *args, **kwargs):
            await original(harness, *args, **kwargs)
            raise RuntimeError("private failure after metered execution")
        monkeypatch.setattr(LearningHarness, "converse", fail_after_real_execution)
    router = ShadowStoreRouter(tmp_path / "isolated")
    job = await promotion.enqueue_shadow(parent.id)
    path = router.path_for(PolicyExecutionBinding.model_validate(job.policy_binding))
    worker = ShadowWorker(
        "metered-worker", promotion, LearningTaskExecutor(None, shadow_store_router=router),
        router, policy_assigner=repo.policy_assigner,
    )
    assert await worker.run_once()
    job = await promotion.enqueue_shadow(parent.id)
    assert job.status == ("failed" if failure else "completed")
    assert len(calls) == 3 and native_count == 2
    assert job.result["model_calls"] == 3
    # Coordinator delegation and the explicit quiz-context lookup are both charged.
    assert job.result["tool_calls"] == 2
    assert job.result["input_tokens"] == (None if unknown_tokens or failure == "provider" else 41)
    assert job.result["output_tokens"] == (None if unknown_tokens or failure == "provider" else 21)
    assert job.result["cost"] is None
    assert float(job.result["latency_seconds"]) >= 0
    assert job.result["structured_result"] == "unavailable"
    persisted = json.dumps(job.result)
    for raw in ("private stub tutor response", "synthetic private input", "synthetic-unused", "stub-model"):
        assert raw not in persisted
    assert (await repo.get(parent.id)).public_dict() == primary.public_dict()
    assert not path.exists() and not path.parent.exists()
    from core.distributed.promotion_models import PolicyObservationRecord
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyObservationRecord)) == 0


@pytest.mark.parametrize("field,value", [
    ("input_hash", "e" * 64),
    ("payload_reference", {"run_id": "forged", "input_hash": "e" * 64}),
    ("policy_binding", {}),
    ("deployment_version", 999),
    ("max_attempts", 999),
])
async def test_shadow_frozen_identity_is_immutable_in_postgres(shadow_repo, field, value):
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    job = await promotion.enqueue_shadow(parent.id)
    with pytest.raises(DBAPIError, match="identity is immutable"):
        async with repo.session_factory() as session, session.begin():
            await session.execute(update(PolicyShadowExecutionRecord).where(
                PolicyShadowExecutionRecord.shadow_id == job.shadow_id,
            ).values({field: value}))
    assert (await promotion.get_shadow(job.shadow_id)).policy_binding == job.policy_binding


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_shadow_terminal_summary_is_append_only(shadow_repo, operation):
    from sqlalchemy import delete, update
    from sqlalchemy.exc import DBAPIError

    repo, promotion, _ = shadow_repo
    parent = await parent_for(shadow_repo)
    await finish_parent(repo, parent)
    job = await promotion.claim_shadow("worker", 30)
    await promotion.complete_shadow(job.shadow_id, "worker", job.fencing_token, {})
    statement = (
        update(PolicyShadowExecutionRecord).values(result={"response": "private"})
        if operation == "update" else delete(PolicyShadowExecutionRecord)
    )
    with pytest.raises(DBAPIError, match="append-only|cannot be deleted"):
        async with repo.session_factory() as session, session.begin():
            await session.execute(statement.where(
                PolicyShadowExecutionRecord.shadow_id == job.shadow_id,
            ))
    assert (await promotion.get_shadow(job.shadow_id)).result["structured_result"] == "unavailable"
