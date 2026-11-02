import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tomllib
from datetime import UTC, datetime

from bootstrap import OWN, ROOT, write

PY = "/Users/bytedance/.local/share/uv/python/cpython-3.11.17-macos-aarch64-none/bin/python3.11"
RUNTIME = Path("/tmp/eduagent-m3-patched-runtime")
PG = Path("/opt/homebrew/opt/postgresql@16/bin")
SERVICE = Path("/Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36")


def run(label, command, env=None):
    record = {"command": command, "started_at": datetime.now(UTC).isoformat()}
    with (OWN / (label + ".log")).open("x") as out:
        proc = subprocess.run(command, env=env, stdout=out, stderr=subprocess.STDOUT)
    record.update(exit=proc.returncode, finished_at=datetime.now(UTC).isoformat())
    write(OWN / (label + "-command.json"), record)
    print(label, proc.returncode, (OWN / (label + ".log")).read_text()[-1500:])
    proc.check_returncode()


def runtime():
    assert not RUNTIME.exists(), "do not overwrite another runtime"
    run("runtime-create", [PY, "-m", "venv", str(RUNTIME)])
    doc = tomllib.loads((ROOT / "python/pyproject.toml").read_text())
    requirements = [*doc["project"]["dependencies"], *doc["project"]["optional-dependencies"]["dev"],
                    *doc["build-system"]["requires"],
                    *(ROOT / "python/requirements.txt").read_text().splitlines(),
                    "anyio>=4.14.2", "certifi>=2026.10.18", "pydantic-settings>=2.14.2",
                    "setuptools>=84.1.0", "starlette>=1.3.1"]
    run("runtime-install", [str(RUNTIME / "bin/python"), "-m", "pip", "install",
                           "--cache-dir", str(OWN / "pip-cache"), *requirements])
    run("runtime-pip-check", [str(RUNTIME / "bin/python"), "-m", "pip", "check"])
    run("runtime-freeze", [str(RUNTIME / "bin/python"), "-m", "pip", "freeze", "--all"])
    run("runtime-pip-inspect", [str(RUNTIME / "bin/python"), "-m", "pip", "inspect"])


def services():
    for port in (57432, 57379, 37730, 37731):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0, f"port in use: {port}"
    assert not SERVICE.exists()
    SERVICE.mkdir(parents=True, mode=0o700)
    data = SERVICE / "pgdata"
    run("pg-init", [str(PG / "initdb"), "-D", str(data), "-U", "postgres",
                    "--auth=trust", "--encoding=UTF8", "--locale=C"])
    run("pg-start", [str(PG / "pg_ctl"), "-D", str(data), "-l", str(SERVICE / "postgres.log"),
                    "-o", f"-h 127.0.0.1 -p 57432 -k {SERVICE}", "-w", "start"])
    redis_and_identity()


def recover_pg():
    data = SERVICE / "pgdata"
    run("pg-start-v2", [str(PG / "pg_ctl"), "-D", str(data), "-l", str(SERVICE / "postgres.log"),
                       "-o", "-h 127.0.0.1 -p 57432 -k ''", "-w", "start"])
    redis_and_identity()


def redis_and_identity():
    data = SERVICE / "pgdata"
    run("redis-start", ["/opt/homebrew/bin/redis-server", "--bind", "127.0.0.1",
                       "--port", "57379", "--protected-mode", "yes", "--daemonize", "yes",
                       "--dir", str(SERVICE), "--save", "", "--appendonly", "no",
                       "--pidfile", str(SERVICE / "redis.pid"), "--logfile", str(SERVICE / "redis.log")])
    save_identity()


def save_identity():
    data = SERVICE / "pgdata"
    run("redis-ready", ["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1", "-p", "57379", "PING"])
    run("pg-ready", [str(PG / "pg_isready"), "-h", "127.0.0.1", "-p", "57432", "-U", "postgres"])
    write(OWN / "service-identity.json", {
        "role": "shared isolated loopback engineering tests; not production",
        "parent": str(SERVICE), "postgres_data_dir": str(data),
        "postgres_pid": int((data / "postmaster.pid").read_text().splitlines()[0]),
        "redis_pid": int((SERVICE / "redis.pid").read_text()),
        "postgres_port": 57432, "redis_port": 57379, "redis_db": 0,
        "postgres_bin": str(PG), "redis_bin": "/opt/homebrew/bin/redis-server",
        "runtime": str(RUNTIME), "started_at": datetime.now(UTC).isoformat(),
        "test_database_policy": "new UUID per invocation; finally drop",
        "redis_cleanup_policy": "exact UUID keys only; never flush/prefix delete",
    })


def modules():
    shutil.copytree(ROOT / "frontend/node_modules", OWN / "frontend/node_modules", symlinks=True)
    for p in (OWN / "frontend/node_modules").rglob("*"):
        if p.is_symlink():
            p.resolve().relative_to(OWN / "frontend/node_modules")
    for p in (Path("/tmp/m3-task9-recovery-parent-evidence-verification.json"),
              Path("/tmp/m3-task9-recovery-parent-evidence-verification.py")):
        if p.exists():
            dest = OWN / "parent-role"
            dest.mkdir(exist_ok=True)
            shutil.copy2(p, dest / p.name)


if __name__ == "__main__":
    import sys
    {"runtime": runtime, "services": services, "recover-pg": recover_pg,
     "identity": save_identity, "modules": modules}[sys.argv[1]]()
