"""Independent CODE audit. Only writes reviewer-owned evidence."""

import asyncio
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlparse
import zipfile

import bootstrap
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT
reference = ROOT / "docs/superpowers/reports/task9-minimum-spec-pass-evidence/final_audit.py"
loader = importlib.util.spec_from_file_location("readonly_audit_reference", reference)
ref = importlib.util.module_from_spec(loader)
loader.loader.exec_module(ref)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def execution():
    review.snapshot("evidence-audit-final-before")
    results = {p.name: ref.xml_record(p) for p in sorted(OWN.glob("*.xml"))}
    expected = {
        "full-final.xml": (1864, 0, 0), "api-final.xml": (315, 0, 0),
        "integrity-complete.xml": (111, 0, 0), "minimum.xml": (28, 0, 0),
        "fresh-leaf.xml": (9, 7, 0), "fresh-active.xml": (6, 5, 0),
        "ui54.xml": (54, 1, 2), "ui54-recheck.xml": (54, 0, 0),
        "ui-visual4.xml": (4, 0, 0),
    }
    for name, (tests, failures, errors) in expected.items():
        assert results[name]["tests"] == tests
        assert results[name]["failures"] == failures
        assert results[name]["errors"] == errors and results[name]["skips"] == 0
    prod = [name for name in results if name.startswith("prod-final-")]
    assert len(prod) == 7
    assert all(results[name]["tests"] == 2 and results[name]["failures"] == 0 for name in prod)
    commands = {p.name: json.loads(p.read_bytes()) for p in OWN.glob("*-command.json")}
    pairs = {}
    for name in commands:
        label = name.removesuffix("-command.json")
        before, after = OWN / (label + "-before.json"), OWN / (label + "-after.json")
        assert before.read_bytes() == after.read_bytes()
        pairs[label] = {"before": before.name, "after": after.name, "sha256": sha(before.read_bytes())}
    retained = OWN / "retained-http-dist"
    assert not retained.exists()
    shutil.copytree(OWN / "frontend/dist", retained)
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
                    entry["parsed_events"] = len([
                        json.loads(line) for line in content.splitlines() if line.strip()])
                members[item.filename] = entry
        traces[str(path.relative_to(OWN))] = {"sha256": sha(path.read_bytes()), "members": members}
    production = {}
    for path in sorted(OWN.glob("production-prod-final-*.json")):
        raw = json.loads(path.read_bytes())
        label, viewport = path.stem.removeprefix("production-").rsplit("-", 1)
        paths = [p for p in (OWN / (label + "-output")).rglob("trace.zip") if viewport in str(p.parent)]
        assert len(paths) == 1
        assert all(r["method"] == "GET" for r in raw["requests"])
        assert not raw["errors"] and raw["overflow"] <= 1
        assets, gets, missing = {}, 0, 0
        with zipfile.ZipFile(paths[0]) as trace:
            for entry in trace.namelist():
                if not entry.endswith(".network"):
                    continue
                for line in trace.read(entry).splitlines():
                    snapshot = json.loads(line).get("snapshot", {})
                    request = snapshot.get("request")
                    if not request:
                        continue
                    assert request["method"] == "GET"
                    gets += 1
                    url = request["url"]
                    if url not in raw["hashes"]:
                        continue
                    response = snapshot["response"]
                    assert response["status"] == 200
                    if "_file" not in response["content"]:
                        missing += 1
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
            "page_gets": len(raw["requests"]), "trace_gets": gets,
            "exact_asset_bytes": assets, "navigation_assets_without_body": missing,
            "overflow": raw["overflow"], "errors": raw["errors"],
            "scroll_before_explicit_wheel": raw["scrollBefore"], "scroll_after": raw["scrollAfter"],
            "scroll_before_may_follow_scrollIntoView": True,
            "health_sources": [r for r in raw["body"]["gate_receipts"] if r["health_source"]],
        }
    assert len(production) == 14
    archives = {}
    for directory, manifest, count in [
        ("task9-minimum-spec-pass-evidence", "retained-manifest.json", 462),
        ("task9-minimum-fix-evidence", "payload-manifest.json", 570),
        ("task9-minimum-spec-failure-evidence", "manifest.json", 466),
    ]:
        base = ROOT / "docs/superpowers/reports" / directory
        data = json.loads((base / manifest).read_bytes())
        assert len(data["files"]) == count
        for name, digest in data["files"].items():
            assert sha((base / name).read_bytes()) == digest
        combined = sha(json.dumps(sorted(data["files"].items()),
                                 ensure_ascii=True, separators=(",", ":")).encode())
        assert combined == data.get("payload_sha256", data.get("combined_sha256"))
        archives[directory] = {"count": count, "manifest_sha256": sha((base / manifest).read_bytes()),
                               "payload_sha256": combined}
    assert archives["task9-minimum-spec-pass-evidence"]["manifest_sha256"] == \
        "8c03414cbb03a275947f017ff274e7692b76cb7cb7867447c81802972b87a1bb"
    changed = review.git(ROOT, "diff", "--name-only",
        "8869166878a193a1c453376471cbe52c8fa84b3f", review.HEAD,
        "--", "python", "frontend").decode().splitlines()
    assert len(changed) == 17
    review.write("independent-execution-audit.json", {
        "time": datetime.now(UTC).isoformat(), "role": "fresh independent WHOLE CODE",
        "head": review.HEAD, "xml": results, "commands": commands, "pairs": pairs,
        "whole_changed_source_paths": changed, "archives": archives, "traces": traces,
        "production": production,
        "dist": {str(p.relative_to(retained)): sha(p.read_bytes())
                 for p in sorted(retained.rglob("*")) if p.is_file()},
        "page_gets": sum(r["page_gets"] for r in production.values()),
        "production_trace_gets": sum(r["trace_gets"] for r in production.values()),
        "asset_byte_checks": sum(len(r["exact_asset_bytes"]) for r in production.values()),
        "all_http_total": "unknown", "actual_model_requests": 0, "actual_model_cost_usd": "0",
        "overlapping_suites_not_independent_samples": True,
        "verdict": "WHOLECODEFAIL", "no_acceptance_or_task10": True,
    })
    review.snapshot("evidence-audit-final-after")


