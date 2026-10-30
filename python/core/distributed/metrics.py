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

    def render(self) -> bytes:
        return generate_latest(self.registry)

    def observe_status_counts(self, counts: dict[str, int]) -> None:
        from .contracts import RunStatus

        for status in RunStatus:
            self.run_states.labels(status=status.value).set(
                counts.get(status.value, 0)
            )
