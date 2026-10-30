# M2 Bounded Expert Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PostgreSQL-authoritative, dual-fenced Expert Plane for Assessment, Curriculum, and Tutor drafts, plus a read-only Ops Console and real multi-process failure evidence.

**Architecture:** A Run Worker freezes a redacted snapshot and creates an expert job under its current Run fencing token. Separate Expert Workers execute a shared snapshot-only engine, append results under a second fencing token, and never receive learner-store write access. The parent Coordinator revalidates and adopts drafts; PostgreSQL polling is authoritative, Redis Streams only accelerates delivery, and `/ops/` reads bounded operational projections.

**Tech Stack:** Python 3.11, Pydantic v2, SQLAlchemy async, PostgreSQL 16, Redis Streams, FastAPI, OpenTelemetry, Prometheus, React 18, TypeScript, Ant Design, pytest, Docker Compose.

---

## Scope and File Map

### Expert protocol and persistence

| File | Responsibility |
| --- | --- |
| `python/core/distributed/expert_contracts.py` | Strict job, snapshot, budget, usage, draft, and authority contracts |
| `python/core/distributed/expert_models.py` | Expert job, lease, result, outbox, inbox, and worker-registry ORM models |
| `python/core/distributed/expert_repository.py` | Job admission, dual fencing, transitions, results, and retry |
| `python/core/distributed/expert_snapshot.py` | Redacted frozen snapshots and snapshot-only read tools |
| `python/core/distributed/expert_engine.py` | Shared bounded Assessment/Curriculum/Tutor draft engine |
| `python/core/distributed/expert_adopter.py` | Parent-authority, policy, source, schema, and role revalidation |
| `python/core/distributed/expert_gateway.py` | Inline and durable gateways, PostgreSQL result polling, parent usage charging |
| `python/core/distributed/expert_dispatcher.py` | Due expert-outbox publication |
| `python/core/distributed/expert_worker.py` | Claim, heartbeat, execute, submit, and ack loop |
| `python/core/distributed/expert_reaper.py` | Expired lease, stale parent, deadline, and retry recovery |
| `python/core/distributed/worker_registry.py` | Process registration, heartbeat, assignment, and stale derivation |

### Parent integration

| File | Responsibility |
| --- | --- |
| `python/core/run_context.py` | Optional distributed authority and expert gateway |
| `python/core/specialist_runtime.py` | Freeze, execute, adopt, charge, and restore parent scope |
| `python/core/coordinator.py` | Remote TutorDraft adoption and parent-only public reply/action execution |
| `python/core/harness.py` | Inject authority/gateway without changing learner commit ownership |
| `python/core/distributed/executor.py` | Pass `RunExecutionAuthority` from Run Worker into the harness |
| `python/core/distributed/worker.py` | Supply authority and support `waiting_expert` lease renewal |
| `python/core/distributed/contracts.py` | Add `waiting_expert` Run status |
| `python/core/distributed/repository.py` | Parent wait/running transitions and Ops projections |

### Control plane, Ops, and delivery

| File | Responsibility |
| --- | --- |
| `python/core/distributed/runtime.py` | Build expert repositories, brokers, gateway, registry, and process components |
| `python/core/distributed/cli.py` | Expert process commands and process-heartbeat lifecycle |
| `python/core/distributed/ops_contracts.py` | Explicit allow-listed Ops response schemas |
| `python/core/distributed/ops_queries.py` | Query-only cursor pagination and detail projections |
| `python/api/ops_routes.py` | Bounded read-only Runs, Trace, Expert Jobs, and Workers endpoints |
| `python/api/distributed_main.py` | Mount Ops routes |
| `frontend/ops/index.html` | Independent Ops HTML entry |
| `frontend/src/ops/types.ts` | Ops response types |
| `frontend/src/ops/api.ts` | Abortable fetch and cursor query helpers |
| `frontend/src/ops/main.tsx` | Ops-only React bootstrap |
| `frontend/src/ops/OpsApp.tsx` | Runs/Trace/Workers shell and routing |
| `frontend/src/ops/RunsView.tsx` | Run table and run/job detail drawer |
| `frontend/src/ops/TraceView.tsx` | Causal span tree |
| `frontend/src/ops/WorkersView.tsx` | Worker freshness and assignment table |
| `frontend/src/ops/ops.css` | Responsive operational styling |
| `frontend/vite.config.ts` | Local `/ops-api` proxy |
| `frontend/nginx.conf` | Container `/ops-api` proxy to distributed API |

