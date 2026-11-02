import asyncio
from datetime import UTC, datetime
import difflib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess

R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = R / "docs/superpowers/reports/task9-leaf-code-failure-evidence"
E = Path("/tmp/m3-task9-leaf-fix-8551ecba-8589-42a0-b9d7-b3873a329816")
HEAD = "855d5c6660343c24df0bef5ad4cf77160e83c566"
os.environ.update(GIT_OPTIONAL_LOCKS="0", PYTHONDONTWRITEBYTECODE="1")


def main():
    E.mkdir(mode=0o700)
    shutil.copy2(__file__, E / "setup.py")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=R).decode().strip() == HEAD
    assert subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=R).decode().strip() == "c52aaababba238ec26282f8c560c8f565a60a09e"
    ports = []
    for _ in range(3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    assert len(set(ports)) == 3
    replacements = {
        "/tmp/m3-task9-wholecode-40baa8dc-0414-46d1-b816-90149468b042": str(E),
        "c52aaababba238ec26282f8c560c8f565a60a09e": HEAD,
        "56737": str(ports[0]), "56738": str(ports[1]), "56739": str(ports[2]),
        "m3_t9_wc40baa_": "m3_t9_leaf8551_",
        "fresh independent WHOLE CODE reviewer": "fresh Task9 leaf implementer",
        "CODE prohibits non-loopback connections": "implementation prohibits non-loopback connections",
    }
    names = (
        "bootstrap.py", "prepare.py", "review.py", "frontend_run.py", "safety.py",
        "conftest.py", "live_server.py", "test_independent_integrity.py",
        "test_chain_metadata.py", "test_spec_relations.py", "test_spec_corroboration.py",
        "test_code_attacks.py", "test_extra_code.py", "test_minimum_evidence.py",
        "test_fresh_leaf_identity.py", "test_fresh_active_leaf.py", "artifact_checks.py",
    )
    provenance = {}
    for name in names:
        original = (A / name).read_text()
        changed = original
        for old, new in replacements.items():
            changed = changed.replace(old, new)
        (E / name).write_text(changed)
        provenance[name] = {"origin": str(A / name), "diff": "".join(difflib.unified_diff(
            original.splitlines(keepends=True), changed.splitlines(keepends=True)))}
    import sys
    sys.path.insert(0, str(E))
    import bootstrap
    import prepare
    initial = bootstrap.snapshot()
    assert initial["m3"]["source_count"] == 355
    assert initial["m3"]["source_sha256"] == "7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc"
    assert initial["primary"]["head"] == "2ff803c968d64741d149e5a1ce88a823d4d32422"
    assert not initial["m3"]["status"] and not initial["primary"]["status"]
    prepare.verify_blobs(HEAD, initial["m3"]["tracked"])
    data = subprocess.check_output(["git", "cat-file", "--batch"], cwd=R.with_name("eduagent"),
        input="".join(f"{initial['primary']['head']}:{p}\n" for p in initial["primary"]["tracked"]).encode())
    pos = 0
    for p, digest in initial["primary"]["tracked"].items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert header[1] == b"blob", p
        size = int(header[2])
        pos = end + 1
        assert prepare.sha(data[pos:pos + size]) == digest, p
        pos += size + 1
    assert pos == len(data)
    prepare.write("initial-snapshot.json", initial)
    prepare.write("matrix-snapshot.json", initial)
    prepare.write("runner-rebinding.json", {"replacements": replacements, "scripts": provenance})
    prepare.write("implementation-identity.json", {
        "role": "fresh implementer; not SPEC/CODE/parent reviewer", "head": HEAD,
        "parent": "c52aaababba238ec26282f8c560c8f565a60a09e",
        "product": "d77299c710a4d330539010d9067c5b4938f4adf1",
        "own": str(E), "ports": ports, "started_at": datetime.now(UTC).isoformat(),
        "model_calls": 0, "model_cost_usd": "0", "http_total": "unknown",
        "m3_tracked_blobs_verified": len(initial["m3"]["tracked"]),
        "primary_tracked_blobs_verified": len(initial["primary"]["tracked"])})
    for p in ("/tmp/m3-task9-leaf-authenticity-fix-brief.md", "/tmp/m3-task9-minimum-spec-brief.md",
              "/tmp/m3-task9-minimum-code-brief.md", "/tmp/m3-task9-complete-chain-code-brief.md",
              "/tmp/m3-task9-complete-chain-spec-brief.md"):
        shutil.copy2(p, E / Path(p).name)
    prepare.raw_audit()
    front = E / "frontend"
    front.mkdir()
    for name in subprocess.check_output(["git", "ls-files", "-z", "--", "frontend"], cwd=R).split(b"\0"):
        if name:
            src = R / name.decode()
            target = front / src.relative_to(R / "frontend")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    for name in ("vite.config.ts", "playwright.config.ts", "playwright.production.config.ts",
                 "live-e2e/spec-health.spec.ts"):
        original = (A / "frontend" / name).read_text()
        changed = original
        for old, new in replacements.items():
            changed = changed.replace(old, new)
        target = front / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(changed)
        provenance["frontend/" + name] = {"origin": str(A / "frontend" / name),
            "diff": "".join(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True)))}
    prepare.write("frontend-rebinding.json", provenance)
    shutil.copytree(R / "frontend/node_modules", front / "node_modules", symlinks=True)
    modules = (front / "node_modules").resolve()
    entries = {}
    for p in sorted((front / "node_modules").rglob("*")):
        if p.is_symlink():
            p.resolve().relative_to(modules)
            entries[str(p.relative_to(front))] = {"link": os.readlink(p)}
        elif p.is_file():
            entries[str(p.relative_to(front))] = {"sha256": prepare.sha(p.read_bytes())}
    prepare.write("dependency-physical-copy.json", {"physical_copy": True, "no_external_symlinks": True,
                                                   "entries": entries})
    prepare.write("shared-pg-identity.json", asyncio.run(prepare.pg_identity()))
    service = E / "redis-service"
    service.mkdir(mode=0o700)
    cmd = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", str(ports[0]),
           "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
           "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
           "--logfile", str(service / "redis.log")]
    subprocess.run(cmd, check=True)
    import redis
    client = redis.Redis(host="127.0.0.1", port=ports[0], decode_responses=True)
    assert client.ping() and client.dbsize() == 0
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    assert int((service / "redis.pid").read_text()) == info["process_id"]
    prepare.write("owned-redis-identity.json", {
        "time": datetime.now(UTC).isoformat(), "command": cmd, "pid": info["process_id"],
        "run_id": info["run_id"], "port": ports[0], "config": config,
        "version": info["redis_version"], "initial_keys": [], "shared": False})
    assert bootstrap.snapshot() == initial
    print(json.dumps({"own": str(E), "ports": ports, "redis_pid": info["process_id"], "head": HEAD}))


if __name__ == "__main__":
    main()
