from __future__ import annotations

from typing import Protocol

from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.distributed.contracts import (
    DistributedRunRequest,
    RunOperation,
)
from core.harness import LearningHarness


class BusinessStoreBusy(RuntimeError):
    pass


class RunExecutor(Protocol):
    async def execute(self, spec: DistributedRunRequest) -> dict:
        """Execute one frozen distributed run request."""


class LearningTaskExecutor:
    def __init__(
        self,
        store_path: str,
        enable_db_logging: bool = False,
    ) -> None:
        self.store_path = store_path
        self.enable_db_logging = enable_db_logging

    async def execute(self, spec: DistributedRunRequest) -> dict:
        if spec.operation != RunOperation.LEARNING_TASK:
            raise ValueError(f"unsupported operation: {spec.operation}")

        orchestrator = AgentOrchestrator(
            enable_db_logging=self.enable_db_logging
        )
        harness: LearningHarness | None = None
        try:
            try:
                harness = LearningHarness(
                    orchestrator,
                    self.store_path,
                    settings.harness_timeout_seconds,
                    settings.quiz_ttl_seconds,
                )
            except RuntimeError as exc:
                message = str(exc)
                if (
                    "requires one server worker" in message
                    or "already owned" in message
                ):
                    raise BusinessStoreBusy(
                        "business_store_busy"
                    ) from exc
                raise

            orchestrator.harness = harness
            payload = spec.payload
            return await harness.converse(
                spec.learner_id,
                spec.request_id,
                payload.knowledge_id,
                payload.question,
                payload.session_id,
                payload.thread_id,
                payload.quiz_id,
                kind="task",
            )
        finally:
            if harness is not None:
                await harness.memory_worker.stop()
                harness.close()
            await orchestrator.close_database()
