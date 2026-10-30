# M2 Bounded Expert Plane and Ops Console Design

Date: 2026-10-30
Status: Approved for implementation
Parent design: `docs/superpowers/specs/2026-10-29-distributed-agent-harness-design.md`

## 1. Objective

M2 distributes the side-effect-free Assessment, Curriculum, and Tutor drafting work
without distributing ownership of learner state.

The resulting system must prove that:

- a Run Worker can delegate an expert step to another process through a durable queue;
- duplicate delivery, worker death, stale workers, retries, cancellation, and late results
  cannot make an expert mutate learner state or make a stale parent adopt a result;
- experts receive a bounded, redacted, immutable snapshot rather than a live
  `RunContext`, SQLite handle, graph object, callback, or process-local deadline;
- the Coordinator validates and adopts an untrusted draft before any action or public
  response is committed;
- operators can inspect runs, attempts, expert jobs, traces, leases, and process
  heartbeats from a read-only console.

M2 preserves the M1 boundary: PostgreSQL is authoritative for distributed execution,
Redis Streams is delivery acceleration, and the existing single-writer
`LearningHarness` remains authoritative for learner-state commits.

## 2. Approaches Considered

### 2.1 Direct HTTP RPC

The parent calls an expert service and waits for the response.

This is simple but loses accepted work when either process dies, has no durable retry
or late-result record, and turns timeout handling into guesswork. It is not selected.

### 2.2 Send the live `RunContext` to a remote worker

This would preserve current runtime code but would also transfer mutable state,
callbacks, SQLite-backed history, graph objects, `ContextVar` state, and a monotonic
deadline that is meaningless in another process. It also obscures which reads and
writes are authorized. It is not selected.

### 2.3 PostgreSQL-authoritative jobs with frozen snapshot tools

The parent writes a frozen expert job to PostgreSQL and an outbox record in one
transaction. Redis delivers a hint to an Expert Worker. The worker executes only
against the job snapshot and appends a result. The parent polls PostgreSQL, validates
the draft against current authority, and alone performs actions or publishes a reply.

This is selected because it extends M1's durable execution semantics, makes all
failure decisions auditable, and creates a strong interview demonstration without
pretending that the learner store is horizontally writable.

## 3. Scope

### 3.1 Included

- durable Assessment, Curriculum, and Tutor draft jobs;
- independent expert leases and fencing tokens;
- frozen/redacted snapshot construction and snapshot-backed read tools;
- bounded model/tool/time budgets and usage accounting across retries;
- Coordinator integration, including a separately validated `TutorDraft`;
- worker registry and heartbeats for API, dispatcher, reaper, Run Workers, and
  Expert Workers;
- read-only `/ops/*` APIs and a React Ops Console with Runs, Trace, and Workers views;
- process-kill, duplicate-delivery, stale-parent, late-result, deadline, retry,
  backpressure, and data-leak tests;
- a repeatable multi-process demonstration and latency/capacity benchmark.

### 3.2 Not Included

- Expert Workers writing BKT state, quizzes, memories, plans, messages, or public
  responses;
- replacing the learner-state SQLite store with PostgreSQL;
- parallel execution of dependent plan steps;
- arbitrary operator mutation, retry, lease-steal, or payload inspection controls;
- M3 Judge v3, campaign scheduling, policy shadow rollout, or automatic rollback;
- exactly-once model billing. A timed-out or killed attempt may still incur provider
  cost and is recorded as such.

## 4. Authority and Trust Boundaries

### 4.1 Single writer

The Run Worker remains the only process allowed to:

- update BKT or learner checkpoints;
- grade answers or change quiz state;
- create a practice quiz;
- commit memory or conversation history;
- update a learning plan;
- return the public `TeachingReply`.

An Expert Worker returns only an untrusted draft plus source references, usage, and
diagnostics. Even a valid Curriculum draft can only propose `PracticeParams`; the
parent executes `prepare_practice` after policy checks. A Tutor Worker returns
`TutorDraft`, never `TeachingReply`; the parent calls `TutorRuntime.reply` to validate
citations and construct the public response.

### 4.2 Execution authority

`RunWorker` passes an immutable `RunExecutionAuthority` to the business executor:

```text
distributed_run_id
run_fencing_token
trace_id
attempt_number
worker_id
parent_deadline_at
```

