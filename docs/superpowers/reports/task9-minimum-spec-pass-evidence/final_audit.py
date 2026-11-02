"""Owned WHOLE SPEC evidence audit; never edits either source worktree."""

import ast
import asyncio
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.metadata as metadata
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
from xml.etree import ElementTree as ET

import asyncpg
from dotenv import dotenv_values
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import redis

import bootstrap
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(name, value):
    review.write(name, value)


def xml_record(path):
    root = ET.fromstring(path.read_bytes())
    cases = list(root.iter("testcase"))
    failures = [
        {"classname": case.get("classname"), "name": case.get("name"),
         "kind": item.tag, "message": item.get("message"), "text": item.text}
        for case in cases for item in case if item.tag in ("failure", "error")
    ]
    return {
        "sha256": sha(path.read_bytes()), "tests": len(cases),
        "failures": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skips": sum(c.find("skipped") is not None for c in cases),
        "suite_seconds": sum(float(s.get("time", 0)) for s in root.iter("testsuite")),
        "modules": dict(Counter(c.get("classname") for c in cases)),
        "nodes": [{"classname": c.get("classname"), "name": c.get("name"),
                   "seconds": c.get("time")} for c in cases],
        "failure_details": failures,
    }


def retained_paths():
    excluded = {"node_modules", "cache", "npm-cache", "vite-cache", "tmp",
                "pycache", "__pycache__", ".vite", ".vite-temp"}
    return [p for p in sorted(OWN.rglob("*"))
            if p.is_file() and not any(part in excluded for part in p.relative_to(OWN).parts)]


def secret_scan(entries):
    values = set()
    configs = []
    for root in (ROOT, ROOT.with_name("eduagent")):
        for name in (".env", "python/.env", ".env.local", "python/.env.local"):
            path = root / name
            if path.is_file():
                configs.append(str(path))
                for key, value in dotenv_values(path).items():
                    if value and any(word in key for word in
                                     ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")):
                        values.add(value.encode())
    for key, value in os.environ.items():
        if len(value) >= 8 and any(word in key for word in
                                  ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")):
            values.add(value.encode())
    patterns = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b", rb"\bgithub_pat_[A-Za-z0-9_]{50,}\b",
        rb"\bAKIA[0-9A-Z]{16}\b", rb"\bsk-[A-Za-z0-9_-]{32,}\b",
    ]
    matches = []
    literal_matches = []
    files = zips = members = 0
    hashes = {}

    def check(name, data):
        if any(value in data for value in values):
            matches.append({"path": name, "kind": "actual_secret_value"})
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, data):
                line = data[:match.start()].count(b"\n") + 1
                old_scanner = ROOT / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py"
                if index == 0 and name == str(old_scanner) and line in (88, 89):
                    assert data == review.git(ROOT, "show", review.HEAD + ":" + str(old_scanner.relative_to(ROOT)))
                    source_line = data.splitlines()[line - 1]
                    assert source_line.strip() == b'assert b"' + match.group() + b'" not in data, name'
                    literal_matches.append({"path": name, "line": line, "pattern_index": index,
                                            "kind": "exact frozen scanner assertion literal, no key body",
                                            "file_sha256": sha(data)})
                else:
                    matches.append({"path": name, "line": line, "pattern_index": index})

    for name, data in entries:
        files += 1
        hashes[name] = sha(data)
        check(name, data)
        if name.endswith(".zip"):
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None, name
                for member in archive.infolist():
                    if not member.is_dir():
                        members += 1
                        check(name + ":" + member.filename, archive.read(member))
    assert not matches, matches
    return {"files": files, "zip_files": zips, "zip_members": members,
            "local_config_files": len(configs), "local_secret_values_distinct": len(values),
            "secret_matches": 0, "pattern_matches": 0,
            "raw_pattern_literal_hits": len(literal_matches),
            "classified_frozen_scanner_assertion_literals": literal_matches,
            "paths_sha256": sha(json.dumps(sorted(hashes.items()), separators=(",", ":")).encode())}


