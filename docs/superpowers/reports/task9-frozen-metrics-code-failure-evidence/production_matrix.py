"""Owned production invocations; never runs historical setup entry points."""
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys

E = Path(__file__).parent
scenarios = [
    "current", "history", "genuine_valid", "genuine_malformed_latest_valid",
    "minimum_zero", "referenced_canary_poison", "approval_malformed_latest",
    "leaf_local_bad", "leaf_active_bad", "leaf_local_valid",
    "leaf_active_valid", "leaf_shadow_valid",
    "metrics_canary_commit_failed", "metrics_active_permission_violation",
    "metrics_shadow_unknown_counter", "metrics_active_valid",
]
results = []
for scenario in scenarios:
    label = "code-production-" + scenario
    started = datetime.now(UTC).isoformat()
    command = [sys.executable, "-B", str(E / "control.py"),
               "run", "production", label, scenario]
    proc = subprocess.run(command)
    results.append(dict(scenario=scenario, command=command, exit=proc.returncode,
                        started_at=started, finished_at=datetime.now(UTC).isoformat()))
with (E / "production-matrix.json").open("x") as output:
    json.dump(results, output, indent=2)
    output.write("\n")
sys.exit(1 if any(row["exit"] for row in results) else 0)
