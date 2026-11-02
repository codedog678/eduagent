import asyncio
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import asyncpg
from dotenv import dotenv_values
from packaging.requirements import Requirement
import redis
import review

OWN = review.OWN
ROOT = review.ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_inventory(path):
    files, links = {}, {}
    for p in sorted(path.rglob("*")):
        if p.is_symlink():
            p.resolve().relative_to(path.resolve())
            links[str(p.relative_to(path))] = os.readlink(p)
        elif p.is_file():
            files[str(p.relative_to(path))] = sha(p.read_bytes())
    return {"files": files, "symlinks": links,
            "sha256": sha(json.dumps(sorted(files.items()), separators=(",", ":")).encode())}


def dependencies():
    project = tomllib.loads((ROOT / "python/pyproject.toml").read_text())
    installed = {d.metadata["Name"].lower().replace("_", "-"): d.version
                 for d in importlib.metadata.distributions()}
    constraints = []
    for group, reqs in (
        ("project", project["project"]["dependencies"]),
        ("dev", project["project"]["optional-dependencies"]["dev"]),
        ("build", project["build-system"]["requires"]),
        ("container", [s.strip() for s in (ROOT / "python/requirements.txt").read_text().splitlines()
                       if s.strip() and not s.lstrip().startswith("#")]),
    ):
        for raw in reqs:
            requirement = Requirement(raw)
            name = requirement.name.lower().replace("_", "-")
            applies = requirement.marker is None or requirement.marker.evaluate()
            version = installed.get(name)
            matches = not applies or (version is not None and version in requirement.specifier)
            constraints.append({"group": group, "constraint": raw, "installed": version,
                                "applies": applies, "matches": matches})
    assert all(c["matches"] for c in constraints)
    proc = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode == 0
    parent = Path("/tmp/m3-task9-new-runtime-parent-dependency-input")
    audit = json.loads((parent / "audit.json").read_text())
    scan = json.loads((parent / "scan-manifest.json").read_text())
    assert scan["audit_sha256"] == sha((parent / "audit.json").read_bytes())
    assert scan["input_sha256"] == sha((parent / "requirements.txt").read_bytes())
    assert len(audit["dependencies"]) == 57
    assert all(installed[d["name"]] == d["version"] and not d["vulns"]
               for d in audit["dependencies"])
    saved = OWN / "parent-dependency-evidence"
    shutil.copytree(parent, saved)
    review.write("dependency-independent-check.json", {
        "time": datetime.now(UTC).isoformat(), "python": sys.version,
        "installed": installed, "installed_count": len(installed), "constraints": constraints,
        "pip_check": {"command": [sys.executable, "-m", "pip", "check"],
                      "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
        "parent_scan_role": "parent execution, independently parsed and matched; NOT my vulnerability scan",
        "parent_scan": scan, "parent_scan_current_versions_match": True,
        "modules_physical": file_inventory(OWN / "frontend/node_modules"),
        "dist": file_inventory(OWN / "frontend/dist")})


def raw():
    records, xml = {}, {}
    protected = {"node_modules", "cache", "tmp", "__pycache__", "pycache", "vite-cache",
                 "npm-cache", ".vite", ".vite-temp"}
    values = set()
    for root in (ROOT, ROOT.with_name("eduagent")):
        for p in (root / ".env", root / "python/.env", root / ".env.local", root / "python/.env.local"):
            if p.is_file():
                values.update(v.encode() for k, v in dotenv_values(p).items() if v and
                              any(w in k for w in ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")))
    hits = []
    for p in sorted(OWN.rglob("*")):
        if not p.is_file() or protected.intersection(p.relative_to(OWN).parts):
            continue
        data = p.read_bytes()
        rel = str(p.relative_to(OWN))
        records[rel] = {"sha256": sha(data), "bytes": len(data)}
        if p.suffix == ".xml":
            cases = list(ET.fromstring(data).iter("testcase"))
            xml[rel] = {"tests": len(cases), "failure": sum(c.find("failure") is not None for c in cases),
                        "error": sum(c.find("error") is not None for c in cases),
                        "skip": sum(c.find("skipped") is not None for c in cases),
                        "sha256": sha(data),
                        "failures": [{"name": c.get("name"), "type": e.tag, "message": e.get("message")}
                                     for c in cases for e in c if e.tag in {"failure", "error"}]}
        if p.suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None
                members = {}
                for m in z.infolist():
                    if m.is_dir():
                        continue
                    b = z.read(m)
                    members[m.filename] = {"sha256": sha(b), "bytes": len(b)}
                    if any(v in b for v in values):
                        hits.append(rel + ":" + m.filename)
                records[rel]["members"] = members
        if any(v in data for v in values):
            hits.append(rel)
    assert not hits
    prod = {}
    for p in sorted(OWN.glob("production-*.json")):
        body = json.loads(p.read_text())
        assert not body["errors"] and body["overflow"] <= 1
        assert all(r["method"] == "GET" for r in body["requests"])
        assert all(h == sha((OWN / "frontend/dist" / url.split(":38731/")[1]).read_bytes())
                   for url, h in body["hashes"].items())
        prod[p.name] = {"page_get_requests": len(body["requests"]), "hashes": body["hashes"],
                        "errors": body["errors"], "overflow": body["overflow"]}
    review.write("raw-parsed-summary.json", {
        "time": datetime.now(UTC).isoformat(), "records": records, "xml": xml, "production": prod,
        "local_secret_values_distinct": len(values), "secret_matches": hits,
        "requests_scope": "browser page recorded GETs only; pytest/API helper requests not globally counted",
        "source_hash_excludes_evidence": True})
    print(json.dumps({"xml": {p: {k: v for k, v in r.items() if k != "failures"} for p, r in xml.items()},
                      "raw_files": len(records), "local_secret_values": len(values), "secret_hits": len(hits)}))


async def pg_cleanup_verify():
    declared = {}
    for p in [*OWN.glob("*-command.json"), *OWN.glob("*-lifecycle.json")]:
        record = json.loads(p.read_text())
        if "db" in record:
            assert re.fullmatch("m3_t9_spec_[0-9a-f]{32}", record["db"])
            assert record["drop_exit"] == 0
            declared[p.name] = record["db"]
    conn = await asyncpg.connect(user="postgres", database="postgres", host="127.0.0.1", port=57432)
    try:
        data_dir = await conn.fetchval("SHOW data_directory")
        identity = json.loads((OWN / "shared-pg-identity.json").read_text())
        assert data_dir == identity["data_dir"]
        assert int((Path(data_dir) / "postmaster.pid").read_text().splitlines()[0]) == identity["pid"]
        rows = await conn.fetch("SELECT datname FROM pg_database WHERE datname = ANY($1::text[])",
                                list(declared.values()))
        assert not rows
        return {"shared_service_preserved": identity, "declared_owned": declared, "actual_remaining": []}
    finally:
        await conn.close()


def cleanup():
    review.snapshot("cleanup-before")
    pg = asyncio.run(pg_cleanup_verify())
    client = redis.Redis(host="127.0.0.1", port=58479, decode_responses=True)
    original = json.loads((OWN / "owned-redis-identity.json").read_text())
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert info["run_id"] == original["run_id"] and info["process_id"] == original["pid"]
    assert config == original["config"]
    keys = sorted(client.scan_iter())
    ledger = [json.loads(l) for l in (OWN / "redis-command-ledger.jsonl").read_text().splitlines()]
    recorded = sorted({k for row in ledger for k in row["exact_keys"]})
    del_commands = [row for row in ledger if row["command"] in {"DEL", "UNLINK"}]
    assert not any(row["command"] in {"FLUSHALL", "FLUSHDB"} for row in ledger)
    review.write("resource-before-shutdown.json", {
        "time": datetime.now(UTC).isoformat(), "postgres": pg, "redis_identity": original,
        "actual_remaining_keys": keys, "recorded_exact_keys": recorded,
        "remaining_unrecorded_keys": sorted(set(keys) - set(recorded)),
        "ledger_complete_for_subprocess": False, "exact_del_commands": del_commands,
        "cleanup_method": "own instance identity checked SHUTDOWN NOSAVE; no broad DEL or flush"})
    client.shutdown(nosave=True)
    client.close()
    ports = {}
    for port in (58479, 38730, 38731):
        with socket.socket() as sock:
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(ports.values())
    procs = subprocess.check_output(["ps", "-axo", "pid=,command="]).decode().splitlines()
    browser = [p for p in procs if str(OWN) in p and any(w in p.lower() for w in ("chrome", "chromium", "playwright", "vite", "live_server"))]
    assert not browser, browser
    shutil.copytree(OWN / "frontend/dist", OWN / "retained-http-dist")
    removed = []
    for relative in ("frontend/node_modules", "frontend/dist", "cache", "tmp", "__pycache__",
                     "pycache", "vite-cache", "npm-cache"):
        p = OWN / relative
        if p.exists():
            p.resolve().relative_to(OWN.resolve())
            assert not p.is_symlink()
            shutil.rmtree(p)
            removed.append(relative)
    review.write("resource-after-cleanup.json", {
        "time": datetime.now(UTC).isoformat(), "ports_closed": ports,
        "remaining_owned_browser_processes": browser, "removed_own_caches": removed,
        "retained_raw_assets": "retained-http-dist",
        "shared_pg_runtime_preserved": True, "model_calls": 0, "model_cost_usd": "0"})
    review.snapshot("final-after")


if __name__ == "__main__":
    {"dependencies": dependencies, "raw": raw, "cleanup": cleanup}[sys.argv[1]]()
