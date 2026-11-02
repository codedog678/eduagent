from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from review import OWN, ROOT, HEAD, PG, PY, digest, git, snapshot, write


def xml_data(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    details = []
    for case in cases:
        kind = next((k for k in ("failure", "error", "skipped") if case.find(k) is not None), "pass")
        item = dict(case.attrib, result=kind)
        if kind != "pass":
            node = case.find(kind)
            item.update(attributes=node.attrib, content=node.text)
        details.append(item)
    counts = Counter(item["result"] for item in details)
    return {"sha256": digest(path.read_bytes()), "tests": len(cases),
            "passed": counts["pass"], "failures": counts["failure"],
            "errors": counts["error"], "skips": counts["skipped"],
            "suite_seconds": sum(float(s.get("time", "0")) for s in root.iter("testsuite")),
            "suites": [s.attrib for s in root.iter("testsuite")],
            "modules": dict(Counter(c.get("classname") for c in cases)), "cases": details}


def archive_audit():
    result = {}
    for name, manifest_name, field in (
        ("task9-source-integrity-fix-evidence", "manifest.json", "files_sha256"),
        ("task9-health-binding-spec-failure-evidence", "retained-manifest.json", "files"),
    ):
        directory = ROOT / "docs/superpowers/reports" / name
        manifest_path = directory / manifest_name
        manifest = json.loads(manifest_path.read_text())
        files = manifest[field]
        assert digest(json.dumps(sorted(files.items()), ensure_ascii=True,
                                 separators=(",", ":")).encode()) == manifest["payload_sha256"]
        records = {}
        objects = {}
        for relative in [manifest_name, *files]:
            path = directory / relative
            raw = path.read_bytes()
            assert raw == git(ROOT, "show", HEAD + ":" + str(path.relative_to(ROOT)))
            if relative in files:
                assert digest(raw) == files[relative]
            record = {"bytes": len(raw), "sha256": digest(raw), "gitblob_exact": True}
            if path.suffix == ".json":
                value = json.loads(raw)
                objects[relative] = value
                record.update(type=type(value).__name__,
                              keys=sorted(value) if isinstance(value, dict) else None)
            elif path.suffix == ".jsonl":
                lines = [json.loads(line) for line in raw.splitlines()]
                record.update(lines=len(lines), parsed_all=True)
            elif path.suffix == ".xml":
                record.update(xml=xml_data(path))
            elif path.suffix == ".zip":
                with ZipFile(path) as archive:
                    assert archive.testzip() is None
                    members = {}
                    for member in archive.namelist():
                        data = archive.read(member)
                        item = {"bytes": len(data), "sha256": digest(data)}
                        if member.endswith((".trace", ".network")):
                            entries = [json.loads(line) for line in data.splitlines()]
                            item.update(events=len(entries),
                                        types=dict(Counter(x.get("type") for x in entries)))
                        members[member] = item
                    record.update(zip_members=members, crc_ok=True)
            elif path.suffix not in {".png"}:
                text = raw.decode()
                record.update(lines=len(text.splitlines()),
                              diagnostic_lines=[line for line in text.splitlines()
                                                if re.search(r"failed|error|passed|collected|Error|FAIL|PASS", line)][-30:])
            records[relative] = record
        snapshots = {}
        baseline = objects["full-before.json"] if "spec-failure" in name else None
        for relative, value in objects.items():
            if not isinstance(value, dict) or not {"m3", "primary"}.issubset(value):
                continue
            if not (relative.endswith(("-before.json", "-after.json"))):
                continue
            source = value["m3"]["source"]
            assert digest(json.dumps(sorted(source.items()), ensure_ascii=True,
                                     separators=(",", ":")).encode()) == value["m3"]["source_sha256"]
            if baseline:
                assert value == baseline
                identity_commit = value["m3"]["head"]
            elif source == json.loads((OWN / "full-before.json").read_text())["m3"]["source"]:
                identity_commit = HEAD
            elif value["m3"]["source_sha256"] == "78fb2d84827b0e9c32df1bebbee9d4840f5eff301100da0a9f5489a0146b4357":
                identity_commit = "3444cf1967f9b5c9d64fde824dd4b53333a29143"
            else:
                identity_commit = None
            if identity_commit:
                for source_path, expected in source.items():
                    assert digest(git(ROOT, "show", identity_commit + ":" + source_path)) == expected
            snapshots[relative] = {"recorded_head": value["m3"]["head"],
                                   "content_matches_commit": identity_commit,
                                   "source_count": len(source), "sha256": value["m3"]["source_sha256"],
                                   "baseline_equal": value == baseline if baseline else None,
                                   "classification": "frozen snapshot" if identity_commit else
                                   "preserved intermediate implementer source; not final-freeze proof"}
        pairs = {}
        for relative, value in objects.items():
            if relative.endswith("-before.json"):
                after = relative.replace("-before.json", "-after.json")
                assert value == objects[after]
                pairs[relative] = after
        result[name] = {"manifest_sha256": digest(manifest_path.read_bytes()),
                        "payload_sha256": manifest["payload_sha256"], "payload_files": len(files),
                        "all_bytes_read_parsed_as_applicable": True, "files": records,
                        "snapshots": snapshots, "paired_snapshots_equal": pairs}
    write("archive-structure-audit.json", result)
    print(json.dumps({k: {"payload": v["payload_files"], "snapshots": len(v["snapshots"]),
                         "pairs": len(v["paired_snapshots_equal"])} for k, v in result.items()}))


def inventory():
    baseline = json.loads((OWN / "full-before.json").read_text())
    snapshots = {}
    for path in sorted(OWN.glob("*-before.json")) + sorted(OWN.glob("*-after.json")):
        assert json.loads(path.read_text()) == baseline, path.name
        snapshots[path.name] = digest(path.read_bytes())
    suites = {p.name: xml_data(p) for p in sorted(OWN.glob("*.xml"))}
    nodes = suites["full.xml"]["cases"]
    f1 = [x for x in nodes if x["name"].startswith((
        "test_gate_tie_order_matches_publish_authority", "test_gate_order_excludes_unbound_or_future_pass"))]
    c1 = [x for x in nodes if x["name"] in {
        "test_current_health_gate_must_not_borrow_previous_deployment_pass",
        "test_historical_health_gate_must_not_be_replaced_by_new_deployment"}]
    positive_decimal = [x for x in nodes if re.search("decimal|precision", x["name"], re.I)]
    assert len(f1) == 9 and len(c1) == 2
    assert all(x["result"] == "pass" for x in f1 + c1 + positive_decimal)
    frontend = {}
    for p, expected in baseline["m3"]["source"].items():
        if not p.startswith("frontend/"):
            continue
        path = OWN / p
        actual = digest(path.read_bytes())
        frontend[p] = {"sha256": actual, "freeze_match": actual == expected}
    assert len(frontend) == 31
    assert {p for p, v in frontend.items() if not v["freeze_match"]} == {
        "frontend/vite.config.ts", "frontend/playwright.config.ts"}
    modules = OWN / "frontend/node_modules"
    assert not modules.is_symlink()
    dependencies = {}
    links = {}
    for directory, dirs, files in os.walk(modules):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                assert path.resolve().is_relative_to(modules)
                links[str(path.relative_to(modules))] = str(path.resolve())
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                dependencies[str(path.relative_to(modules))] = digest(path.read_bytes())
    assets = {str(p.relative_to(OWN / "frontend/dist")): digest(p.read_bytes())
              for p in sorted((OWN / "frontend/dist").rglob("*")) if p.is_file()}
    versions = {name: json.loads((modules / name / "package.json").read_text())["version"]
                for name in ("vite", "@vitejs/plugin-react", "react", "react-dom", "@playwright/test", "typescript")}
    production = {}
    for path in sorted(OWN.glob("production-*-desktop.json")) + sorted(OWN.glob("production-*-mobile.json")):
        data = json.loads(path.read_text())
        assert not data["errors"] and data["overflow"] <= 1
        assert all(x["method"] == "GET" for x in data["requests"])
        for url, sha in data["hashes"].items():
            assert assets["assets/" + url.rsplit("/", 1)[1]] == sha
        production[path.name] = {"sha256": digest(path.read_bytes()), "scenario": data["scenario"],
                                "page_http": len(data["requests"]),
                                "explicit_context_http": 1 + len(data["hashes"]) +
                                int(data["scenario"].startswith("history")),
                                "errors": data["errors"], "overflow": data["overflow"],
                                "asset_hashes": data["hashes"],
                                "health": [r for r in data["body"]["gate_receipts"] if r["health_source"]]}
    commands = {p.name: json.loads(p.read_text()) for p in sorted(OWN.glob("*-command.json"))}
    lifecycle = {p.name: json.loads(p.read_text()) for p in sorted(OWN.glob("*-lifecycle.json"))}
    assert all(v["drop_exit"] == 0 for v in [*lifecycle.values(),
                                           *(v for v in commands.values() if "db" in v)])
    write("independent-verification.json", {
        "recorded_at": datetime.now(UTC).isoformat(), "own_raw": str(OWN), "scope": "WHOLE Task9 SPEC only",
        "head": HEAD, "parent": git(ROOT, "rev-parse", HEAD + "^").decode().strip(),
        "branch": git(ROOT, "branch", "--show-current").decode().strip(),
        "changed_source_whole": git(ROOT, "diff", "--name-status",
            "8869166878a193a1c453376471cbe52c8fa84b3f", HEAD, "--", "python", "frontend").decode(),
        "source_identity": {k: {p: v[p] for p in ("head", "source_sha256", "index_hash", "index_mtime",
                                                    "status", "venv", "vite", "vite_temp")}
                            for k, v in baseline.items()},
        "source_counts": {k: len(v["source"]) for k, v in baseline.items()},
        "snapshots": snapshots, "all_snapshots_equal": True,
        "suites": suites, "f1_nine": f1, "c1_two": c1, "positive_decimal": positive_decimal,
        "commands": commands, "lifecycles": lifecycle, "frontend_copy": frontend,
        "dependency_versions": versions, "dependency_files": len(dependencies),
        "dependency_tree_sha256": digest(json.dumps(sorted(dependencies.items()),
                                                   separators=(",", ":")).encode()),
        "dependencies_physical": True, "internal_symlinks": links,
        "dist": assets, "production": production,
        "accounting": {"pytest_invocations": sum("db" in v for v in commands.values()),
                       "production_scenarios": len(lifecycle),
                       "page_http": sum(v["page_http"] for v in production.values()),
                       "explicit_context_http": sum(v["explicit_context_http"] for v in production.values()),
                       "readiness_probes": "at least one GET per scenario; retries not counted",
                       "backend_inprocess_mock_ui_http": "not instrumented; unknown",
                       "actual_model_requests": 0, "actual_model_cost": "0",
                       "role": "synthetic engineering fixtures; no students/holdout/release qualification"},
    })
    print(json.dumps({k: {p: v[p] for p in ("tests", "passed", "failures", "errors", "skips",
                                           "suite_seconds", "sha256")} for k, v in suites.items()}, indent=2))


def cleanup():
    from redis import Redis
    dbs = {json.loads(p.read_text())["db"] for p in OWN.glob("*-command.json")
           if "db" in json.loads(p.read_text())}
    dbs.update(json.loads(p.read_text())["db"] for p in OWN.glob("*-lifecycle.json"))
    assert all(re.fullmatch(r"m3_t9_spec_[0-9a-f]{32}", db) for db in dbs)
    existing = set(subprocess.check_output([
        PG + "psql", "-h", "127.0.0.1", "-p", "55432", "-U", "postgres", "-d", "postgres",
        "-Atc", "select datname from pg_database"]).decode().splitlines())
    assert not existing.intersection(dbs)
    streams = sorted({json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()})
    assert all(re.fullmatch(r"test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*", s) for s in streams)
    redis = Redis(host="127.0.0.1", port=56379, db=0)
    before = {s: redis.exists(s) for s in streams}
    for stream, exists in before.items():
        if exists:
            redis.delete(stream)
    after = {s: redis.exists(s) for s in streams}
    redis.close()
    assert not any(after.values())
    ports = {}
    for port in (35730, 35731):
        with socket.socket() as sock:
            sock.settimeout(1)
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port))
    assert all(ports.values())
    removed = []
    for relative in ("frontend/node_modules", "frontend/dist", "frontend/.vite",
                     "cache", "tmp", "npm-cache", "vite-cache", "pycache", "__pycache__"):
        path = OWN / relative
        assert not path.is_symlink() and path.resolve().is_relative_to(OWN)
        if path.exists():
            shutil.rmtree(path)
            removed.append(relative)
    write("cleanup-verification.json", {"recorded_at": datetime.now(UTC).isoformat(),
          "exact_databases": sorted(dbs), "db_remaining": [],
          "exact_streams": streams, "redis_before": before, "redis_after": after,
          "ports_connect_ex": ports, "removed_own_paths": removed,
          "scope": "own exact resources only; no prefix deletion or global flush"})
    snapshot("final-source-after")
    assert json.loads((OWN / "final-source-after.json").read_text()) == json.loads((OWN / "full-before.json").read_text())
    print(json.dumps({"db_count": len(dbs), "stream_count": len(streams),
                      "deleted_existing_streams": sum(before.values()), "ports_closed": ports,
                      "final_snapshot_equal": True}))


