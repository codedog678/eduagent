import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import UTC, datetime

own = Path(__file__).parent
label, command = sys.argv[1], sys.argv[2:]
started = datetime.now(UTC).isoformat()
env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
with (own / (label + "-launcher.log")).open("x") as output:
    result = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT)
with (own / (label + "-launcher.json")).open("x") as out:
    json.dump(dict(command=command, cwd=os.getcwd(), started_at=started,
                   finished_at=datetime.now(UTC).isoformat(), exit=result.returncode,
                   model_calls=0, model_cost_usd="0", http_total="unknown"), out, indent=2)
    out.write("\n")
print((own / (label + "-launcher.log")).read_text()[-3000:])
sys.exit(result.returncode)