### Verification and evidence

| File | Responsibility |
| --- | --- |
| `python/tests/distributed/test_expert_contracts.py` | Contract, redaction, hash, deadline, and schema tests |
| `python/tests/distributed/test_expert_repository.py` | State, fencing, admission, result, retry, and lock-order tests |
| `python/tests/distributed/test_expert_snapshot.py` | Snapshot isolation and tool scope tests |
| `python/tests/distributed/test_expert_engine.py` | Role loops, budgets, usage, and TutorDraft tests |
| `python/tests/distributed/test_expert_gateway.py` | Inline/remote parity, polling, cancellation, and charging |
| `python/tests/distributed/test_expert_worker.py` | Worker heartbeat, retry, stale result, and ack behavior |
| `python/tests/distributed/test_ops_api.py` | Pagination, filters, redaction, and worker freshness |
| `python/tests/integration/test_expert_failover.py` | Real Expert Worker and parent-worker failure tests |
| `tools/demo_expert_failover.py` | Repeatable evidence-producing process demo |
| `tools/benchmark_expert_plane.py` | Bounded-concurrency latency/capacity benchmark |
| `docs/engineering/bounded-expert-plane.md` | Protocol, failure matrix, commands, evidence, and honest limits |

## Task 1: Freeze Contracts, Settings, and Parent Authority

**Files:**
- Create: `python/core/distributed/expert_contracts.py`
- Create: `python/tests/distributed/test_expert_contracts.py`
- Modify: `python/config/settings.py`
- Modify: `python/core/distributed/contracts.py`
- Modify: `python/core/run_context.py`

- [ ] **Step 1: Write failing contract and settings tests**

Create tests named `test_job_hash_is_stable_and_extra_fields_are_forbidden`,
`test_tutor_draft_cannot_smuggle_public_response_metadata`,
`test_deadline_must_be_utc_and_not_after_parent_deadline`,
`test_usage_preserves_unknown_tokens_instead_of_zero`,
`test_distributed_experts_require_distributed_run_plane`, and
`test_waiting_expert_is_active_but_not_terminal`.

Use fixed UTC datetimes and assert Pydantic `ValidationError` for naive timestamps,
unknown fields, mismatched learner scope, and a Tutor draft containing
`dialogue_state`.

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
cd python
python -m pytest tests/distributed/test_expert_contracts.py -q
```

Expected: collection fails because `core.distributed.expert_contracts` does not exist.

- [ ] **Step 3: Implement strict contracts**

Define:

```python
class ExpertRole(StrEnum):
    ASSESSMENT = "Assessment"
    CURRICULUM = "Curriculum"
    TUTOR = "Tutor"

class RunExecutionAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    distributed_run_id: UUID
    run_fencing_token: int = Field(ge=1)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    attempt_number: int = Field(ge=1)
    worker_id: Identifier
    parent_deadline_at: datetime

class ExpertBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_model_calls: int = Field(ge=1, le=6)
    max_tool_calls: int = Field(ge=0, le=10)
    max_output_tokens: int = Field(ge=100, le=2000)
    max_context_tokens: int = Field(ge=1000, le=32000)
    max_attempts: int = Field(ge=1, le=5)
    deadline_at: datetime

class ExpertUsage(BaseModel):
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    provider: str
    model: str
    uncertain: bool = False
