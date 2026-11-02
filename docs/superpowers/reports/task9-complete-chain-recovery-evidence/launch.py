import os
import subprocess
import sys
from datetime import UTC, datetime

from bootstrap import OWN, write

label, script, *args = sys.argv[1:]
cmd = ["/tmp/eduagent-m3-patched-runtime/bin/python", str(OWN / script), *args]
record = {"command": cmd, "started_at": datetime.now(UTC).isoformat(),
          "execution_root": os.environ.get("TASK9_EXEC_ROOT", "M3")}
with (OWN / (label + "-launcher.log")).open("x") as out:
    result = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT)
record.update(exit=result.returncode, finished_at=datetime.now(UTC).isoformat())
write(OWN / (label + "-launcher.json"), record)
print((OWN / (label + "-launcher.log")).read_text()[-4000:])
sys.exit(result.returncode)
