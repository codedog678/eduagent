# M3 Task9 Implementer Result

IMPLEMENTED AND FROZEN. NOT ACCEPTED. Fresh independent SPEC then CODE review
must follow. No Task10 implementation or duplicate implementer was started.

## Commit And Ownership

- Worktree: `/Users/bytedance/Documents/trae_projects/eduagent-m3`.
- Branch: `feature/m3-trusted-policy-promotion`.
- NEW commit: `38f48d763b4a9599aa215f98a2cba1b32003b1e7`.
- Parent: `8869166878a193a1c453376471cbe52c8fa84b3f`.
- Subject: `feat(ops): expose read-only trusted policy promotion evidence`.
- Normal `git commit -F -` with heredoc; no hook/signing bypass, amend, push or
  Git configuration change.
- Exact 62 owned committed paths: 13 source/test/UI, one report, 48 evidence
  files. Post-commit verification checked every source/evidence blob against
  the manifest and checked the changed path set against the owned allowlist.
- M3 worktree clean after commit.
- Primary remains `2ff803c968d64741d149e5a1ce88a823d4d32422`,
  `main...origin/main [ahead 2]`, clean and unmodified.
- Parent Task8 reviews, interview index and Task10 preflight were not staged
  or changed.

## Hashes

- Combined owned source SHA-256:
  `67581927eea462b0c8ce36ef495b84d3211d7f11d62980d16d71315f90616810`.
- Combined retained evidence SHA-256:
  `432b7da2ddf1a45af5003e70e716066ac98db52d694ea972bb9558aa96e8b62b`.
- Manifest SHA-256:
  `0dc0ecc9d01b270ee2a58399dcf32b936a57c5ca5749644b4a7860dd42f95cd6`.
- Report SHA-256:
  `2a082f66f0e1ecdd8f6a44c3ec6e99adad4b7418996fcc615863aaef7bd372e3`.
- Final build log SHA-256:
  `5e59f8ac2bc529d4d0fbe32befe8e2ba4a84c2c34ca76dfec707dc5f73e38fe0`.

Both combined digests hash compact ASCII JSON of sorted
`(relative_path, file_sha256)` pairs. Source excludes report/evidence. Evidence
paths are relative to `task9-ops-evidence`; its combined digest excludes
`manifest.json` to avoid self-reference. The complete individual source/log/
XML/screenshot hashes are committed in the manifest.

Report:
`docs/superpowers/reports/2026-11-02-m3-task9-ops.md`.
Manifest:
`docs/superpowers/reports/task9-ops-evidence/manifest.json`.

## Delivered

Exactly four GET policy routes, bounded strict keyset cursors/filters and shared
Ops bearer/loopback authorization. Explicit PostgreSQL READ ONLY query
transactions; command-service tripwires and real DML rejection tests.
Frozen typed deployment/gate/health/audit projections; opaque actor/reason/
issuer labels, numeric aggregate allowlists, no details/components/raw namespace
or freeform sensitive bodies.

Stored Run summary/detail/Trace bindings remain immutable across head advance/
real health rollback; legacy NULL bindings remain unavailable. Real rollback
events on the new deployment are correlated back to the failed deployment by
typed failed-deployment/window IDs. Freeze transitions use closed state labels.
The date-overflow feedback is covered on all three policy list cursors, using
64-hex window cursor identities; both extreme timezone conversions return 422.

PoliciesView has compact responsive table/timeline, filters, cursor pages,
version selection, full hashes, current-head relation, traffic/cohort counts,
frozen thresholds, gates and candidate/stable metrics. Runs/Trace link the
stored version. Loading/empty/error/retry/auth, strict schemas, horizontal
scrolling and stale list/detail requests are exercised in both viewport sizes.

## Exact Final Commands

Backend commands ran from the M3 root through `/tmp/m3-task9-pytest.sh`.
That temporary runner was byte-identical to the committed
`docs/superpowers/reports/task9-ops-evidence/pytest-runner.sh`, then removed.
The archived runner can be used directly for subsequent verification.
Each invocation creates a unique fresh database and drops it in an EXIT trap;
it changes cwd to `python` before pytest.

