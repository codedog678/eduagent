# M3 Task6 Execution Evidence

Status: Task6 independently reviewed and accepted after the corrections below.
Task7 is not started.
Branch: `feature/m3-trusted-policy-promotion`.
Base revision: `5b8c2b7`.

## Independent Review Closure

The first Task6 review found a completed-PostgreSQL-step replay bypass and a
startup DDL deadlock. Task6 was not accepted on its initial green suite.

- `ed6652641bf64f080914a87edf85cbea9f4fc35e` closes the result-binding bypass.
  Independent review passed with 216 relevant tests, zero skips and one
  startup-owned test deselected, plus supplementary worker/outbox and SQLite
  replay probes. Cached and fresh results now fail closed at execution and
  repository commit boundaries.
- `b391d94d6ee4ec2237964caf52a6c429a36807e0` separates explicit migration from
  ordinary process startup. Independent review passed with 24 real
  PostgreSQL/Redis startup tests, zero skips, and two CI-settings probes.
  Startup core and test blobs matched the reviewed commit.
- The final CI-style distributed/process matrix reports 576 passed, zero
  skips. The preceding frozen combined backend run reports 1129 passed, zero
  skips. Counts overlap and are not additive. See the
  [startup correction report](2026-11-01-m3-schema-startup.md) for commands,
  source hashes, historical failures and verification boundaries.

Both review findings are closed. Migration still requires drained traffic;
Docker validation remains static YAML validation. Legacy payloads/results
remain historical evidence and are not silently rebound. No formal policy
qualification, model evaluation, Shadow implementation or broader project
completion is claimed by Task6 acceptance.

## Implemented Boundaries

- Workers pass `RunClaim.policy_binding`, not the stale plan symbol `binding`,
  to the executor. Authority, RunContext, traces and SQLite execution metadata
  carry deployment, policy hash, cohort, namespace and rehearsal identity.
- Distributed Harness execution requires the trusted binding. Pending quiz,
  plan and pending-history pins must agree before execution. Pinned components
  do not consult the file registry or local policy-health monitor.
- Environment capability checks run inside the locked claim transaction and
  before business execution. The store router derives paths from server
  configuration, validates ASCII rehearsal namespaces and rejects root escapes.
- Runtime and CLI reuse Task5's dedicated topic routes. Compose has two
  rehearsal workers with a dedicated shared volume and no production mount;
  production workers do not mount rehearsal state.
- Snapshot construction, locked-parent enqueue/replay, persisted expert jobs,
  result acceptance and adoption validate inherited identities. Inline expert
  execution also rejects missing or mismatched distributed identity; explicitly
  local unbound execution remains supported.
- Existing fencing, learner, source and deadline checks remain active.
  Real PostgreSQL/Redis tests run the worker, executor and Harness after a
  head change for first execution, retry and lease takeover.

The dispatcher required no duplicate implementation. Expert deployment and
namespace columns already existed and did not require a new schema edit.

## Verification

Interpreter: `/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python`.
Working directory: `/Users/bytedance/Documents/trae_projects/eduagent-m3`.
Each infrastructure run used a fresh database on local PostgreSQL port 55432,
an EXIT `dropdb` trap and Redis port 56379, database 0.

```bash
PYTHONPATH="$PWD/python" TZ=UTC \
  DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$db" \
  DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:56379/0" \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m pytest python/tests -q --tb=short
```

Final code run: **958 passed, 0 skipped**, 73.65 seconds.
One historical `PytestCollectionWarning`: the v2 helper class `TestAgent`
has an `__init__` constructor and is not collected as a test class.

Separate final `python/tests/integration` run with the same environment:
**5 passed, 0 skipped**, 20.01 seconds. Both final runs include the
explicit worker-startup readiness barrier described below.

Earlier distributed + Harness + RSI policy + coordinator matrix:
**435 passed, 0 skipped**, 38.20 seconds, before the final inline-expert guard.
After that guard, expert-engine + coordinator verification:
**46 passed, 0 skipped**, 0.55 seconds. Counts overlap; they are not additive.

TDD evidence: initial pinning/router/worker/executor tests had 12 failures;
expert inheritance/result tests had 10 failures; the final direct inline
consumer tests had 7 failures and 15 passes before the guard. These failures
demonstrated execution or acceptance of missing/mismatched identity.

`git diff --check`: passed. Ruby `YAML.safe_load(..., aliases: true)` and
explicit assertions passed for both rehearsal-worker commands, roots and
mounts and both production-worker mounts. This is YAML validation, **not
Docker execution**. Docker is unavailable and was not installed.

## Failed Runs And Rollout Limits

- The first process-suite attempt failed four tests at admission because its
  fresh test fixture omitted the production bootstrap. The fixture now uses
  the existing test-only bootstrap helper. No qualification campaign,
  release-eligible candidate or production configuration was fabricated.
