# Fresh Independent Task 8 CODE Review

Date: 2026-11-02. Completed result: **CODE PASS**.

## Findings

No confirmed P1, P2, or P3 findings remain within the approved full Task 8 scope.
This result comes from fresh source/test review, an independently executed full
backend suite, and newly written adversarial probes. It does not infer acceptance
from SPEC PASS or from the finished agent whose result was not delivered.
No Agent50 semantic review was performed. Task9/10 were not started.

## Identity and Read-Only Boundary

- Reviewed repository: `/Users/bytedance/Documents/trae_projects/eduagent-m3`.
- Python/test freeze: `5c38e26ac3838ad0d52ff08701c2a0a6b3e61a16`.
- Freeze parent: `59b529e15fd16cb7b229c7ea6170fa8bf0f85695`.
- Initial docs-only HEAD: `761ee6102e5cbfcbdd85dbcb5c32940ae3eeac08`.
- Final docs-only HEAD: `944b55f05220d81542ba7b971cc2b8735b730593`.
- The latter commit's five-line review-delivery note was inspected.
  `git diff 5c38e26 HEAD -- python` is empty.
- Primary repository remained clean at
  `2ff803c968d64741d149e5a1ce88a823d4d32422`.
- No repository source/test/docs/config edits, staging, commits, amend, push,
  installation, Docker, new agents, environment dumps, or secret output.
- Only own temporary probes/evidence outside the repositories were created.
  They were removed after execution, XML parsing, and hashing. This report is
  the sole retained artifact from this reviewer, for parent archival/cleanup.

## Scope and Source Conclusions

Read the approved plan's complete Task8, design sections 9 and 10, the latest
health/spec-review/code-review reports, and relevant implementation and tests.
Paths below are relative to `eduagent-m3`; references describe verified behavior,
not outstanding findings.

| Area | Source and review conclusion |
| --- | --- |
| Terminal identity and recovery | `python/core/distributed/policy_health.py:41-45,199-318`: canonical Run/deployment/cohort/contract keys; one terminal observation; PostgreSQL identity/outcome; cumulative attempt evidence; SQL/JSON-null legacy bindings excluded before bounded recovery limits. |
| Usage honesty | `python/core/distributed/shadow_usage.py:4-99`, `repository.py:443-461`, `expert_repository.py:1429-1488`, Harness/Coordinator/specialist/expert instrumentation: retries accumulate, inline expert calls are not duplicated, uncovered or uncertain cost stays unknown, structured rates use actual decision counts. |
| Matching and arithmetic | `policy_health.py:48-165,348-415`: Decimal arithmetic, nearest-rank p95, threshold equality fails, minimum 20 on both sides, deterministic bounded unequal-count proportional baselines including 50/20; Shadow requires identical parent sets. Missing qualified evidence holds; confirmed hard events fail immediately. |
| Complete frozen gate replay | `promotion_repository.py:651-760,878-953`: receipt/window identity, exact ordered unique keys, stats, cost, artifact/protocol/runtime/source, metric contract, sample counts and observation/persistence chronology are validated and recomputed; latest non-pass and lifetime hard evidence block consumption. |
| Actual causal inheritance | `promotion_repository.py:762-875`, `policy_health.py:363-419`: Active uses the exact consumed Canary window/approval/audit; hard sources are the deployment plus at most two audited predecessors, not arbitrary same-policy history. A late causal hard key prevents reuse of an earlier Active PASS. |
| Publication synchronization | `policy_health.py:172-188,333-343`, `promotion_repository.py:353-579`: direct primary, Shadow and recovery publication use the same environment-head row lock as promotion. Publication takes no health advisory lock and waits without terminal write locks; health takes advisory then head. Terminal transactions finish before publication. |
| Atomic rollback and pinning | `promotion_repository.py:276-339`, `policy_health.py:420-469`, admission/claim/Worker paths: failed window, immutable snapshot, CAS head, audit and Outbox commit atomically; concurrent evaluators produce one rollback; late unrelated historical windows cannot move the head; accepted old Runs retain their binding and new Runs use stable. |
| Actual SQLite diagnostics | `executor.py:29-33,79-187`, `worker.py:191-210,417-461`, `shadow_worker.py:76-176`: initial, successful and exceptional opened-store checks; cleanup hard causes preserved; all cleanup/usage stages attempted; hard failures are non-retryable through supported wrappers; constructors and unqueryable connections do not invent violations. |
| Signed faults | `policy_assignment.py:85-110,155-182`, `worker.py:233-239,374-381`, `repository.py:452-461`, `policy_health.py:79-85,219-246`: frozen signed candidate-only injection; stable profiles cleared; latency tags do not turn subsequent real hard/natural failures into injected commit failures. |
| Metrics and startup | `metrics.py:113-207`, `runtime.py:84-91,183-195,378-433,970-1019`, `cli.py:55-68,111-115`: bounded labels; postcommit local instruments plus separate database-authoritative counts; enabled-only health process; explicit transactional migration; ordinary startup checks schema rather than performing DDL. |

