import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from core.distributed.contracts import RunStatus
from core.distributed.models import (
    DistributedBase,
    DistributedInbox,
    DistributedLease,
    DistributedOutbox,
    DistributedRun,
    DistributedRunAttempt,
    DistributedStep,
    DistributedTraceSpan,
)
from core.distributed.expert_models import (
    DistributedExpertInbox,
    DistributedExpertJob,
    DistributedExpertLease,
    DistributedExpertOutbox,
    DistributedExpertResult,
    DistributedWorkerRegistry,
)
from core.distributed.repository import (
    DistributedRunRepository,
    FencingViolation,
    RequestConflict,
    RunClaim,
)
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


def test_distributed_metadata_contains_run_and_expert_plane_tables():
    assert set(DistributedBase.metadata.tables) == {
        "distributed_runs",
        "distributed_run_attempts",
        "distributed_steps",
        "distributed_leases",
        "distributed_outbox",
        "distributed_inbox",
        "distributed_trace_spans",
        "distributed_expert_jobs",
        "distributed_expert_leases",
        "distributed_expert_results",
        "distributed_expert_outbox",
        "distributed_expert_inbox",
        "distributed_worker_registry",
        "policy_artifacts",
        "policy_gate_receipts",
        "policy_deployments",
        "policy_environment_heads",
        "rehearsal_token_nonces",
        "policy_observations",
        "policy_health_windows",
        "policy_audit_events",
        "policy_shadow_executions",
    }
    assert DistributedRun.__table__.c.payload.type.python_type is dict
    assert DistributedRunAttempt.__table__.c.fencing_token.type.python_type is int
    assert DistributedStep.__table__.c.result.nullable
    assert DistributedLease.__table__.c.run_id.primary_key
    assert DistributedOutbox.__table__.c.event_key.unique
    assert DistributedInbox.__table__.c.message_key.nullable is False
    assert DistributedTraceSpan.__table__.c.attributes.type.python_type is dict
    assert DistributedExpertJob.__table__.c.payload.type.python_type is dict
    assert DistributedExpertLease.__table__.c.job_id.primary_key
    assert DistributedExpertResult.__table__.c.disposition.nullable is False
    assert DistributedExpertOutbox.__table__.c.available_at.nullable is False
    assert DistributedExpertInbox.__table__.c.message_key.nullable is False
    assert DistributedWorkerRegistry.__table__.c.capabilities.type.python_type is dict
    assert {
        "deployment_id",
        "effective_policy_hash",
        "policy_cohort",
        "assignment_key_hash",
        "assignment_reason",
        "state_namespace",
        "rehearsal_id",
        "rehearsal_fault_profile",
    } <= set(DistributedRun.__table__.c.keys())
    assert {"deployment_id", "state_namespace"} <= set(
        DistributedExpertJob.__table__.c.keys()
    )
    assert {
        foreign_key.target_fullname
        for foreign_key in DistributedRun.__table__.c.effective_policy_hash.foreign_keys
    } == {"policy_artifacts.policy_hash"}
    assert {
        foreign_key.target_fullname
        for foreign_key in DistributedExpertJob.__table__.c.policy_hash.foreign_keys
    } == {"policy_artifacts.policy_hash"}


