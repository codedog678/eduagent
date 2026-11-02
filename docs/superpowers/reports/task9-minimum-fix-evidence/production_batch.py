import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

OWN = Path(__file__).parent
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
SCENARIOS = (
    "current", "history", "approval_malformed_latest", "genuine_malformed_latest_valid",
    "genuine_valid", "referenced_canary_poison", "minimum_zero",
)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TASK9_MATRIX_SNAPSHOT="final-snapshot.json")
records = []
for scenario in SCENARIOS:
    label = "prod-final-" + scenario
    command = [PY, str(OWN / "frontend_run.py"), "production", label, scenario]
    start = datetime.now(UTC).isoformat()
    result = subprocess.run(command, env=env)
    records.append(dict(scenario=scenario, command=command, started_at=start,
                        finished_at=datetime.now(UTC).isoformat(), exit=result.returncode))
    assert result.returncode == 0, scenario
with (OWN / "production-batch.json").open("x") as output:
    json.dump(records, output, indent=2)
    output.write("\n")
