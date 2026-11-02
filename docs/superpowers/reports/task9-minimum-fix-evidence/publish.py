import asyncio
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import artifact_checks
import bootstrap
import finish_audit
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT
ARCHIVE = ROOT / "docs/superpowers/reports/task9-minimum-fix-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-minimum-fix.md"
TMP_REPORT = Path("/tmp/m3-task9-minimum-fix-result.md")
PRODUCT = "d77299c710a4d330539010d9067c5b4938f4adf1"


def manifest_sha(mapping):
    return prepare.sha(json.dumps(sorted(mapping.items()), ensure_ascii=True,
                                   separators=(",", ":")).encode())


def inventory():
    current = bootstrap.snapshot()
    frozen = json.loads((OWN / "final-snapshot.json").read_bytes())
    assert current == frozen
    commands = {}
    for path in sorted(OWN.glob("*-command.json")):
        body = json.loads(path.read_bytes())
        commands[path.name] = body
    review.write("execution-ledger.json", {
        "time": datetime.now(UTC).isoformat(), "role": "implementation verification, not acceptance",
        "commands": commands, "model_calls": 0, "model_cost_usd": "0", "global_http_requests": "unknown",
        "bookkeeping_commands": [
            "setup.py",
            "artifact_checks.py provenance",
            "artifact_checks.py stage product-staged-secret-check",
            "phase.py final-snapshot",
            "production_batch.py",
            "finish_audit.py dependencies",
            "finish_audit.py audit (invalid, preserved)",
            "finish_audit.py audit audit-corrected (invalid, preserved)",
            "finish_audit.py audit audit-final",
            "finish_audit.py cleanup",
            "publish.py inventory",
            "publish.py publish",
            "artifact_checks.py stage docs-staged-secret-check",
            "publish.py postfreeze",
        ],
        "product_commit": {
            "head": PRODUCT, "parent": review.git(ROOT, "rev-parse", PRODUCT + "^").decode().strip(),
            "paths": review.git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", PRODUCT).decode().splitlines(),
            "no_amend_push_config_or_hook_bypass": True,
        },
        "warnings_retained": [
            "pytest_asyncio asyncio_default_fixture_loop_scope unset",
            "parametrize non-Collection zip deprecated",
            "TestAgent with __init__ not collected",
            "Vite chunk larger than 500 kB",
        ],
    })
    pairs = {}
    for before in sorted(OWN.glob("*-before.json")):
        after = OWN / before.name.replace("-before.json", "-after.json")
        assert after.is_file()
        assert json.loads(before.read_bytes()) == json.loads(after.read_bytes())
        pairs[before.name] = dict(before_sha256=prepare.sha(before.read_bytes()),
                                 after_sha256=prepare.sha(after.read_bytes()))
    files = finish_audit.payload()
    hashes = {str(path.relative_to(OWN)): prepare.sha(path.read_bytes()) for path in files}
    scan = artifact_checks.scan((str(path.relative_to(OWN)), path.read_bytes()) for path in files)
    xml, zip_count, member_count = {}, 0, 0
    for path in files:
        if path.suffix == ".xml":
            cases = list(ET.fromstring(path.read_bytes()).iter("testcase"))
            xml[path.name] = dict(tests=len(cases),
                failure=sum(c.find("failure") is not None for c in cases),
                error=sum(c.find("error") is not None for c in cases),
                skip=sum(c.find("skipped") is not None for c in cases))
        elif path.suffix == ".zip":
            zip_count += 1
            with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
                assert archive.testzip() is None
                member_count += sum(not member.is_dir() for member in archive.infolist())
    audit = {
        "time": datetime.now(UTC).isoformat(), "product": PRODUCT,
        "source_count": current["m3"]["source_count"], "source_sha256": current["m3"]["source_sha256"],
        "source": current["m3"]["source"], "pairs": pairs, "xml": xml,
        "raw_files_checked": len(hashes), "raw_payload_sha256": manifest_sha(hashes),
        "files_sha256": hashes, "zip_count": zip_count, "zip_members": member_count,
        "secret_scan": scan, "primary_unchanged": True,
        "audit_report_generated_after_payload_check_no_self_hash": True,
    }
    review.write("final-payload-audit.json", audit)
    hashes["final-payload-audit.json"] = prepare.sha((OWN / "final-payload-audit.json").read_bytes())
    manifest = {
        "role": "pre-report immutable raw payload manifest; excludes self and reports",
        "product": PRODUCT, "product_parent": review.git(ROOT, "rev-parse", PRODUCT + "^").decode().strip(),
        "source_count": current["m3"]["source_count"], "source_sha256": current["m3"]["source_sha256"],
        "files": hashes, "file_count": len(hashes), "payload_sha256": manifest_sha(hashes),
        "excludes": ["payload-manifest.json", "report.md", str(REPORT.relative_to(ROOT)),
                     "docs-staged-secret-check.json", "/tmp/m3-task9-minimum-fix-postcommit.json"],
        "report_and_self_verified_separately_by_gitblob": True,
    }
    review.write("payload-manifest.json", manifest)
    print(json.dumps(dict(raw_file_count=len(hashes), payload_sha256=manifest["payload_sha256"],
        manifest_sha256=prepare.sha((OWN / "payload-manifest.json").read_bytes()),
        xml_count=len(xml), paired_snapshots=len(pairs), zip_count=zip_count, zip_members=member_count,
        secret_scan=scan, source_count=current["m3"]["source_count"], source_sha256=current["m3"]["source_sha256"])))


