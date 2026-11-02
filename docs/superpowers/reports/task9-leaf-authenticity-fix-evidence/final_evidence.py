import importlib.metadata as metadata
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from packaging.requirements import Requirement
import bootstrap
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT


def write(name, value):
    review.write(name, value)


def runtime():
    root = Path("/tmp/eduagent-m3-patched-runtime")
    before = bootstrap.metadata(root)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPYCACHEPREFIX": str(OWN / "pycache")}
    commands = {}
    for label, args in (("runtime-v2-pip-check", ["-m", "pip", "check"]),
                        ("runtime-v2-freeze", ["-m", "pip", "freeze", "--all"])):
        started = datetime.now(UTC).isoformat()
        proc = subprocess.run([review.PY, *args], env=env, capture_output=True)
        with (OWN / (label + ".log")).open("xb") as out:
            out.write(proc.stdout + proc.stderr)
        assert proc.returncode == 0
        commands[label] = dict(command=[review.PY, *args], started_at=started,
                               finished_at=datetime.now(UTC).isoformat(), exit=proc.returncode)
    project = tomllib.loads((ROOT / "python/pyproject.toml").read_text())
    groups = {
        "project": project["project"]["dependencies"],
        "dev": project["project"]["optional-dependencies"]["dev"],
        "build": project["build-system"]["requires"],
        "requirements": (ROOT / "python/requirements.txt").read_text().splitlines(),
        "repair_floors": ["anyio>=4.14.2", "certifi>=2026.10.18",
                         "pydantic-settings>=2.14.2", "setuptools>=84.1.0", "starlette>=1.3.1"],
    }
    coverage = []
    for group, rows in groups.items():
        for text in rows:
            if not text.strip() or text.startswith("#"):
                continue
            req = Requirement(text)
            active = req.marker is None or req.marker.evaluate()
            version = metadata.version(req.name) if active else None
            passed = not active or req.specifier.contains(version, prereleases=True)
            coverage.append(dict(group=group, requirement=text, active=active,
                                 installed=version, passed=passed))
    versions = {d.metadata["Name"]: d.version for d in metadata.distributions()}
    assert len(versions) == 58 and len(coverage) == 44
    assert all(row["passed"] for row in coverage)
    after = bootstrap.metadata(root)
    assert before == after
    write("runtime-final.json", dict(python=sys.version, executable=sys.executable,
          versions=versions, installed_count=len(versions), coverage=coverage,
          coverage_count=len(coverage), project_dev_build_requirements_count=39,
          additional_repair_floors=5, before=before, after=after, unchanged=True,
          commands=commands, real_model_calls=0, real_model_cost_usd="0",
          scope="read-only constraints and pip check; no Task10 vulnerability scan"))
    print(json.dumps({"installed": len(versions), "constraints": len(coverage), "unchanged": True}))


