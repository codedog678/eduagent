# M1 Durable Run Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PostgreSQL-authoritative, Redis Streams-delivered Run Plane that executes the existing learning task through two competing worker processes, survives worker death through leases and fencing, exposes durable traces and Prometheus metrics, and proves zero duplicate business effects.

**Architecture:** A dedicated distributed FastAPI control plane accepts immutable run requests and transactionally writes a run plus outbox record to PostgreSQL. Dispatchers publish outbox records to Redis Streams; workers claim runs with monotonic fencing tokens, execute the existing `LearningHarness` using a shared single-writer SQLite store, and conditionally commit results to PostgreSQL. M1 intentionally keeps SQLite business state single-writer while moving run truth, delivery, recovery, and observability to PostgreSQL/Redis; M2 will distribute side-effect-free expert work.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, PostgreSQL 16, Redis Streams, Pydantic v2, OpenTelemetry, Prometheus, pytest, Docker Compose.

---

## Scope Boundary

This plan implements only M1 from the approved design:

- PostgreSQL run/attempt/step/lease/outbox/inbox/span records;
- Redis Streams delivery;
- lease renewal, reaping, fencing, idempotent completion, cancellation;
- a dedicated control-plane API and two worker processes;
- an adapter for the existing `/learning/task` semantics;
- internal trace storage, optional OTLP export, Prometheus metrics;
- deterministic integration and process-kill recovery tests;
- a one-command distributed profile and recovery demonstration.

It does not implement remote specialist workers, the React Ops Console, Judge v3, distributed Campaigns, or policy shadow rollout. Those are M2/M3.

## File Structure

### New runtime package

| File | Responsibility |
| --- | --- |
| `python/core/distributed/contracts.py` | Public enums, Pydantic request/result contracts, canonical hashes |
| `python/core/distributed/models.py` | Seven PostgreSQL ORM tables for runs, attempts, steps, leases, outbox, inbox, spans |
| `python/core/distributed/repository.py` | All transactional state transitions and fencing checks |
| `python/core/distributed/broker.py` | Redis Streams publish, consume, group creation, ack |
| `python/core/distributed/dispatcher.py` | Transactional outbox publication and reconciliation |
| `python/core/distributed/executor.py` | Executor protocol and existing `LearningHarness` adapter |
| `python/core/distributed/telemetry.py` | Durable span lifecycle and optional OTLP bridge |
| `python/core/distributed/metrics.py` | Prometheus counters, gauges, and histograms |
| `python/core/distributed/worker.py` | Claim, heartbeat, execute, fence, retry, ack loop |
| `python/core/distributed/reaper.py` | Expired lease recovery and requeue |
| `python/core/distributed/runtime.py` | Control-plane startup/shutdown ownership |
| `python/core/distributed/cli.py` | `dispatcher`, `worker`, and `reaper` process entry points |
| `python/api/distributed_routes.py` | Submit/status/trace/cancel/metrics endpoints |
| `python/api/distributed_main.py` | Dedicated FastAPI control-plane app without SQLite Harness ownership |

### Tests and evidence

| File | Responsibility |
| --- | --- |
| `python/tests/distributed/test_contracts.py` | Payload validation and stable hashing |
| `python/tests/distributed/test_repository.py` | State machine, leases, fencing, idempotency |
| `python/tests/distributed/test_dispatcher.py` | Outbox duplicate publication and Redis recovery |
| `python/tests/distributed/test_worker.py` | Heartbeat, cancellation, retry taxonomy, stale-token rejection |
| `python/tests/distributed/test_api.py` | 202 submit, conflict, status, trace, cancel, metrics |
| `python/tests/integration/test_distributed_failover.py` | PostgreSQL + Redis + two process failover |
| `tools/demo_distributed_recovery.py` | Repeatable worker-kill demonstration and evidence summary |
| `docs/engineering/distributed-run-plane.md` | Operational contract, commands, boundaries, failure evidence |

### Existing files to modify

- `python/config/settings.py`: distributed profile settings and validation.
- `python/models/__init__.py`: import distributed models before `create_all`.
- `python/models/session.py`: support explicit engine disposal in worker tests.
- `python/pyproject.toml`, `python/requirements.txt`: telemetry and metrics dependencies.
- `python/api/routes.py`: no behavior change; extract shared request contract only if required.
- `.env.example`: documented distributed defaults and warnings.
- `docker-compose.yml`: Redis, distributed API, two workers, shared business-state volume.
- `.github/workflows/ci.yml`: PostgreSQL/Redis integration job.
- `README.md`: distributed profile quick start and honest M1 boundary.

## Task 1: Freeze Contracts, Settings, and Dependencies

**Files:**
- Create: `python/core/distributed/__init__.py`
- Create: `python/core/distributed/contracts.py`
- Create: `python/tests/distributed/__init__.py`
- Create: `python/tests/distributed/test_contracts.py`
- Modify: `python/config/settings.py`
- Modify: `python/pyproject.toml`
- Modify: `python/requirements.txt`

- [ ] **Step 1: Write contract tests**

```python
# python/tests/distributed/test_contracts.py
import pytest
from pydantic import ValidationError

from core.distributed.contracts import (
    DistributedRunRequest,
    RunOperation,
    RunStatus,
    canonical_hash,
)


def request(**updates):
    value = {
        "learner_id": "student-1",
        "request_id": "request-1",
        "operation": RunOperation.LEARNING_TASK,
        "payload": {
            "learner_id": "student-1",
            "request_id": "request-1",
            "knowledge_id": "grammar_tenses",
            "question": "安排十分钟复习",
        },
    }
    value.update(updates)
    return DistributedRunRequest.model_validate(value)


def test_canonical_hash_ignores_mapping_order():
    left = canonical_hash({"b": 2, "a": {"y": 1, "x": 0}})
    right = canonical_hash({"a": {"x": 0, "y": 1}, "b": 2})
    assert left == right


def test_learning_task_scope_must_match_envelope():
    with pytest.raises(ValidationError, match="payload learner_id"):
        request(payload={
            "learner_id": "other",
            "request_id": "request-1",
            "knowledge_id": "grammar_tenses",
            "question": "安排复习",
        })


def test_terminal_statuses_are_explicit():
    assert RunStatus.COMPLETED.terminal
    assert RunStatus.CANCELLED.terminal
    assert not RunStatus.RUNNING.terminal
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd python
python -m pytest tests/distributed/test_contracts.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'core.distributed'`.

- [ ] **Step 3: Add the contracts**

```python
# python/core/distributed/contracts.py
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunOperation(StrEnum):
    LEARNING_TASK = "learning_task"


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    COMMITTING = "committing"
    RETRYABLE_FAILED = "retryable_failed"
    COMPLETED = "completed"
    TERMINAL_FAILED = "terminal_failed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.TERMINAL_FAILED,
            self.EXHAUSTED,
            self.CANCELLED,
        }


def canonical_hash(value: Any) -> str:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class DistributedRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    operation: RunOperation
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_scope(self):
        if self.payload.get("learner_id") != self.learner_id:
            raise ValueError("payload learner_id must match envelope")
        if self.payload.get("request_id") != self.request_id:
            raise ValueError("payload request_id must match envelope")
        if self.operation == RunOperation.LEARNING_TASK:
            for name in ("knowledge_id", "question"):
                if not str(self.payload.get(name, "")).strip():
                    raise ValueError(f"payload {name} is required")
        return self

    @property
    def input_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))
```