async def test_m3_upgrade_from_isolated_m2_schema_is_complete_and_idempotent():
    from core.distributed.runtime import (
        PRODUCTION_DEPLOYMENT_ID,
        upgrade_m3_schema,
    )

    url = os.environ["DISTRIBUTED_TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    schema = f"m3_upgrade_{uuid4().hex}"
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(
                text(f'SET LOCAL search_path TO "{schema}"')
            )
            await _create_m2_run_and_expert_tables(connection)
            await connection.run_sync(DistributedBase.metadata.create_all)
            await connection.execute(
                text(
                    "INSERT INTO distributed_runs ("
                    "id, learner_id, request_id, operation, input_hash, "
                    "payload, status, trace_id, attempt_count, created_at, "
                    "updated_at"
                    ") VALUES ("
                    "'00000000-0000-0000-0000-000000000021', 'student', "
                    "'legacy-m3-run', 'learning_task', :hash, "
                    "CAST('{}' AS JSON), 'queued', :trace_id, 0, :now, :now"
                    ")"
                ),
                {"hash": "8" * 64, "trace_id": "7" * 32, "now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO distributed_expert_jobs ("
                    "id, parent_run_id, parent_fencing_token, logical_key, "
                    "role, input_hash, policy_hash, payload, payload_bytes, "
                    "status, "
                    "attempt_count, max_attempts, deadline_at, created_at, "
                    "updated_at"
                    ") VALUES ("
                    "'00000000-0000-0000-0000-000000000022', "
                    "'00000000-0000-0000-0000-000000000021', 1, "
                    "'legacy-job', 'Assessment', :hash, :hash, "
                    "CAST('{}' AS JSON), 2, 'queued', 0, 1, :deadline, "
                    ":now, :now)"
                ),
                {
                    "hash": "9" * 64,
                    "deadline": now + timedelta(minutes=1),
                    "now": now,
                },
            )

            await upgrade_m3_schema(connection)
            await upgrade_m3_schema(connection)

            run = (
                await connection.execute(
                    text(
                        "SELECT deployment_id, effective_policy_hash, "
                        "policy_cohort, assignment_reason, state_namespace, "
                        "rehearsal_fault_profile FROM distributed_runs"
                    )
                )
            ).one()
            experts = (
                await connection.execute(
                    text(
                        "SELECT logical_key, deployment_id, state_namespace "
                        "FROM distributed_expert_jobs ORDER BY logical_key"
                    )
                )
            ).all()
            columns = (
                await connection.execute(
                    text(
                        "SELECT column_name, is_nullable "
                        "FROM information_schema.columns "
                        "WHERE table_schema = :schema "
                        "AND table_name = 'distributed_runs'"
                    ),
                    {"schema": schema},
                )
            ).all()
            constraints = set(
                (
                    await connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint "
                            "WHERE connamespace = "
                            "(SELECT oid FROM pg_namespace "
                            "WHERE nspname = :schema)"
                        ),
                        {"schema": schema},
                    )
                ).scalars()
            )
            indexes = set(
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_indexes "
                            "WHERE schemaname = :schema"
                        ),
                        {"schema": schema},
                    )
                ).scalars()
            )

        assert run.deployment_id == PRODUCTION_DEPLOYMENT_ID
        assert len(run.effective_policy_hash) == 64
        assert run.policy_cohort == "stable"
        assert run.assignment_reason == "legacy_backfill"
        assert run.state_namespace == "production"
        assert run.rehearsal_fault_profile == "none"
        assert experts == [
            ("legacy-job", PRODUCTION_DEPLOYMENT_ID, "production"),
        ]
        nullable = dict(columns)
        assert nullable["deployment_id"] == "NO"
        assert nullable["effective_policy_hash"] == "NO"
        assert nullable["state_namespace"] == "NO"
        assert {
            "fk_distributed_run_deployment",
            "fk_distributed_run_effective_policy",
            "fk_expert_job_deployment",
            "fk_expert_job_policy_artifact",
        } <= constraints
        assert {
            "ix_distributed_run_deployment",
            "ix_distributed_run_effective_policy",
            "ix_expert_job_deployment",
            "ix_expert_job_policy",
        } <= indexes
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            )
        await engine.dispose()


