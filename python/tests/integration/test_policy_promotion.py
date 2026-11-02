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
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config.settings import Settings
from core.distributed.broker import RedisRunBroker, RedisStreamBroker
from core.distributed.contracts import RunStatus
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.models import DistributedBase, DistributedRunAttempt
from core.distributed.expert_models import DistributedWorkerRegistry
from core.distributed.policy_assignment import PolicyAssigner
from core.distributed.promotion_contracts import (
    DeploymentState,
    PolicyArtifact,
    PromotionCommand,
)
from core.distributed.promotion_models import (
    PolicyAuditEventRecord,
    PolicyGateReceiptRecord,
    PolicyHealthWindowRecord,
    PolicyObservationRecord,
    PolicyShadowExecutionRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from core.distributed.promotion_service import (
    QualificationMaterial,
    RehearsalTokenIssuer,
)
from core.distributed.reaper import LeaseReaper
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import (
    BUILTIN_FIXED_COMPONENTS_HASH,
    BUILTIN_POLICY_HASH,
    migrate_schema,
)
from core.versions import policy_runtime_hash
from evals.live_runner import code_revision
from tests.distributed.helpers import spec
from tests.distributed.test_policy_assignment import SECRET
from tests.distributed.test_promotion_repository import qualification_material

pytestmark = pytest.mark.distributed_integration

PYTHON_ROOT = Path(__file__).parents[2]
PROCESS_TIMEOUT = 30


@pytest_asyncio.fixture
async def raw_repo():
    database_url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is required")
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("DROP TABLE IF EXISTS distributed_schema_version")
        )
        await connection.run_sync(DistributedBase.metadata.drop_all)
        await connection.run_sync(DistributedBase.metadata.create_all)
    repository = DistributedRunRepository(
        async_sessionmaker(engine, expire_on_commit=False)
    )
    try:
        yield repository
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DROP TABLE IF EXISTS distributed_schema_version")
            )
            await connection.run_sync(DistributedBase.metadata.drop_all)
        await engine.dispose()


def process_env(
    *,
    database_url: str,
    redis_url: str,
    stream: str,
    group: str,
    rehearsal_stream: str,
    rehearsal_group: str,
    worker_id: str,
    store_path: Path,
    rehearsal_root: Path,
) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(PYTHON_ROOT),
        "DISTRIBUTED_ENABLED": "true",
        "DISTRIBUTED_EXPERTS_ENABLED": "false",
        "DISTRIBUTED_DATABASE_URL": database_url,
        "DISTRIBUTED_REDIS_URL": redis_url,
        "DISTRIBUTED_STREAM": stream,
        "DISTRIBUTED_CONSUMER_GROUP": group,
        "DISTRIBUTED_WORKER_ID": worker_id,
        "DISTRIBUTED_LEASE_SECONDS": "3",
        "DISTRIBUTED_HEARTBEAT_SECONDS": "0.5",
        "DISTRIBUTED_ATTEMPT_TIMEOUT_SECONDS": "60",
        "DISTRIBUTED_MAX_ATTEMPTS": "3",
        "PROMOTION_ENABLED": "true",
        "PROMOTION_COMMAND_PRINCIPAL": "integration-test",
        "PROMOTION_REHEARSAL_SECRET": SECRET.decode(),
        "PROMOTION_ASSIGNMENT_SECRET": SECRET.decode(),
        "PROMOTION_REHEARSAL_STREAM": rehearsal_stream,
        "PROMOTION_REHEARSAL_CONSUMER_GROUP": rehearsal_group,
        "PROMOTION_REHEARSAL_STORE_ROOT": str(rehearsal_root),
        "PROMOTION_HEALTH_POLL_SECONDS": "0.1",
        "PROMOTION_FAULT_INJECTION_ENABLED": "true",
        "PROMOTION_INJECTED_LATENCY_SECONDS": "2.5",
        "HARNESS_STORE_PATH": str(store_path),
        "LLM_PROVIDER": "template",
        "MEMORY_RETRIEVAL_MODE": "lexical",
        "MEMORY_WORKER_ENABLED": "false",
    }