`python/core/distributed/__init__.py` exports only contracts:

```python
from .contracts import DistributedRunRequest, RunOperation, RunStatus

__all__ = ["DistributedRunRequest", "RunOperation", "RunStatus"]
```

- [ ] **Step 4: Add distributed settings**

Add these fields to `Settings`:

```python
    distributed_enabled: bool = False
    distributed_database_url: str = ""
    distributed_redis_url: str = "redis://localhost:6379/1"
    distributed_stream: str = "eduagent:runs"
    distributed_consumer_group: str = "eduagent-run-workers"
    distributed_worker_id: str = ""
    distributed_lease_seconds: float = Field(default=15, ge=3, le=300)
    distributed_heartbeat_seconds: float = Field(default=3, ge=.5, le=60)
    distributed_poll_block_ms: int = Field(default=1000, ge=10, le=60000)
    distributed_max_attempts: int = Field(default=3, ge=1, le=20)
    distributed_outbox_batch_size: int = Field(default=50, ge=1, le=500)
    distributed_demo_pause_before_commit_seconds: float = Field(default=0, ge=0, le=300)
    otel_exporter_otlp_endpoint: str = ""
```

Extend the model validator:

```python
        if self.distributed_enabled:
            if not (self.distributed_database_url or self.database_url):
                raise ValueError("distributed database URL is required")
            if self.distributed_heartbeat_seconds >= self.distributed_lease_seconds / 2:
                raise ValueError(
                    "DISTRIBUTED_HEARTBEAT_SECONDS must be less than half the lease"
                )
        return self
```

Add a property:

```python
    @property
    def effective_distributed_database_url(self) -> str:
        return self.distributed_database_url or self.database_url
```

- [ ] **Step 5: Add dependencies**

Add to both `python/pyproject.toml` and `python/requirements.txt`:

```text
opentelemetry-api>=1.38.0
opentelemetry-sdk>=1.38.0
opentelemetry-exporter-otlp-proto-http>=1.38.0
prometheus-client>=0.23.1
```

Keep the existing `redis>=7.4.0` dependency.

- [ ] **Step 6: Install and run tests**

Run:

```bash
python -m pip install -e "./python[dev]"
cd python
python -m pytest tests/distributed/test_contracts.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add python/core/distributed python/tests/distributed \
  python/config/settings.py python/pyproject.toml python/requirements.txt
git commit -m "feat(distributed): define durable run contracts"
```

## Task 2: Add PostgreSQL Models and Transactional Repository

**Files:**
- Create: `python/core/distributed/models.py`
- Create: `python/core/distributed/repository.py`
- Create: `python/tests/distributed/conftest.py`
- Create: `python/tests/distributed/helpers.py`
- Create: `python/tests/distributed/test_repository.py`
- Modify: `python/models/__init__.py`
- Modify: `python/models/session.py`

- [ ] **Step 1: Write repository state-machine tests**

The fixture uses a PostgreSQL URL only when explicitly provided, so normal unit runs remain offline:

```python
# python/tests/distributed/conftest.py
import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.distributed.models import DistributedBase
from core.distributed.repository import DistributedRunRepository


@pytest_asyncio.fixture
async def repo():
    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(DistributedBase.metadata.drop_all)
        await conn.run_sync(DistributedBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield DistributedRunRepository(factory)
    await engine.dispose()
```

```python
# python/tests/distributed/helpers.py
from core.distributed.contracts import DistributedRunRequest, RunOperation


def spec(request_id="r1", question="复习"):
    return DistributedRunRequest(
        learner_id="student",
        request_id=request_id,
        operation=RunOperation.LEARNING_TASK,
        payload={
            "learner_id": "student",
            "request_id": request_id,
            "knowledge_id": "grammar_tenses",
            "question": question,
        },
    )
```

```python
# python/tests/distributed/test_repository.py
from datetime import UTC, datetime, timedelta

import pytest

from core.distributed.contracts import RunStatus
from core.distributed.repository import FencingViolation, RequestConflict
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


async def test_accept_is_idempotent_and_conflicting_payload_is_rejected(repo):
    first = await repo.accept(spec())
    replay = await repo.accept(spec())
    assert first.id == replay.id
    with pytest.raises(RequestConflict):
        await repo.accept(spec(question="不同内容"))


async def test_expired_lease_increments_fencing_and_rejects_old_owner(repo):
    run = await repo.accept(spec())
    first = await repo.claim(run.id, "worker-a", lease_seconds=1)
    await repo.force_lease_expiry(run.id, datetime.now(UTC) - timedelta(seconds=1))
    await repo.requeue_expired(now=datetime.now(UTC))
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    assert second.fencing_token == first.fencing_token + 1
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, first.fencing_token, {"owner": "a"})
    await repo.transition_committing(run.id, second.fencing_token)
    completed = await repo.complete(run.id, second.fencing_token, {"owner": "b"})
    assert completed.status == RunStatus.COMPLETED


async def test_step_result_is_reused_only_for_same_input_hash(repo):
    run = await repo.accept(spec())
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    first = await repo.complete_step(
        run.id, "business-execution", "hash-a", claim.fencing_token, {"ok": True}
    )
    replay = await repo.complete_step(
        run.id, "business-execution", "hash-a", claim.fencing_token, {"ok": True}
    )
    assert replay.id == first.id
    with pytest.raises(RequestConflict):
        await repo.start_step(
            run.id, "business-execution", "hash-b", claim.fencing_token
        )
```

- [ ] **Step 2: Run the repository tests and verify failure**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
  python -m pytest tests/distributed/test_repository.py -q
```

Expected: collection fails because models and repository do not exist.

- [ ] **Step 3: Define focused ORM models**

Use a separate metadata object so integration tests can create/drop only M1 tables:

```python
# python/core/distributed/models.py
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DistributedBase(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid4())


class DistributedRun(DistributedBase):
    __tablename__ = "distributed_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    learner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("learner_id", "request_id", name="uq_distributed_request"),
        Index("ix_distributed_run_status_updated", "status", "updated_at"),
    )

    def public_dict(self) -> dict:
        return {
            "run_id": self.id,
            "learner_id": self.learner_id,
            "request_id": self.request_id,
            "operation": self.operation,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "result": self.result,
            "error_code": self.error_code,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DistributedRunAttempt(DistributedBase):
    __tablename__ = "distributed_run_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("distributed_runs.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("run_id", "number", name="uq_distributed_attempt_number"),
    )


class DistributedStep(DistributedBase):
    __tablename__ = "distributed_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("distributed_runs.id"), nullable=False)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("run_id", "step_id", name="uq_distributed_step"),
    )


class DistributedLease(DistributedBase):
    __tablename__ = "distributed_leases"
    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"), primary_key=True
    )
    owner: Mapped[str | None] = mapped_column(String(128))
    fencing_token: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DistributedOutbox(DistributedBase):
    __tablename__ = "distributed_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DistributedInbox(DistributedBase):
    __tablename__ = "distributed_inbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    consumer: Mapped[str] = mapped_column(String(128), nullable=False)
    message_key: Mapped[str] = mapped_column(String(180), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("consumer", "message_key", name="uq_distributed_inbox"),
    )