```bash
bash /tmp/m3-task9-pytest.sh red-api-valid-fixture tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py -q
bash /tmp/m3-task9-pytest.sh red-cursor-overflow-valid tests/distributed/test_promotion_ops_api.py -q -k timezone_overflow
bash /tmp/m3-task9-pytest.sh red-correlation tests/distributed/test_promotion_ops_api.py -q -k 'rehearsal_run or audit_closed or cohort_counts or numeric_allowlist'
bash /tmp/m3-task9-pytest.sh green-api-freeze tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py -q
bash /tmp/m3-task9-pytest.sh full-backend-final tests -q
```

Frontend commands ran from `frontend`:

```bash
env PLAYWRIGHT_JUNIT_OUTPUT_FILE=../docs/superpowers/reports/task9-ops-evidence/red-ui.xml npm exec --yes --package=node@20.19.5 -- node node_modules/@playwright/test/cli.js test e2e/ops.spec.ts --project=desktop --grep 'policy strict' --reporter=line,junit --output=/tmp/m3-task9-playwright-red > ../docs/superpowers/reports/task9-ops-evidence/red-ui.log 2>&1
env OPS_SCREENSHOT_DIR=/tmp/m3-task9-screenshots PLAYWRIGHT_JUNIT_OUTPUT_FILE=../docs/superpowers/reports/task9-ops-evidence/green-ui-final.xml npm exec --yes --package=node@20.19.5 -- node node_modules/@playwright/test/cli.js test e2e/ops.spec.ts --reporter=line,junit --output=/tmp/m3-task9-playwright-final > ../docs/superpowers/reports/task9-ops-evidence/green-ui-final.log 2>&1
npm exec --yes --package=node@20.19.5 -- node -e 'console.log("Node",process.version); const {spawnSync}=require("node:child_process"); const {dirname}=require("node:path"); const r=spawnSync("npm",["run","build"],{stdio:"inherit",env:{...process.env,PATH:dirname(process.execPath)+":"+process.env.PATH}});process.exit(r.status??1)' > ../docs/superpowers/reports/task9-ops-evidence/build-final.log 2>&1
```

## JUnit Statistics

All entries have zero skips. Columns are actual tests/passed/failures/errors.
Files are under `docs/superpowers/reports/task9-ops-evidence`.

| XML Stem | T/P/F/E | SHA-256 |
| --- | --- | --- |
| red-api | 75/19/0/56 | 77389e22656e1f8531f0cb7b4b4d30f0d44a62919b4a167b8228115fca350273 |
| red-api-valid-fixture | 75/19/56/0 | a4536516cf9fe2279ac6a850ca12a8dcfa3d10db567606bb291871c196eb7f5b |
| green-api-attempt1 | 75/73/2/0 | 66a9582988777b0e9320d3e312f4bf073750cbb34f80df7f309c17c5325bd509 |
| green-api-attempt2 | 76/74/2/0 | b12e83181921ede71d52085d4550ed57b5e3495d2186f59a20153124255919fa |
| green-api | 76/76/0/0 | 585ac2444d8df6e2aa526796f2b27ceb30afef724b94e2b9b755922eb2816331 |
| red-cursor-overflow | 0/0/0/0 | f36bdd2c7be5b93047d023b4a3fc291a7ed6aadda0a4288a741c94e0861e7090 |
| red-cursor-overflow-valid | 6/0/6/0 | 92ab1ef3079ff81f3b223b79a943cae5b2362335445ea996202a32fb06dbcbcb |
| green-cursor-api | 82/82/0/0 | 401d7e33c2e5c23610eef9683d4ced90fb4c87c02109eb27f6b831db252082ff |
| red-ui | 1/0/1/0 | 3868dd8868ab8e896d4748274d6368ceba976b9891e4aac1c258e0a44dd5927d |
| green-ui-attempt1 | 22/18/4/0 | a6a4fcf804f66e6cf6068829a1466951e34569a3c71b034c3745c0dc66a7822d |
| green-ui-attempt2 | 22/18/4/0 | b3d6507e235815834c87c90657ce09fac6d9d2bbee0dd29b9b6e88e27882a65d |
| green-ui-attempt3 | 36/36/0/0 | deed578b055b047092abca5a9a38db129a41108bf2623142fda28d71d64870ed |
| full-backend-attempt1 | 1670/1670/0/0 | 19830bd303480169e0aec77f5e84398d45ad32b81f09699543ab2eb8ba72444d |
| red-correlation | 4/2/2/0 | fb50fdfd98f6a52848f5285d6ae587c74a07e173036cbdd3b2c9cba289f6211f |
| green-api-final | 85/85/0/0 | aa8fb7f073312b9ad65eb4acfd2d897e6d33e7640d8677bd65964716b497e63a |
| green-ui-attempt4 | 36/36/0/0 | 4044196d43b3d8020353b37c4a91c4da627d8d9285ceb6c42fbacf4af7c03ee3 |
| green-ui-final | 40/40/0/0 | 3f8a12fce1cacf69b27ba8670e79295761d93c6da20daec02739402b336a1f03 |
| full-backend-final | 1675/1675/0/0 | a5a99c8991698c92f1fb0a20987b003eafcd65350038460831bfaf4192828db8 |
| green-api-freeze | 87/87/0/0 | da238bf77a61cad579a7926efb02e96f1aa7365f994c9764c479d62fba894433 |

