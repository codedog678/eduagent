"""Implementation evidence bookkeeping, not SPEC/CODE review or acceptance."""
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from xml.etree import ElementTree as ET

from review import HEAD, OWN, PG, PY, ROOT, digest, git, snapshot, write

ARCHIVE = ROOT / "docs/superpowers/reports/task9-source-integrity-fix-evidence"
REPORT = ROOT / "docs/superpowers/reports/task9-source-integrity-fix-implementation.md"
SOURCE = [
    "python/core/distributed/ops_queries.py",
    "python/tests/distributed/test_ops_health_binding.py",
    "python/tests/distributed/test_ops_source_integrity.py",
]
NODE = "/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node"


def command(*args):
    return subprocess.check_output(args).decode().strip()


def inventory():
    xml = {}
    for path in sorted(OWN.glob("*.xml")):
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        failures = [c for c in cases if c.find("failure") is not None]
        errors = [c for c in cases if c.find("error") is not None]
        skips = [c for c in cases if c.find("skipped") is not None]
        counts = Counter(c.get("classname") for c in cases)
        xml[path.name] = {
            "sha256": digest(path.read_bytes()), "tests": len(cases),
            "passed": len(cases) - len(failures) - len(errors) - len(skips),
            "failures": len(failures), "errors": len(errors), "skipped": len(skips),
            "suite_seconds": sum(float(s.get("time", 0)) for s in root.iter("testsuite")),
            "timestamp": [s.get("timestamp") for s in root.iter("testsuite")],
            "modules": dict(counts), "nodes": [c.get("name") for c in cases],
            "nonpassing": [
                {"node": c.get("name"), "class": c.get("classname"),
                 "type": (c.find("failure") if c.find("failure") is not None else c.find("error")).get("type"),
                 "message": (c.find("failure") if c.find("failure") is not None else c.find("error")).get("message")}
                for c in failures + errors
            ],
        }
    expected = {
        "red-relations.xml": (11, 2, 9), "red-corroboration.xml": (3, 0, 3),
        "green-probes-v1.xml": (56, 56, 0), "source-regressions-v1.xml": (67, 57, 10),
        "source-regressions-v2.xml": (67, 67, 0), "full-final.xml": (1793, 1793, 0),
        "relations-api-final.xml": (244, 244, 0), "ui-final.xml": (54, 54, 0),
    }
    for name, numbers in expected.items():
        assert tuple(xml[name][k] for k in ("tests", "passed", "failures")) == numbers
        assert xml[name]["errors"] == xml[name]["skipped"] == 0
    for name in (
        "production-current-v2.xml", "production-history.xml", "production-approval-malformed.xml",
        "production-genuine-malformed.xml", "production-genuine-valid.xml",
    ):
        assert tuple(xml[name][k] for k in ("tests", "passed", "failures", "errors", "skipped")) == (2, 2, 0, 0, 0)
    nodes = xml["full-final.xml"]["nodes"]
    f1 = [n for n in nodes if n.startswith((
        "test_gate_tie_order_matches_publish_authority", "test_gate_order_excludes_unbound_or_future_pass",
    ))]
    c1 = [n for n in nodes if n in {
        "test_current_health_gate_must_not_borrow_previous_deployment_pass",
        "test_historical_health_gate_must_not_be_replaced_by_new_deployment",
    }]
    assert len(f1) == 9 and len(c1) == 2
    snapshots = {}
    for path in sorted(OWN.glob("*-before.json")):
        after = path.with_name(path.name.replace("-before", "-after"))
        before_data, after_data = json.loads(path.read_text()), json.loads(after.read_text())
        assert before_data == after_data, path
        snapshots[path.stem.removesuffix("-before")] = {
            "before_sha256": digest(path.read_bytes()), "after_sha256": digest(after.read_bytes()),
            "count": len(before_data["m3"]["source"]), "source_sha256": before_data["m3"]["source_sha256"],
            "primary_source_sha256": before_data["primary"]["source_sha256"],
            "primary_index_sha256": before_data["primary"]["index_hash"],
        }
    frontend = {}
    for raw in git(ROOT, "ls-files", "-z", "frontend").split(b"\0"):
        if not raw:
            continue
        name = raw.decode()
        actual = OWN / name
        assert actual.exists(), name
        if name not in {"frontend/vite.config.ts", "frontend/playwright.config.ts"}:
            assert actual.read_bytes() == (ROOT / name).read_bytes(), name
        frontend[name] = digest(actual.read_bytes())
    # npm 的内部 .bin 链接可保留；不允许任何链接指回产品/主工作树。
    symlinks = {str(p.relative_to(OWN)): str(p.resolve())
                for p in (OWN / "frontend/node_modules").rglob("*") if p.is_symlink()}
    assert all(Path(target).is_relative_to(OWN.resolve()) for target in symlinks.values())
    assets = {str(p.relative_to(OWN / "frontend/dist")): digest(p.read_bytes())
              for p in sorted((OWN / "frontend/dist").rglob("*")) if p.is_file()}
    production = {}
    for path in sorted(OWN.glob("production-*-desktop.json")) + sorted(OWN.glob("production-*-mobile.json")):
        data = json.loads(path.read_text())
        assert not data["errors"] and data["overflow"] <= 1
        assert all(r["method"] == "GET" for r in data["requests"])
        for url, sha in data["hashes"].items():
            assert assets["assets/" + url.rsplit("/", 1)[1]] == sha
        production[path.name] = {
            "sha256": digest(path.read_bytes()), "scenario": data["scenario"],
            "observed_page_http": len(data["requests"]),
            "explicit_request_context_http": 1 + len(data["hashes"]) + int(data["scenario"].startswith("history")),
            "console_errors": len(data["errors"]), "overflow": data["overflow"], "assets": data["hashes"],
        }
    protected = [p.decode() for p in git(ROOT, "diff", "--name-only", "-z",
                                       HEAD + "^", HEAD).split(b"\0") if p]
    assert len(protected) == 206
    for name in protected:
        assert (ROOT / name).read_bytes() == git(ROOT, "show", HEAD + ":" + name)
    runtime = {
        "python": command(PY, "--version"), "python_path": PY,
        "postgres": command(PG + "psql", "-h", "127.0.0.1", "-p", "55432", "-U", "postgres",
                            "-d", "postgres", "-Atc", "select version()"),
        "redis": "127.0.0.1:56379/0", "node": command(NODE, "--version"), "node_path": NODE,
        "lock_sha256": digest((ROOT / "frontend/package-lock.json").read_bytes()),
        "roles": "synthetic engineering; genuine transitions/evaluator; no students/holdout/model calls",
        "model_requests": 0, "model_cost": "0", "production_database_url_configured": False,
    }
    invalid = [
        "source-regressions-v1: 10 failed test nodes from fixture errors: 2 invalid environment DTO/503, "
        "2 foreign keys, 2 decimal-control assertion setup, 4 UUID-vs-varchar errors; not product RED.",
        "production-current first collection: SPEC_SCENARIO missing, zero collected; preserved log/XML.",
        "read-only file lookup failures for live-e2e/config paths before locating frontend subdirectory.",
        "read-only lookup python/tests/conftest.py absent; distributed conftest located.",
        "apply_patch independent playwright.config hunk failed once, actual config read and corrected.",
        "initial empty mistaken mktemp directory /tmp/m3-task9-fix-VWoyu6AI; no evidence files.",
        "inventory first attempt rejected normal npm internal .bin symlinks; corrected containment "
        "check accepts only links resolving inside OWN, never links to product or primary worktrees.",
    ]
    write("implementation-verification.json", {
        "authority": "implementer verification only; pending parent fresh WHOLE SPEC then CODE",
        "started_head": HEAD, "parent": command("git", "-C", str(ROOT), "rev-parse", HEAD + "^"),
        "xml": xml, "snapshots": snapshots, "f1_nine": f1, "c1_two": c1,
        "frontend": frontend, "node_internal_symlinks": symlinks,
        "assets": assets, "production": production, "runtime": runtime,
        "preserved_3444cf1_paths": protected, "invalid_attempts": invalid,
        "request_accounting": {
            "pytest_invocations": len(list(OWN.glob("*-command.json"))),
            "page_http": sum(x["observed_page_http"] for x in production.values()),
            "explicit_request_context_http": sum(x["explicit_request_context_http"] for x in production.values()),
            "backend_inprocess_api_and_mock_ui_http_count": "not instrumented; not counted as external model requests",
            "model_requests": 0, "model_cost": "0",
            "synthetic_fixture_model_calls_and_costs": "simulated bookkeeping only, not actual requests/billing",
        },
        "service_lifecycles": {
            p.stem.removeprefix("live-").removesuffix("-db"): {
                "database": p.read_text().strip(),
                "database_record_time": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(),
                "cleanup_record_time": datetime.fromtimestamp(
                    p.with_name(p.name.replace("-db", "-cleanup")).stat().st_mtime, UTC).isoformat(),
                "port": 34631,
            } for p in OWN.glob("live-*-db.txt")
        },
    })
    print(json.dumps({name: [v[k] for k in ("tests", "passed", "failures", "errors", "skipped")]
                      for name, v in xml.items()}, indent=2))