- Subsequent process runs alternated between a green run and a parent/expert
  startup timeout. A diagnostic rerun captured PostgreSQL
  `DeadlockDetectedError` in `upgrade_m3_schema` at
  `ALTER TABLE distributed_expert_jobs ADD COLUMN IF NOT EXISTS deployment_id`.
  Startup DDL conflicted with live parent polling. This existing online
  startup/migration limitation is not fixed by Task6.
- The parent-kill process test now waits for the real expert CLI process to
  register after startup DDL, then starts the parent. It still kills the real
  parent, rejects the late result and verifies no accepted result. This proves
  fencing under completed startup, not online DDL safety.
- Deployment must drain active work and sequence startup/schema upgrade before
  accepting new parent traffic. Starting another migration-running process
  against live expert polling remains unsupported by this evidence.
- Backfilled M2 expert columns do not make old immutable payloads trusted.
  Missing payload identity fails closed at claim, result acceptance and
  terminal lookup. Old SQLite results lacking matching deployment/hash/
  namespace return 409 on distributed replay; neither payload nor stored
  result is silently rewritten. Drain legacy in-flight work before upgrading
  and retain old results as historical evidence rather than rebind them.
- These are deterministic/template-backed engineering tests, not new model
  evaluation, policy release qualification, Docker qualification or evidence
  that Task7 health observations and promotion monitoring are implemented.

## Task6 Review Correction Evidence

Corrective base: `e05552ac93fec9b6448a645d90f7eb1980ced12a`.
Only the `eduagent-m3` worktree was edited. This is a new corrective commit,
not an amendment or a push. The approved Task6 plan and design section 5.4
remain the contract; the plan's metadata-free executor spy is not a valid
business result under that contract.

### Corrected Commit Boundaries

- `result_identity.py` validates exactly deployment, effective policy hash,
  cohort, state namespace and rehearsal ID against the frozen persisted Run
  binding. Missing keys fail closed, including a missing production rehearsal
  ID where the contract requires explicit null. It adds no request-ID,
  learner-ID, attempt-ID or distributed/local Run-ID equivalence requirement.
- Worker validation covers fresh executor results and completed PostgreSQL
  step results before any commit API or committing transition. Cached null,
  malformed, legacy and explicitly mismatched results produce terminal
  `ProtocolIdentityError`, not retry work.
- `complete_step` validates both the caller result and a completed step's
  cached result under the locked Run transaction. `complete` independently
  validates the caller result before any Run, attempt or lease mutation.
  Rejection rolls back atomically. Existing lease, step-token and input-hash
  fencing remain authoritative; valid completed-step replay preserves its
  original body, finish time and token.
- Pinned SQLite replay reuses the validator, preserving HTTP 409 and stored
  historical evidence. Explicit local unbound replay is unchanged.
  Real `LearningTaskExecutor` already emits all five fields. Test executors
  now emit valid execution metadata instead of weakening the validator.

Real PostgreSQL tests cover both production and rehearsal, each missing or
wrong field, absent/malformed execution metadata, legacy deployment/namespace
omissions, direct repository rejection, cached takeover with zero executor
calls and no public Run result, no new retry outbox, duplicate delivery, and
valid cached takeover after a head change. They also assert the worker never
calls either commit API or the committing transition for invalid results.

### Corrective Test Runs

All runs used the interpreter and real infrastructure above, unique databases
created with `createdb` and removed by an EXIT `dropdb` trap, `TZ=UTC`, PostgreSQL
55432 as `postgres`, and Redis 56379 database 0. `PYTHONPATH="$PWD/python"`
points only to this worktree's Python source, not the main checkout's source.
Counts overlap and must not be summed.

| Run | Result | Seconds | Evidence Boundary |
| --- | --- | --- | --- |
| Initial red: identity + pinning | 145 failed, 24 passed | 26.33 | Included fixture mistakes: frozen admission clock used for live leases, missing reaper argument and pre-existing takeover retry outbox |
| Corrected red: identity + pinning | 144 failed, 25 passed | 27.90 | Real database lease time; invalid results accepted by both repository APIs and fresh/cached workers; cached null incorrectly retried |
| Initial green: identity + pinning | 169 passed | 28.36 | Shared validator implemented |
| First required matrix | 1 failed, 588 passed | 70.82 | One stale fake-executor assertion expected a metadata-free body |
| Required matrix after expectation update | 589 passed | 69.95 | Before final stale-step error-order test and concurrent startup edits |
| Process integrations | 5 passed | 22.93 | Before final stale-step ordering adjustment and concurrent startup edits |
| Stale-step ordering red | 1 failed | 0.66 | Identity validation preceded the running step's stale-token fencing error |
| Final owned-file focused regression | 217 passed | 35.96 | Includes corrected fencing order and both extra replay/fencing tests; owned-file hashes identical before/after |
| Concurrent full backend attempt | 6 failed, 1096 passed, 6 setup errors | 111.56 | Startup-dependent fixtures lacked the concurrently introduced schema marker; whole-source hash changed during the run; not final combined verification |

