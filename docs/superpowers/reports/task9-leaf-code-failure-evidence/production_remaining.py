"""Sequential independent production fixtures on our exclusively owned port."""

from datetime import UTC, datetime
import subprocess

import review

rows = []
for label, scenario in [
    ("approval-malformed", "approval_malformed_latest"),
    ("genuine-malformed", "genuine_malformed_latest_valid"),
    ("genuine-valid", "genuine_valid"),
    ("referenced-poison", "referenced_canary_poison"),
    ("minimum-zero", "minimum_zero"),
]:
    command = [review.PY, "-B", str(review.OWN / "frontend_run.py"),
               "production", "prod-final-" + label, scenario]
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(command)
    rows.append({"command": command, "started_at": started,
                 "finished_at": datetime.now(UTC).isoformat(), "exit": result.returncode})
    if result.returncode:
        break
review.write("production-remaining-batch.json", {"commands": rows, "model_calls": 0})
assert len(rows) == 5 and all(row["exit"] == 0 for row in rows)