```

Add frozen `HistoryRecord`, `ExpertSnapshot`, `ExpertJobRequest`,
Assessment/Curriculum draft unions, `TutorDraft`, and `ExpertTerminalEnvelope`.
All models use `extra="forbid"`; canonical hashes use the existing
`canonical_hash(model_dump(mode="json"))`.

- [ ] **Step 4: Add validated settings**

Add `distributed_experts_enabled`, separate stream/group, lease/heartbeat/poll
intervals, job/payload/queue/running limits, retry base/max delay, result poll
interval, and demo pause fields. Validate:

```python
if self.distributed_experts_enabled and not self.distributed_enabled:
    raise ValueError("distributed experts require distributed run plane")
if self.expert_heartbeat_seconds >= self.expert_lease_seconds / 2:
    raise ValueError("expert heartbeat must be less than half the lease")
```

Add `RunStatus.WAITING_EXPERT` and treat it as active. Add optional
`execution_authority` and `expert_gateway` fields to `RunContext`.

- [ ] **Step 5: Run tests and commit**

```bash
cd python
python -m pytest tests/distributed/test_contracts.py \
  tests/distributed/test_expert_contracts.py -q
git add python/config/settings.py python/core/run_context.py \
  python/core/distributed/contracts.py python/core/distributed/expert_contracts.py \
  python/tests/distributed/test_expert_contracts.py
git commit -m "feat(experts): freeze bounded expert contracts"
```

Expected: all selected tests pass.

## Task 2: Add Expert Schema and Transactional Repository

**Files:**
- Create: `python/core/distributed/expert_models.py`
- Create: `python/core/distributed/expert_repository.py`
- Create: `python/tests/distributed/test_expert_repository.py`
- Modify: `python/core/distributed/models.py`
- Modify: `python/tests/distributed/conftest.py`

- [ ] **Step 1: Write PostgreSQL repository tests**

Test job idempotency and hash conflict, parent-token validation, per-run and per-role
admission, claim token increments, renewal, one accepted result, rejected stale/late
result retention, cumulative usage, terminal failure, deadline expiry, delayed retry
outbox, old parent epoch cleanup, and cancellation closing active jobs.

The key race test must use two independent async sessions:

```python
accepted = await asyncio.gather(
    repo.submit_result(job.id, "worker-a", token_a, result_a),
    repo.submit_result(job.id, "worker-b", token_b, result_b),
    return_exceptions=True,
)
assert await repo.accepted_result_count(job.id) == 1
assert await repo.result_count(job.id) == 2
```

- [ ] **Step 2: Verify tests fail**

```bash
cd python
python -m pytest tests/distributed/test_expert_repository.py -q
```

Expected: import failure for expert models/repository.

- [ ] **Step 3: Add six ORM tables and indexes**

Implement the five expert tables plus `DistributedWorkerRegistry`. Use a partial
unique index:

```python
Index(
    "uq_expert_result_accepted",
    DistributedExpertResult.job_id,
    unique=True,
    postgresql_where=DistributedExpertResult.disposition == "accepted",
)
```

Use timezone-aware columns, JSON payloads, bounded strings, and named unique
constraints. Import these models before `DistributedBase.metadata.create_all`.
Add `deadline_at` to `DistributedRunAttempt`; derive it from PostgreSQL time plus the
configured parent timeout during claim, return it on `RunClaim`, and include it in
`RunExecutionAuthority`. Expert request validation rejects a deadline after this
persisted parent deadline.

- [ ] **Step 4: Implement repository transitions and lock order**

`ExpertJobRepository` must expose:

```python
async def create_or_replay(self, request: ExpertJobRequest) -> tuple[JobView, bool]
async def claim(self, job_id: str, worker_id: str, roles: set[ExpertRole], lease_seconds: float) -> ExpertClaim
async def renew(self, job_id: str, worker_id: str, token: int, lease_seconds: float) -> None
async def submit_result(self, job_id: str, worker_id: str, token: int, envelope: ExpertTerminalEnvelope) -> ResultReceipt
async def fail_attempt(self, job_id: str, worker_id: str, token: int, failure: ExpertFailure) -> JobView
async def terminal(self, job_id: str, parent_token: int) -> ExpertTerminalEnvelope | None
async def reap_expired(self) -> list[str]
```

Every cross-plane method locks Run, Run lease, job, Expert lease, and result in that
order. Use database `clock_timestamp()`. Rejected result insertion is append-only and
does not mutate job or parent rows.

- [ ] **Step 5: Add deterministic advisory admission**

Use `pg_advisory_xact_lock(namespace, hashtextextended(key, 0))` before counts.
Creation serializes by parent and role; claims serialize by role. Assert one active job
per parent and configured queued/running limits. Queue-full raises
`ExpertBackpressure` before insert.

Before admitting a new parent token, atomically mark active jobs from older tokens
`parent_stale`. Capability mismatch returns a non-claim receipt before attempt count or
retry budget changes.

- [ ] **Step 6: Run repository suites and commit**

```bash
cd python
python -m pytest tests/distributed/test_repository.py \
  tests/distributed/test_expert_repository.py -q
