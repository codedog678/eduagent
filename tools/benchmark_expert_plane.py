#!/usr/bin/env python3
"""Benchmark bounded Expert Plane queueing with fixed template execution."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
os.environ["LLM_PROVIDER"] = "template"

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.distributed.broker import RedisStreamBroker
from core.distributed.expert_contracts import ExpertRole
from core.distributed.expert_dispatcher import ExpertDispatcher
from core.distributed.expert_engine import ExpertEngine
from core.distributed.expert_gateway import DurableExpertGateway
from core.distributed.expert_models import DistributedExpertResult
from core.distributed.expert_repository import ExpertJobRepository
from core.distributed.expert_worker import ExpertWorker
from core.distributed.models import DistributedBase
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import upgrade_m1_schema
from core.llm_service import get_llm_service
from api.orchestrator import AgentOrchestrator
from core.harness import LearningHarness
from expert_plane_support import (
    expert_request,
    fingerprint,
    git_revision,
    git_worktree_evidence,
    isolated_database,
    percentile,
    redis_url,
    run_request,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run a bounded, template-only Expert Plane benchmark",
    )
    value.add_argument("--requests", type=int, default=30)
    value.add_argument("--concurrency", type=int, default=4)
    value.add_argument("--warmup", type=int, default=3)
    return value


class RecordingEngine:
    def __init__(self, inner, starts):
        self.inner = inner
        self.starts = starts

    async def execute(self, request, consumed=None):
        self.starts.setdefault(request.logical_key, perf_counter())
        return await self.inner.execute(request, consumed=consumed)


async def main(args: argparse.Namespace) -> int:
    if args.requests < 1 or args.concurrency < 1 or args.warmup < 0:
        raise ValueError("requests/concurrency must be positive; warmup >= 0")

    suffix = uuid4().hex
    stream = f"eduagent:benchmark:experts:{suffix}"
    group = f"eduagent-benchmark-experts-{suffix}"
    config = {
        "provider": "template",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "warmup": args.warmup,
        "roles": ["Assessment"],
        "running_limit_per_role": args.concurrency,
    }
    isolated = await isolated_database("eduagent_expert_benchmark")
    engine = isolated.engine
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(
        factory,
        parent_timeout_seconds=120,
    )
    expert_repository = ExpertJobRepository(
        factory,
        queued_limit_per_role=max(
            50,
            args.requests + args.warmup + 2,
        ),
        running_limit_per_role=args.concurrency,
        retry_base_seconds=0.05,
        retry_max_seconds=0.05,
    )
    redis = Redis.from_url(redis_url(), decode_responses=True)
    broker = RedisStreamBroker(redis, stream, group)
    stop = asyncio.Event()
    starts: dict[str, float] = {}
    worker_tasks = []
    dispatcher_task = None
    measured_job_ids: list[str] = []

    try:
        async with engine.begin() as connection:
            await connection.run_sync(DistributedBase.metadata.create_all)
            await upgrade_m1_schema(connection, 120)
        await broker.reset_for_tests()
        await broker.ensure_group()
        recording_engine = RecordingEngine(
            ExpertEngine(get_llm_service()),
            starts,
        )
        warmup_jobs, _, _ = await _enqueue_jobs(
            repository,
            expert_repository,
            suffix=suffix,
            count=args.warmup,
            phase="warmup",
        )
        warmup_worker = ExpertWorker(
            "benchmark-warmup",
            expert_repository,
            broker,
            recording_engine,
            roles={ExpertRole.ASSESSMENT},
            lease_seconds=15,
            heartbeat_seconds=1,
            pending_idle_ms=50,
            poll_block_ms=25,
        )
        if warmup_jobs:
            await ExpertDispatcher(
                expert_repository,
                broker,
            ).dispatch_once()
            for _ in warmup_jobs:
                assert await warmup_worker.run_once()
            await _wait_for_jobs(expert_repository, warmup_jobs)

        starts.clear()
        jobs, enqueue_times, logical_keys = await _enqueue_jobs(
            repository,
            expert_repository,
            suffix=suffix,
            count=args.requests,
            phase="measure",
        )
        measured_job_ids = list(jobs)
        queue_peak = 0
        for job_id in jobs:
            queue_peak += int(
                (await expert_repository.get(job_id)).status == "queued"
            )
        dispatcher_task = asyncio.create_task(
            _dispatcher_loop(
                ExpertDispatcher(expert_repository, broker),
                stop,
            )
        )
        worker_tasks = [
            asyncio.create_task(
                _worker_loop(
                    ExpertWorker(
                        f"benchmark-expert-{index}",
                        expert_repository,
                        broker,
                        recording_engine,
                        roles={ExpertRole.ASSESSMENT},
                        lease_seconds=15,
                        heartbeat_seconds=1,
                        pending_idle_ms=50,
                        poll_block_ms=25,
                    ),
                    stop,
                )
            )
            for index in range(args.concurrency)
        ]
        benchmark_started = min(enqueue_times.values())
        completion_times = await _wait_for_jobs(
            expert_repository,
            jobs,
        )
        benchmark_finished = max(completion_times.values())

        enqueue_to_start = [
            starts[logical_keys[job_id]] - enqueue_times[job_id]
            for job_id in jobs
        ]
        end_to_end = [
            completion_times[job_id] - enqueue_times[job_id]
            for job_id in jobs
        ]
        lock_wait = await _parent_lock_probe(
            repository,
            expert_repository,
            suffix=suffix,
        )
        results = await _accepted_results(factory, measured_job_ids)
        costs = [
            row.usage.get("estimated_cost_usd")
            for row in results
            if row.usage.get("estimated_cost_usd") is not None
        ]
        costs_known = len(costs) == len(results)
        async with engine.connect() as connection:
            postgres_version = str(
                (await connection.execute(text("SHOW server_version"))).scalar()
            )
        redis_info = await redis.info("server")
        elapsed = benchmark_finished - benchmark_started
        report = {
            "schema_version": 1,
            "status": "completed",
            "revision": git_revision(),
            "working_tree": git_worktree_evidence(),
            "config_fingerprint": fingerprint(config),
            "config": config,
            "request_count": args.requests,
            "warmup_request_count": args.warmup,
            "provider_request_count": sum(
                int(row.usage.get("model_calls", 0))
                for row in results
            ),
            "enqueue_to_start_ms": {
                "p50": round(
                    percentile(enqueue_to_start, 0.50) * 1000,
                    3,
                ),
                "p95": round(
                    percentile(enqueue_to_start, 0.95) * 1000,
                    3,
                ),
            },
            "end_to_end_ms": {
                "p50": round(percentile(end_to_end, 0.50) * 1000, 3),
                "p95": round(percentile(end_to_end, 0.95) * 1000, 3),
            },
            "throughput_requests_per_second": round(
                args.requests / elapsed,
                3,
            ),
            "queue_peak": queue_peak,
            "errors": args.requests - len(results),
            "estimated_cost_usd": (
                sum(float(value) for value in costs)
                if costs_known
                else None
            ),
            "cost_status": "known" if costs_known else "unknown",
            "parent_sqlite_owner_lock_wait_seconds": round(
                lock_wait,
                6,
            ),
            "parent_lock_measurement": (
                "actual LearningHarness owner lock held around one real "
                "DurableExpertGateway wait; gateway-only proxy, not a "
                "full parent business execution"
            ),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "postgres": postgres_version,
                "redis": str(redis_info.get("redis_version", "unknown")),
                "provider": "template",
                "model": "template",
            },
            "limitations": [
                "Template-mode control-plane benchmark; not provider-scale.",
                "Does not measure horizontal learner-state writes.",
                "Parent lock probe measures one durable expert wait.",
            ],
        }
    finally:
        stop.set()
        tasks = [
            task
            for task in [dispatcher_task, *worker_tasks]
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await broker.reset_for_tests()
        finally:
            try:
                await redis.aclose()
            finally:
                await isolated.close()

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


async def _dispatcher_loop(dispatcher, stop):
    while not stop.is_set():
        await dispatcher.dispatch_once()
        await asyncio.sleep(0.005)


async def _worker_loop(worker, stop):
    while not stop.is_set():
        await worker.run_once()


async def _enqueue_jobs(
    repository,
    expert_repository,
    *,
    suffix,
    count,
    phase,
):
    jobs = []
    enqueue_times = {}
    logical_keys = {}
    for index in range(count):
        request_id = f"expert-benchmark-{phase}-{suffix}-{index}"
        run = await repository.accept(
            run_request(
                request_id,
                learner_id=f"benchmark-{phase}-{suffix}-{index}",
            )
        )
        parent = await repository.claim(
            run.id,
            "evidence-parent",
            lease_seconds=120,
        )
        logical_key = f"{phase}-{suffix}-{index}"
        request = expert_request(parent, logical_key=logical_key)
        enqueued_at = perf_counter()
        job, _ = await expert_repository.create_or_replay(request)
        jobs.append(job.id)
        enqueue_times[job.id] = enqueued_at
        logical_keys[job.id] = logical_key
    return jobs, enqueue_times, logical_keys


async def _wait_for_jobs(expert_repository, job_ids):
    pending = set(job_ids)
    completed = {}
    async with asyncio.timeout(120):
        while pending:
            for job_id in list(pending):
                job = await expert_repository.get(job_id)
                if job.status in {
                    "completed",
                    "terminal_failed",
                    "exhausted",
                    "cancelled",
                    "parent_stale",
                }:
                    completed[job_id] = perf_counter()
                    pending.remove(job_id)
            if pending:
                await asyncio.sleep(0.002)
    return completed


async def _parent_lock_probe(
    repository,
    expert_repository,
    *,
    suffix,
):
    run = await repository.accept(
        run_request(
            f"expert-benchmark-lock-{suffix}",
            learner_id=f"benchmark-lock-{suffix}",
        )
    )
    parent = await repository.claim(
        run.id,
        "evidence-parent",
        lease_seconds=120,
    )
    request = expert_request(
        parent,
        logical_key=f"lock-probe-{suffix}",
    )
    gateway = DurableExpertGateway(
        expert_repository,
        poll_seconds=0.002,
    )
    with tempfile.TemporaryDirectory(
        prefix="eduagent-parent-lock-"
    ) as raw:
        orchestrator = AgentOrchestrator(enable_db_logging=False)
        harness = LearningHarness(
            orchestrator,
            str(Path(raw) / "harness.sqlite3"),
        )
        try:
            started = perf_counter()
            await gateway.execute(request)
            elapsed = perf_counter() - started
        finally:
            await harness.memory_worker.stop()
            harness.close()
            await orchestrator.close_database()
    return elapsed


async def _accepted_results(factory, job_ids):
    async with factory() as session:
        return list(
            await session.scalars(
                select(DistributedExpertResult).where(
                    DistributedExpertResult.job_id.in_(job_ids),
                    DistributedExpertResult.disposition == "accepted",
                )
            )
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parser().parse_args())))
