# M3 Task8: Health Gates and Transactional Rollback

## Scope and Freeze Identity

- Task8 implementation only. No Task9 Ops/UI work, deployment, live model evaluation, installation or push.
- Isolated worktree: `eduagent-m3`, branch `feature/m3-trusted-policy-promotion`.
- Test-freeze starting base: `4418e66`; final integration parent: `d50b25d` (parent documentation-only commit during testing). Parent-owned demo, benchmark, interview, frontend and prior report changes are not staged.
- Approved references: plan Task8 and design sections 9.1-9.3.
- Frozen Task8 Python content digest: `f46c6276d788144531e316f5b1a58d7e40b867cfa31f1671935e2eee0efc31c4`.
- Schema version: `3`; schema contract hash: `61f768276d7b939bd66d8c55f0f0c37c373dfb6dcc20849eb47cf1403b9f361e`.
- Default frozen thresholds hash: `35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f`.

The digest covers the 23 changed/new runtime Python files and five changed/new test files, ordered by repository-relative path. After checkout of the Task8 commit, reproduce with:

```bash
git show --pretty='' --name-only HEAD -- '*.py' | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256
```

The report and XML/log evidence are excluded from this content digest. Final commit identity is the commit containing this report; no self-referential commit hash is embedded here.

## Implemented Contracts

| Area | Authoritative behavior |
| --- | --- |
| Observation | `record_run(run_id)` accepts no caller policy/cohort identity. PostgreSQL Run, attempts and committed business step supply frozen identity, terminal outcome, latency, actual server diagnostic and cumulative attempt usage. |
| Identity | Canonical hash of `{run_id, deployment_id, cohort, metric_contract_version}`. Terminal retries create one final observation; paired Shadow and stable primary share parent Run ID but coexist. |
| Recovery | Poll PostgreSQL for missing observations using full deployment/cohort/contract identity; Redis terminal notification is not required for recovery. |
| Shadow | Stable primary and Shadow must match parent Run IDs and immutable deployment. Shadow isolation maps to `isolated`, not an invented permission grant; absent structured evidence maps to `unavailable`. |
| Canary/Active | Same immutable deployment, stable policy, rehearsal, operation distribution and metric contract; production stable cannot substitute for rehearsal stable. Incomplete matched windows hold. |
| Window | Sort by `(observed_at, observation_key)`, select the last 50 candidates, select bounded matched baselines and freeze exact keys, aggregates, threshold identity and deterministic window ID. |
| Arithmetic | Decimal mean cost and nearest-rank p95; relative increase uses frozen epsilon. Equal-to-maximum fails. Ordinary guardrails require at least 20 candidate and 20 matched stable Runs. |
| Missing evidence | Unknown cost or structured counts hold, never zero/pass. A separately known failure at qualified sample size still fails; confirmed permission failure is immediate regardless of missing evidence or baseline. |
| Hard failure | A bounded lifetime lookup freezes the earliest confirmed candidate permission event even if it fell outside the last 50 samples. An already committed hard event blocks old pass receipts before the next evaluator poll. |
| Receipt | Pass issues deployment/version/threshold/window-bound Shadow or Canary health receipt with the exact artifact protocol/runtime/source identity. Hold/fail issue none; existing qualification requirements remain enforced. |
| Rollback | Environment advisory lock plus head `FOR UPDATE`; recheck deployment/version/window; insert immutable failed-candidate-retaining `rolled_back` snapshot with traffic 0; CAS head, audit and Outbox in one transaction. Stable policy is unchanged. |
| Late events | Old accepted Runs retain candidate binding. New Runs use stable after rollback. Old-deployment observations create historical windows only; two evaluators of one window produce one rollback. |
| Faults | Only signed rehearsal candidate bindings allow frozen server latency or `RehearsalInjectedCommitFailure` immediately before commit transition. Persist injection separately from natural failure origin. |
| Permission | `ConfirmedPermissionViolation` is a typed server invariant diagnostic propagated through exception causes. Actual opened SQLite database metadata is checked against the frozen store capability before/after execution; ordinary request/tool denial is not a confirmed violation. |
| Metrics | Fixed-label local counters/histograms update only after committed observation/window/assignment work. Separate PostgreSQL gauges refresh at the metrics endpoint and cover cross-process persistent counts. No learner/request/Run/deployment/hash labels. |
| Startup | `policy-health` polls only when promotion is enabled. Ordinary runtime startup only checks version 3 and contract hash; explicit CLI migration performs real `ADD COLUMN`/indexes and transactional historical backfill before publishing the marker. |