def start_process(command: str, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.integration.policy_promotion_process",
            command,
        ],
        cwd=PYTHON_ROOT,
        env=env,
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
    if process.poll() is None:
        return
    stderr = process.stderr.read() if process.stderr is not None else ""
    raise AssertionError(f"{label} exited early with {process.returncode}\n{stderr}")


async def wait_until(predicate, *, timeout: float = PROCESS_TIMEOUT):
    async with asyncio.timeout(timeout):
        while True:
            value = await predicate()
            if value:
                return value
            await asyncio.sleep(0.05)


async def wait_with_processes(predicate, processes, *, timeout=PROCESS_TIMEOUT):
    async def checked():
        for process, label in processes:
            assert_running(process, label)
        return await predicate()

    return await wait_until(checked, timeout=timeout)


async def fixture_material() -> QualificationMaterial:
    body = qualification_material().model_dump(mode="json")
    body["artifact"]["parent_policy_hash"] = BUILTIN_POLICY_HASH
    body["artifact"]["fixed_components_hash"] = BUILTIN_FIXED_COMPONENTS_HASH
    body["artifact"]["runtime_hash"] = policy_runtime_hash(
        Settings(
            llm_provider="template",
            memory_retrieval_mode="lexical",
        )
    )
    body["artifact"]["source_revision"] = code_revision()[
        "python_source_sha256"
    ]
    body["artifact"]["evidence_bindings"].update(
        evidence_role="test_fixture",
        release_eligible=False,
    )
    body["artifact"]["policy_hash"] = PromotionRepository._artifact_hash(
        PolicyArtifact.model_validate(body["artifact"])
    )
    for receipt in body["receipts"]:
        receipt["policy_hash"] = body["artifact"]["policy_hash"]
        receipt["runtime_hash"] = body["artifact"]["runtime_hash"]
        receipt["source_revision"] = body["artifact"]["source_revision"]
        receipt["details"].update(
            evidence_role="test_fixture",
            release_eligible=False,
        )
    return QualificationMaterial.model_validate(body)


async def transition(repository, snapshot, target, *, traffic=0):
    return await repository.transition(
        PromotionCommand(
            command_id=f"integration-{target}-{uuid4().hex}",
            environment="rehearsal",
            expected_version=snapshot.version,
            current_state=snapshot.state,
            target_state=target,
            traffic_basis_points=traffic,
            actor="integration-test",
            reason="fixture-only controlled promotion integration",
        )
    )


async def terminal(repo, run_id):
    run = await repo.get(run_id)
    if run is not None and run.status in {
        RunStatus.COMPLETED,
        RunStatus.TERMINAL_FAILED,
        RunStatus.EXHAUSTED,
    }:
        return run
    return None


async def run_with_cohort(
    *,
    repo,
    issuer,
    dispatcher,
    request_prefix: str,
    cohort: str,
    fault_profile: str = "none",
    dispatch: bool = True,
):
    for index in range(1000):
        request_id = f"{request_prefix}-{index}"
        issued = await issuer.issue(
            rehearsal_id="task10",
            namespace="rehearsal-task10",
            learner_id="student",
            request_id=request_id,
            operation="learning_task",
            fault_profile=fault_profile,
            ttl_seconds=300,
        )
        if issued["expected_cohort"] == cohort:
            run, replay = await repo.accept_with_replay(
                spec(request_id),
                rehearsal_token=issued["token"],
            )
            assert not replay
            if dispatch:
                assert await dispatcher.dispatch_once() >= 1
            return run
    raise AssertionError(f"could not select {cohort} request")


async def cohort_observations(repository, deployment_id):
    async with repository.session_factory() as session:
        rows = (
            await session.scalars(
                select(PolicyObservationRecord).where(
                    PolicyObservationRecord.deployment_id == str(deployment_id)
                )
            )
        ).all()
    return rows