Meaningful existing tests inspected and independently executed include health,
corrections, publication interleavings, executor lifecycle/exception/cleanup,
Worker/Shadow/usage, promotion/admission/pinning, expert accounting, schema
upgrade/startup, and instrumentation tests. The full execution includes the
692-test Task8 impact matrix; no separate fresh 692-only run is claimed.

## Diagnostic-Precedence Angle

`policy_health.py:30-38` follows explicit `__cause__` and returns the first typed
permission or injection diagnostic. A manually constructed injected typed
wrapper around a harder permission cause would select injection first.
No supported runtime path producing that combination was found:
`RehearsalInjectedCommitFailure` is raised only in `worker.py:381`, after the
executor, its cleanup, result validation, business-step completion and authority
checks have succeeded. It is not used as an executor/cleanup wrapper.

Actual Harness failure wrapping is explicit `HTTPException ... from exc`
(`harness.py:405`); Shadow wraps explicitly (`executor.py:185`). The examined
server-diagnostic lifecycle does not use ExceptionGroup/TaskGroup or implicit
context-only wrapping for these typed diagnostics. No unsupported requirement
or hypothetical combination is classified as a finding.
New durable probes verified early real hard failures under signed none/latency/
commit profiles, ordinary controls, and real successful injection after cleanup.

## Independently Executed Verification

All runs used existing primary `.venv/bin/python`, absolute m3 `PYTHONPATH`,
`TZ=UTC`, `PYTHONDONTWRITEBYTECODE=1`, PostgreSQL 16 at `127.0.0.1:55432`
as postgres without a password, and Redis `redis://127.0.0.1:56379/0`.
Each pytest invocation created a distinct database and dropped it with an EXIT
trap. Redis fixtures used unique streams and teardown reset. No model calls
were made by the new probes; full-suite provider/model behavior was fixture-based.

| Run | Observed result | Parsed JUnit time |
| --- | --- | --- |
| Fresh full backend | 1607 passed, zero failure/error/skip, exit 0; pytest 310.45 s | 310.432 s |
| Initial 28 probes | 21 passed / 7 assertion failures, zero error/skip; 17.46 s | 17.460 s |
| Expanded 32 probes | 31 passed / 1 assertion failure, zero error/skip; 18.32 s | 18.319 s |
| Corrected complete 32 probes | 32 passed, zero failure/error/skip, exit 0; 16.08 s | 16.084 s |

The initial six assertions expected a gate rejection after health had already
rolled back, so correctly received version conflicts; rejection was moved before
evaluation. One UUID/string comparison was normalized. The expanded failure
expected recovery to be empty after direct Shadow publication while its primary
had not yet been recorded; that primary was explicitly recorded. These were
probe errors, not product defects, and failed rounds are not counted as passes.

The 32 new probes comprise: 12 signed candidate early-failure/hard-vs-ordinary
cases through actual Harness HTTP wrapping; 4 Shadow execution/cleanup controls;
6 successful real Harness signed candidate/stable controls; 2 delayed signed-hard
recovery/consumed-Active PASS invalidations; 1 rollback Outbox interruption and
four-evaluator recovery; 4 live head-publication waits with NOWAIT terminal-lock
checks across primary/Shadow and direct/recovery; 3 jointly corrupted frozen
evidence rejections through actual promotion commands.

Hard diagnostics in the new probes came from real SQLite ATTACH, committed
outside markers, and `assert_open_store_capability`, followed by independent
marker reads. Cleanup probes used five ordinary explicit cause wrappers.
The rollback interruption left window/audit/Outbox counts and head unchanged;
retry produced exactly one window, rollback audit and deployment-change Outbox.
Full backend retained the existing `TestAgent` constructor collection warning.

Actual command setup, from `eduagent-m3/python`:

```bash
zsh -c 'set -o pipefail
DB="task8_fresh_code_full_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
/opt/homebrew/opt/postgresql@16/bin/createdb -h 127.0.0.1 -p 55432 -U postgres "$DB" || exit
trap '\''/opt/homebrew/opt/postgresql@16/bin/dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"'\'' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH=/Users/bytedance/Documents/trae_projects/eduagent-m3/python
export TZ=UTC PYTHONDONTWRITEBYTECODE=1
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest tests -q --tb=short \
  -p no:cacheprovider --basetemp=/tmp/m3-task8-fresh-code.S94XP0/full-temp \
  --junitxml=/tmp/m3-task8-fresh-code.S94XP0/full.xml \
  2>&1 | tee /tmp/m3-task8-fresh-code.S94XP0/full.log'
```

