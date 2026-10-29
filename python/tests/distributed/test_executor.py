import pytest

from api.orchestrator import AgentOrchestrator
from core.distributed.executor import (
    BusinessStoreBusy,
    LearningTaskExecutor,
)
from core.harness import LearningHarness
from tests.distributed.helpers import spec


async def test_executor_reuses_existing_harness_request(tmp_path):
    executor = LearningTaskExecutor(
        store_path=str(tmp_path / "shared.sqlite3")
    )
    request = spec(request_id="same-request")

    first = await executor.execute(request)
    second = await executor.execute(request)

    assert second == first
    assert first["execution"]["request_id"] == "same-request"


async def test_executor_classifies_shared_store_lock_contention(tmp_path):
    store_path = str(tmp_path / "shared.sqlite3")
    owner = LearningHarness(AgentOrchestrator(), store_path)
    try:
        with pytest.raises(BusinessStoreBusy):
            await LearningTaskExecutor(store_path).execute(spec())
    finally:
        await owner.memory_worker.stop()
        owner.close()


async def test_executor_rejects_unsupported_operation(tmp_path):
    request = spec().model_copy(
        update={"operation": "unsupported"},
    )

    with pytest.raises(ValueError, match="unsupported operation"):
        await LearningTaskExecutor(
            str(tmp_path / "shared.sqlite3")
        ).execute(request)
