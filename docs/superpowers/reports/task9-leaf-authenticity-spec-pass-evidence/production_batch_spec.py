"""Serial isolated production scenarios, each with an independent UUID database."""
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess

E = Path(__file__).parent
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
scenarios = [
    "history", "approval_malformed_latest", "genuine_malformed_latest_valid",
    "genuine_valid", "referenced_canary_poison", "minimum_zero",
    "leaf_local_bad", "leaf_active_bad", "leaf_local_valid",
    "leaf_active_valid", "leaf_shadow_valid",
]
started = datetime.now(UTC).isoformat()
commands = []
try:
    for scenario in scenarios:
        command = [PY, "-B", str(E / "control.py"), "run", "production",
                   "spec-production-" + scenario, scenario]
        start = datetime.now(UTC).isoformat()
        result = subprocess.run(command, cwd=E)
        commands.append(dict(command=command, started_at=start,
            finished_at=datetime.now(UTC).isoformat(), exit=result.returncode))
        if result.returncode:
            raise RuntimeError(scenario)
finally:
    with (E / "production-batch-command.json").open("x") as out:
        json.dump(dict(started_at=started, finished_at=datetime.now(UTC).isoformat(),
                       commands=commands), out, indent=2)
        out.write("\n")
