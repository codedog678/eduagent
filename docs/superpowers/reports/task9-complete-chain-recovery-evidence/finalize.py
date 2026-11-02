import importlib.metadata as metadata
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

OWN = bootstrap.OWN
ROOT = bootstrap.ROOT
ARCHIVE = ROOT / "docs/superpowers/reports/task9-complete-chain-recovery-evidence"
PG = "/opt/homebrew/opt/postgresql@16/bin/"


def write(name, value):
    bootstrap.write(OWN / name, value)


def requirement_coverage():
    project_path = ROOT / "python/pyproject.toml"
    requirements_path = ROOT / "python/requirements.txt"
    project = tomllib.loads(project_path.read_text())
    groups = {
        "project": project["project"]["dependencies"],
        "dev": project["project"]["optional-dependencies"]["dev"],
        "build": project["build-system"]["requires"],
        "requirements": requirements_path.read_text().splitlines(),
        "repair_floors": ["anyio>=4.14.2", "certifi>=2026.10.18",
                          "pydantic-settings>=2.14.2", "setuptools>=84.1.0",
                          "starlette>=1.3.1"],
    }
    rows = []
    for group, values in groups.items():
        for raw in values:
            req = Requirement(raw)
            active = req.marker is None or req.marker.evaluate()
            version = metadata.version(req.name) if active else None
            passed = not active or req.specifier.contains(version, prereleases=True)
            rows.append(dict(group=group, requirement=raw, name=req.name,
                             extras=sorted(req.extras), active=active,
                             installed=version, passed=passed))
    assert all(r["passed"] for r in rows)
    versions = {d.metadata["Name"]: d.version for d in metadata.distributions()}
    old = ROOT / "docs/superpowers/reports/task9-patched-runtime-baseline/runtime-context.json"
    write("runtime-context.json", {
        "role": "new implementer isolated runtime, not reconstructed old audit",
        "observed_at": datetime.now(UTC).isoformat(), "python": sys.version,
        "executable": sys.executable, "versions": versions, "installed_count": len(versions),
        "inputs": {str(p.relative_to(ROOT)): bootstrap.sha(p.read_bytes())
                   for p in (project_path, requirements_path)},
        "coverage": rows, "coverage_count": len(rows),
        "retained_old_context_sha256": bootstrap.sha(old.read_bytes()),
        "retained_old_context": json.loads(old.read_text()),
        "pip_check": (OWN / "runtime-pip-check.log").read_text().strip(),
        "real_model_requests": 0, "real_model_cost_usd": "0",
        "security_scan_of_this_runtime": "not executed; Task10 scope not authorized",
    })
    permitted = [
        ("/tmp/m3-recovery-parent-dependency-audit", [
            "audit.json", "scan-manifest.json", "scan.stdout.log", "scan.stderr.log"]),
        ("/tmp/m3-recovery-parent-dependency-input", ["requirements.txt", "manifest.json"]),
    ]
    copied = {}
    for directory, names in permitted:
        for name in names:
            source = Path(directory) / name
            if not source.exists():
                copied[str(source)] = {"present": False}
                continue
            target = OWN / "parent-role" / source.parent.name / name
            target.parent.mkdir(parents=True, exist_ok=True)
            assert not target.exists()
            shutil.copy2(source, target)
            copied[str(source)] = {
                "present": True, "archive_path": str(target.relative_to(OWN)),
                "sha256": bootstrap.sha(target.read_bytes()),
            }
    write("parent-dependency-support.json", {
        "role": "parent NEW old-env scan FAIL; future Task10 preflight only",
        "source_times_user_reported": [
            "2026-11-02T02:10:34.271181Z", "2026-11-02T02:10:48.573361Z"],
        "user_reported_counts": dict(exit=1, dependencies=54, affected=5,
                                     raw_vulnerabilities=12, alias_groups=8),
        "missing_old_environment_roots": ["psycopg2-binary", "wheel"],
        "not_this_runtime": True, "not_acceptance": True,
        "excluded": ["tool-install.log", "toolenv", "env", "caches"],
        "files": copied,
    })
    print(json.dumps({"requirements": len(rows), "installed": len(versions),
                      "all_constraints_passed": True}))


