from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config.settings import settings
from core.policy_store import (
    BUILTIN_HASH,
    builtin_components,
    digest as policy_digest,
)
from core.tutor_policy import fixed_components

from .broker import RedisStreamBroker
from .contracts import canonical_hash
from .metrics import DistributedMetrics
from .models import DistributedBase
from .ops_queries import OpsQueries
from .repository import DistributedRunRepository
from .telemetry import DurableTracer, build_optional_otel_tracer
from .worker_registry import WorkerRegistry

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
        self.expert_broker = RedisStreamBroker(
            broker.redis,
            settings_obj.expert_stream,
            settings_obj.expert_consumer_group,
        )
        self.metrics = metrics or DistributedMetrics()
        self.tracer = tracer or DurableTracer(repository)
        self.otel_provider = otel_provider
        self.settings = settings_obj
        self.worker_registry = WorkerRegistry(session_factory)
        self.ops_queries = OpsQueries(
            session_factory,
            worker_stale_seconds=settings_obj.ops_worker_stale_seconds,
        )
        self.expert_repository = self._build_expert_repository()

    async def start(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(DistributedBase.metadata.create_all)
            await upgrade_m1_schema(
                conn,
                self.settings.distributed_attempt_timeout_seconds,
            )
            await upgrade_m3_schema(conn)
        await self.broker.ensure_group()
        if self.settings.distributed_experts_enabled:
            await self.expert_broker.ensure_group()

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

    def worker(
        self,
        worker_id,
        executor,
        *,
        registry_process=None,
    ) -> RunWorker:
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
            registry_process=registry_process,
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

        return DurableExpertGateway(
            self.expert_repository,
            InlineExpertGateway(
                ExpertEngine(get_llm_service())
            ),
            poll_seconds=self.settings.expert_result_poll_seconds,
            metrics=self.metrics,
        )

    def expert_dispatcher(self):
        from .expert_dispatcher import ExpertDispatcher

        return ExpertDispatcher(
            self.expert_repository,
            self.expert_broker,
            self.settings.distributed_outbox_batch_size,
            metrics=self.metrics,
        )

    def expert_reaper(self):
        from .expert_reaper import ExpertReaper

        return ExpertReaper(
            self.expert_repository,
            metrics=self.metrics,
        )

    def expert_worker(
        self,
        worker_id,
        engine,
        *,
        roles,
        registry_process=None,
    ):
        from .expert_worker import ExpertWorker

        return ExpertWorker(
            worker_id,
            self.expert_repository,
            self.expert_broker,
            engine,
            roles=roles,
            lease_seconds=self.settings.expert_lease_seconds,
            heartbeat_seconds=self.settings.expert_heartbeat_seconds,
            poll_block_ms=self.settings.expert_poll_block_ms,
            pause_before_result_seconds=(
                self.settings.expert_demo_pause_before_result_seconds
            ),
            metrics=self.metrics,
            registry_process=registry_process,
        )

    def _build_expert_repository(self):
        from .expert_repository import ExpertJobRepository

        return ExpertJobRepository(
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


BUILTIN_POLICY_COMPONENTS = builtin_components()
BUILTIN_POLICY_HASH = BUILTIN_HASH
BUILTIN_FIXED_COMPONENTS_HASH = policy_digest(fixed_components())
BUILTIN_RUNTIME_HASH = canonical_hash({"runtime": "builtin"})
BUILTIN_PROTOCOL_HASH = canonical_hash({"protocol": "builtin"})
BUILTIN_PROPOSER_HASH = canonical_hash({"proposer": "system"})
PRODUCTION_DEPLOYMENT_ID = "00000000-0000-0000-0000-000000000001"
REHEARSAL_DEPLOYMENT_ID = "00000000-0000-0000-0000-000000000002"
DEFAULT_POLICY_THRESHOLDS = {
    "candidate_min_runs": 20,
    "stable_min_runs": 20,
    "window_max_runs": 50,
    "commit_failure_rate": "0.05",
    "terminal_failure_rate": "0.10",
    "latency_increase_rate": "0.50",
    "mean_cost_increase_rate": "0.30",
    "unknown_rate": "0.10",
    "relative_epsilon": "0.000001",
}
DEFAULT_POLICY_THRESHOLDS_HASH = canonical_hash(DEFAULT_POLICY_THRESHOLDS)


async def upgrade_m3_schema(connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    run_columns = {
        "deployment_id": "VARCHAR(36)",
        "effective_policy_hash": "VARCHAR(64)",
        "policy_cohort": "VARCHAR(16)",
        "assignment_key_hash": "VARCHAR(64)",
        "assignment_reason": "VARCHAR(128)",
        "state_namespace": "VARCHAR(128)",
        "rehearsal_id": "VARCHAR(128)",
        "rehearsal_fault_profile": "VARCHAR(32) DEFAULT 'none'",
    }
    expert_columns = {
        "deployment_id": "VARCHAR(36)",
        "state_namespace": "VARCHAR(128)",
    }
    for name, sql_type in run_columns.items():
        await connection.execute(
            text(
                f"ALTER TABLE distributed_runs "
                f"ADD COLUMN IF NOT EXISTS {name} {sql_type}"
            )
        )
    for name, sql_type in expert_columns.items():
        await connection.execute(
            text(
                f"ALTER TABLE distributed_expert_jobs "
                f"ADD COLUMN IF NOT EXISTS {name} {sql_type}"
            )
        )

    now = datetime.now(UTC)
    await connection.execute(
        text(
            "INSERT INTO policy_artifacts ("
            "policy_hash, parent_policy_hash, components, "
            "fixed_components_hash, runtime_hash, source_revision, "
            "protocol_hash, proposer_hash, data_role, evidence_bindings, "
            "created_at"
            ") VALUES ("
            ":policy_hash, NULL, CAST(:components AS JSON), "
            ":fixed_hash, :runtime_hash, 'builtin', :protocol_hash, "
            ":proposer_hash, 'builtin', CAST('{}' AS JSON), :created_at"
            ") ON CONFLICT (policy_hash) DO NOTHING"
        ),
        {
            "policy_hash": BUILTIN_POLICY_HASH,
            "components": json.dumps(
                BUILTIN_POLICY_COMPONENTS,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "fixed_hash": BUILTIN_FIXED_COMPONENTS_HASH,
            "runtime_hash": BUILTIN_RUNTIME_HASH,
            "protocol_hash": BUILTIN_PROTOCOL_HASH,
            "proposer_hash": BUILTIN_PROPOSER_HASH,
            "created_at": now,
        },
    )
    for environment, deployment_id in (
        ("production", PRODUCTION_DEPLOYMENT_ID),
        ("rehearsal", REHEARSAL_DEPLOYMENT_ID),
    ):
        await connection.execute(
            text(
                "INSERT INTO policy_deployments ("
                "deployment_id, environment, version, state, "
                "candidate_policy_hash, stable_policy_hash, "
                "previous_stable_deployment_id, traffic_basis_points, "
                "assignment_salt_id, thresholds, thresholds_hash, "
                "required_receipts, command_id, reason, actor, created_at"
                ") VALUES ("
                ":deployment_id, :environment, 1, 'registered', NULL, "
                ":policy_hash, NULL, 0, 'builtin', "
                "CAST(:thresholds AS JSON), :thresholds_hash, "
                "CAST('[]' AS JSON), :command_id, 'builtin bootstrap', "
                "'system', :created_at"
                ") ON CONFLICT (deployment_id) DO NOTHING"
            ),
            {
                "deployment_id": deployment_id,
                "environment": environment,
                "policy_hash": BUILTIN_POLICY_HASH,
                "thresholds": (
                    '{"candidate_min_runs":20,"commit_failure_rate":"0.05",'
                    '"latency_increase_rate":"0.50",'
                    '"mean_cost_increase_rate":"0.30",'
                    '"relative_epsilon":"0.000001","stable_min_runs":20,'
                    '"terminal_failure_rate":"0.10","unknown_rate":"0.10",'
                    '"window_max_runs":50}'
                ),
                "thresholds_hash": DEFAULT_POLICY_THRESHOLDS_HASH,
                "command_id": f"bootstrap-{environment}",
                "created_at": now,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO policy_environment_heads ("
                "environment, current_deployment_id, current_version, "
                "updated_at"
                ") VALUES (:environment, :deployment_id, 1, :updated_at) "
                "ON CONFLICT (environment) DO NOTHING"
            ),
            {
                "environment": environment,
                "deployment_id": deployment_id,
                "updated_at": now,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO policy_audit_events ("
                "event_id, environment, deployment_id, event_type, "
                "command_id, actor, reason, details, created_at"
                ") VALUES ("
                ":event_id, :environment, :deployment_id, 'bootstrap', "
                ":command_id, 'system', 'builtin bootstrap', "
                "CAST('{}' AS JSON), :created_at"
                ") ON CONFLICT (event_id) DO NOTHING"
            ),
            {
                "event_id": (
                    "00000000-0000-0000-0000-000000000011"
                    if environment == "production"
                    else "00000000-0000-0000-0000-000000000012"
                ),
                "environment": environment,
                "deployment_id": deployment_id,
                "command_id": f"bootstrap-{environment}",
                "created_at": now,
            },
        )

    await connection.execute(
        text(
            "UPDATE distributed_runs SET "
            "deployment_id = COALESCE(deployment_id, :deployment_id), "
            "effective_policy_hash = COALESCE("
            "effective_policy_hash, :policy_hash), "
            "policy_cohort = COALESCE(policy_cohort, 'stable'), "
            "assignment_key_hash = COALESCE("
            "assignment_key_hash, :policy_hash), "
            "assignment_reason = COALESCE("
            "assignment_reason, 'legacy_backfill'), "
            "state_namespace = COALESCE(state_namespace, 'production'), "
            "rehearsal_fault_profile = COALESCE("
            "rehearsal_fault_profile, 'none') "
            "WHERE deployment_id IS NULL "
            "OR effective_policy_hash IS NULL "
            "OR policy_cohort IS NULL "
            "OR assignment_key_hash IS NULL "
            "OR assignment_reason IS NULL "
            "OR state_namespace IS NULL "
            "OR rehearsal_fault_profile IS NULL"
        ),
        {
            "deployment_id": PRODUCTION_DEPLOYMENT_ID,
            "policy_hash": BUILTIN_POLICY_HASH,
        },
    )
    await connection.execute(
        text(
            "UPDATE distributed_expert_jobs AS jobs SET "
            "deployment_id = COALESCE(jobs.deployment_id, runs.deployment_id), "
            "state_namespace = COALESCE("
            "jobs.state_namespace, runs.state_namespace) "
            "FROM distributed_runs AS runs "
            "WHERE jobs.parent_run_id = runs.id "
            "AND (jobs.deployment_id IS NULL OR jobs.state_namespace IS NULL)"
        )
    )
    for source_table, source_column in (
        ("distributed_runs", "effective_policy_hash"),
        ("distributed_expert_jobs", "policy_hash"),
    ):
        await connection.execute(
            text(
                "INSERT INTO policy_artifacts ("
                "policy_hash, parent_policy_hash, components, "
                "fixed_components_hash, runtime_hash, source_revision, "
                "protocol_hash, proposer_hash, data_role, evidence_bindings, "
                "created_at"
                ") SELECT "
                "source.policy_hash, NULL, "
                "json_build_object("
                "'retrieval_rules', "
                "'Legacy policy content is unavailable after M3 schema "
                "migration; this placeholder is not release eligible.'"
                "), "
                ":fixed_hash, :runtime_hash, 'legacy-m3-backfill', "
                ":protocol_hash, :proposer_hash, 'legacy', "
                "json_build_object("
                "'migration', 'm3', "
                "'legacy_policy_hash', source.policy_hash, "
                "'release_eligible', false"
                "), :created_at "
                f"FROM (SELECT DISTINCT {source_column} AS policy_hash "
                f"FROM {source_table} WHERE {source_column} IS NOT NULL"
                ") AS source "
                "LEFT JOIN policy_artifacts AS artifacts "
                "ON artifacts.policy_hash = source.policy_hash "
                "WHERE artifacts.policy_hash IS NULL "
                "ON CONFLICT (policy_hash) DO NOTHING"
            ),
            {
                "fixed_hash": BUILTIN_FIXED_COMPONENTS_HASH,
                "runtime_hash": BUILTIN_RUNTIME_HASH,
                "protocol_hash": BUILTIN_PROTOCOL_HASH,
                "proposer_hash": BUILTIN_PROPOSER_HASH,
                "created_at": now,
            },
        )

    defaults = {
        "deployment_id": PRODUCTION_DEPLOYMENT_ID,
        "effective_policy_hash": BUILTIN_POLICY_HASH,
        "policy_cohort": "stable",
        "assignment_key_hash": BUILTIN_POLICY_HASH,
        "assignment_reason": "legacy_backfill",
        "state_namespace": "production",
        "rehearsal_fault_profile": "none",
    }
    for column, default in defaults.items():
        await connection.execute(
            text(
                f"ALTER TABLE distributed_runs ALTER COLUMN {column} "
                f"SET DEFAULT '{default}'"
            )
        )
        await connection.execute(
            text(
                f"ALTER TABLE distributed_runs ALTER COLUMN {column} "
                "SET NOT NULL"
            )
        )
    for column, default in (
        ("deployment_id", PRODUCTION_DEPLOYMENT_ID),
        ("state_namespace", "production"),
    ):
        await connection.execute(
            text(
                f"ALTER TABLE distributed_expert_jobs ALTER COLUMN {column} "
                f"SET DEFAULT '{default}'"
            )
        )
        await connection.execute(
            text(
                f"ALTER TABLE distributed_expert_jobs ALTER COLUMN {column} "
                "SET NOT NULL"
            )
        )

    constraints = {
        "fk_distributed_run_deployment": (
            "distributed_runs",
            "FOREIGN KEY (deployment_id) "
            "REFERENCES policy_deployments(deployment_id)",
        ),
        "fk_distributed_run_effective_policy": (
            "distributed_runs",
            "FOREIGN KEY (effective_policy_hash) "
            "REFERENCES policy_artifacts(policy_hash)",
        ),
        "fk_expert_job_deployment": (
            "distributed_expert_jobs",
            "FOREIGN KEY (deployment_id) "
            "REFERENCES policy_deployments(deployment_id)",
        ),
        "fk_expert_job_policy_artifact": (
            "distributed_expert_jobs",
            "FOREIGN KEY (policy_hash) "
            "REFERENCES policy_artifacts(policy_hash)",
        ),
        "uq_policy_audit_command_deployment_event_type": (
            "policy_audit_events",
            "UNIQUE (command_id, deployment_id, event_type)",
        ),
    }
    for name, (table_name, definition) in constraints.items():
        await connection.execute(
            text(
                "DO $$ BEGIN "
                f"IF NOT EXISTS (SELECT 1 FROM pg_constraint "
                f"WHERE conname = '{name}' "
                f"AND conrelid = '{table_name}'::regclass) THEN "
                f"ALTER TABLE {table_name} ADD CONSTRAINT {name} "
                f"{definition}; "
                "END IF; END $$"
            )
        )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_distributed_run_deployment "
            "ON distributed_runs (deployment_id)"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_distributed_run_effective_policy "
            "ON distributed_runs (effective_policy_hash)"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_expert_job_deployment "
            "ON distributed_expert_jobs (deployment_id)"
        )
    )
    await connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_expert_job_policy "
            "ON distributed_expert_jobs (policy_hash)"
        )
    )

    await connection.execute(
        text(
            "CREATE OR REPLACE FUNCTION reject_m3_append_only_change() "
            "RETURNS trigger AS $$ BEGIN "
            "RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    for table_name in (
        "policy_artifacts",
        "policy_gate_receipts",
        "policy_deployments",
        "policy_observations",
        "policy_health_windows",
        "policy_audit_events",
    ):
        trigger_name = f"trg_{table_name}_append_only"
        await connection.execute(
            text(
                f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"
            )
        )
        await connection.execute(
            text(
                f"CREATE TRIGGER {trigger_name} "
                f"BEFORE UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION "
                "reject_m3_append_only_change()"
            )
        )
    await connection.execute(
        text(
            "CREATE OR REPLACE FUNCTION reject_run_binding_change() "
            "RETURNS trigger AS $$ BEGIN "
            "IF NEW.deployment_id IS DISTINCT FROM OLD.deployment_id "
            "OR NEW.effective_policy_hash IS DISTINCT FROM "
            "OLD.effective_policy_hash "
            "OR NEW.policy_cohort IS DISTINCT FROM OLD.policy_cohort "
            "OR NEW.assignment_key_hash IS DISTINCT FROM "
            "OLD.assignment_key_hash "
            "OR NEW.assignment_reason IS DISTINCT FROM OLD.assignment_reason "
            "OR NEW.state_namespace IS DISTINCT FROM OLD.state_namespace "
            "OR NEW.rehearsal_id IS DISTINCT FROM OLD.rehearsal_id "
            "OR NEW.rehearsal_fault_profile IS DISTINCT FROM "
            "OLD.rehearsal_fault_profile THEN "
            "RAISE EXCEPTION 'distributed run assignment is immutable'; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    await connection.execute(
        text(
            "DROP TRIGGER IF EXISTS trg_distributed_run_binding_immutable "
            "ON distributed_runs"
        )
    )
    await connection.execute(
        text(
            "CREATE TRIGGER trg_distributed_run_binding_immutable "
            "BEFORE UPDATE ON distributed_runs "
            "FOR EACH ROW EXECUTE FUNCTION reject_run_binding_change()"
        )
    )
    await connection.execute(
        text(
            "CREATE OR REPLACE FUNCTION reject_expert_binding_change() "
            "RETURNS trigger AS $$ BEGIN "
            "IF NEW.deployment_id IS DISTINCT FROM OLD.deployment_id "
            "OR NEW.state_namespace IS DISTINCT FROM OLD.state_namespace "
            "OR NEW.policy_hash IS DISTINCT FROM OLD.policy_hash THEN "
            "RAISE EXCEPTION 'distributed expert assignment is immutable'; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    await connection.execute(
        text(
            "DROP TRIGGER IF EXISTS trg_expert_job_binding_immutable "
            "ON distributed_expert_jobs"
        )
    )
    await connection.execute(
        text(
            "CREATE TRIGGER trg_expert_job_binding_immutable "
            "BEFORE UPDATE ON distributed_expert_jobs "
            "FOR EACH ROW EXECUTE FUNCTION reject_expert_binding_change()"
        )
    )
    await connection.execute(
        text(
            "CREATE OR REPLACE FUNCTION reject_invalid_shadow_change() "
            "RETURNS trigger AS $$ BEGIN "
            "IF TG_OP = 'DELETE' THEN "
            "RAISE EXCEPTION '% rows cannot be deleted', TG_TABLE_NAME; "
            "END IF; "
            "IF OLD.status NOT IN ('queued', 'leased', 'running') THEN "
            "RAISE EXCEPTION '% terminal row is append-only', TG_TABLE_NAME; "
            "END IF; "
            "IF NEW.shadow_id IS DISTINCT FROM OLD.shadow_id "
            "OR NEW.parent_run_id IS DISTINCT FROM OLD.parent_run_id "
            "OR NEW.deployment_id IS DISTINCT FROM OLD.deployment_id "
            "OR NEW.policy_hash IS DISTINCT FROM OLD.policy_hash "
            "OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN "
            "RAISE EXCEPTION '% identity is immutable', TG_TABLE_NAME; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    await connection.execute(
        text(
            "DROP TRIGGER IF EXISTS trg_policy_shadow_terminal_immutable "
            "ON policy_shadow_executions"
        )
    )
    await connection.execute(
        text(
            "CREATE TRIGGER trg_policy_shadow_terminal_immutable "
            "BEFORE UPDATE OR DELETE ON policy_shadow_executions "
            "FOR EACH ROW EXECUTE FUNCTION reject_invalid_shadow_change()"
        )
    )


class PromotionCommandRuntime:
    """Database-only runtime for the isolated promotion command CLI."""

    def __init__(self, engine, session_factory, service, token_issuer) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.service = service
        self.token_issuer = token_issuer

    async def start(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(DistributedBase.metadata.create_all)
            await upgrade_m3_schema(connection)

    async def close(self) -> None:
        await self.engine.dispose()


def build_promotion_command_runtime(settings_obj=settings) -> PromotionCommandRuntime:
    """Build promotion DB services without Redis, HTTP, workers, or Ops."""
    from .promotion_repository import PromotionRepository
    from .promotion_service import (
        PromotionCommandService,
        RehearsalTokenIssuer,
    )

    engine = create_async_engine(
        settings_obj.effective_distributed_database_url,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = PromotionRepository(factory)
    return PromotionCommandRuntime(
        engine,
        factory,
        PromotionCommandService(repository),
        RehearsalTokenIssuer(
            repository,
            signing_secret=(
                settings_obj.promotion_rehearsal_secret.get_secret_value()
            ),
            assignment_secret=(
                settings_obj.promotion_assignment_secret.get_secret_value()
            ),
            allow_fault_injection=(
                settings_obj.promotion_fault_injection_enabled
            ),
        ),
    )
