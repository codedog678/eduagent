import hashlib
import json
from pathlib import Path
import subprocess

OWN = Path(__file__).parent
def sha(data):
    return hashlib.sha256(data).hexdigest()
def digest(files):
    return sha(json.dumps(sorted(files.items()), separators=(",", ":"), ensure_ascii=True).encode())

first = json.loads((OWN / "full-before.json").read_text())
last = json.loads((OWN / "review-final.json").read_text())
assert first == last
pg = subprocess.run([
    "/opt/homebrew/opt/postgresql@16/bin/psql", "-h", "127.0.0.1", "-p", "55432",
    "-U", "postgres", "-d", "postgres", "-At", "-c",
    "SELECT datname FROM pg_database WHERE datname LIKE 'm3_t9_code_%'",
], capture_output=True, text=True)
assert pg.returncode == 0 and not pg.stdout.strip()
listeners = subprocess.run(["lsof", "-nP", "-iTCP:33490", "-iTCP:33491", "-sTCP:LISTEN"],
                           capture_output=True, text=True)
assert listeners.returncode == 1 and not listeners.stdout.strip()
deleted = ["frontend/node_modules", "frontend/dist", "pycache", "pytest-cache", "npm-cache", "vite-cache", "tmp", "live.pid"]
assert not any((OWN / name).exists() for name in deleted)
redis = json.loads((OWN / "redis-cleanup.json").read_text())
assert not redis["remaining"]
cleanup = {
    "first_to_final_unchanged": True, "snapshot_pairs": 7,
    "pg_own_namespace": {"command": pg.args, "exit_code": pg.returncode, "stdout": pg.stdout},
    "listeners": {"command": listeners.args, "exit_code": listeners.returncode, "stdout": listeners.stdout},
    "removed_own_paths": deleted, "redis_deleted": len(redis["existed_and_deleted"]),
    "redis_remaining": 0, "live_exit_code": 143,
    "live_cleanup": (OWN / "live-cleanup.log").read_text().strip(),
    "source_sha256": last["m3"]["source_authoritative_sha"],
    "protected_venv_metadata": last["venv"],
}
(OWN / "cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
files = {str(p.relative_to(OWN)): sha(p.read_bytes()) for p in OWN.rglob("*")
         if p.is_file() and p != OWN / "manifest.json"}
manifest = {
    "role": "fresh independent full Task9 CODE FAIL evidence",
    "head": last["m3"]["head"], "product_revision": "e29bdb4d0c1b0e07b0e60a62ee61df3ae2e9915e",
    "base": "8869166878a193a1c453376471cbe52c8fa84b3f",
    "source_sha256": last["m3"]["source_authoritative_sha"],
    "files": files, "retained_count": len(files), "retained_sha256": digest(files),
    "junit": json.loads((OWN / "verification.json").read_text())["fresh_xml"],
}
(OWN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({
    "retained_count": len(files), "retained_sha256": digest(files),
    "manifest_sha256": sha((OWN / "manifest.json").read_bytes()),
    "build_sha256": sha((OWN / "build.log").read_bytes()),
    "script_sha256": sha((OWN / "test_code_attacks.py").read_bytes()),
    "extra_script_sha256": sha((OWN / "test_extra_code.py").read_bytes()),
    "archive_xml_count": len(json.loads((OWN / "verification.json").read_text())["archive_xml"]),
    "cleanup": cleanup,
}, indent=2))
