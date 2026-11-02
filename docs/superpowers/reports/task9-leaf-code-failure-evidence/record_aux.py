"""Capture every remaining auxiliary invocation without overwriting prior raw."""

from datetime import UTC, datetime
import subprocess
import sys

import review

label, command = sys.argv[1], sys.argv[2:]
started = datetime.now(UTC).isoformat()
with (review.OWN / (label + ".log")).open("x") as out:
    result = subprocess.run(command, cwd=review.OWN, stdout=out, stderr=subprocess.STDOUT)
review.write(label + "-aux-record.json", {
    "command": command, "cwd": str(review.OWN), "started_at": started,
    "finished_at": datetime.now(UTC).isoformat(), "exit": result.returncode,
    "model_calls": 0, "http_total": "unknown",
})
print((review.OWN / (label + ".log")).read_text()[-5000:])
sys.exit(result.returncode)