class DistributedTraceSpan(DistributedBase):
    __tablename__ = "distributed_trace_spans"
    span_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(32))
    run_id: Mapped[str] = mapped_column(ForeignKey("distributed_runs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_distributed_trace", "trace_id", "started_at"),)

    def public_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "status": self.status,
            "attributes": self.attributes,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
```

- [ ] **Step 4: Implement repository transitions**

`DistributedRunRepository` must expose these exact methods:

```python
class RequestConflict(RuntimeError):
    pass


class FencingViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class RunClaim:
    run_id: str
    learner_id: str
    request_id: str
    operation: str
    payload: dict
    input_hash: str
    trace_id: str
    attempt_count: int
    fencing_token: int

    def to_request(self) -> DistributedRunRequest:
        return DistributedRunRequest(
            learner_id=self.learner_id,
            request_id=self.request_id,
            operation=self.operation,
            payload=self.payload,
        )


```

Implement `DistributedRunRepository(session_factory, clock)` with this exact public surface:

| Method | Return | Transaction rule |
| --- | --- | --- |
| `accept(spec)` | `DistributedRun` | insert run, lease and accepted outbox together; matching conflict replays |
| `get(run_id)` | `DistributedRun \| None` | read only |
| `get_by_request(learner_id, request_id)` | `DistributedRun \| None` | read only |
| `claim(run_id, worker_id, lease_seconds)` | `RunClaim` | lock run+lease, increment attempt and token |
| `renew(run_id, worker_id, token, lease_seconds)` | `DistributedLease` | owner+token conditional update |
| `lease(run_id)` | `DistributedLease` | read only, used by diagnostics |
| `start_step(run_id, step_id, input_hash, token)` | `DistributedStep` | same hash replays; different hash conflicts |
| `complete_step(run_id, step_id, input_hash, token, result)` | `DistributedStep` | current token only |
| `transition_committing(run_id, token)` | `DistributedRun` | running to committing, current token only |
| `complete(run_id, token, result)` | `DistributedRun` | committing to completed, current token only |
| `fail(run_id, token, code, retryable)` | `DistributedRun` | finish attempt and either outbox a retry or terminate |
| `cancel(run_id)` | `DistributedRun` | idempotent terminal transition |
| `pending_outbox(limit)` | `list[DistributedOutbox]` | lock with `skip_locked=True` |
| `mark_outbox_published(outbox_id, event_key)` | `None` | key must match locked row |
| `record_inbox(consumer, message_key)` | `bool` | uniqueness conflict returns false |
| `requeue_expired(now)` | `list[str]` | lock expired leases, finish attempts, write outboxes |
| `force_lease_expiry(run_id, at)` | `None` | test helper, located behind `_for_tests` naming |
| `start_span(run_id, trace_id, span_id, parent_span_id, name, attributes)`, `finish_span(span_id, status, attributes)`, `trace(run_id)` | span objects | durable trace lifecycle |

Every mutating method follows this transaction pattern:

```python
async with self.session_factory() as session, session.begin():
    run = await session.scalar(
        select(DistributedRun).where(DistributedRun.id == run_id).with_for_update()
    )
    lease = await session.scalar(
        select(DistributedLease)
        .where(DistributedLease.run_id == run_id)
        .with_for_update()
    )
    if lease.fencing_token != token:
        raise FencingViolation(f"stale fencing token for run {run_id}")
    # Apply one legal state transition and write attempt/outbox in this transaction.
```

`accept()` writes `DistributedRun`, `DistributedLease`, and an outbox event in one transaction. On uniqueness conflict it reloads the existing run, returns it only when `input_hash` matches, and otherwise raises `RequestConflict`.

`claim()` only accepts `accepted`, `queued`, or `retryable_failed`; increments `attempt_count` and `fencing_token`; writes an attempt; and moves the run to `running`.

`complete()` uses:

```python
updated = await session.execute(
    update(DistributedRun)
    .where(
        DistributedRun.id == run_id,
        DistributedRun.status == RunStatus.COMMITTING,
        exists().where(
            DistributedLease.run_id == run_id,
            DistributedLease.fencing_token == token,
        ),
    )
    .values(
        status=RunStatus.COMPLETED,
        result=result,
        updated_at=self.clock(),
    )
)
if updated.rowcount != 1:
    raise FencingViolation(f"run {run_id} cannot be completed by token {token}")
```

- [ ] **Step 5: Register metadata and explicit session reset**

Import the models in `python/models/__init__.py`:

```python
from core.distributed.models import DistributedBase
```

Add to `python/models/session.py`:

```python
async def reset_db_for_tests() -> None:
    """Dispose cached global engine/factory; tests only."""
    await close_db()
```

The distributed control plane uses its own engine/factory and does not reuse the business ORM globals.

- [ ] **Step 6: Run repository tests**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
  python -m pytest tests/distributed/test_repository.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add python/core/distributed/models.py python/core/distributed/repository.py \
  python/tests/distributed/test_repository.py python/models
git commit -m "feat(distributed): persist run state with fencing"
```

## Task 3: Add Redis Streams and Transactional Outbox Dispatch

**Files:**
- Create: `python/core/distributed/broker.py`
- Create: `python/core/distributed/dispatcher.py`
- Create: `python/tests/distributed/test_dispatcher.py`
- Modify: `python/tests/distributed/conftest.py`

- [ ] **Step 1: Write duplicate-delivery and recovery tests**

```python
# python/tests/distributed/test_dispatcher.py
import os
import pytest
from redis.asyncio import Redis

from core.distributed.broker import RedisRunBroker
from core.distributed.dispatcher import OutboxDispatcher
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


@pytest.fixture
def redis_url():
    value = os.getenv("DISTRIBUTED_TEST_REDIS_URL")
    if not value:
        pytest.skip("DISTRIBUTED_TEST_REDIS_URL is not configured")
    return value


@pytest.fixture
async def broker(redis_url):
    value = RedisRunBroker(
        Redis.from_url(redis_url, decode_responses=True),
        "test:runs",
        "test-workers",
    )
    await value.reset_for_tests()
    yield value
    await value.redis.aclose()


async def test_dispatch_republishes_safely(repo, redis_url):
    run = await repo.accept(spec())
    broker = RedisRunBroker(Redis.from_url(redis_url), "test:runs", "test-workers")
    dispatcher = OutboxDispatcher(repo, broker, batch_size=10)
    await broker.reset_for_tests()
    await dispatcher.dispatch_once()
    await dispatcher.dispatch_once()
    messages = await broker.read("consumer-a", count=10, block_ms=10)
    assert [item.event_key for item in messages] == [f"run:{run.id}:accepted"]


async def test_unmarked_publish_can_be_republished_without_duplicate_effect(repo, redis_url):
    run = await repo.accept(spec(request_id="r2"))
    broker = RedisRunBroker(Redis.from_url(redis_url), "test:runs", "test-workers")
    row = (await repo.pending_outbox(1))[0]
    await broker.publish(row.event_key, row.payload)
    await broker.publish(row.event_key, row.payload)
    messages = await broker.read("consumer-b", count=10, block_ms=10)
    assert len(messages) == 2
    assert {item.event_key for item in messages} == {f"run:{run.id}:accepted"}
```

- [ ] **Step 2: Implement the broker**

