# M3 Task8: Health Gates and Transactional Rollback

## Fresh SPEC Corrections and Current Freeze

This section supersedes the original implementation freeze below. The independent
SPEC review failed despite the original 407/1350 green tests; those tests did not
cover recovery starvation, legitimate Active baselines, full receipt/window
consumption validation, or unequal-count proportional windows. The original
review file and qualification-prerequisite report are parent-owned and unchanged.
This correction is Task8 only, not Task9, Task10, or independent review approval.

- Implementation base: `b9924dc`; approved correction follows docs-only parent
  `172bcb9` (including `e52c05d` and `86ceca2`).
- Recovery SQL excludes SQL/JSON-null bindings before the bounded limit, for
  both primary and Shadow. Unknown legacy hashes remain non-executable; no
  binding, usage, or release eligibility is fabricated. The regression creates
  205 old unbound terminals, performs two actual PostgreSQL migrations including
  unknown-hash artifact backfill, and proves newer valid terminals recover
  without repeated zero-persistence polls.
- Canary compares the last 50 candidates against a stable pool bounded to 50.
  It selects the largest qualified exact-proportion baseline deterministically,
  choosing newest rows within each rehearsal/operation bucket. Integer
  cross-multiplication enforces equal distributions, not equal sample counts.
  50/20 one-bucket and 40/10 versus 16/4 two-bucket samples qualify. Missing
  buckets, incompatible proportions, or fewer than 20 stable Runs hold.
- Active never accepts stable observations assigned to the Active deployment.
  It uses only stable keys from the passing predecessor Canary window actually
  consumed by the immutable activation approval. It replays receipt/window
  evidence and checks predecessor environment, candidate/stable policies,
  thresholds, audit/approval binding, rehearsal/operation/contract and observed
  and persisted chronology before activation. No global historical or
  production-stable query substitutes for this evidence.
- Receipt consumption requires an existing persisted passing window, complete
  canonical identity and evidence hashes, exact keys, aggregates, gate cohort,
  artifact protocol/runtime/source, version, thresholds, sample count and cost.
  It reloads bounded observations, recomputes aggregates/decision, and checks
  identity and chronology. The latest non-pass window and lifetime confirmed
  permission event still block consumption. Shadow retains strict paired parents.
- Real command-chain fixtures exercise healthy Canary-to-Active and strict
  equal-threshold latency rollback under 100% Active candidate assignment,
  including old candidate pinning and new stable assignment after rollback.
- Unknown cost/decisions, lifetime hard events, immutable pinning, lock fencing,
  typed actual SQLite permission diagnostics, schema checks/read-only startup
  and bounded metrics are unchanged and covered by the final targeted matrix.

Correction content digest (four owned Python files, sorted repository paths):
`d4e4f774402a8e9249f0623e544f9e28498a0ce461bf2e38b1759a41fb96dd91`.

```bash
shasum -a 256 \
  python/core/distributed/policy_health.py \
  python/core/distributed/promotion_repository.py \
  python/tests/distributed/test_policy_health_corrections.py \
  python/tests/distributed/test_promotion_repository.py | shasum -a 256
```

| Correction Round | Observed Result | Evidence |
| --- | --- | --- |
| Initial RED probe | 19 pass / 21 fail, 14.97 s; exit 1 | `2026-11-01-m3-task8-corrections-red.xml` / `.log`; includes fixture NULL-constraint, pending-delete flush and UUID setup errors, not all feature reproductions. Preserved unchanged. |
| Fixture-corrected RED | 19 pass / 21 fail, 14.83 s; exit 1 | `2026-11-01-m3-task8-corrections-repro-red.xml` / `.log`; recovery repeats `[200,200,200]` primary or `[400,400,400]` primary/Shadow with zero persisted. Active admission still encountered incompatible fixture fixed-components. |
| Active feature RED | 0 pass / 2 fail, 1.48 s; exit 1 | `2026-11-01-m3-task8-active-repro-red.xml` / `.log`; after fixing the artifact fixture, legitimate healthy and threshold-failing Active windows both hold against unchanged production code. |
| Development impact | 193 pass / 7 fail, 37.64 s | Original 40 correction cases green; older command-test helper still assumed receipt-only evidence. Fixture helper now creates real persisted windows; validator not weakened. |
| Scoped GREEN | 200 pass, 36.14 s; exit 0 | Correction, health and promotion suites; development result before ten additional edge cases. |
| Frozen targeted GREEN | 457 pass / 0 fail/error/skip, 91.68 s; exit 0 | `2026-11-01-m3-task8-corrections-targeted.xml` / `.log`; XML time 91.676 s. Includes all 50 new correction cases. |
| Frozen full backend GREEN | 1400 pass / 0 fail/error/skip, 258.60 s; exit 0 | `2026-11-01-m3-task8-corrections-full.xml` / `.log`; XML time 258.590 s. Same pre-existing `TestAgent` collection warning. |