There were no skips in these runs. The full backend attempt retained the
historical `TestAgent` collection warning. The first red run is not presented
as clean bypass evidence; the corrected red run is.

Exact test selections, with the common runner below:

```bash
# Red and first green:
run_task6_tests python/tests/distributed/test_business_result_identity.py \
python/tests/distributed/test_policy_pinning.py

# Required matrix:
run_task6_tests python/tests/distributed \
python/tests/test_learning_harness.py \
python/tests/test_rsi_policy_runtime.py \
python/tests/test_coordinator_runtime.py

# Process integrations:
run_task6_tests python/tests/integration

# Stale-step ordering red:
run_task6_tests python/tests/distributed/test_business_result_identity.py::test_unclaimed_running_step_still_rejects_stale_token_before_identity

# Final owned-file focused regression:
run_task6_tests python/tests/distributed/test_business_result_identity.py \
python/tests/distributed/test_policy_pinning.py \
python/tests/distributed/test_repository.py \
python/tests/distributed/test_worker.py \
python/tests/distributed/test_expert_integration.py \
python/tests/distributed/test_instrumentation.py

# Concurrent full backend attempt:
run_task6_tests python/tests
```

```bash
run_task6_tests() (
  set -eu
  db="m3_task6_corrective_$(date +%s)_$$"
  createdb -h 127.0.0.1 -p 55432 -U postgres "$db"
  trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$db"' EXIT
  PYTHONPATH="$PWD/python" TZ=UTC \
    DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$db" \
    DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:56379/0" \
    /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
    -m pytest "$@" -q --tb=short
)
```

The first red used `--tb=line`, the corrected red used `--tb=no`, and all
remaining runs used `--tb=short`.

### Tested Source And Limits

Final owned-file focused run: SHA-256 of the ordered `git hash-object` output
was identical before and after:
`0af8fea141efb9091147cb2a37cb7ad2f7f3f5601ebccca0cb9e574a5f1e1d17`.
The file order was:

```text
python/core/distributed/result_identity.py
python/core/distributed/repository.py
python/core/distributed/worker.py
python/core/harness.py
python/tests/distributed/helpers.py
python/tests/distributed/test_business_result_identity.py
python/tests/distributed/test_policy_pinning.py
python/tests/distributed/test_repository.py
python/tests/distributed/test_worker.py
python/tests/distributed/test_expert_integration.py
python/tests/distributed/test_instrumentation.py
python/tests/integration/test_expert_failover.py
```

Full backend attempt: HEAD was `e05552ac93fec9b6448a645d90f7eb1980ced12a`
both before and after, with uncommitted Task6 and parallel startup changes.
The SHA-256 of sorted `rg --files python` file checksums followed by the
`docker-compose.yml` checksum changed from
`22bd2f7fe4d7d8a9020f95608c3a0c0d288620c6ce3a9f6e4b19511ef8530068` to
`424fd0a4d96b42126ca0f978acec31f7c88c4f0c70009d1764f5e825a00a66c9`.
The runtime, CLI and Compose blob IDs remained, respectively:

```text
dcc80fcf48707280d95108bd671144c05ca20d46
5bbcfba70a69176aa37c23d34cf8b608885717d6
1497f150fbdde3fa3180f0dc383fcaa09a22cfab
```

The startup failures reported `SchemaVersionMismatch`: missing/incompatible
schema marker, requiring the explicit drained `cli migrate` step. Six API
fixture setup errors, one runtime/pinning failure and five process failures
were recorded. No startup implementation or pre-migration fixture change is
included in this correction; the parent coordinates that follow-up after both
agents finish. Earlier 589/5 green counts are not evidence for the combined
startup patch. The 217 focused count identifies only unchanged Task6-owned
files, not a frozen snapshot of all concurrent files.

Legacy or forged cached results are retained, never silently rewritten or
rebound. Drain legacy in-flight work; this correction does not repair already
published historical results. Task7, model evaluation, release qualification,
Docker execution and startup rollout qualification remain outside this commit.

Manual staged-patch scope and secret review found no added credentials or
secret material. `git diff --cached --check` passed. Only the twelve owned
source/test paths listed above and this Task6 report are included; parallel
startup files and tests are excluded.

The separately authorized startup follow-up is documented in
[M3 Schema Startup Correction](2026-11-01-m3-schema-startup.md). It replaces
normal runtime startup DDL with a read-only schema marker check and explicit
drained migration, and corrects the startup-dependent fixtures for combined
verification. The historical runs and pending independent-review status above
are unchanged. Compose startup is not a claim of online migration safety.
