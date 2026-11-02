# Bookkeeping Attempts

These are implementation-process errors, not product RED or acceptance findings.

- First lookup of `/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93/live-e2e/spec-health.spec.ts`
  and `playwright.production.config.ts`: no such file. Located under its `frontend/`;
  copied into own UUID directory before adapting.
- Lookup `python/tests/conftest.py`: no such file. Actual distributed conftest was read.
- One `apply_patch` hunk for own `frontend/playwright.config.ts` failed because its actual
  webServer command was `npm run dev -- --host 127.0.0.1`, not the assumed strict-port form.
  Other independent hunks applied; actual file was then read and patched.
- First own inventory failed with `AssertionError` at:
  `assert not any(p.is_symlink() for p in (OWN / "frontend/node_modules").rglob("*"))`.
  Standard copied npm .bin links are internal. Corrected check asserts every target resolves
  strictly inside OWN, with explicit target inventory. No link to either product worktree.
- source-regressions-v1.xml: 67 tests, 57 passed, 10 failed testcase nodes (not setup error XML).
  Two invalid environment fixture DTOs produced 503; two invalid foreign keys prevented insert;
  two decimal-control assertions had no repeating mean at count20; four probes passed UUID
  objects to internal varchar queries. Fixed fixture before re-run source-regressions-v2:
  67 passed. No immutable UPDATE/trigger bypass/assertion weakening.
- production-current.xml: zero collected. Log has:
  `TypeError: Cannot read properties of undefined (reading 'startsWith')` because
  SPEC_SCENARIO was not supplied. production-current-v2 supplies `SPEC_SCENARIO=current`,
  both desktop/mobile passed.
- The initial empty mistaken `/tmp/m3-task9-fix-VWoyu6AI` directory had no raw artifacts;
  exact empty directory removed during own cleanup.

All pytest/node test failures have original XML/log and commands preserved. Read-only lookup
and patch-tool errors have this sequence record; their exact wall times were not instrumented.
