from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class DistributedMetrics:
    """Prometheus instruments owned by one distributed runtime."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = (
            registry
            if registry is not None
            else CollectorRegistry(auto_describe=True)
        )
        self.runs = Counter(
            "eduagent_distributed_runs_total",
            "Distributed runs by terminal outcome",
            ("outcome",),
            registry=self.registry,
        )
        self.run_states = Gauge(
            "eduagent_distributed_runs_by_status",
            "Authoritative PostgreSQL run count by current status",
            ("status",),
            registry=self.registry,
        )
        self.lease_takeovers = Counter(
            "eduagent_distributed_lease_takeovers_total",
            "Expired lease takeovers",
            registry=self.registry,
        )
        self.idempotency_hits = Counter(
            "eduagent_distributed_idempotency_hits_total",
            "Request or step replay hits",
            ("scope",),
            registry=self.registry,
        )
        self.fencing_rejections = Counter(
            "eduagent_distributed_fencing_rejections_total",
            "Writes rejected because the fencing token was stale",
            registry=self.registry,
        )
        self.queue_depth = Gauge(
            "eduagent_distributed_queue_depth",
            "Redis stream pending depth",
            registry=self.registry,
        )
        self.run_latency = Histogram(
            "eduagent_distributed_run_latency_seconds",
            "Accepted-to-terminal latency",
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
            registry=self.registry,
        )
        self.recovery_latency = Histogram(
            "eduagent_distributed_recovery_latency_seconds",
            "Lease expiry to successful reclaim",
            buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
            registry=self.registry,
        )
        self.expert_queue_depth = Gauge(
            "eduagent_expert_queue_depth",
            "Expert Redis stream pending depth",
            registry=self.registry,
        )
        self.expert_jobs = Gauge(
            "eduagent_expert_jobs_by_role_status",
            "Authoritative expert job count by role and status",
            ("role", "status"),
            registry=self.registry,
        )
        self.expert_results = Counter(
            "eduagent_expert_results_total",
            "Expert result decisions by disposition and rejection code",
            ("disposition", "rejection_code"),
            registry=self.registry,
        )
        self.expert_takeovers = Counter(
            "eduagent_expert_takeovers_total",
            "Expert jobs changed by recovery processing",
            registry=self.registry,
        )
        self.expert_retries = Counter(
            "eduagent_expert_retries_total",
            "Expert attempts scheduled for retry",
            ("role",),
            registry=self.registry,
        )
        self.expert_backpressure = Counter(
            "eduagent_expert_backpressure_total",
            "Expert admission rejections",
            ("role",),
            registry=self.registry,
        )
        self.expert_snapshot_bytes = Histogram(
            "eduagent_expert_snapshot_bytes",
            "Frozen expert request size",
            buckets=(1024, 4096, 16384, 65536, 262144, 1048576),
            registry=self.registry,
        )
        self.expert_parent_wait = Histogram(
            "eduagent_expert_parent_wait_seconds",
            "Parent wait time for a durable expert terminal decision",
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
            registry=self.registry,
        )
        self.expert_attempt_duration = Histogram(
            "eduagent_expert_attempt_duration_seconds",
            "Expert attempt execution duration",
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
            registry=self.registry,
        )
        self.policy_assignments = Counter(
            "eduagent_policy_assignments_total", "Assignments admitted by this process",
            ("environment", "cohort"), registry=self.registry,
        )
        self.policy_gate_decisions = Counter(
            "eduagent_policy_gate_decisions_total", "Health receipts issued by this process",
            ("gate", "status"), registry=self.registry,
        )
        self.policy_health_decisions = Counter(
            "eduagent_policy_health_decisions_total", "Frozen windows evaluated by this process",
            ("environment", "decision"), registry=self.registry,
        )
        self.policy_rollbacks = Counter(
            "eduagent_policy_rollbacks_total", "Health rollbacks committed by this process",
            ("environment", "trigger"), registry=self.registry,
        )
        self.policy_observation_latency = Histogram(
            "eduagent_policy_observation_latency_seconds", "Terminal observations recorded by this process",
            ("cohort",), registry=self.registry,
        )
        self.policy_observation_cost = Histogram(
            "eduagent_policy_observation_cost_usd", "Known cost observations recorded by this process",
            ("cohort",), registry=self.registry,
        )
        self.policy_assignment_counts = Gauge(
            "eduagent_policy_assignments_persisted", "Authoritative PostgreSQL admitted assignments",
            ("environment", "cohort"), registry=self.registry,
        )
        self.policy_health_counts = Gauge(
            "eduagent_policy_health_windows_persisted", "Authoritative PostgreSQL frozen health windows",
            ("environment", "decision"), registry=self.registry,
        )
        self.policy_gate_counts = Gauge(
            "eduagent_policy_gate_receipts_persisted", "Authoritative PostgreSQL gate receipts",
            ("gate", "status"), registry=self.registry,
        )
        self.policy_rollback_counts = Gauge(
            "eduagent_policy_rollbacks_persisted", "Authoritative PostgreSQL health rollbacks",
            ("environment", "trigger"), registry=self.registry,
        )

    async def refresh_policy_counts(self, session_factory):
        from sqlalchemy import func, select
        from .models import DistributedRun
        from .promotion_contracts import GateType
        from typing import get_args
        from .promotion_models import (
            PolicyAuditEventRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
            PolicyHealthWindowRecord,
        )

        async with session_factory() as session:
            assignments = {(environment, cohort): count for environment, cohort, count in
                (await session.execute(select(
                    PolicyDeploymentRecord.environment, DistributedRun.policy_cohort, func.count()
                ).join(PolicyDeploymentRecord,
                       DistributedRun.deployment_id == PolicyDeploymentRecord.deployment_id)
                 .group_by(PolicyDeploymentRecord.environment, DistributedRun.policy_cohort))).all()}
            windows = {(environment, decision): count for environment, decision, count in
                (await session.execute(select(
                    PolicyDeploymentRecord.environment, PolicyHealthWindowRecord.decision, func.count()
                ).join(PolicyDeploymentRecord,
                       PolicyHealthWindowRecord.deployment_id == PolicyDeploymentRecord.deployment_id)
                 .group_by(PolicyDeploymentRecord.environment, PolicyHealthWindowRecord.decision))).all()}
            gates = {(gate, status): count for gate, status, count in
                (await session.execute(select(
                    PolicyGateReceiptRecord.gate_type, PolicyGateReceiptRecord.status, func.count()
                ).group_by(PolicyGateReceiptRecord.gate_type, PolicyGateReceiptRecord.status))).all()}
            rollbacks = dict((await session.execute(select(
                PolicyAuditEventRecord.environment, func.count()
            ).where(PolicyAuditEventRecord.event_type == "health_rollback")
             .group_by(PolicyAuditEventRecord.environment))).all())
        # 固定标签枚举，数据库中的未知值也不得放大 Prometheus 基数。
        for environment in ("production", "rehearsal"):
            for cohort in ("stable", "candidate", "shadow"):
                self.policy_assignment_counts.labels(environment=environment, cohort=cohort).set(
                    assignments.get((environment, cohort), 0))
            for decision in ("pass", "hold", "fail"):
                self.policy_health_counts.labels(environment=environment, decision=decision).set(
                    windows.get((environment, decision), 0))
            self.policy_rollback_counts.labels(environment=environment, trigger="health_threshold").set(
                rollbacks.get(environment, 0))
        for gate in get_args(GateType):
            for status in ("passed", "failed", "unknown"):
                self.policy_gate_counts.labels(gate=gate, status=status).set(gates.get((gate, status), 0))

    def render(self) -> bytes:
        return generate_latest(self.registry)

    def observe_status_counts(self, counts: dict[str, int]) -> None:
        from .contracts import RunStatus

        for status in RunStatus:
            self.run_states.labels(status=status.value).set(
                counts.get(status.value, 0)
            )
