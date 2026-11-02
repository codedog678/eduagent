import json
from pathlib import Path
import sys

import bootstrap

own = Path(__file__).parent
snapshot = bootstrap.snapshot()
initial = json.loads((own / "initial-snapshot.json").read_text())
assert snapshot["primary"] == initial["primary"]
for key in ("venv", "vite", "vite_temp", "index_sha256", "index_mtime_ns"):
    assert snapshot["m3"][key] == initial["m3"][key], key
with (own / (sys.argv[1] + "-snapshot.json")).open("x") as out:
    json.dump(snapshot, out, indent=2)
    out.write("\n")
print(json.dumps({k: {"source_count": v["source_count"], "sha": v["source_sha256"]}
                  for k, v in snapshot.items()}))
