from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.distributed.broker import RedisRunBroker
from core.distributed.contracts import RunStatus
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.models import DistributedBase
from core.distributed.reaper import LeaseReaper
from core.distributed.repository import DistributedRunRepository
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


async def wait_for_status(repo, run_id, expected, timeout=20):
    async with asyncio.timeout(timeout):
        while True:
            run = await repo.get(run_id)
            if run is not None and run.status == expected:
                return run
            await asyncio.sleep(0.05)


def worker_process(
    *,
    database_url: str,
    redis_url: str,
    stream: str,
    group: str,
    store_path: Path,
    worker_id: str,
    pause_before_commit: float,
) -> subprocess.Popen:
    env = {
        **os.environ,
        "DISTRIBUTED_ENABLED": "true",
        "DISTRIBUTED_DATABASE_URL": database_url,
        "DISTRIBUTED_REDIS_URL": redis_url,
        "DISTRIBUTED_STREAM": stream,
        "DISTRIBUTED_CONSUMER_GROUP": group,
        "DISTRIBUTED_WORKER_ID": worker_id,
        "DISTRIBUTED_LEASE_SECONDS": "3",
        "DISTRIBUTED_HEARTBEAT_SECONDS": "0.5",
        "DISTRIBUTED_MAX_ATTEMPTS": "3",
        "DISTRIBUTED_DEMO_PAUSE_BEFORE_COMMIT_SECONDS": str(
            pause_before_commit
        ),
        "HARNESS_STORE_PATH": str(store_path),
        "LLM_PROVIDER": "template",
        "MEMORY_RETRIEVAL_MODE": "lexical",
        "MEMORY_WORKER_ENABLED": "false",
    }
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "core.distributed.cli",
            "worker",
        ],
        cwd=Path(__file__).parents[2],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


async def test_killed_worker_is_fenced_and_second_worker_replays_once(
    tmp_path,
):
    database_url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    redis_url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("distributed PostgreSQL and Redis URLs are required")

    suffix = uuid4().hex
    stream = f"eduagent:test:failover:{suffix}"
    group = f"eduagent-test-{suffix}"
    store_path = tmp_path / "shared-harness.sqlite3"
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(factory, max_attempts=3)
    redis = Redis.from_url(redis_url, decode_responses=True)
    broker = RedisRunBroker(redis, stream, group)
    dispatcher = OutboxDispatcher(repository, broker)
    reaper = LeaseReaper(repository)
    first = None
    second = None

    try:
        async with engine.begin() as connection:
            await connection.run_sync(DistributedBase.metadata.drop_all)
            await connection.run_sync(DistributedBase.metadata.create_all)
        await broker.ensure_group()

        run = await repository.accept(spec(request_id="kill-recover"))
        assert await dispatcher.dispatch_once() == 1

        first = worker_process(
            database_url=database_url,
            redis_url=redis_url,
            stream=stream,
            group=group,
            store_path=store_path,
            worker_id="worker-a",
            pause_before_commit=30,
        )
        await wait_for_status(
            repository,
            run.id,
            RunStatus.COMMITTING,
        )
        stop_process(first)

        await asyncio.sleep(3.2)
        assert await reaper.reap_once() == [run.id]
        assert await dispatcher.dispatch_once() == 1

        second = worker_process(
            database_url=database_url,
            redis_url=redis_url,
            stream=stream,
            group=group,
            store_path=store_path,
            worker_id="worker-b",
            pause_before_commit=0,
        )
        completed = await wait_for_status(
            repository,
            run.id,
            RunStatus.COMPLETED,
        )

        assert completed.attempt_count == 2
        spans = await repository.trace(run.id)
        assert {span.name for span in spans} >= {
            "run.attempt",
            "business.execute",
            "run.commit",
        }
        assert {
            span.attributes.get("worker.id")
            for span in spans
            if span.name == "run.attempt"
        } >= {"worker-a", "worker-b"}
        with sqlite3.connect(store_path) as business:
            run_count = business.execute(
                "SELECT COUNT(*) FROM runs "
                "WHERE learner=? AND request=? AND status='completed'",
                ("student", "kill-recover"),
            ).fetchone()[0]
        assert run_count == 1
    finally:
        stop_process(first)
        stop_process(second)
        await redis.delete(stream)
        await redis.aclose()
        async with engine.begin() as connection:
            await connection.run_sync(DistributedBase.metadata.drop_all)
        await engine.dispose()
