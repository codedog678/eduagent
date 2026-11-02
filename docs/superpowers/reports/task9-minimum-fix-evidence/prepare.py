import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import asyncpg
import redis

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = ROOT / "docs/superpowers/reports/task9-complete-chain-recovery-evidence"
HEAD = "6147cec5bff26d60a3422b0f43f133b2db782e8f"
PRODUCT = "9ef34434cc72f270085d234d89eae5f22d3d6ecd"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, value):
    with (OWN / name).open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def git(*args, input=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, input=input)


def verify_blobs(revision, files):
    data = git("cat-file", "--batch", input="".join(
        f"{revision}:{p}\n" for p in files).encode())
    pos = 0
    for name, digest in files.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", name
        size = int(header[2])
        pos = end + 1
        assert sha(data[pos:pos + size]) == digest, name
        pos += size + 1
    assert pos == len(data)


def raw_audit():
    records = {}
    for p in (ROOT / "docs/superpowers/reports").rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(ROOT))
        if "task9" not in rel:
            continue
        data = p.read_bytes()
        item = {"sha256": sha(data), "bytes": len(data)}
        if p.suffix == ".json":
            parsed = json.loads(data)
            item["json_type"] = type(parsed).__name__
        elif p.suffix == ".jsonl":
            lines = [json.loads(line) for line in data.splitlines() if line.strip()]
            item["jsonl_lines"] = len(lines)
        elif p.suffix == ".xml":
            root = ET.fromstring(data)
            cases = list(root.iter("testcase"))
            item["counts"] = dict(tests=len(cases),
                failure=sum(c.find("failure") is not None for c in cases),
                error=sum(c.find("error") is not None for c in cases),
                skip=sum(c.find("skipped") is not None for c in cases))
            item["failures"] = [
                {"classname": c.get("classname"), "name": c.get("name"),
                 "kind": e.tag, "message": e.get("message"), "text": e.text}
                for c in cases for e in c if e.tag in ("failure", "error")]
        elif p.suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None, rel
                members = {}
                for member in z.infolist():
                    if member.is_dir():
                        continue
                    content = z.read(member)
                    entry = {"sha256": sha(content), "bytes": len(content)}
                    if member.filename.endswith((".trace", ".network")):
                        events = [json.loads(line) for line in content.splitlines() if line.strip()]
                        entry["events"] = len(events)
                    members[member.filename] = entry
                item["members"] = members
        elif p.suffix not in (".png", ".tar"):
            data.decode("utf-8")
            item["text_read_full"] = True
        records[rel] = item
    verify_blobs(HEAD, {p: r["sha256"] for p, r in records.items()})
    manifests = {}
    for p in (ROOT / "docs/superpowers/reports").rglob("*manifest*.json"):
        if "task9" not in str(p):
            continue
        data = json.loads(p.read_bytes())
        mapping = data.get("files", data.get("files_sha256"))
        if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values()):
            continue
        checked = 0
        for name, digest in mapping.items():
            target = p.parent / name
            if target.is_file():
                assert sha(target.read_bytes()) == digest, str(target)
                checked += 1
        manifests[str(p.relative_to(ROOT))] = {
            "sha256": sha(p.read_bytes()), "declared": len(mapping), "checked": checked}
    write("historical-and-recovery-raw-audit.json", {
        "role": "minimum fix implementer byte/structure audit, not inherited execution",
        "time": datetime.now(UTC).isoformat(), "files": records, "manifests": manifests})


async def pg_identity():
    db = await asyncpg.connect(user="postgres", database="postgres", host="127.0.0.1", port=57432)
    try:
        data = await db.fetchval("SHOW data_directory")
        version = await db.fetchval("SHOW server_version")
        names = [r["datname"] for r in await db.fetch("SELECT datname FROM pg_database ORDER BY datname")]
        pid = int((Path(data) / "postmaster.pid").read_text().splitlines()[0])
        assert pid == 16852
        assert data == "/Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36/pgdata"
        return {"shared": True, "port": 57432, "pid": pid, "data_dir": data,
                "version": version, "before_database_names": names}
    finally:
        await db.close()


