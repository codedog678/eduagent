import asyncio
from datetime import UTC, datetime
import difflib
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
ARCHIVE = ROOT / "docs/superpowers/reports/task9-minimum-fix-evidence"
HEAD = "a6500f5a4fb8ce1494742735655841230b6124fe"
PRODUCT = "d77299c710a4d330539010d9067c5b4938f4adf1"
os.environ.update(GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip() == HEAD
    assert subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=ROOT).decode().strip() == PRODUCT
    ports = []
    for _ in range(3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    assert len(set(ports)) == 3
    replacements = {
        "/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb": str(OWN),
        "6147cec5bff26d60a3422b0f43f133b2db782e8f": HEAD,
        "9ef34434cc72f270085d234d89eae5f22d3d6ecd": PRODUCT,
        "61803": str(ports[0]), "61804": str(ports[1]), "61805": str(ports[2]),
        "m3_t9_minfix_": "m3_t9_ws90d3_",
        "minimum fix implementer": "fresh independent WHOLE SPEC reviewer",
    }
    names = (
        "bootstrap.py", "prepare.py", "review.py", "frontend_run.py", "safety.py",
        "conftest.py", "live_server.py", "test_independent_integrity.py",
        "test_chain_metadata.py", "test_spec_relations.py", "test_spec_corroboration.py",
        "test_code_attacks.py", "test_extra_code.py", "test_minimum_evidence.py",
        "artifact_checks.py",
    )
    provenance = {}
    for name in names:
        original = (ARCHIVE / name).read_text()
        text = original
        for old, new in replacements.items():
            text = text.replace(old, new)
        (OWN / name).write_text(text)
        provenance[name] = {
            "origin": str((ARCHIVE / name).relative_to(ROOT)),
            "diff": "".join(difflib.unified_diff(
                original.splitlines(keepends=True), text.splitlines(keepends=True),
                fromfile=str(ARCHIVE / name), tofile=str(OWN / name))),
        }
    import bootstrap
    import prepare
    initial = bootstrap.snapshot()
    assert initial["m3"]["source_count"] == 355
    assert initial["m3"]["source_sha256"] == "7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc"
    assert not initial["m3"]["status"] and not initial["primary"]["status"]
    prepare.verify_blobs(HEAD, initial["m3"]["tracked"])
    prepare.verify_blobs(PRODUCT, initial["m3"]["source"])
    data = subprocess.check_output(
        ["git", "cat-file", "--batch"],
        input="".join(f"{initial['primary']['head']}:{p}\n" for p in initial["primary"]["tracked"]).encode(),
        cwd=ROOT.with_name("eduagent"))
    pos = 0
    for name, digest in initial["primary"]["tracked"].items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert header[1] == b"blob", name
        size = int(header[2])
        pos = end + 1
        assert prepare.sha(data[pos:pos + size]) == digest, name
        pos += size + 1
    assert pos == len(data)
    prepare.write("initial-snapshot.json", initial)
    prepare.write("matrix-snapshot.json", initial)
    prepare.write("runner-rebinding.json", {"replacements": replacements, "scripts": provenance})
    prepare.write("review-identity.json", {
        "role": "fresh independent WHOLE SPEC reviewer; not implementer, parent provenance or WHOLE CODE",
        "head": HEAD, "product": PRODUCT, "product_parent": subprocess.check_output(
            ["git", "rev-parse", "HEAD^^"], cwd=ROOT).decode().strip(),
        "scope_start": "8869166878a193a1c453376471cbe52c8fa84b3f",
        "own": str(OWN), "ports": ports, "started_at": datetime.now(UTC).isoformat(),
        "model_calls": 0, "model_cost_usd": "0", "http_total": "unknown",
        "m3_tracked_blobs_verified": len(initial["m3"]["tracked"]),
        "primary_tracked_blobs_verified": len(initial["primary"]["tracked"]),
    })
    for name, path in (
        ("authorized-brief.md", "/tmp/m3-task9-minimum-spec-brief.md"),
        ("old-complete-scope-brief.md", "/tmp/m3-task9-complete-chain-spec-brief.md"),
        ("implementation-brief.md", "/tmp/m3-task9-minimum-fix-brief.md"),
        ("implementation-result.md", "/tmp/m3-task9-minimum-fix-result.md"),
    ):
        shutil.copy2(path, OWN / name)
    (OWN / "whole-task9-source.diff").write_bytes(subprocess.check_output([
        "git", "diff", "8869166878a193a1c453376471cbe52c8fa84b3f", HEAD,
        "--", "python", "frontend"], cwd=ROOT))
    prepare.raw_audit()
    front = OWN / "frontend"
    front.mkdir()
    for name in subprocess.check_output(["git", "ls-files", "-z", "--", "frontend"], cwd=ROOT).split(b"\0"):
        if not name:
            continue
        source = ROOT / name.decode()
        target = front / source.relative_to(ROOT / "frontend")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in ("vite.config.ts", "playwright.config.ts", "playwright.production.config.ts",
                 "live-e2e/spec-health.spec.ts"):
        text = (ARCHIVE / "frontend" / name).read_text()
        for old, new in replacements.items():
            text = text.replace(old, new)
        target = front / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    shutil.copytree(ROOT / "frontend/node_modules", front / "node_modules", symlinks=True)
    modules = (front / "node_modules").resolve()
    entries = {}
    for path in sorted((front / "node_modules").rglob("*")):
        if path.is_symlink():
            path.resolve().relative_to(modules)
            entries[str(path.relative_to(front))] = {"link": os.readlink(path)}
        elif path.is_file():
            entries[str(path.relative_to(front))] = {"sha256": prepare.sha(path.read_bytes())}
    prepare.write("dependency-physical-copy.json", {
        "physical_copy": True, "no_external_symlinks": True, "entries": entries})
    prepare.write("shared-pg-identity.json", asyncio.run(prepare.pg_identity()))
    for port in ports:
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
    service = OWN / "redis-service"
    service.mkdir(mode=0o700)
    command = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", str(ports[0]),
               "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
               "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
               "--logfile", str(service / "redis.log")]
    subprocess.run(command, check=True)
    import redis
    client = redis.Redis(host="127.0.0.1", port=ports[0], decode_responses=True)
    assert client.ping() and client.dbsize() == 0
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    assert int((service / "redis.pid").read_text()) == info["process_id"]
    prepare.write("owned-redis-identity.json", {
        "time": datetime.now(UTC).isoformat(), "command": command,
        "pid": info["process_id"], "run_id": info["run_id"], "port": ports[0],
        "config": config, "version": info["redis_version"], "initial_keys": [], "shared": False})
    assert bootstrap.snapshot() == initial
    print(json.dumps({"own": str(OWN), "ports": ports, "redis_pid": info["process_id"],
                      "head": HEAD, "source_count": 355, "shared_pg_pid": 16852}))


if __name__ == "__main__":
    main()
