import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import bootstrap
from datetime import UTC, datetime
from uuid import uuid4
from xml.etree import ElementTree as ET

OWN = Path(__file__).parent
ROOT = Path(os.environ.get("TASK9_EXEC_ROOT", "/Users/bytedance/Documents/trae_projects/eduagent-m3"))
PRIMARY = ROOT.with_name("eduagent")
HEAD = "ed42d33a187115825a8a94fb45ae8b4652cf4c11"
PG = "/opt/homebrew/opt/postgresql@16/bin/"
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def write(name, data):
    path = OWN / name
    assert not path.exists(), name
    path.write_text(json.dumps(data, indent=2) + "\n")


def metadata(path):
    items = []
    if path.exists():
        for entry in [path, *sorted(path.rglob("*"))]:
            stat = entry.lstat()
            items.append((str(entry.relative_to(path)), stat.st_mode,
                          stat.st_size, stat.st_mtime_ns, stat.st_ino))
    return {"entries": len(items), "sha256": digest(json.dumps(items).encode())}


def snapshot(label):
    result = bootstrap.snapshot()
    initial = json.loads((OWN / "initial-snapshot.json").read_text())
    assert result == initial, "protected trees/index/venv/cache changed"
    from prepare import verify_blobs
    verify_blobs(HEAD, result["m3"]["tracked"])
    verify_blobs("9ef34434cc72f270085d234d89eae5f22d3d6ecd", result["m3"]["source"])
    assert result["primary"] == initial["primary"], "primary changed during this invocation"
    assert result["m3"]["source"] == initial["m3"]["source"], "M3 source changed during matrix"
    result["execution"] = {
        "root": str(ROOT), "mode": "BASELINE_REPLAY" if ROOT.resolve() == (OWN / "baseline").resolve() else "FINAL_SOURCE",
        "baseline_extra_test": "python/tests/distributed/test_ops_complete_chain.py",
    }
    write(label + ".json", result)
    print(json.dumps({k: {"head": v["head"], "source_count": len(v["source"]),
                          "sha": v["source_sha256"]} for k, v in result.items() if k != "execution"}))


def run_pytest(label, args):
    snapshot(label + "-before")
    db = "m3_t9_spec_" + uuid4().hex
    cmd_base = ["-h", "127.0.0.1", "-p", "57432", "-U", "postgres", db]
    subprocess.run([PG + "createdb", *cmd_base], check=True)
    env = os.environ.copy()
    for key in list(env):
        if key == "DATABASE_URL" or any(word in key for word in ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")):
            env.pop(key, None)
    env.update(DISTRIBUTED_TEST_DATABASE_URL=f"postgresql+asyncpg://postgres@127.0.0.1:57432/{db}",
               DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:58479/0",
               PYTHONPATH=f"{ROOT}/python:{OWN}", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPYCACHEPREFIX=str(OWN / "pycache"), TMPDIR=str(OWN / "tmp"),
               REVIEW_OWN=str(OWN), EVIDENCE_RUN=label, TZ="UTC")
    (OWN / "tmp").mkdir(exist_ok=True)
    cmd = [PY, "-m", "pytest", *args, "-p", "safety",
           "-o", f"cache_dir={OWN}/cache/{label}", f"--basetemp={OWN}/tmp/{label}",
           f"--junitxml={OWN}/{label}.xml"]
    record = {"db": db, "command": cmd, "cwd": str(ROOT / "python"),
              "started_at": datetime.now(UTC).isoformat(), "execution_root": str(ROOT),
              "mode": "BASELINE_REPLAY" if ROOT.resolve() == (OWN / "baseline").resolve() else "FINAL_SOURCE",
              "environment": {k: env[k] for k in (
                  "DISTRIBUTED_TEST_DATABASE_URL", "DISTRIBUTED_TEST_REDIS_URL", "PYTHONPATH",
                  "PYTHONDONTWRITEBYTECODE", "TMPDIR", "REVIEW_OWN", "EVIDENCE_RUN")},
              "model_calls": 0, "model_cost_usd": "0", "http_total": "unknown"}
    try:
        with (OWN / (label + ".log")).open("x") as output:
            proc = subprocess.run(cmd, cwd=ROOT / "python", env=env, stdout=output,
                                  stderr=subprocess.STDOUT)
        record["exit"] = proc.returncode
    finally:
        dropped = subprocess.run([PG + "dropdb", *cmd_base])
        record["drop_exit"] = dropped.returncode
        record["finished_at"] = datetime.now(UTC).isoformat()
        write(label + "-command.json", record)
        snapshot(label + "-after")
    print((OWN / (label + ".log")).read_text()[-4000:])
    assert dropped.returncode == 0
    return proc.returncode


def archives():
    records = {}
    for directory in sorted((ROOT / "docs/superpowers/reports").glob("task9*")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.xml")):
            tree = ET.parse(path).getroot()
            cases = list(tree.iter("testcase"))
            failures = [c for c in cases if c.find("failure") is not None]
            errors = [c for c in cases if c.find("error") is not None]
            records[str(path.relative_to(ROOT))] = {
                "sha256": digest(path.read_bytes()), "tests": len(cases),
                "failure": len(failures), "error": len(errors),
                "skip": sum(c.find("skipped") is not None for c in cases),
                "failure_messages": [{"name": c.get("name"),
                    "type": (c.find("failure") if c.find("failure") is not None else c.find("error")).get("type"),
                    "message": (c.find("failure") if c.find("failure") is not None else c.find("error")).get("message")}
                    for c in failures + errors]}
    checks = {}
    for name, field in (("task9-source-integrity-fix-evidence", "files_sha256"),
                        ("task9-health-binding-spec-failure-evidence", "files_sha256"),
                        ("task9-health-binding-fix-evidence", "files_sha256"),
                        ("task9-code-failure-evidence", "files")):
        archive = ROOT / "docs/superpowers/reports" / name
        manifest_name = "retained-manifest.json" if name == "task9-health-binding-spec-failure-evidence" else "manifest.json"
        manifest = json.loads((archive / manifest_name).read_text())
        if name == "task9-health-binding-spec-failure-evidence":
            field = "files"
        for p, expected in manifest[field].items():
            assert digest((archive / p).read_bytes()) == expected
            assert git(ROOT, "show", HEAD + ":" + str((archive / p).relative_to(ROOT))) == (archive / p).read_bytes()
        checks[name] = {"files": len(manifest[field]), "manifest_sha": digest((archive / manifest_name).read_bytes())}
    write("archive-parsed.json", {"xml": records, "checks": checks})
    print(json.dumps({"xml_count": len(records), "checks": checks}))


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "snapshot":
        snapshot(sys.argv[2])
    elif action == "archives":
        archives()
    elif action == "pytest":
        sys.exit(run_pytest(sys.argv[2], sys.argv[3:]))
