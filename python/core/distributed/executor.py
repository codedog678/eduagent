from __future__ import annotations

from typing import Protocol
from pathlib import Path

from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.distributed.contracts import (
    DistributedRunRequest,
    RunOperation,
)
from core.distributed.expert_contracts import RunExecutionAuthority
from core.distributed.promotion_contracts import Environment, PolicyExecutionBinding
from core.distributed.policy_health import ConfirmedPermissionViolation
from core.distributed.rehearsal_store import RehearsalStoreRouter, ShadowStoreRouter
from core.harness import LearningHarness


class BusinessStoreBusy(RuntimeError):
    pass


class ShadowExecutionError(RuntimeError):
    def __init__(self, usage):
        super().__init__("shadow execution failed")
        self.usage = usage


def assert_open_store_capability(database, expected_path):
    # 读取已打开连接的服务端 SQLite 元数据，不把拒绝请求当成实际越权。
    for _, _, filename in database.execute("PRAGMA database_list"):
        if filename and Path(filename).resolve() != expected_path:
            raise ConfirmedPermissionViolation("opened database differs from frozen store capability")


class RunExecutor(Protocol):
    async def execute(
        self,
        spec: DistributedRunRequest,
        authority: RunExecutionAuthority,
        binding: PolicyExecutionBinding,
    ) -> dict:
        """Execute one frozen distributed run request."""


class LearningTaskExecutor:
    def __init__(
        self,
        store_path: str | None,
        enable_db_logging: bool = False,
        expert_gateway=None,
        *,
        allowed_environment: Environment = "production",
        rehearsal_store_root: str | None = None,
        shadow_store_router: ShadowStoreRouter | None = None,
        usage_recorder=None,
    ) -> None:
        self.store_path = store_path
        self.enable_db_logging = enable_db_logging
        self.expert_gateway = expert_gateway
        self.usage_recorder = usage_recorder
        if shadow_store_router is not None:
            if store_path is not None or expert_gateway is not None:
                raise ValueError("shadow executor cannot receive primary store or durable gateway")
            if enable_db_logging:
                raise ValueError("shadow executor cannot enable database logging")
            self.store_router = shadow_store_router
        else:
            if store_path is None:
                raise ValueError("primary executor requires store path")
            self.store_router = RehearsalStoreRouter(
                store_path,
                rehearsal_store_root or settings.promotion_rehearsal_store_root,
                allowed_environment=allowed_environment,
            )

    async def execute(
        self,
        spec: DistributedRunRequest,
        authority: RunExecutionAuthority,
        binding: PolicyExecutionBinding,
    ) -> dict:
        authority.validate_binding(binding)
        if (authority.execution_mode == "shadow") != isinstance(self.store_router, ShadowStoreRouter):
            raise ValueError("executor store capability differs from authority")
        if authority.execution_mode == "shadow":
            self.store_router.assert_locked(binding)
        if spec.operation != RunOperation.LEARNING_TASK:
            raise ValueError(f"unsupported operation: {spec.operation}")
        store_path = str(self.store_router.path_for(binding))
        expected_path = Path(store_path).resolve()

        orchestrator = AgentOrchestrator(
            enable_db_logging=self.enable_db_logging
        )
        harness: LearningHarness | None = None
        shadow_usage = {"model_calls": 0, "tool_calls": 0}
        try:
            try:
                harness = LearningHarness(
                    orchestrator,
                    store_path,
                    settings.harness_timeout_seconds,
                    settings.quiz_ttl_seconds,
                    execution_authority=authority,
                    expert_gateway=self.expert_gateway,
                    pinned_policy=binding,
                    state_namespace=binding.state_namespace,
                    shadow_usage_sink=shadow_usage.update if authority.execution_mode == "shadow" else None,
                    execution_usage_sink=shadow_usage.update if authority.execution_mode != "shadow" else None,
                )
                assert_open_store_capability(harness.db, expected_path)
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
            result = await harness.converse(
                spec.learner_id,
                spec.request_id,
                payload.knowledge_id,
                payload.question,
                payload.session_id,
                payload.thread_id,
                payload.quiz_id,
                kind="task",
            )
            assert_open_store_capability(harness.db, expected_path)
            return result
        except Exception as exc:
            if authority.execution_mode == "shadow":
                raise ShadowExecutionError(shadow_usage) from exc
            raise
        finally:
            if harness is not None:
                await harness.memory_worker.stop()
                harness.close()
            await orchestrator.close_database()
            if self.usage_recorder is not None and authority.execution_mode != "shadow":
                await self.usage_recorder(
                    str(authority.distributed_run_id), authority.run_fencing_token, shadow_usage,
                )
