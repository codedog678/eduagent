"""Verify independent raw evidence, record cleanup, and seal read-only review."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from provenance import EVIDENCE, OWN, digest, junit, sha, snapshot

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
expected = {
    "all-api.xml": 104,
    "fresh-attacks.xml": 23,
    "ui-40.xml": 40,
    "live-failed.xml": 8,
    "live-unknown.xml": 2,
    "live-run-detail-unknown.xml": 2,
}
raw = {}
for name, count in expected.items():
    path = EVIDENCE / name
    counts = junit(path)
    assert counts == {"tests": count, "failures": 0, "errors": 0, "skipped": 0}
    raw[name] = {"counts": counts, "sha256": sha(path.read_bytes())}
assert sum(value["counts"]["tests"] for value in raw.values()) == 179

front = json.loads((EVIDENCE / "frontend-isolation.json").read_text())
dist = {str(p.relative_to(OWN / "frontend/dist")): sha(p.read_bytes())
        for p in (OWN / "frontend/dist").rglob("*") if p.is_file()}
assert dist == front["dist"]
for name in ("production-http-desktop.json", "production-http-mobile.json",
             "production-http-unknown-desktop.json", "production-http-unknown-mobile.json"):
    http = json.loads((EVIDENCE / name).read_text())
    assert http["hashes"] == {p: h for p, h in dist.items() if p != "index.html"}
    assert http["methods"] and set(http["methods"]) == {"GET"}

def run(args):
    result = subprocess.run(args, text=True, capture_output=True)
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}

pg = run(["/opt/homebrew/opt/postgresql@16/bin/psql", "-h", "127.0.0.1", "-p", "55432",
          "-U", "postgres", "-d", "postgres", "-Atc",
          "SELECT datname FROM pg_database WHERE datname LIKE 'm3_t9_cspec_%';"])
assert pg["exit_code"] == 0 and pg["stdout"] == ""
ports = run(["lsof", "-nP", "-iTCP:33290", "-iTCP:33291", "-sTCP:LISTEN"])
assert ports["exit_code"] == 1 and ports["stdout"] == "" and ports["stderr"] == ""
redis = run(["redis-cli", "-h", "127.0.0.1", "-p", "56379", "-n", "0",
             "--scan", "--pattern", "m3_t9_cspec_*"])
assert redis["exit_code"] == 0 and redis["stdout"] == ""
shutil.copy2(OWN / "prepare.sh", EVIDENCE / "prepare.sh")
for name in ("playwright-ui", "playwright-live-failed", "playwright-live-unknown",
             "playwright-live-run-detail-unknown"):
    folder = OWN / name
    assert [p for p in folder.rglob("*") if p.is_file() and p.name != ".last-run.json"] == []
    last = folder / ".last-run.json"
    assert json.loads(last.read_text())["status"] == "passed"
    shutil.copy2(last, EVIDENCE / f"{name}-last-run.json")

deleted = []
for rel in ("frontend", "npm-cache", "pycache", "pytest-cache", "vite-cache",
            "playwright-ui", "playwright-live-failed", "playwright-live-unknown",
            "playwright-live-run-detail-unknown"):
    path = OWN / rel
    assert path.parent == OWN and path.is_dir() and not path.is_symlink()
    shutil.rmtree(path)
    deleted.append(str(path))
for rel in ("live-runner.pid", "prepare.sh"):
    path = OWN / rel
    path.unlink()
    deleted.append(str(path))
assert sorted(p.name for p in OWN.iterdir()) == ["evidence"]
result = {
    "role": "fresh independent reviewer executions; not implementer reruns",
    "raw_xml": raw, "total_test_executions": 179,
    "api_test_executions": 127, "browser_test_executions": 52,
    "real_pg_production_browser_executions": 12,
    "dist_sha256": digest(dist), "dist_files": dist,
    "database_audit": pg, "listener_audit": ports, "redis_prefix_audit": redis,
    "redis_deleted_keys": [], "redis_used_by_targeted_tests": False,
    "server_exit_codes": {"failed": 143, "unknown": 143},
    "server_exit_explanation": "intentional TERM; EXIT traps dropped owned databases and snapshotted",
    "deleted_owned_paths": deleted,
    "retained": "own evidence only; raw XML/log/scripts/config/SHA/screenshots/snapshots",
    "cleanup_assertions": "no own DBs, listeners, Redis prefix keys, caches/dependencies/dist/PID",
}
(EVIDENCE / "execution-summary.json").write_text(json.dumps(result, indent=2) + "\n")
snapshot("review-after")
print(json.dumps({"raw_xml": raw, "cleanup": result["cleanup_assertions"]}, indent=2))
