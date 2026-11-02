"""Owned Task9 implementation evidence orchestration."""
import asyncio
from datetime import UTC, datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = R / "docs/superpowers/reports/task9-frozen-metrics-code-failure-evidence"
HEAD = "ffc607d4908dc50d3d7977d8056a7d33385b78e5"
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
sys.path.insert(0, str(E))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(name, value):
    with (E / name).open("x") as out:
        json.dump(value, out, indent=2, default=str)
        out.write("\n")


def snapshot():
    import bootstrap
    value = bootstrap.snapshot()
    for name, root in (("m3", R), ("primary", R.with_name("eduagent"))):
        value[name]["source_metadata"] = {
            p: (root / p).lstat().st_mtime_ns for p in value[name]["source"]
        }
    value["m3"]["runtime"] = bootstrap.metadata(Path(PY).parent.parent)
    return value


def setup():
    ports = []
    for _ in range(3):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    assert len(set(ports)) == 3
    save("ports.json", dict(zip(("redis", "vite", "production"), ports)))
    names = [
        "bootstrap.py", "review.py", "frontend_run.py", "safety.py", "conftest.py",
        "live_server.py", "test_independent_integrity.py", "test_chain_metadata.py",
        "test_spec_relations.py", "test_spec_corroboration.py", "test_code_attacks.py",
        "test_extra_code.py", "test_minimum_evidence.py", "test_fresh_leaf_identity.py",
        "test_fresh_active_leaf.py", "prepare.py", "test_complementary_metrics.py",
        "test_code_boundary.py",
    ]
    replacements = {
        "/private/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814": str(E.resolve()),
        "/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814": str(E),
        "a3e2c0b0f510235cec8a98784afdb26b3bb6db79": HEAD,
        "m3_t9_codee8c530_": "m3_t9_metrics410687_",
    }
    replacements.update({old: str(new) for old, new in zip(("56684", "56685", "56686"), ports)})
    def rebound(text):
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    for name in names:
        (E / name).write_text(rebound((A / name).read_text()))
    # All generated source is a mechanical copy of the archived runner.
    initial = snapshot()
    assert initial["m3"]["head"] == HEAD and not initial["m3"]["status"]
    assert initial["m3"]["source_count"] == 357
    assert initial["m3"]["source_sha256"] == "14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813"
    save("initial-snapshot.json", initial)
    save("matrix-snapshot.json", initial)
    save("role.json", dict(role="fresh implementer, not reviewer", head=HEAD,
        parent="a3e2c0b0f510235cec8a98784afdb26b3bb6db79",
        model_requests=0, actual_model_cost_usd="0", http_total="unknown",
        agent50="semantic paused", started_at=datetime.now(UTC).isoformat()))
    prepare = load("owned_prepare", E / "prepare.py")
    prepare.verify_blobs(HEAD, initial["m3"]["tracked"])
    save("initial-gitblobs.json", dict(m3=len(initial["m3"]["tracked"]),
        source_count=357, verified_revision=HEAD))
    save("shared-pg-identity.json", asyncio.run(prepare.pg_identity()))
    save("runtime-version.json", dict(command=[PY, "--version"],
        stdout=subprocess.check_output([PY, "--version"]).decode()))
    for name in initial["m3"]["source"]:
        if name.startswith("frontend/"):
            dest = E / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(R / name, dest)
    for name in ("vite.config.ts", "playwright.config.ts",
                 "playwright.production.config.ts", "live-e2e/spec-health.spec.ts"):
        dest = E / "frontend" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rebound((A / "frontend" / name).read_text()))
    shutil.copytree(R / "frontend/node_modules", E / "frontend/node_modules", symlinks=True)
    links = {}
    for path in (E / "frontend/node_modules").rglob("*"):
        if path.is_symlink():
            path.resolve().relative_to((E / "frontend/node_modules").resolve())
            links[str(path.relative_to(E))] = str(path.resolve())
    save("physical-modules-copy.json", dict(source=str(R / "frontend/node_modules"),
        destination=str(E / "frontend/node_modules"), internal_links=links))
    import redis
    service = E / "redis-service"
    service.mkdir(mode=0o700)
    cmd = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", str(ports[0]),
        "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
        "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
        "--logfile", str(service / "redis.log")]
    subprocess.run(cmd, check=True)
    client = redis.Redis(host="127.0.0.1", port=ports[0], decode_responses=True)
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert info["process_id"] == int((service / "redis.pid").read_text())
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    save("owned-redis-identity.json", dict(command=cmd, port=ports[0],
        pid=info["process_id"], run_id=info["run_id"], config=config,
        initial_keys=client.keys("*"), time=datetime.now(UTC).isoformat()))
    for name in ("m3-task9-metrics-code-fail-postcommit.json", "m3-task9-metrics-code-fail-commit.log"):
        shutil.copy2(Path("/tmp") / name, E / name)
    save("setup-after.json", snapshot())
    assert snapshot() == initial
    print(json.dumps(dict(evidence=str(E), ports=ports, setup="complete")))


def main():
    action = sys.argv[1]
    if action == "setup":
        setup()
        return 0
    import bootstrap
    bootstrap.snapshot = snapshot_base = bootstrap.snapshot
    original = snapshot_base
    def protected():
        value = original()
        for name, root in (("m3", R), ("primary", R.with_name("eduagent"))):
            value[name]["source_metadata"] = {
                p: (root / p).lstat().st_mtime_ns for p in value[name]["source"]
            }
        value["m3"]["runtime"] = bootstrap.metadata(Path(PY).parent.parent)
        return value
    bootstrap.snapshot = protected
    if action == "checkpoint":
        save(sys.argv[2], protected())
        return 0
    import review
    if action == "pytest":
        return review.run_pytest(sys.argv[2], sys.argv[3:])
    sys.argv = [str(E / "frontend_run.py"), action, *sys.argv[2:]]
    load("owned_frontend", E / "frontend_run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
