from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess

import asyncpg
from redis.asyncio import Redis

from review import OWN, ROOT, PRIMARY, git, digest, write, snapshot


def evidence():
    baseline = json.loads((OWN / "full-before.json").read_text())
    snapshots = {}
    for path in sorted(OWN.glob("*-before.json")) + sorted(OWN.glob("*-after.json")):
        current = json.loads(path.read_text())
        assert current == baseline, path
        snapshots[path.name] = digest(path.read_bytes())
    suites = {}
    for path in sorted(OWN.glob("*.xml")):
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        failures = [c for c in cases if c.find("failure") is not None]
        errors = [c for c in cases if c.find("error") is not None]
        skipped = [c for c in cases if c.find("skipped") is not None]
        modules = Counter(c.get("classname") for c in cases)
        suites[path.name] = {
            "tests": len(cases), "passed": len(cases) - len(failures) - len(errors) - len(skipped),
            "failures": len(failures), "errors": len(errors), "skips": len(skipped),
            "suite_seconds": sum(float(s.get("time", "0")) for s in root.iter("testsuite")),
            "sha256": digest(path.read_bytes()), "modules": dict(modules),
            "failures_detail": [{"name": c.get("name"), "type": c.find("failure").get("type"),
                                 "message": c.find("failure").get("message")} for c in failures],
            "errors_detail": [{"name": c.get("name"), "type": c.find("error").get("type"),
                               "message": c.find("error").get("message")} for c in errors],
        }
    full_cases = list(ET.parse(OWN / "full.xml").iter("testcase"))
    f1 = [c for c in full_cases if any(p in c.get("name", "") for p in (
        "test_gate_tie_order_matches_publish_authority",
        "test_later_gate_pass_restores_display_and_authority",
        "test_gate_order_excludes_unbound_or_future_pass"))]
    assert len(f1) == 9, [c.get("name") for c in f1]
    health = [c for c in full_cases if "test_ops_health_binding" in c.get("classname", "")]
    assert len(health) == 42
    frontend = {p: h for p, h in baseline["m3"]["source"].items()
                if p.startswith("frontend/")}
    copy_matches = {}
    for path, expected in frontend.items():
        relative = path.removeprefix("frontend/")
        actual = digest((OWN / "frontend" / relative).read_bytes())
        copy_matches[relative] = actual == expected
    mismatches = [p for p, same in copy_matches.items() if not same]
    assert set(mismatches) == {"playwright.config.ts", "vite.config.ts"}, mismatches
    dependencies = OWN / "frontend/node_modules"
    assert not dependencies.is_symlink()
    external_symlinks = []
    for directory, dirs, files in os.walk(dependencies):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink() and not path.resolve().is_relative_to(dependencies):
                external_symlinks.append(str(path))
    assert not external_symlinks, external_symlinks
    dist = {str(p.relative_to(OWN / "frontend/dist")): digest(p.read_bytes())
            for p in sorted((OWN / "frontend/dist").rglob("*")) if p.is_file()}
    commands = {p.name: json.loads(p.read_text()) for p in sorted(OWN.glob("*-command.json"))}
    archive = json.loads((OWN / "archive-parsed.json").read_text())
    final_archive = {p: v for p, v in archive["xml"].items()
                     if "task9-health-binding-fix-evidence/" in p}
    assert len(final_archive) == 19
    report = {
        "recorded_at": datetime.now(UTC).isoformat(), "own_raw": str(OWN),
        "source_identity": {k: {"head": v["head"], "source_count": len(v["source"]),
                               "source_sha256": v["source_sha256"], "status": v["status"],
                               "index_sha256": v["index_hash"], "index_mtime": v["index_mtime"],
                               "venv": v["venv"], "vite": v["vite"], "vite_temp": v["vite_temp"]}
                            for k, v in baseline.items()},
        "all_snapshots_equal": True, "snapshots": snapshots, "suites": suites,
        "f1_cases": [c.get("name") for c in f1],
        "health_binding_cases": [c.get("name") for c in health],
        "changed_source": git(ROOT, "diff", "--name-status",
            "8869166878a193a1c453376471cbe52c8fa84b3f", "HEAD", "--", "python", "frontend").decode(),
        "frontend_copy_count": len(frontend), "frontend_copy_mismatches": mismatches,
        "node_modules_physical": True, "external_dependency_symlinks": external_symlinks,
        "dist_sha256": dist, "commands": commands, "final_archive_xml": final_archive,
        "archive_xml_count": len(archive["xml"]), "archive_checks": archive["checks"],
    }
    write("independent-verification.json", report)
    print(json.dumps({p: {k: v[k] for k in ("tests", "passed", "failures", "errors", "skips",
                                          "suite_seconds", "sha256")} for p, v in suites.items()}, indent=2))
    print(json.dumps({"f1": len(f1), "health_binding": len(health), "snapshots": len(snapshots),
                      "frontend": len(frontend), "archive_checks": archive["checks"],
                      "dist": dist}, indent=2))


