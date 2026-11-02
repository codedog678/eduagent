import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4
from urllib.request import urlopen

import review

OWN = review.OWN
NODE = "/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node"
FRONT = OWN / "frontend"
env = os.environ.copy()
for key in list(env):
    if key == "DATABASE_URL" or any(word in key for word in ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")):
        env.pop(key, None)
env.update(PATH=str(Path(NODE).parent) + ":" + env["PATH"], PYTHONPATH=f"{review.ROOT}/python:{OWN}",
           PYTHONDONTWRITEBYTECODE="1", REVIEW_OWN=str(OWN),
           PYTHONPYCACHEPREFIX=str(OWN / "pycache"), TMPDIR=str(OWN / "tmp"),
           npm_config_cache=str(OWN / "npm-cache"), TZ="UTC")


def execute(label, command):
    started = datetime.now(UTC).isoformat()
    with (OWN / (label + ".log")).open("x") as out:
        result = subprocess.run(command, cwd=FRONT, env=env, stdout=out, stderr=subprocess.STDOUT)
    review.write(label + "-command.json", {"command": command, "cwd": str(FRONT),
                 "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
                 "exit": result.returncode, "node": subprocess.check_output([NODE, "--version"]).decode().strip()})
    print((OWN / (label + ".log")).read_text()[-3500:])
    return result.returncode


mode = sys.argv[1]
label = sys.argv[2]
review.snapshot(label + "-before")
try:
    env["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] = str(OWN / (label + ".xml"))
    if mode == "build":
        result = execute(label, ["npm", "run", "build"])
    elif mode == "ui":
        result = execute(label, [NODE, str(FRONT / "node_modules/@playwright/test/cli.js"), "test",
                          "--reporter=line,junit", "--output=" + str(OWN / (label + "-output")), *sys.argv[3:]])
    elif mode == "production":
        scenario = sys.argv[3]
        env.update(SPEC_SCENARIO=scenario, EVIDENCE_RUN=label,
                   DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:61803/0",
                   SPEC_RUN_TAG=label)
        db = "m3_t9_minfix_" + uuid4().hex
        args = ["-h", "127.0.0.1", "-p", "57432", "-U", "postgres", db]
        subprocess.run([review.PG + "createdb", *args], check=True)
        env["DISTRIBUTED_TEST_DATABASE_URL"] = f"postgresql+asyncpg://postgres@127.0.0.1:57432/{db}"
        server = None
        (OWN / "screenshots").mkdir(exist_ok=True)
        with (OWN / (label + "-server.log")).open("x") as output:
            try:
                server = subprocess.Popen([review.PY, str(OWN / "live_server.py")], cwd=review.ROOT / "python",
                                          env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 45
                while True:
                    if server.poll() is not None:
                        raise RuntimeError((OWN / (label + "-server.log")).read_text())
                    try:
                        with urlopen("http://127.0.0.1:61805/ops/", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(0.1)
                result = execute(label, [NODE, str(FRONT / "node_modules/@playwright/test/cli.js"), "test",
                    "--config=playwright.production.config.ts", "--reporter=line,junit",
                    "--output=" + str(OWN / (label + "-output"))])
            finally:
                if server is not None and server.poll() is None:
                    server.terminate()
                    server.wait(timeout=15)
                dropped = subprocess.run([review.PG + "dropdb", *args])
                review.write(label + "-lifecycle.json", {"db": db, "server_pid": server.pid if server else None,
                    "server_exit": server.returncode if server else None, "drop_exit": dropped.returncode})
                assert dropped.returncode == 0
    else:
        raise ValueError(mode)
finally:
    review.snapshot(label + "-after")
sys.exit(result)
