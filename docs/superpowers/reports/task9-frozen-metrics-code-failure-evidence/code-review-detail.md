# Task9 Independent WHOLE CODE: FAIL

## Verdict and Authority Boundary

One P1 BUSINESS_SEMANTICS defect, confidence 10/10. All four source-review groups and cross-group checks were performed by this reviewer using the bits-code-guard fallback, not delegated or inherited from SPEC. This is CODE FAIL, not final Task9 acceptance, Task10 approval or release qualification.

Evidence root `E=/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814`.

| Identity | Value |
|---|---|
| Authoritative repository | `/Users/bytedance/Documents/trae_projects/eduagent-m3` |
| Branch | `feature/m3-trusted-policy-promotion` |
| Actual clean CODE HEAD | `a3e2c0b0f510235cec8a98784afdb26b3bb6db79` |
| Parent | `9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f` |
| Product | `1b8e4b745126c92cfd56f9f021388dd615d98791` |
| Product base | `855d5c6660343c24df0bef5ad4cf77160e83c566` |
| WHOLE Task9 start | Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f` |
| WHOLE source scope | 21 files, actual Git `+3857/-51` |
| M3 protected source | 357 files, SHA256 `14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813` |
| Primary read-only HEAD | `2ff803c968d64741d149e5a1ce88a823d4d32422` |
| Primary protected source | 266 files, SHA256 `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5` |

The first brief, all nine task briefs, approved design, Task9 six-step plan and acceptance criteria, complete implementation/SPEC/history reports and raw were read. `whole-code-source-scope.json` records actual HEAD bytes and hashes for the complete 21-file scope. The original broad script-filtered list is retained as `review_files.initial-filtered.md`; archive raw is not counted as source.

Prerequisite NEW independent SPEC PASS is retained in the repository at `docs/superpowers/reports/2026-11-02-m3-task9-leaf-authenticity-spec-pass.md` and `task9-leaf-authenticity-spec-pass-evidence/`. Its report hash is `542fd8da3e1b25a77794f48ef39f7cfae1e998cb0dcb2ef90b0dca7abf4cb081`; manifest `75a133cbc9f589c7ca0d1565fe6dd582d1691962234fdd928caca257f2fcfd99`; payload `a35cfc82487b2da96f18446227d1ea79ede8a7b2e70b787e0bd9c692c91db70c`. Its green results are not this reviewer's execution evidence. The archived helper locator error is not copied: `health_evidence_identity.py` has 51 actual lines. `parent-locator-and-visual-notes.md` governs historical corrections without altering original report bytes.

## P1: Metrics Claims Are Not Authenticated Against Exact Observations

Location: `python/core/distributed/ops_queries.py:594-604`, `_frozen_summary_matches` (full function 526-604). Immediate callers are the receipt projection at 508-510 and exact consumed-Canary projection reused for Active.

```python
for row in rows:
    if (
        row.deployment_id != source.deployment_id or row.cohort != cohort
        or row.policy_hash != policy or row.metric_contract_version != 1
        or not source.created_at <= row.observed_at <= window.evaluated_at
        or row.created_at > window.evaluated_at
        or not isinstance(row.cost, Decimal) or not row.cost.is_finite() or row.cost < 0
    ):
        return False
    total += row.cost
