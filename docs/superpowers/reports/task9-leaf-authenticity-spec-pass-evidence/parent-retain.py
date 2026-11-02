"""父侧复算、同字节留档及提交后核验独立 SPEC；不授予 CODE 或 Task9。"""

import argparse
import asyncio
import importlib.util
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

spec = importlib.util.spec_from_file_location("checks", "/tmp/m3-parent-evidence-checks.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
RAW = Path("/tmp/m3-task9-leaf-spec-9efac2fb-3201-4499-9be6-a10cde0023e7")
DEST = ROOT / "docs/superpowers/reports/task9-leaf-authenticity-spec-pass-evidence"
REPORT = DEST.parent / "2026-11-02-m3-task9-leaf-authenticity-spec-pass.md"
HEAD = "9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f"
PRODUCT = "1b8e4b745126c92cfd56f9f021388dd615d98791"
SOURCE = "14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813"


def read(name):
    return json.loads((RAW / name).read_bytes())


def protected(state, after_archive=False):
    c.protected(PRIMARY, state["primary"])
    c.worktree(ROOT, state["m3"]["tracked"])
    if not after_archive:
        c.protected(ROOT, state["m3"])
    else:
        for key, path in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                          ("vite_temp", "frontend/node_modules/.vite-temp")):
            assert c.metadata(ROOT / path) == state["m3"][key]
    assert c.metadata(Path("/tmp/eduagent-m3-patched-runtime")) == state["m3"]["runtime"]
    for root, key in ((ROOT, "m3"), (PRIMARY, "primary")):
        for path, mtime in state[key]["source_metadata"].items():
            assert (root / path).stat().st_mtime_ns == mtime, (key, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-head")
    args = parser.parse_args()
    state = read("initial-snapshot.json")
    if args.verify_head:
        tip = args.verify_head
        assert c.git(ROOT, "rev-parse", "HEAD").decode().strip() == tip
        assert c.git(ROOT, "rev-parse", tip + "^").decode().strip() == HEAD
        assert not c.git(ROOT, "status", "--porcelain")
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        prefix = str(DEST.relative_to(ROOT)) + "/"
        mapping = dict(state["m3"]["tracked"])
        mapping.update({prefix + p: digest for p, digest in proof["retained_files"].items()})
        mapping[prefix + "parent-retention.json"] = c.sha((DEST / "parent-retention.json").read_bytes())
        mapping[str(REPORT.relative_to(ROOT))] = proof["report_sha256"]
        assert set(mapping) == c.names(ROOT, "ls-files", "-z")
        c.worktree(ROOT, mapping)
        c.blobs(ROOT, tip, mapping)
        assert c.names(ROOT, "diff", "--name-only", "-z", HEAD, tip) == set(mapping) - set(state["m3"]["tracked"])
        assert not c.git(ROOT, "diff", HEAD, tip, "--", "python", "frontend", "tools")
        protected(state, after_archive=True)
        result = dict(
            verified_at=datetime.now(UTC).isoformat(), head=tip, parent=HEAD, product=PRODUCT,
            actual_tracked_gitblobs=len(mapping), new_docs_paths=len(mapping)-len(state["m3"]["tracked"]),
            source_count=357, source_sha256=SOURCE, raw_manifest_sha256=proof["raw_manifest_sha256"],
            raw_payload_sha256=proof["raw_payload_sha256"], report_sha256=proof["report_sha256"],
            primary_unchanged=True, source_runtime_venv_cache_unchanged=True,
            role="parent SPEC PASS postcommit provenance; not CODE or final Task9 acceptance",
        )
        out = Path("/tmp/m3-task9-leaf-spec-pass-postcommit.json")
        assert not out.exists()
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    assert not DEST.exists() and not REPORT.exists()
    assert state["m3"]["head"] == HEAD and len(state["m3"]["tracked"]) == 6503
    protected(state)
    source = state["m3"]["source"]
    assert len(source) == 357 and c.combined(source) == SOURCE
    assert source.keys() == c.names(ROOT, "ls-files", "-z", "--", "python", "frontend")
    c.blobs(ROOT, HEAD, state["m3"]["tracked"])
    c.blobs(ROOT, PRODUCT, source)
    c.blobs(PRIMARY, state["primary"]["head"], state["primary"]["tracked"])
    seal = json.loads(Path("/tmp/m3-task9-leaf-authenticity-spec-seal.json").read_bytes())
    mb = (RAW / "manifest.json").read_bytes()
    manifest = json.loads(mb)
    assert c.sha(mb) == seal["manifest_sha256"] == "75a133cbc9f589c7ca0d1565fe6dd582d1691962234fdd928caca257f2fcfd99"
    assert manifest["payload_count"] == len(manifest["files"]) == 781
    assert manifest["payload_sha256"] == seal["payload_sha256"] == "a35cfc82487b2da96f18446227d1ea79ede8a7b2e70b787e0bd9c692c91db70c"
    report = Path("/tmp/m3-task9-leaf-authenticity-spec-result.md").read_bytes()
    assert report == (RAW / "review-result.md").read_bytes()
    assert c.sha(report) == seal["report_sha256"] == "542fd8da3e1b25a77794f48ef39f7cfae1e998cb0dcb2ef90b0dca7abf4cb081"
    configs, secrets = c.secret_values((ROOT, PRIMARY))
    checked = c.check_archive(RAW, manifest, secrets)
    audit = read("execution-final-audit.json")
    matrix = read("verification-matrix.json")
    assert len(checked["xml"]) == len(audit["suites"]) == 21
    assert checked["zip_crc_checked"] == 82 and checked["zip_members_secret_checked"] == 2937
    for name, counts in checked["xml"].items():
        declared = audit["suites"][name]
        assert all(counts[k] == declared[k] for k in counts), name
        assert c.sha((RAW / name).read_bytes()) == declared["sha256"]
        cases = list(ET.parse(RAW / name).getroot().iter("testcase"))
        assert len(cases) == len(declared["testcases"])
        for case, item in zip(cases, declared["testcases"]):
            assert (case.get("classname") or "") == item["classname"]
            assert case.get("name") == item["name"]
            assert case.get("time") == item["seconds"]
            outcome = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
            assert item["outcome"] == outcome, (name, item)
        assert matrix["suites"][name] == declared, name
    for name, count in {
        "spec-full.xml": 1911, "spec-api.xml": 362, "spec-integrity.xml": 131,
        "spec-leaf-minimum.xml": 90, "spec-ui.xml": 54,
        "spec-visual.xml": 4, "spec-boundary-v3.xml": 9,
    }.items():
        assert checked["xml"][name] == dict(tests=count, passed=count, failure=0, error=0, skip=0), name
    for name in ("spec-boundary.xml", "spec-boundary-v2.xml"):
        assert checked["xml"][name] == dict(tests=9, passed=8, failure=1, error=0, skip=0), name
    production_xml = [name for name in checked["xml"] if name.startswith("spec-production-")]
    assert len(production_xml) == 12
    for name in production_xml:
        assert checked["xml"][name] == dict(tests=2, passed=2, failure=0, error=0, skip=0), name
    for name in ("spec-full.xml", "spec-api.xml"):
        cases = list(ET.parse(RAW / name).getroot().iter("testcase"))
        assert sum(case.get("classname") == "tests.distributed.test_ops_leaf_authenticity" for case in cases) == 47
    assert set(matrix["changed_source_paths"]) == c.names(ROOT, "diff", "--name-only", "-z", manifest["whole_base"], HEAD, "--", "python", "frontend")
    assert len(matrix["changed_source_paths"]) == 21
    pairs = audit["complete_byte_equal_pairs"]
    assert len(pairs) == 22
    for name, pair in pairs.items():
        before = (RAW / name).read_bytes()
        after = (RAW / name.replace("-before.json", "-after.json")).read_bytes()
        assert before == after and c.sha(before) == pair["before_sha256"] == pair["after_sha256"], name
        phase = json.loads(before)
        assert {key: phase[key] for key in state} == state, name
    assert (RAW / "initial-snapshot.json").read_bytes() == (RAW / "final-protected-snapshot.json").read_bytes()
    commands = read("command-ledger-final.json")["commands"]
    for name, declaration in commands.items():
        if ":" in name:
            filename, field = name.split(":", 1)
            raw = read(filename)[field]
            assert raw == declaration, name
            rows = raw if isinstance(raw, list) else [raw]
        else:
            raw = read(name)
            assert raw == declaration["raw"], name
            assert c.sha((RAW / name).read_bytes()) == declaration["raw_sha256"]
            rows = [raw]
        for row in rows:
            if "command" in row:
                assert isinstance(row["command"], list)
            if "started_at" in row and "finished_at" in row:
                assert datetime.fromisoformat(row["finished_at"]) >= datetime.fromisoformat(row["started_at"])
    assets_count = network_gets = 0
    for name, declared in audit["traces"].items():
        assets, bodies, gets = [], [], 0
        with zipfile.ZipFile(RAW / name) as trace:
            assert trace.testzip() is None
            members = set(trace.namelist())
            assert members == set(declared["members"]), name
            for member in trace.infolist():
                row = declared["members"][member.filename]
                content = trace.read(member)
                assert row["bytes"] == len(content) and row["sha256"] == c.sha(content)
                assert row["crc"] == member.CRC and row["directory"] == member.is_dir()
                if not member.filename.endswith((".network", ".trace")):
                    continue
                events = [json.loads(line) for line in content.splitlines() if line.strip()]
                if member.filename.endswith(".network"):
                    for event in events:
                        snap = event.get("snapshot", {})
                        req, resp = snap.get("request", {}), snap.get("response", {})
                        if not req:
                            continue
                        gets += int(req["method"] == "GET")
                        if not declared["production"]:
                            continue
                        assert req["method"] == "GET", name
                        url = req["url"]
                        resource = resp.get("content", {}).get("_file") or resp.get("content", {}).get("_sha1")
                        if not resource:
                            continue
                        resource = resource if resource.startswith("resources/") else "resources/" + resource
                        actual = trace.read(resource)
                        if "/assets/" in url:
                            relative = c.safe_relative(urlparse(url).path.lstrip("/"))
                            assert resp["status"] == 200
                            assert actual == (RAW / "frontend/dist" / relative).read_bytes()
                            assets.append(dict(url=url, bytes=len(actual), sha256=c.sha(actual), resource=resource))
                        if "/ops/policies/deployments/" in url and resp["status"] == 200:
                            bodies.append(json.loads(actual))
            assert assets == declared["assets"], name
            assert bodies == declared["detail_bodies"], name
            assert gets == declared["network_gets"], name
        assets_count += len(assets)
        network_gets += gets if declared["production"] else 0
    assert assets_count == 96 and network_gets == 242
    page_gets = explicit_gets = mobile_scroll = 0
    for name, declaration in audit["productions"].items():
        raw = read(name)
        trace = audit["traces"][declaration["trace"]]
        assert raw["body"] in trace["detail_bodies"]
        assert raw["errors"] == declaration["errors"] == []
        assert raw["overflow"] == declaration["overflow"] == 0
        assert all(item["method"] == "GET" for item in raw["requests"])
        assert len(raw["requests"]) == declaration["page_gets"] == 6
        assert raw["scrollBefore"] == declaration["scroll_before"]
        assert raw["scrollAfter"] == declaration["scroll_after"]
        if declaration["viewport"] == "mobile":
            assert raw["scrollAfter"][0]["left"] > raw["scrollBefore"][0]["left"]
            mobile_scroll += 1
        for asset in raw["assetEvidence"]:
            assert asset["status"] == 200
            assert any(item["url"] == asset["url"] and item["sha256"] == asset["sha256"]
                       and item["bytes"] == asset["bytes"] for item in trace["assets"])
        page_gets += len(raw["requests"])
        explicit_gets += declaration["explicit_gets"]
    assert (page_gets, explicit_gets, mobile_scroll) == (144, 96, 12)
    cleanup = read("spec-cleanup-final.json")
    names = list(cleanup["exact_database_records"])
    shared = cleanup["shared_pg"]
    assert len(names) == 19
    db_check = asyncio.run(c.check_databases(shared["port"], names, shared["data_dir"], shared["pid"]))
    ports = c.closed_ports(cleanup["closed_ports"])
    assert cleanup["shutdown_command"] == "SHUTDOWN NOSAVE" and cleanup["shutdown_exit"] == 0
    assert cleanup["flush_or_prefix_delete"] is False
    visual = read("spec-scope-corroboration.json")["independently_viewed_images"]
    for name, digest in visual.items():
        assert c.sha((RAW / name).read_bytes()) == digest
    protected(state)
    DEST.mkdir()
    for name in manifest["files"]:
        target = DEST / c.safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAW / name, target)
    shutil.copyfile(RAW / "manifest.json", DEST / "manifest.json")
    extras = {
        Path(__file__): "parent-retain.py",
        Path("/tmp/m3-parent-evidence-checks.py"): "parent-evidence-checks.py",
        Path("/tmp/m3-task9-leaf-authenticity-spec-seal.json"): "reviewer-seal.json",
        Path("/tmp/m3-task9-leaf-spec-parent-notes.md"): "parent-locator-and-visual-notes.md",
        Path("/tmp/m3-task9-leaf-authenticity-parent-verify.py"): "parent-implementation-verify.py",
        Path("/tmp/m3-task9-leaf-authenticity-parent-verification.json"): "parent-implementation-verification.json",
        Path("/tmp/m3-task9-leaf-authenticity-parent-browser-check.py"): "parent-implementation-browser-check.py",
        Path("/tmp/m3-task9-leaf-authenticity-parent-browser-verification.json"): "parent-implementation-browser-verification.json",
        Path("/tmp/m3-task9-leaf-authenticity-parent-proof-handoff.md"): "parent-implementation-proof-handoff.md",
    }
    for path, name in extras.items():
        shutil.copyfile(path, DEST / name)
    REPORT.write_bytes(report)
    retained = {str(p.relative_to(DEST)): c.sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    for name in retained:
        c.scan_bytes((DEST / name).read_bytes(), name, secrets)
    proof = dict(
        verified_at=datetime.now(UTC).isoformat(),
        role="parent independent SPEC PASS provenance; not CODE or Task9 acceptance",
        head=HEAD, product=PRODUCT, source_count=357, source_sha256=SOURCE,
        raw_manifest_sha256=c.sha(mb), raw_payload_sha256=manifest["payload_sha256"],
        raw_payload_count=781, report_sha256=c.sha(report), retained_files=retained,
        archive_check=checked, complete_equal_snapshot_pairs=22,
        existing_actual_gitblobs=6503, primary_actual_gitblobs=1110,
        new_leaf_tests_in_full_and_api=47, actual_asset_response_bodies=96,
        production_network_gets=242, page_gets=144, explicit_gets=96, mobile_scroll_records=12,
        reviewer_actual_visual_images=8, parent_actual_visual_images=4,
        exact_database_check=db_check, owned_ports_closed=ports,
        secret_scan=dict(config_files=configs, distinct_actual_values=len(secrets), matches=0),
        original_report_unchanged=True, locator_corrections="parent-locator-and-visual-notes.md",
        preserved_auxiliary_failure_suites=2, raw_whitespace_preserved=True,
        source_index_mtime_runtime_venv_cache_protected=True,
        model_requests=0, actual_cost_usd="0", global_http="unknown", overlap_not_summed=True,
        normal_hook_timeout_not_complete_scan=True,
    )
    (DEST / "parent-retention.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({k: v for k, v in proof.items() if k not in ("retained_files", "archive_check")}, indent=2))


if __name__ == "__main__":
    main()