```python
# python/core/distributed/broker.py
from dataclasses import dataclass
import json

from redis.asyncio import Redis
from redis.exceptions import ResponseError


@dataclass(frozen=True)
class RunMessage:
    redis_id: str
    event_key: str
    payload: dict


class RedisRunBroker:
    def __init__(self, redis: Redis, stream: str, group: str):
        self.redis = redis
        self.stream = stream
        self.group = group

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.stream, self.group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event_key: str, payload: dict) -> str:
        return await self.redis.xadd(
            self.stream,
            {"event_key": event_key, "payload": json.dumps(payload)},
        )

    async def read(self, consumer: str, count: int, block_ms: int) -> list[RunMessage]:
        await self.ensure_group()
        rows = await self.redis.xreadgroup(
            self.group, consumer, {self.stream: ">"}, count=count, block=block_ms
        )
        return [
            RunMessage(message_id, fields["event_key"], json.loads(fields["payload"]))
            for _, messages in rows
            for message_id, fields in messages
        ]

    async def ack(self, redis_id: str) -> None:
        await self.redis.xack(self.stream, self.group, redis_id)
```

Set `decode_responses=True` when constructing Redis clients.

- [ ] **Step 3: Implement one outbox dispatch pass**

```python
# python/core/distributed/dispatcher.py
class OutboxDispatcher:
    def __init__(self, repository, broker, batch_size=50):
        self.repository = repository
        self.broker = broker
        self.batch_size = batch_size

    async def dispatch_once(self) -> int:
        rows = await self.repository.pending_outbox(self.batch_size)
        published = 0
        for row in rows:
            await self.broker.publish(row.event_key, row.payload)
            await self.repository.mark_outbox_published(row.id, row.event_key)
            published += 1
        return published
```

Do not deduplicate in Redis. Duplicate delivery is intentional and is resolved by inbox/run state in PostgreSQL.

- [ ] **Step 4: Run tests**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
  python -m pytest tests/distributed/test_dispatcher.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add python/core/distributed/broker.py python/core/distributed/dispatcher.py \
  python/tests/distributed/test_dispatcher.py
git commit -m "feat(distributed): dispatch transactional outbox"
```

## Task 4: Adapt the Existing Learning Harness to a Worker Executor

**Files:**
- Create: `python/core/distributed/executor.py`
- Create: `python/tests/distributed/test_executor.py`

- [ ] **Step 1: Write an executor replay test**

```python
# python/tests/distributed/test_executor.py
from core.distributed.contracts import DistributedRunRequest, RunOperation
from core.distributed.executor import LearningTaskExecutor


async def test_executor_reuses_existing_harness_request(tmp_path, monkeypatch):
    executor = LearningTaskExecutor(store_path=str(tmp_path / "shared.sqlite3"))
    run = DistributedRunRequest(
        learner_id="student",
        request_id="same-request",
        operation=RunOperation.LEARNING_TASK,
        payload={
            "learner_id": "student",
            "request_id": "same-request",
            "knowledge_id": "grammar_tenses",
            "question": "安排十分钟复习",
        },
    )
    first = await executor.execute(run)
    second = await executor.execute(run)
    assert second == first
    assert first["execution"]["request_id"] == "same-request"
```

- [ ] **Step 2: Implement the executor protocol**

```python
# python/core/distributed/executor.py
from typing import Protocol

from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.distributed.contracts import DistributedRunRequest, RunOperation
from core.harness import LearningHarness


class RunExecutor(Protocol):
    async def execute(self, spec: DistributedRunRequest) -> dict:
        """Execute one frozen distributed run request."""


class LearningTaskExecutor:
    def __init__(self, store_path: str, enable_db_logging: bool = False):
        self.store_path = store_path
        self.enable_db_logging = enable_db_logging

    async def execute(self, spec: DistributedRunRequest) -> dict:
        if spec.operation != RunOperation.LEARNING_TASK:
            raise ValueError(f"unsupported operation: {spec.operation}")
        orchestrator = AgentOrchestrator(enable_db_logging=self.enable_db_logging)
        harness = LearningHarness(
            orchestrator,
            self.store_path,
            settings.harness_timeout_seconds,
            settings.quiz_ttl_seconds,
        )
        orchestrator.harness = harness
        try:
            payload = spec.payload
            return await harness.converse(
                spec.learner_id,
                spec.request_id,
                payload["knowledge_id"],
                payload["question"],
                payload.get("session_id"),
                payload.get("thread_id"),
                payload.get("quiz_id"),
                kind="task",
            )
        finally:
            await harness.memory_worker.stop()
            harness.close()
            await orchestrator.close_database()
```

The executor opens the current SQLite Harness only while holding a valid distributed lease. This preserves current transaction semantics and makes file-lock release automatic when a worker dies.

- [ ] **Step 3: Add explicit lock contention classification**

Wrap harness construction:

```python
class BusinessStoreBusy(RuntimeError):
    pass


try:
    harness = LearningHarness(
        orchestrator,
        self.store_path,
        settings.harness_timeout_seconds,
        settings.quiz_ttl_seconds,
    )
except RuntimeError as exc:
    if "already owned" in str(exc):
        raise BusinessStoreBusy("business_store_busy") from exc
    raise
```

The worker treats `BusinessStoreBusy` as retryable. Validation, permission, and budget exhaustion are not retried blindly.

- [ ] **Step 4: Run the executor test**

Run:

```bash
cd python
LLM_PROVIDER=template MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m pytest tests/distributed/test_executor.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add python/core/distributed/executor.py python/tests/distributed/test_executor.py
git commit -m "feat(distributed): execute learning tasks in workers"
```

## Task 5: Implement Worker Heartbeats, Fencing, and Reaping

**Files:**
- Create: `python/core/distributed/worker.py`
- Create: `python/core/distributed/reaper.py`
- Create: `python/tests/distributed/test_worker.py`

- [ ] **Step 1: Write worker behavior tests**

```python
# python/tests/distributed/test_worker.py
import asyncio
import pytest

from core.distributed.worker import RunWorker
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.reaper import LeaseReaper
from core.distributed.repository import FencingViolation
from tests.distributed.helpers import spec


class BlockingExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def execute(self, spec):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return {"ok": True}


async def test_worker_renews_lease_while_executor_runs(repo, broker):
    run = await repo.accept(spec())
    await OutboxDispatcher(repo, broker).dispatch_once()
    executor = BlockingExecutor()
    worker = RunWorker(
        "worker-a", repo, broker, executor,
        lease_seconds=2, heartbeat_seconds=.25, max_attempts=3,
    )
    task = asyncio.create_task(worker.run_once())
    await executor.started.wait()
    first = await repo.lease(run.id)
    await asyncio.sleep(.6)
    second = await repo.lease(run.id)
    assert second.expires_at > first.expires_at
    executor.release.set()
    await task


async def test_stale_worker_cannot_commit_after_reap(repo, broker):
    run = await repo.accept(spec(request_id="stale"))
    first = await repo.claim(run.id, "worker-a", lease_seconds=.1)
    await asyncio.sleep(.2)
    await LeaseReaper(repo).reap_once()
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, first.fencing_token, {"owner": "a"})
    await repo.transition_committing(run.id, second.fencing_token)
    await repo.complete(run.id, second.fencing_token, {"owner": "b"})