git add python/core/distributed/expert_models.py \
  python/core/distributed/expert_repository.py \
  python/core/distributed/models.py python/tests/distributed
git commit -m "feat(experts): persist dual-fenced expert jobs"
```

## Task 3: Build Frozen Snapshots and Snapshot-only Tools

**Files:**
- Create: `python/core/distributed/expert_snapshot.py`
- Create: `python/tests/distributed/test_expert_snapshot.py`
- Modify: `python/core/output_safety.py`

- [ ] **Step 1: Write isolation and leak tests**

Build a context with two learners, omitted history, secret-shaped nested keys, and a
write callback. Assert:

```python
assert "prepare_practice" not in executor.tool_names
assert await executor.read("foreign-ref") == denied("source_unavailable")
assert await executor.read("omitted-ref") == denied("source_unavailable")
assert "api_key" not in json.dumps(snapshot.model_dump()).lower()
assert snapshot.model_dump() == original_dump
```

Also prove search excerpts are not promoted to verified references until
`read_learning_history` succeeds.

- [ ] **Step 2: Verify tests fail**

```bash
cd python
python -m pytest tests/distributed/test_expert_snapshot.py -q
```

- [ ] **Step 3: Implement snapshot builder and executor**

`ExpertSnapshotBuilder.freeze` copies only explicit fields, redacts with existing
public-data rules, recursively rejects keys matching
`token|secret|password|authorization|cookie|api_key`, enforces byte limits, sorts
records by source reference, and returns a frozen Pydantic model.

`SnapshotToolExecutor.execute(NativeToolCall)` validates arguments with the existing
tool schemas but handles only the five read tools against snapshot values. It tracks
read references locally and never imports `LearningHistory`, SQLite, repositories, or
write callbacks.

- [ ] **Step 4: Run tests and commit**

```bash
cd python
python -m pytest tests/distributed/test_expert_snapshot.py -q
git add python/core/distributed/expert_snapshot.py \
  python/core/output_safety.py python/tests/distributed/test_expert_snapshot.py
git commit -m "feat(experts): freeze redacted snapshot tools"
```

## Task 4: Extract a Shared Bounded Expert Engine and Parent Adopter

**Files:**
- Create: `python/core/distributed/expert_engine.py`
- Create: `python/core/distributed/expert_adopter.py`
- Create: `python/tests/distributed/test_expert_engine.py`
- Modify: `python/core/specialist_runtime.py`
- Modify: `python/core/specialist_drafts.py`
- Modify: `python/tests/test_coordinator_runtime.py`

- [ ] **Step 1: Add failing parity and security tests**

Cover Assessment search/read, Curriculum action proposal, TutorDraft, model/tool
budget exhaustion, duplicate tool IDs, invalid citations, cumulative usage, and no
private reasoning in result diagnostics.

Add a parameterized parity test that runs the same frozen request through inline and
worker entry points and compares normalized draft/hash/source references.

- [ ] **Step 2: Verify tests fail**

```bash
cd python
python -m pytest tests/distributed/test_expert_engine.py \
  tests/test_coordinator_runtime.py -q