def audit():
    suites, snapshots, traces, production = {}, {}, {}, {}
    for p in sorted(OWN.glob("*.xml")):
        tree = ET.parse(p).getroot()
        cases = list(tree.iter("testcase"))
        counts = dict(tests=len(cases),
                      failure=sum(c.find("failure") is not None for c in cases),
                      error=sum(c.find("error") is not None for c in cases),
                      skip=sum(c.find("skipped") is not None for c in cases))
        counts["passed"] = counts["tests"] - sum(counts[k] for k in ("failure", "error", "skip"))
        suites[p.name] = {**counts, "sha256": review.digest(p.read_bytes()),
                         "suite_seconds": sum(float(s.get("time", "0")) for s in tree.iter("testsuite"))}
    for p in OWN.glob("*-before.json"):
        after = OWN / p.name.replace("-before.json", "-after.json")
        assert after.exists(), p.name
        assert json.loads(p.read_bytes()) == json.loads(after.read_bytes())
        snapshots[p.name] = dict(before_sha256=review.digest(p.read_bytes()),
                                after_sha256=review.digest(after.read_bytes()), equal=True)
    for p in sorted(OWN.rglob("trace.zip")):
        members, asset_matches = {}, []
        with zipfile.ZipFile(p) as archive:
            assert archive.testzip() is None
            names = set(archive.namelist())
            for member in archive.infolist():
                if member.is_dir():
                    continue
                data = archive.read(member)
                item = dict(bytes=len(data), sha256=review.digest(data))
                if member.filename.endswith((".trace", ".network")):
                    events = [json.loads(line) for line in data.splitlines() if line.strip()]
                    item["events"] = len(events)
                    if member.filename.endswith(".network") and "production" in str(p):
                        for event in events:
                            snapshot = event.get("snapshot", {})
                            request, response = snapshot.get("request", {}), snapshot.get("response", {})
                            url = request.get("url", "")
                            content = response.get("content", {})
                            body_name = content.get("_file") or content.get("_sha1")
                            if "/assets/" in url and body_name:
                                from urllib.parse import urlparse
                                target = OWN / "frontend/dist" / urlparse(url).path.lstrip("/")
                                resource = body_name if body_name.startswith("resources/") else "resources/" + body_name
                                assert target.is_file() and resource in names
                                actual = archive.read(resource)
                                assert actual == target.read_bytes(), url
                                assert request["method"] == "GET" and response["status"] == 200
                                asset_matches.append(dict(url=url, bytes=len(actual),
                                                         sha256=review.digest(actual), resource=resource))
                members[member.filename] = item
        if "production" in str(p):
            assert asset_matches, str(p)
        traces[str(p.relative_to(OWN))] = dict(sha256=review.digest(p.read_bytes()),
                                             members=members, dist_asset_matches=asset_matches)
    for p in OWN.glob("production-*.json"):
        doc = json.loads(p.read_bytes())
        assert not doc["errors"] and doc["overflow"] <= 1
        assert all(r["method"] == "GET" for r in doc["requests"])
        for asset in doc["assetEvidence"]:
            assert asset["status"] == 200
        production[p.name] = dict(scenario=doc["scenario"], viewport=doc["viewport"],
            browser_gets=len(doc["requests"]), explicit_gets=1 + len(doc["assetEvidence"]),
            errors=doc["errors"], overflow=doc["overflow"], scroll_before=doc["scrollBefore"],
            scroll_after=doc["scrollAfter"], assets=doc["assetEvidence"])
    initial = json.loads((OWN / "initial-snapshot.json").read_bytes())
    prepare.verify_blobs("855d5c6660343c24df0bef5ad4cf77160e83c566", initial["m3"]["tracked"])
    for name, digest in initial["m3"]["tracked"].items():
        if not name.startswith(("python/", "frontend/")):
            assert review.digest((ROOT / name).read_bytes()) == digest, name
    source = json.loads((OWN / "green-snapshot.json").read_bytes())["m3"]["source"]
    write("final-verification.json", dict(role="implementer verification; not independent acceptance",
          suites=suites, snapshots=snapshots, traces=traces, production=production,
          historical_gitblobs_verified=len(initial["m3"]["tracked"]),
          source_count=len(source), source_sha256=json.loads((OWN / "green-snapshot.json").read_bytes())["m3"]["source_sha256"],
          model_calls=0, model_cost_usd="0", all_http="unknown",
          counts_overlap=True, frozen_fixture_usd="synthetic, not billed",
          invalid_json_retained="live-fixture-final-production-leaf_local_bad.json is original partial startup output"))
    print(json.dumps({"suites": suites, "snapshot_pairs": len(snapshots), "traces": len(traces),
                      "members": sum(len(v["members"]) for v in traces.values()),
                      "actual_dist_responses": sum(len(v["dist_asset_matches"]) for v in traces.values())}))