def cleanup():
    from redis import Redis
    database_names = [json.loads(p.read_text())["db"] for p in OWN.glob("*-command.json")]
    database_names += [p.read_text().strip() for p in OWN.glob("live-*-db.txt")]
    existing = set(command(PG + "psql", "-h", "127.0.0.1", "-p", "55432", "-U", "postgres",
                           "-d", "postgres", "-Atc", "select datname from pg_database").splitlines())
    assert all(name.startswith("m3_t9_fix_") for name in database_names)
    assert not existing.intersection(database_names)
    streams = sorted({json.loads(line)["stream"] for line in (OWN / "redis-owned.jsonl").read_text().splitlines()})
    redis = Redis(host="127.0.0.1", port=56379, db=0)
    remaining = [stream for stream in streams if redis.exists(stream)]
    assert not remaining, remaining
    ports = {}
    for port in (34630, 34631):
        with socket.socket() as sock:
            ports[port] = sock.connect_ex(("127.0.0.1", port))
        assert ports[port] != 0
    removed = []
    for relative in ("frontend/node_modules", "frontend/dist", "cache", "tmp", "pycache",
                     "npm-cache", "vite-cache"):
        target = OWN / relative
        if target.exists():
            assert target.resolve().is_relative_to(OWN.resolve())
            shutil.rmtree(target)
            removed.append(relative)
    mistake = Path("/tmp/m3-task9-fix-VWoyu6AI")
    if mistake.exists():
        mistake.rmdir()
        removed.append(str(mistake))
    write("cleanup-verification.json", {
        "time": datetime.now(UTC).isoformat(), "exact_databases": database_names,
        "exact_streams": streams, "remaining_databases": [], "remaining_streams": [],
        "ports_connect_ex": ports, "removed_own_paths": removed,
        "scope": "only this UUID's exact resources; no global flush/prefix deletes/foreign resources",
    })
    snapshot("final-source-after")
    print(json.dumps({"databases": len(database_names), "streams": len(streams), "ports_closed": ports}))


