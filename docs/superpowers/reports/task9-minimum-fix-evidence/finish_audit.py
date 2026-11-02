import asyncio
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
from urllib.parse import urlparse
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import asyncpg
from packaging.requirements import Requirement
import redis
import artifact_checks
import bootstrap
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT
EXCLUDED = {
    "node_modules", "cache", "tmp", "__pycache__", "pycache", "vite-cache",
    "npm-cache", ".vite", ".vite-temp",
}


def payload():
    return [p for p in sorted(OWN.rglob("*")) if p.is_file()
            and not EXCLUDED.intersection(p.relative_to(OWN).parts)]


def dependencies():
    project = tomllib.loads((ROOT / "python/pyproject.toml").read_text())
    installed = {d.metadata["Name"].lower().replace("_", "-"): d.version
                 for d in importlib.metadata.distributions()}
    constraints = []
    for group, requirements in (
        ("project", project["project"]["dependencies"]),
        ("dev", project["project"]["optional-dependencies"]["dev"]),
        ("build", project["build-system"]["requires"]),
        ("container", [line.strip() for line in (ROOT / "python/requirements.txt").read_text().splitlines()
                       if line.strip() and not line.lstrip().startswith("#")]),
    ):
        for raw in requirements:
            requirement = Requirement(raw)
            name = requirement.name.lower().replace("_", "-")
            applies = requirement.marker is None or requirement.marker.evaluate()
            version = installed.get(name)
            matches = not applies or (version is not None and version in requirement.specifier)
            constraints.append(dict(group=group, constraint=raw, installed=version,
                                    applies=applies, matches=matches))
    assert all(row["matches"] for row in constraints)
    command = [sys.executable, "-m", "pip", "check"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    review.write("runtime-dependency-check.json", {
        "time": datetime.now(UTC).isoformat(), "python": sys.version,
        "installed": installed, "installed_count": len(installed), "constraints": constraints,
        "pip_check": dict(command=command, exit=result.returncode,
                          stdout=result.stdout, stderr=result.stderr),
        "node": subprocess.check_output([
            "/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node",
            "--version"]).decode().strip(),
        "vulnerability_scan_performed": False,
        "parent_dependency_preflight_not_own_audit": True,
    })
    print(json.dumps(dict(installed=len(installed), constraints=len(constraints), pip_check=0)))


def audit():
    snapshot_label = sys.argv[2] if len(sys.argv) > 2 else "audit"
    review.snapshot(snapshot_label + "-before")
    start = json.loads((OWN / "initial-snapshot.json").read_text())
    current = bootstrap.snapshot()
    product = current["m3"]["head"]
    prepare.verify_blobs(product, current["m3"]["tracked"])
    prepare.verify_blobs(product, current["m3"]["source"])
    prepare.verify_blobs("6147cec5bff26d60a3422b0f43f133b2db782e8f", start["m3"]["tracked"])
    for name, digest in start["m3"]["tracked"].items():
        if name != "python/core/distributed/ops_queries.py":
            assert prepare.sha((ROOT / name).read_bytes()) == digest, name
    records, xml, pairs, production = {}, {}, {}, {}
    zip_count = member_count = event_count = 0
    files = payload()
    secret_scan = artifact_checks.scan((str(p.relative_to(OWN)), p.read_bytes()) for p in files)
    for path in files:
        name, data = str(path.relative_to(OWN)), path.read_bytes()
        item = dict(sha256=prepare.sha(data), bytes=len(data))
        if path.suffix == ".json":
            json.loads(data)
        elif path.suffix == ".jsonl":
            item["jsonl_lines"] = sum(1 for line in data.splitlines() if line.strip())
            for line in data.splitlines():
                if line.strip():
                    json.loads(line)
        elif path.suffix == ".xml":
            cases = list(ET.fromstring(data).iter("testcase"))
            counts = dict(tests=len(cases), failure=sum(c.find("failure") is not None for c in cases),
                          error=sum(c.find("error") is not None for c in cases),
                          skip=sum(c.find("skipped") is not None for c in cases))
            counts["passed"] = counts["tests"] - counts["failure"] - counts["error"] - counts["skip"]
            counts["failures"] = [
                dict(name=c.get("name"), kind=e.tag, message=e.get("message"), text=e.text)
                for c in cases for e in c if e.tag in ("failure", "error")]
            xml[name] = counts
            label = path.stem
            command = json.loads((OWN / (label + "-command.json")).read_text())
            assert command["exit"] == (1 if counts["failure"] or counts["error"] else 0)
        elif path.suffix == ".zip":
            zip_count += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None
                members = {}
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_count += 1
                    content = archive.read(member)
                    members[member.filename] = dict(bytes=len(content), sha256=prepare.sha(content))
                    if member.filename.endswith((".trace", ".network")):
                        events = [json.loads(line) for line in content.splitlines() if line.strip()]
                        members[member.filename]["events"] = len(events)
                        event_count += len(events)
                item["members"] = members
        records[name] = item
    for before in sorted(OWN.glob("*-before.json")):
        if before.name == snapshot_label + "-before.json":
            continue
        after = OWN / before.name.replace("-before.json", "-after.json")
        assert after.is_file(), before.name
        first, second = json.loads(before.read_bytes()), json.loads(after.read_bytes())
        assert first == second, before.name
        assert first["primary"] == start["primary"]
        for key in ("venv", "vite", "vite_temp"):
            assert first["m3"][key] == start["m3"][key]
        label = before.name.removesuffix("-before.json")
        if label.endswith("final") or label.startswith("prod-final-"):
            assert first["m3"]["head"] == product and first["m3"]["source"] == current["m3"]["source"]
        pairs[label] = dict(before_sha=prepare.sha(before.read_bytes()),
                            after_sha=prepare.sha(after.read_bytes()),
                            head=first["m3"]["head"], source_count=first["m3"]["source_count"],
                            source_sha256=first["m3"]["source_sha256"])
    for path in sorted(OWN.glob("production-*.json")):
        if not path.name.endswith(("-desktop.json", "-mobile.json")):
            continue
        body = json.loads(path.read_bytes())
        assert not body["errors"] and body["overflow"] <= 1
        assert all(r["method"] == "GET" for r in body["requests"])
        for url, digest in body["hashes"].items():
            asset = OWN / "frontend/dist" / urlparse(url).path.lstrip("/")
            assert prepare.sha(asset.read_bytes()) == digest
        production[path.name] = dict(page_get_requests=len(body["requests"]),
                                     hashes=body["hashes"], scenario=body["scenario"],
                                     errors=body["errors"], overflow=body["overflow"])
    viewed = []
    scenarios = (
        "current", "history", "approval_malformed_latest", "genuine_malformed_latest_valid",
        "genuine_valid", "referenced_canary_poison", "minimum_zero")
    for scenario in scenarios:
        for viewport in ("desktop", "mobile"):
            name = f"screenshots/detail-prod-final-{scenario}-{viewport}-left.png"
            viewed.append(dict(path=name, sha256=prepare.sha((OWN / name).read_bytes())))
    for name in ("policies-desktop", "policies-mobile", "policy-trace-desktop", "policy-trace-mobile"):
        path = f"screenshots/{name}.png"
        viewed.append(dict(path=path, sha256=prepare.sha((OWN / path).read_bytes())))
    review.write("execution-audit.json", {
        "time": datetime.now(UTC).isoformat(), "role": "fix implementer verification, not acceptance",
        "product": product, "parent": review.git(ROOT, "rev-parse", "HEAD^").decode().strip(),
        "tracked_gitblobs_verified": len(current["m3"]["tracked"]),
        "source_count": current["m3"]["source_count"], "source_sha256": current["m3"]["source_sha256"],
        "source": current["m3"]["source"], "historical_start_blobs_verified": len(start["m3"]["tracked"]),
        "historical_archives_unchanged": True, "xml": xml, "pairs": pairs, "records": records,
        "zip_count": zip_count, "zip_members": member_count, "trace_network_events": event_count,
        "production": production, "actual_view_image_inspections": viewed, "secret_scan": secret_scan,
        "overlap_counts_not_independent_samples": True, "model_calls": 0, "model_cost_usd": "0",
        "http_total": "unknown; browser page GETs only are counted per production record",
        "invalid_red_attempt": {
            "xml": "red-new-get.xml", "invalid_fixture_failures": 1,
            "valid_product_failures": 11, "passed": 12,
            "corrected_red_xml": "red-new-get-corrected.xml",
        },
    })
    review.snapshot(snapshot_label + "-after")
    print(json.dumps(dict(xml_count=len(xml), paired=len(pairs), raw=len(records),
                          zip_count=zip_count, zip_members=member_count,
                          secret_scan=secret_scan, counts={k: {
                              key: value for key, value in v.items() if key != "failures"
                          } for k, v in xml.items()})))


async def pg_verify():
    declared = {}
    for path in [*OWN.glob("*-command.json"), *OWN.glob("*-lifecycle.json")]:
        body = json.loads(path.read_bytes())
        if "db" in body:
            assert re.fullmatch(r"m3_t9_minfix_[0-9a-f]{32}", body["db"])
            assert body["drop_exit"] == 0
            declared[path.name] = body["db"]
    historical = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence"
    old = {}
    for path in [*historical.glob("*-command.json"), *historical.glob("*-lifecycle.json")]:
        body = json.loads(path.read_bytes())
        if "db" in body:
            assert re.fullmatch(r"m3_t9_spec_[0-9a-f]{32}", body["db"])
            old[path.name] = body["db"]
    identity = json.loads((OWN / "shared-pg-identity.json").read_bytes())
    conn = await asyncpg.connect(user="postgres", database="postgres", host="127.0.0.1", port=57432)
    try:
        data_dir = await conn.fetchval("SHOW data_directory")
        assert data_dir == identity["data_dir"]
        assert int((Path(data_dir) / "postmaster.pid").read_text().splitlines()[0]) == identity["pid"] == 16852
        names = sorted(set(declared.values()) | set(old.values()))
        remaining = await conn.fetch("SELECT datname FROM pg_database WHERE datname = ANY($1::text[])", names)
        assert not remaining
        return dict(shared_service_preserved=identity, declared_owned=declared,
                    owned_database_count=len(set(declared.values())),
                    historical_declared=old, historical_database_count=len(set(old.values())),
                    exact_query_names=names, actual_remaining=[])
    finally:
        await conn.close()


def cleanup():
    review.snapshot("cleanup-before")
    pg = asyncio.run(pg_verify())
    original = json.loads((OWN / "owned-redis-identity.json").read_bytes())
    client = redis.Redis(host="127.0.0.1", port=61803, decode_responses=True)
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert info["run_id"] == original["run_id"] and info["process_id"] == original["pid"]
    assert config == original["config"] and config["save"] == "" and config["appendonly"] == "no"
    keys = sorted(client.scan_iter())
    ledger = [json.loads(line) for line in (OWN / "redis-command-ledger.jsonl").read_text().splitlines()]
    assert not any(row["command"] in ("FLUSHALL", "FLUSHDB") for row in ledger)
    deletions = [row for row in ledger if row["command"] in ("DEL", "UNLINK")]
    assert all(re.fullmatch(r"(?:test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*|eduagent:test:failover:[0-9a-f]{32})", key)
               for row in deletions for key in row["exact_keys"])
    recorded = sorted({key for row in ledger for key in row["exact_keys"]})
    review.write("resource-before-shutdown.json", {
        "time": datetime.now(UTC).isoformat(), "postgres": pg, "redis_identity": original,
        "actual_remaining_keys": keys, "recorded_exact_keys": recorded,
        "remaining_unrecorded_keys": sorted(set(keys) - set(recorded)),
        "ledger_complete_for_subprocess": False, "exact_del_commands": deletions,
        "cleanup_method": "identity-checked own nonpersistent SHUTDOWN NOSAVE, no prefix DEL or flush",
    })
    client.shutdown(nosave=True)
    client.close()
    ports = {}
    for port in (61803, 61804, 61805):
        with socket.socket() as sock:
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(ports.values())
    process_lines = subprocess.check_output(["ps", "-axo", "pid=,command="]).decode().splitlines()
    browser = [line for line in process_lines if str(OWN) in line and any(
        word in line.lower() for word in ("chrome", "chromium", "playwright", "vite", "live_server"))]
    assert not browser, browser
    shutil.copytree(OWN / "frontend/dist", OWN / "retained-http-dist")
    removed = []
    for name in ("frontend/node_modules", "frontend/dist", "cache", "tmp", "__pycache__",
                 "pycache", "vite-cache", "npm-cache"):
        path = OWN / name
        if path.exists():
            path.resolve().relative_to(OWN.resolve())
            assert not path.is_symlink()
            shutil.rmtree(path)
            removed.append(name)
    review.write("resource-after-cleanup.json", {
        "time": datetime.now(UTC).isoformat(), "ports_closed": ports,
        "remaining_owned_browser_processes": browser, "removed_own_caches": removed,
        "retained_raw_assets": "retained-http-dist", "shared_pg_runtime_preserved": True,
        "model_calls": 0, "model_cost_usd": "0",
    })
    review.snapshot("cleanup-after")
    print(json.dumps(dict(own_db_count=pg["owned_database_count"],
                          historical_db_count=pg["historical_database_count"],
                          actual_remaining=0, ports_closed=ports, removed=removed)))


if __name__ == "__main__":
    {"dependencies": dependencies, "audit": audit, "cleanup": cleanup}[sys.argv[1]]()