async def passed_receipt(repository, policy_hash, gate):
    async with repository.session_factory() as session:
        receipt = await session.scalar(
            select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash == policy_hash,
                PolicyGateReceiptRecord.gate_type == gate,
                PolicyGateReceiptRecord.status == "passed",
            )
        )
        if receipt is not None:
            return receipt
        windows = (
            await session.scalars(
                select(PolicyHealthWindowRecord).order_by(
                    PolicyHealthWindowRecord.created_at.desc()
                )
            )
        ).all()
        if windows:
            latest = windows[0]
            if (
                latest.candidate_stats.get("run_count", 0) >= 20
                and latest.stable_stats.get("run_count", 0) >= 20
            ):
                raise AssertionError(
                    "health did not pass: "
                    f"{latest.decision} {latest.triggered_thresholds} "
                    f"candidate={latest.candidate_stats} "
                    f"stable={latest.stable_stats}"
                )
        return None


async def test_real_process_promotion_rolls_back_and_preserves_pinning(
    raw_repo,
    tmp_path,
):
    database_url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    redis_url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("distributed PostgreSQL and Redis URLs are required")

    await migrate_schema(raw_repo.session_factory.kw["bind"])
    suffix = uuid4().hex
    stream = f"test:runs:promotion:{suffix}"
    group = f"test-run-workers-{suffix}"
    rehearsal_stream = f"{stream}:rehearsal"
    rehearsal_group = f"test-rehearsal-workers-{suffix}"
    redis = Redis.from_url(redis_url, decode_responses=True)
    broker = RedisRunBroker(redis, stream, group)
    rehearsal_broker = RedisStreamBroker(redis, rehearsal_stream, rehearsal_group)
    deployment_broker = RedisStreamBroker(
        redis,
        f"{stream}:deployments",
        f"test-deployments-{suffix}",
    )
    dispatcher = OutboxDispatcher(
        raw_repo,
        broker,
        rehearsal_broker=rehearsal_broker,
        deployment_broker=deployment_broker,
    )
    promotion = PromotionRepository(raw_repo.session_factory)
    material = await fixture_material()
    raw_repo.policy_assigner = PolicyAssigner(
        signing_secret=SECRET,
        assignment_secret=SECRET,
        runtime_hash=material.artifact.runtime_hash,
        source_revision=material.artifact.source_revision,
        allow_fault_injection=True,
        settings_obj=SimpleNamespace(
            promotion_injected_latency_seconds=2.5,
        ),
    )
    issuer = RehearsalTokenIssuer(
        promotion,
        signing_secret=SECRET.decode(),
        assignment_secret=SECRET.decode(),
        allow_fault_injection=True,
    )
    env = process_env(
        database_url=database_url,
        redis_url=redis_url,
        stream=stream,
        group=group,
        rehearsal_stream=rehearsal_stream,
        rehearsal_group=rehearsal_group,
        worker_id="unused",
        store_path=tmp_path / "production.sqlite3",
        rehearsal_root=tmp_path / "rehearsal",
    )
    processes: list[subprocess.Popen] = []

    try:
        await broker.ensure_group()
        await rehearsal_broker.ensure_group()
        await deployment_broker.ensure_group()
        registered = await promotion.register_qualification(
            material,
            actor="integration-test",
            command_id=f"integration-register-{suffix}",
        )
        assert registered.state == DeploymentState.REGISTERED
        shadow = await transition(promotion, registered, "shadow")

        health = start_process("policy-health", env)
        worker_a = start_process(
            "rehearsal-worker",
            {**env, "DISTRIBUTED_WORKER_ID": "rehearsal-a"},
        )
        processes.extend([health, worker_a])

        first_shadow_run = await run_with_cohort(
            repo=raw_repo,
            issuer=issuer,
            dispatcher=dispatcher,
            request_prefix="shadow-queued",
            cohort="stable",
        )
        await wait_with_processes(
            lambda: terminal(raw_repo, first_shadow_run.id),
            (
                (health, "policy health"),
                (worker_a, "rehearsal worker"),
            ),
        )
        queued_shadow = await wait_with_processes(
            lambda: _shadow_for_run(raw_repo, first_shadow_run.id),
            (
                (health, "policy health"),
                (worker_a, "rehearsal worker"),
            ),
        )
        assert queued_shadow.status == "queued"
        await asyncio.sleep(1)

        shadow_worker = start_process(
            "shadow-worker",
            {**env, "DISTRIBUTED_WORKER_ID": "shadow-a"},
        )
        processes.append(shadow_worker)
        await wait_with_processes(
            lambda: _registered_process_types(
                raw_repo,
                {"policy-health", "rehearsal-worker", "shadow-worker"},
            ),
            (
                (health, "policy health"),
                (shadow_worker, "shadow worker"),
                (worker_a, "rehearsal worker"),
            ),
        )

        shadow_runs = [first_shadow_run]
        for number in range(1, 20):
            run = await run_with_cohort(
                repo=raw_repo,
                issuer=issuer,
                dispatcher=dispatcher,
                request_prefix=f"shadow-{number}",
                cohort="stable",
            )
            shadow_runs.append(run)
        await wait_with_processes(
            lambda: _all_terminal(raw_repo, [run.id for run in shadow_runs]),
            (
                (health, "policy health"),
                (shadow_worker, "shadow worker"),
                (worker_a, "rehearsal worker"),
            ),
        )
        await wait_with_processes(
            lambda: _shadow_count(raw_repo, shadow.deployment_id, 20),
            (
                (health, "policy health"),
                (shadow_worker, "shadow worker"),
                (worker_a, "rehearsal worker"),
            ),
        )
        shadow_receipt = await wait_with_processes(
            lambda: passed_receipt(
                promotion,
                material.artifact.policy_hash,
                "shadow_health",
            ),
            (
                (health, "policy health"),
                (shadow_worker, "shadow worker"),
                (worker_a, "rehearsal worker"),
            ),
        )
        assert shadow_receipt.issuer == "policy-health"
        assert shadow_receipt.details["evidence_role"] == "test_fixture"
        assert shadow_receipt.details["release_eligible"] is False
        observations = await cohort_observations(promotion, shadow.deployment_id)
        assert {row.cohort for row in observations} == {"stable", "shadow"}
        assert all(row.permission_outcome == "isolated" for row in observations if row.cohort == "shadow")
        completed_shadow = await _shadow_for_run(
            raw_repo,
            first_shadow_run.id,
        )
        first_observation = next(
            row
            for row in observations
            if row.run_id == first_shadow_run.id and row.cohort == "shadow"
        )
        queue_delay = (
            completed_shadow.started_at - completed_shadow.created_at
        ).total_seconds()
        assert queue_delay >= 0.9
        assert float(first_observation.latency_seconds) < queue_delay

        canary = await transition(promotion, shadow, "canary", traffic=5000)
        healthy = []
        for number in range(18):
            for cohort in ("stable", "candidate"):
                healthy.append(
                    await run_with_cohort(
                        repo=raw_repo,
                        issuer=issuer,
                        dispatcher=dispatcher,
                        request_prefix=f"canary-{cohort}-{number}",
                        cohort=cohort,
                    )
                )
        for number in range(18, 20):
            healthy.append(
                await run_with_cohort(
                    repo=raw_repo,
                    issuer=issuer,
                    dispatcher=dispatcher,
                    request_prefix=f"canary-stable-{number}",
                    cohort="stable",
                )
            )
        await wait_until(lambda: _all_terminal(raw_repo, [run.id for run in healthy]))

        stop_process(worker_a)
        processes.remove(worker_a)
        failover = await run_with_cohort(
            repo=raw_repo,
            issuer=issuer,
            dispatcher=dispatcher,
            request_prefix="canary-failover",
            cohort="candidate",
        )
        first = start_process(
            "rehearsal-worker",
            {
                **env,
                "DISTRIBUTED_WORKER_ID": "rehearsal-killed",
                "PROMOTION_FIXTURE_PAUSE_REQUEST_PREFIX": "canary-failover",
            },
        )
        processes.append(first)
        first_attempt = await wait_until(
            lambda: _owned_attempt(
                raw_repo,
                failover.id,
                "rehearsal-killed",
            )
        )
        assert first_attempt.usage_summary is None
        stop_process(first, kill=True)
        processes.remove(first)

        await asyncio.sleep(3.1)
        assert await LeaseReaper(raw_repo).reap_once() == [failover.id]
        assert await dispatcher.dispatch_once() >= 1
        second = start_process(
            "rehearsal-worker",
            {**env, "DISTRIBUTED_WORKER_ID": "rehearsal-takeover"},
        )
        processes.append(second)
        completed_failover = await wait_until(
            lambda: terminal(raw_repo, failover.id),
            timeout=PROCESS_TIMEOUT + 5,
        )
        assert completed_failover.status == RunStatus.COMPLETED
        assert completed_failover.policy_binding == failover.policy_binding
        attempts = await _attempts(raw_repo, failover.id)
        assert [attempt.fencing_token for attempt in attempts] == [1, 2]
        assert attempts[0].usage_summary is None

        failed = await run_with_cohort(
            repo=raw_repo,
            issuer=issuer,
            dispatcher=dispatcher,
            request_prefix="canary-commit-failure",
            cohort="candidate",
            fault_profile="commit_failure",
        )
        late = await run_with_cohort(
            repo=raw_repo,
            issuer=issuer,
            dispatcher=dispatcher,
            request_prefix="canary-late",
            cohort="candidate",
            dispatch=False,
        )
        failed = await wait_until(lambda: terminal(raw_repo, failed.id))
        assert failed.status == RunStatus.TERMINAL_FAILED
        assert failed.error_code == "RehearsalInjectedCommitFailure"
        failed_observation = await wait_with_processes(
            lambda: _observation_for_run(promotion, failed.id),
            (
                (health, "policy health"),
                (second, "takeover worker"),
            ),
        )
        assert failed_observation.terminal_status == "commit_failed"
        assert failed_observation.commit_outcome == "failed"
        assert failed_observation.fault_injected is True

        try:
            rolled_back = await wait_with_processes(
                lambda: _head_in_state(
                    promotion,
                    DeploymentState.ROLLED_BACK,
                ),
                (
                    (health, "policy health"),
                    (second, "takeover worker"),
                ),
            )
        except TimeoutError:
            raise AssertionError(
                await _health_debug(promotion, canary.deployment_id)
            ) from None
        failure_window = await _failure_window(promotion, canary.deployment_id)
        assert failure_window.decision == "fail"
        assert "commit_failure_rate" in failure_window.triggered_thresholds
        assert failure_window.candidate_stats["run_count"] == 20
        assert failure_window.stable_stats["run_count"] >= 20
        assert failure_window.candidate_stats["injected_commit_failure_count"] == 1
        rollback_event = await _rollback_event(promotion)
        assert rollback_event is not None
        assert (
            rollback_event.details["failed_deployment_id"]
            == str(canary.deployment_id)
        )

        pinned = await raw_repo.get(failover.id)
        assert pinned.policy_cohort == "candidate"
        assert pinned.deployment_id == str(canary.deployment_id)
        fresh = await run_with_cohort(
            repo=raw_repo,
            issuer=issuer,
            dispatcher=dispatcher,
            request_prefix="post-rollback",
            cohort="stable",
            dispatch=False,
        )
        assert fresh.policy_cohort == "stable"
        assert fresh.effective_policy_hash == rolled_back.stable_policy_hash

        assert await dispatcher.dispatch_once() >= 1
        late = await wait_until(lambda: terminal(raw_repo, late.id))
        assert late.policy_cohort == "candidate"
        await wait_until(lambda: _observation_exists(promotion, late.id))
        unchanged = await promotion.get_head("rehearsal")
        assert unchanged.deployment_id == rolled_back.deployment_id
        assert unchanged.version == rolled_back.version
        assert unchanged.state == DeploymentState.ROLLED_BACK

        for process, label in (
            (health, "policy health"),
            (shadow_worker, "shadow worker"),
            (second, "takeover worker"),
        ):
            assert_running(process, label)
    finally:
        for process in processes:
            stop_process(process)
        await broker.reset_for_tests()
        await rehearsal_broker.reset_for_tests()
        await deployment_broker.reset_for_tests()
        await redis.aclose()