`HealthDecision` preserves the existing external `rollback` enum. Internally windows store `fail`; `health_decision_from_window()` maps the wire enum without claiming that a head moved. Automatic rollback applies only to the current Canary/Active head. A failed Shadow window denies a gate but does not move the head.

## Usage and Decision Accounting

Primary execution now exports the same context evidence as isolated Shadow execution and persists it on the fenced PostgreSQL attempt. Coordinator schema decisions count real attempted parses, including invalid output. Accepted expert envelopes carry cumulative charged usage and actual structured draft/repair decisions. Inline expert usage is not counted twice.

Retry attempts are aggregated, including known charged calls and uncertain usage. Missing provider cost, missing attempt ledger, uncovered Coordinator/Tutor calls or uncertain expert usage keep cost unknown. Token counts remain independently known or unknown; no expert-only ledger is presented as a complete whole-Run bill. Unknown/invalid structured rate uses actual decision counts, not completed-Run counts.

The Task7 lock/lease protections are preserved: attempt/job/shadow blocking locks precede the final fresh database-time authorization, and Shadow cancellation drains the internal task before capability release. New usage and injection writes follow the same fenced attempt-lock discipline.

## Test Execution

All final implementation tests use the existing main-worktree Python virtual environment, not an installed replacement. PostgreSQL 16 and Redis are real local services; model/provider behavior is deterministic fixture behavior with no external model requests.

```bash
createdb -h 127.0.0.1 -p 55432 -U postgres "$DB"
trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$PWD"
export TZ=UTC
```

Each own integration run uses a separately created database and drops it at exit. Redis test streams use unique test identities. Parent test processes/databases are not managed by this implementation task.

| Round | Result | Evidence/status |
| --- | --- | --- |
| Initial feature RED | Health module/methods absent, `ModuleNotFoundError` | Observed before implementation; development check, not release evidence. |
| Development impact runs | 163 pass / 9 fail; then 103 pass. Wider run 332 pass / 1 fail. | Old Shadow summary assertions and a lock-wait snapshot barrier were corrected; the latter now checks actual PostgreSQL blocking PIDs/locks. Old exact expert usage assertion was updated. |
| Pre-final targeted | 376 pass in 75.98 s | Earlier development snapshot, superseded by the frozen run below. |
| Latest health/executor/promotion check | 164 pass in 21.39 s | Included lifetime hard-event lookup, receipt invalidation and actual opened-store diagnostic. |
| Final-matrix RED | 395 pass / 3 fail in 73.99 s; exit 1 | `2026-11-01-m3-task8-targeted-red.xml` and `.log`: old exact Shadow summary dictionaries omitted new structured fields. |
| Parent backend RED | 707 pass / 4 fail / 56 skip / 578 deselected in 18.39 s | `2026-11-01-m3-task8-parent-backend-red.xml` and `.log`: same three assertions plus `repository=object()` in runtime wiring fixture. Not full integration qualification. |
| Scoped correction | 22 pass in 0.38 s | `test_shadow_usage.py` and `test_expert_cli.py`; production behavior was not weakened. |
| Parent health supplement | 60 pass / 0 failure/error/skip in 10.73 s | Parent-reported independent unique-DB run, provisional rather than an independent release campaign. |
| Parent expanded non-distributed GREEN | 711 pass / 56 skip / 583 deselected in 13.96 s | Parent-reported supplemental check; the skipped PostgreSQL-dependent cases mean this cannot substitute for the frozen full-services matrix. |
| Frozen targeted | 407 pass / 0 failure/error/skip in 74.75 s; exit 0 | `2026-11-01-m3-task8-targeted.xml` and `.log`; XML suite time 74.746 s. |
| Frozen full backend | 1350 pass / 0 failure/error/skip in 235.36 s; exit 0 | `2026-11-01-m3-task8-full.xml` and `.log`; XML suite time 235.346 s. One pre-existing collection warning for helper `TestAgent` with a constructor. |