No runtime/test edits occurred between the frozen targeted and full runs. Each
run used a new unique database, PostgreSQL 16 at `127.0.0.1:55432`, Redis
`127.0.0.1:56379/0`, the existing main `.venv/bin/python`, absolute m3 Python
`PYTHONPATH`, and `TZ=UTC`. The database variable was
`DISTRIBUTED_TEST_DATABASE_URL`, not `DATABASE_URL`. Each invocation created
and dropped its own database with the PostgreSQL 16 Homebrew executables and
an `EXIT` trap. Final catalog verification found no databases for any correction
run prefixes. No parent processes/databases were managed.

Final targeted command is the original 15-file matrix below plus
`tests/distributed/test_policy_health_corrections.py`; output names have suffix
`corrections-targeted`. Full command remains `python -m pytest tests -q
--tb=short`, with suffix `corrections-full`. Evidence remains under
`python/tests/distributed/evidence/`.

| Correction XML | SHA-256 |
| --- | --- |
| `2026-11-01-m3-task8-corrections-red.xml` | `e4d6343ffa0ab2f93e357e17b7e3826bd02fa99ce6297fb85f5dc195f6c5369c` |
| `2026-11-01-m3-task8-corrections-repro-red.xml` | `8385bf5a2892afc166d5ec3f5cad8dd1e3b732a840a453ddb5cf715a87719fd7` |
| `2026-11-01-m3-task8-active-repro-red.xml` | `d045575dbdc75f3fc2f159609f5082105b9b2cd3b29f41b893388aa3eca1fac1` |
| `2026-11-01-m3-task8-corrections-targeted.xml` | `2d78fb32edc1bfa41b17be0ae839588ff291fca45ccbf9f8873aac39580521aa` |
| `2026-11-01-m3-task8-corrections-full.xml` | `444d6a82f721b46ac82c72c47a6eab3d816366534292c05f8b52b4dffb1d5f86` |

These are deterministic engineering fixtures: no provider/model requests,
installation, Docker verification, push, or real release qualification occurred.
The formal JudgeV3 qualification chain is missing; configured credentials in
the primary workspace are not the blocker. Parent independent fresh SPEC then
CODE reviews remain pending. Broad M3 completion is not claimed.

## Scope and Freeze Identity

Historical original implementation evidence follows; it is not the current
correction freeze or proof that the four fresh SPEC failures were absent.

- Task8 implementation only. No Task9 Ops/UI work, deployment, live model evaluation, installation or push.
- Isolated worktree: `eduagent-m3`, branch `feature/m3-trusted-policy-promotion`.
- Test-freeze starting base: `4418e66`; final integration parent: `d50b25d` (parent documentation-only commit during testing). Parent-owned demo, benchmark, interview, frontend and prior report changes are not staged.
- Approved references: plan Task8 and design sections 9.1-9.3.
- Frozen Task8 Python content digest: `f46c6276d788144531e316f5b1a58d7e40b867cfa31f1671935e2eee0efc31c4`.
- Schema version: `3`; schema contract hash: `61f768276d7b939bd66d8c55f0f0c37c373dfb6dcc20849eb47cf1403b9f361e`.
- Default frozen thresholds hash: `35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f`.

The digest covers the 23 changed/new runtime Python files and five changed/new test files, ordered by repository-relative path. After checkout of the Task8 commit, reproduce with:

```bash
git show --pretty='' --name-only b9924dc -- '*.py' | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256
```

The report and XML/log evidence are excluded from this content digest. Final commit identity is the commit containing this report; no self-referential commit hash is embedded here.

## Implemented Contracts

| Area | Authoritative behavior |
| --- | --- |
| Observation | `record_run(run_id)` accepts no caller policy/cohort identity. PostgreSQL Run, attempts and committed business step supply frozen identity, terminal outcome, latency, actual server diagnostic and cumulative attempt usage. |
| Identity | Canonical hash of `{run_id, deployment_id, cohort, metric_contract_version}`. Terminal retries create one final observation; paired Shadow and stable primary share parent Run ID but coexist. |
| Recovery | Poll PostgreSQL for missing observations using full deployment/cohort/contract identity; Redis terminal notification is not required for recovery. |
| Shadow | Stable primary and Shadow must match parent Run IDs and immutable deployment. Shadow isolation maps to `isolated`, not an invented permission grant; absent structured evidence maps to `unavailable`. |
| Canary/Active | Canary uses same-deployment stable; Active uses only the gate-pinned predecessor Canary baseline. Same stable policy, rehearsal/operation distribution and metric contract; production stable cannot substitute. Missing qualified distributions hold, not unequal counts alone. |
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