def dependencies():
    runtime = Path(review.PY).parent.parent
    before = bootstrap.metadata(runtime)
    distributions = {canonicalize_name(d.metadata["Name"]): d.version for d in metadata.distributions()}
    project = tomllib.loads((ROOT / "python/pyproject.toml").read_text())
    declared = [
        ("requirements.txt", line.strip())
        for line in (ROOT / "python/requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    declared += [("project.dependencies", line) for line in project["project"]["dependencies"]]
    declared += [("project.optional-dependencies.dev", line)
                 for line in project["project"]["optional-dependencies"]["dev"]]
    declared += [("build-system.requires", line) for line in project["build-system"]["requires"]]
    checks = []
    for origin, text in declared:
        req = Requirement(text)
        version = distributions[canonicalize_name(req.name)]
        assert req.specifier.contains(version, prereleases=True), (text, version)
        checks.append({"origin": origin, "requirement": text, "version": version, "matches": True})
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(OWN / "pycache"))
    started = datetime.now(UTC).isoformat()
    proc = subprocess.run([review.PY, "-m", "pip", "check"], env=env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert bootstrap.metadata(runtime) == before
    put("dependencies-independent.json", {
        "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
        "command": [review.PY, "-m", "pip", "check"], "exit": proc.returncode,
        "stdout": proc.stdout, "stderr": proc.stderr, "python": sys.version,
        "distributions": distributions, "distribution_count": len(distributions),
        "checks": checks, "declared_constraint_count": len(checks),
        "runtime_readonly_before_after": before,
        "no_install": True, "no_vulnerability_audit_claim": True,
        "docker_binary_available": shutil.which("docker") is not None,
        "docker_and_real_ci_executed": False,
    })


def execution():
    review.snapshot("evidence-audit-before")
    results = {p.name: xml_record(p) for p in sorted(OWN.glob("*.xml"))}
    assert {name: row["tests"] for name, row in results.items()
            if not name.startswith("prod-")} == {
        "full-final.xml": 1864, "api-final.xml": 315, "integrity-complete.xml": 111,
        "minimum.xml": 28, "ui54.xml": 54, "ui-visual4.xml": 4,
    }
    assert len([name for name in results if name.startswith("prod-")]) == 7
    assert all(row["failures"] == row["errors"] == row["skips"] == 0 for row in results.values())
    commands = {p.name: json.loads(p.read_bytes()) for p in sorted(OWN.glob("*-command.json"))}
    pairs = {}
    for name in commands:
        label = name.removesuffix("-command.json")
        before, after = OWN / (label + "-before.json"), OWN / (label + "-after.json")
        assert before.read_bytes() == after.read_bytes()
        assert commands[name]["exit"] == 0
        pairs[label] = {"before": before.name, "after": after.name, "sha256": sha(before.read_bytes())}

    archives = {}
    for folder, manifest, count in (
        ("task9-minimum-fix-evidence", "payload-manifest.json", 570),
        ("task9-minimum-spec-failure-evidence", "manifest.json", 466),
    ):
        directory = ROOT / "docs/superpowers/reports" / folder
        path = directory / manifest
        data = json.loads(path.read_bytes())
        files = data["files"]
        assert len(files) == count
        for name, digest in files.items():
            assert sha((directory / name).read_bytes()) == digest, name
        prepare.verify_blobs(review.HEAD, {
            str((directory / name).relative_to(ROOT)): digest for name, digest in files.items()
        })
        combined = sha(json.dumps(sorted(files.items()), ensure_ascii=True, separators=(",", ":")).encode())
        expected = data.get("payload_sha256", data.get("combined_sha256"))
        if expected:
            assert combined == expected, (folder, combined, expected)
        report_name = "report.md" if count == 570 else "review-result.md"
        archives[folder] = {
            "files": count, "manifest_sha256": sha(path.read_bytes()), "payload_sha256": combined,
            "report_sha256": sha((directory / report_name).read_bytes()), "all_actual_gitblob_equal": True,
        }
    new_report = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-minimum-fix.md"
    assert new_report.read_bytes() == (OWN / "implementation-result.md").read_bytes()
    assert sha(new_report.read_bytes()) == "3610b6c2f13d80144ea77774f25636dc3b4b93969de3c0a599e408d0b2012446"
    assert archives["task9-minimum-fix-evidence"]["payload_sha256"] == \
        "a0f174383667b0ccdc56c174e28d5e0f8acf0c4b07006abcc872c46449ae6d9b"

    retained = OWN / "retained-http-dist"
    assert not retained.exists()
    shutil.copytree(OWN / "frontend/dist", retained)
    dist = {str(p.relative_to(retained)): sha(p.read_bytes()) for p in sorted(retained.rglob("*")) if p.is_file()}
    traces = {}
    for path in sorted(OWN.rglob("trace.zip")):
        members = {}
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            for item in archive.infolist():
                if item.is_dir():
                    continue
                content = archive.read(item)
                entry = {"sha256": sha(content), "bytes": len(content)}
                if item.filename.endswith((".trace", ".network")):
                    entry["parsed_events"] = len([json.loads(line) for line in content.splitlines() if line.strip()])
                members[item.filename] = entry
        traces[str(path.relative_to(OWN))] = {"sha256": sha(path.read_bytes()), "members": members}
    assert len(traces) == 72
    production = {}
    for path in sorted(OWN.glob("production-prod-final-*.json")):
        raw = json.loads(path.read_bytes())
        label, viewport = path.stem.removeprefix("production-").rsplit("-", 1)
        trace_paths = [p for p in (OWN / (label + "-output")).rglob("trace.zip") if viewport in str(p.parent)]
        assert len(trace_paths) == 1
        assert all(r["method"] == "GET" for r in raw["requests"])
        assert not raw["errors"] and raw["overflow"] <= 1
        assets = {}
        get_count = missing_navigation_body = 0
        with zipfile.ZipFile(trace_paths[0]) as trace:
            for entry in trace.namelist():
                if not entry.endswith(".network"):
                    continue
                for line in trace.read(entry).splitlines():
                    snapshot = json.loads(line).get("snapshot", {})
                    request = snapshot.get("request")
                    if not request:
                        continue
                    assert request["method"] == "GET"
                    get_count += 1
                    url = request["url"]
                    if url not in raw["hashes"]:
                        continue
                    response = snapshot["response"]
                    assert response["status"] == 200
                    if "_file" not in response["content"]:
                        missing_navigation_body += 1
                        continue
                    content = trace.read(response["content"]["_file"])
                    relative = Path(urlparse(url).path.lstrip("/"))
                    assert ".." not in relative.parts
                    assert content == (retained / relative).read_bytes()
                    assert sha(content) == raw["hashes"][url]
                    assets[url] = {"bytes": len(content), "sha256": sha(content)}
        assert {url: row["sha256"] for url, row in assets.items()} == raw["hashes"]
        assert len(assets) == len(raw["assetEvidence"]) == 3
        production[path.name] = {
            "scenario": raw["scenario"], "viewport": raw["viewport"],
            "page_gets": len(raw["requests"]), "trace_gets": get_count,
            "exact_asset_bytes": assets, "navigation_assets_without_body": missing_navigation_body,
            "overflow": raw["overflow"], "errors": raw["errors"],
            "scroll_before_explicit_wheel": raw["scrollBefore"], "scroll_after": raw["scrollAfter"],
            "scroll_before_is_after_source_scrollIntoView": True,
            "health_sources": [r for r in raw["body"]["gate_receipts"] if r["health_source"]],
        }
    assert len(production) == 14
    visuals = []
    labels = [name.removesuffix("-command.json") for name in commands if name.startswith("prod-final-")]
    for label in sorted(labels):
        for viewport in ("desktop", "mobile"):
            path = OWN / "screenshots" / f"detail-{label}-{viewport}-left.png"
            visuals.append({"path": str(path.relative_to(OWN)), "sha256": sha(path.read_bytes()),
                            "actual_view_image_inspected": True})
    for stem in ("policies", "policy-trace"):
        for viewport in ("desktop", "mobile"):
            path = OWN / "screenshots" / f"{stem}-{viewport}.png"
            visuals.append({"path": str(path.relative_to(OWN)), "sha256": sha(path.read_bytes()),
                            "actual_view_image_inspected": True})

    changed = review.git(ROOT, "diff", "--name-only", "8869166878a193a1c453376471cbe52c8fa84b3f",
                         review.HEAD, "--", "python", "frontend").decode().splitlines()
    symbols = {}
    for name in changed:
        path = ROOT / name
        if path.suffix == ".py":
            tree = ast.parse(path.read_text())
            symbols[name] = [{"name": n.name, "line": n.lineno, "end_line": n.end_lineno}
                             for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    put("independent-execution-audit.json", {
        "time": datetime.now(UTC).isoformat(), "role": "fresh independent WHOLE SPEC execution",
        "head": review.HEAD, "xml": results, "commands": commands, "pairs": pairs,
        "archives": archives, "whole_changed_source_paths": changed, "python_symbols": symbols,
        "dist": dist, "traces": traces, "production": production, "actual_visual_inspections": visuals,
        "page_gets": sum(r["page_gets"] for r in production.values()),
        "production_trace_gets": sum(r["trace_gets"] for r in production.values()),
        "asset_byte_checks": sum(len(r["exact_asset_bytes"]) for r in production.values()),
        "all_http_total": "unknown", "actual_model_requests": 0, "actual_model_cost_usd": "0",
        "repeated_matrix_results_not_independent_samples": True,
        "docker_real_ci_agent50_task10_wholecode_executed": False,
    })
    review.snapshot("evidence-audit-after")


async def databases(exact_names):
    conn = await asyncpg.connect(host="127.0.0.1", port=57432, user="postgres", database="postgres")
    try:
        rows = await conn.fetch("SELECT datname FROM pg_database WHERE datname = ANY($1::text[])", exact_names)
        assert not rows, rows
        identity = await prepare.pg_identity()
        before = json.loads((OWN / "shared-pg-identity.json").read_bytes())
        for key in ("pid", "port", "data_dir", "version"):
            assert before[key] == identity[key]
        return {"exact_names": exact_names, "remaining": [], "shared_pg_preserved_identity": identity}
    finally:
        await conn.close()


def cleanup():
    review.snapshot("cleanup-before")
    commands = [json.loads(p.read_bytes()) for p in OWN.glob("*-command.json")]
    lifecycle = [json.loads(p.read_bytes()) for p in OWN.glob("*-lifecycle.json")]
    own_names = sorted({r["db"] for r in commands + lifecycle if "db" in r})
    assert len(own_names) == 11
    assert all(r.get("drop_exit", 0) == 0 for r in commands + lifecycle)
    previous_names = set()
    for folder in ("task9-minimum-fix-evidence", "task9-minimum-spec-failure-evidence"):
        directory = ROOT / "docs/superpowers/reports" / folder
        for path in list(directory.glob("*-command.json")) + list(directory.glob("*-lifecycle.json")):
            row = json.loads(path.read_bytes())
            if "db" in row:
                previous_names.add(row["db"])
    db = asyncio.run(databases(own_names + sorted(previous_names)))
    identity = json.loads((OWN / "owned-redis-identity.json").read_bytes())
    client = redis.Redis(host="127.0.0.1", port=identity["port"], decode_responses=True)
    server, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert server["process_id"] == identity["pid"]
    assert server["run_id"] == identity["run_id"] and config == identity["config"]
    assert int((OWN / "redis-service/redis.pid").read_text()) == identity["pid"]
    ledger = [json.loads(line) for line in (OWN / "redis-command-ledger.jsonl").read_bytes().splitlines()]
    assert not any(r["command"] in ("FLUSHALL", "FLUSHDB") for r in ledger)
    deleted = [r for r in ledger if r["command"] in ("DEL", "UNLINK")]
    for row in deleted:
        assert all(re.fullmatch(
            r"(?:test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*|eduagent:test:failover:[0-9a-f]{32})", key)
                   for key in row["exact_keys"])
    remaining = sorted(client.scan_iter())
    started = datetime.now(UTC).isoformat()
    client.shutdown(nosave=True)
    client.close()
    ports = {}
    for port in (50864, 50865, 50866):
        with socket.socket() as sock:
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port))
        assert ports[str(port)] != 0
    removed = []
    for name in ("frontend/node_modules", "frontend/dist", "cache", "tmp", "npm-cache",
                 "vite-cache", "pycache", "__pycache__"):
        path = OWN / name
        if path.exists():
            assert path.resolve().is_relative_to(OWN.resolve())
            shutil.rmtree(path)
            removed.append(name)
    snapshot = bootstrap.snapshot()
    assert snapshot == json.loads((OWN / "initial-snapshot.json").read_bytes())
    prepare.verify_blobs(review.HEAD, snapshot["m3"]["tracked"])
    primary = snapshot["primary"]
    input_data = "".join(f"{primary['head']}:{name}\n" for name in primary["tracked"]).encode()
    data = subprocess.check_output(["git", "cat-file", "--batch"], input=input_data, cwd=ROOT.with_name("eduagent"))
    pos = 0
    for name, digest in primary["tracked"].items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert header[1] == b"blob"
        size = int(header[2])
        pos = end + 1
        assert sha(data[pos:pos + size]) == digest, name
        pos += size + 1
    assert pos == len(data)
    put("final-source-gitblob.json", {
        "time": datetime.now(UTC).isoformat(), "snapshot": snapshot,
        "m3_verified_blobs": len(snapshot["m3"]["tracked"]),
        "primary_verified_blobs": len(primary["tracked"]), "full_start_end_equal": True,
    })
    put("cleanup-independent.json", {
        "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
        "own_uuid_database_count": len(own_names), "own_databases": own_names,
        "historical_exact_database_count": len(previous_names), "database_check": db,
        "owned_redis_identity_before_shutdown": {"server": server, "config": config},
        "ledger_rows": len(ledger), "exact_del_unlink_commands": len(deleted),
        "remaining_keys_before_shutdown": remaining,
        "remaining_worker_keys_unmetered": len(remaining),
        "ledger_not_claimed_complete_for_subprocess_workers": True,
        "shutdown_command": "SHUTDOWN NOSAVE", "identity_checked": True,
        "no_flush_or_prefix_delete": True, "ports_closed": ports,
        "removed_own_cache_only": removed, "patched_runtime_and_shared_pg_preserved": True,
    })
    review.snapshot("cleanup-after")


def manifest():
    report = OWN / "review-result.md"
    assert report.read_bytes() == Path("/tmp/m3-task9-minimum-spec-result.md").read_bytes()
    entries = {str(p.relative_to(OWN)): sha(p.read_bytes()) for p in retained_paths()
               if p.name != "retained-manifest.json"}
    put("retained-manifest.json", {
        "time": datetime.now(UTC).isoformat(), "role": "fresh WHOLE SPEC; not acceptance or CODE",
        "head": review.HEAD, "files": entries, "file_count": len(entries),
        "payload_sha256": sha(json.dumps(sorted(entries.items()), ensure_ascii=True, separators=(",", ":")).encode()),
        "report_sha256": sha(report.read_bytes()), "same_byte_report": report.name,
        "external_report": "/tmp/m3-task9-minimum-spec-result.md", "self_excluded_no_hash_cycle": True,
    })


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "dependencies":
        dependencies()
    elif action == "execution":
        execution()
    elif action == "cleanup":
        cleanup()
    elif action == "scan":
        paths = retained_paths()
        source = json.loads((OWN / "independent-execution-audit.json").read_bytes())["whole_changed_source_paths"]
        historical = [p for p in (ROOT / "docs/superpowers/reports").rglob("*")
                      if p.is_file() and "task9" in str(p.relative_to(ROOT))]
        entries = [(str(p), p.read_bytes()) for p in paths + historical + [ROOT / name for name in source]]
        result = secret_scan(entries)
        result.update(time=datetime.now(UTC).isoformat(), actual_value_scan=True,
                      hook_complete_not_claimed=True, scanned_owned_files=len(paths),
                      scanned_historical_files=len(historical), scanned_changed_source_files=len(source))
        put(sys.argv[2] if len(sys.argv) > 2 else "independent-secret-scan.json", result)
    elif action == "manifest":
        manifest()
    elif action == "publish-report":
        source = Path("/tmp/m3-task9-minimum-spec-result.md")
        destination = OWN / "review-result.md"
        assert not destination.exists()
        shutil.copyfile(source, destination)
        assert source.read_bytes() == destination.read_bytes()
        original = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence/test_minimum_evidence.py"
        corrected = OWN / "test_minimum_evidence.py"
        import difflib
        difference = "".join(difflib.unified_diff(
            original.read_text().splitlines(keepends=True),
            corrected.read_text().splitlines(keepends=True),
            fromfile=str(original.relative_to(ROOT)), tofile="owned/test_minimum_evidence.py"))
        put("minimum-probe-independent-provenance.json", {
            "original_sha256": sha(original.read_bytes()),
            "owned_sha256": sha(corrected.read_bytes()), "diff": difference,
            "original_gitblob_equal": original.read_bytes() == review.git(
                ROOT, "show", review.HEAD + ":" + str(original.relative_to(ROOT))),
            "gate_specific_correction_not_product_edit": True,
        })
    elif action == "verify":
        path = OWN / "retained-manifest.json"
        value = json.loads(path.read_bytes())
        for name, digest in value["files"].items():
            assert sha((OWN / name).read_bytes()) == digest, name
        assert len(value["files"]) == value["file_count"]
        assert sha(json.dumps(sorted(value["files"].items()), ensure_ascii=True,
                              separators=(",", ":")).encode()) == value["payload_sha256"]
        assert (OWN / "review-result.md").read_bytes() == Path("/tmp/m3-task9-minimum-spec-result.md").read_bytes()
        assert sha((OWN / "review-result.md").read_bytes()) == value["report_sha256"]
        snapshot = bootstrap.snapshot()
        assert snapshot == json.loads((OWN / "initial-snapshot.json").read_bytes())
        prepare.verify_blobs(review.HEAD, snapshot["m3"]["tracked"])
        scan = json.loads((OWN / "independent-secret-final.json").read_bytes())
        assert scan["local_secret_values_distinct"] == 2
        assert scan["secret_matches"] == scan["pattern_matches"] == 0
        assert scan["raw_pattern_literal_hits"] == 2
        print(json.dumps({"verdict": "WHOLESPECPASS", "file_count": value["file_count"],
                          "payload_sha256": value["payload_sha256"],
                          "manifest_sha256": sha(path.read_bytes()),
                          "report_sha256": value["report_sha256"],
                          "source_count": snapshot["m3"]["source_count"],
                          "m3_actual_verified_blobs": len(snapshot["m3"]["tracked"]),
                          "primary_protected_tracked": len(snapshot["primary"]["tracked"]),
                          "two_worktrees_start_end_equal": True,
                          "all_retained_bytes_verified": True,
                          "secret_scan": {key: scan[key] for key in (
                              "files", "zip_files", "zip_members", "local_secret_values_distinct",
                              "secret_matches", "pattern_matches", "raw_pattern_literal_hits")},
                          "whole_code_or_acceptance_started": False}, indent=2))
    else:
        raise ValueError(action)
