import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from core.distributed.contracts import RunStatus
from core.distributed.expert_contracts import ExpertErrorCode, ExpertRole
from core.distributed.expert_models import (
    DistributedExpertJob,
    DistributedExpertLease,
    DistributedExpertResult,
)
from core.distributed.expert_repository import ExpertFailure, ExpertFencingViolation, ResultReceipt
from core.distributed.models import DistributedLease, DistributedRunAttempt
from core.distributed.repository import FencingViolation
from tests.distributed.helpers import business_result, spec
from tests.distributed.test_expert_repository import envelope, request_for, usage

pytestmark = [pytest.mark.asyncio, pytest.mark.distributed_integration]


async def crossing_lock(repo, lock_sql, params, deadline, operation, *, lock_update=None):
    async with repo.session_factory() as locker, locker.begin():
        blocker_pid = await locker.scalar(text("SELECT pg_backend_pid()"))
        await locker.execute(text(lock_sql), params)
        task = asyncio.create_task(operation())
        try:
            async with repo.session_factory() as observer:
                # 只在目标操作确实等待本事务的锁后跨过期限，避免盲睡造成假阳性。
                for _ in range(400):
                    await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
                    blocked = await observer.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname=current_database() AND wait_event_type='Lock' "
                        "AND :blocker = ANY(pg_blocking_pids(pid))"
                    ), {"blocker": blocker_pid})
                    if blocked:
                        break
                    if task.done():
                        await task
                        raise AssertionError("operation returned before entering Lock wait")
                    await asyncio.sleep(0.005)
                else:
                    raise AssertionError("operation never entered PostgreSQL Lock wait")
                before = await observer.scalar(select(func.clock_timestamp()))
                assert before < deadline, "fixture failed to enter Lock wait before expiry"
                await observer.execute(text(
                    "SELECT pg_sleep(GREATEST(0, EXTRACT(EPOCH FROM "
                    "(CAST(:deadline AS timestamptz)-clock_timestamp()))) + 0.05)"
                ), {"deadline": deadline})
            assert not task.done(), "operation did not remain blocked"
            if lock_update is not None:
                await locker.execute(text(lock_update), params)
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    return await task


LOCKS = {
    "run": "SELECT id FROM distributed_runs WHERE id=:run_id FOR UPDATE",
    "lease": "SELECT run_id FROM distributed_leases WHERE run_id=:run_id FOR UPDATE",
    "attempt": "SELECT id FROM distributed_run_attempts WHERE run_id=:run_id FOR UPDATE",
    "step": "SELECT id FROM distributed_steps WHERE run_id=:run_id FOR UPDATE",
    "job": "SELECT id FROM distributed_expert_jobs WHERE id=:job_id FOR UPDATE",
    "expert_lease": "SELECT job_id FROM distributed_expert_leases WHERE job_id=:job_id FOR UPDATE",
    "result": "SELECT id FROM distributed_expert_results WHERE job_id=:job_id FOR UPDATE",
    "role": "SELECT pg_advisory_xact_lock(hashtextextended('role:Assessment', 0))",
    "queue": "SELECT pg_advisory_xact_lock(hashtextextended('queue:payload-bytes', 0))",
    "parent": "SELECT pg_advisory_xact_lock(hashtextextended('parent:' || :run_id, 0))",
}

PRIMARY_CASES = [
    (method, lock, "deadline")
    for method in ("renew", "start_step", "complete_step", "transition_committing", "complete", "fail")
    for lock in ("run", "lease", "attempt")
] + [
    (method, "step", "deadline") for method in ("start_step", "complete_step")
] + [
    (method, "run", "lease") for method in ("renew", "fail")
]
PRIMARY_METHODS = (
    "renew", "start_step", "complete_step", "transition_committing", "complete", "fail",
)