```

- [ ] **Step 3: Implement `ExpertEngine`**

Move the model/tool loop out of mutable `RunContext` code. `ExpertEngine` has
constructor `ExpertEngine(service, *, clock=datetime.now)` and async method
`execute(request: ExpertJobRequest, consumed: ExpertUsage | None = None) ->
ExpertTerminalEnvelope`. These are its only dependencies.

Use `SnapshotToolExecutor`, frozen budgets, strict role adapters, and sanitized
diagnostics. Return usage on success and every controlled failure.

- [ ] **Step 4: Implement parent adoption**

Add `ExpertResultAdopter` that checks job/step/role/input/policy/parent identity,
revalidates source ownership and availability through the current parent history,
validates action role, and returns either `AgentResult` or `TutorDraft`.
If adoption fails after database acceptance, retain the accepted result and emit an
`expert.adoption_rejected` span with a stable reason.

Refactor `SpecialistRuntime.run` into allocate/freeze/gateway/adopt/charge/finally.
Inline mode must also pass through the frozen engine and adopter.

- [ ] **Step 5: Run regression and commit**

```bash
cd python
python -m pytest tests/distributed/test_expert_engine.py \
  tests/test_coordinator_runtime.py tests/test_memory_coordination.py -q
git add python/core/distributed/expert_engine.py \
  python/core/distributed/expert_adopter.py \
  python/core/specialist_runtime.py python/core/specialist_drafts.py \
  python/tests/distributed/test_expert_engine.py python/tests/test_coordinator_runtime.py
git commit -m "refactor(experts): share snapshot engine and adopter"
```

## Task 5: Add Durable Gateway, Dispatcher, Worker, and Reaper

**Files:**
- Create: `python/core/distributed/expert_gateway.py`
- Create: `python/core/distributed/expert_dispatcher.py`
- Create: `python/core/distributed/expert_worker.py`
- Create: `python/core/distributed/expert_reaper.py`
- Create: `python/tests/distributed/test_expert_gateway.py`
- Create: `python/tests/distributed/test_expert_worker.py`
- Modify: `python/core/distributed/broker.py`
- Modify: `python/core/distributed/metrics.py`

- [ ] **Step 1: Write gateway and worker failure tests**

Test pre-accept inline fallback, no inline fallback after durable acceptance,
PostgreSQL polling truth, parent cancellation, parent lease loss, worker heartbeat
loss, retry taxonomy, duplicate Redis delivery, stale result rejection, delayed
outbox, and ack only after a PostgreSQL terminal decision.

- [ ] **Step 2: Verify tests fail**

```bash
cd python
python -m pytest tests/distributed/test_expert_gateway.py \
  tests/distributed/test_expert_worker.py -q
```

- [ ] **Step 3: Generalize broker without changing M1 behavior**

Rename only internal message terminology or add a generic alias; retain the public
`RedisRunBroker` import for compatibility. Instantiate a separate stream/group for
experts. M1 broker tests must remain unchanged.

- [ ] **Step 4: Implement the durable components**

`DurableExpertGateway.execute` creates/replays once, polls `repository.terminal`, checks
the parent cancellation event, and never uses Redis as result truth.

`ExpertWorker.handle` records inbox, claims, starts an Expert lease heartbeat, runs
the engine, submits a result/failure, and acknowledges only after the repository
returns a terminal or safely rejected receipt.

`ExpertReaper` delegates all decisions to `ExpertJobRepository.reap_expired`.
`ExpertDispatcher` selects due outbox rows with `SKIP LOCKED`.

- [ ] **Step 5: Add metrics and commit**

Expose role/status queue gauges, result disposition, late result, takeover, retry,
backpressure, snapshot bytes, parent wait, and attempt duration.

```bash
cd python
python -m pytest tests/distributed/test_dispatcher.py \
  tests/distributed/test_expert_gateway.py \
  tests/distributed/test_expert_worker.py -q
