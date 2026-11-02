"""父侧原字节归档独立规格PASS；不替代独立CODE或Task9最终验收。"""
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
RAW = Path("/tmp/m3-task9-wholespec-90d3cbd2-0290-48f8-aba7-530548519b0e")
DEST = ROOT / "docs/superpowers/reports/task9-minimum-spec-pass-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-minimum-spec-pass.md"
HEAD = "a6500f5a4fb8ce1494742735655841230b6124fe"
SOURCE = "7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc"


def read(name):
    return json.loads((RAW / name).read_bytes())


def validate_protected(state, m3_index=True):
    c.protected(PRIMARY, state["primary"])
    c.worktree(ROOT, state["m3"]["tracked"])
    c.blobs(ROOT, HEAD, state["m3"]["tracked"])
    if m3_index:
        c.protected(ROOT, state["m3"])
    else:
        for key, path in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                          ("vite_temp", "frontend/node_modules/.vite-temp")):
            assert c.metadata(ROOT / path) == state["m3"][key], key


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-head")
    parser.add_argument("--finalize-visual", action="store_true")
    args = parser.parse_args()
    state = read("initial-snapshot.json")
    if args.finalize_visual:
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        proof["retained_files"]["parent-visual-inspections.md"] = c.sha(
            (DEST / "parent-visual-inspections.md").read_bytes())
        proof["parent_actual_visual_inspections"] = 4
        # 保留本归档脚本的最终版本，清单不哈希自身proof。
        shutil.copyfile(__file__, DEST / "parent-retain.py")
        proof["retained_files"]["parent-retain.py"] = c.sha((DEST / "parent-retain.py").read_bytes())
        configs, secrets = c.secret_values((ROOT, PRIMARY))
        for name, digest in proof["retained_files"].items():
            data = (DEST / name).read_bytes()
            assert c.sha(data) == digest
            c.scan_bytes(data, name, secrets)
        (DEST / "parent-retention.json").write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps(dict(parent_actual_visual_inspections=4, retained_files=len(proof["retained_files"]),
                              actual_secret_values_checked=len(secrets), matches=0), indent=2))
        return
    if args.verify_head:
        tip = args.verify_head
        assert c.git(ROOT, "rev-parse", "HEAD").decode().strip() == tip
        assert c.git(ROOT, "rev-parse", "HEAD^").decode().strip() == HEAD
        assert not c.git(ROOT, "status", "--porcelain")
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        mapping = dict(state["m3"]["tracked"])
        prefix = str(DEST.relative_to(ROOT)) + "/"
        mapping.update({prefix + p: h for p, h in proof["retained_files"].items()})
        mapping[prefix + "parent-retention.json"] = c.sha((DEST / "parent-retention.json").read_bytes())
        mapping[str(REPORT.relative_to(ROOT))] = proof["report_sha256"]
        assert set(mapping) == c.names(ROOT, "ls-files", "-z")
        c.worktree(ROOT, mapping)
        c.blobs(ROOT, tip, mapping)
        changed = c.names(ROOT, "diff", "--name-only", "-z", HEAD, tip)
        assert changed == set(mapping) - set(state["m3"]["tracked"])
        assert not c.git(ROOT, "diff", HEAD, tip, "--", "python", "frontend", "tools")
        validate_protected(state, m3_index=False)
        result = dict(head=tip, parent=HEAD, all_gitblobs_exact=len(mapping),
                      changed_docs_paths=len(changed), source_count=355, source_sha256=SOURCE,
                      primary_unchanged=True, product_unchanged=True,
                      role="parent postcommit provenance; not CODE acceptance")
        print(json.dumps(result, indent=2))
        return

    assert not DEST.exists() and not REPORT.exists()
    assert state["m3"]["head"] == HEAD
    validate_protected(state)
    assert len(state["m3"]["tracked"]) == 4419
    assert len(state["primary"]["tracked"]) == 1110
    source = state["m3"]["source"]
    assert len(source) == 355 and c.combined(source) == SOURCE
    assert set(source) == c.names(ROOT, "ls-files", "-z", "--", "python", "frontend")
    mb = (RAW / "retained-manifest.json").read_bytes()
    manifest = json.loads(mb)
    assert manifest["head"] == HEAD
    assert manifest["file_count"] == len(manifest["files"]) == 462
    assert manifest["payload_sha256"] == "ae71838146eb68041589efe58c5889c7425c0c83140bd05c02b15f61c085bd2e"
    report = Path("/tmp/m3-task9-minimum-spec-result.md").read_bytes()
    assert report == (RAW / "review-result.md").read_bytes()
    assert c.sha(report) == manifest["report_sha256"] == "80ccd67d9b2a80673475595c7b479a05fb00fc4e8a5cc58f8c342126338887cd"
    configs, secrets = c.secret_values((ROOT, PRIMARY))
    checked = c.check_archive(RAW, manifest, secrets)
    assert len(checked["xml"]) == 13
    assert checked["zip_crc_checked"] == 72 and checked["zip_members_secret_checked"] == 2615
    audit = read("independent-execution-audit.json")
    assert set(audit["xml"]) == set(checked["xml"])
    for name, actual in checked["xml"].items():
        expected = audit["xml"][name]
        assert actual["tests"] == expected["tests"]
        assert actual["failure"] == expected["failures"] == 0
        assert actual["error"] == expected["errors"] == 0
        assert actual["skip"] == expected["skips"] == 0
        assert c.sha((RAW / name).read_bytes()) == expected["sha256"]
    for name, count in (("full-final.xml", 1864), ("api-final.xml", 315),
                        ("integrity-complete.xml", 111), ("minimum.xml", 28),
                        ("ui54.xml", 54), ("ui-visual4.xml", 4)):
        assert checked["xml"][name]["tests"] == count
    assert all(v["tests"] == 2 for k, v in checked["xml"].items() if k.startswith("prod-final-"))
    cases = list(ET.parse(RAW / "full-final.xml").getroot().iter("testcase"))
    assert sum(x.get("classname") == "tests.distributed.test_ops_minimum_evidence" for x in cases) == 24
    assert len(audit["commands"]) == len(audit["pairs"]) == 14
    for name, command in audit["commands"].items():
        assert read(name) == command and command["exit"] == 0
        # 每条命令保留原UTC与数组，不从suite时间拼造wall clock。
        assert isinstance(command, dict) and len(command) >= 5
    for label, pair in audit["pairs"].items():
        before = (RAW / pair["before"]).read_bytes()
        after = (RAW / pair["after"]).read_bytes()
        assert before == after and c.sha(before) == pair["sha256"], label
        phase = json.loads(before)
        assert {k: phase[k] for k in state} == state, label
        assert set(phase) == set(state) | {"execution"}
        assert phase["execution"] == {
            "root": str(ROOT), "mode": "FINAL_SOURCE",
            "new_complete_get_regression": "python/tests/distributed/test_ops_minimum_evidence.py",
        }
    for label in ("evidence-audit", "cleanup"):
        before = (RAW / (label + "-before.json")).read_bytes()
        assert before == (RAW / (label + "-after.json")).read_bytes()
        phase = json.loads(before)
        assert {k: phase[k] for k in state} == state, label
    assert read("final-source-gitblob.json")["snapshot"] == state
    assert len(audit["traces"]) == 72
    for name, declared in audit["traces"].items():
        with zipfile.ZipFile(RAW / name) as trace:
            members = {p.filename for p in trace.infolist() if not p.is_dir()}
            assert members == set(declared["members"]), name
            for member in members:
                content = trace.read(member)
                row = declared["members"][member]
                assert c.sha(content) == row["sha256"] and len(content) == row["bytes"]
                if member.endswith((".trace", ".network")):
                    assert len([json.loads(x) for x in content.splitlines() if x.strip()]) == row["parsed_events"]
    page_gets = trace_gets = assets_count = 0
    assert len(audit["production"]) == 14
    for name, declared in audit["production"].items():
        raw = read(name)
        assert all(x["method"] == "GET" for x in raw["requests"])
        assert not raw["errors"] and raw["overflow"] <= 1
        label, viewport = Path(name).stem.removeprefix("production-").rsplit("-", 1)
        traces = [p for p in (RAW / (label + "-output")).rglob("trace.zip") if viewport in str(p.parent)]
        assert len(traces) == 1
        found, gets = {}, 0
        with zipfile.ZipFile(traces[0]) as trace:
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
                        continue
                    content = trace.read(response["content"]["_file"])
                    relative = c.safe_relative(urlparse(url).path.lstrip("/"))
                    assert content == (RAW / "retained-http-dist" / relative).read_bytes()
                    assert c.sha(content) == raw["hashes"][url]
                    found[url] = dict(bytes=len(content), sha256=c.sha(content))
        assert found == declared["exact_asset_bytes"] and len(found) == 3
        assert gets == declared["trace_gets"]
        assert len(raw["requests"]) == declared["page_gets"]
        page_gets += len(raw["requests"])
        trace_gets += gets
        assets_count += len(found)
    assert (page_gets, trace_gets, assets_count) == (84, 142, 42)
    for row in audit["actual_visual_inspections"]:
        assert c.sha((RAW / row["path"]).read_bytes()) == row["sha256"]
    cleanup = read("cleanup-independent.json")
    pg = cleanup["database_check"]["shared_pg_preserved_identity"]
    names = cleanup["database_check"]["exact_names"]
    assert len(names) == 41 and len(cleanup["own_databases"]) == 11
    db_check = asyncio.run(c.check_databases(pg["port"], names, pg["data_dir"], pg["pid"]))
    ports = c.closed_ports(cleanup["ports_closed"])
    assert cleanup["identity_checked"] and cleanup["no_flush_or_prefix_delete"]
    validate_protected(state)
    DEST.mkdir()
    for name in manifest["files"]:
        target = DEST / c.safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAW / name, target)
    shutil.copyfile(RAW / "retained-manifest.json", DEST / "retained-manifest.json")
    shutil.copyfile(__file__, DEST / "parent-retain.py")
    shutil.copyfile("/tmp/m3-parent-evidence-checks.py", DEST / "parent-evidence-checks.py")
    shutil.copyfile("/tmp/m3-task9-minimum-spec-pass-parent-attempts.md", DEST / "parent-invalid-attempts.md")
    for name in ("m3-task9-minimum-parent-verification.json",
                 "m3-task9-minimum-parent-browser-verification.json",
                 "m3-task9-minimum-parent-postcommit.json"):
        shutil.copyfile(Path("/tmp") / name, DEST / name)
    REPORT.write_bytes(report)
    retained = {str(p.relative_to(DEST)): c.sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    for name in retained:
        c.scan_bytes((DEST / name).read_bytes(), name, secrets)
    proof = dict(verified_at=datetime.now(UTC).isoformat(),
                 role="parent byte-exact SPEC PASS provenance; not CODE/Task9 acceptance",
                 head=HEAD, source_count=355, source_sha256=SOURCE,
                 preexisting_gitblobs_verified=4419, primary_gitblobs_verified=1110,
                 raw_manifest_sha256=c.sha(mb), raw_payload_sha256=manifest["payload_sha256"],
                 raw_payload_count=462, report_sha256=c.sha(report), retained_files=retained,
                 archive_check=checked, complete_equal_snapshot_pairs=16,
                 new_minimum_tests_in_full=24, exact_database_check=db_check,
                 owned_ports_closed=ports, page_gets=84, trace_gets=142, actual_asset_byte_checks=42,
                 reviewer_actual_visual_inspections=18, parent_actual_visual_inspections="separate file",
                 secret_scan=dict(local_config_files=configs, distinct_values=len(secrets), matches=0),
                 primary_index_venv_cache_unchanged=True, invalid_scan_attempt_preserved=True,
                 raw_whitespace_preserved=True, new_model_requests=0, new_cost_usd="0",
                 global_http_total="unknown", normal_hook_scan_timeout_not_complete=True)
    (DEST / "parent-retention.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({k: v for k, v in proof.items() if k not in ("retained_files", "archive_check")}, indent=2))


if __name__ == "__main__":
    main()