`LearningTaskExecutor` injects this authority and an `ExpertGateway` into the
`LearningHarness`. The harness stores both on `RunContext`. Local, non-distributed
execution has no authority and uses the existing inline expert runtime.

The deterministic domain `ctx.run_id` remains available for learning-history
correlation. It must not be used as the distributed parent identifier.

## 5. Frozen Expert Contract

### 5.1 Job identity

One logical job is identified by:

```text
parent_run_id + parent_fencing_token + logical_key
```

`logical_key` is the canonical hash of plan ID, plan version, step ID, role, and
effective policy hash. Re-submission with the same key and input hash reuses the same
job. Re-submission with the same key and a different input hash is a protocol conflict.
A new parent fencing token always creates a new authority epoch and cannot reuse a
previous epoch's accepted result.

### 5.2 Payload

`ExpertJobPayload` is Pydantic-validated with `extra="forbid"` and contains:

- protocol version, role, plan step, goal, constraints, and ancestor results;
- learner scope: learner ID, knowledge ID, current input, and student inputs;
- effective policy hash and a server-derived practice policy;
- redacted knowledge state, learner profile, review queue, knowledge context, and
  optional quiz context;
- stable memories and authorized history records with source reference, role,
  timestamp, knowledge scope, and full redacted content;
- an explicit set of verified source references;
- `ExpertBudget`: maximum model calls, tool calls, output tokens, context tokens,
  retry attempts, and absolute `deadline_at`;
- parent trace/span IDs needed for causal tracing.

The payload never contains:

- a database URL, API key, request header, secret, or provider credential;
- SQLite objects, repositories, `LearningHistory`, graph instances, callbacks, or
  `ContextVar` values;
- mutable parent collections such as `ctx.steps`, `ctx.events`, or tool caches;
- private model reasoning;
- a `time.monotonic()` value.

`deadline_at` is a PostgreSQL `TIMESTAMPTZ`. Every process compares it with the
PostgreSQL clock at a state transition and with local UTC only for early cancellation.
The database decision is authoritative. The parent attempt persists
`parent_deadline_at`, derived from PostgreSQL time when claimed; an expert deadline
cannot exceed it.

### 5.3 Snapshot tools

Expert processes do not query the learner store. `SnapshotToolExecutor` exposes a
role-specific subset of existing read tools over the immutable payload:

- `search_learning_history` searches only included records and returns candidate
  references;
- `read_learning_history` returns full content only for an included reference;
- `get_knowledge_context`, `get_learner_profile`, and `get_review_queue` return
  snapshot values.

Write tools and delegate tools are absent. Unknown tools, duplicate call IDs, malformed
arguments, out-of-scope source references, and role-incompatible actions are rejected.
Snapshot construction uses the existing public-data/output-safety rules and a final
recursive deny-list scan for secret-shaped keys.

## 6. Parent Runtime Decomposition

The current `SpecialistRuntime` is split by responsibility:

1. `ExpertSnapshotBuilder.freeze(ctx, step, plan, authority)` creates and hashes the
   immutable request.
2. `ExpertGateway.execute(request)` chooses inline or durable execution and returns a
   terminal envelope with total usage.
3. `ExpertEngine.execute(request, service)` runs the bounded model/tool loop solely
   against snapshot tools. It is shared by inline and remote execution.
4. `ExpertResultAdopter.adopt(ctx, step, plan, envelope)` revalidates identity, role,
   policy hash, parent authority, source scope, current source availability, schema,
   status, and proposed actions.
5. `SpecialistRuntime.run` allocates/restores parent budget scope, invokes the four
   components, charges all reported usage, and emits parent trace events.

`TutorDraft` is a separate strict schema:

```text
status: completed | needs_input | failed
content: non-empty only when completed
source_refs: bounded list
needs_input: non-empty only when needs_input
uncertainty: bounded string
error_code: stable allow-list
```

It cannot carry generation mode, dialogue state, a plan, action receipt, quiz, or any
other public-response metadata. The parent validates citations and calls
`TutorRuntime.reply(draft.content)`.

Inline mode uses the same frozen request, engine, and adopter. This prevents local and
remote semantics from drifting and keeps offline tests deterministic.

## 7. PostgreSQL Model

Five tables form the expert execution plane.

### 7.1 `distributed_expert_jobs`

Key fields:

- `id`, `parent_run_id`, `parent_fencing_token`, `logical_key`;
- `role`, `input_hash`, `policy_hash`, `payload`;
- `status`, `attempt_count`, `max_attempts`, `error_code`;
- `deadline_at`, `created_at`, `updated_at`, `completed_at`.