async def primary_setup(repo, method):
    run = await repo.accept(spec(request_id=f"primary-{method}"))
    claim = await repo.claim(run.id, "owner", 60)
    result = business_result(claim.policy_binding, ok=True)
    if method in {"start_step", "complete_step"}:
        await repo.start_step(run.id, "step", "hash", claim.fencing_token)
    if method == "complete":
        await repo.transition_committing(run.id, claim.fencing_token)
    operations = {
        "renew": lambda: repo.renew(run.id, "owner", claim.fencing_token, 60),
        "start_step": lambda: repo.start_step(run.id, "step", "hash", claim.fencing_token),
        "complete_step": lambda: repo.complete_step(run.id, "step", "hash", claim.fencing_token, result),
        "transition_committing": lambda: repo.transition_committing(run.id, claim.fencing_token),
        "complete": lambda: repo.complete(run.id, claim.fencing_token, result),
        "fail": lambda: repo.fail(run.id, claim.fencing_token, "probe", False),
    }
    return run, claim, operations[method]


async def set_expiry(repo, run_id, expiry, job_id=None):
    async with repo.session_factory() as session, session.begin():
        deadline = await session.scalar(select(func.clock_timestamp())) + timedelta(seconds=0.8)
        if expiry == "deadline":
            row = await session.scalar(select(DistributedRunAttempt).where(
                DistributedRunAttempt.run_id == run_id
            ))
            row.deadline_at = deadline
        elif expiry == "lease":
            row = await session.get(DistributedLease, run_id)
            row.expires_at = deadline
        elif expiry == "expert_lease":
            row = await session.get(DistributedExpertLease, job_id)
            row.expires_at = deadline
        else:
            row = await session.get(DistributedExpertJob, job_id)
            row.deadline_at = deadline
        return deadline


@pytest.mark.parametrize("method,lock,expiry", PRIMARY_CASES)
async def test_primary_rejects_expiry_after_last_lock(repo, method, lock, expiry):
    run, claim, operation = await primary_setup(repo, method)
    before = await repo.get(run.id)
    lease_before = await repo.lease(run.id)
    deadline = await set_expiry(repo, run.id, expiry)
    with pytest.raises(FencingViolation):
        await crossing_lock(repo, LOCKS[lock], {"run_id": run.id}, deadline, operation)
    after = await repo.get(run.id)
    assert (after.status, after.result, after.error_code) == (
        before.status, before.result, before.error_code
    )
    assert (await repo.lease(run.id)).owner == lease_before.owner
    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)
        assert attempt.finished_at is None
        assert attempt.status == RunStatus.RUNNING
        if method in {"start_step", "complete_step"}:
            from core.distributed.models import DistributedStep

            step = await session.scalar(select(DistributedStep).where(
                DistributedStep.run_id == run.id
            ))
            assert step.status == RunStatus.RUNNING
            assert step.result is None


@pytest.mark.parametrize("method", PRIMARY_METHODS)
async def test_primary_active_mutations_still_work(repo, method):
    _, _, operation = await primary_setup(repo, method)
    await operation()


EXPERT_CASES = [
    (method, lock, "deadline")
    for method in ("create", "claim", "renew", "submit_result", "fail", "terminal")
    for lock in ("run", "lease", "attempt", "job")
] + [
    (method, "expert_lease", "deadline")
    for method in ("claim", "renew", "submit_result", "fail", "terminal")
] + [
    (method, "result", "deadline") for method in ("submit_result", "fail", "terminal")
] + [
    ("create", lock, "deadline") for lock in ("parent", "queue", "role")
] + [
    ("claim", "role", "deadline")
] + [
    (method, "run", "lease") for method in ("renew", "submit_result")
] + [
    (method, lock, expiry)
    for method in ("renew", "submit_result", "fail")
    for lock, expiry in (("expert_lease", "expert_lease"), ("result" if method != "renew" else "job", "job_deadline"))
]


