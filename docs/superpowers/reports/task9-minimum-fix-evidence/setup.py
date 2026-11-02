import asyncio
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from datetime import UTC, datetime

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
ARCHIVE = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence"
HEAD = "6147cec5bff26d60a3422b0f43f133b2db782e8f"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip() == HEAD
    ports = []
    for _ in range(3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    assert len(set(ports)) == 3
    substitutions = {
        "ed42d33a187115825a8a94fb45ae8b4652cf4c11": HEAD,
        "/tmp/m3-task9-wholespec-7116c864-8783-4351-92c2-550bf3427d3e": str(OWN),
        "58479": str(ports[0]), "38730": str(ports[1]), "38731": str(ports[2]),
        "m3_t9_spec_": "m3_t9_minfix_",
        "fresh independent WHOLE": "minimum fix implementer",
        "fresh WHOLE SPEC independent": "minimum fix implementer",
    }
    scripts = (
        "bootstrap.py", "review.py", "frontend_run.py", "safety.py", "conftest.py",
        "live_server.py", "test_independent_integrity.py", "test_chain_metadata.py",
        "test_spec_relations.py", "test_spec_corroboration.py", "test_code_attacks.py",
        "test_extra_code.py", "test_minimum_evidence.py", "prepare.py",
    )
    for name in scripts:
        text = (ARCHIVE / name).read_text()
        for old, new in substitutions.items():
            text = text.replace(old, new)
        (OWN / name).write_text(text)
    import bootstrap
    import prepare
    initial = bootstrap.snapshot()
    assert initial["m3"]["source_count"] == 354
    assert initial["m3"]["source_sha256"] == "6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96"
    prepare.verify_blobs(HEAD, initial["m3"]["tracked"])
    prepare.verify_blobs(HEAD, initial["m3"]["source"])
    prepare.write("initial-snapshot.json", initial)
    prepare.write("matrix-snapshot.json", initial)
    prepare.write("implementation-identity.json", {
        "role": "Task9 SPEC-1 fix implementer, not acceptance reviewer",
        "head": HEAD, "own": str(OWN), "ports": ports,
        "started_at": datetime.now(UTC).isoformat(), "model_calls": 0,
        "model_cost_usd": "0", "http_total": "unknown",
    })
    prepare.raw_audit()
    front = OWN / "frontend"
    front.mkdir()
    for name in subprocess.check_output(["git", "ls-files", "-z", "--", "frontend"], cwd=ROOT).split(b"\0"):
        if not name:
            continue
        source = ROOT / name.decode()
        dest = front / source.relative_to(ROOT / "frontend")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in ("vite.config.ts", "playwright.config.ts", "playwright.production.config.ts",
                 "live-e2e/spec-health.spec.ts"):
        text = (ARCHIVE / "frontend" / name).read_text()
        for old, new in substitutions.items():
            text = text.replace(old, new)
        dest = front / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    shutil.copytree(ROOT / "frontend/node_modules", front / "node_modules", symlinks=True)
    modules = (front / "node_modules").resolve()
    mapping = {}
    for path in sorted((front / "node_modules").rglob("*")):
        if path.is_symlink():
            path.resolve().relative_to(modules)
            mapping[str(path.relative_to(front))] = {"link": os.readlink(path)}
        elif path.is_file():
            mapping[str(path.relative_to(front))] = {"sha256": prepare.sha(path.read_bytes())}
    prepare.write("dependency-independent-check.json", {
        "physical_copy": True, "no_external_symlinks": True, "entries": mapping,
    })
    prepare.write("shared-pg-identity.json", asyncio.run(prepare.pg_identity()))
    for port in ports:
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
    service = OWN / "redis-service"
    service.mkdir(mode=0o700)
    cmd = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", str(ports[0]),
           "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
           "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
           "--logfile", str(service / "redis.log")]
    subprocess.run(cmd, check=True)
    import redis
    client = redis.Redis(host="127.0.0.1", port=ports[0], decode_responses=True)
    assert client.ping() and client.dbsize() == 0
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    prepare.write("owned-redis-identity.json", {
        "time": datetime.now(UTC).isoformat(), "command": cmd, "pid": info["process_id"],
        "run_id": info["run_id"], "port": ports[0], "config": config,
        "version": info["redis_version"], "initial_keys": [], "shared": False,
    })
    assert bootstrap.snapshot() == initial
    shutil.copy2("/tmp/m3-task9-minimum-fix-brief.md", OWN / "authorized-brief.md")
    print(json.dumps({"own": str(OWN), "ports": ports, "redis_pid": info["process_id"],
                      "shared_pg_pid": 16852, "start_source": initial["m3"]["source_sha256"]}))


if __name__ == "__main__":
    main()