async def test_m3_expert_backfill_preserves_each_existing_binding(repo):
    from core.distributed.runtime import (
        PRODUCTION_DEPLOYMENT_ID,
        REHEARSAL_DEPLOYMENT_ID,
        upgrade_m3_schema,
    )

    run = await repo.accept(spec(request_id="partial-expert-backfill"))
    now = datetime.now(UTC)
    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await connection.execute(
            text(
                "INSERT INTO policy_deployments ("
                "deployment_id, environment, version, state, "
                "candidate_policy_hash, stable_policy_hash, "
                "previous_stable_deployment_id, traffic_basis_points, "
                "assignment_salt_id, thresholds, thresholds_hash, "
                "required_receipts, command_id, reason, actor, created_at"
                ") VALUES ("
                ":deployment_id, 'test', 1, 'registered', NULL, :policy_hash, "
                "NULL, 0, 'test', CAST('{}' AS JSON), :policy_hash, "
                "CAST('[]' AS JSON), 'partial-backfill', 'test', 'test', :now)"
            ),
            {
                "deployment_id": REHEARSAL_DEPLOYMENT_ID,
                "policy_hash": "a" * 64,
                "now": now,
            },
        )
        for job_id, logical_key, deployment_id, state_namespace in (
            (
                "00000000-0000-0000-0000-000000000022",
                "preserve-deployment",
                REHEARSAL_DEPLOYMENT_ID,
                None,
            ),
            (
                "00000000-0000-0000-0000-000000000023",
                "preserve-namespace",
                None,
                "legacy:preserved",
            ),
        ):
            await connection.execute(
                text(
                    "INSERT INTO distributed_expert_jobs ("
                    "id, parent_run_id, parent_fencing_token, logical_key, "
                    "role, input_hash, policy_hash, deployment_id, "
                    "state_namespace, payload, payload_bytes, status, "
                    "attempt_count, max_attempts, deadline_at, created_at, "
                    "updated_at"
                    ") VALUES ("
                    ":id, :run_id, 1, :logical_key, 'Assessment', :hash, "
                    ":policy_hash, :deployment_id, :state_namespace, "
                    "CAST('{}' AS JSON), 2, 'queued', 0, 1, :deadline, "
                    ":now, :now)"
                ),
                {
                    "id": job_id,
                    "run_id": run.id,
                    "logical_key": logical_key,
                    "hash": "9" * 64,
                    "policy_hash": "a" * 64,
                    "deployment_id": deployment_id,
                    "state_namespace": state_namespace,
                    "deadline": now + timedelta(minutes=1),
                    "now": now,
                },
            )

        await upgrade_m3_schema(connection)
        experts = (
            await connection.execute(
                text(
                    "SELECT logical_key, deployment_id, state_namespace "
                    "FROM distributed_expert_jobs ORDER BY logical_key"
                )
            )
        ).all()

    assert experts == [
        ("preserve-deployment", REHEARSAL_DEPLOYMENT_ID, "production"),
        (
            "preserve-namespace",
            PRODUCTION_DEPLOYMENT_ID,
            "legacy:preserved",
        ),
    ]


@pytest.mark.parametrize(
    "table_name",
    [
        "policy_artifacts",
        "policy_gate_receipts",
        "policy_deployments",
        "policy_observations",
        "policy_health_windows",
        "policy_audit_events",
    ],
)
async def test_m3_append_only_tables_reject_update_and_delete(repo, table_name):
    from sqlalchemy.exc import DBAPIError

    from core.distributed.runtime import upgrade_m3_schema

    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await upgrade_m3_schema(connection)
        await _seed_append_only_test_rows(connection)

    for operation in ("UPDATE", "DELETE"):
        async with repo.session_factory() as session:
            with pytest.raises(DBAPIError, match="append-only"):
                if operation == "UPDATE":
                    await session.execute(
                        text(f"UPDATE {table_name} SET created_at = created_at")
                    )
                else:
                    await session.execute(text(f"DELETE FROM {table_name}"))


async def test_m3_environment_head_remains_cas_updatable(repo):
    from core.distributed.runtime import upgrade_m3_schema

    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await upgrade_m3_schema(connection)
        result = await connection.execute(
            text(
                "UPDATE policy_environment_heads "
                "SET current_version = current_version "
                "WHERE environment = 'rehearsal' AND current_version = 1"
            )
        )

    assert result.rowcount == 1