def audit():
    suites = {}
    for path in sorted(OWN.glob("*.xml")):
        tree = ET.parse(path).getroot()
        cases = list(tree.iter("testcase"))
        failure = [c for c in cases if c.find("failure") is not None]
        error = [c for c in cases if c.find("error") is not None]
        skip = [c for c in cases if c.find("skipped") is not None]
        counts = dict(tests=len(cases), passed=len(cases) - len(failure) - len(error) - len(skip),
                      failure=len(failure), error=len(error), skip=len(skip))
        suites[path.name] = {
            **counts, "sha256": bootstrap.sha(path.read_bytes()),
            "suite_seconds": sum(float(s.get("time", "0")) for s in tree.iter("testsuite")),
            "nodes": [{"classname": c.get("classname"), "name": c.get("name"),
                       "seconds": c.get("time")} for c in cases],
            "failure_nodes": [c.get("name") for c in failure + error],
        }
    expected = {
        "red-integrity47-v2.xml": (47, 42, 5),
        "red-metadata17-v2.xml": (17, 11, 6),
        "red-complete-chain-v2.xml": (47, 16, 31),
        "red-production-poison.xml": (2, 0, 2),
        "green-complete-chain.xml": (47, 47, 0),
        "green-integrity47.xml": (47, 47, 0),
        "green-metadata17.xml": (17, 17, 0),
        "relations-api-final.xml": (291, 291, 0),
        "full-final.xml": (1840, 1840, 0),
        "ui54.xml": (54, 54, 0),
        "ui-visual4.xml": (4, 4, 0),
        "ui-screenshots4.xml": (4, 4, 0),
    }
    for label in ["current", "history", "approval-malformed", "genuine-malformed",
                  "genuine-valid", "referenced-poison"]:
        expected[f"production-{label}.xml"] = (2, 2, 0)
    assert set(expected) == set(suites)
    for name, counts in expected.items():
        found = suites[name]
        assert tuple(found[k] for k in ("tests", "passed", "failure")) == counts, name
        assert found["error"] == found["skip"] == 0, name
    snapshots = {}
    for before in OWN.glob("*-before.json"):
        after = OWN / before.name.replace("-before.json", "-after.json")
        if not after.exists():
            continue
        a, b = json.loads(before.read_text()), json.loads(after.read_text())
        assert a == b, before.name
        snapshots[before.name] = {
            "before_sha256": bootstrap.sha(before.read_bytes()),
            "after_sha256": bootstrap.sha(after.read_bytes()), "full_equal": True,
        }
    initial = json.loads((OWN / "initial-snapshot.json").read_text())
    historical = {p: h for p, h in initial["m3"]["tracked"].items()
                  if p.startswith("docs/")}
    for p, h in historical.items():
        data = (ROOT / p).read_bytes()
        assert bootstrap.sha(data) == h, p
        assert bootstrap.git(ROOT, "show", bootstrap.BASE + ":" + p) == data, p
    assets = {str(p.relative_to(OWN / "frontend/dist")): bootstrap.sha(p.read_bytes())
              for p in (OWN / "frontend/dist").rglob("*") if p.is_file()}
    requests, bodies, explicit = 0, {}, 0
    for p in OWN.glob("production-*-desktop.json"):
        for viewport in ("desktop", "mobile"):
            path = OWN / p.name.replace("-desktop.json", f"-{viewport}.json")
            body = json.loads(path.read_text())
            requests += len(body["requests"])
            assert all(r["method"] == "GET" for r in body["requests"])
            assert not body["errors"] and body["overflow"] <= 1
            explicit += 1 + len(body["hashes"]) + (body["scenario"] == "history")
            bodies[path.name] = {
                "requests": len(body["requests"]), "explicit_gets": 1 + len(body["hashes"])
                + (body["scenario"] == "history"),
                "hashes": body["hashes"],
            }
    write("implementation-verification.json", {
        "role": "implementer engineering verification, not fresh independent review",
        "suites": suites, "snapshots": snapshots,
        "historical_docs_gitblob_verified": len(historical),
        "dist_assets": assets, "production_http": bodies,
        "production_including_red_page_http": requests,
        "production_including_red_explicit_http": explicit,
        "all_http": "unknown; backend in-process and mocked UI not instrumented",
        "real_model_requests": 0, "real_model_cost_usd": "0",
        "fixture_cost": "synthetic evidence ledger only; not actual billed USD",
        "overlapping_suites": "not additive independent cases",
    })
    print(json.dumps({"suites": {n: {k: d[k] for k in ("tests", "passed", "failure")}
                                for n, d in suites.items()}, "snapshot_pairs": len(snapshots),
                      "old_docs": len(historical), "page_http": requests, "explicit_http": explicit}))


