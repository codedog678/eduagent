from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config.settings import settings
from core.distributed import runtime as runtime_module
from core.distributed.expert_repository import ExpertJobRepository
from core.distributed.repository import DistributedRunRepository
from tests.distributed.helpers import spec
from tests.distributed.test_expert_repository import request_for

pytestmark = pytest.mark.distributed_integration


@pytest_asyncio.fixture
async def startup_engine():
    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    schema = f"startup_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        await runtime_module.migrate_schema(engine, 120)
        yield engine, schema
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


def configured_runtime(engine, schema):
    redis_url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("DISTRIBUTED_TEST_REDIS_URL is not configured")
    suffix = uuid4().hex
    configured = settings.model_copy(update={
        "distributed_database_url": engine.url.render_as_string(hide_password=False),
        "distributed_redis_url": redis_url,
        "distributed_experts_enabled": True,
        "distributed_stream": f"test:schema:runs:{suffix}",
        "distributed_consumer_group": f"schema-runs-{suffix}",
        "promotion_rehearsal_stream": f"test:schema:rehearsal:{suffix}",
        "promotion_rehearsal_consumer_group": f"schema-rehearsal-{suffix}",
        "expert_stream": f"test:schema:experts:{suffix}",
        "expert_consumer_group": f"schema-experts-{suffix}",
    })
    runtime = runtime_module.build_runtime(configured)
    original_engine = runtime.engine
    factory = async_sessionmaker(engine, expire_on_commit=False)
    runtime = runtime_module.DistributedRuntime(
        engine, factory, DistributedRunRepository(factory), runtime.broker,
        settings_obj=configured,
    )
    return runtime, original_engine


async def cleanup_runtime(runtime, original_engine):
    for broker in (runtime.broker, runtime.rehearsal_broker,
                   runtime.deployment_broker, runtime.expert_broker):
        await broker.reset_for_tests()
    await runtime.close()
    await original_engine.dispose()


@pytest.mark.asyncio
async def test_current_schema_startup_executes_no_ddl_or_database_writes(startup_engine):
    engine, schema = startup_engine
    runtime, original_engine = configured_runtime(engine, schema)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())

    event.listen(engine.sync_engine, "before_cursor_execute", observe)
    try:
        await runtime.start()
        assert await runtime.health() == {
            "status": "ok", "mode": "distributed-control-plane",
            "postgres": "ok", "redis": "ok",
        }
        assert statements
        assert all(sql.startswith(("SELECT", "SET TRANSACTION READ ONLY"))
                   for sql in statements), statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", observe)
        await cleanup_runtime(runtime, original_engine)


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_kind", ["distributed", "promotion"])
@pytest.mark.parametrize("marker_state", [
    "missing_table", "missing_row", "stale_version", "stale_hash",
    "changed_runtime_version", "changed_runtime_hash",
])
async def test_missing_or_stale_marker_rejects_without_database_writes(
    startup_engine, monkeypatch, runtime_kind, marker_state,
):
    engine, schema = startup_engine
    async with engine.begin() as connection:
        if marker_state == "missing_table":
            await connection.execute(text("DROP TABLE distributed_schema_version"))
        elif marker_state == "missing_row":
            await connection.execute(text("DELETE FROM distributed_schema_version"))
        elif marker_state == "stale_version":
            await connection.execute(text("UPDATE distributed_schema_version SET version = 0"))
        elif marker_state == "stale_hash":
            await connection.execute(text(
                "UPDATE distributed_schema_version SET schema_hash = :hash"
            ), {"hash": "0" * 64})
    if marker_state == "changed_runtime_version":
        monkeypatch.setattr(runtime_module, "SCHEMA_VERSION", 999)
    elif marker_state == "changed_runtime_hash":
        monkeypatch.setattr(runtime_module, "schema_contract_hash", lambda: "0" * 64)
    runtime, original_engine = configured_runtime(engine, schema)
    if runtime_kind == "promotion":
        target = runtime_module.PromotionCommandRuntime(engine, None, None, None)
    else:
        target = runtime
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())

    event.listen(engine.sync_engine, "before_cursor_execute", observe)
    try:
        with pytest.raises(runtime_module.SchemaVersionMismatch, match="drain.*migrate"):
            await target.start()
        assert statements
        assert all(sql.startswith(("SELECT", "SET TRANSACTION READ ONLY"))
                   for sql in statements), statements
        assert not await runtime.broker.redis.exists(runtime.broker.stream)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", observe)
        await cleanup_runtime(runtime, original_engine)


@pytest.mark.asyncio
async def test_promotion_command_startup_is_also_read_only(startup_engine):
    engine, _ = startup_engine
    runtime = runtime_module.PromotionCommandRuntime(engine, None, None, None)
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())

    event.listen(engine.sync_engine, "before_cursor_execute", observe)
    try:
        await runtime.start()
        assert all(sql.startswith(("SELECT", "SET TRANSACTION READ ONLY"))
                   for sql in statements), statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", observe)


async def wait_until(check, timeout=5):
    async with asyncio.timeout(timeout):
        while not await check():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("startup_kind", ["runtime", "cli"])
