from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.executor import BusinessStoreBusy
from core.distributed.reaper import LeaseReaper
from core.distributed.worker import RunWorker
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


class RecordingTracer:
    def __init__(self):
        self.calls = []

    @asynccontextmanager
    async def span(
        self,
        run_id,
        trace_id,
        name,
        *,
        parent_span_id=None,
        attributes=None,
    ):
        span = SimpleNamespace(
            span_id=f"span-{len(self.calls) + 1}"
        )
        call = {
            "run_id": run_id,
            "trace_id": trace_id,
            "name": name,
            "span_id": span.span_id,
            "parent_span_id": parent_span_id,
            "attributes": attributes or {},
            "status": "running",
        }
        self.calls.append(call)
        try:
            yield span
        except BaseException:
            call["status"] = "error"
            raise
        else:
            call["status"] = "ok"


class RecordingCounter:
    def __init__(self):
        self.value = 0
        self.labels_seen = []

    def labels(self, **labels):
        self.labels_seen.append(labels)
        return self

    def inc(self):
        self.value += 1


class RecordingGauge:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


class RecordingMetrics:
    def __init__(self):
        self.runs = RecordingCounter()
        self.lease_takeovers = RecordingCounter()
        self.queue_depth = RecordingGauge()
        self.idempotency_hits = RecordingCounter()
        self.fencing_rejections = RecordingCounter()


class ImmediateExecutor:
    async def execute(self, request, authority):
        return {"request_id": request.request_id}


class BusyExecutor:
    async def execute(self, request, authority):
        raise BusinessStoreBusy("business_store_busy")


def worker(repo, broker, executor, tracer, metrics):
    return RunWorker(
        "worker-a",
        repo,
        broker,
        executor,
        lease_seconds=5,
        heartbeat_seconds=0.1,
        max_attempts=3,
        tracer=tracer,
        metrics=metrics,
    )


async def test_runtime_components_emit_spans_and_confirmed_metrics(
    repo,
    broker,
):
    tracer = RecordingTracer()
    metrics = RecordingMetrics()
    dispatcher = OutboxDispatcher(
        repo,
        broker,
        tracer=tracer,
        metrics=metrics,
    )

    completed = await repo.accept(spec(request_id="instrumented-ok"))
    assert await dispatcher.dispatch_once() == 1
    assert await worker(
        repo,
        broker,
        ImmediateExecutor(),
        tracer,
        metrics,
    ).run_once()

    failed = await repo.accept(spec(request_id="instrumented-fail"))
    assert await dispatcher.dispatch_once() == 1
    assert await worker(
        repo,
        broker,
        BusyExecutor(),
        tracer,
        metrics,
    ).run_once()

    requeued = await repo.accept(spec(request_id="instrumented-reap"))
    await repo.claim(requeued.id, "dead-worker", lease_seconds=10)
    await repo.force_lease_expiry(
        requeued.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await LeaseReaper(
        repo,
        tracer=tracer,
        metrics=metrics,
    ).reap_once() == [requeued.id]

    names = [call["name"] for call in tracer.calls]
    assert "outbox.publish" in names
    assert "run.attempt" in names
    assert "business.execute" in names
    assert "run.commit" in names
    assert "lease.reap" in names

    completed_calls = [
        call for call in tracer.calls
        if call["run_id"] == completed.id
    ]
    parent = next(
        call for call in completed_calls
        if call["name"] == "run.attempt"
    )
    children = [
        call for call in completed_calls
        if call["name"] in {"business.execute", "run.commit"}
    ]
    assert {call["parent_span_id"] for call in children} == {
        parent["span_id"]
    }

    assert {"outcome": "completed"} in metrics.runs.labels_seen
    assert {
        "outcome": "retryable_failed"
    } in metrics.runs.labels_seen
    assert metrics.runs.value == 2
    assert metrics.lease_takeovers.value == 1
    assert metrics.queue_depth.values
    assert any(
        call["run_id"] == failed.id
        and call["name"] == "business.execute"
        and call["status"] == "error"
        for call in tracer.calls
    )