Final targeted database: `task8_final_targeted_20261101_b62e`; full database: `task8_final_full_20261101_c84b`. Source/tests did not change between these final runs. Both final databases and the final-matrix RED database were confirmed absent after their exit traps.

Evidence paths are under `python/tests/distributed/evidence/`. SHA-256 identities:

| XML | SHA-256 |
| --- | --- |
| `2026-11-01-m3-task8-targeted.xml` | `7682d880591cd3938753eab60d01120449232420699b0d071831345167c70473` |
| `2026-11-01-m3-task8-targeted-red.xml` | `d430836be174334cb7ec365fabd058ce5bd4f4e643e0dd231e741cd0ffb572c8` |
| `2026-11-01-m3-task8-parent-backend-red.xml` | `4c608575d137b4ed1398c585aac462527873b1f192e391a464984be9783be1da` |
| `2026-11-01-m3-task8-full.xml` | `849e8241e224fc1d2fd6de077835f10cfc26523aac3d04cdd6d4b26a378e5d31` |

A detached shell launcher failed to start an earlier test process (empty output); it was not counted as a test pass. Final runs use a detached `subprocess.Popen` launcher with observed output/exit markers and database cleanup.

Final targeted matrix, from `python/`:

```bash
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_instrumentation.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_shadow_worker.py \
  tests/distributed/test_shadow_usage.py \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_promotion_schema_upgrade.py \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_expert_engine.py \
  tests/distributed/test_expert_repository.py \
  tests/distributed/test_expert_cli.py \
  tests/distributed/test_runtime_schema_startup.py \
  tests/distributed/test_schema_migration.py \
  tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_executor.py -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-targeted.xml
```

Full backend command:

```bash
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-full.xml
```

## Evidence and Limits

- Data role: `test_fixture`; generated health-receipt fixture details explicitly carry `evidence_role=test_fixture` and `release_eligible=false`.
- No formally eligible JudgeV3 campaign currently exists. No eligible calibration/formal-holdout/harness qualification receipts were fabricated, and no real release was qualified.
- External model requests: 0. External model charge: USD 0. Fixture Decimal costs exercise arithmetic only; they are not measured provider expenditure. Actual Run cost remains unknown when its evidence is incomplete.
- These operational guardrails are deterministic reliability checks, not evidence of statistically significant educational improvement.
- The server diagnostic checks the known execution store boundary; it is not a claim of OS-level sandboxing or proof against every possible side effect.
- Old M3 rows lacking decision evidence remain unknown after migration. Historical immutable health windows are preserved, not rewritten into newly qualified gates.
- Process counters are process-local and restart-sensitive; authoritative persisted-count gauges are separate. Known-cost histograms omit unknown costs rather than counting them as zero.
- Docker was unavailable; no Docker or Compose runtime verification is claimed. Task8 does not add Task9 read-only Ops views or production hosting.
- Final independent spec review and code review are performed by the parent workflow after this new implementation commit. This report is implementation evidence, not those review approvals.

## Completion Checklist

- [x] Observation, matching window, deterministic evaluator and atomic rollback implemented.
- [x] Signed injection, honest usage/decision counters, real server permission hook and receipt invalidation implemented.
- [x] CLI/metrics and real explicit old-schema migration implemented.
- [x] Red evidence preserved; scoped assertion corrections pass.
- [x] Frozen targeted verified with 407 pass and no source changes.
- [x] Frozen full backend verified with 1350 pass and no source changes.
- [x] Final XML identities checked; sensitive configuration and parent-owned files excluded.
- [x] Task8-only implementation and evidence prepared for the new commit containing this report.
- [ ] Parent independent two-stage review, intentionally pending after implementation handoff.