git add python/core/distributed python/tests/distributed
git commit -m "feat(experts): run durable expert workers"
```

## Task 6: Wire Run Authority, Coordinator, and Parent-only Tutor Reply

**Files:**
- Modify: `python/core/distributed/executor.py`
- Modify: `python/core/distributed/worker.py`
- Modify: `python/core/distributed/repository.py`
- Modify: `python/core/harness.py`
- Modify: `python/core/coordinator.py`
- Modify: `python/core/tutor_runtime.py`
- Create: `python/tests/distributed/test_expert_integration.py`
- Modify: `python/tests/distributed/test_executor.py`
- Modify: `python/tests/test_coordinator_runtime.py`

- [ ] **Step 1: Write integration-boundary tests**

Assert the Run Worker passes current authority, harness stores it on context, expert
wait changes parent status while renewing the lease, stale parent cannot adopt, remote
Curriculum can only propose an action, and remote Tutor returns a draft that becomes a
public `TeachingReply` only after parent citation validation.

Instrument parent-only methods:

```python
assert expert_process_calls["prepare_practice"] == 0
assert parent_process_calls["prepare_practice"] == 1
assert expert_process_calls["TutorRuntime.reply"] == 0
assert parent_process_calls["TutorRuntime.reply"] == 1
```

- [ ] **Step 2: Change executor authority signature**

Use:

```python
class RunExecutor(Protocol):
    async def execute(
        self,
        spec: DistributedRunRequest,
        authority: RunExecutionAuthority,
    ) -> dict:
        raise NotImplementedError
```

Construct authority from the current claim in `RunWorker`. `LearningTaskExecutor`
receives an optional gateway, injects both into `LearningHarness`, and never serializes
the gateway into a payload.

- [ ] **Step 3: Add parent wait transitions**

Repository methods set `RUNNING -> WAITING_EXPERT -> RUNNING` only for the current
token. Renew permits both states. Completion still requires `COMMITTING`; cancellation
and reaping include `WAITING_EXPERT`.

- [ ] **Step 4: Integrate Coordinator**

Assessment/Curriculum continue to adopt `AgentResult`. Tutor delegates through the
same gateway when durable experts are enabled, adopts `TutorDraft`, then calls
`TutorRuntime.reply` in the parent. Preserve existing inline behavior and plan
serialization. Coordinator delegation already consumes one parent tool call; remote
model/tool usage is charged exactly once from the terminal cumulative usage and does
not re-charge the delegate call.

- [ ] **Step 5: Run broad parent regression and commit**

```bash
cd python
python -m pytest tests/distributed/test_executor.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_expert_integration.py \
  tests/test_coordinator_runtime.py tests/test_tutor_harness.py -q
git add python/core python/tests
git commit -m "feat(experts): delegate coordinator drafts safely"
```

## Task 7: Add Process Registry and Read-only Ops APIs

**Files:**
- Create: `python/core/distributed/ops_contracts.py`
- Create: `python/core/distributed/ops_queries.py`
- Create: `python/core/distributed/worker_registry.py`
- Create: `python/api/ops_routes.py`
- Create: `python/tests/distributed/test_ops_api.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `python/api/distributed_main.py`
- Modify: `python/api/distributed_routes.py`

- [ ] **Step 1: Write registry and API tests**

Test startup/upsert/heartbeat/assignment/stop, database-time freshness, cursor
pagination, filter allow-lists, 404 behavior, trace tree data, expert attempt/result
metadata, and redaction. Recursively assert forbidden keys and seeded secret values
are absent from every Ops response.

- [ ] **Step 2: Implement registry lifecycle**

