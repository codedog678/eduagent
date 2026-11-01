# M3 Schema Startup Correction

Branch: `feature/m3-trusted-policy-promotion`.
Recovery base: `ed6652641bf64f080914a87edf85cbea9f4fc35e`.
Only `/Users/bytedance/Documents/trae_projects/eduagent-m3` was edited.
Scope: corrective infrastructure for the approved workflow, not Tasks 7-10.
The preceding Task6 cached-result correction is retained unchanged except for
the necessary startup fixture adjustments. Task6 independent review remains
with the parent.

## Recovery Checklist

- [x] Inspect and retain the interrupted patch and its existing red evidence.
- [x] Reuse existing upgrades in an explicit, serialized, one-shot migration.
- [x] Require a matching version/hash marker on normal startup, without DDL.
- [x] Gate distributed Compose processes on successful one-shot migration.
- [x] Migrate only startup-dependent fixtures and clean their raw marker.
- [x] Verify targeted tests, real process failover and installed-wheel hashing.
- [x] Verify the frozen combined full backend matrix.
- [x] Reproduce the CI settings failure before the authorized fixture-only fix.
- [x] Make promotion settings test modes explicit without changing validation.
- [x] Verify the local/CI contracts module and complete real-service CI selection.
- [x] Review the named staged paths for scope, whitespace and secrets.

## Startup Contract

`DistributedRuntime.start` and `PromotionCommandRuntime.start` use a PostgreSQL
read-only transaction to check the singleton marker's version and contract hash.
Missing table/row, stale version/hash and changed runtime version/hash fail
closed with the drained migration command. They do not repair the schema.
Redis consumer-group setup follows the successful database check.

`python -m core.distributed.cli migrate` uses the existing M1 and M3 upgrades.
A PostgreSQL transaction-scoped advisory lock serializes concurrent migrators.
The marker is published only after successful DDL, backfills, constraints,
triggers and bootstrap; a failure rolls the transaction back. Migration is a
one-shot database operation, not a Redis client or a worker process loop.

The marker version is `3`. The contract hashes sorted PostgreSQL ORM table/index
DDL, the source of the two upgrade functions, builtin policy and threshold hashes.
`models.py` registers expert and promotion models with the shared metadata.
Fresh API, distributed CLI and promotion CLI imports all expose **22 tables**
and the same hash:

```text
0678f13efa7826db51b51d8e42ab41960821aabe6a36cb99b629b1ae7839c64a
```

The installed wheel retains `.py` sources for `inspect.getsource`; it produced
the same hash under each of those entrypoints. A real wheel CLI migration with
unreachable Redis exited successfully, and this worktree's source checker
accepted its marker. This checks a standard installed wheel, not bytecode-only,
source-stripped or frozen distributions.

## Fixture Changes

- `tests/distributed/test_api.py`: each application lifespan gets an isolated
  schema, actual migration before startup, and `DROP SCHEMA ... CASCADE` cleanup.
- `tests/distributed/test_policy_pinning.py`: only the runtime-routing test
  migrates; its `finally` explicitly drops the raw marker before `raw_repo`
  performs ORM cleanup.
- Both process failover modules migrate before real CLI startup. Their public
  schema fixtures explicitly drop the raw marker on reset and teardown.
  Migration supplies the real production bootstrap instead of inserting a
  duplicate test-only bootstrap. The existing worker-readiness barrier and all
  failover, fencing and accepted-result assertions remain intact.
- `raw_repo` and direct repository/upgrade tests are unchanged. There is no
  global/autouse migration and no fabricated marker. Legacy/backfill tests
  still exercise their intentionally pre-migration schemas.
- Promotion command replay tests mock the lifecycle, so they require no
  fixture change; the real promotion runtime has read-only startup coverage.
- `tests/distributed/test_promotion_contracts.py`: the parent separately
  authorized deterministic settings fixtures because the current CI selection
  needs to remain healthy. The disabled promotion prerequisite case explicitly
  sets `distributed_enabled=False`; all five settings constructions explicitly
  set `distributed_experts_enabled=False`, and the four enabled constructions
  retain `distributed_enabled=True`. Neither tested mode can inherit CI's flags.
  This is test compatibility, not a runtime settings behavior change; validation
  and the existing prerequisite, principal and secret-redaction assertions are
  unchanged.

CI's process integration job invokes these migrated fixtures. Its non-fixture
startup path is Compose, already gated on the migration service; no redundant
global CI migration was added.

## Historical Evidence