def cleanup():
    records = []
    for path in sorted(OWN.glob("*.json")):
        doc = json.loads(path.read_text())
        if isinstance(doc, dict) and "db" in doc:
            records.append({"file": path.name, "db": doc["db"], "drop_exit": doc["drop_exit"]})
    dbs = sorted({r["db"] for r in records})
    for db in dbs:
        assert db.startswith("m3_t9_fix_") and len(db.removeprefix("m3_t9_fix_")) == 32
        assert all(r["drop_exit"] == 0 for r in records if r["db"] == db)
    result = subprocess.check_output([PG + "psql", "-h", "127.0.0.1", "-p", "57432",
        "-U", "postgres", "-d", "postgres", "-Atc", "SELECT datname FROM pg_database"])
    remaining = result.decode().splitlines()
    assert not set(dbs) & set(remaining)
    import redis
    client = redis.Redis(host="127.0.0.1", port=57379, db=0, decode_responses=True)
    streams = sorted({json.loads(line)["stream"] for line in
                      (OWN / "redis-owned.jsonl").read_text().splitlines()})
    residual = [key for key in streams if client.exists(key)]
    assert not residual, residual
    all_keys = sorted(client.scan_iter())
    redis_before_shutdown = {
        key: {"type": client.type(key), "stream_info": client.xinfo_stream(key)}
        for key in all_keys
    }
    listeners = {}
    for port in (37730, 37731):
        with socket.socket() as sock:
            listeners[str(port)] = sock.connect_ex(("127.0.0.1", port)) == 0
    assert not any(listeners.values())
    identity = json.loads((OWN / "service-identity.json").read_text())
    for key in ("postgres_pid", "redis_pid"):
        os.kill(identity[key], 0)
    redis_info = client.info("server")
    assert redis_info["process_id"] == identity["redis_pid"]
    redis_persistence = client.config_get("save", "appendonly", "dir")
    assert redis_persistence["save"] == "" and redis_persistence["appendonly"] == "no"
    assert redis_persistence["dir"] == identity["parent"]
    write("redis-before-owned-service-shutdown.json", {
        "role": "own nonpersistent Redis; not shared production",
        "observed_at": datetime.now(UTC).isoformat(),
        "pid": identity["redis_pid"], "config": redis_persistence,
        "exact_reset_logged_streams_already_absent": len(streams),
        "residual_keys": redis_before_shutdown,
        "residual_creation_log": "child subprocess creation not instrumented",
        "source_explanation": [
            "python/tests/integration/test_expert_failover.py::process_env",
            "python/tests/integration/test_distributed_failover.py::worker_process",
            "python/core/distributed/runtime.py::build_runtime",
        ],
        "action": "stop this own nonpersistent service; no DEL, prefix deletion or FLUSH",
    })
    shutdown = subprocess.run(["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1",
        "-p", "57379", "SHUTDOWN", "NOSAVE"], capture_output=True, text=True, check=True)
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", 57379)) != 0
    identity["redis_retained"] = False
    identity["redis_shutdown"] = "own service stopped NOSAVE; ephemeral keys not retained"
    identity["postgres_retained"] = True
    ps = subprocess.check_output(["ps", "-axo", "pid=,command="]).decode()
    live_children = [line for line in ps.splitlines()
                     if str(OWN) in line and any(s in line for s in (
                         "/live_server.py", "/@playwright/test/cli.js", "vite --host", "chromium"))]
    assert not live_children, live_children
    service = Path(identity["parent"])
    logs = OWN / "service-logs"
    logs.mkdir()
    for name in ("postgres.log", "redis.log"):
        shutil.copy2(service / name, logs / name)
    removed = []
    for name in ("frontend/node_modules", "frontend/dist", "baseline",
                 "cache", "npm-cache", "pip-cache", "tmp", "__pycache__", "pycache"):
        path = OWN / name
        if path.exists():
            shutil.rmtree(path)
            removed.append(name)
    current = bootstrap.snapshot()
    initial = json.loads((OWN / "initial-snapshot.json").read_text())
    assert current == initial, "unexpected source/index/primary metadata mutation"
    write("cleanup-source-snapshot.json", current)
    write("cleanup-verification.json", {
        "observed_at": datetime.now(UTC).isoformat(), "database_records": records,
        "exact_database_count": len(dbs), "remaining_database_names": remaining,
        "exact_stream_count": len(streams), "exact_streams": streams,
        "residual_exact_streams": residual, "redis_keys_before_shutdown": all_keys,
        "redis_shutdown_exit": shutdown.returncode,
        "redis_key_delete_or_flush_performed": False,
        "redis_listener_after_shutdown": False,
        "ports_listening": listeners, "own_live_children": live_children,
        "removed_own_cache_paths": removed,
        "primary_and_m3_before_commit_full_snapshot_equal": True,
        "kept": identity, "service_logs_are_point_in_time": True,
    })
    print(json.dumps({"databases": len(dbs), "streams": len(streams),
                      "reset_logged_residual": 0, "redis_stopped": True,
                      "source_snapshot_equal": True, "retained": identity}))


