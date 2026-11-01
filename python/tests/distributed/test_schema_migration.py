from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.distributed import runtime as runtime_module
from core.distributed.cli import parser
from core.distributed.models import DistributedBase

pytestmark = pytest.mark.distributed_integration


@pytest.mark.parametrize("entrypoint", [
    "api.distributed_main",
    "core.distributed.cli",
    "core.distributed.promotion_cli",
])
def test_schema_contract_hash_is_independent_of_entrypoint_import_order(entrypoint):
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import importlib, json; "
            f"importlib.import_module({entrypoint!r}); "
            "from core.distributed.runtime import DistributedBase, schema_contract_hash; "
            "print(json.dumps({'hash': schema_contract_hash(), "
            "'tables': sorted(DistributedBase.metadata.tables)}))",
        ],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[2])},
        capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(result.stdout) == {
        "hash": runtime_module.schema_contract_hash(),
        "tables": sorted(DistributedBase.metadata.tables),
    }


@pytest_asyncio.fixture
async def migration_engine():
    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    schema = f"migration_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield engine, schema
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def snapshot(engine):
    async with engine.connect() as connection:
        return {
            "marker": tuple((await connection.execute(text(
                "SELECT version, schema_hash FROM distributed_schema_version WHERE id = 1"
            ))).one()),
            "policies": await connection.scalar(text("SELECT count(*) FROM policy_artifacts")),
            "deployments": await connection.scalar(text("SELECT count(*) FROM policy_deployments")),
            "audits": await connection.scalar(text("SELECT count(*) FROM policy_audit_events")),
            "triggers": await connection.scalar(text(
                "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
                "AND tgrelid IN (SELECT oid FROM pg_class "
                "WHERE relnamespace = current_schema()::regnamespace)"
            )),
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_explicit_migration_creates_or_upgrades_idempotently(migration_engine, legacy):
    engine, _ = migration_engine
    if legacy:
        async with engine.begin() as connection:
            await connection.run_sync(DistributedBase.metadata.create_all)
            await connection.execute(text(
                "ALTER TABLE distributed_run_attempts DROP COLUMN deadline_at"
            ))
            for table, columns in {
                "distributed_runs": [
                    "deployment_id", "effective_policy_hash", "policy_cohort",
                    "assignment_key_hash", "assignment_reason", "state_namespace",
                    "rehearsal_id", "rehearsal_fault_profile", "policy_binding",
                ],
                "distributed_expert_jobs": ["deployment_id", "state_namespace"],
                "policy_shadow_executions": [
                    "input_hash", "payload_reference", "policy_binding", "deployment_version",
                    "attempt_count", "max_attempts", "error_code", "started_at",
                    "finished_at", "deadline_at",
                ],
            }.items():
                for column in columns:
                    await connection.execute(text(
                        f"ALTER TABLE {table} DROP COLUMN {column} CASCADE"
                    ))
            await connection.execute(text(
                "INSERT INTO distributed_runs "
                "(id, learner_id, request_id, operation, input_hash, payload, "
                "status, trace_id, attempt_count, created_at, updated_at) "
                "VALUES ('legacy-run', 'learner', 'legacy-request', 'learning_task', "
                ":hash, CAST('{}' AS JSON), 'completed', :hash, 1, now(), now())"
            ), {"hash": "a" * 64})
            await connection.execute(text(
                "INSERT INTO distributed_run_attempts "
                "(id, run_id, number, worker_id, fencing_token, status, started_at) "
                "VALUES ('legacy-attempt', 'legacy-run', 1, 'legacy-worker', "
                "1, 'completed', now())"
            ))
    with pytest.raises(runtime_module.SchemaVersionMismatch):
        await runtime_module.check_schema_version(engine)
    await runtime_module.migrate_schema(engine)
    first = await snapshot(engine)
    await runtime_module.check_schema_version(engine)
    await runtime_module.migrate_schema(engine)
    assert await snapshot(engine) == first
    assert first["marker"] == (
        runtime_module.SCHEMA_VERSION, runtime_module.schema_contract_hash()
    )
    assert first["policies"] == 1
    assert first["deployments"] == first["audits"] == 2
    assert first["triggers"] >= 9
    if legacy:
        async with engine.connect() as connection:
            binding = (await connection.execute(text(
                "SELECT deployment_id, effective_policy_hash, state_namespace, "
                "policy_binding FROM distributed_runs WHERE id = 'legacy-run'"
            ))).one()
            assert binding.deployment_id == runtime_module.PRODUCTION_DEPLOYMENT_ID
            assert binding.effective_policy_hash == runtime_module.BUILTIN_POLICY_HASH
            assert binding.state_namespace == "production"
            assert binding.policy_binding["components"] == runtime_module.BUILTIN_POLICY_COMPONENTS
            assert await connection.scalar(text(
                "SELECT deadline_at > started_at FROM distributed_run_attempts "
                "WHERE id = 'legacy-attempt'"
            ))


@pytest.mark.asyncio
@pytest.mark.parametrize("already_migrated", [False, True])
async def test_failed_migration_does_not_publish_a_success_marker(
    migration_engine, monkeypatch, already_migrated,
):
    engine, _ = migration_engine
    if already_migrated:
        await runtime_module.migrate_schema(engine)
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE distributed_schema_version SET version = 0"))

    async def failing_upgrade(connection):
        await connection.execute(text("CREATE TABLE should_rollback (id INT)"))
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(runtime_module, "upgrade_m3_schema", failing_upgrade)
    with pytest.raises(RuntimeError, match="injected migration failure"):
        await runtime_module.migrate_schema(engine)
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT to_regclass('should_rollback')")) is None
        if already_migrated:
            assert await connection.scalar(text(
                "SELECT version FROM distributed_schema_version WHERE id = 1"
            )) == 0
        else:
            assert await connection.scalar(text(
                "SELECT to_regclass('distributed_schema_version')"
            )) is None


async def start_cli_migration(engine, schema):
    # Adapt only the connection's search_path; run the real parser and CLI code.
    return await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "from functools import partial; "
        "from sqlalchemy.ext.asyncio import create_async_engine; "
        "from core.distributed import cli; "
        "cli.create_async_engine = partial(create_async_engine, "
        f"connect_args={{'server_settings': {{'search_path': {schema!r}}}}}); "
        "cli.main()",
        "migrate",
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[2]),
            "DISTRIBUTED_DATABASE_URL": engine.url.render_as_string(hide_password=False),
            # Successful migration must not touch Redis or start a process loop.
            "DISTRIBUTED_REDIS_URL": "redis://127.0.0.1:1/0",
            "LLM_PROVIDER": "template",
        },
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_two_real_cli_migration_processes_serialize_and_exit(migration_engine):
    engine, schema = migration_engine
    assert parser().parse_args(["migrate"]).command == "migrate"
    blocker = await engine.connect()
    transaction = await blocker.begin()
    await blocker.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": runtime_module.SCHEMA_MIGRATION_LOCK},
    )
    processes = []
    try:
        processes.append(await start_cli_migration(engine, schema))
        processes.append(await start_cli_migration(engine, schema))
        async with asyncio.timeout(10):
            while True:
                async with engine.connect() as connection:
                    waiting = await connection.scalar(text(
                        "SELECT count(*) FROM pg_locks "
                        "WHERE locktype = 'advisory' AND NOT granted "
                        "AND database = (SELECT oid FROM pg_database "
                        "WHERE datname = current_database())"
                    ))
                    assert await connection.scalar(text(
                        "SELECT to_regclass('distributed_schema_version')"
                    )) is None
                if waiting == 2:
                    break
                for process in processes:
                    assert process.returncode is None
                await asyncio.sleep(0.01)
        await transaction.rollback()
        for process in processes:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 10)
            assert process.returncode == 0, (stdout.decode(), stderr.decode())
        await runtime_module.check_schema_version(engine)
        state = await snapshot(engine)
        assert state["policies"] == 1
        assert state["deployments"] == state["audits"] == 2
        async with engine.connect() as connection:
            assert await connection.scalar(text(
                "SELECT count(*) FROM distributed_worker_registry"
            )) == 0
    finally:
        if transaction.is_active:
            await transaction.rollback()
        await blocker.close()
        for process in processes:
            if process.returncode is None:
                process.terminate()
                await asyncio.wait_for(process.communicate(), 5)
