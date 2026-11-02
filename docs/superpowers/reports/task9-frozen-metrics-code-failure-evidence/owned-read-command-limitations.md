# Owned Read-Only Auxiliary Outcomes

These are not product test failures. No test setup was counted as a valid attack.

| Outcome | Known execution evidence | UTC |
|---|---|---|
| Project-memory local file absent | Read command exit 1, prior context tool observation | Unknown |
| `setup_spec.py` does not exist | Read command exit 1, prior context tool observation; main not invoked | Unknown |
| `rg` scenario/mode query no matches | Read-only exit 1, prior context tool observation | Unknown |
| Final report statistics assertion | Exit 1; `finalize-structure-command.json`, failed v1 script and traceback | Exact in raw |
| Final group directory create | Exit 1; `finalize-structure_v2-command.json`, failed v2 script and traceback | Exact in raw |

Shell read tool outputs were observed, but a complete exported read-command/UTC ledger is unavailable; this is an evidence limit, not fabricated success or a silently dropped unknown.
Runtime/model/API test and production invocations have their own retained command records, XML, logs, snapshots and DB lifecycle evidence.