async def _all_terminal(repo, run_ids):
    return all(
        await asyncio.gather(
            *(terminal(repo, run_id) for run_id in run_ids)
        )
    )


async def _shadow_count(repo, deployment_id, expected):
    async with repo.session_factory() as session:
        rows = (
            await session.scalars(
                select(PolicyShadowExecutionRecord).where(
                    PolicyShadowExecutionRecord.deployment_id
                    == str(deployment_id)
                )
            )
        ).all()
    completed = sum(row.status == "completed" for row in rows)
    terminal_rows = [
        row for row in rows if row.status in {"completed", "failed", "exhausted"}
    ]
    if len(terminal_rows) >= expected and completed < expected:
        details = [
            (row.status, row.error_code, row.result) for row in terminal_rows
        ]
        raise AssertionError(f"shadow executions did not complete: {details}")
    return completed >= expected


async def _shadow_for_run(repo, run_id):
    async with repo.session_factory() as session:
        return await session.scalar(
            select(PolicyShadowExecutionRecord).where(
                PolicyShadowExecutionRecord.parent_run_id == str(run_id)
            )
        )


async def _registered_process_types(repo, expected):
    async with repo.session_factory() as session:
        rows = (
            await session.scalars(
                select(DistributedWorkerRegistry).where(
                    DistributedWorkerRegistry.status == "running"
                )
            )
        ).all()
    return expected <= {row.process_type for row in rows}