def cleanup():
    import redis
    records = []
    for p in OWN.glob("*.json"):
        try:
            doc = json.loads(p.read_bytes())
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and "db" in doc:
            assert doc["db"].startswith("m3_t9_leaf8551_") and doc["drop_exit"] == 0
            records.append({"file": p.name, "db": doc["db"], "drop_exit": doc["drop_exit"]})
    pg = __import__("asyncio").run(prepare.pg_identity())
    assert not {r["db"] for r in records} & set(pg["before_database_names"])
    client = redis.Redis(host="127.0.0.1", port=62584, decode_responses=True)
    identity = json.loads((OWN / "owned-redis-identity.json").read_bytes())
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert info["process_id"] == identity["pid"] and info["run_id"] == identity["run_id"]
    assert config == identity["config"]
    assert Path(OWN / "redis-service/redis.pid").read_text().strip() == str(identity["pid"])
    keys = sorted(client.scan_iter())
    ledger = [json.loads(line) for line in (OWN / "redis-command-ledger.jsonl").read_text().splitlines()]
    assert not any(row["command"] in {"FLUSHDB", "FLUSHALL"} for row in ledger)
    streams = sorted({json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()})
    residual = [key for key in streams if client.exists(key)]
    assert not residual
    ports = {}
    for port in (62585, 62586):
        with socket.socket() as sock:
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port)) == 0
    assert not any(ports.values())
    result = subprocess.run(["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1",
                             "-p", "62584", "SHUTDOWN", "NOSAVE"], capture_output=True)
    assert result.returncode == 0
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", 62584)) != 0
    removed = []
    for name in ("frontend/node_modules", "cache", "npm-cache", "tmp", "pycache", "__pycache__"):
        target = OWN / name
        if target.exists():
            assert target.resolve().is_relative_to(OWN.resolve())
            shutil.rmtree(target)
            removed.append(name)
    final = bootstrap.snapshot()
    assert final == json.loads((OWN / "green-snapshot.json").read_bytes())
    write("cleanup-final.json", dict(time=datetime.now(UTC).isoformat(), databases=records,
          database_count=len({r["db"] for r in records}), shared_pg=pg,
          redis_identity=identity, redis_verified_config=config, keys_before_shutdown=keys,
          keys_creation_complete=False, subprocess_keys="unmetered; no full key ownership claim",
          reset_streams=streams, residual_reset_streams=residual, shutdown_command="SHUTDOWN NOSAVE",
          shutdown_exit=result.returncode, flush_or_prefix_delete=False, ports_listening=ports,
          removed_own_cache_paths=removed, kept=["frontend/dist", "all raw", "scripts", "trace ZIPs"],
          protected_snapshot_equal=True))
    write("precommit-final-snapshot.json", final)
    print(json.dumps({"databases": len({r["db"] for r in records}), "redis_stopped": True,
                      "primary_and_source_protected": True}))


def freeze():
    head = review.git(ROOT, "rev-parse", "HEAD").decode().strip()
    parent = review.git(ROOT, "rev-parse", "HEAD^").decode().strip()
    assert parent == "855d5c6660343c24df0bef5ad4cf77160e83c566"
    snapshot = json.loads((OWN / "green-snapshot.json").read_bytes())
    prepare.verify_blobs(head, snapshot["m3"]["source"])
    for name, digest in snapshot["m3"]["source"].items():
        assert review.digest((ROOT / name).read_bytes()) == digest
    current = bootstrap.snapshot()
    assert current["primary"] == snapshot["primary"]
    for key in ("venv", "vite", "vite_temp"):
        assert current["m3"][key] == snapshot["m3"][key]
    write("product-freeze.json", dict(time=datetime.now(UTC).isoformat(), product=head, parent=parent,
          source=snapshot["m3"]["source"], source_count=len(snapshot["m3"]["source"]),
          source_sha256=snapshot["m3"]["source_sha256"], all_actual_gitblobs_match=True,
          changed_paths=review.git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", head).decode().splitlines()))
    write("postproduct-snapshot.json", current)
    print(json.dumps({"product": head, "parent": parent, "source_count": current["m3"]["source_count"],
                      "source_sha256": current["m3"]["source_sha256"]}))


if __name__ == "__main__":
    {"runtime": runtime, "audit": audit, "cleanup": cleanup, "freeze": freeze}[sys.argv[1]]()