def cleanup():
    review.snapshot("cleanup-before")
    commands = [json.loads(p.read_bytes()) for p in OWN.glob("*-command.json")]
    lifecycles = [json.loads(p.read_bytes()) for p in OWN.glob("*-lifecycle.json")]
    own_names = sorted({r["db"] for r in commands + lifecycles if "db" in r})
    assert len(own_names) == 13
    assert all(r.get("drop_exit", 0) == 0 for r in commands + lifecycles)
    db = asyncio.run(ref.databases(own_names))
    identity = json.loads((OWN / "owned-redis-identity.json").read_bytes())
    client = ref.redis.Redis(host="127.0.0.1", port=identity["port"], decode_responses=True)
    server, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert server["process_id"] == identity["pid"] and server["run_id"] == identity["run_id"]
    assert config == identity["config"]
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
    for port in (56737, 56738, 56739):
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
    data = subprocess.check_output(["git", "cat-file", "--batch"],
        input="".join(f"{primary['head']}:{name}\n" for name in primary["tracked"]).encode(),
        cwd=ROOT.with_name("eduagent"))
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
    review.write("final-source-gitblob.json", {
        "time": datetime.now(UTC).isoformat(), "snapshot": snapshot,
        "m3_verified_blobs": len(snapshot["m3"]["tracked"]),
        "primary_verified_blobs": len(primary["tracked"]), "full_start_end_equal": True,
    })
    review.write("cleanup-independent.json", {
        "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
        "own_uuid_database_count": len(own_names), "own_databases": own_names, "database_check": db,
        "owned_redis_identity_before_shutdown": {"server": server, "config": config},
        "ledger_rows": len(ledger), "exact_del_unlink_commands": len(deleted),
        "remaining_keys_before_shutdown": remaining, "remaining_worker_keys_unmetered": len(remaining),
        "ledger_not_claimed_complete_for_subprocess_workers": True,
        "shutdown_command": "SHUTDOWN NOSAVE", "identity_checked": True,
        "no_flush_or_prefix_delete": True, "ports_closed": ports,
        "removed_own_cache_only": removed, "patched_runtime_and_shared_pg_preserved": True,
    })
    review.snapshot("cleanup-after")


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "execution":
        execution()
    elif action == "dependencies":
        ref.dependencies()
    elif action == "cleanup":
        cleanup()
    elif action == "scan":
        paths = ref.retained_paths()
        historical = [p for p in (ROOT / "docs/superpowers/reports").rglob("*")
                      if p.is_file() and "task9" in str(p.relative_to(ROOT))]
        source = review.git(ROOT, "diff", "--name-only",
            "8869166878a193a1c453376471cbe52c8fa84b3f", review.HEAD,
            "--", "python", "frontend").decode().splitlines()
        result = ref.secret_scan((str(p), p.read_bytes())
                                for p in paths + historical + [ROOT / name for name in source])
        result.update(time=datetime.now(UTC).isoformat(), hook_complete_not_claimed=True)
        review.write(sys.argv[2], result)
        print(json.dumps(result))
    else:
        raise ValueError(action)