```

- [ ] **Step 2: Implement the lease reaper**

```python
# python/core/distributed/reaper.py
from datetime import UTC, datetime


class LeaseReaper:
    def __init__(self, repository):
        self.repository = repository

    async def reap_once(self) -> list[str]:
        return await self.repository.requeue_expired(datetime.now(UTC))
```

`requeue_expired()` atomically marks the active attempt `retryable_failed`, sets the run `queued`, clears owner/expiry, and writes a new outbox event.

- [ ] **Step 3: Implement one worker delivery**

```python
# python/core/distributed/worker.py
import asyncio
from contextlib import suppress

from core.distributed.executor import BusinessStoreBusy


class RunWorker:
    def __init__(
        self, worker_id, repository, broker, executor, *,
        lease_seconds, heartbeat_seconds, max_attempts,
        pause_before_commit_seconds=0,
    ):
        self.worker_id = worker_id
        self.repository = repository
        self.broker = broker
        self.executor = executor
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.max_attempts = max_attempts
        self.pause_before_commit_seconds = pause_before_commit_seconds

    async def _heartbeat(self, run_id, token):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self.repository.renew(
                run_id, self.worker_id, token, self.lease_seconds
            )

    async def handle(self, message):
        if not await self.repository.record_inbox(self.worker_id, message.redis_id):
            await self.broker.ack(message.redis_id)
            return
        run_id = message.payload["run_id"]
        claim = await self.repository.claim(
            run_id, self.worker_id, self.lease_seconds
        )
        heartbeat = asyncio.create_task(
            self._heartbeat(run_id, claim.fencing_token)
        )
        try:
            spec = claim.to_request()
            step_hash = spec.input_hash
            cached = await self.repository.start_step(
                run_id, "business-execution", step_hash, claim.fencing_token
            )
            result = cached.result if cached.status == "completed" else (
                await self.executor.execute(spec)
            )
            await self.repository.complete_step(
                run_id, "business-execution", step_hash,
                claim.fencing_token, result,
            )
            await self.repository.transition_committing(
                run_id, claim.fencing_token
            )
            if self.pause_before_commit_seconds:
                await asyncio.sleep(self.pause_before_commit_seconds)
            await self.repository.complete(run_id, claim.fencing_token, result)
            await self.broker.ack(message.redis_id)
        except BusinessStoreBusy:
            await self.repository.fail(
                run_id, claim.fencing_token, "business_store_busy", retryable=True
            )
            await self.broker.ack(message.redis_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.repository.fail(
                run_id, claim.fencing_token, type(exc).__name__,
                retryable=claim.attempt_count < self.max_attempts,
            )
            await self.broker.ack(message.redis_id)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def run_once(self):
        messages = await self.broker.read(self.worker_id, count=1, block_ms=100)
        if messages:
            await self.handle(messages[0])
```

If `renew()` raises `FencingViolation`, heartbeat cancellation must cancel the execution task and prevent completion. Add a shared `lease_lost` event and check it before every state mutation.

- [ ] **Step 4: Run worker tests**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
  python -m pytest tests/distributed/test_worker.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add python/core/distributed/worker.py python/core/distributed/reaper.py \
  python/tests/distributed/test_worker.py
git commit -m "feat(distributed): recover leased runs across workers"
```

## Task 6: Add Durable Traces and Prometheus Metrics

**Files:**
- Create: `python/core/distributed/telemetry.py`
- Create: `python/core/distributed/metrics.py`
- Create: `python/tests/distributed/test_telemetry.py`
- Modify: `python/core/distributed/dispatcher.py`
- Modify: `python/core/distributed/worker.py`
- Modify: `python/core/distributed/reaper.py`

- [ ] **Step 1: Write redaction and span-tree tests**

```python
# python/tests/distributed/test_telemetry.py
from core.distributed.telemetry import DurableTracer


async def test_trace_tree_is_durable_and_sensitive_values_are_redacted(repo):
    run = await repo.accept(spec())
    tracer = DurableTracer(repo)
    async with tracer.span(
        run.id, run.trace_id, "run_attempt",
        attributes={"worker.id": "worker-a", "authorization": "secret"},
    ) as parent:
        async with tracer.span(
            run.id, run.trace_id, "business_execution",
            parent_span_id=parent.span_id,
            attributes={"request.body": "private"},
        ):
            pass
    trace = await repo.trace(run.id)
    assert [span.name for span in trace] == ["run_attempt", "business_execution"]
    serialized = str([span.attributes for span in trace])
    assert "secret" not in serialized
    assert "private" not in serialized
```

- [ ] **Step 2: Implement durable span lifecycle**

```python
# python/core/distributed/telemetry.py
from contextlib import asynccontextmanager
from secrets import token_hex

SENSITIVE_KEYS = {
    "authorization", "api_key", "request.body", "response.body",
    "reasoning_content",
}


def public_attributes(value):
    return {
        key: ("[redacted]" if key.lower() in SENSITIVE_KEYS else item)
        for key, item in value.items()
    }


class DurableTracer:
    def __init__(self, repository, otel_tracer=None):
        self.repository = repository
        self.otel_tracer = otel_tracer

    @asynccontextmanager
    async def span(
        self, run_id, trace_id, name, *,
        parent_span_id=None, attributes=None,
    ):
        span = await self.repository.start_span(
            run_id=run_id,
            trace_id=trace_id,
            span_id=token_hex(8),
            parent_span_id=parent_span_id,
            name=name,
            attributes=public_attributes(attributes or {}),
        )
        try:
            yield span
        except BaseException as exc:
            await self.repository.finish_span(
                span.span_id, "error", {"error.type": type(exc).__name__}
            )
            raise
        else:
            await self.repository.finish_span(span.span_id, "ok", {})
```

Configure OpenTelemetry only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Failure to export must never fail a run; durable PostgreSQL spans remain authoritative.

- [ ] **Step 3: Define stable Prometheus instruments**

```python
# python/core/distributed/metrics.py
from prometheus_client import Counter, Gauge, Histogram

RUNS = Counter(
    "eduagent_distributed_runs_total",
    "Distributed runs by terminal outcome",
    ("outcome",),
)
LEASE_TAKEOVERS = Counter(
    "eduagent_distributed_lease_takeovers_total",
    "Expired lease takeovers",
)
IDEMPOTENCY_HITS = Counter(
    "eduagent_distributed_idempotency_hits_total",
    "Request or step replay hits",
    ("scope",),
)
FENCING_REJECTIONS = Counter(
    "eduagent_distributed_fencing_rejections_total",
    "Writes rejected because the fencing token was stale",
)
QUEUE_DEPTH = Gauge(
    "eduagent_distributed_queue_depth",
    "Redis stream pending depth",
)
RUN_LATENCY = Histogram(
    "eduagent_distributed_run_latency_seconds",
    "Accepted-to-terminal latency",
    buckets=(.1, .25, .5, 1, 2, 5, 10, 30, 60),
)
RECOVERY_LATENCY = Histogram(
    "eduagent_distributed_recovery_latency_seconds",
    "Lease expiry to successful reclaim",
    buckets=(.1, .25, .5, 1, 2, 5, 10, 30),
)
```

Increment metrics at repository-confirmed transitions, not before database commits.

- [ ] **Step 4: Instrument dispatcher, worker, and reaper**

Use span names and attributes:

```text
outbox.publish       messaging.system=redis
run.attempt          worker.id, run.attempt, run.fencing_token
lease.heartbeat      worker.id
business.execute     run.operation
run.commit           run.fencing_token
lease.reap           previous_worker.id
```

Do not attach prompts, model responses, tool payloads, learner names, or secrets.

- [ ] **Step 5: Run telemetry tests**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
  python -m pytest tests/distributed/test_telemetry.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add python/core/distributed/telemetry.py python/core/distributed/metrics.py \
  python/core/distributed/dispatcher.py python/core/distributed/worker.py \
  python/core/distributed/reaper.py python/tests/distributed/test_telemetry.py
git commit -m "feat(distributed): persist traces and export metrics"
```

## Task 7: Add the Dedicated Control-Plane API

**Files:**
- Create: `python/api/distributed_routes.py`
- Create: `python/api/distributed_main.py`
- Create: `python/core/distributed/runtime.py`
- Create: `python/tests/distributed/test_api.py`

- [ ] **Step 1: Write API tests**

```python
# python/tests/distributed/test_api.py
from httpx import ASGITransport, AsyncClient


async def test_submit_returns_202_and_replay_returns_same_run(distributed_app):
    payload = {
        "learner_id": "student",
        "request_id": "api-1",
        "operation": "learning_task",
        "payload": {
            "learner_id": "student",
            "request_id": "api-1",
            "knowledge_id": "grammar_tenses",
            "question": "安排十分钟复习",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=distributed_app), base_url="http://test"
    ) as client:
        first = await client.post("/api/distributed/runs", json=payload)
        second = await client.post("/api/distributed/runs", json=payload)
        assert first.status_code == second.status_code == 202
        assert first.json()["run_id"] == second.json()["run_id"]
        status = await client.get(first.json()["status_url"])
        assert status.json()["status"] in {"accepted", "queued"}


async def test_conflicting_request_id_returns_409(distributed_client):
    first = run_payload("api-conflict", question="问题一")
    second = run_payload("api-conflict", question="问题二")
    assert (await distributed_client.post("/api/distributed/runs", json=first)).status_code == 202
    response = await distributed_client.post("/api/distributed/runs", json=second)
    assert response.status_code == 409


async def test_cancel_is_idempotent_and_metrics_are_exposed(distributed_client):
    created = await distributed_client.post(
        "/api/distributed/runs", json=run_payload("cancel")
    )
    run_id = created.json()["run_id"]
    assert (await distributed_client.post(
        f"/api/distributed/runs/{run_id}/cancel"
    )).status_code == 200
    assert (await distributed_client.post(
        f"/api/distributed/runs/{run_id}/cancel"
    )).status_code == 200
    metrics = await distributed_client.get("/metrics")
    assert "eduagent_distributed_runs_total" in metrics.text
```

- [ ] **Step 2: Implement API routes**

```python
# python/api/distributed_routes.py
from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from core.distributed.contracts import DistributedRunRequest
from core.distributed.repository import RequestConflict

router = APIRouter()


@router.post("/distributed/runs", status_code=status.HTTP_202_ACCEPTED)
async def submit_run(spec: DistributedRunRequest, request: Request):
    try:
        run = await request.app.state.distributed.repository.accept(spec)
    except RequestConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "run_id": run.id,
        "status": run.status,
        "status_url": f"/api/distributed/runs/{run.id}",
        "trace_url": f"/api/distributed/runs/{run.id}/trace",
    }