The interrupted agent's existing report recorded the following red evidence
before its startup correction: the current-schema SQL observer rejected
startup DDL/writes, and both barrier tests (`runtime` and `cli`) produced actual
PostgreSQL `DeadlockDetectedError`. Expert terminal polling held the job lock
and waited on Runs while startup DDL waited on expert jobs. PostgreSQL selected
the poll transaction as victim in that reproduction. Task6 separately recorded
a startup CLI exit-1 victim. No particular victim is required for the defect.
These historical red executions were **not rerun or newly claimed** here.

The interrupted report also recorded **33 passed, 0 skipped, 6.87s**, including
the unchanged promotion-schema-upgrade and expert-CLI tests. The parent supplied
an independent **21 passed, 0 skipped, 6.06s** startup/migration result.
Neither count is a combined full-backend verification.

The [Task6 report](2026-11-01-m3-task6-execution.md) records the concurrent
combined attempt: **6 failed, 1096 passed, 6 setup errors, 111.56s**, no skips.
Six API setups, one runtime-routing test and five process tests lacked the new
marker. Source changed during that run, so it is not frozen combined evidence.
The fixture corrections above address those startup boundaries.

## Recovery Verification

Interpreter: `/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python`.
Working directory: `/Users/bytedance/Documents/trae_projects/eduagent-m3`.
Each real-service run uses a fresh database created by `createdb`, an EXIT
`dropdb` trap, PostgreSQL **55432** as `postgres`, Redis **56379/0** and `TZ=UTC`.
`PYTHONPATH="$PWD/python"` selects only this worktree's source.

| Recovery Run | Result | Seconds |
| --- | --- | --- |
| Original startup/migration selection, before three import-order cases | 21 passed, 0 skipped | 4.48 |
| Affected fixtures, real process tests, startup/migration and unchanged upgrade/CLI regressions | 75 passed, 0 skipped | 31.21 |
| Full backend, no marker exclusions | 1129 passed, 0 skipped | 113.75 |
| Historical distributed CI selection before settings fixture fix | 575 passed, 1 failed, 0 skipped | 97.32 |
| Affected matrix with the same CI-style runtime flags | 75 passed, 0 skipped | 36.46 |
| Finalization red probe, both distributed flags true, before fix | 1 failed, 0 skipped | 0.25 |
| Finalization contracts module, both distributed flags false | 15 passed, 0 skipped | 0.23 |
| Finalization contracts module, both distributed flags true | 15 passed, 0 skipped | 0.24 |
| Finalization complete distributed CI selection, both flags true | 576 passed, 0 skipped | 96.98 |

Counts overlap and are not additive. The hot-start barriers use real expert
terminal polling held behind a locked parent. Runtime and the real rehearsal
CLI become ready while that poll remains blocked. SQL observers allow only
SELECT and `SET TRANSACTION READ ONLY` at startup. Migration tests cover fresh
and legacy schemas, idempotence, rollback and two real serialized CLI processes.

The full backend run had only the historical `PytestCollectionWarning` for
the v2 helper class `TestAgent` with an `__init__` constructor. HEAD was the
recovery base above; code changes were still uncommitted. The SHA-256 of sorted
`rg --files python` file checksums followed by the Compose checksum was identical
before and after the full run:

```text
cdbf171cbf467834d13fe2a1570916c99c499f74d0324e1912c21ca6a3e3d5bd
```

The executed digest command, before and after pytest, was:

```bash
{
  rg --files python | LC_ALL=C sort | xargs shasum -a 256
  shasum -a 256 docker-compose.yml
} | shasum -a 256
```

The retained runtime, CLI and Compose blobs are respectively:

```text
dcc80fcf48707280d95108bd671144c05ca20d46
5bbcfba70a69176aa37c23d34cf8b608885717d6
1497f150fbdde3fa3180f0dc383fcaa09a22cfab
```

Equivalent reproduction helper for the executed test subshells:

```bash
run_schema_tests() (
  set -eu
  db="m3_startup_verify_$(date +%s)_$$"
  createdb -h 127.0.0.1 -p 55432 -U postgres "$db"
  trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$db"' EXIT
  PYTHONPATH="$PWD/python" TZ=UTC \
    DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$db" \
    DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:56379/0" \
    /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
    -m pytest "$@" -q --tb=short
)

# Original selection now includes the three added entrypoint import-order cases.
run_schema_tests python/tests/distributed/test_runtime_schema_startup.py \
  python/tests/distributed/test_schema_migration.py

# Executed affected matrix:
run_schema_tests python/tests/distributed/test_api.py \
  python/tests/distributed/test_policy_pinning.py python/tests/integration \
  python/tests/distributed/test_runtime_schema_startup.py \
  python/tests/distributed/test_schema_migration.py \
  python/tests/distributed/test_promotion_schema_upgrade.py \
  python/tests/distributed/test_expert_cli.py

# Full backend, no marker exclusions:
run_schema_tests python/tests
```