async def expert_setup(repo, expert_repo, method):
    run = await repo.accept(spec(request_id=f"expert-{method}"))
    claim = await repo.claim(run.id, "parent-worker", 60)
    request = request_for(claim)
    job, _ = await expert_repo.create_or_replay(request)
    leased = None
    if method not in {"create", "claim"}:
        leased = await expert_repo.claim(job.id, "expert-worker", {ExpertRole.ASSESSMENT}, 60)
    async with repo.session_factory() as session, session.begin():
        session.add(DistributedExpertResult(
            job_id=job.id, expert_fencing_token=0, worker_id="old",
            disposition="rejected", rejection_code="expert_token_stale",
            draft=None, usage=usage(model_calls=0).model_dump(mode="json"),
            diagnostics=[], created_at=await session.scalar(select(func.clock_timestamp())),
        ))
    if method == "terminal":
        receipt = await expert_repo.submit_result(job.id, "expert-worker", leased.fencing_token, envelope(request))
        assert receipt.accepted
    return run, claim, request, job, leased


def expert_operation(expert_repo, method, request, job, leased):
    token = leased.fencing_token if leased else 0
    operations = {
        "create": lambda: expert_repo.create_or_replay(request),
        "claim": lambda: expert_repo.claim(job.id, "expert-worker", {ExpertRole.ASSESSMENT}, 60),
        "renew": lambda: expert_repo.renew(job.id, "expert-worker", token, 60),
        "submit_result": lambda: expert_repo.submit_result(job.id, "expert-worker", token, envelope(request)),
        "fail": lambda: expert_repo.fail_attempt(job.id, "expert-worker", token, ExpertFailure(
            code=ExpertErrorCode.PROVIDER_UNAVAILABLE, retryable=False, usage=usage(),
        )),
        "terminal": lambda: expert_repo.terminal(job.id, job.parent_fencing_token),
    }
    return operations[method]


@pytest.mark.parametrize("method,lock,expiry", EXPERT_CASES)
async def test_expert_rejects_expiry_after_last_lock(repo, expert_repo, method, lock, expiry):
    run, claim, request, job, leased = await expert_setup(repo, expert_repo, method)
    before = await expert_repo.get(job.id)
    accepted_before = await expert_repo.accepted_result_count(job.id)
    deadline = await set_expiry(repo, run.id, expiry, job.id)
    if method == "create":
        request = request_for(replace(claim, deadline_at=deadline))
        async with repo.session_factory() as session, session.begin():
            row = await session.get(DistributedExpertJob, job.id)
            row.input_hash = request.input_hash
            row.payload = request.model_dump(mode="json")
            row.deadline_at = deadline
    operation = expert_operation(expert_repo, method, request, job, leased)
    if method in {"submit_result", "fail"}:
        receipt = await crossing_lock(repo, LOCKS[lock], {
            "run_id": run.id, "job_id": job.id,
        }, deadline, operation)
        assert isinstance(receipt, ResultReceipt), "expired attempt still mutated the job"
        assert not receipt.accepted, "expired parent/expert result was accepted"
        assert await expert_repo.result_count(job.id) == 2
    else:
        with pytest.raises(ExpertFencingViolation):
            await crossing_lock(repo, LOCKS[lock], {
                "run_id": run.id, "job_id": job.id,
            }, deadline, operation)
    after = await expert_repo.get(job.id)
    assert (after.status, after.completed_at, after.error_code) == (
        before.status, before.completed_at, before.error_code
    )
    assert await expert_repo.accepted_result_count(job.id) == accepted_before


@pytest.mark.parametrize("method", ("create", "claim", "renew", "submit_result", "fail", "terminal"))
async def test_expert_active_mutations_still_work(repo, expert_repo, method):
    _, _, request, job, leased = await expert_setup(repo, expert_repo, method)
    result = await expert_operation(expert_repo, method, request, job, leased)()
    if method == "submit_result":
        assert result.accepted
    elif method == "terminal":
        assert result.outcome == "succeeded"


@pytest.mark.parametrize("lock", ("attempt", "result"))
async def test_expert_reaper_uses_time_after_last_lock(repo, expert_repo, lock):
    run, _, _, job, _ = await expert_setup(repo, expert_repo, "renew")
    deadline = await set_expiry(repo, run.id, "deadline", job.id)
    changed = await crossing_lock(repo, LOCKS[lock], {
        "run_id": run.id, "job_id": job.id,
    }, deadline, expert_repo.reap_expired)
    assert changed == [job.id]
    assert (await expert_repo.get(job.id)).status == "parent_stale"
    assert await expert_repo.accepted_result_count(job.id) == 0


