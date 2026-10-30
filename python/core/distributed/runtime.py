from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config.settings import settings

from .metrics import DistributedMetrics
from .models import DistributedBase
from .repository import DistributedRunRepository
from .telemetry import DurableTracer, build_optional_otel_tracer

if TYPE_CHECKING:
    from .dispatcher import OutboxDispatcher
    from .reaper import LeaseReaper
    from .worker import RunWorker


class DistributedRuntime:
    def __init__(
        self,
        engine,
        session_factory,
        repository,
        broker,
        *,
        metrics=None,
        tracer=None,
        otel_provider=None,
        settings_obj=settings,
    ) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.repository = repository
        self.broker = broker
        self.metrics = metrics or DistributedMetrics()
        self.tracer = tracer or DurableTracer(repository)
        self.otel_provider = otel_provider
        self.settings = settings_obj

    async def start(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(DistributedBase.metadata.create_all)
            await upgrade_m1_schema(
                conn,
                self.settings.distributed_attempt_timeout_seconds,
            )
        await self.broker.ensure_group()

    async def close(self) -> None:
        try:
            await self.broker.redis.aclose()
        finally:
            await self.engine.dispose()
            if self.otel_provider is not None:
                with suppress(Exception):
                    self.otel_provider.shutdown()

    async def health(self) -> dict[str, str]:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        redis_ok = bool(await self.broker.redis.ping())
        return {
            "status": "ok" if redis_ok else "degraded",
            "mode": "distributed-control-plane",
            "postgres": "ok",
            "redis": "ok" if redis_ok else "error",
        }

    def dispatcher(self) -> OutboxDispatcher:
        from .dispatcher import OutboxDispatcher

        return OutboxDispatcher(
            self.repository,
            self.broker,
            self.settings.distributed_outbox_batch_size,
            tracer=self.tracer,
            metrics=self.metrics,
        )

    def reaper(self) -> LeaseReaper:
        from .reaper import LeaseReaper

        return LeaseReaper(
            self.repository,
            tracer=self.tracer,
            metrics=self.metrics,
        )

    def worker(self, worker_id, executor) -> RunWorker:
        from .worker import RunWorker

        return RunWorker(
            worker_id,
            self.repository,
            self.broker,
            executor,
            lease_seconds=self.settings.distributed_lease_seconds,
            heartbeat_seconds=self.settings.distributed_heartbeat_seconds,
            max_attempts=self.settings.distributed_max_attempts,
            pause_before_commit_seconds=(
                self.settings.distributed_demo_pause_before_commit_seconds
            ),
            tracer=self.tracer,
            metrics=self.metrics,
        )

    def expert_gateway(self):
        if not self.settings.distributed_experts_enabled:
            return None
        from core.llm_service import get_llm_service

        from .expert_engine import ExpertEngine
        from .expert_gateway import (
            DurableExpertGateway,
            InlineExpertGateway,
        )
        from .expert_repository import ExpertJobRepository

        repository = ExpertJobRepository(
            self.session_factory,
            queued_limit_per_role=(
                self.settings.expert_queued_limit_per_role
            ),
            running_limit_per_role=(
                self.settings.expert_running_limit_per_role
            ),
            queued_payload_bytes_limit=(
                self.settings.expert_queued_payload_bytes_limit
            ),
            max_payload_bytes=self.settings.expert_max_payload_bytes,
            max_job_seconds=self.settings.expert_max_job_seconds,
            retry_base_seconds=self.settings.expert_retry_base_seconds,
            retry_max_seconds=self.settings.expert_retry_max_seconds,
        )
        return DurableExpertGateway(
            repository,
            InlineExpertGateway(
                ExpertEngine(get_llm_service())
            ),
            poll_seconds=self.settings.expert_result_poll_seconds,
            metrics=self.metrics,
        )


def build_runtime(settings_obj=settings) -> DistributedRuntime:
    from .broker import RedisRunBroker

    engine = create_async_engine(
        settings_obj.effective_distributed_database_url,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(
        factory,
        max_attempts=settings_obj.distributed_max_attempts,
        parent_timeout_seconds=(
            settings_obj.distributed_attempt_timeout_seconds
        ),
    )
    broker = RedisRunBroker(
        Redis.from_url(
            settings_obj.distributed_redis_url,
            decode_responses=True,
        ),
        settings_obj.distributed_stream,
        settings_obj.distributed_consumer_group,
    )
    metrics = DistributedMetrics()
    otel_tracer, otel_provider = build_optional_otel_tracer(
        settings_obj.otel_exporter_otlp_endpoint
    )
    return DistributedRuntime(
        engine,
        factory,
        repository,
        broker,
        metrics=metrics,
        tracer=DurableTracer(repository, otel_tracer),
        otel_provider=otel_provider,
        settings_obj=settings_obj,
    )


async def upgrade_m1_schema(
    connection,
    parent_timeout_seconds: float,
) -> None:
    await connection.execute(
        text(
            "ALTER TABLE distributed_run_attempts "
            "ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ"
        )
    )
    await connection.execute(
        text(
            "UPDATE distributed_run_attempts "
            "SET deadline_at = started_at + "
            "make_interval(secs => CAST(:timeout AS double precision)) "
            "WHERE deadline_at IS NULL"
        ),
        {"timeout": parent_timeout_seconds},
    )
    await connection.execute(
        text(
            "ALTER TABLE distributed_run_attempts "
            "ALTER COLUMN deadline_at SET NOT NULL"
        )
    )