@router.get("/distributed/runs/{run_id}")
async def run_status(run_id: str, request: Request):
    run = await request.app.state.distributed.repository.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run.public_dict()


@router.get("/distributed/runs/{run_id}/trace")
async def run_trace(run_id: str, request: Request):
    return {"run_id": run_id, "spans": [
        span.public_dict()
        for span in await request.app.state.distributed.repository.trace(run_id)
    ]}


@router.post("/distributed/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request):
    return (await request.app.state.distributed.repository.cancel(run_id)).public_dict()


@router.get("/health")
async def health(request: Request):
    return await request.app.state.distributed.health()


@router.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

- [ ] **Step 3: Implement runtime ownership**

```python
# python/core/distributed/runtime.py
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from config.settings import settings
from core.distributed.broker import RedisRunBroker
from core.distributed.dispatcher import OutboxDispatcher
from core.distributed.models import DistributedBase
from core.distributed.reaper import LeaseReaper
from core.distributed.repository import DistributedRunRepository
from core.distributed.worker import RunWorker


class DistributedRuntime:
    def __init__(self, engine, session_factory, repository, broker):
        self.engine = engine
        self.session_factory = session_factory
        self.repository = repository
        self.broker = broker

    async def start(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(DistributedBase.metadata.create_all)
        await self.broker.ensure_group()

    async def close(self):
        await self.broker.redis.aclose()
        await self.engine.dispose()

    async def health(self):
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "mode": "distributed-control-plane",
            "postgres": "ok",
            "redis": "ok" if await self.broker.redis.ping() else "error",
        }

    def dispatcher(self):
        return OutboxDispatcher(
            self.repository, self.broker, settings.distributed_outbox_batch_size
        )

    def reaper(self):
        return LeaseReaper(self.repository)

    def worker(self, worker_id, executor):
        return RunWorker(
            worker_id,
            self.repository,
            self.broker,
            executor,
            lease_seconds=settings.distributed_lease_seconds,
            heartbeat_seconds=settings.distributed_heartbeat_seconds,
            max_attempts=settings.distributed_max_attempts,
            pause_before_commit_seconds=(
                settings.distributed_demo_pause_before_commit_seconds
            ),
        )


def build_runtime():
    engine = create_async_engine(
        settings.effective_distributed_database_url,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = DistributedRunRepository(factory)
    broker = RedisRunBroker(
        Redis.from_url(settings.distributed_redis_url, decode_responses=True),
        settings.distributed_stream,
        settings.distributed_consumer_group,
    )
    return DistributedRuntime(engine, factory, repository, broker)
```

- [ ] **Step 4: Create a control-plane-only FastAPI app**

```python
# python/api/distributed_main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.distributed_routes import router
from core.distributed.runtime import build_runtime


@asynccontextmanager
async def lifespan(app):
    runtime = build_runtime()
    await runtime.start()
    app.state.distributed = runtime
    try:
        yield
    finally:
        await runtime.close()


app = FastAPI(title="EduAgent Distributed Run Plane", lifespan=lifespan)
app.include_router(router, prefix="/api")
```

This app must not instantiate `AgentOrchestrator` or `LearningHarness`.

- [ ] **Step 5: Run API tests**

Run:

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
  python -m pytest tests/distributed/test_api.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add python/api/distributed_routes.py python/api/distributed_main.py \
  python/core/distributed/runtime.py python/tests/distributed/test_api.py
git commit -m "feat(distributed): expose durable run control plane"
```

## Task 8: Add Process Entrypoints and Docker Distributed Profile

**Files:**
- Create: `python/core/distributed/cli.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `python/Dockerfile`

- [ ] **Step 1: Add a CLI smoke test**

```python
# append to python/tests/distributed/test_contracts.py
def test_cli_subcommands_parse():
    from core.distributed.cli import parser

    assert parser().parse_args(["dispatcher"]).command == "dispatcher"
    assert parser().parse_args(["worker"]).command == "worker"
    assert parser().parse_args(["reaper"]).command == "reaper"
```

- [ ] **Step 2: Implement long-running CLI loops**

```python
# python/core/distributed/cli.py
import argparse
import asyncio
import os
import socket

from config.settings import settings
from core.distributed.executor import LearningTaskExecutor
from core.distributed.runtime import build_runtime


def parser():
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("dispatcher")
    sub.add_parser("worker")
    sub.add_parser("reaper")
    return value


async def run_forever(command):
    runtime = build_runtime()
    await runtime.start()
    try:
        if command == "dispatcher":
            component = runtime.dispatcher()
            while True:
                await component.dispatch_once()
                await asyncio.sleep(.25)
        elif command == "reaper":
            component = runtime.reaper()
            while True:
                await component.reap_once()
                await asyncio.sleep(settings.distributed_heartbeat_seconds)
        else:
            worker_id = (
                settings.distributed_worker_id
                or f"{socket.gethostname()}:{os.getpid()}"
            )
            component = runtime.worker(
                worker_id,
                LearningTaskExecutor(settings.harness_store_path),
            )
            while True:
                await component.run_once()
    finally:
        await runtime.close()


def main():
    args = parser().parse_args()
    asyncio.run(run_forever(args.command))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Extend the Docker image health/runtime support**

Keep one image and add a non-root runtime user only after verifying the shared volume is writable:

```dockerfile
RUN useradd --create-home --uid 10001 eduagent \
    && mkdir -p /app/data \
    && chown -R eduagent:eduagent /app
USER eduagent
```

The default command stays unchanged; Compose overrides it for distributed services.

- [ ] **Step 4: Add Redis and distributed services**

Add to `docker-compose.yml`:

```yaml
  redis:
    image: redis:7.4-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 20

  distributed-api:
    profiles: ["distributed"]
    build:
      context: ./python
    command: ["uvicorn", "api.distributed_main:app", "--host", "0.0.0.0", "--port", "8890"]
    ports:
      - "8890:8890"
    environment: &distributed-env
      DISTRIBUTED_ENABLED: "true"
      DISTRIBUTED_DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/edu_agent
      DISTRIBUTED_REDIS_URL: redis://redis:6379/1
      HARNESS_STORE_PATH: /app/data/distributed-harness.sqlite3
      LLM_PROVIDER: template
      MEMORY_RETRIEVAL_MODE: lexical
      MEMORY_WORKER_ENABLED: "false"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  run-dispatcher:
    profiles: ["distributed"]
    build:
      context: ./python
    command: ["python", "-m", "core.distributed.cli", "dispatcher"]
    environment: *distributed-env
    depends_on:
      distributed-api:
        condition: service_started

  run-reaper:
    profiles: ["distributed"]
    build:
      context: ./python
    command: ["python", "-m", "core.distributed.cli", "reaper"]
    environment: *distributed-env
    depends_on:
      distributed-api:
        condition: service_started

  run-worker-a:
    profiles: ["distributed"]
    build:
      context: ./python
    command: ["python", "-m", "core.distributed.cli", "worker"]
    environment:
      <<: *distributed-env
      DISTRIBUTED_WORKER_ID: worker-a
      DISTRIBUTED_DEMO_PAUSE_BEFORE_COMMIT_SECONDS: ${DISTRIBUTED_DEMO_PAUSE_BEFORE_COMMIT_SECONDS:-0}
    volumes:
      - distributed_harnessdata:/app/data
    depends_on:
      distributed-api:
        condition: service_started

  run-worker-b:
    profiles: ["distributed"]
    build:
      context: ./python
    command: ["python", "-m", "core.distributed.cli", "worker"]
    environment:
      <<: *distributed-env
      DISTRIBUTED_WORKER_ID: worker-b
    volumes:
      - distributed_harnessdata:/app/data
    depends_on:
      distributed-api:
        condition: service_started
```

Add volumes:

```yaml
  redisdata:
  distributed_harnessdata:
```

- [ ] **Step 5: Document environment defaults**

Add to `.env.example`:

```dotenv
# 分布式 Run Plane（默认关闭；启用后 PostgreSQL 是运行状态真相）
DISTRIBUTED_ENABLED=false
DISTRIBUTED_DATABASE_URL=
DISTRIBUTED_REDIS_URL=redis://localhost:6379/1
DISTRIBUTED_STREAM=eduagent:runs
DISTRIBUTED_CONSUMER_GROUP=eduagent-run-workers
DISTRIBUTED_LEASE_SECONDS=15
DISTRIBUTED_HEARTBEAT_SECONDS=3
DISTRIBUTED_MAX_ATTEMPTS=3
# 可选 OTLP HTTP collector；为空时仅保留 PostgreSQL Trace
OTEL_EXPORTER_OTLP_ENDPOINT=
```

- [ ] **Step 6: Build and smoke test the profile**

Run:

```bash
docker compose --profile distributed up --build -d \
  postgres redis distributed-api run-dispatcher run-reaper run-worker-a run-worker-b
curl --fail http://localhost:8890/api/health
```

Expected response includes:

```json
{"status":"ok","mode":"distributed-control-plane","postgres":"ok","redis":"ok"}
```

- [ ] **Step 7: Commit**

```bash
git add python/core/distributed/cli.py python/tests/distributed/test_contracts.py \
  docker-compose.yml .env.example python/Dockerfile
git commit -m "feat(distributed): run control plane and workers in compose"
```

## Task 9: Prove Cross-Process Failover and Zero Duplicate Effects

**Files:**
- Create: `python/tests/integration/test_distributed_failover.py`
- Create: `tools/demo_distributed_recovery.py`

- [ ] **Step 1: Write a real-process integration test**

The test starts dispatcher/reaper loops in the test process and workers as separate `multiprocessing.Process` instances. Worker A pauses after the inner Harness commits but before PostgreSQL completion; the test terminates A, waits for lease expiry, starts B, and verifies replay.

```python
# python/tests/integration/test_distributed_failover.py
import multiprocessing
import os
import time

import pytest

pytestmark = pytest.mark.distributed_integration


def worker_main(worker_id, pause):
    os.environ["DISTRIBUTED_WORKER_ID"] = worker_id
    os.environ["DISTRIBUTED_DEMO_PAUSE_BEFORE_COMMIT_SECONDS"] = str(pause)
    from core.distributed.cli import run_forever
    import asyncio
    asyncio.run(run_forever("worker"))


async def test_killed_worker_is_fenced_and_second_worker_replays_once(
    distributed_stack, tmp_path
):
    run = await distributed_stack.submit(request_id="kill-recover")
    first = multiprocessing.Process(target=worker_main, args=("worker-a", 30))
    first.start()
    await distributed_stack.wait_for_status(run.id, "committing", timeout=20)
    first.terminate()
    first.join(timeout=5)

    second = multiprocessing.Process(target=worker_main, args=("worker-b", 0))
    second.start()
    completed = await distributed_stack.wait_for_status(
        run.id, "completed", timeout=30
    )
    second.terminate()
    second.join(timeout=5)

    assert completed.attempt_count == 2
    assert await distributed_stack.business_effect_count(
        learner_id="student", request_id="kill-recover"
    ) == 1
    spans = await distributed_stack.repository.trace(run.id)
    assert any(span.name == "lease.reap" for span in spans)
    assert {span.attributes.get("worker.id") for span in spans} >= {
        "worker-a", "worker-b"
    }
```

The `distributed_stack` fixture creates unique stream/group names, a temporary shared SQLite path, starts dispatcher/reaper tasks, and cleans only rows with the test run IDs.

- [ ] **Step 2: Run the process failover test**

Run:

```bash
cd python
DISTRIBUTED_ENABLED=true \
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
DISTRIBUTED_REDIS_URL=redis://localhost:6379/15 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
  python -m pytest tests/integration/test_distributed_failover.py -q
```

Expected: `1 passed`, with two attempts and one business effect.

- [ ] **Step 3: Implement the interview demonstration**

`tools/demo_distributed_recovery.py` performs these exact actions:

```python
async def main():
    compose("up", "--build", "-d", "postgres", "redis", "distributed-api",
            "run-dispatcher", "run-reaper")
    compose("up", "-d", "run-worker-a", env={
        "DISTRIBUTED_DEMO_PAUSE_BEFORE_COMMIT_SECONDS": "30",
    })
    run = await submit_learning_task("demo-recovery")
    await wait_for(run["run_id"], "committing")
    compose("kill", "run-worker-a")
    compose("up", "-d", "run-worker-b")
    result = await wait_for(run["run_id"], "completed")
    trace = await get_json(run["trace_url"])
    assert result["attempt_count"] == 2
    assert count_business_effects(result) == 1
    print_summary(result, trace)
```

Use `subprocess.run(args, check=True)` with argument arrays; do not invoke a shell. The summary prints run ID, first and second workers, fencing tokens, recovery duration, attempt count, duplicate business effect count, status URL, trace URL, and metrics URL.

- [ ] **Step 4: Run the demonstration**

Run:

```bash
python tools/demo_distributed_recovery.py
```

Expected final lines:

```text
status: completed
attempts: 2
lease_takeovers: 1
duplicate_business_effects: 0
```

- [ ] **Step 5: Commit**

```bash
git add python/tests/integration/test_distributed_failover.py \
  tools/demo_distributed_recovery.py
git commit -m "test(distributed): prove worker crash recovery"
```

## Task 10: Add CI, Operational Documentation, and Full Verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `python/pyproject.toml`
- Create: `docs/engineering/distributed-run-plane.md`
- Modify: `README.md`

- [ ] **Step 1: Register the integration marker**

Add to `python/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "distributed_integration: requires PostgreSQL and Redis",
]
```

Default backend CI excludes it:

```bash
python -m pytest tests -q -m "not distributed_integration"
```

- [ ] **Step 2: Add a dedicated CI job with real services**

Add to `.github/workflows/ci.yml`:

```yaml
  distributed-integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: edu_agent
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 2s
          --health-timeout 2s
          --health-retries 20
      redis:
        image: redis:7.4-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 2s
          --health-timeout 2s
          --health-retries 20
    env:
      DISTRIBUTED_ENABLED: "true"
      DISTRIBUTED_TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent
      DISTRIBUTED_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent
      DISTRIBUTED_TEST_REDIS_URL: redis://localhost:6379/15
      DISTRIBUTED_REDIS_URL: redis://localhost:6379/15
      LLM_PROVIDER: template
      MEMORY_RETRIEVAL_MODE: lexical
      MEMORY_WORKER_ENABLED: "false"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: python/pyproject.toml
      - run: python -m pip install -e "./python[dev]"
      - working-directory: python
        run: python -m pytest tests/distributed tests/integration/test_distributed_failover.py -q
