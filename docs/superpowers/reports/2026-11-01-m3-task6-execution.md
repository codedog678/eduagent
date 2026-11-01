# M3 Task6 Execution Evidence

Status: implemented, pending independent review. Task7 is not started.
Branch: `feature/m3-trusted-policy-promotion`.
Base revision: `5b8c2b7`.

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
