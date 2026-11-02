import json
from pathlib import Path
import shutil
import sys
from datetime import UTC, datetime

E = Path("/tmp/m3-task9-leaf-fix-8551ecba-8589-42a0-b9d7-b3873a329816")
sys.path.insert(0, str(E))
import artifact_checks
import bootstrap
import prepare
import review

R = review.ROOT
A = R / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence"
S = R / "docs/superpowers/reports/task9-leaf-authenticity-fix-staging-evidence"
REPORT = R / "docs/superpowers/reports/2026-11-02-m3-task9-leaf-authenticity-fix.md"
TMP_REPORT = Path("/tmp/m3-task9-leaf-authenticity-fix-result.md")


def write(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")


def staged():
    names = review.git(R, "diff", "--cached", "--name-only", "-z").split(b"\0")
    names = [name.decode() for name in names if name]
    mapping = {name: review.digest(review.git(R, "show", ":" + name)) for name in names}
    scan = artifact_checks.scan((name, review.git(R, "show", ":" + name)) for name in names)
    return mapping, scan


def scan():
    started = datetime.now(UTC).isoformat()
    assert not S.exists()
    manifest = json.loads((A / "manifest.json").read_bytes())
    for name, digest in manifest["files"].items():
        assert review.digest((A / name).read_bytes()) == digest
    assert REPORT.read_bytes() == TMP_REPORT.read_bytes()
    mapping, result = staged()
    assert len(mapping) == 999, len(mapping)
    assert all(name.startswith("docs/superpowers/reports/") for name in mapping)
    S.mkdir()
    shutil.copy2(__file__, S / "finalize-docs.py")
    base = Path("/Users/bytedance/Library/Application Support/Trae CN/ModularData/ai-agent/command-execution")
    for label, cid in (("seal-prepare-tool", "ceb8c0f2ddf20deb05a2961bd4e8afb3"),
                       ("seal-persist-tool", "73b5040b6b9f59d6e38a682931726e45")):
        shutil.copy2(base / cid / "output.log", S / (label + ".log"))
    write(S / "staged-files.json", dict(files=mapping, file_count=len(mapping),
          report_sha256=review.digest(REPORT.read_bytes()),
          manifest_sha256=review.digest((A / "manifest.json").read_bytes()),
          all_payload_and_report_bytes_match=True))
    write(S / "staged-secret-scan.json", dict(**result, started_at=started,
          finished_at=datetime.now(UTC).isoformat(), actual_values_never_output=True,
          command=[review.PY, __file__, "scan"], model_calls=0, model_cost_usd="0",
          http_total="unknown", scope="actual 999 staged core/report files; ZIP members fully scanned",
          subsequent_self_generated_annex="safe metadata; full staged set rescanned externally before commit"))
    entries = {str(p.relative_to(S)): review.digest(p.read_bytes())
               for p in sorted(S.iterdir()) if p.is_file()}
    write(S / "manifest.json", dict(files=entries, file_count=len(entries),
          payload_sha256=review.digest(json.dumps(sorted(entries.items()), ensure_ascii=True,
                                separators=(",", ":")).encode()),
          self_excluded=True, role="implementer staging evidence"))
    print(json.dumps({"scan": result, "report_sha256": review.digest(REPORT.read_bytes()),
                      "annex_files": len(entries) + 1}))


def finalscan():
    mapping, result = staged()
    path = Path("/tmp/m3-task9-leaf-final-staged-scan.json")
    write(path, dict(**{**result, "file_count": result["files"], "files": mapping}, time=datetime.now(UTC).isoformat(),
                    role="external precommit complete staged scan; excluded to avoid audit self-reference",
                    model_calls=0, model_cost_usd="0", http_total="unknown"))
    print(json.dumps({"scan": result, "record": str(path), "sha256": review.digest(path.read_bytes())}))


def refresh():
    shutil.copy2(S / "manifest.json", S / "manifest-v1.json")
    shutil.copy2(S / "finalize-docs.py", S / "finalize-docs-v1.py")
    shutil.copy2(__file__, S / "finalize-docs.py")
    source = Path("/Users/bytedance/Library/Application Support/Trae CN/ModularData/ai-agent/command-execution/604224167ca019b18fe004445d241d4a/output.log")
    shutil.copy2(source, S / "invalid-finalscan-writer.log")
    write(S / "invalid-finalscan-writer.json", {
        "time": datetime.now(UTC).isoformat(),
        "error": "TypeError: dict() got multiple values for keyword argument 'files'",
        "cause": "scan file count and staged path mapping used the same files field",
        "phase": "full scan completed; JSON output construction failed",
        "classification": "evidence writer error; not product failure",
        "correction": "count separately recorded as file_count, files is staged path/hash mapping",
        "old_annex_script_and_manifest_retained": True,
        "model_calls": 0, "model_cost_usd": "0", "http_total": "unknown",
    })
    entries = {str(p.relative_to(S)): review.digest(p.read_bytes())
               for p in sorted(S.iterdir()) if p.is_file() and p.name != "manifest.json"}
    content = dict(files=entries, file_count=len(entries),
                   payload_sha256=review.digest(json.dumps(sorted(entries.items()), ensure_ascii=True,
                                                          separators=(",", ":")).encode()),
                   self_excluded=True, role="implementer staging evidence with original writer failure")
    with (S / "manifest.json").open("w") as out:
        json.dump(content, out, indent=2)
        out.write("\n")
    print(json.dumps({"annex_files": len(entries) + 1, "original_writer_failure_retained": True}))


def postcommit():
    head = review.git(R, "rev-parse", "HEAD").decode().strip()
    parent = review.git(R, "rev-parse", "HEAD^").decode().strip()
    product = json.loads((E / "product-freeze.json").read_bytes())
    assert parent == product["product"]
    assert review.git(R, "status", "--porcelain") == b""
    snap = bootstrap.snapshot()
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    assert snap["primary"] == initial["primary"]
    assert snap["m3"]["source"] == product["source"]
    for key in ("venv", "vite", "vite_temp"):
        assert snap["m3"][key] == initial["m3"][key]
    prepare.verify_blobs(head, product["source"])
    for directory in (A, S):
        manifest = json.loads((directory / "manifest.json").read_bytes())
        for name, digest in manifest["files"].items():
            assert review.digest((directory / name).read_bytes()) == digest
    assert REPORT.read_bytes() == TMP_REPORT.read_bytes()
    all_items = list(snap["m3"]["tracked"].items())
    for offset in range(0, len(all_items), 500):
        prepare.verify_blobs(head, dict(all_items[offset:offset + 500]))
    new_docs = {str(p.relative_to(R)): review.digest(p.read_bytes())
                for directory in (A, S) for p in directory.rglob("*") if p.is_file()}
    new_docs[str(REPORT.relative_to(R))] = review.digest(REPORT.read_bytes())
    staged_record = Path("/tmp/m3-task9-leaf-final-staged-scan.json")
    staged_doc = json.loads(staged_record.read_bytes())
    assert staged_doc["files"] == new_docs
    write(Path("/tmp/m3-task9-leaf-authenticity-fix-freeze.json"), dict(
        time=datetime.now(UTC).isoformat(), docs_review_head=head, parent=parent,
        product=product["product"], product_parent=product["parent"],
        source_count=product["source_count"], source_sha256=product["source_sha256"],
        all_actual_tracked_gitblobs_verified=len(all_items), new_docs_actual_gitblobs=len(new_docs),
        new_docs_files=new_docs, report_sha256=review.digest(REPORT.read_bytes()),
        manifest_sha256=review.digest((A / "manifest.json").read_bytes()),
        payload_sha256=json.loads((A / "manifest.json").read_bytes())["payload_sha256"],
        staging_manifest_sha256=review.digest((S / "manifest.json").read_bytes()),
        final_staged_scan_sha256=review.digest(staged_record.read_bytes()), final_staged_scan=staged_doc,
        protected_snapshot=snap, primary_full_equal=True, source_and_venv_cache_equal=True,
        m3_clean=True, model_calls=0, model_cost_usd="0", http_total="unknown",
        status="implementer done; parent NEWfreeze -> fresh WHOLE SPEC -> new PASS -> fresh WHOLE CODE",
        independent_acceptance=False, push_amend_config_bypass=False,
        report_and_payload_same_byte=True))
    print(json.dumps({"docs_review_head": head, "parent": parent, "product": product["product"],
                      "tracked_gitblobs": len(all_items), "new_docs_gitblobs": len(new_docs),
                      "report_sha256": review.digest(REPORT.read_bytes()), "clean": True}))


{"scan": scan, "finalscan": finalscan, "refresh": refresh, "postcommit": postcommit}[sys.argv[1]]()