```

- [ ] **Step 3: Write the operational contract**

`docs/engineering/distributed-run-plane.md` must contain:

```markdown
# Distributed Run Plane

## What PostgreSQL Guarantees
- Run identity, state, attempts, leases, fencing, steps, outbox, inbox and spans.

## What Redis Does Not Guarantee
- Redis is delivery acceleration, not business truth.
- Duplicate delivery is expected.

## M1 Business-State Boundary
- Existing teaching state remains in one shared SQLite store.
- Only a worker holding a valid PostgreSQL lease opens that store.
- File-lock release plus the original request ID enables crash replay.
- This is recovery, not horizontally scalable business-state writes.

## Failure Matrix
[API/outbox, dispatcher, Redis, worker, heartbeat, stale commit, cancellation]

## Commands
[normal profile, distributed profile, tests, demo, metrics]

## Evidence
[commit, test output, demo run ID, trace and metric snapshots]
```

Do not claim distributed business-state writes or network-level exactly-once behavior.

- [ ] **Step 4: Update README**

Add a concise `分布式 Run Plane（M1）` section after `Harness 执行边界`:

```markdown
启用 distributed profile 后，PostgreSQL 保存 Run/Lease/Step/Outbox/Trace，
Redis Streams 负责投递，两个 Worker 通过租约和 fencing token 竞争执行。
现有教学状态在 M1 仍由共享 SQLite 单写；Worker 崩溃后释放文件锁，接管
Worker 使用相同业务 request ID 重放，因此可证明恢复和零重复业务效果，
但不宣称教学状态已支持水平多写。
```

Include:

```bash
docker compose --profile distributed up --build -d
python tools/demo_distributed_recovery.py
```

- [ ] **Step 5: Run focused and full verification**

Run:

```bash
cd python
LLM_PROVIDER=template MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m pytest tests -q -m "not distributed_integration"