async def test_m3_run_assignment_rejects_update_but_lifecycle_can_advance(repo):
    from core.distributed.runtime import upgrade_m3_schema

    run = await repo.accept(spec(request_id="immutable-run-binding"))
    async with repo.session_factory() as session, session.begin():
        await upgrade_m3_schema(await session.connection())

    async with repo.session_factory() as session:
        with pytest.raises(DBAPIError, match="run assignment is immutable"):
            await session.execute(
                text(
                    "UPDATE distributed_runs "
                    "SET assignment_reason = 'tampered' WHERE id = :run_id"
                ),
                {"run_id": run.id},
            )

    async with repo.session_factory() as session, session.begin():
        result = await session.execute(
            text(
                "UPDATE distributed_runs "
                "SET status = 'running', attempt_count = attempt_count + 1 "
                "WHERE id = :run_id"
            ),
            {"run_id": run.id},
        )
    assert result.rowcount == 1


async def test_m3_expert_assignment_rejects_update_but_lifecycle_can_advance(
    repo,
):
    from core.distributed.runtime import upgrade_m3_schema

    run = await repo.accept(spec(request_id="immutable-expert-binding"))
    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await upgrade_m3_schema(connection)
        await _insert_expert_job(connection, run.id, "immutable-expert-job")

    async with repo.session_factory() as session:
        with pytest.raises(DBAPIError, match="expert assignment is immutable"):
            await session.execute(
                text(
                    "UPDATE distributed_expert_jobs "
                    "SET policy_hash = :policy_hash WHERE logical_key = :key"
                ),
                {"policy_hash": "6" * 64, "key": "immutable-expert-job"},
            )

    async with repo.session_factory() as session, session.begin():
        result = await session.execute(
            text(
                "UPDATE distributed_expert_jobs "
                "SET status = 'running', attempt_count = attempt_count + 1 "
                "WHERE logical_key = :key"
            ),
            {"key": "immutable-expert-job"},
        )
    assert result.rowcount == 1


async def test_m3_active_shadow_allows_lifecycle_update(repo):
    shadow_id = await _insert_shadow(repo, "queued")
    async with repo.session_factory() as session, session.begin():
        result = await session.execute(
            text(
                "UPDATE policy_shadow_executions SET "
                "status = 'running', fencing_token = fencing_token + 1, "
                "owner = 'shadow-worker', lease_expires_at = :lease, "
                "result = CAST(:result AS JSON), "
                "updated_at = :updated_at WHERE shadow_id = :shadow_id"
            ),
            {
                "lease": datetime.now(UTC) + timedelta(seconds=30),
                "result": '{"started":true}',
                "updated_at": datetime.now(UTC),
                "shadow_id": shadow_id,
            },
        )
    assert result.rowcount == 1


async def test_m3_active_shadow_rejects_delete(repo):
    shadow_id = await _insert_shadow(repo, "leased")
    async with repo.session_factory() as session:
        with pytest.raises(DBAPIError, match="cannot be deleted"):
            await session.execute(
                text(
                    "DELETE FROM policy_shadow_executions "
                    "WHERE shadow_id = :shadow_id"
                ),
                {"shadow_id": shadow_id},
            )


@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_m3_terminal_shadow_rejects_any_change(repo, operation):
    shadow_id = await _insert_shadow(repo, "completed")
    async with repo.session_factory() as session:
        expected = (
            "terminal row is append-only"
            if operation == "update"
            else "cannot be deleted"
        )
        with pytest.raises(DBAPIError, match=expected):
            if operation == "update":
                await session.execute(
                    text(
                        "UPDATE policy_shadow_executions "
                        "SET updated_at = updated_at "
                        "WHERE shadow_id = :shadow_id"
                    ),
                    {"shadow_id": shadow_id},
                )
            else:
                await session.execute(
                    text(
                        "DELETE FROM policy_shadow_executions "
                        "WHERE shadow_id = :shadow_id"
                    ),
                    {"shadow_id": shadow_id},
                )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("shadow_id", "00000000-0000-0000-0000-000000000099"),
        ("parent_run_id", "00000000-0000-0000-0000-000000000098"),
        ("deployment_id", "00000000-0000-0000-0000-000000000001"),
        ("policy_hash", "5" * 64),
        ("created_at", datetime(2099, 1, 1, tzinfo=UTC)),
    ],
)
async def test_m3_active_shadow_rejects_identity_tampering(
    repo,
    column,
    value,
):
    shadow_id = await _insert_shadow(repo, "running")
    async with repo.session_factory() as session:
        with pytest.raises(DBAPIError, match="identity is immutable"):
            await session.execute(
                text(
                    f"UPDATE policy_shadow_executions SET {column} = :value "
                    "WHERE shadow_id = :shadow_id"
                ),
                {"value": value, "shadow_id": shadow_id},
            )