def publish():
    assert TMP_REPORT.is_file() and not ARCHIVE.exists() and not REPORT.exists()
    assert review.git(ROOT, "rev-parse", "HEAD").decode().strip() == PRODUCT
    manifest = json.loads((OWN / "payload-manifest.json").read_bytes())
    assert manifest_sha(manifest["files"]) == manifest["payload_sha256"]
    for name, digest in manifest["files"].items():
        assert prepare.sha((OWN / name).read_bytes()) == digest
    artifact_checks.scan((name, (OWN / name).read_bytes()) for name in manifest["files"])
    ARCHIVE.mkdir()
    for name in [*manifest["files"], "payload-manifest.json"]:
        source, target = OWN / name, ARCHIVE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert source.read_bytes() == target.read_bytes()
    for path in (OWN / "report.md", ARCHIVE / "report.md", REPORT):
        shutil.copy2(TMP_REPORT, path)
        assert path.read_bytes() == TMP_REPORT.read_bytes()
    entries = [(str(path.relative_to(ROOT)), path.read_bytes()) for path in ARCHIVE.rglob("*") if path.is_file()]
    entries.append((str(REPORT.relative_to(ROOT)), REPORT.read_bytes()))
    result = artifact_checks.scan(entries)
    print(json.dumps(dict(report_sha256=prepare.sha(TMP_REPORT.read_bytes()),
                          archived_paths=len(entries), secret_scan=result,
                          archive=str(ARCHIVE), report=str(REPORT))))


def postfreeze():
    head = review.git(ROOT, "rev-parse", "HEAD").decode().strip()
    parent = review.git(ROOT, "rev-parse", "HEAD^").decode().strip()
    assert head != PRODUCT and parent == PRODUCT
    paths = review.git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", head).decode().splitlines()
    assert paths and all(path == str(REPORT.relative_to(ROOT)) or path.startswith(str(ARCHIVE.relative_to(ROOT)) + "/")
                         for path in paths)
    assert not review.git(ROOT, "status", "--porcelain").strip()
    current = bootstrap.snapshot()
    start = json.loads((OWN / "initial-snapshot.json").read_bytes())
    final = json.loads((OWN / "final-snapshot.json").read_bytes())
    assert current["primary"] == start["primary"]
    assert current["m3"]["source"] == final["m3"]["source"]
    for key in ("venv", "vite", "vite_temp"):
        assert current["m3"][key] == start["m3"][key]
    prepare.verify_blobs(head, current["m3"]["tracked"])
    prepare.verify_blobs(PRODUCT, current["m3"]["source"])
    for name, digest in start["m3"]["tracked"].items():
        if name != "python/core/distributed/ops_queries.py":
            assert prepare.sha((ROOT / name).read_bytes()) == digest
    manifest = json.loads((ARCHIVE / "payload-manifest.json").read_bytes())
    assert manifest_sha(manifest["files"]) == manifest["payload_sha256"]
    for name, digest in manifest["files"].items():
        assert prepare.sha((ARCHIVE / name).read_bytes()) == digest
    assert TMP_REPORT.read_bytes() == REPORT.read_bytes() == (ARCHIVE / "report.md").read_bytes()
    assert review.git(ROOT, "show", head + ":" + str(REPORT.relative_to(ROOT))) == TMP_REPORT.read_bytes()
    scan = artifact_checks.scan((path, (ROOT / path).read_bytes()) for path in paths)
    pg = asyncio.run(finish_audit.pg_verify())
    result = {
        "time": datetime.now(UTC).isoformat(), "role": "postcommit implementation handoff, not acceptance",
        "actual_HEAD": head, "actual_parent": parent, "product_freeze": PRODUCT,
        "product_parent": review.git(ROOT, "rev-parse", PRODUCT + "^").decode().strip(),
        "docs_new_paths": len(paths), "all_current_tracked_gitblobs_verified": len(current["m3"]["tracked"]),
        "source_count": current["m3"]["source_count"], "source_sha256": current["m3"]["source_sha256"],
        "report_sha256": prepare.sha(TMP_REPORT.read_bytes()),
        "report_byte_identical_tmp_repo_archive": True,
        "raw_files": manifest["file_count"], "payload_sha256": manifest["payload_sha256"],
        "manifest_sha256": prepare.sha((ARCHIVE / "payload-manifest.json").read_bytes()),
        "secret_scan": scan, "primary_unchanged": True, "worktree_clean": True,
        "postgres": pg, "resources": json.loads((ARCHIVE / "resource-after-cleanup.json").read_bytes()),
        "SPEC_CODE_acceptance": "not performed; fresh WHOLESPEC required, then fresh WHOLECODE on PASS",
        "models": dict(requests=0, cost_usd="0"), "global_http_total": "unknown",
        "archive": str(ARCHIVE), "report": str(REPORT),
        "hash_cycle_avoidance": "postcommit actual hash is external; durable report resolves its own archive commit by path",
    }
    with Path("/tmp/m3-task9-minimum-fix-postcommit.json").open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({key: result[key] for key in (
        "actual_HEAD", "actual_parent", "product_freeze", "docs_new_paths",
        "all_current_tracked_gitblobs_verified", "source_count", "source_sha256",
        "report_sha256", "raw_files", "payload_sha256", "manifest_sha256",
        "secret_scan", "primary_unchanged", "worktree_clean")}, indent=2))


if __name__ == "__main__":
    {"inventory": inventory, "publish": publish, "postfreeze": postfreeze}[sys.argv[1]]()
