# Reviewer Auxiliary Attempts

These are not product counterexamples and do not replace the raw test results.

1. Two read-only `cat` commands used nonexistent guessed report paths. Exit 1,
   no file write. The actual paths were found with `rg --files` and read fully.
   No product test was invalidated. Terminal command IDs:
   `80b90d13238ef85a7de5a35a737027c9`, `7afe2f92ed6c7a7805bae1b13569641a`.
2. `final_checks.py execution` first exited 1 at line 43. It incorrectly
   classified the first UI runner's three unsuccessful tests as three XML
   failures. The original XML actually contains 51 PASS, 1 failure and
   2 errors. The failed script is retained as `invalid-final-checks-attempt.py`,
   its before snapshot is retained as `evidence-audit-before.json`, and all
   first-run UI trace/XML/log bytes remain unchanged. Corrected audit uses a
   different before/after label and checks failures and errors separately.
   Terminal command ID `42e0bd6b4854ae31889be04ca4e7a664`.
3. First UI run `ui54`: 51 PASS / 1 failure / 2 timeout errors. The failure
   context shows a navigation/reload while checking the Run drawer; the other
   two terminate at the 30-second timeout, one with skeleton loading visible.
   Same source, same runner/config, no timeout increase or retry setting change:
   complete `ui54-recheck` passed 54/54 after the backend finished. These are
   retained execution failures, not proven product bugs or erased attempts.

Auxiliary terminal start/end UTC was not separately captured and is unknown.
All pytest/build/Playwright invocations have their own actual command/UTC record.

4. `scan-precleanup` was incorrectly scheduled concurrently with cleanup.
   Redis shutdown removed its pid file after the scanner had enumerated it,
   causing `FileNotFoundError` before the scan completed. This scan is invalid,
   not a successful zero-match scan. Its actual UTC/command/exit/log are retained
   in `scan-precleanup-aux-record.json` and `scan-precleanup.log`.
   The Redis identity/pid contents were already retained in the original identity
   and final cleanup records. Final scan is run serially after cleanup on the
   stable retained files, history and changed source, with no pattern exemptions
   added to handle this inventory race.
