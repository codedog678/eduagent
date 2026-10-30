import pytest

from api.orchestrator import AgentOrchestrator
from core.distributed.executor import (
    BusinessStoreBusy,
    LearningTaskExecutor,
)
from core.harness import LearningHarness
from core.run_context import active_run
from tests.distributed.helpers import authority, spec


async def test_executor_reuses_existing_harness_request(tmp_path):
    executor = LearningTaskExecutor(
        store_path=str(tmp_path / "shared.sqlite3")
    )
    request = spec(request_id="same-request")

    first = await executor.execute(request, authority())
    second = await executor.execute(request, authority())

    assert second == first
    assert first["execution"]["request_id"] == "same-request"


async def test_executor_classifies_shared_store_lock_contention(tmp_path):
    store_path = str(tmp_path / "shared.sqlite3")
    owner = LearningHarness(AgentOrchestrator(), store_path)
    try:
        with pytest.raises(BusinessStoreBusy):
            await LearningTaskExecutor(store_path).execute(
                spec(),
                authority(),
            )
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
        ).execute(request, authority())


async def test_harness_injects_authority_and_gateway_into_run_context(
    tmp_path,
):
    expected_authority = authority()
    expected_gateway = object()
    harness = LearningHarness(
        AgentOrchestrator(),
        str(tmp_path / "authority.sqlite3"),
        execution_authority=expected_authority,
        expert_gateway=expected_gateway,
    )

    async def operation():
        ctx = active_run.get()
        assert ctx is not None
        assert ctx.execution_authority is expected_authority
        assert ctx.expert_gateway is expected_gateway
        return {}, None

    try:
        await harness.run(
            "student",
            "authority-request",
            {"kind": "task", "knowledge_id": "grammar_tenses"},
            operation,
        )
    finally:
        await harness.memory_worker.stop()
        harness.close()
