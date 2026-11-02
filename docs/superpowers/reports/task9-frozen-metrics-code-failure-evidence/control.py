"""Independent Task9 WHOLE CODE controller; writes only its UUID evidence tree."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = R / "docs/superpowers/reports/task9-leaf-authenticity-spec-pass-evidence"
HEAD = "a3e2c0b0f510235cec8a98784afdb26b3bb6db79"
PRODUCT = "1b8e4b745126c92cfd56f9f021388dd615d98791"
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
sys.path.insert(0, str(E))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(name, value):
    with (E / name).open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")


def freeport():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def setup():
    assert not (E / "initial-snapshot.json").exists()
    bootstrap = load("snapshot_tools", A / "bootstrap.py")
    initial = bootstrap.snapshot()
    assert initial["m3"]["head"] == HEAD and not initial["m3"]["status"]
    assert initial["m3"]["source_count"] == 357
    assert initial["m3"]["source_sha256"] == "14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813"
    assert initial["primary"]["head"] == "2ff803c968d64741d149e5a1ce88a823d4d32422"
    ports = [freeport() for _ in range(3)]
    assert len(set(ports)) == 3
    save("ports.json", dict(zip(("redis", "vite", "production"), ports)))
    scripts = [
        "bootstrap.py", "review.py", "frontend_run.py", "safety.py", "conftest.py",
        "live_server.py", "test_independent_integrity.py", "test_chain_metadata.py",
        "test_spec_relations.py", "test_spec_corroboration.py", "test_code_attacks.py",
        "test_extra_code.py", "test_minimum_evidence.py", "test_fresh_leaf_identity.py",
        "test_fresh_active_leaf.py", "prepare.py",
    ]
    replacements = {
        "/private/tmp/m3-task9-leaf-spec-9efac2fb-3201-4499-9be6-a10cde0023e7": str(E.resolve()),
        "/tmp/m3-task9-leaf-spec-9efac2fb-3201-4499-9be6-a10cde0023e7": str(E),
        "9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f": HEAD,
        "m3_t9_spec9efa_": "m3_t9_codee8c530_",
        "independent WHOLE SPEC provenance audit": "independent WHOLE CODE provenance audit",
    }
    for old, new in zip(("51476", "51477", "51478"), ports):
        replacements[old] = str(new)

    def rebound(text):
        # Mechanical rebinding only; no historical runner main is invoked.
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    for name in scripts:
        (E / name).write_text(rebound((A / name).read_text()))
    own_bootstrap = load("bootstrap", E / "bootstrap.py")
    sys.modules["bootstrap"] = own_bootstrap
    original_snapshot = own_bootstrap.snapshot

    def protected_snapshot():
        value = original_snapshot()
        for name, root in (("m3", R), ("primary", R.with_name("eduagent"))):
            value[name]["source_metadata"] = {
                p: (root / p).lstat().st_mtime_ns for p in value[name]["source"]
            }
        value["m3"]["runtime"] = own_bootstrap.metadata(Path(PY).parent.parent)
        return value

    initial = protected_snapshot()
    save("initial-snapshot.json", initial)
    save("matrix-snapshot.json", initial)
    for name, value in initial.items():
        if name in ("m3", "primary"):
            verify = load("blob_tools", A / "prepare.py")
            if name == "m3":
                verify.verify_blobs(HEAD, value["tracked"])
                verify.verify_blobs(PRODUCT, value["source"])
    # Primary uses its own Git object store.
    primary = R.with_name("eduagent")
    names = list(initial["primary"]["tracked"])
    data = subprocess.check_output(["git", "cat-file", "--batch"],
        cwd=primary, input="".join(f"{initial['primary']['head']}:{p}\n" for p in names).encode())
    pos = 0
    for name in names:
        end = data.index(b"\n", pos)
        size = int(data[pos:end].split()[2])
        pos = end + 1
        assert own_bootstrap.sha(data[pos:pos + size]) == initial["primary"]["tracked"][name]
        pos += size + 1
    save("actual-gitblobs.json", dict(head=HEAD, product=PRODUCT,
        m3=len(initial["m3"]["tracked"]), primary=len(names), source_count=357,
        source_sha256=initial["m3"]["source_sha256"]))
    for brief in (
        "leaf-authenticity-code", "leaf-authenticity-spec", "leaf-authenticity-fix",
        "minimum-spec", "minimum-code", "minimum-fix", "complete-chain-code",
        "complete-chain-spec", "recovery-implementation",
    ):
        shutil.copy2(f"/tmp/m3-task9-{brief}-brief.md", E / f"{brief}-brief.md")
    front = E / "frontend"
    for name in initial["m3"]["source"]:
        if not name.startswith("frontend/"):
            continue
        target = E / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(R / name, target)
    for name in ("vite.config.ts", "playwright.config.ts",
                 "playwright.production.config.ts", "live-e2e/spec-health.spec.ts"):
        target = front / name
        target.parent.mkdir(parents=True, exist_ok=True)
        text = rebound((A / "frontend" / name).read_text())
        if name.endswith("spec-health.spec.ts"):
            text = text.replace("info.project.name === 'mobile' && scenario !== 'current'",
                                "info.project.name === 'mobile'")
            text = text.replace("await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)",
                "await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(scrollBefore[0].left)")
        target.write_text(text)
    shutil.copytree(R / "frontend/node_modules", front / "node_modules", symlinks=True)
    links = {}
    for path in (front / "node_modules").rglob("*"):
        if path.is_symlink():
            path.resolve().relative_to((front / "node_modules").resolve())
            links[str(path.relative_to(E))] = str(path.resolve())
    save("modules-physical-copy.json", dict(source=str(R / "frontend/node_modules"),
        own=str(front / "node_modules"), internal_links=links, source_symlink=False))
    pg = load("pg_tools", E / "prepare.py")
    save("shared-pg-identity.json", asyncio.run(pg.pg_identity()))
    import redis
    service = E / "redis-service"
    service.mkdir(mode=0o700)
    cmd = ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1", "--port", str(ports[0]),
        "--protected-mode", "yes", "--daemonize", "yes", "--dir", str(service),
        "--save", "", "--appendonly", "no", "--pidfile", str(service / "redis.pid"),
        "--logfile", str(service / "redis.log")]
    start = datetime.now(UTC).isoformat()
    subprocess.run(cmd, check=True)
    client = redis.Redis(host="127.0.0.1", port=ports[0], decode_responses=True)
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert config["save"] == "" and config["appendonly"] == "no"
    assert Path(config["dir"]).resolve() == service.resolve()
    assert info["process_id"] == int((service / "redis.pid").read_text())
    save("owned-redis-identity.json", dict(command=cmd, started_at=start,
        finished_at=datetime.now(UTC).isoformat(), exit=0, port=ports[0],
        pid=info["process_id"], run_id=info["run_id"], config=config, keys=client.keys("*")))
    save("setup-after.json", protected_snapshot())
    assert protected_snapshot() == initial
    print(json.dumps(dict(evidence=str(E), ports=ports, source=357, setup="complete")))


def install_snapshot():
    import bootstrap
    original = bootstrap.snapshot

    def snapshot():
        value = original()
        for name, root in (("m3", R), ("primary", R.with_name("eduagent"))):
            value[name]["source_metadata"] = {
                p: (root / p).lstat().st_mtime_ns for p in value[name]["source"]
            }
        value["m3"]["runtime"] = bootstrap.metadata(Path(PY).parent.parent)
        return value

    bootstrap.snapshot = snapshot


def run():
    install_snapshot()
    import review
    mode, label = sys.argv[2:4]
    if mode == "pytest":
        return review.run_pytest(label, sys.argv[4:])
    sys.argv = [str(E / "frontend_run.py"), mode, label, *sys.argv[4:]]
    load("owned_frontend_execution", E / "frontend_run.py")
    return 0


if __name__ == "__main__":
    started = datetime.now(UTC).isoformat()
    if sys.argv[1] == "setup":
        try:
            setup()
        finally:
            save("setup-command.json", dict(command=sys.argv, cwd=os.getcwd(),
                started_at=started, finished_at=datetime.now(UTC).isoformat()))
    elif sys.argv[1] == "run":
        sys.exit(run())
