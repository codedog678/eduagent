import os
from pathlib import Path
import subprocess
import sys

own = Path(__file__).parent
scenarios = sys.argv[1:] or [
    "current", "history", "approval_malformed_latest", "genuine_malformed_latest_valid",
    "genuine_valid", "referenced_canary_poison", "minimum_zero",
    "leaf_local_bad", "leaf_active_bad", "leaf_local_valid",
    "leaf_active_valid", "leaf_shadow_valid",
]
env = {**os.environ, "TASK9_MATRIX_SNAPSHOT": "green-snapshot.json"}
for scenario in scenarios:
    subprocess.run(["/tmp/eduagent-m3-patched-runtime/bin/python", "frontend_run.py",
                    "production", os.environ.get("TASK9_PRODUCTION_PREFIX", "final-production-") + scenario, scenario],
                   cwd=own, env=env, check=True)
