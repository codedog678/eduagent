"""Capture temporary build identity, then remove only this repair's resources."""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from redis import Redis

from provenance import EVIDENCE, ROOT, digest, sha

OWN = Path("/tmp/m3-task9-gate-order-fix")
PG = "/opt/homebrew/opt/postgresql@16/bin/psql"


def frontend():
    copy = OWN / "frontend"
    paths = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "frontend"], text=True,
    ).splitlines()
    configs = {"frontend/vite.config.ts", "frontend/playwright.config.ts"}
    matched = {}
    for path in paths:
        if path in configs:
            continue
        original = (ROOT / path).read_bytes()
        assert (copy / Path(path).relative_to("frontend")).read_bytes() == original, path
        matched[path] = sha(original)
    archive = EVIDENCE / "execution-config"
    archive.mkdir(exist_ok=True)
    for path in configs:
        src = copy / Path(path).relative_to("frontend")
        shutil.copy2(src, archive / src.name)
    for name in ("playwright.live.config.ts", "gate-tie.spec.ts", "live.spec.ts"):
        source = copy / name if name.endswith("config.ts") else copy / "live-e2e" / name
        assert source.read_bytes() == (EVIDENCE / name).read_bytes(), name
    dependencies = copy / "node_modules"
    assert not dependencies.is_symlink()
    external_links = [
        str(p.relative_to(dependencies)) for p in dependencies.rglob("*")
        if p.is_symlink() and not p.resolve().is_relative_to(copy.resolve())
    ]
    assert not external_links, external_links
    dist = {str(p.relative_to(copy / "dist")): sha(p.read_bytes())
            for p in sorted((copy / "dist").rglob("*")) if p.is_file()}
    assert dist
    result = {
        "matched_tracked_frontend": matched, "matched_count": len(matched),
        "matched_sha256": digest(matched),
        "config_exceptions": sorted(configs),
        "config_retention": "execution-config/; cacheDir and dedicated port only",
        "live_scripts_match_retained_bytes": True,
        "node_modules_is_symlink": False, "node_modules_realpath": str(dependencies.resolve()),
        "external_dependency_symlinks": external_links,
        "node": "20.19.5", "vite": "7.3.7",
        "versions_evidence": "build.log",
        "dist": dist, "dist_count": len(dist), "dist_sha256": digest(dist),
        "retention_limit": "dist bytes hashed; dependency location checked; neither retained",
    }
    (EVIDENCE / "frontend-isolation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def cleanup():
    count = subprocess.check_output([
        PG, "-h", "127.0.0.1", "-p", "55432", "-U", "postgres", "-d", "postgres",
        "-Atc", "SELECT count(*) FROM pg_database WHERE datname LIKE 'm3_t9_fix_%';",
    ], text=True).strip()
    assert count == "0", count
    ports = subprocess.run([
        "lsof", "-nP", "-iTCP:33190", "-iTCP:33191", "-sTCP:LISTEN",
    ], capture_output=True, text=True)
    assert ports.returncode == 1 and not ports.stdout, ports.stdout
    client = Redis(host="127.0.0.1", port=56379, db=0, decode_responses=True)
    try:
        patterns = ("test:runs:*", "test:experts:*", "eduagent:test:failover:*")
        first = ET.parse(EVIDENCE / "red-gate-order.xml").getroot().find("testsuite")
        start_ms = int(datetime.fromisoformat(first.get("timestamp")).replace(
            tzinfo=timezone.utc,
        ).timestamp() * 1000)
        remaining = {}
        for pattern in patterns:
            rows = [client.xinfo_stream(k) for k in client.scan_iter(match=pattern)]
            ids = [int(r["last-generated-id"].split("-")[0]) for r in rows]
            remaining[pattern] = {
                "count": len(rows), "empty": sum(r["length"] == 0 for r in rows),
                "max_last_generated_ms": max(ids, default=0),
                "last_generated_in_or_after_repair": sum(v >= start_ms for v in ids),
            }
        assert all(v["last_generated_in_or_after_repair"] == 0 for v in remaining.values())
    finally:
        client.close()
    candidates = sorted(p.name for p in OWN.iterdir())
    allowed = {
        "frontend", "live-runner.pid", "npm-cache", "playwright-live-failed",
        "playwright-live-unknown", "playwright-ui", "pycache", "pytest-cache", "vite-cache",
    }
    assert set(candidates) <= allowed, candidates
    assert (EVIDENCE / "frontend-isolation.json").exists()
    for name in candidates:
        path = OWN / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    result = {
        "database_prefix": "m3_t9_fix_", "database_remaining": int(count),
        "database_lifecycle": "unique DB per invocation; runner EXIT trap dropdb",
        "dedicated_ports": [33190, 33191], "listeners_remaining": 0,
        "redis_prefix_audit": remaining, "earliest_repair_test_start_ms": start_ms,
        "redis_lifecycle": "UUID streams and fixture/failover finalizers; no FLUSH or extra DEL",
        "redis_ownership_limit": "Shared prefixes are not ownership. Old or zero-ID keys left untouched.",
        "removed_own_tmp_entries": candidates, "remaining_own_tmp_entries": [],
        "primary_written": False, "shared_services_stopped": False,
        "original_independent_tmp_removed": False,
        "failed_materials": "retained in independent/ and red-gate-order*.log/xml",
        "limits": "No new generated message ID in scanned prefixes. Zero-ID keys cannot prove ownership.",
    }
    assert not list(OWN.iterdir())
    (EVIDENCE / "cleanup.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    {"frontend": frontend, "cleanup": cleanup}[sys.argv[1]]()