Probe invocations used the identical setup with prefix `task8_fresh_code_probes_`,
test argument `/tmp/m3-task8-fresh-code.S94XP0/test_independent_review.py` and
`-c /Users/bytedance/Documents/trae_projects/eduagent-m3/python/pyproject.toml`.
Initial/expanded/verified output suffixes were `probes`, `probes-final`,
`probes-verified`; basetemp suffixes were `probes-temp`, `probes-final-temp`,
`probes-verified-temp`. These temporary files were parsed/hashed then removed.
Full command ID: `7abf752daf98ea690c090fe5e00b116f`, observed exited 0.
Final probe command ID: `06566df01dcda64665973bc49e480c73`, exited 0.

## Evidence Identity

Independently computed source hashes match the freeze:

- `executor.py`: `a94715b44f881fd29b6cfae5b439579937292a07872b93fb73b663d2df932b65`.
- `test_executor_cleanup_cause.py`: `f75287ea05df8391c9dfe2c0abfb66ba60c907ef5ecba69ec58971e051fc0f1e`.
- Combined repository-relative `shasum` output digest:
  `c97e321cac16d8948ea4025c86b694d320dc8549ce629155202b03da5a54dd22`.

Fresh execution hashes, computed before temporary cleanup:

| Artifact | SHA-256 |
| --- | --- |
| Full XML | `d55debf621b1df19ede270cdd948151c8878165d359cbc6f3553e50729ec22a4` |
| Full log | `708bc8708473bd537b3533cb6bda623f8e655c0c85933f1ccfe335aed26e4965` |
| Final probe XML | `147f29585bcf2446bec1e76a76348d1a7b19b2e7467cdbf8aea57fb2d5b420c2` |
| Final probe log | `172272a6caab996eeff9dfaf654c52edb6193e5f086faf18c07b28743e91f788` |
| Final probe source | `b81f3381ddaf0c88602197722cfdde57e1d3cae952d1c4f0d9f1f9c2e2aa466b` |
| Initial probe XML | `8f1c4fea50329558c0516fdacca9924da9aa7ff2546bffbbcf8c6012a74f703f` |
| Initial probe log | `830362115bf81349c3a4d525924362f791a0cdeff24deab5cf02cebb7287891e` |
| Expanded probe XML | `9a6fe3b0a19dc5cca4d192cd284efd99096478644be4c0f39aaeb8333d344f08` |
| Expanded probe log | `2e590ebc91f370bd72b3758dfa4887fb1d072d8a80d124b210e3e9a2879b463d` |

Separately read and parsed all five frozen cause XML files and computed all ten
XML/log hashes; every value matches the health freeze report. Those are archived
implementation evidence, not this reviewer's fresh executions:

| Frozen suffix | XML tests/failures/errors/skips; time | XML SHA-256 | Log SHA-256 |
| --- | --- | --- | --- |
| cause-red | 88/54/0/0; 7.496 s | `ed48003bd503b2c88d8e294cb73edee6a79bec69c64383fdaa01833020532795` | `f303438b563847c6d2feaf02cbaaaa9ac492d09b0b06e3f283b9252f865dd18b` |
| cause-repro-red | 120/75/0/0; 19.306 s | `fa44a78b78dfe183b183cc430f2984701bd071236ec149467ba640f3f15443ba` | `2d5b9433b4c9e2cab0c587913805b0ea34ea824288dadec4d91037f451f84f3e` |
| cause-focused | 195/0/0/0; 28.435 s | `b042f22c2996d37f4ccf26b7d7a339b43a7dbd46eec972fa77a34c45d40f5f1c` | `d455cb250b2d948178cef9011b369c53d03827876f76e735eb81ca213f338477` |
| cause-targeted | 692/0/0/0; 128.117 s | `02a619d7f7877da5b0072a52f24d7a0f6a1374bf952874d55eb54264b90f4c5d` | `9df1e5a3d14ac8f36b4a48c79713e534c2fb45ce8f674a689d7cc477e5d106e1` |
| cause-full | 1607/0/0/0; 301.418 s | `4936a8ed2d8442483d0f6ef408983be7600cbfd9785a74e16a25ef61d09ab86f` | `1f8686ae34703af470c10ae31c79c67666377acb3e309c597c051d2826a9d6f4` |

## Limits and Cleanup

Outer primary Worker cancellation, Shadow deadline/cancellation drain, and
expired/fenced authority can still leave no durable hard diagnostic. This review
does not restore authority, promise such persistence, or infer diagnostics absent
from PostgreSQL. Automatic rollback timing depends on health process availability.
The SQLite check is not OS sandboxing or proof against all possible side effects.
Fixtures do not establish formal release eligibility, real student traffic,
provider charges, or educational improvement. No formal campaign or external
model evaluation, frontend/Compose delivery, or broad M3 acceptance is claimed.

All four own databases were dropped; the scoped PostgreSQL catalog query returned
zero `task8_fresh_code_%` databases. All own temporary probe/log/XML/SQLite
directories were removed. Both worktrees had empty tracked/untracked status and
`git diff --check` passed. Existing parent temporary artifacts were untouched.
All reviewer test commands completed; no active code agent was created.

**Final disposition: approved full Task8 CODE PASS at the stated Python freeze.
Parent may archive this result and apply its sequential Task9 gate.**
