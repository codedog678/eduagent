"""父侧独立复算新冻结及原始证据；不执行或授予 SPEC/CODE 验收。"""

import asyncio
import importlib.metadata
import importlib.util
import json
import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
spec = importlib.util.spec_from_file_location("history", "/tmp/m3-historical-evidence-preflight.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
c, ROOT, PRIMARY = h.c, h.ROOT, h.PRIMARY
A = ROOT / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence"
S = A.parent / "task9-leaf-authenticity-fix-staging-evidence"
REPORT = A.parent / "2026-11-02-m3-task9-leaf-authenticity-fix.md"
OUT = Path("/tmp/m3-task9-leaf-authenticity-parent-verification.json")
HEAD = "9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f"
PRODUCT = "1b8e4b745126c92cfd56f9f021388dd615d98791"
BASE = "855d5c6660343c24df0bef5ad4cf77160e83c566"
SOURCE = "14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813"


def load(path):
    return json.loads(path.read_bytes())


def main():
    assert not OUT.exists()
    started = datetime.now(UTC).isoformat()
    before = h.snapshot(ROOT), h.snapshot(PRIMARY)
    freeze = load(Path("/tmp/m3-task9-leaf-authenticity-fix-freeze.json"))
    assert freeze["docs_review_head"] == HEAD and freeze["product"] == PRODUCT
    assert before[0]["head"] == HEAD and not before[0]["status"] and not before[1]["status"]
    assert c.git(ROOT, "rev-parse", HEAD + "^").decode().strip() == PRODUCT
    assert c.git(ROOT, "rev-parse", PRODUCT + "^").decode().strip() == BASE
    initial = load(A / "initial-snapshot.json")
    product = load(A / "product-freeze.json")
    source = product["source"]
    changed = set(product["changed_paths"])
    assert len(changed) == 5 and changed == c.names(ROOT, "diff", "--name-only", "-z", BASE, PRODUCT)
    assert len(source) == 357 and c.combined(source) == SOURCE
    assert set(source) == c.names(ROOT, "ls-files", "-z", "--", "python", "frontend")
    c.blobs(ROOT, PRODUCT, source)
    c.blobs(ROOT, BASE, initial["m3"]["tracked"])
    assert len(initial["m3"]["tracked"]) == 5492
    allfiles = {
        p: c.sha((ROOT / p).read_bytes())
        for p in sorted(c.names(ROOT, "ls-files", "-z"))
    }
    assert len(allfiles) == 6503
    c.blobs(ROOT, HEAD, allfiles)
    docs = {
        str(p.relative_to(ROOT)): c.sha(p.read_bytes())
        for directory in (A, S) for p in directory.rglob("*") if p.is_file()
    }
    docs[str(REPORT.relative_to(ROOT))] = c.sha(REPORT.read_bytes())
    assert len(docs) == 1009 and docs == freeze["new_docs_files"]
    assert set(docs) == c.names(ROOT, "diff", "--name-only", "-z", PRODUCT, HEAD)
    assert set(allfiles) == set(initial["m3"]["tracked"]) | set(source) | set(docs)
    for path, digest in initial["m3"]["tracked"].items():
        if path not in changed:
            assert allfiles[path] == digest, path
    config_count, secret_values = c.secret_values((ROOT, PRIMARY))
    manifest_bytes = (A / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert c.sha(manifest_bytes) == freeze["manifest_sha256"] == "37449214c2bb58d5c4e4119d2b0bda5915b39368e136d35b5fe6c2d6c0b3dfbf"
    assert len(manifest["files"]) == manifest["file_count"] == 997
    assert manifest["payload_sha256"] == freeze["payload_sha256"] == "c44505192c92ed41c69a6027c4f564af421262ecd6a485f534201d2487e7bb5f"
    archive = c.check_archive(A, manifest, secret_values)
    stage_bytes = (S / "manifest.json").read_bytes()
    assert c.sha(stage_bytes) == freeze["staging_manifest_sha256"]
    staging = c.check_archive(S, json.loads(stage_bytes), secret_values)
    assert len(staging["xml"]) == 0
    for path in set(docs) | changed:
        data = (ROOT / path).read_bytes()
        c.scan_bytes(data, path, secret_values)
        assert not re.search(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b", data), path
    report_bytes = REPORT.read_bytes()
    assert report_bytes == Path("/tmp/m3-task9-leaf-authenticity-fix-result.md").read_bytes()
    assert c.sha(report_bytes) == freeze["report_sha256"] == "6d623c64406c84a7e20e75bdb9e7746fde1bdf16994a149c38c191d5b17fdbdf"
    audit = load(A / "final-verification.json")
    assert len(archive["xml"]) == len(audit["suites"]) == 28
    assert archive["zip_crc_checked"] == len(audit["traces"]) == 84
    assert archive["zip_members_secret_checked"] == 2982
    for name, actual in archive["xml"].items():
        declaration = audit["suites"][name]
        assert all(actual[k] == declaration[k] for k in actual), name
        assert c.sha((A / name).read_bytes()) == declaration["sha256"], name
    for name, count in {
        "final-backend.xml": 1911, "final-api.xml": 362,
        "final-integrity.xml": 131, "final-leaf-minimum.xml": 90,
        "green-new-get.xml": 47, "green-leaf-active.xml": 15,
        "green-minimum.xml": 28, "final-ui.xml": 54,
        "final-visual4.xml": 2, "final-policy-visual2.xml": 2,
    }.items():
        assert archive["xml"][name] == dict(tests=count, passed=count, failure=0, error=0, skip=0), name
    for name, total, failures in (
        ("red-valid-leaf.xml", 9, 7), ("red-valid-active.xml", 6, 5),
        ("red-new-get.xml", 47, 33),
    ):
        assert archive["xml"][name] == dict(tests=total, passed=total-failures, failure=failures, error=0, skip=0), name
    finals = [name for name in archive["xml"] if name.startswith("final-production-")]
    # approval_malformed 是保留的无效场景名尝试；合法对照被错误断言失败。
    failed_attempt = "final-production-approval_malformed.xml"
    assert archive["xml"][failed_attempt]["failure"] == 2
    assert len(finals) == 13
    for name in set(finals) - {failed_attempt}:
        assert archive["xml"][name] == dict(tests=2, passed=2, failure=0, error=0, skip=0), name
    full_cases = list(ET.parse(A / "final-backend.xml").getroot().iter("testcase"))
    api_cases = list(ET.parse(A / "final-api.xml").getroot().iter("testcase"))
    for cases in (full_cases, api_cases):
        assert sum(case.get("classname") == "tests.distributed.test_ops_leaf_authenticity" for case in cases) == 47
    snapshot_sources = {}
    assert len(audit["snapshots"]) == 30
    for name, declaration in audit["snapshots"].items():
        pre = (A / name).read_bytes()
        post = (A / name.replace("-before.json", "-after.json")).read_bytes()
        assert pre == post, name
        assert c.sha(pre) == declaration["before_sha256"] == declaration["after_sha256"]
        state = json.loads(pre)
        assert state["primary"] == initial["primary"], name
        local = state["m3"]
        assert c.combined(local["source"]) == local["source_sha256"]
        assert len(local["source"]) == local["source_count"]
        for key in ("venv", "vite", "vite_temp"):
            assert local[key] == initial["m3"][key], (name, key)
        for path, digest in initial["m3"]["tracked"].items():
            if path not in changed:
                assert local["tracked"][path] == digest, (name, path)
        if name.startswith("final-"):
            assert local["source"] == source, name
        snapshot_sources[name] = local["source_sha256"]
    runtime = load(A / "runtime-final.json")
    assert len(runtime["versions"]) == runtime["installed_count"] == 58
    assert c.metadata(Path("/tmp/eduagent-m3-patched-runtime")) == runtime["before"] == runtime["after"]
    from packaging.requirements import Requirement
    for name, version in runtime["versions"].items():
        assert importlib.metadata.version(name) == version, name
    assert len(runtime["coverage"]) == 44
    assert sum(row["group"] != "repair_floors" for row in runtime["coverage"]) == 39
    for row in runtime["coverage"]:
        requirement = Requirement(row["requirement"])
        if row["active"]:
            assert importlib.metadata.version(requirement.name) in requirement.specifier
    cleanup = load(A / "cleanup-final.json")
    names = {row["db"] for row in cleanup["databases"]}
    assert len(names) == cleanup["database_count"] == 26
    assert all(row["drop_exit"] == 0 and row["db"].startswith("m3_t9_leaf8551_") for row in cleanup["databases"])
    shared = cleanup["shared_pg"]
    db_check = asyncio.run(c.check_databases(shared["port"], names, shared["data_dir"], shared["pid"]))
    ports = c.closed_ports((62584, 62585, 62586))
    assert not cleanup["keys_creation_complete"] and not cleanup["flush_or_prefix_delete"]
    assert cleanup["redis_verified_config"]["save"] == ""
    assert cleanup["redis_verified_config"]["appendonly"] == "no"
    assert cleanup["shutdown_command"] == "SHUTDOWN NOSAVE"
    c.protected(PRIMARY, initial["primary"])
    c.protected(ROOT, freeze["protected_snapshot"]["m3"])
    assert (h.snapshot(ROOT), h.snapshot(PRIMARY)) == before
    result = dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(),
        role="parent independently recomputed provenance; not SPEC/CODE acceptance",
        head=HEAD, product=PRODUCT, base=BASE, source_count=357, source_sha256=SOURCE,
        current_actual_gitblobs=6503, historical_actual_gitblobs=5492, new_docs_gitblobs=1009,
        changed_paths=sorted(changed), archive=archive, staging_archive=staging,
        manifest_sha256=c.sha(manifest_bytes), report_sha256=c.sha(report_bytes),
        complete_byte_equal_snapshot_pairs=30, snapshot_source_sha256=snapshot_sources,
        final_backend=1911, final_api=362, final_ui=54, final_integrity=131,
        final_valid_production_cases=24, retained_invalid_production_failure_cases=2,
        new_get_tests_in_full_and_api=47, runtime_distributions=58,
        project_dev_build_requirements_constraints=39, extra_repair_floors=5,
        vulnerability_scan_executed=False, exact_database_check=db_check, closed_ports=ports,
        secret_scan=dict(config_files=config_count, distinct_actual_values=len(secret_values), matches=0),
        primary_and_review_head_index_venv_cache_unchanged=True,
        browser_bytes_and_actual_visual_verification="separate check pending",
        model_requests=0, model_cost_usd="0", all_http="unknown",
        historical_and_failed_attempts_preserved=True,
        normal_hook_timeout_is_not_full_scan_pass=True,
        auxiliary_invalid_reads=[dict(
            shell_id="fbbb1af256eff3072feebd5235e29a27", exit=1,
            reason="assumed final_checks.py; actual archived verifier is final_evidence.py",
            product_failure=False,
        )],
    )
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("archive", "staging_archive", "snapshot_source_sha256")}, indent=2))


if __name__ == "__main__":
    main()
