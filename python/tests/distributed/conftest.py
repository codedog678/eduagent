import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def repo():
    from core.distributed import expert_models  # noqa: F401
    from core.distributed.models import DistributedBase
    from core.distributed.repository import DistributedRunRepository

    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
        await conn.run_sync(DistributedBase.metadata.create_all)
        for policy_hash in ("a" * 64, "b" * 64):
            await conn.execute(
                text(
                    "INSERT INTO policy_artifacts ("
                    "policy_hash, parent_policy_hash, components, "
                    "fixed_components_hash, runtime_hash, source_revision, "
                    "protocol_hash, proposer_hash, data_role, "
                    "evidence_bindings, created_at"
                    ") VALUES ("
                    ":policy_hash, NULL, CAST('{}' AS JSON), :policy_hash, "
                    ":policy_hash, 'test', :policy_hash, :policy_hash, "
                    "'test', CAST('{}' AS JSON), :created_at)"
                ),
                {
                    "policy_hash": policy_hash,
                    "created_at": datetime.now(UTC),
                },
            )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield DistributedRunRepository(factory)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def expert_repo(repo):
    from core.distributed.expert_repository import ExpertJobRepository

    return ExpertJobRepository(repo.session_factory)


@pytest_asyncio.fixture
async def broker():
    from core.distributed.broker import RedisRunBroker

    url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    stream = f"test:runs:{uuid4().hex}"
    value = RedisRunBroker(client, stream, "test-workers")
    await value.reset_for_tests()
    yield value
    await value.reset_for_tests()
    await client.aclose()


@pytest_asyncio.fixture
async def expert_broker():
    from core.distributed.broker import RedisStreamBroker

    url = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    stream = f"test:experts:{uuid4().hex}"
    value = RedisStreamBroker(client, stream, "test-expert-workers")
    await value.reset_for_tests()
    yield value
    await value.reset_for_tests()
    await client.aclose()