def traces():
    records = {}
    for path in sorted(OWN.glob("*-output/**/*.zip")):
        with ZipFile(path) as archive:
            assert archive.testzip() is None
            members = {}
            for member in archive.namelist():
                raw = archive.read(member)
                entry = {"bytes": len(raw), "sha256": digest(raw)}
                if member.endswith((".trace", ".network")):
                    events = [json.loads(line) for line in raw.splitlines()]
                    entry.update(events=len(events),
                                 types=dict(Counter(e.get("type") for e in events)))
                members[member] = entry
        records[str(path.relative_to(OWN))] = {"sha256": digest(path.read_bytes()),
                                              "crc_ok": True, "members": members}
    write("own-trace-audit.json", records)
    print(json.dumps({"own_trace_zip_count": len(records), "all_crc_and_events_parsed": True}))


def manifest():
    assert (OWN / "review-result.md").exists()
    files = {str(p.relative_to(OWN)): digest(p.read_bytes()) for p in sorted(OWN.rglob("*"))
             if p.is_file() and p.name != "retained-manifest.json"}
    write("retained-manifest.json", {"recorded_at": datetime.now(UTC).isoformat(),
          "files": files, "payload_sha256": digest(json.dumps(sorted(files.items()),
              ensure_ascii=True, separators=(",", ":")).encode()),
          "role": "independent WHOLE Task9 SPEC FAIL; no acceptance"})
    print(json.dumps({"retained_files": len(files),
                      "manifest_sha256": digest((OWN / "retained-manifest.json").read_bytes())}))


if __name__ == "__main__":
    {"archives": archive_audit, "inventory": inventory, "cleanup": cleanup,
     "traces": traces, "manifest": manifest}[sys.argv[1]]()