async def _owned_attempt(repo, run_id, worker_id):
    async with repo.session_factory() as session:
        return await session.scalar(
            select(DistributedRunAttempt).where(
                DistributedRunAttempt.run_id == str(run_id),
                DistributedRunAttempt.worker_id == worker_id,
                DistributedRunAttempt.status == RunStatus.RUNNING,
            )
        )


async def _attempts(repo, run_id):
    async with repo.session_factory() as session:
        return list(
            await session.scalars(
                select(DistributedRunAttempt)
                .where(DistributedRunAttempt.run_id == str(run_id))
                .order_by(DistributedRunAttempt.number)
            )
        )


async def _head_in_state(repository, state):
    head = await repository.get_head("rehearsal")
    return head if head.state == state else None


async def _failure_window(repository, deployment_id):
    async with repository.session_factory() as session:
        return await session.scalar(
            select(PolicyHealthWindowRecord)
            .where(
                PolicyHealthWindowRecord.deployment_id == str(deployment_id),
                PolicyHealthWindowRecord.decision == "fail",
            )
            .order_by(PolicyHealthWindowRecord.created_at.desc())
        )


async def _health_debug(repository, deployment_id):
    head = await repository.get_head("rehearsal")
    async with repository.session_factory() as session:
        windows = list(
            await session.scalars(
                select(PolicyHealthWindowRecord)
                .where(
                    PolicyHealthWindowRecord.deployment_id
                    == str(deployment_id)
                )
                .order_by(PolicyHealthWindowRecord.created_at)
            )
        )
    return {
        "head": head.model_dump(mode="json"),
        "windows": [
            {
                "decision": window.decision,
                "reasons": window.triggered_thresholds,
                "candidate": window.candidate_stats,
                "stable": window.stable_stats,
                "keys": window.observation_keys,
            }
            for window in windows
        ],
    }


async def _rollback_event(repository):
    async with repository.session_factory() as session:
        rows = list(
            await session.scalars(
                select(PolicyAuditEventRecord).where(
                    PolicyAuditEventRecord.event_type == "health_rollback"
                )
            )
        )
    assert len(rows) <= 1
    return rows[0] if rows else None


async def _observation_exists(repository, run_id):
    return bool(await _observation_for_run(repository, run_id))


async def _observation_for_run(repository, run_id):
    async with repository.session_factory() as session:
        return await session.scalar(
            select(PolicyObservationRecord).where(
                PolicyObservationRecord.run_id == str(run_id)
            )
        )
