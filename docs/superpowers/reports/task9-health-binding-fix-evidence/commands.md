# Invocation Ledger

All commands run from the authorized M3 worktree or owned temporary frontend.
Python uses the primary venv read-only with PYTHONDONTWRITEBYTECODE=1. The
`pytest.sh` runner allocates a unique PG database and drops it on EXIT for every
invocation, including invalid fixtures and failed executions. `safety.py` rejects
non-loopback connections and restricts Redis reset to UUID test streams.

| Label | Runner Arguments / Scope |
| --- | --- |
| c1red | external original C1 two tests, invalid missing fixture before product edits |
| c1redvalid | same two tests after adding copied fixture dependencies; valid 2 assertion failures before product edits |
| c1green | same original two C1 tests |
| relations | new source regressions + full test_promotion_ops_api.py + test_ops_api.py |
| relationsv2 | same scope; fix unique receipt evidence fixture |
| relationsv3 | same scope plus Active tests; incorrect JSONB function |
| relationsv4 | same scope; fix JSON function, expose Active DTO serialization fixture |
| relationsfinal | same scope; expose duplicate environment/version fixture |
| relationsfinalv2 | same scope plus valid Active control, 138 PASS |
| full | `-c pyproject.toml -q tests`; 1725 PASS / 1 failed receipt tie-order fixture |
| fullv2 | `-c pyproject.toml -q tests`; 1726 PASS after deterministic fixture ordering |
| greenfinal | `-c pyproject.toml -q <OWN>/test_code_attacks.py -k 'current_health_gate_must_not_borrow_previous_deployment_pass or historical_health_gate_must_not_be_replaced_by_new_deployment'` |
| relationsfreeze | `-c pyproject.toml -q tests/distributed/test_ops_health_binding.py tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py` |
| build, buildv2 | `node.sh <label> build`; type/parenthesis errors retained |
| buildv3, buildfinal | `node.sh <label> build`; Node20 build passes |
| uifull | `node.sh uifull test --config playwright.health.config.ts e2e/ops.spec.ts`; six UI/test failures |
| uifinal | same full scope; parallel production output-dir collision causes two context-close errors |
| uifinalv2 | same full scope with `--output <OWN>/uifinalv2-artifacts`; 54 PASS |
| production | `node.sh production test --config playwright.production.config.ts`; 4 PASS, supplementary only: combined fixtures displaced current head |
| productioncurrentfinal | `LIVE_SCENARIO=current LIVE_LABEL=currentfinal bash live.sh`, then `LIVE_FIXTURE=<OWN>/live-fixture-currentfinal.json node.sh productioncurrentfinal test --config playwright.production.config.ts --output <OWN>/productioncurrentfinal-artifacts --grep 'production current'`; 2 PASS |
| productionhistoryfinal | identical isolated service with historyfinal/history and `--grep 'production history'`; 2 PASS |

Node20.19.5 interpreter:
`/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`.
Frontend node_modules is a physical rsync copy, not a symlink. Own Vite port
33520 and production HTTP port 33521; own npm/TMP/cache only. No model requests,
no dependency downgrade, no production DB URL, no Docker, no Task10.

Every XML records suite timestamp and duration; `test-counts.json` parses actual
testcase elements and includes module-level and nonpassing-case matrices.
Counts are executions, not unique cases or HTTP request counts. The six final
invocations overlap; do not add the 138 API/relationship tests again to the full
backend total. Parent compatibility baseline 1684 is not this run.

Service processes were terminated through their recorded own PIDs, then awaited
for EXIT database cleanup. Wrapper exit 143 is intentional shutdown after all
production assertions completed, not a pytest failure.