def main():
    assert git("rev-parse", "HEAD").decode().strip() == HEAD
    assert git("rev-parse", "HEAD^").decode().strip() == PRODUCT
    resumed = (OWN / "initial-snapshot.json").exists()
    for name in (() if resumed else ("bootstrap.py", "review.py", "frontend_run.py", "safety.py", "conftest.py",
                 "live_server.py", "test_independent_integrity.py", "test_chain_metadata.py",
                 "test_spec_relations.py", "test_spec_corroboration.py", "test_code_attacks.py",
                 "test_extra_code.py")):
        text = (A / name).read_text()
        text = text.replace("85c2759d54fd55691cf69d98df91c81ad9caf65b", HEAD)
        text = text.replace("57379", "61803").replace("37730", "61804").replace("37731", "61805")
        text = text.replace("m3_t9_fix_", "m3_t9_minfix_")
        (OWN / name).write_text(text)
    import bootstrap
    initial = bootstrap.snapshot()
    assert initial["m3"]["source_count"] == 354
    assert initial["m3"]["source_sha256"] == "6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96"
    verify_blobs(HEAD, initial["m3"]["tracked"])
    verify_blobs(PRODUCT, initial["m3"]["source"])
    if resumed:
        assert initial == json.loads((OWN / "initial-snapshot.json").read_text())
        write("preparation-attempt-boundary.json", {
            "time": datetime.now(UTC).isoformat(),
            "error": "ValueError: resolved /private/tmp path relative_to unresolved /tmp node_modules",
            "phase": "modules ownership check, before services or tests",
            "model_calls": 0, "pytest_invocations": 0, "product_failure": False})
    else:
        write("initial-snapshot.json", initial)
        write("review-identity.json", {
        "role": "minimum fix implementer Task9 SPEC reviewer",
        "head": HEAD, "product": PRODUCT, "base": "8869166878a193a1c453376471cbe52c8fa84b3f",
        "own": str(OWN), "started_at": datetime.now(UTC).isoformat(),
            "inherited_execution_not_owned": True, "model_calls": 0, "model_cost_usd": "0"})
        raw_audit()
    front = OWN / "frontend"
    front.mkdir(exist_ok=True)
    for name in ([] if resumed else git("ls-files", "-z", "--", "frontend").split(b"\0")):
        if not name:
            continue
        source = ROOT / name.decode()
        dest = front / source.relative_to(ROOT / "frontend")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in (() if resumed else ("vite.config.ts", "playwright.config.ts", "playwright.production.config.ts",
                 "live-e2e/spec-health.spec.ts")):
        dest = front / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = (A / "frontend" / name).read_text()
        text = text.replace("/tmp/m3-task9-chain-recovery-d7c17eb6-6c53-4bca-9c54-26b53147cd36", str(OWN))
        text = text.replace("37730", "61804").replace("37731", "61805")
        dest.write_text(text)
    if not resumed:
        shutil.copytree(ROOT / "frontend/node_modules", front / "node_modules", symlinks=True)
    for p in (front / "node_modules").rglob("*"):
        if p.is_symlink():
            p.resolve().relative_to((front / "node_modules").resolve())
    write("shared-pg-identity.json", asyncio.run(pg_identity()))
    for port in (61803, 61804, 61805):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0, port
    service = OWN / "redis-service"
    service.mkdir(mode=0o700)
    cmd = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", "61803",
           "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
           "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
           "--logfile", str(service / "redis.log")]
    subprocess.run(cmd, check=True)
    client = redis.Redis(host="127.0.0.1", port=61803, decode_responses=True)
    assert client.ping()
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    write("owned-redis-identity.json", {
        "time": datetime.now(UTC).isoformat(), "command": cmd, "pid": info["process_id"],
        "run_id": info["run_id"], "version": info["redis_version"], "port": 61803,
        "config": config, "initial_keys": client.keys("*"), "shared": False})
    assert bootstrap.snapshot() == initial
    print(json.dumps({"own": str(OWN), "source_count": 354, "preparation": "complete",
                      "redis_pid": info["process_id"], "shared_pg_pid": 16852}))


if __name__ == "__main__":
    main()