def freeze():
    head = bootstrap.git(ROOT, "rev-parse", "HEAD").decode().strip()
    parent = bootstrap.git(ROOT, "rev-parse", "HEAD^").decode().strip()
    assert parent == bootstrap.BASE
    initial = json.loads((OWN / "initial-snapshot.json").read_text())
    source = initial["m3"]["source"]
    for p, h in source.items():
        data = (ROOT / p).read_bytes()
        assert bootstrap.sha(data) == h
        assert bootstrap.git(ROOT, "show", head + ":" + p) == data
    changed = bootstrap.git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", head).decode().splitlines()
    assert set(changed) == {"python/core/distributed/ops_queries.py",
                            "python/tests/distributed/test_ops_complete_chain.py"}
    current = bootstrap.snapshot()
    assert current["primary"] == initial["primary"]
    write("freeze-verification.json", {
        "freeze": head, "parent": parent, "branch": bootstrap.git(ROOT, "branch", "--show-current").decode().strip(),
        "source_count": len(source), "source_sha256": initial["m3"]["source_sha256"],
        "source": source, "all_gitblob_worktree_match": True, "changed": changed,
        "primary_unchanged": True, "no_push": True,
    })
    print(json.dumps({"freeze": head, "parent": parent, "source_count": len(source),
                      "source_sha256": initial["m3"]["source_sha256"]}))