The CI-style run enabled `DISTRIBUTED_ENABLED` and
`DISTRIBUTED_EXPERTS_ENABLED`, set both runtime and test URLs to the same fresh
database/Redis, and used template/lexical execution with memory workers disabled:

```bash
run_ci_schema_tests() (
  set -eu
  db="m3_startup_ci_verify_$(date +%s)_$$"
  createdb -h 127.0.0.1 -p 55432 -U postgres "$db"
  trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$db"' EXIT
  PYTHONPATH="$PWD/python" TZ=UTC \
    DISTRIBUTED_ENABLED=true DISTRIBUTED_EXPERTS_ENABLED=true \
    DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$db" \
    DISTRIBUTED_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$db" \
    DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:56379/0" \
    DISTRIBUTED_REDIS_URL="redis://127.0.0.1:56379/0" \
    LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
    /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
    -m pytest "$@" -q --tb=short
)

run_ci_schema_tests python/tests/distributed \
  python/tests/integration/test_distributed_failover.py \
  python/tests/integration/test_expert_failover.py

run_ci_schema_tests python/tests/distributed/test_api.py \
  python/tests/distributed/test_policy_pinning.py python/tests/integration \
  python/tests/distributed/test_runtime_schema_startup.py \
  python/tests/distributed/test_schema_migration.py \
  python/tests/distributed/test_promotion_schema_upgrade.py \
  python/tests/distributed/test_expert_cli.py
```

The sole historical CI-style failure was the then-unchanged
`test_promotion_settings_require_distributed_mode_and_redacted_secrets` at
`tests/distributed/test_promotion_contracts.py:227`. Its first `Settings`
construction omitted `distributed_enabled=False` and inherited the CI
environment's `true`, so the expected validation error was not raised.
The test, settings code and CI workflow had no diff against the recovery base
at that time. Isolated probes returned
**1 failed, 0.13s** with both distributed flags true and **1 passed, 0.11s**
with both false. That recovery run did not alter the environment-sensitive
settings test and was not green. The parent subsequently authorized the
necessary deterministic fixture correction recorded below; this historical
failure is retained rather than relabeled as passing.

```bash
PYTHONPATH="$PWD/python" TZ=UTC \
  DISTRIBUTED_ENABLED=true DISTRIBUTED_EXPERTS_ENABLED=true \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m pytest python/tests/distributed/test_promotion_contracts.py::test_promotion_settings_require_distributed_mode_and_redacted_secrets -q --tb=short
PYTHONPATH="$PWD/python" TZ=UTC \
  DISTRIBUTED_ENABLED=false DISTRIBUTED_EXPERTS_ENABLED=false \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m pytest python/tests/distributed/test_promotion_contracts.py::test_promotion_settings_require_distributed_mode_and_redacted_secrets -q --tb=short
```

### Authorized Finalization

Before editing, the first isolated probe above was rerun with both flags true
and reproduced **1 failed, 0 skipped, 0.25s**: `DID NOT RAISE` at line 227.
Only six explicit mode fields were then added to the five `Settings`
constructions in `test_promotion_contracts.py`. No settings runtime code or CI
workflow was changed.

The whole contracts module passed with both flags false (**15 passed,
0 skipped, 0.23s**) and with both flags true (**15 passed, 0 skipped, 0.24s**),
using the same interpreter, worktree `PYTHONPATH` and `TZ=UTC` as above:

```bash
PYTHONPATH="$PWD/python" TZ=UTC \
  DISTRIBUTED_ENABLED=false DISTRIBUTED_EXPERTS_ENABLED=false \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m pytest python/tests/distributed/test_promotion_contracts.py -q --tb=short
PYTHONPATH="$PWD/python" TZ=UTC \
  DISTRIBUTED_ENABLED=true DISTRIBUTED_EXPERTS_ENABLED=true \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m pytest python/tests/distributed/test_promotion_contracts.py -q --tb=short
```

The complete CI selection shown in `run_ci_schema_tests` above was then run
against actual PostgreSQL **55432** as `postgres` in the unique database
`m3_startup_finalize_ci_1793524736_51844` and actual Redis **56379/0**.
Runtime and test URLs matched; both distributed flags were true, with
template/lexical execution and memory workers disabled. Result: **576 passed,
0 skipped, 96.98s**, exit 0. The EXIT trap removed the database.

