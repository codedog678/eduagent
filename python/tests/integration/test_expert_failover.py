from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.distributed.broker import RedisRunBroker, RedisStreamBroker
from core.distributed.contracts import RunStatus
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.expert_dispatcher import ExpertDispatcher
from core.distributed.expert_gateway import DurableExpertGateway
from core.distributed.expert_models import (
    DistributedExpertJob,
    DistributedExpertLease,
    DistributedExpertResult,
)
from core.distributed.expert_reaper import ExpertReaper
from core.distributed.expert_repository import ExpertJobRepository
from core.distributed.models import DistributedBase
from core.distributed.repository import DistributedRunRepository
from core.distributed.worker import RunWorker
from tests.distributed.helpers import spec
from tests.distributed.test_expert_repository import parent_claim, request_for

pytestmark = pytest.mark.distributed_integration

PYTHON_ROOT = Path(__file__).parents[2]


@pytest_asyncio.fixture
async def repo():
    database_url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(DistributedBase.metadata.drop_all)
        await connection.run_sync(DistributedBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield DistributedRunRepository(factory)
    async with engine.begin() as connection:
        await connection.run_sync(DistributedBase.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def expert_repo(repo):
    return ExpertJobRepository(
        repo.session_factory,
        retry_base_seconds=0.1,
        retry_max_seconds=0.1,
    )


@pytest_asyncio.fixture
async def expert_broker():
    redis_url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("DISTRIBUTED_TEST_REDIS_URL is not configured")
    client = Redis.from_url(redis_url, decode_responses=True)
    suffix = uuid4().hex
    broker = RedisStreamBroker(
        client,
        f"test:experts:process:{suffix}",
        f"test-expert-workers-{suffix}",
    )
    await broker.reset_for_tests()
    yield broker
    await broker.reset_for_tests()
    await client.aclose()


def process_env(
    *,
    expert_broker,
    worker_id: str,
    pause_before_result: float,
    run_stream: str | None = None,
    run_group: str | None = None,
) -> dict[str, str]:
    database_url = os.environ["DISTRIBUTED_TEST_DATABASE_URL"]
    redis_url = os.environ["DISTRIBUTED_TEST_REDIS_URL"]
    suffix = uuid4().hex
    return {
        **os.environ,
        "PYTHONPATH": str(PYTHON_ROOT),
        "DISTRIBUTED_ENABLED": "true",
        "DISTRIBUTED_EXPERTS_ENABLED": "true",
        "DISTRIBUTED_DATABASE_URL": database_url,
        "DISTRIBUTED_REDIS_URL": redis_url,
        "DISTRIBUTED_STREAM": (
            run_stream or f"test:runs:expert-process:{suffix}"
        ),
        "DISTRIBUTED_CONSUMER_GROUP": (
            run_group or f"test-run-workers-{suffix}"
        ),
        "EXPERT_STREAM": expert_broker.stream,
        "EXPERT_CONSUMER_GROUP": expert_broker.group,
        "EXPERT_WORKER_ID": worker_id,
        "EXPERT_WORKER_ROLES": "Assessment",
        "EXPERT_LEASE_SECONDS": "3",
        "EXPERT_HEARTBEAT_SECONDS": "0.5",
        "EXPERT_POLL_BLOCK_MS": "50",
        "EXPERT_RETRY_BASE_SECONDS": "0.1",
        "EXPERT_RETRY_MAX_SECONDS": "0.1",
        "EXPERT_DEMO_PAUSE_BEFORE_RESULT_SECONDS": str(
            pause_before_result
        ),
        "LLM_PROVIDER": "template",
        "MEMORY_RETRIEVAL_MODE": "lexical",
        "MEMORY_WORKER_ENABLED": "false",
    }


def expert_worker_process(
    *,
    expert_broker,
    worker_id: str,
    pause_before_result: float = 0,
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "core.distributed.cli",
            "expert-worker",
        ],
        cwd=PYTHON_ROOT,
        env=process_env(
            expert_broker=expert_broker,
            worker_id=worker_id,
            pause_before_result=pause_before_result,
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def parent_probe_process(
    *,
    expert_broker,
    run_stream: str,
    run_group: str,
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "parent-probe",
        ],
        cwd=PYTHON_ROOT,
        env=process_env(
            expert_broker=expert_broker,
            worker_id="unused",
            pause_before_result=0,
            run_stream=run_stream,
            run_group=run_group,
        ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def stop_process(
    process: subprocess.Popen | None,
    *,
    kill: bool = False,
) -> str:
    if process is None:
        return ""
    if process.poll() is None:
        process.kill() if kill else process.terminate()
    try:
        _, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        _, stderr = process.communicate(timeout=5)
    return stderr


def assert_running(process: subprocess.Popen, label: str) -> None:
    code = process.poll()
    if code is None:
        return
    stderr = process.stderr.read() if process.stderr is not None else ""
    raise AssertionError(
        f"{label} exited early with code {code}\n{stderr}"
    )


async def wait_until(predicate, *, timeout: float = 15):
    async with asyncio.timeout(timeout):
        while True:
            value = await predicate()
            if value:
                return value
            await asyncio.sleep(0.05)


async def job_for_run(repo, run_id: str):
    async with repo.session_factory() as session:
        return await session.scalar(
            select(DistributedExpertJob)
            .where(DistributedExpertJob.parent_run_id == run_id)
            .order_by(DistributedExpertJob.created_at.desc())
        )


async def lease_for_job(repo, job_id: str):
    async with repo.session_factory() as session:
        return await session.get(DistributedExpertLease, job_id)


async def results_for_job(repo, job_id: str):
    async with repo.session_factory() as session:
        return list(
            await session.scalars(
                select(DistributedExpertResult)
                .where(DistributedExpertResult.job_id == job_id)
                .order_by(DistributedExpertResult.created_at)
            )
        )


async def dispatch_created_job(repo, expert_repo, expert_broker, request_id):
    _, parent = await parent_claim(repo, request_id)
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    assert await ExpertDispatcher(
        expert_repo,
        expert_broker,
    ).dispatch_once() == 1
    return job


async def test_killed_expert_worker_gets_higher_token_and_one_result(
    repo,
    expert_repo,
    expert_broker,
):
    job = await dispatch_created_job(
        repo,
        expert_repo,
        expert_broker,
        "expert-worker-kill",
    )
    first = expert_worker_process(
        expert_broker=expert_broker,
        worker_id="expert-a",
        pause_before_result=30,
    )
    second = None
    try:
        await wait_until(
            lambda: _job_has_status(
                expert_repo,
                job.id,
                "running",
                process=first,
                label="first expert worker",
            )
        )
        first_lease = await lease_for_job(repo, job.id)
        assert first_lease.fencing_token == 1
        stop_process(first, kill=True)

        await asyncio.sleep(3.1)
        assert await ExpertReaper(expert_repo).reap_once() == [job.id]
        await asyncio.sleep(0.15)
        assert await ExpertDispatcher(
            expert_repo,
            expert_broker,
        ).dispatch_once() == 1

        second = expert_worker_process(
            expert_broker=expert_broker,
            worker_id="expert-b",
        )
        await wait_until(
            lambda: _accepted_result_exists(
                expert_repo,
                job.id,
                process=second,
                label="second expert worker",
            )
        )

        final_lease = await lease_for_job(repo, job.id)
        rows = await results_for_job(repo, job.id)
        assert final_lease.fencing_token == 2
        assert sum(row.disposition == "accepted" for row in rows) == 1
        assert {row.expert_fencing_token for row in rows} == {1, 2}
    finally:
        stop_process(first)
        stop_process(second)


async def test_killed_parent_makes_late_result_parent_stale(
    repo,
    expert_repo,
    expert_broker,
):
    suffix = uuid4().hex
    run_stream = f"test:runs:parent-process:{suffix}"
    run_group = f"test-parent-workers-{suffix}"
    run_broker = RedisRunBroker(
        expert_broker.redis,
        run_stream,
        run_group,
    )
    await run_broker.reset_for_tests()
    await run_broker.ensure_group()
    run = await repo.accept(spec(request_id="parent-worker-kill"))
    assert await OutboxDispatcher(
        repo,
        run_broker,
    ).dispatch_once() == 1
    parent = parent_probe_process(
        expert_broker=expert_broker,
        run_stream=run_stream,
        run_group=run_group,
    )
    worker = None
    try:
        job = await wait_until(
            lambda: _job_created_by_probe(
                repo,
                run.id,
                process=parent,
            )
        )
        assert await ExpertDispatcher(
            expert_repo,
            expert_broker,
        ).dispatch_once() == 1
        worker = expert_worker_process(
            expert_broker=expert_broker,
            worker_id="expert-parent-stale",
            pause_before_result=5,
        )
        await wait_until(
            lambda: _job_has_status(
                expert_repo,
                job.id,
                "running",
                process=worker,
                label="late-result expert worker",
            )
        )

        stop_process(parent, kill=True)
        rows = await wait_until(
            lambda: _result_with_rejection(
                repo,
                job.id,
                "parent_stale",
                process=worker,
            ),
            timeout=10,
        )
        assert sum(row.disposition == "accepted" for row in rows) == 0
        assert await ExpertReaper(expert_repo).reap_once() == [job.id]
        assert (await expert_repo.get(job.id)).status == "parent_stale"
        assert (await repo.get(run.id)).result is None
    finally:
        stop_process(parent)
        stop_process(worker)
        await run_broker.reset_for_tests()


async def test_duplicate_redis_messages_produce_one_accepted_result(
    repo,
    expert_repo,
    expert_broker,
):
    _, parent = await parent_claim(repo, "expert-duplicate-message")
    request = request_for(parent)
    job, _ = await expert_repo.create_or_replay(request)
    row = (await expert_repo.pending_outbox(1))[0]
    await expert_broker.publish(row.event_key, row.payload)
    await expert_broker.publish(row.event_key, row.payload)
    worker = expert_worker_process(
        expert_broker=expert_broker,
        worker_id="expert-duplicate",
    )
    try:
        await wait_until(
            lambda: _accepted_and_drained(
                expert_repo,
                expert_broker,
                job.id,
                process=worker,
            )
        )
        rows = await results_for_job(repo, job.id)
        assert sum(row.disposition == "accepted" for row in rows) == 1
        assert len(rows) == 1
    finally:
        stop_process(worker)


async def test_cancel_waiting_parent_rejects_late_draft(
    repo,
    expert_repo,
    expert_broker,
):
    job = await dispatch_created_job(
        repo,
        expert_repo,
        expert_broker,
        "expert-cancel-parent",
    )
    worker = expert_worker_process(
        expert_broker=expert_broker,
        worker_id="expert-cancelled",
        pause_before_result=1,
    )
    try:
        await wait_until(
            lambda: _job_has_status(
                expert_repo,
                job.id,
                "running",
                process=worker,
                label="cancelled-parent expert worker",
            )
        )
        await repo.cancel(job.parent_run_id)
        rows = await wait_until(
            lambda: _result_with_rejection(
                repo,
                job.id,
                "parent_stale",
                process=worker,
            )
        )

        cancelled = await repo.get(job.parent_run_id)
        assert cancelled.status == RunStatus.CANCELLED
        assert cancelled.result is None
        assert (await expert_repo.get(job.id)).status == "cancelled"
        assert sum(row.disposition == "accepted" for row in rows) == 0
    finally:
        stop_process(worker)


async def _job_has_status(
    expert_repo,
    job_id,
    status,
    *,
    process,
    label,
):
    assert_running(process, label)
    return (await expert_repo.get(job_id)).status == status


async def _accepted_result_exists(
    expert_repo,
    job_id,
    *,
    process,
    label,
):
    assert_running(process, label)
    return await expert_repo.accepted_result_count(job_id) == 1


async def _job_created_by_probe(repo, run_id, *, process):
    assert_running(process, "parent probe")
    return await job_for_run(repo, run_id)


async def _result_with_rejection(
    repo,
    job_id,
    rejection_code,
    *,
    process,
):
    assert_running(process, "expert worker")
    rows = await results_for_job(repo, job_id)
    return (
        rows
        if any(row.rejection_code == rejection_code for row in rows)
        else None
    )


async def _accepted_and_drained(
    expert_repo,
    expert_broker,
    job_id,
    *,
    process,
):
    assert_running(process, "duplicate-delivery expert worker")
    return (
        await expert_repo.accepted_result_count(job_id) == 1
        and await expert_broker.pending_count() == 0
    )


class _ProbeExecutor:
    def __init__(self, expert_repository):
        self.gateway = DurableExpertGateway(
            expert_repository,
            poll_seconds=0.02,
        )

    async def execute(self, run_request, authority):
        claim = SimpleNamespace(
            run_id=str(authority.distributed_run_id),
            request_id=run_request.request_id,
            learner_id=run_request.learner_id,
            fencing_token=authority.run_fencing_token,
            trace_id=authority.trace_id,
            attempt_count=authority.attempt_number,
            deadline_at=authority.parent_deadline_at,
        )
        terminal = await self.gateway.execute(request_for(claim))
        return {"expert_outcome": terminal.outcome}


async def _run_parent_probe() -> None:
    database_url = os.environ["DISTRIBUTED_DATABASE_URL"]
    redis_url = os.environ["DISTRIBUTED_REDIS_URL"]
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(
        factory,
        parent_timeout_seconds=30,
    )
    expert_repository = ExpertJobRepository(factory)
    redis = Redis.from_url(redis_url, decode_responses=True)
    broker = RedisRunBroker(
        redis,
        os.environ["DISTRIBUTED_STREAM"],
        os.environ["DISTRIBUTED_CONSUMER_GROUP"],
    )
    try:
        worker = RunWorker(
            "parent-worker",
            repository,
            broker,
            _ProbeExecutor(expert_repository),
            lease_seconds=3,
            heartbeat_seconds=0.5,
            max_attempts=3,
        )
        await worker.run_once()
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__" and sys.argv[1:2] == ["parent-probe"]:
    asyncio.run(_run_parent_probe())