Final backend JUnit 316.689s; API 14.492s; UI 27.420s summed suite time,
14.9s wall time. UI is 20 cases on each viewport. Full backend is existing
1607 plus 68 Task9 tests; targeted API is Task9 68 plus existing Ops 19.
The initial fixture failure and zero-test wrong-path invocation are preserved
but not counted as meaningful implementation RED. Intermediate failed GREEN
attempts are explicitly failed, not success claims.

## Build, Browser And Limits

Actual Node v20.19.5 `npm run build` PASS. Vite 7.3.7/plugin 5.2.0,
TypeScript 5.9.3, React 18.3.1, Ant Design 6.4.3, Playwright 1.64.1;
actual Chromium 156.0.8078.4. PostgreSQL 16.15 at 55432 and Redis at 56379.
Python 3.11.17, pytest 9.0.3, pytest-asyncio 1.3.0.

Final screenshots inspected:

| File | Pixels | SHA-256 |
| --- | --- | --- |
| policies-desktop.png | 1440x2302 | 97f5550cba46fcd06b3fedb478dbd0ac7c56a9216264f5fb82163bb4ed460cc0 |
| policies-mobile.png | 390x2776 | b36240764fe2e757e63e52a2f63d141ed08624842ce33e70c361c743152e9131 |
| policy-trace-desktop.png | 1440x900 | 9a1e617266a4fe6ddd013c3f6e669fb6587d8263f8207d9fda5593c3745b3b7c |
| policy-trace-mobile.png | 390x844 | 29e7ee4db7460e43fcbd1791c5695ffbb2808647d1eb77c7467a1e1494aa16d2 |

API tests use real PostgreSQL; UI browser tests use synthetic route mocks,
not real promotion infrastructure. This is development regression evidence,
not independent release qualification, safety proof, formal holdout or CI/
Docker proof. Formal model requests 0; formal model cost USD 0.
One pre-existing TestAgent collection warning and an existing shared frontend
chunk-size warning remain. Parent-reported dependency advisories and demo DB
wrapper isolation are separate follow-ups; no dependency/config changes here.

Authored/source whitespace checks PASS. Broad staged diff check reports 3005
raw-log/XML whitespace warnings across 17 files; originals preserved unchanged.
Narrow high-risk credential-pattern scan found no matches; synthetic test
tokens are not real credentials.

## Cleanup And Next

All unique Task9 databases dropped; PostgreSQL query confirmed no `m3_t9_*`
database remains. Redis fixtures remove only their own streams. No port 3000
listener remains. Own `/tmp` pytest/cache/browser-debug/screenshot/runner files
removed after required evidence was archived. No global cleanup performed.
Parent `/tmp/m3-task9-spec-review-brief.md` and Task10 preflight preserved.
Normal ignored dependency/build output is not in the commit.

This completed handoff is written before the final notification.
Next: fresh independent SPEC review on commit 38f48d7, then fresh CODE review.
Do not mark Task9 accepted from these implementer results.
