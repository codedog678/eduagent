# Fresh SPEC Execution Commands

These are reproducible equivalent invocations reconstructed from the retained
runners, XML test identities and execution logs, not a claim of an additional run.
For a future rerun, copy the scripts and adjust every OWN/EVIDENCE/cache/port path
to a new isolated directory first. Do not overwrite this evidence or repo archives.

```bash
OWN=/tmp/m3-task9-corrected-spec-20261102
E="$OWN/evidence"
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
bash "$E/pytest-runner.sh" all-api -c pyproject.toml -q -s \
  tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py \
  "$E/independent/test_independent.py" "$E/independent/test_gate_tie.py"
bash "$E/pytest-runner.sh" fresh-attacks -c pyproject.toml -q -s "$E/test_fresh_attacks.py"
bash "$E/node-runner.sh" build build
bash "$E/node-runner.sh" ui-40 test e2e/ops.spec.ts \
  --reporter=line,junit --output="$OWN/playwright-ui"
bash "$E/live-runner.sh" failed
env FIX_GATE_STATUS=failed bash "$E/node-runner.sh" live-failed test \
  --config=playwright.live.config.ts --reporter=line,junit \
  --output="$OWN/playwright-live-failed"
kill -TERM "$(cat "$OWN/live-runner.pid")"
bash "$E/live-runner.sh" unknown
env FIX_GATE_STATUS=unknown bash "$E/node-runner.sh" live-unknown test \
  live-e2e/gate-tie.spec.ts --config=playwright.live.config.ts \
  --reporter=line,junit --output="$OWN/playwright-live-unknown"
env FIX_GATE_STATUS=unknown bash "$E/node-runner.sh" live-run-detail-unknown test \
  live-e2e/fresh-live.spec.ts --config=playwright.live.config.ts \
  --reporter=line,junit --output="$OWN/playwright-live-run-detail-unknown"
kill -TERM "$(cat "$OWN/live-runner.pid")"
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/finalize.py"
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/archive-check.py"
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/provenance.py" manifest
```

Live runners execute asynchronously in separate terminals; wait for
AUTHORITATIVE_GATE_REJECTS_NEWER and application startup before browser tests.
Wait for TERM/EXIT cleanup before starting the other live server.

Node runner uses npm exec --yes --package=node@20.19.5 -- node, then spawns build
or the local Playwright CLI with the Node20 executable and PATH.
prepare.sh records the initial entity dependency copy and path adjustments.
The failed 8-test live run used fresh-live-v1.spec.ts bytes as fresh-live.spec.ts.
The extra unknown 2-test run used the screenshot-only revised fresh-live.spec.ts.

Six new raw XML files count 179 executions: API 127, browser 52.
The 40 UI browser executions use mocked responses. Twelve browser executions use
actual production assets and real PostgreSQL-backed Ops API.
No full-backend 1684 rerun, historical RED rerun, live model call, CODE gate or Task10.
