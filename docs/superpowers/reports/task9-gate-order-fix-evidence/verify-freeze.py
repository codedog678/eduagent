"""Verify the exact repair commit and frozen bytes; do not update evidence."""

import json
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from provenance import EVIDENCE, PRIMARY, ROOT, digest, git, junit, original, sha, source

REPORT = "docs/superpowers/reports/2026-11-02-m3-task9-gate-order-fix.md"
PARENT = "38f48d763b4a9599aa215f98a2cba1b32003b1e7"
PRODUCT = {"python/core/distributed/ops_queries.py",
           "python/tests/distributed/test_promotion_ops_api.py"}
manifest = json.loads((EVIDENCE / "manifest.json").read_text())
files = {str(p.relative_to(EVIDENCE)): sha(p.read_bytes())
         for p in sorted(EVIDENCE.rglob("*")) if p.is_file() and p.name != "manifest.json"}
assert files == manifest["files"]
assert digest(files) == manifest["retained_sha256"]
assert source(ROOT) == manifest["source"]
assert original() == manifest["original_task9"]
assert {p: junit(EVIDENCE / p) for p in manifest["junit"]} == manifest["junit"]
assert {p: junit(ROOT / p) for p in manifest["original_task9_junit"]} == manifest["original_task9_junit"]
for entry in manifest["independent_retention"]["retained"]:
    assert files[entry["archive_path"]] == entry["sha256"]
patterns = [
    rb"sk-[A-Za-z0-9_-]{24,}", rb"gh[pousr]_[A-Za-z0-9]{30,}",
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]
scanned = 0
for p in EVIDENCE.rglob("*"):
    if not p.is_file():
        continue
    blobs = [p.read_bytes()]
    if p.suffix == ".zip":
        with ZipFile(p) as archive:
            blobs.extend(archive.read(name) for name in archive.namelist() if not name.endswith("/"))
    for blob in blobs:
        assert not any(re.search(pattern, blob) for pattern in patterns), str(p)
        scanned += 1
head = git(ROOT, "rev-parse", "HEAD")
precommit = "--precommit" in sys.argv
if precommit:
    assert head == PARENT
else:
    assert git(ROOT, "rev-parse", "HEAD^") == PARENT
prefix = str(EVIDENCE.relative_to(ROOT)) + "/"
allowed = PRODUCT | {REPORT, prefix + "manifest.json"} | {prefix + p for p in files}
changed = set((git(ROOT, "diff", "--cached", "--name-only") if precommit else
               git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", head)).splitlines())
assert changed == allowed, {"unexpected": sorted(changed - allowed), "missing": sorted(allowed - changed)}
for path in changed | set(manifest["source"]) | set(manifest["original_task9"]):
    ref = f":{path}" if precommit else f"{head}:{path}"
    frozen = subprocess.check_output(["git", "-C", str(ROOT), "show", ref])
    assert frozen == (ROOT / path).read_bytes(), path
if precommit:
    subprocess.check_call(["git", "-C", str(ROOT), "diff", "--exit-code"])
    assert all(line[:2] in {"A ", "M "} for line in git(ROOT, "status", "--porcelain").splitlines())
else:
    assert not git(ROOT, "status", "--porcelain")
baseline = json.loads((EVIDENCE / "cleanup-check-after.json").read_text())
assert git(PRIMARY, "rev-parse", "HEAD") == baseline["primary_head"]
assert git(PRIMARY, "status", "--porcelain") == baseline["primary_status"] == ""
assert digest(source(PRIMARY)) == baseline["primary_source_sha256"]
for path, mtime in baseline["protected_mtime_ns"].items():
    assert Path(path).stat().st_mtime_ns == mtime, path
print(json.dumps({
    "mode": "staged precommit" if precommit else "frozen postcommit",
    "commit": head, "parent": PARENT, "changed_paths": len(changed),
    "source_count": manifest["source_count"], "source_sha256": manifest["source_sha256"],
    "retained_count_excluding_manifest": len(files), "retained_sha256": digest(files),
    "manifest_sha256": sha((EVIDENCE / "manifest.json").read_bytes()),
    "report_sha256": sha((ROOT / REPORT).read_bytes()),
    "original_task9_preserved_count": len(manifest["original_task9"]),
    "original_task9_junit_count": len(manifest["original_task9_junit"]),
    "retained_independent_count": len(manifest["independent_retention"]["retained"]),
    "new_and_archived_junit_count": len(manifest["junit"]),
    "paired_runs": len(manifest["runs"]), "secret_pattern_blobs_scanned": scanned,
    "primary_head": baseline["primary_head"], "primary_clean": True,
    "m3_clean": not precommit, "unstaged_clean": True,
    "gitblob_working_bytes_equal": True,
}, indent=2))