Constraints:

- unique `(parent_run_id, parent_fencing_token, logical_key)`;
- indexed `(status, role, updated_at)` and `(parent_run_id, created_at)`;
- payload size is checked before insert;
- terminal statuses are `completed`, `terminal_failed`, `exhausted`, `cancelled`,
  and `parent_stale`.

### 7.2 `distributed_expert_leases`

One row per job:

- `job_id`, `owner`, monotonic `fencing_token`, `expires_at`, `updated_at`.

Every claim increments the token. Renew, success, failure, and cancellation require
the current owner/token and a live database-clock lease.

### 7.3 `distributed_expert_results`

Append-only attempt evidence:

- `id`, `job_id`, `expert_fencing_token`, `worker_id`;
- `disposition` (`accepted` or `rejected`) and optional `rejection_code`;
- `draft`, `usage`, `diagnostics`, `created_at`.

A PostgreSQL partial unique index permits at most one accepted result per job.
Rejected late or stale results are retained. They do not update the job or parent.
The reaper later closes an orphaned job under the normal lock protocol.

### 7.4 `distributed_expert_outbox`

Fields include `event_key`, `topic`, `payload`, `available_at`, `published_at`,
`publish_attempts`, and timestamps. `available_at` supports bounded exponential
backoff without sleeping in a transaction.

### 7.5 `distributed_expert_inbox`

Records `(consumer, message_key)` once for delivery diagnostics. As in M1, an inbox
hit never proves business completion and cannot replace a PostgreSQL claim.

### 7.6 `distributed_worker_registry`

This cross-plane table powers the Workers view:

- `worker_id`, `process_type`, `instance_id`, `status`;
- `current_run_id`, `current_job_id`, `capabilities`, `metadata`;
- `started_at`, `last_heartbeat_at`, `stopped_at`.

Processes upsert at startup and heartbeat on a fixed interval. API responses derive
`healthy`, `stale`, or `stopped` from database time. Redis consumer membership is not
used as a health signal.

## 8. State Machines

### 8.1 Expert job

```text
accepted -> queued -> running -> completed
                    -> retryable_failed -> queued
                    -> terminal_failed
                    -> exhausted
                    -> cancelled
                    -> parent_stale
```

The parent run may be `running` or `waiting_expert`. Creating the first active job for
the current parent token sets it to `waiting_expert`. Adoption or terminal failure
returns it to `running` only when the same parent token is still live and no other
active job exists.

### 8.2 Result disposition

An Expert Worker appends an accepted result only if, in one transaction:

- the parent Run and Run lease still match the job's parent token;
- the parent lease is live and the Run is active;
- the job and Expert lease match the worker's token and are live;
- the job is not past its database deadline;
- no accepted result exists;
- role, input hash, policy hash, and output schema match.

Otherwise it appends `rejected` with a stable code such as
`parent_stale`, `expert_token_stale`, `deadline_expired`, `result_conflict`, or
`schema_invalid`.

## 9. Locking and Fencing

All transactions that touch both planes lock rows in this order:

```text
distributed_runs
-> distributed_leases
-> distributed_expert_jobs
-> distributed_expert_leases
-> distributed_expert_results
```

Repository methods never acquire an earlier lock after a later lock.

There are two independent tokens:

- parent Run token proves authority to await and adopt a job;
- Expert Job token proves authority to execute and append an accepted result.

Both are required for acceptance. A valid expert token cannot compensate for a stale
parent, and a valid parent cannot adopt a result from a stale expert attempt.

The parent's PostgreSQL polling is the source of truth. Redis result notifications
may reduce latency later but are not required for correctness.

## 10. Admission and Backpressure

Admission is based on PostgreSQL state, not Redis pending entries.

- job creation obtains transaction-scoped advisory locks for the parent run and role;
- at most one active expert job is allowed per parent Run;
- configurable per-role running limits bound provider concurrency;
- configurable per-role queued limits and a global payload-byte limit bound backlog;
- Expert Worker claim obtains the role advisory lock and counts current running jobs;
- denied claims remain queued and receive a delayed outbox event;
- a full queue fails fast with `expert_backpressure` before a job is accepted.

Default limits are intentionally small for the interview profile: one active job per
run, two running jobs per role, and fifty queued jobs per role. Limits are settings,
validated as positive integers, and exposed in health/metrics.