async def cleanup():
    dbs = {json.loads(p.read_text())["db"] for p in OWN.glob("*-command.json")}
    dbs.update(p.read_text().strip() for p in OWN.glob("live-*-db.txt"))
    assert all(re.fullmatch(r"m3_t9_spec_[0-9a-f]{32}", db) for db in dbs)
    con = await asyncpg.connect(host="127.0.0.1", port=55432, user="postgres", database="postgres")
    try:
        existing = await con.fetch("SELECT datname FROM pg_database WHERE datname=ANY($1::text[])", list(dbs))
        for row in existing:
            subprocess.run(["/opt/homebrew/opt/postgresql@16/bin/dropdb",
                            "-h", "127.0.0.1", "-p", "55432", "-U", "postgres", row["datname"]], check=True)
        remaining = await con.fetch("SELECT datname FROM pg_database WHERE datname=ANY($1::text[])", list(dbs))
        assert not remaining
    finally:
        await con.close()
    redis = Redis.from_url("redis://127.0.0.1:56379/0")
    streams = {json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()}
    assert all(re.fullmatch(r"test:(?:[a-z-]+:)*[0-9a-f]{32}(?::[a-z-]+)*", s) for s in streams)
    try:
        redis_before = {s: await redis.exists(s) for s in sorted(streams)}
        for stream, exists in redis_before.items():
            if exists:
                await redis.delete(stream)
        redis_after = {s: await redis.exists(s) for s in sorted(streams)}
        assert not any(redis_after.values())
    finally:
        await redis.aclose()
    ports = {}
    for port in (33630, 33631):
        with socket.socket() as sock:
            sock.settimeout(1)
            ports[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(ports.values()), ports
    removed = []
    for name in ("frontend/node_modules", "frontend/dist", "frontend/.vite",
                 "npm-cache", "cache", "tmp", "vite-cache", "pycache", "__pycache__"):
        path = OWN / name
        assert not path.is_symlink()
        assert path.resolve().is_relative_to(OWN)
        if path.exists():
            shutil.rmtree(path)
            removed.append(name)
    write("cleanup-verification.json", {
        "recorded_at": datetime.now(UTC).isoformat(), "exact_owned_databases": sorted(dbs),
        "db_before": [r["datname"] for r in existing], "db_after": [],
        "exact_owned_streams": sorted(streams), "redis_before": redis_before, "redis_after": redis_after,
        "ports_closed": ports, "removed_own_cache_dirs": removed,
    })
    snapshot("final-source-after")
    final = json.loads((OWN / "final-source-after.json").read_text())
    assert final == json.loads((OWN / "full-before.json").read_text())
    retained = {}
    for path in sorted(OWN.rglob("*")):
        if path.is_file() and path.name != "retained-manifest.json":
            retained[str(path.relative_to(OWN))] = digest(path.read_bytes())
    write("retained-manifest.json", {
        "files": retained, "payload_sha256": digest(json.dumps(sorted(retained.items()),
              ensure_ascii=True, separators=(",", ":")).encode()),
        "recorded_at": datetime.now(UTC).isoformat()})
    print(json.dumps({"exact_db_count": len(dbs), "exact_stream_count": len(streams),
                      "db_remaining": 0, "streams_remaining": 0, "ports": ports,
                      "removed": removed, "retained_count": len(retained)}))


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "evidence":
        evidence()
    elif sys.argv[1] == "archive-gitblob":
        result = {}
        for name, field in (("task9-health-binding-fix-evidence", "files_sha256"),
                            ("task9-code-failure-evidence", "files")):
            directory = ROOT / "docs/superpowers/reports" / name
            manifest = json.loads((directory / "manifest.json").read_text())
            paths = ["manifest.json", *manifest[field]]
            for relative in paths:
                path = directory / relative
                assert git(ROOT, "show", "HEAD:" + str(path.relative_to(ROOT))) == path.read_bytes()
            result[name] = {"git_blob_paths": len(paths), "all_equal": True}
        write("archive-gitblob.json", result)
        print(json.dumps(result))
    elif sys.argv[1] == "cleanup":
        asyncio.run(cleanup())
