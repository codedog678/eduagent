"""Verify staged source blobs and create a noncircular raw archive manifest."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
ARCHIVE = ROOT / "docs/superpowers/reports/task9-health-binding-fix-evidence"
identity = json.loads((ARCHIVE / "source-manifest.json").read_text())
for path, expected in identity["files_sha256"].items():
    blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f":{path}"])
    assert hashlib.sha256(blob).hexdigest() == expected, path
mapping = {str(path.relative_to(ARCHIVE)): hashlib.sha256(path.read_bytes()).hexdigest()
           for path in sorted(ARCHIVE.rglob("*")) if path.is_file() and path.name != "manifest.json"}
body = {
    "parent": identity["parent"], "role": "implementation validation; parent review required",
    "source_authoritative_sha256": identity["authoritative_sha256"],
    "raw_files": len(mapping), "files_sha256": mapping,
    "manifest_scope": "all archive files except manifest.json; no circular digest",
    "payload_sha256": hashlib.sha256(json.dumps(sorted(mapping.items()),
        separators=(",", ":"), ensure_ascii=True).encode()).hexdigest(),
}
(ARCHIVE / "manifest.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
print(json.dumps({key: value for key, value in body.items() if key != "files_sha256"}, indent=2))