Before a new parent fencing epoch admits work, it atomically marks active jobs from
older parent tokens `parent_stale`; an abandoned old job cannot block takeover.
Rejecting a job whose role is outside a Worker's advertised capabilities does not
increment attempt count or consume retry budget.

Once a durable job has been accepted, the parent does not silently run the same step
inline. That could double provider cost and create two competing drafts. Inline
fallback is allowed only when durable mode is disabled or job creation fails before
PostgreSQL acceptance.

## 11. Deadline, Retry, and Usage Semantics

- A job's absolute deadline cannot exceed the parent deadline or the configured expert
  maximum.
- Workers check the database deadline before claim and before result acceptance.
- Retryable failures are provider timeout, connection failure, 408/425/429, and 5xx.
- Schema, authorization, source, policy, budget, and invalid-tool failures are
  terminal.
- Retry delay is capped exponential backoff with deterministic jitter derived from
  job ID; attempts never exceed the job's frozen maximum.
- Reaping an expired expert lease creates a new queued attempt only when the parent
  token and deadline remain valid.
- Parent cancellation or lease loss prevents result acceptance and adoption.

Each attempt records model calls, tool calls, input/output tokens when available,
estimated cost, provider/model, and whether the call outcome was uncertain. The job
budget is cumulative across attempts. A retry receives only the remaining allowance.
The parent charges total terminal usage, including failed attempts, before continuing.
Unknown usage is retained as unknown rather than replaced with zero.

Database acceptance and parent adoption are separate decisions. A result accepted
under live execution authority can still fail adoption if a cited source is deleted or
the pinned policy becomes unavailable before the parent reads it. The accepted row is
retained and an `expert.adoption_rejected` span records the reason.

## 12. Dispatcher, Worker, and Reaper

The existing `RedisRunBroker` implementation is reused as a generic stream transport
but instantiated with a separate expert stream and consumer group.

- `ExpertDispatcher` publishes due expert outbox rows and marks them after publish.
- `ExpertWorker` records inbox delivery, claims a job, heartbeats its lease, runs
  `ExpertEngine`, and submits the result.
- `ExpertReaper` expires expert leases, detects stale parents/deadlines, consumes retry
  budget, and writes delayed retry outbox rows.
- all three register process heartbeats;
- Expert Workers advertise supported roles; a worker refuses a job outside its
  capabilities without consuming an execution attempt.

The CLI adds `expert-dispatcher`, `expert-worker`, and `expert-reaper`. Compose starts
two Expert Workers so a real process kill can demonstrate takeover.

## 13. Observability

Durable spans extend the M1 trace:

```text
run.attempt
  -> coordinator.step
    -> expert.enqueue
    -> expert.wait

expert.attempt
  -> model.call
  -> snapshot_tool.call
  -> expert.result

coordinator.step
  -> expert.adopt
  -> parent.action
  -> tutor.reply
```

Cross-process spans carry the parent trace ID and an explicit parent span ID from the
frozen payload. Public attributes contain IDs, role, attempt, status, duration, usage,
and rejection code, never full prompts, history content, secrets, or reasoning.

Metrics include queue depth and age by role, active jobs, attempt duration, lease
loss, takeover, retry, backpressure, accepted/rejected/late result counts, parent wait
duration, snapshot bytes, usage, and worker freshness.

## 14. Read-only Ops API and Console

The distributed control plane adds:

```text
GET /ops/runs
GET /ops/runs/{run_id}
GET /ops/runs/{run_id}/trace
GET /ops/expert-jobs
GET /ops/expert-jobs/{job_id}
GET /ops/workers
```

All list endpoints use bounded cursor pagination and filter allow-lists. Payloads,
prompts, full history text, secrets, and private reasoning are never returned.
Expert-job detail exposes hashes, budget, usage, source-reference IDs, attempts,
dispositions, and rejection codes.

The React application serves a separate `/ops/` surface and leaves the learning
experience unchanged:

- **Runs**: state, attempts, owner, lease freshness, expert jobs, latency, and usage;
- **Trace**: expandable causal tree with duration, status, process, and fencing token;
- **Workers**: process type, capabilities, current assignment, heartbeat age, and
  recent failure.

The console uses restrained operational styling, dense tables, explicit empty/error/
loading states, and responsive detail drawers. It has no mutation buttons.

## 15. API and Compatibility