async def _seed_append_only_test_rows(connection):
    from core.distributed.runtime import (
        BUILTIN_POLICY_HASH,
        REHEARSAL_DEPLOYMENT_ID,
    )

    run_id = "00000000-0000-0000-0000-000000000031"
    now = datetime.now(UTC)
    await connection.execute(
        text(
            "INSERT INTO distributed_runs ("
            "id, learner_id, request_id, operation, input_hash, payload, "
            "status, trace_id, attempt_count, created_at, updated_at"
            ") VALUES ("
            ":id, 'student', 'append-only-test', 'learning_task', "
            ":hash, CAST('{}' AS JSON), 'completed', :trace_id, 0, :now, :now"
            ") ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": run_id,
            "hash": "d" * 64,
            "trace_id": "e" * 32,
            "now": now,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO policy_gate_receipts ("
            "receipt_id, policy_hash, gate_type, status, evidence_hash, "
            "protocol_hash, runtime_hash, source_revision, model_identity, "
            "data_role, sample_count, cost, details, issued_at, issuer, "
            "created_at"
            ") VALUES ("
            "'00000000-0000-0000-0000-000000000032', :policy_hash, "
            "'artifact_integrity', 'passed', :hash, :hash, :hash, "
            "'test', 'test', 'builtin', 1, 0, CAST('{}' AS JSON), "
            ":now, 'test', :now"
            ") ON CONFLICT (receipt_id) DO NOTHING"
        ),
        {"policy_hash": BUILTIN_POLICY_HASH, "hash": "f" * 64, "now": now},
    )
    await connection.execute(
        text(
            "INSERT INTO policy_observations ("
            "observation_key, run_id, deployment_id, policy_hash, cohort, "
            "state_namespace, metric_contract_version, terminal_status, "
            "latency_seconds, input_tokens, output_tokens, cost, "
            "commit_outcome, permission_outcome, structured_result, "
            "injected, observed_at, source_trace_id, created_at"
            ") VALUES ("
            ":key, :run_id, :deployment_id, :policy_hash, 'stable', "
            "'production', 1, 'completed', 1, 1, 1, 0, 'succeeded', "
            "'allowed', 'valid', FALSE, :now, :trace_id, :now"
            ") ON CONFLICT (observation_key) DO NOTHING"
        ),
        {
            "key": "1" * 64,
            "run_id": run_id,
            "deployment_id": REHEARSAL_DEPLOYMENT_ID,
            "policy_hash": BUILTIN_POLICY_HASH,
            "now": now,
            "trace_id": "e" * 32,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO policy_health_windows ("
            "window_id, deployment_id, metric_contract_version, "
            "observation_start_key, observation_end_key, candidate_stats, "
            "stable_stats, decision, triggered_thresholds, evaluated_at, "
            "created_at"
            ") VALUES ("
            ":window_id, :deployment_id, 1, :key, :key, "
            "CAST('{}' AS JSON), CAST('{}' AS JSON), 'hold', "
            "CAST('[]' AS JSON), :now, :now"
            ") ON CONFLICT (window_id) DO NOTHING"
        ),
        {
            "window_id": "2" * 64,
            "deployment_id": REHEARSAL_DEPLOYMENT_ID,
            "key": "1" * 64,
            "now": now,
        },
    )


async def _create_m2_run_and_expert_tables(connection):
    await connection.execute(
        text(
            "CREATE TABLE distributed_runs ("
            "id VARCHAR(36) PRIMARY KEY, learner_id VARCHAR(128) NOT NULL, "
            "request_id VARCHAR(128) NOT NULL, operation VARCHAR(64) NOT NULL, "
            "input_hash VARCHAR(64) NOT NULL, payload JSON NOT NULL, "
            "status VARCHAR(32) NOT NULL, trace_id VARCHAR(64) NOT NULL, "
            "result JSON, error_code VARCHAR(128), "
            "attempt_count INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL, "
            "updated_at TIMESTAMPTZ NOT NULL)"
        )
    )
    await connection.execute(
        text(
            "CREATE TABLE distributed_expert_jobs ("
            "id VARCHAR(36) PRIMARY KEY, parent_run_id VARCHAR(36) NOT NULL "
            "REFERENCES distributed_runs(id), "
            "parent_fencing_token BIGINT NOT NULL, "
            "logical_key VARCHAR(128) NOT NULL, role VARCHAR(32) NOT NULL, "
            "input_hash VARCHAR(64) NOT NULL, policy_hash VARCHAR(64) NOT NULL, "
            "payload JSON NOT NULL, payload_bytes INTEGER NOT NULL, "
            "status VARCHAR(32) NOT NULL, attempt_count INTEGER NOT NULL, "
            "max_attempts INTEGER NOT NULL, error_code VARCHAR(128), "
            "deadline_at TIMESTAMPTZ NOT NULL, "
            "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, "
            "completed_at TIMESTAMPTZ)"
        )
    )


async def _insert_expert_job(connection, run_id, logical_key):
    from core.distributed.runtime import BUILTIN_POLICY_HASH

    now = datetime.now(UTC)
    await connection.execute(
        text(
            "INSERT INTO distributed_expert_jobs ("
            "id, parent_run_id, parent_fencing_token, logical_key, role, "
            "input_hash, policy_hash, payload, payload_bytes, status, "
            "attempt_count, max_attempts, deadline_at, created_at, updated_at"
            ") VALUES ("
            ":id, :run_id, 1, :logical_key, 'Assessment', :hash, "
            ":policy_hash, CAST('{}' AS JSON), 2, 'queued', 0, 2, "
            ":deadline, :now, :now)"
        ),
        {
            "id": str(uuid4()),
            "run_id": run_id,
            "logical_key": logical_key,
            "hash": "4" * 64,
            "policy_hash": BUILTIN_POLICY_HASH,
            "deadline": now + timedelta(minutes=1),
            "now": now,
        },
    )


async def _insert_shadow(repo, status):
    from core.distributed.runtime import (
        BUILTIN_POLICY_HASH,
        REHEARSAL_DEPLOYMENT_ID,
        upgrade_m3_schema,
    )

    run = await repo.accept(spec(request_id=f"shadow-{status}-{uuid4().hex}"))
    shadow_id = str(uuid4())
    now = datetime.now(UTC)
    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await upgrade_m3_schema(connection)
        await connection.execute(
            text(
                "INSERT INTO policy_shadow_executions ("
                "shadow_id, parent_run_id, deployment_id, policy_hash, "
                "status, fencing_token, owner, lease_expires_at, result, "
                "created_at, updated_at"
                ") VALUES ("
                ":shadow_id, :run_id, :deployment_id, :policy_hash, :status, "
                "0, NULL, NULL, NULL, :now, :now)"
            ),
            {
                "shadow_id": shadow_id,
                "run_id": run.id,
                "deployment_id": REHEARSAL_DEPLOYMENT_ID,
                "policy_hash": BUILTIN_POLICY_HASH,
                "status": status,
                "now": now,
            },
        )
    return shadow_id


async def test_accept_is_idempotent_and_conflicting_payload_is_rejected(repo):
    first = await repo.accept(spec())
    replay = await repo.accept(spec())
    assert first.id == replay.id
    with pytest.raises(RequestConflict):
        await repo.accept(spec(question="不同内容"))


async def test_expired_lease_increments_fencing_and_rejects_old_owner(repo):
    run = await repo.accept(spec())
    first = await repo.claim(run.id, "worker-a", lease_seconds=1)
    await repo.force_lease_expiry(
        run.id, datetime.now(UTC) - timedelta(seconds=1)
    )
    await repo.requeue_expired(now=datetime.now(UTC))
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    assert second.fencing_token == first.fencing_token + 1
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, first.fencing_token, {"owner": "a"})
    await repo.transition_committing(run.id, second.fencing_token)
    completed = await repo.complete(
        run.id, second.fencing_token, {"owner": "b"}
    )
    assert completed.status == RunStatus.COMPLETED


async def test_claim_persists_database_derived_parent_deadline(repo):
    run = await repo.accept(spec(request_id="persisted-deadline"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)

    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)

    assert attempt is not None
    assert attempt.deadline_at == claim.deadline_at
    assert claim.deadline_at > attempt.started_at


async def test_m1_attempt_schema_is_backfilled_during_upgrade(repo):
    from core.distributed.runtime import upgrade_m1_schema

    run = await repo.accept(spec(request_id="m1-schema-upgrade"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await connection.execute(
            text(
                "ALTER TABLE distributed_run_attempts "
                "DROP COLUMN deadline_at"
            )
        )
        await upgrade_m1_schema(connection, parent_timeout_seconds=75)
        row = (
            await connection.execute(
                text(
                    "SELECT started_at, deadline_at "
                    "FROM distributed_run_attempts WHERE id = :attempt_id"
                ),
                {"attempt_id": claim.attempt_id},
            )
        ).one()

    assert row.deadline_at == row.started_at + timedelta(seconds=75)


async def test_waiting_expert_parent_can_renew_lease(repo):
    run = await repo.accept(spec(request_id="waiting-expert-renew"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    async with repo.session_factory() as session, session.begin():
        stored = await session.get(DistributedRun, run.id, with_for_update=True)
        assert stored is not None
        stored.status = RunStatus.WAITING_EXPERT

    renewed = await repo.renew(
        run.id,
        "worker-a",
        claim.fencing_token,
        lease_seconds=20,
    )

    assert renewed.owner == "worker-a"
    assert renewed.fencing_token == claim.fencing_token


async def test_step_result_is_reused_only_for_same_input_hash(repo):
    run = await repo.accept(spec())
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
    )
    first = await repo.complete_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
        {"ok": True},
    )
    replay = await repo.complete_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
        {"ok": True},
    )
    assert replay.id == first.id
    with pytest.raises(RequestConflict):
        await repo.start_step(
            run.id,
            "business-execution",
            "hash-b",
            claim.fencing_token,
        )


async def test_renew_fail_outbox_and_inbox_are_transactional(repo):
    run = await repo.accept(spec(request_id="lifecycle"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    renewed = await repo.renew(
        run.id,
        "worker-a",
        claim.fencing_token,
        lease_seconds=20,
    )
    assert renewed.owner == "worker-a"

    failed = await repo.fail(
        run.id,
        claim.fencing_token,
        "business_store_busy",
        retryable=True,
    )
    assert failed.status == RunStatus.RETRYABLE_FAILED
    assert failed.error_code == "business_store_busy"

    rows = await repo.pending_outbox(10)
    assert [row.topic for row in rows] == ["run.accepted", "run.retry"]
    with pytest.raises(RequestConflict):
        await repo.mark_outbox_published(rows[0].id, "wrong-key")
    await repo.mark_outbox_published(rows[0].id, rows[0].event_key)

    event_key = f"run:{run.id}:retry:{claim.fencing_token}"
    assert await repo.record_inbox("worker-a", event_key)
    assert not await repo.record_inbox("worker-a", event_key)


async def test_cancel_is_idempotent_and_releases_active_lease(repo):
    run = await repo.accept(spec(request_id="cancel"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    cancelled = await repo.cancel(run.id)
    replay = await repo.cancel(run.id)
    lease = await repo.lease(run.id)

    assert cancelled.status == RunStatus.CANCELLED
    assert replay.id == cancelled.id
    assert lease.owner is None
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, claim.fencing_token, {"too": "late"})


async def test_requeue_marks_run_queued_and_trace_lifecycle_is_durable(repo):
    run = await repo.accept(spec(request_id="trace"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await repo.requeue_expired(datetime.now(UTC)) == [run.id]
    queued = await repo.get(run.id)
    assert queued is not None
    assert queued.status == RunStatus.QUEUED

    span = await repo.start_span(
        run.id,
        run.trace_id,
        "span-1",
        None,
        "run_attempt",
        {"worker.id": "worker-a"},
    )
    finished = await repo.finish_span(
        span.span_id,
        "ok",
        {"attempt": claim.attempt_count},
    )
    trace = await repo.trace(run.id)
    assert finished.status == "ok"
    assert finished.attributes["attempt"] == 1
    assert [item.span_id for item in trace] == ["span-1"]


async def test_expired_unreaped_lease_cannot_be_renewed_or_mutated(repo):
    run = await repo.accept(spec(request_id="expired"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
    )
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(FencingViolation, match="expired"):
        await repo.renew(
            run.id,
            "worker-a",
            claim.fencing_token,
            lease_seconds=10,
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.start_step(
            run.id,
            "another-step",
            "hash-b",
            claim.fencing_token,
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.complete_step(
            run.id,
            "business-execution",
            "hash-a",
            claim.fencing_token,
            {"ok": True},
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.transition_committing(run.id, claim.fencing_token)

    committing = await repo.accept(spec(request_id="expired-complete"))
    committing_claim = await repo.claim(
        committing.id,
        "worker-a",
        lease_seconds=10,
    )
    await repo.transition_committing(
        committing.id,
        committing_claim.fencing_token,
    )
    await repo.force_lease_expiry(
        committing.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.complete(
            committing.id,
            committing_claim.fencing_token,
            {"ok": True},
        )


async def test_complete_requires_step_intent_and_takeover_updates_token(repo):
    run = await repo.accept(spec(request_id="step-intent"))
    first = await repo.claim(run.id, "worker-a", lease_seconds=10)
    with pytest.raises(RequestConflict, match="not been started"):
        await repo.complete_step(
            run.id,
            "business-execution",
            "hash-a",
            first.fencing_token,
            {"ok": True},
        )
    started = await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        first.fencing_token,
    )
    assert started.fencing_token == first.fencing_token

    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    await repo.requeue_expired(datetime.now(UTC))
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    taken_over = await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        second.fencing_token,
    )
    assert taken_over.id == started.id
    assert taken_over.fencing_token == second.fencing_token


async def test_concurrent_claim_has_exactly_one_winner(repo):
    run = await repo.accept(spec(request_id="concurrent-claim"))
    outcomes = await asyncio.gather(
        repo.claim(run.id, "worker-a", lease_seconds=10),
        repo.claim(run.id, "worker-b", lease_seconds=10),
        return_exceptions=True,
    )
    assert sum(isinstance(item, RunClaim) for item in outcomes) == 1
    assert sum(isinstance(item, FencingViolation) for item in outcomes) == 1


async def test_reaper_exhausts_run_at_max_attempts(repo):
    limited = DistributedRunRepository(
        repo.session_factory,
        max_attempts=1,
    )
    run = await limited.accept(spec(request_id="exhausted"))
    await limited.claim(run.id, "worker-a", lease_seconds=10)
    await limited.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await limited.requeue_expired(datetime.now(UTC)) == []
    exhausted = await limited.get(run.id)
    assert exhausted is not None
    assert exhausted.status == RunStatus.EXHAUSTED
