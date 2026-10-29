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

    def render(self) -> bytes:
        return generate_latest(self.registry)

    def observe_status_counts(self, counts: dict[str, int]) -> None:
        from .contracts import RunStatus

        for status in RunStatus:
            self.run_states.labels(status=status.value).set(
                counts.get(status.value, 0)
            )
