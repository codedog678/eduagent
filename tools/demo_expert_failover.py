#!/usr/bin/env python3
"""Produce machine-readable Expert Worker crash-recovery evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.distributed.broker import RedisStreamBroker
from core.distributed.expert_dispatcher import ExpertDispatcher
from core.distributed.expert_models import (
    DistributedExpertLease,
    DistributedExpertResult,
)
from core.distributed.expert_reaper import ExpertReaper
from core.distributed.expert_repository import ExpertJobRepository
from core.distributed.models import DistributedBase
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import upgrade_m1_schema
from core.harness_migrations import migrate
from expert_plane_support import (
    expert_request,
    fingerprint,
    git_revision,
    git_worktree_evidence,
    isolated_database,
    redis_url,
    run_request,
    spawn_expert_worker,
    wait_until,
)


async def main() -> int:
    suffix = uuid4().hex
    stream = f"eduagent:evidence:experts:{suffix}"
    group = f"eduagent-evidence-experts-{suffix}"
    config = {
        "provider": "template",
        "expert_lease_seconds": 3,
        "expert_heartbeat_seconds": 0.5,
        "expert_retry_seconds": 0.1,
        "roles": ["Assessment"],
        "scenario": "kill-before-result",
    }
    isolated = await isolated_database("eduagent_expert_demo")
    engine = isolated.engine
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(
        factory,
        parent_timeout_seconds=120,
    )
    expert_repository = ExpertJobRepository(
        factory,
        retry_base_seconds=0.1,
        retry_max_seconds=0.1,
    )
    redis = Redis.from_url(redis_url(), decode_responses=True)
    broker = RedisStreamBroker(redis, stream, group)
    first = None
    second = None
    evidence = None

    with tempfile.TemporaryDirectory(prefix="eduagent-expert-demo-") as raw:
        log_dir = Path(raw)
        learner_store = log_dir / "learner-store.sqlite3"
        with sqlite3.connect(learner_store) as connection:
            migrate(connection)
        learner_before = _learner_state(learner_store)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    DistributedBase.metadata.create_all
                )
                await upgrade_m1_schema(connection, 120)
            await broker.reset_for_tests()
            await broker.ensure_group()

            run = await repository.accept(
                run_request(
                    f"expert-demo-{suffix}",
                    learner_id=f"demo-{suffix}",
                )
            )
            parent = await repository.claim(
                run.id,
                "evidence-parent",
                lease_seconds=120,
            )
            request = expert_request(
                parent,
                logical_key=f"assessment-{suffix}",
            )
            job, _ = await expert_repository.create_or_replay(request)
            assert await ExpertDispatcher(
                expert_repository,
                broker,
            ).dispatch_once() == 1

            first = spawn_expert_worker(
                stream=stream,
                group=group,
                worker_id=f"expert-a-{suffix[:8]}",
                pause_before_result=30,
                suffix=suffix,
                log_dir=log_dir,
                database_url_value=isolated.url,
            )

            async def first_running():
                first.assert_running("first expert worker")
                return (
                    await expert_repository.get(job.id)
                ).status == "running"

            await wait_until(first_running)
            first_lease = await _lease(factory, job.id)
            first.stop(kill=True)
            await asyncio.sleep(3.1)
            assert await ExpertReaper(
                expert_repository
            ).reap_once() == [job.id]
            await asyncio.sleep(0.15)
            assert await ExpertDispatcher(
                expert_repository,
                broker,
            ).dispatch_once() == 1

            second = spawn_expert_worker(
                stream=stream,
                group=group,
                worker_id=f"expert-b-{suffix[:8]}",
                pause_before_result=0,
                suffix=suffix,
                log_dir=log_dir,
                database_url_value=isolated.url,
            )

            async def accepted():
                second.assert_running("second expert worker")
                return (
                    await expert_repository.accepted_result_count(job.id)
                    == 1
                )

            await wait_until(accepted)
            final_lease = await _lease(factory, job.id)
            results = await _results(factory, job.id)
            stored_run = await repository.get(run.id)
            learner_after = _learner_state(learner_store)
            usage = [
                row.usage
                for row in results
                if row.disposition == "accepted"
            ]
            known_costs = [
                item.get("estimated_cost_usd")
                for item in usage
                if item.get("estimated_cost_usd") is not None
            ]
            all_costs_known = len(known_costs) == len(usage)
            evidence = {
                "schema_version": 1,
                "status": "completed",
                "revision": git_revision(),
                "working_tree": git_worktree_evidence(),
                "config_fingerprint": fingerprint(config),
                "config": config,
                "run_id": run.id,
                "job_id": job.id,
                "parent_fencing_tokens": [parent.fencing_token],
                "expert_fencing_tokens": sorted(
                    {
                        first_lease.fencing_token,
                        final_lease.fencing_token,
                        *(
                            row.expert_fencing_token
                            for row in results
                        ),
                    }
                ),
                "process_ids": {
                    "controller": os.getpid(),
                    "killed_expert_worker": first.pid,
                    "recovery_expert_worker": second.pid,
                },
                "accepted_result_count": sum(
                    row.disposition == "accepted" for row in results
                ),
                "rejected_result_count": sum(
                    row.disposition == "rejected" for row in results
                ),
                "rejection_codes": [
                    row.rejection_code
                    for row in results
                    if row.rejection_code
                ],
                "learner_effect_count": sum(
                    learner_after["counts"].values()
                ) - sum(learner_before["counts"].values()),
                "learner_effect_evidence": (
                    "SQLite row counts and digest unchanged; parent result "
                    "is null; expert process environment omits "
                    "HARNESS_STORE_PATH"
                ),
                "learner_store_before": learner_before,
                "learner_store_after": learner_after,
                "parent_result_is_null": stored_run.result is None,
                "submitted_request_count": 1,
                "provider_request_count": sum(
                    int(item.get("model_calls", 0)) for item in usage
                ),
                "provider": "template",
                "model": "template",
                "estimated_cost_usd": (
                    sum(float(value) for value in known_costs)
                    if all_costs_known
                    else None
                ),
                "cost_status": (
                    "known" if all_costs_known else "unknown"
                ),
            }
        finally:
            if first is not None:
                first.stop()
            if second is not None:
                second.stop()
            try:
                await broker.reset_for_tests()
            finally:
                try:
                    await redis.aclose()
                finally:
                    await isolated.close()

    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


async def _lease(factory, job_id):
    async with factory() as session:
        return await session.get(DistributedExpertLease, job_id)


async def _results(factory, job_id):
    async with factory() as session:
        return list(
            await session.scalars(
                select(DistributedExpertResult)
                .where(DistributedExpertResult.job_id == job_id)
                .order_by(DistributedExpertResult.created_at)
            )
        )


def _learner_state(path: Path) -> dict:
    tables = (
        "runs",
        "checkpoints",
        "conversation_messages",
        "learning_evidence",
    )
    counts = {}
    digest = hashlib.sha256()
    with sqlite3.connect(path) as connection:
        for table in tables:
            rows = connection.execute(
                f'SELECT * FROM "{table}" ORDER BY rowid'
            ).fetchall()
            counts[table] = len(rows)
            digest.update(
                json.dumps(
                    rows,
                    ensure_ascii=False,
                    default=str,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
    return {"counts": counts, "sha256": digest.hexdigest()}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
