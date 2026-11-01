"""在专用数据库上验证当前冻结源；只写 /tmp，不改项目环境。"""
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

root = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
primary = Path("/Users/bytedance/Documents/trae_projects/eduagent")
py = "/tmp/eduagent-m3-patched-runtime/bin/python"
pg = Path("/opt/homebrew/opt/postgresql@16/bin")
out = Path("/tmp/m3-patched-runtime-baseline-365a115")
out.mkdir(exist_ok=True)

def git(*args, cwd=root):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()

def snapshot():
    source = {}
    for path in git("ls-files", "python", "frontend").splitlines():
        if "/evidence/" in path or Path(path).suffix not in {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".toml", ".json", ".yaml", ".yml",
        }:
            continue
        source[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    return {
        "head": git("rev-parse", "HEAD"),
        "source_sha256": hashlib.sha256(
            json.dumps(source, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "source_files": source,
        "m3_status": git("status", "--short", "--branch"),
        "primary_head": git("rev-parse", "HEAD", cwd=primary),
        "primary_status": git("status", "--short", "--branch", cwd=primary),
    }

started = datetime.now(timezone.utc).isoformat()
before = snapshot()
(out / "before.json").write_text(json.dumps(before, indent=2) + "\n")
database = "m3_patchbase_" + uuid4().hex
admin = ["-h", "127.0.0.1", "-p", "55432", "-U", "postgres"]
subprocess.run([str(pg / "createdb"), *admin, database], check=True)
env = dict(os.environ)
env.update({
    "DISTRIBUTED_TEST_DATABASE_URL":
        "postgresql+asyncpg://postgres@127.0.0.1:55432/" + database,
    "DISTRIBUTED_TEST_REDIS_URL": "redis://127.0.0.1:56379/0",
    "PYTHONPATH": str(root / "python"),
    "PYTHONPYCACHEPREFIX": str(out / "pycache"),
    "TZ": "UTC",
})
command = [
    py, "-m", "pytest", "tests", "-q",
    "-o", "cache_dir=" + str(out / "pytest-cache"),
    "--junitxml=" + str(out / "full.xml"),
]
result = None
cleanup = None
try:
    with (out / "full.log").open("wb") as log:
        result = subprocess.run(command, cwd=root / "python", env=env,
                                stdout=log, stderr=subprocess.STDOUT).returncode
finally:
    cleanup = subprocess.run(
        [str(pg / "dropdb"), *admin, database],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    after = snapshot()
    (out / "after.json").write_text(json.dumps(after, indent=2) + "\n")
counts = {}
if (out / "full.xml").is_file():
    suites = ET.parse(out / "full.xml").getroot()
    cases = list(suites.iter("testcase"))
    counts = {
        "test_executions": len(cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skips": sum(case.find("skipped") is not None for case in cases),
    }
files = {
    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
    for path in out.iterdir() if path.is_file() and path.name != "manifest.json"
}
manifest = {
    "started_at_utc": started,
    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    "command": command,
    "cwd": str(root / "python"),
    "database": database,
    "database_cleanup_exit": cleanup,
    "exit_code": result,
    "counts": counts,
    "source_revision": before["head"],
    "source_unchanged": before["source_files"] == after["source_files"],
    "primary_unchanged": before["primary_head"] == after["primary_head"]
        and before["primary_status"] == after["primary_status"],
    "data_role": "preimplementation_dependency_compatibility",
    "release_eligible": False,
    "scope": "current Task9 freeze only; rerun against final Task10 source required",
    "new_model_requests": 0,
    "cost": None,
    "hashes": files,
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({k: manifest[k] for k in (
    "source_revision", "exit_code", "counts", "database_cleanup_exit",
    "source_unchanged", "primary_unchanged", "scope",
)}, ensure_ascii=False))
sys.exit(result if result is not None else 1)