def prepare():
    fixtures = {}
    for path in sorted(OWN.glob("live-fixture-*.json")):
        doc = json.loads(path.read_text())
        detail = doc["detail"]
        fixtures[path.name] = {
            "role": doc["role"], "scenario": doc["scenario"],
            "deployment_id": doc["id"], "candidate_policy_hash": detail["candidate_policy_hash"],
            "thresholds": detail["thresholds"], "thresholds_hash": detail["thresholds_hash"],
            "receipt_ids_and_evidence": [
                {k: r[k] for k in ("receipt_id", "gate_type", "status", "evidence_hash",
                                  "sample_count", "cost", "issued_at", "health_source")}
                for r in detail["gate_receipts"]],
        }
    ps = subprocess.check_output(["ps", "-axo", "pid=,command="]).decode()
    children = [line for line in ps.splitlines()
                if "/tmp/eduagent-m3-patched-runtime/bin/python -m core.distributed.cli" in line]
    assert not children
    write("execution-ledger.json", {
        "role": "synthetic implementer engineering, not release qualification",
        "observed_at": datetime.now(UTC).isoformat(),
        "core_cli_worker_matches": children,
        "fixture_metadata_source": "python/tests/distributed/test_policy_health.py::candidate_head",
        "fixture_protocol_hash": "b" * 64, "fixture_runtime_hash": "f" * 64,
        "fixture_source_revision": "test-source",
        "artifact_literal_data_role": "holdout_validated",
        "artifact_literal_role_caveat": "fixture literal only, not actual independent holdout evidence",
        "evidence_binding_role": "test_fixture", "release_eligible": False,
        "leaf_model_identity": "server-policy-health-v1",
        "approval_model_identity": "authenticated-promotion-command",
        "model_identity_caveat": "server receipt labels, not live model API calls",
        "real_model_requests": 0, "real_model_cost_usd": "0",
        "prior_lost_requests_times_cost": "unknown, not reconstructed",
        "fixtures": fixtures,
        "full_source_freeze": json.loads((OWN / "freeze-verification.json").read_text())["freeze"],
    })
    payload = {str(p.relative_to(OWN)): bootstrap.sha(p.read_bytes())
               for p in sorted(OWN.rglob("*")) if p.is_file()
               and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    validity = {"json": 0, "jsonl": 0, "xml": 0, "zip": 0}
    for name in payload:
        path = OWN / name
        if path.suffix == ".json":
            json.loads(path.read_text())
            validity["json"] += 1
        elif path.suffix == ".jsonl":
            for line in path.read_text().splitlines():
                json.loads(line)
            validity["jsonl"] += 1
        elif path.suffix == ".xml":
            ET.parse(path)
            validity["xml"] += 1
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                assert z.testzip() is None
            validity["zip"] += 1
    write("retained-raw-manifest.json", {
        "files": payload, "payload_count": len(payload),
        "payload_sha256": bootstrap.sha(json.dumps(sorted(payload.items()), ensure_ascii=True,
                                     separators=(",", ":")).encode()),
        "excluded": ["retained-raw-manifest.json itself", "future implementation-report.md",
                     "future archive manifest.json", "post-archive commit observations", "caches"],
        "validity": validity,
    })
    manifest = OWN / "retained-raw-manifest.json"
    print(json.dumps({"raw_count": len(payload), "raw_manifest_sha256": bootstrap.sha(manifest.read_bytes()),
                      "raw_payload_sha256": json.loads(manifest.read_text())["payload_sha256"],
                      "validity": validity}))


def archive():
    report = Path("/tmp/m3-task9-complete-chain-fix-result.md")
    assert report.exists()
    assert not ARCHIVE.exists()
    shutil.copy2(report, OWN / "implementation-report.md")
    payload = {str(p.relative_to(OWN)): bootstrap.sha(p.read_bytes())
               for p in sorted(OWN.rglob("*")) if p.is_file()
               and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    validity = {"json": 0, "jsonl": 0, "xml": 0, "zip": 0, "zip_jsonlines": 0}
    for name in payload:
        path = OWN / name
        if path.suffix == ".json":
            json.loads(path.read_text())
            validity["json"] += 1
        elif path.suffix == ".jsonl":
            for line in path.read_text().splitlines():
                json.loads(line)
            validity["jsonl"] += 1
        elif path.suffix == ".xml":
            ET.parse(path)
            validity["xml"] += 1
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                assert z.testzip() is None
                for item in z.namelist():
                    if item.endswith((".trace", ".network")):
                        for line in z.read(item).decode().splitlines():
                            json.loads(line)
                            validity["zip_jsonlines"] += 1
            validity["zip"] += 1
    ARCHIVE.mkdir()
    for name in payload:
        dest = ARCHIVE / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OWN / name, dest)
        assert bootstrap.sha(dest.read_bytes()) == payload[name]
    manifest = {
        "role": "new Task9 repair implementer raw archive; not acceptance",
        "files": payload, "payload_count": len(payload),
        "payload_sha256": bootstrap.sha(json.dumps(sorted(payload.items()), ensure_ascii=True,
                                     separators=(",", ":")).encode()),
        "excluded": ["manifest.json itself", "caches", "dependencies", "services data",
                     "post-archive git index/head observations"],
        "validity": validity,
        "report_sha256": bootstrap.sha(report.read_bytes()),
        "product_freeze": json.loads((OWN / "freeze-verification.json").read_text())["freeze"],
    }
    bootstrap.write(ARCHIVE / "manifest.json", manifest)
    assert report.read_bytes() == (ARCHIVE / "implementation-report.md").read_bytes()
    print(json.dumps({"archive": str(ARCHIVE), "payload_count": len(payload),
                      "payload_sha256": manifest["payload_sha256"],
                      "manifest_sha256": bootstrap.sha((ARCHIVE / "manifest.json").read_bytes()),
                      "report_sha256": manifest["report_sha256"], "validity": validity}))


if __name__ == "__main__":
    {"runtime": requirement_coverage, "audit": audit, "cleanup": cleanup,
     "freeze": freeze, "prepare": prepare, "archive": archive}[sys.argv[1]]()