return receipt.cost == total
```

Facts: keys/canonical identity, frozen minima/run count, ordering and exact Decimal cost are checked. Other aggregate claims are compared only between `receipt.details` and `window`, not against actual rows. The shared pure identity helper does not validate the observation schema, all frozen metrics or actual decision. Publication authority does: `promotion_repository.py:651-754`, `_observation` at 721-722 and `evaluate_window`/aggregate comparison at 743-749.

Valid reproducible input: append a new observation, window and matching claimed-passed receipt under real migrations, FK and append-only rules. Retain original observations and receipt; use a fresh admitted parent run, canonical observation key, legal nonproduction identity, matching pairing/distribution, exact counts/cost and timestamps. The authority evaluates that exact new leaf first. No immutable row update, trigger disabling, invalid FK setup, mocked GET result or swallowed setup failure was used.

Actual: authority rejects each poisoned leaf. Full detail GET returns 200 and displays `local passed`; Active referencing that exact Canary receipt displays both Canary and Shadow as `consumed_chain passed`. Expected: invalid local leaf must not gain a trusted health source, and an invalid exact Canary must invalidate Active's entire health consumption chain without falling back to a different leaf.

Minimal owned evidence: `code-complement/active-candidate-permission_violation.json`. It records `authority_accepts=false`, independent exact-row `decision=fail`, reason `confirmed_permission_violation`, actual terminal-failure rate `0.05`, but stored claims have zero failures and GET displays passed Canary plus Shadow. An append-only engineering Active snapshot is not a successful production promotion: `is_current=false` and the current head remains Canary in raw. This proves a read-projection defect, not a publication write bypass.

One root cause covers six poisons: `commit_failed`, `terminal_failed`, `permission_violation`, `unknown_counter`, `invalid_counter` and `stats_claim`. Local matrix: 6 poisons x 2 cohorts x 2 gates = 24 valid FAIL assertions. Same-input Active: 6 poisons x 2 cohorts = 12 valid FAIL assertions. Six legal controls pass. `invalid_counter` is an appendable database row rejected by observation schema, not failed test setup; `stats_claim` keeps legal raw observations but changes frozen metric claims.

Repair guidance, not implementation: authenticate bounded exact frozen rows through a pure read-only schema/complete-aggregate/threshold predicate shared by local and consumed-chain projections. Do not invoke a promotion command or an unbounded/side-effect evaluator from Ops GET. Preserve exact Decimal cost, frozen custom minima, valid nonpassed local visibility, independent Shadow/history, and legitimate Active sources/baseline from exact consumed Canary keys.

## Owned Execution Matrix

Counts are testcase executions, not independent students, model samples or unique qualification evidence. Overlapping suites are not summed.

| Owned invocation | P/F/E/S | Evidence |
|---|---|---|
| Full backend | 1911/0/0/0 | `code-full.xml`, command/log |
| Full Ops/promotion API | 362/0/0/0 | `code-api.xml`, command/log |
| Source-integrity plus independent command/approval metadata | 131/0/0/0 | `code-integrity.xml` |
| Fresh original leaf plus Active plus minimum matrix | 90/0/0/0 | `code-leaf-minimum.xml` |
| New complementary entire-metric attacks | 6/36/0/0 | `code-complement.xml`, 42 complete proofs |
| SQL error/closed DTO 503 plus actual FK/append-only supplement | 9/0/0/0 | `code-boundary.xml` |
| All checked-in UI | 54/0/0/0 | `code-ui.xml` |
| Additional fixture UI/Trace | 4/0/0/0 | `code-visual.xml`, `visual/` |
| Actual PG production-build checks | 28/6/0/0 | 17 production XML files, desktop/mobile |
| Node 20 build | exit 0 | `code-build-command.json`, log and owned dist |

All 47 checked-in new leaf cases occur in both full/backend and API XML, and in the 90-case minimum/leaf suite. That suite is fresh leaf 9 + independent Active 6 + extra minimum 4 + checked-in minimum 24 + checked-in leaf 47. Original seven local counterexamples and five separately asserted same-input Active counterexamples now pass; all original failure archives remain intact. Their correction does not cancel the new 36 valid FAIL assertions.

Reviewed/tested invariants include actual run/deployment/cohort/version canonical identity, both cohorts and gates, nonproduction namespace on both sides, Canary rehearsal and operation distributions, Shadow run pairing, start/end/empty/order/max key constraints, passed empty triggers, frozen default/custom minima (22/23), Decimal 21/21, nonpass unknown, exact receipt consumption, eight approval fields, latest malformed approval, time-cutoff full chain/F1C1S1S2S3S1R, pinned Trace identity, closed/private DTOs, auth keyset, RR READ ONLY and GET nonmutation.

Original 12 PG production scenarios each ran desktop/mobile: `current`, `history`, `genuine_valid`, `genuine_malformed_latest_valid`, `minimum_zero`, `referenced_canary_poison`, `approval_malformed_latest`, `leaf_local_bad`, `leaf_active_bad`, `leaf_local_valid`, `leaf_active_valid`, `leaf_shadow_valid`: 24P. New `metrics_canary_commit_failed`, `metrics_active_permission_violation`, `metrics_shadow_unknown_counter`: 6F. Legal `metrics_active_valid`: 2P. Additional actual-PG pinned Trace: 2P. Total 34 checks, 28P/6F; not 34 distinct samples.

All 32 health-detail production viewport records have full GET 200, page errors zero, and actual horizontal mobile scroll in 16 scenarios. Current mobile is 0 -> 220; legal before positions 39/193 are retained, not rewritten to zero. Explicit three asset GETs per viewport and response SHA/bytes match this owned dist. Actual stored Run Trace also has full GET 200, fixed deployment/policy/cohort/namespace identity and matching response bodies. Its role is migrated-PG `test_fixture`, release false, not model/release qualification.

`code-execution-final-audit.json` independently parses 25 XMLs per testcase, 26 complete byte-equal protected before/after pairs, 92 trace ZIPs/3251 members with CRC/body hashes, exact production bodies, and 136 actual asset response bodies matching dist. Metrics: 192 health-page GETs; 340 production trace-network GETs including Trace; 136 explicit request-context GETs. These overlap and are not added. Total all-HTTP remains unknown; recorded production page/network requests are GET-only.

Reviewer personally viewed five actual PG production images listed with SHA in `code-visual-inspection-record.json`, plus two fixture images in `code-visual-fixture-inspection.json`. Bad leaf detail, valid Active, current mobile, prior bad local and actual pinned mobile Trace were inspected. Fixture Trace screenshots remain UI-only evidence.

Runtime: `/tmp/eduagent-m3-patched-runtime/bin/python`, actual 3.11.17; 58 installed distributions, 39 actual declarations plus five repair floors checked read-only, pip check exit 0. `spec-runtime-final.json` is this CODE invocation's recomputed output filename, not inherited SPEC green. Node actual 20.19.5 at `/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`; owned physical module copy, no writable source symlink. Vite 7.3.7 build succeeds with retained large-chunk warning.

Execution timestamps and exact argv/cwd/exits are in `*-command.json` and production DB lifecycle files. Setup 07:23:02.937054Z -> 07:24:43.125147Z; full backend 07:25:13.738787Z -> 07:32:15.413486Z; complementary failure 07:31:39.771090Z -> 07:32:15.620147Z; production bad cases 07:38:43Z through 07:39:11Z; actual Trace 07:43:37.232867Z -> 07:43:38.563398Z. The setup wrapper omits an explicit exit field; observed tool exit 0 and snapshots exist, omission is not synthesized into raw. Exploration read commands have no complete UTC ledger; unknown remains unknown.

## Historical Corroboration and Failure Retention

`historical-full-raw-audit.json` freshly audits 6076 historical files, 18 manifests, 245 XMLs, 734 ZIPs/25943 members and current 7296/prior 5492 actual Git blobs. Historical pass/fail executions are not counted as owned.

Older 352-source manifest is verified against its actual `2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d` Git blobs, not a wrong root. Historical v1 script is preserved as `finalize-docs-v1.py`, byte-matching its old manifest name. All other manifests are complete. The original malformed implementation fixture JSON (SHA `680e848859b608d0feeeaa388a908b442a7c638d52ecf2afdc6d01dd75570600`) is preserved/classified, not repaired. Old CODE seven-local/five-Active valid failures and every implementation interrupted/failed execution remain untouched.

SPEC's own schema-helper 8P/1F and historical v1 misparse remain original auxiliary failures, not product regressions. Three raw trailing spaces remain exact bytes. Historical normal-hook two-second timeout is not complete secret-scan PASS. Original unscrolled implementation images are not overwritten; corrected SPEC scroll/parent locator notes remain separately classified.

Owned finalization auxiliary failures: first summary used incorrect additions 3918; actual Git is 3857. Second `group.mkdir()` failed because an earlier empty group directory existed. Failed scripts, exact tracebacks and command UTC/exits are retained; version 3 completes. These do not negate or create the product P1. Earlier read-only missing memory file, nonexistent `setup_spec.py` and no-match `rg` exits are retained in `owned-read-command-limitations.md` with unknown UTC, not portrayed as product test FAIL.

## Protection, Cleanup, Secrets and Seal

`code-cleanup-final.json`: all 23 exact invocation UUID DBs have drop exit 0 and exact remaining 0. Shared PG 16.15 remains loopback 57432/PID16852 with its original data directory and original `postgres/template0/template1` set. No fixed historical setup/bootstrap main was executed.

Owned Redis 56684/PID45475/run ID `8712c75f4c68c9fd73fa93f40de8f92b1d9bf916` was revalidated with owned dir, save empty, appendonly no; stopped by `SHUTDOWN NOSAVE`, exit 0. Redis/Vite/production ports 56684/56685/56686 are closed. No FLUSH or prefix-wide deletion. The recorded key ledger is incomplete for subprocesses: residual owned keys were listed then discarded solely by whole owned nonpersistent-process shutdown, not claimed individually deleted. Original implementation/SPEC closed Redis identities were not reused.

Only owned module/cache directories were removed: frontend/node_modules, cache, npm-cache, tmp, vite-cache. Raw assertions/logs/screenshots/ZIP/dist/scripts remain. Cleanup independently verifies complete first/final protected snapshots, 7296 M3 actual tracked blobs and 1110 primary tracked blobs. Source bytes/mtime/index, local venv, source Vite caches and patched runtime are unchanged; both repositories are read-only throughout.

Owned actual-secret scan completed: `code-secret-final.json` records 9320 files, 826 ZIPs/29194 members, one TAR/358 members, two distinct actual values, zero actual-secret matches and zero effective high-confidence pattern matches. This covers both repositories' tracked bytes, all retained owned files and result/report bytes. Values were read privately from local configurations and never echoed. Only exact old `parent-retain.py` lines 88/89 at Git-verified SHA `9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a` classify two scanner assertion literals; no whitelist expansion. Final report/script updates are rescanned separately into `code-secret-final-report.json`; original scan bytes and commands stay unchanged. This is not a normal-hook timeout PASS.

`manifest.json` covers owned evidence except itself; compact sorted per-file records determine payload SHA. External `/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814-seal.json` binds manifest, payload and report/result hashes without recursion. External final-verification/command artifacts document post-seal reads. No repository archive/commit/push or external comments were performed.

## Remaining Limits

Zero new model requests, actual new cost USD 0; Agent50 remains paused. No Docker installation/run, CI execution, formal v3 independent qualification chain or student-outcome evidence. Engineering fixture scores and GET/UI success are not independent release qualification or successful promotion writes. Parent must independently verify this NEW CODE FAIL evidence before any authorized archive or fresh implementation loop; no self-authorized Task9 acceptance or Task10 work.