DISTRIBUTED_ENABLED=true \
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
DISTRIBUTED_REDIS_URL=redis://localhost:6379/15 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
  python -m pytest tests/distributed tests/integration/test_distributed_failover.py -q

cd ../frontend
npm run build

cd ..
docker compose config
python tools/demo_distributed_recovery.py
```

Expected:

- all pre-existing non-integration tests pass;
- all distributed tests pass;
- frontend build succeeds;
- Compose config validates;
- demo reports `completed`, two attempts, one takeover, and zero duplicate business effects.

- [ ] **Step 6: Verify archive-safe evidence**

Run:

```bash
git diff --check
git status --short
rg -n 'API_KEY=.+|authorization.+Bearer|reasoning_content' \
  docs/engineering/distributed-run-plane.md README.md
```

Expected: no whitespace errors, no unexpected generated files, and no secret/private reasoning content.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml python/pyproject.toml \
  docs/engineering/distributed-run-plane.md README.md
git commit -m "docs(distributed): document and gate durable run plane"
```

## Completion Audit

Before declaring M1 complete, inspect current evidence for every item:

| Requirement | Authoritative evidence |
| --- | --- |
| PostgreSQL is Run truth | rows and transition tests for all seven tables |
| Redis duplicate delivery is safe | dispatcher duplicate test plus inbox/run idempotency |
| Worker crash is recovered | real-process failover test and demo Trace |
| Stale Worker cannot commit | fencing integration test |
| Existing business runs in profile | completed learning-task result from worker executor |
| No duplicate business effect | SQLite evidence count after replay equals one |
| Trace crosses processes | durable span tree contains both worker IDs and takeover |
| Metrics are available | `/metrics` assertions and demo URL |
| Local mode still works | complete existing backend suite |
| Distributed profile is reproducible | Compose build, health check, demo script |

M1 is incomplete if any row has only a unit-test mock or documentation claim instead of the listed runtime evidence.
