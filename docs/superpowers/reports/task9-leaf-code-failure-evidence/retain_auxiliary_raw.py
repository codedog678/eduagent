"""Retain original tool failure output, never synthesize missing raw."""

from datetime import UTC, datetime
import shutil
from pathlib import Path

import review

root = Path("/Users/bytedance/Library/Application Support/Trae CN/ModularData/ai-agent/command-execution")
commands = {
    "invalid-read-production-spec": "80b90d13238ef85a7de5a35a737027c9",
    "invalid-read-ui-context": "7afe2f92ed6c7a7805bae1b13569641a",
    "invalid-xml-count-assumption": "42e0bd6b4854ae31889be04ca4e7a664",
    "xml-count-diagnostic": "00a0776d0997945c3fb9269a380dfc2c",
}
rows = []
for label, command in commands.items():
    source = root / command / "output.log"
    target = review.OWN / (label + "-original-tool-output.log")
    if source.is_file():
        shutil.copyfile(source, target)
        rows.append({"command_id": command, "original_output": target.name, "available": True})
    else:
        rows.append({"command_id": command, "available": False, "raw": "unknown/unavailable"})
review.write("original-auxiliary-output-retention.json", {
    "time_captured": datetime.now(UTC).isoformat(), "rows": rows,
    "no_reconstruction_of_missing_raw": True,
    "redis_pid_file": "removed by normal shutdown; original identity and final verified PID retained",
})