def archive():
    assert not ARCHIVE.exists()
    ARCHIVE.mkdir()
    files = {}
    for path in sorted(OWN.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(OWN)
        if relative.parts[0] in {"__pycache__"}:
            continue
        dest = ARCHIVE / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        files[str(relative)] = digest(dest.read_bytes())
    manifest = {
        "role": "implementation evidence; no independent acceptance",
        "source_file_count": 353,
        "source_sha256": json.loads((OWN / "final-source-after.json").read_text())["m3"]["source_sha256"],
        "files_sha256": files,
        "payload_sha256": digest(json.dumps(sorted(files.items()), ensure_ascii=True, separators=(",", ":")).encode()),
    }
    (ARCHIVE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"archive": str(ARCHIVE), "files": len(files), "payload_sha256": manifest["payload_sha256"]}))


def stage():
    assert REPORT.exists()
    names = SOURCE + [str(REPORT.relative_to(ROOT))] + [
        str(path.relative_to(ROOT)) for path in sorted(ARCHIVE.rglob("*")) if path.is_file()
    ]
    for offset in range(0, len(names), 100):
        subprocess.run(["git", "add", "-f", "--", *names[offset:offset + 100]], cwd=ROOT, check=True)
    staged = [p.decode() for p in git(ROOT, "diff", "--cached", "--name-only", "-z").split(b"\0") if p]
    assert set(staged) == set(names)
    for name in staged:
        assert (ROOT / name).read_bytes() == git(ROOT, "show", ":" + name)
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    write("staged-files.json", {"parent": HEAD, "files": staged, "staged_gitblob_byte_exact": True})
    print(json.dumps({"staged": len(staged), "source_files": SOURCE}))


def postcommit():
    frozen = git(ROOT, "rev-parse", "HEAD").decode().strip()
    assert git(ROOT, "rev-parse", "HEAD^").decode().strip() == HEAD
    staged = json.loads((OWN / "staged-files.json").read_text())["files"]
    assert set(staged) == set(p.decode() for p in git(ROOT, "diff", "--name-only", "-z", "HEAD^", "HEAD").split(b"\0") if p)
    for name in staged:
        assert (ROOT / name).read_bytes() == git(ROOT, "show", "HEAD:" + name)
    source = {p.decode(): digest((ROOT / p.decode()).read_bytes())
              for p in git(ROOT, "ls-files", "-z", "python", "frontend").split(b"\0") if p}
    final = json.loads((OWN / "final-source-after.json").read_text())
    assert source == final["m3"]["source"] and len(source) == 353
    assert not git(ROOT, "status", "--porcelain")
    for name in source:
        assert (ROOT / name).read_bytes() == git(ROOT, "show", "HEAD:" + name)
    import review
    review.HEAD = frozen
    snapshot("postcommit-source")
    post = json.loads((OWN / "postcommit-source.json").read_text())
    assert post["primary"] == final["primary"]
    assert post["m3"]["source"] == final["m3"]["source"]
    write("freeze-verification.json", {
        "commit": frozen, "parent": HEAD, "files": staged, "gitblob_files": len(staged),
        "source_count": 353, "source_sha256": final["m3"]["source_sha256"],
        "source_gitblob_byte_exact": True, "status": "clean", "primary_unchanged": True,
        "time": datetime.now(UTC).isoformat(),
    })
    print(frozen)


if __name__ == "__main__":
    {"inventory": inventory, "cleanup": cleanup, "archive": archive,
     "stage": stage, "postcommit": postcommit}[sys.argv[1]]()