- Existing learning and distributed submission contracts remain backward compatible.
- Durable expert mode is opt-in through `DISTRIBUTED_EXPERTS_ENABLED`.
- The setting is valid only when the distributed Run Plane is enabled.
- Local API, offline evaluation, and unit tests default to inline expert mode.
- Existing `AgentResult` remains the Coordinator's adopted Assessment/Curriculum
  contract.
- Existing saved `LearningPlan` rows require no migration.
- New PostgreSQL tables are created through the current metadata bootstrap in M2;
  production migration tooling remains a later deployment concern and is documented.
- The parent keeps the single-writer SQLite lock while waiting for an expert. This
  preserves M1 safety but serializes learner-state execution during remote latency;
  the benchmark reports this limitation rather than claiming horizontal state writes.

## 16. Failure Matrix

| Failure | Required behavior |
| --- | --- |
| Parent writes job, dispatcher dies | committed outbox is published later |
| Dispatcher publishes, dies before marking | duplicate delivery; one DB claim |
| Expert Worker dies before result | expert lease expires; another worker gets a new token |
| Old Expert Worker returns late | append rejected result; no job/parent update |
| Parent Run Worker dies while expert runs | parent token becomes stale; result rejected |
| Parent is cancelled while waiting | no acceptance/adoption; evidence retained |
| Redis is unavailable | PostgreSQL job/outbox remains; recovery republishes |
| Two expert results race | partial unique index and locks allow one accepted result |
| Result cites omitted/foreign source | parent adopter rejects it |
| Worker exceeds frozen budget | terminal budget failure; usage retained |
| Queue limit is reached | fail before job acceptance with retryable backpressure |
| Registry heartbeat stops | worker appears stale; no false health from Redis |
| Ops API receives broad/unbounded query | validation rejects or caps it |

## 17. Verification

### 17.1 Unit and repository tests

- strict contracts, stable hashes, payload redaction, size limits, and UTC deadlines;
- job idempotency/conflict, state transitions, lock order, dual fencing, and one
  accepted result;
- admission under concurrent claims, delayed outbox retries, and cumulative budgets;
- snapshot tools cannot read omitted or foreign data and expose no write operation;
- Assessment/Curriculum/Tutor drafts pass through the same inline and remote adopter;
- Coordinator charges usage, validates current sources, executes actions only in the
  parent, and creates the public Tutor reply only in the parent;
- Ops serializers never return payload content.

### 17.2 Real PostgreSQL/Redis process tests

- two Expert Workers compete for one job;
- kill the active Expert Worker during a deterministic pause, wait for lease expiry,
  and prove takeover by a higher expert fencing token;
- kill the parent Run Worker while the expert is running, then prove the late result
  is stored as rejected and a new parent attempt cannot adopt it;
- publish duplicate messages and prove one accepted result and one learner-state
  commit;
- cancel a waiting run and prove no late draft is adopted;
- verify worker heartbeats and cross-process trace parentage.

### 17.3 Regression and frontend checks

- all existing non-distributed tests pass;
- all M1 distributed tests pass unchanged;
- frontend TypeScript build passes;
- Playwright checks `/ops/` at desktop and mobile widths for loading, populated,
  empty, and error states, with no overlap or clipped labels;
- Compose configuration parses and all distributed services become healthy.

### 17.4 Interview evidence

The demonstration records:

- run/job IDs, both parent and expert fencing tokens, and process IDs;
- attempts and accepted/rejected result rows;
- trace tree and metrics before/after process kill;
- learner-store effect count proving the expert never writes business state;
- p50/p95 enqueue-to-start and end-to-end latency at bounded concurrency;
- exact code revision, configuration, test command, request count, model, and cost.

## 18. Completion Criteria

M2 is complete only when:

1. a real Run Worker delegates all three draft roles through separate Expert Worker
   processes when enabled;
2. no Expert Worker has a code path or credential that can mutate learner state;
3. dual fencing and the accepted-result uniqueness rule pass real concurrent tests;
4. worker-kill, parent-kill, cancellation, duplicate delivery, and Redis outage paths
   leave auditable terminal evidence;
5. the Ops Console renders real PostgreSQL-backed run, trace, job, and worker data;
6. existing offline, single-process, M1, package, and frontend checks still pass;
7. the implementation, frozen protocol, test evidence, benchmark, and cost ledger are
   committed and pushed without secrets or transient databases.