async def test_hot_start_while_real_expert_terminal_poll_holds_job_lock(
    startup_engine, monkeypatch, startup_kind,
):
    engine, schema = startup_engine
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(factory)
    expert_repository = ExpertJobRepository(factory)
    parent = await repository.accept(spec(request_id=f"hot-start-{uuid4().hex}"))
    claim = await repository.claim(parent.id, "parent-worker", lease_seconds=120)
    job, _ = await expert_repository.create_or_replay(request_for(claim))
    identity_read = asyncio.Event()
    proceed_to_parent = asyncio.Event()
    poll_pid = None
    original_identity = expert_repository._job_identity

    async def paused_identity(session, job_id):
        nonlocal poll_pid
        identity = await original_identity(session, job_id)
        poll_pid = await session.scalar(text("SELECT pg_backend_pid()"))
        identity_read.set()
        await proceed_to_parent.wait()
        return identity

    monkeypatch.setattr(expert_repository, "_job_identity", paused_identity)
    runtime, original_engine = configured_runtime(engine, schema)
    blocker = await engine.connect()
    transaction = await blocker.begin()
    await blocker.execute(
        text("SELECT id FROM distributed_runs WHERE id = :id FOR UPDATE"),
        {"id": parent.id},
    )
    poll = asyncio.create_task(expert_repository.terminal(job.id, claim.fencing_token))
    startup = None
    process = None
    worker_id = f"schema-hot-{uuid4().hex}"
    try:
        await asyncio.wait_for(identity_read.wait(), 5)
        if startup_kind == "runtime":
            startup = asyncio.create_task(runtime.start())
        else:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c",
                "import runpy; from functools import partial; "
                "from sqlalchemy.ext.asyncio import create_async_engine; "
                "from core.distributed import runtime; "
                "runtime.create_async_engine = partial(create_async_engine, "
                f"connect_args={{'server_settings': {{'search_path': {schema!r}}}}}); "
                "runpy.run_module('core.distributed.cli', run_name='__main__')",
                "rehearsal-worker",
                env={
                    **os.environ,
                    "PYTHONPATH": str(Path(__file__).parents[2]),
                    "DISTRIBUTED_ENABLED": "true",
                    "DISTRIBUTED_EXPERTS_ENABLED": "true",
                    "DISTRIBUTED_DATABASE_URL": engine.url.render_as_string(
                        hide_password=False
                    ),
                    "DISTRIBUTED_REDIS_URL": os.environ["DISTRIBUTED_TEST_REDIS_URL"],
                    "DISTRIBUTED_WORKER_ID": worker_id,
                    "DISTRIBUTED_STREAM": runtime.broker.stream,
                    "DISTRIBUTED_CONSUMER_GROUP": runtime.broker.group,
                    "PROMOTION_REHEARSAL_STREAM": runtime.rehearsal_broker.stream,
                    "PROMOTION_REHEARSAL_CONSUMER_GROUP": runtime.rehearsal_broker.group,
                    "EXPERT_STREAM": runtime.expert_broker.stream,
                    "EXPERT_CONSUMER_GROUP": runtime.expert_broker.group,
                    "LLM_PROVIDER": "template",
                    "MEMORY_WORKER_ENABLED": "false",
                },
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

        async def ready_or_ddl_wait():
            async with engine.connect() as connection:
                ddl_wait = await connection.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks "
                    "WHERE relation = 'distributed_runs'::regclass "
                    "AND mode = 'AccessExclusiveLock' AND NOT granted)"
                ))
                registered = await connection.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM distributed_worker_registry "
                    "WHERE worker_id = :id AND status = 'running')"
                ), {"id": worker_id})
            return ddl_wait or registered or (startup is not None and startup.done())

        await wait_until(ready_or_ddl_wait)
        proceed_to_parent.set()

        async def poll_waiting_on_parent():
            async with engine.connect() as connection:
                return await connection.scalar(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE pid = :pid AND wait_event_type = 'Lock')"
                ), {"pid": poll_pid})

        await wait_until(poll_waiting_on_parent)
        if startup is not None:
            await asyncio.wait_for(startup, 5)
        else:
            async def registered_or_exited():
                if process.returncode is not None:
                    stderr = (await process.stderr.read()).decode()
                    pytest.fail(f"CLI exited {process.returncode}: {stderr}")
                async with engine.connect() as connection:
                    return await connection.scalar(text(
                        "SELECT EXISTS (SELECT 1 FROM distributed_worker_registry "
                        "WHERE worker_id = :id AND status = 'running' "
                        "AND process_type = 'rehearsal-worker')"
                    ), {"id": worker_id})
            await wait_until(registered_or_exited)
            assert process.returncode is None
        assert not poll.done()
        await transaction.rollback()
        assert await asyncio.wait_for(poll, 5) is None
    finally:
        proceed_to_parent.set()
        if transaction.is_active:
            await transaction.rollback()
        await blocker.close()
        if process is not None and process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.communicate(), 5)
        for task in (startup, poll):
            if task is not None:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await cleanup_runtime(runtime, original_engine)