Use a unique `(worker_id, instance_id)` identity. Every long-running command registers,
heartbeats in a background task, updates current assignment, marks stopped in
`finally`, and tolerates a registry-write failure without corrupting job execution.

- [ ] **Step 3: Implement bounded projections**

Implement all reads in query-only `OpsQueries`; it has no mutation methods. Return
strict `ops_contracts.py` response models instead of ORM objects. Every list accepts
`limit <= 100` and opaque `(created_at, id)` cursor. Detail responses expose hashes,
tokens, status, usage, and source IDs, never job payload/draft/history content.

- [ ] **Step 4: Mount APIs and commit**

```bash
cd python
python -m pytest tests/distributed/test_ops_api.py \
  tests/distributed/test_api.py -q
git add python/api python/core/distributed python/tests/distributed/test_ops_api.py
git commit -m "feat(ops): expose durable run and worker views"
```

## Task 8: Build the Separate Ops Console

**Files:**
- Create: `frontend/ops/index.html`
- Create: `frontend/src/ops/types.ts`
- Create: `frontend/src/ops/api.ts`
- Create: `frontend/src/ops/main.tsx`
- Create: `frontend/src/ops/OpsApp.tsx`
- Create: `frontend/src/ops/RunsView.tsx`
- Create: `frontend/src/ops/TraceView.tsx`
- Create: `frontend/src/ops/WorkersView.tsx`
- Create: `frontend/src/ops/ops.css`
- Create: `frontend/e2e/ops.spec.ts`
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/nginx.conf`
- Modify: `frontend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the Ops entry and typed API client**

Configure Vite as a two-entry build with the existing `index.html` and
`ops/index.html`. `frontend/src/ops/main.tsx` renders only `OpsApp`; the existing
learning entry remains unchanged. Use hash navigation (`/ops/#/runs`,
`/ops/#/trace/{run_id}`, `/ops/#/workers`) so UI paths never collide with API paths.
The API client uses `/ops-api/ops`, an `AbortController`, explicit response guards,
and no polling faster than five seconds.

- [ ] **Step 2: Implement feature-complete views**

Add `lucide-react` and `@playwright/test` to the appropriate dependency groups. Use
compact Ant Design tables/tabs, Lucide icons, status tags, tooltips, cursor
next/previous controls, loading skeletons, empty states, retryable errors, and a
detail drawer. Trace uses a nested semantic list with fixed duration columns; Workers
displays heartbeat age and never calls Redis directly.

- [ ] **Step 3: Add responsive styling and proxying**

Keep cards at `8px` or less, avoid nested cards and decorative gradients, preserve
stable table/control dimensions, and ensure labels wrap on mobile. Vite proxies
`/ops-api` to `http://localhost:8890`. nginx redirects exact `/ops` to `/ops/`, serves
the Ops HTML only for exact `/ops/`, and proxies `/ops-api/` through Docker's deferred
DNS resolver so normal non-distributed startup does not fail when `distributed-api`
is absent. Proxy `/api/distributed/` to port 8890 before generic `/api/`. Change the
frontend image to copy the lockfile and run `npm ci`.

- [ ] **Step 4: Build and browser-verify**

```bash
cd frontend
npm run build
npx playwright test e2e/ops.spec.ts
```

Mock the Ops APIs and use Playwright at `1440x900` and `390x844`. Verify populated,
loading, empty, error, cursor pagination, and stale-worker states; no mutation
controls, overlap, clipped text, console errors, or failed API requests. Save no
screenshots in the repository.

- [ ] **Step 5: Commit**

```bash
git add frontend docker-compose.yml
git commit -m "feat(ops): add read-only expert operations console"
```

## Task 9: Add CLI, Compose, Real Failover, and Benchmark Evidence

