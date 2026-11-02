"""Sequential owned production invocations; each runner owns a finally-dropped DB."""
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess

E = Path(__file__).parent
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
scenarios = [
    "current", "history", "genuine_valid", "approval_malformed_latest",
    "genuine_malformed_latest_valid", "referenced_canary_poison", "minimum_zero",
    "leaf_local_bad", "leaf_active_bad", "leaf_local_valid",
    "leaf_active_valid", "leaf_shadow_valid",
    "metrics_canary_commit_failed", "metrics_shadow_unknown_counter",
    "metrics_active_permission_violation", "metrics_active_valid", "trace_pinned",
]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
           TASK9_MATRIX_SNAPSHOT=os.environ.get("TASK9_MATRIX_SNAPSHOT", "metrics-source-before3.json"))
prefix = os.environ.get("PRODUCTION_PREFIX", "final-production-")
results = []
for scenario in scenarios:
    command = [PY, str(E / "wave.py"), "production",
               prefix + scenario, scenario]
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(command, env=env, cwd=E)
    results.append(dict(scenario=scenario, command=command, exit=result.returncode,
                        started_at=started, finished_at=datetime.now(UTC).isoformat()))
with (E / (prefix + "batch.json")).open("x") as out:
    json.dump(results, out, indent=2)
    out.write("\n")
assert all(item["exit"] == 0 for item in results)