@pytest.mark.parametrize("lock", ("job", "expert_lease"))
async def test_create_prelocks_old_epoch_before_authority_check(repo, expert_repo, lock):
    run, claim, _, old_job, _ = await expert_setup(repo, expert_repo, "create")
    async with repo.session_factory() as session, session.begin():
        row = await session.get(DistributedExpertJob, old_job.id)
        row.parent_fencing_token = 0
    deadline = await set_expiry(repo, run.id, "deadline")
    request = request_for(replace(claim, deadline_at=deadline), logical_key="new")
    with pytest.raises(ExpertFencingViolation):
        await crossing_lock(repo, LOCKS[lock], {
            "run_id": run.id, "job_id": old_job.id,
        }, deadline, lambda: expert_repo.create_or_replay(request))
    assert (await expert_repo.get(old_job.id)).status == "queued"


async def future_boundary(repo):
    async with repo.session_factory() as session:
        return await session.scalar(select(func.clock_timestamp())) + timedelta(seconds=0.8)


@pytest.mark.parametrize("lock", ("run", "lease"))
async def test_primary_claim_timestamps_start_after_last_lock(repo, lock):
    run = await repo.accept(spec(request_id=f"claim-{lock}"))
    boundary = await future_boundary(repo)
    claim = await crossing_lock(repo, LOCKS[lock], {"run_id": run.id}, boundary,
                                lambda: repo.claim(run.id, "owner", 1))
    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)
        assert attempt.started_at > boundary
    assert (await repo.lease(run.id)).expires_at > boundary + timedelta(seconds=1)


async def test_primary_reaper_timestamps_follow_attempt_lock(repo):
    run, claim, _ = await primary_setup(repo, "renew")
    async with repo.session_factory() as session, session.begin():
        lease = await session.get(DistributedLease, run.id)
        lease.expires_at = await session.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)
    boundary = await future_boundary(repo)
    changed = await crossing_lock(repo, LOCKS["attempt"], {"run_id": run.id}, boundary,
                                  lambda: repo.requeue_expired(boundary))
    assert changed == [run.id]
    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)
        assert attempt.finished_at > boundary
    assert (await repo.get(run.id)).updated_at > boundary


async def test_expert_claim_timestamps_follow_role_lock(repo, expert_repo):
    run, _, _, job, _ = await expert_setup(repo, expert_repo, "claim")
    boundary = await future_boundary(repo)
    claim = await crossing_lock(repo, LOCKS["role"], {"run_id": run.id}, boundary,
                                lambda: expert_repo.claim(job.id, "expert-worker", {ExpertRole.ASSESSMENT}, 1))
    assert claim.lease_expires_at > boundary + timedelta(seconds=1)
    assert (await expert_repo.get(job.id)).updated_at > boundary


@pytest.mark.parametrize("method", ("claim", "renew", "submit_result", "fail"))
async def test_expert_live_guard_refreshes_job_state_after_lock(repo, expert_repo, method):
    run, _, request, job, leased = await expert_setup(repo, expert_repo, method)
    boundary = await future_boundary(repo)
    operation = expert_operation(expert_repo, method, request, job, leased)
    params = {"run_id": run.id, "job_id": job.id}
    lock_update = "UPDATE distributed_expert_jobs SET status='cancelled' WHERE id=:job_id"
    if method in {"submit_result", "fail"}:
        receipt = await crossing_lock(repo, LOCKS["job"], params, boundary, operation,
                                      lock_update=lock_update)
        assert isinstance(receipt, ResultReceipt)
        assert not receipt.accepted
    else:
        with pytest.raises(ExpertFencingViolation):
            await crossing_lock(repo, LOCKS["job"], params, boundary, operation,
                                lock_update=lock_update)
    assert (await expert_repo.get(job.id)).status == "cancelled"
    assert await expert_repo.accepted_result_count(job.id) == 0
