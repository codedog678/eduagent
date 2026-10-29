from prometheus_client import CollectorRegistry

from core.distributed.metrics import DistributedMetrics
from core.distributed.telemetry import DurableTracer
from tests.distributed.helpers import spec


async def test_trace_tree_is_durable_and_sensitive_values_are_redacted(repo):
    run = await repo.accept(spec())
    tracer = DurableTracer(repo)

    async with tracer.span(
        run.id,
        run.trace_id,
        "run.attempt",
        attributes={
            "worker.id": "worker-a",
            "authorization": "secret",
            "nested": {"api_key": "private", "safe": "public"},
        },
    ) as parent:
        async with tracer.span(
            run.id,
            run.trace_id,
            "business.execute",
            parent_span_id=parent.span_id,
            attributes={"request.body": {"question": "private"}},
        ):
            pass

    trace = await repo.trace(run.id)
    assert [span.name for span in trace] == [
        "run.attempt",
        "business.execute",
    ]
    serialized = str([span.attributes for span in trace])
    assert "secret" not in serialized
    assert "private" not in serialized
    assert "public" in serialized


def test_metrics_use_explicit_registries_without_duplicate_registration():
    first = DistributedMetrics(CollectorRegistry())
    second = DistributedMetrics(CollectorRegistry())

    first.idempotency_hits.labels(scope="request").inc()
    second.idempotency_hits.labels(scope="request").inc()

    assert "eduagent_distributed_idempotency_hits_total" in first.render().decode()
    assert "eduagent_distributed_idempotency_hits_total" in second.render().decode()


class BrokenOtelContext:
    def __init__(self, fail_on):
        self.fail_on = fail_on

    def __enter__(self):
        if self.fail_on == "enter":
            raise RuntimeError("collector unavailable")

    def __exit__(self, *_):
        if self.fail_on == "exit":
            raise RuntimeError("collector unavailable")


class BrokenOtelTracer:
    def __init__(self, fail_on):
        self.fail_on = fail_on

    def start_as_current_span(self, *_args, **_kwargs):
        return BrokenOtelContext(self.fail_on)


async def test_otel_failures_do_not_fail_run_or_durable_trace(repo):
    run = await repo.accept(spec(request_id="otel"))

    for fail_on in ("enter", "exit"):
        tracer = DurableTracer(repo, BrokenOtelTracer(fail_on))
        async with tracer.span(
            run.id,
            run.trace_id,
            f"otel.{fail_on}",
        ):
            pass

    trace = await repo.trace(run.id)
    assert [span.status for span in trace] == ["ok", "ok"]
