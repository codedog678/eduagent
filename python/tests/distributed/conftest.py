import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def repo():
    from core.distributed.models import DistributedBase
    from core.distributed.repository import DistributedRunRepository

    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
        await conn.run_sync(DistributedBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield DistributedRunRepository(factory)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
    await engine.dispose()