The same source/Compose digest command was identical before and after this
finalization CI run:

```text
d22bee229459d69b923184972586575ef27b6b4a611a915a48573b5b5f2c9c64
```

The runtime/CLI/Compose blobs above were rechecked and remain unchanged.
The earlier **1129 passed** full backend run and its distinct frozen digest
remain historical evidence for the retained startup patch. The full backend
was not rerun after this fixture-only correction; the current passing claim
is the complete **576-test distributed CI selection** and the local/CI contracts
module, not a new full-backend run. Counts overlap and are not additive.

Wheel commands: the same interpreter ran
`pip wheel ./python --no-deps --no-build-isolation --wheel-dir "$work/dist"`
and `pip install --no-deps --target "$work/install" "$work"/dist/*.whl`,
with a temporary directory under this worktree's `.superpowers`. Fresh Python
processes set `PYTHONPATH="$work/install"` and verified the actual imported
runtime path, both `inspect.getsource` calls and all three entrypoint hashes.
Then `python -m core.distributed.cli migrate` used the wheel path and a fresh
PostgreSQL database with `DISTRIBUTED_REDIS_URL=redis://127.0.0.1:1/0`.
The source checker ran with `PYTHONPATH="$PWD/python"` against that database.
The first ad-hoc checker used two asyncio loops and logged a disposal error
after a successful check; the corrected single-loop verifier reran cleanly.
Temporary wheel installation and its database were removed.

## Compose And Rollout

Ruby `YAML.safe_load(..., aliases: true)` assertions passed for the one-shot
command, `restart: "no"`, common database environment, healthy PostgreSQL
dependency, all **11** application-process migration gates and both pairs of
production/rehearsal commands, store roots and isolated mounts. Migration has
no Harness mount. This is **static YAML validation only**, not Docker execution.
Docker is unavailable and was not installed.

Migration requires API traffic and every worker/dispatcher/reaper to be drained.
The advisory lock serializes migrators, not online business traffic. Compose
will run its migration service on startup; its dependency gates do **not**
stop an already live deployment. Do not use `compose up` as an online upgrade.
After stopping ingress and allowing active work to drain, the explicit sequence
for this profile is:

```bash
docker compose --profile distributed stop \
  distributed-api run-dispatcher run-reaper run-worker-a run-worker-b \
  expert-dispatcher expert-reaper expert-worker-a expert-worker-b \
  rehearsal-worker-a rehearsal-worker-b
docker compose --profile distributed build distributed-migrate
docker compose --profile distributed run --rm distributed-migrate
docker compose --profile distributed up --build -d
```

Stop any external consumers sharing the database as well. A normal CLI hot
start against an already matching schema runs only the read-only startup
check and does not migrate. Missing/stale markers still require the drained
sequence. No online migration safety, Task7 work, model evaluation, formal
qualification or Docker rollout qualification is claimed.

## Commit Scope

Manual review covered the complete staged diff and all staged status entries
for exactly these twelve authorized paths:

```text
docker-compose.yml
python/core/distributed/cli.py
python/core/distributed/runtime.py
python/tests/distributed/test_api.py
python/tests/distributed/test_policy_pinning.py
python/tests/distributed/test_promotion_contracts.py
python/tests/distributed/test_runtime_schema_startup.py
python/tests/distributed/test_schema_migration.py
python/tests/integration/test_distributed_failover.py
python/tests/integration/test_expert_failover.py
docs/superpowers/reports/2026-11-01-m3-schema-startup.md
docs/superpowers/reports/2026-11-01-m3-task6-execution.md
```

No added credentials or secret material were found; secret-redaction test
values remain synthetic and unchanged. `git diff --cached --check` passed.
The staged source matched the tested worktree and there were no unrelated
staged paths. Settings runtime, CI workflow and ignore rules remain unchanged.
`git check-ignore -v --no-index` confirmed `.gitignore:55` excludes both report
paths under `/docs/superpowers/*`; both explicitly authorized evidence reports
were staged with `git add -f`, without altering ignore or Git configuration.
This is the finalizer's scope/secret review, not the parent's independent
startup or Task6 review.

The new corrective commit contains the retained runtime/CLI/Compose patch,
the two startup/migration test modules, the four necessary fixture modules,
the authorized deterministic promotion settings test fixture, this report and
a reference-only Task6 report update. No unrelated fixture, settings runtime,
CI workflow, Task7 or qualification change is included. No amendment, push or
Git configuration change is authorized or performed. Task6 independent review
remains with the parent; this finalization does not claim Task6 complete.