**Files:**
- Create: `python/tests/integration/test_expert_failover.py`
- Create: `tools/demo_expert_failover.py`
- Create: `tools/benchmark_expert_plane.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add expert process commands and services**

Add `expert-dispatcher`, `expert-worker`, and `expert-reaper`; Compose runs two Expert
Workers with distinct IDs and shared PostgreSQL/Redis only. Do not mount the harness
SQLite volume or learner-store credentials into Expert Worker containers.

- [ ] **Step 2: Write real process-kill tests**

Use deterministic test pauses, subprocesses, and real PostgreSQL/Redis. Verify:

```text
expert worker killed -> higher expert token -> one accepted result
parent worker killed -> late result disposition=parent_stale -> no adoption
duplicate Redis messages -> one accepted result
cancel waiting parent -> no accepted/adopted late draft
```

All subprocesses terminate in `finally`; preserve stderr on failure.

- [ ] **Step 3: Add evidence scripts**

The demo prints machine-readable JSON containing revision, config fingerprint, run/job
IDs, both token sequences, process IDs, accepted/rejected counts, learner effect count,
request count, model, and cost/unknown cost.

The benchmark uses fixed template/model mode, warmup, bounded concurrency, and reports
p50/p95 enqueue-to-start and end-to-end latency, throughput, queue peak, errors, and
environment metadata. It also reports time holding the parent SQLite lock while
waiting; it does not claim provider-scale performance or horizontal learner-state
writes.

- [ ] **Step 4: Run and commit**

```bash
cd python
python -m pytest tests/integration/test_expert_failover.py -q
cd ..
python tools/demo_expert_failover.py
python tools/benchmark_expert_plane.py --requests 30 --concurrency 4
git add python/core/distributed/cli.py python/tests/integration \
  tools docker-compose.yml .env.example
git commit -m "test(experts): prove multiprocess failover"
```

## Task 10: CI, Engineering Documentation, and Full Acceptance

**Files:**
- Create: `docs/engineering/bounded-expert-plane.md`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

- [ ] **Step 1: Extend CI**

The PostgreSQL/Redis job runs all distributed unit tests plus both M1 and M2 integration
tests. Frontend still builds independently. Package verification imports every new
module and invokes CLI `--help`.

- [ ] **Step 2: Write the engineering evidence document**

Document authority, frozen payload fields, table constraints, lock order, state
machines, retry/usage semantics, data-redaction rules, commands, failure evidence,
benchmark context, and honest limitations. Include exact Git revision and no secrets.

- [ ] **Step 3: Run static and regression gates**

```bash
git diff --check
cd python
python -m pytest tests -q -m "not distributed_integration"
eduagent-eval run --suite builtin --output /tmp/eduagent-m2-eval.json
cd ../frontend
npm ci
npm run build
cd ..
python -m build python --outdir /tmp/eduagent-m2-dist
```

Expected: all tests/builds pass; offline evaluation reports no required-case
regression.

- [ ] **Step 4: Run real infrastructure gates**

```bash
cd python
DISTRIBUTED_ENABLED=true \
DISTRIBUTED_EXPERTS_ENABLED=true \
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
DISTRIBUTED_REDIS_URL=redis://localhost:6379/15 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
python -m pytest tests/distributed tests/integration/test_distributed_failover.py \
  tests/integration/test_expert_failover.py -q
```

Then parse Compose, start the distributed profile, submit a real coordinated run,
inspect `/ops/runs`, `/ops/workers`, and `/ops/runs/{id}/trace`, kill one Expert
Worker, and repeat the run.

- [ ] **Step 5: Audit, clean, commit, merge, and push**

Check `git status`, tracked files, environment files, generated databases, caches,
logs, and evidence for credentials. Remove only task-generated transient files.
Confirm every completion criterion in the design has authoritative evidence.

```bash
git add .github/workflows/ci.yml .gitignore README.md \
  docs/engineering/bounded-expert-plane.md
git commit -m "docs(experts): publish M2 operations evidence"
git push -u origin feat/m2-bounded-expert-plane
```

After green CI and local acceptance, fast-forward `main`, push `origin/main`, and
record the final revision in the evidence document. Do not mark the broader interview
goal complete; M3 trusted policy promotion remains.
