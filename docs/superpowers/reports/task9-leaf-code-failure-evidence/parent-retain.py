"""原字节保留独立CODE叶子真实性FAIL；不赋予Task9验收。"""
import asyncio
import importlib.util
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

spec = importlib.util.spec_from_file_location("checks", "/tmp/m3-parent-evidence-checks.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
RAW = Path("/tmp/m3-task9-wholecode-40baa8dc-0414-46d1-b816-90149468b042")
DEST = ROOT / "docs/superpowers/reports/task9-leaf-code-failure-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-leaf-code-failure.md"
HEAD = "c52aaababba238ec26282f8c560c8f565a60a09e"
SOURCE = "7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc"


def read(name):
    return json.loads((RAW / name).read_bytes())


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-head")
    args = parser.parse_args()
    initial = read("initial-snapshot.json")
    if args.verify_head:
        tip = args.verify_head
        assert c.git(ROOT, "rev-parse", "HEAD").decode().strip() == tip
        assert c.git(ROOT, "rev-parse", "HEAD^").decode().strip() == HEAD
        assert not c.git(ROOT, "status", "--porcelain")
        proof = json.loads((DEST / "parent-retention.json").read_bytes())
        prefix = str(DEST.relative_to(ROOT)) + "/"
        added = {prefix + p: h for p, h in proof["retained_files"].items()}
        added[prefix + "parent-retention.json"] = c.sha((DEST / "parent-retention.json").read_bytes())
        added[str(REPORT.relative_to(ROOT))] = proof["report_sha256"]
        mapping = {**initial["m3"]["tracked"], **added}
        assert set(mapping) == c.names(ROOT, "ls-files", "-z")
        assert c.names(ROOT, "diff", "--name-only", "-z", HEAD, tip) == set(added)
        c.worktree(ROOT, mapping)
        c.blobs(ROOT, tip, mapping)
        c.protected(PRIMARY, initial["primary"])
        for key, path in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                          ("vite_temp", "frontend/node_modules/.vite-temp")):
            assert c.metadata(ROOT / path) == initial["m3"][key]
        print(json.dumps(dict(head=tip, parent=HEAD, all_actual_gitblobs_exact=len(mapping),
                              added_docs_paths=len(added), source_count=355, source_sha256=SOURCE,
                              primary_unchanged=True, product_unchanged=True,
                              verdict_retained="WHOLECODEFAIL"), indent=2))
        return
    assert not DEST.exists() and not REPORT.exists()
    c.protected(ROOT, initial["m3"])
    c.protected(PRIMARY, initial["primary"])
    assert initial["m3"]["head"] == HEAD and len(initial["m3"]["tracked"]) == 4891
    source = initial["m3"]["source"]
    assert len(source) == 355 and c.combined(source) == SOURCE
    assert set(source) == c.names(ROOT, "ls-files", "-z", "--", "python", "frontend")
    mb = (RAW / "retained-manifest.json").read_bytes()
    manifest = json.loads(mb)
    assert c.sha(mb) == "1da8278d77d5b683e4b6c08211a0c49d610932a553971c33a24dad8d4c6ba92a"
    assert manifest["verdict"] == "WHOLECODEFAIL" and manifest["head"] == HEAD
    assert manifest["file_count"] == len(manifest["files"]) == 595
    report = Path("/tmp/m3-task9-minimum-code-result.md").read_bytes()
    assert report == (RAW / "review-result.md").read_bytes()
    assert c.sha(report) == manifest["report_sha256"]
    configs, secrets = c.secret_values((ROOT, PRIMARY))
    archive = c.check_archive(RAW, manifest, secrets)
    assert len(archive["xml"]) == 16
    assert archive["zip_crc_checked"] == 126 and archive["zip_members_secret_checked"] == 4457
    audit = read("independent-execution-audit.json")
    assert set(audit["xml"]) == set(archive["xml"])
    for name, counts in archive["xml"].items():
        declared = audit["xml"][name]
        assert counts["tests"] == declared["tests"]
        assert counts["failure"] == declared["failures"]
        assert counts["error"] == declared["errors"] and counts["skip"] == declared["skips"] == 0
        assert c.sha((RAW / name).read_bytes()) == declared["sha256"]
    assert archive["xml"]["fresh-leaf.xml"] == dict(tests=9, passed=2, failure=7, error=0, skip=0)
    assert archive["xml"]["fresh-active.xml"] == dict(tests=6, passed=1, failure=5, error=0, skip=0)
    assert archive["xml"]["ui54.xml"] == dict(tests=54, passed=51, failure=1, error=2, skip=0)
    for name, count in (("full-final.xml", 1864), ("api-final.xml", 315),
                        ("integrity-complete.xml", 111), ("minimum.xml", 28),
                        ("ui54-recheck.xml", 54), ("ui-visual4.xml", 4)):
        assert archive["xml"][name] == dict(tests=count, passed=count, failure=0, error=0, skip=0)
    assert all(v == dict(tests=2, passed=2, failure=0, error=0, skip=0)
               for k, v in archive["xml"].items() if k.startswith("prod-final-"))
    def sources(dto):
        return {r["gate_type"]: r for r in dto["gate_receipts"] if r["health_source"]}
    attacks = {}
    for path in sorted((RAW / "fresh-leaf").glob("*.json")) + sorted((RAW / "fresh-active").glob("*.json")):
        row = json.loads(path.read_bytes())
        if "poison" not in row:
            continue
        valid = row["poison"] == "valid"
        assert row["authority_accepts"] == valid
        gate = "shadow_health" if row["state"] == "shadow" else "canary_health"
        local = sources(row["local"])
        assert local[gate]["status"] == "passed" and local[gate]["health_source"]["relation"] == "local"
        if row["state"] == "canary":
            active = sources(row["active"])
            assert set(active) == {"canary_health", "shadow_health"}
            assert all(v["health_source"]["relation"] == "consumed_chain" for v in active.values())
        attacks[str(path.relative_to(RAW))] = dict(poison=row["poison"], state=row["state"],
                                                  authority_accepts=valid, ops_local_passed=True)
    assert len(attacks) == 15
    assert sum(not r["authority_accepts"] for r in attacks.values()) == 12
    assert len(audit["commands"]) == len(audit["pairs"]) == 17
    for name, command in audit["commands"].items():
        assert read(name) == command
        assert command["exit"] in (0, 1)
    for label, pair in audit["pairs"].items():
        before = (RAW / pair["before"]).read_bytes()
        after = (RAW / pair["after"]).read_bytes()
        assert before == after and c.sha(before) == pair["sha256"]
        state = json.loads(before)
        assert {k: state[k] for k in initial} == initial, label
    for label in ("evidence-audit-final", "cleanup"):
        before = (RAW / (label + "-before.json")).read_bytes()
        assert before == (RAW / (label + "-after.json")).read_bytes()
        state = json.loads(before)
        assert {k: state[k] for k in initial} == initial, label
    assert read("final-source-gitblob.json")["snapshot"] == initial
    for name, declaration in audit["traces"].items():
        with zipfile.ZipFile(RAW / name) as trace:
            assert {p.filename for p in trace.infolist() if not p.is_dir()} == set(declaration["members"])
            for name, row in declaration["members"].items():
                content = trace.read(name)
                assert c.sha(content) == row["sha256"] and len(content) == row["bytes"]
                if name.endswith((".trace", ".network")):
                    assert len([json.loads(x) for x in content.splitlines() if x.strip()]) == row["parsed_events"]
    get_count = page_gets = assets_count = 0
    for name, declared in audit["production"].items():
        row = read(name)
        assert not row["errors"] and row["overflow"] <= 1
        assert all(r["method"] == "GET" for r in row["requests"])
        label, viewport = Path(name).stem.removeprefix("production-").rsplit("-", 1)
        paths = [p for p in (RAW / (label + "-output")).rglob("trace.zip") if viewport in str(p.parent)]
        assert len(paths) == 1
        found, gets = {}, 0
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
                    if url not in row["hashes"]:
                        continue
                    response = snapshot["response"]
                    assert response["status"] == 200
                    if "_file" not in response["content"]:
                        continue
                    content = trace.read(response["content"]["_file"])
                    path = c.safe_relative(urlparse(url).path.lstrip("/"))
                    assert content == (RAW / "retained-http-dist" / path).read_bytes()
                    assert c.sha(content) == row["hashes"][url]
                    found[url] = dict(bytes=len(content), sha256=c.sha(content))
        assert found == declared["exact_asset_bytes"] and len(found) == 3
        assert gets == declared["trace_gets"] and len(row["requests"]) == declared["page_gets"]
        get_count += gets
        page_gets += len(row["requests"])
        assets_count += len(found)
    assert (page_gets, get_count, assets_count) == (84, 142, 42)
    cleanup = read("cleanup-independent.json")
    pg = cleanup["database_check"]["shared_pg_preserved_identity"]
    names = cleanup["database_check"]["exact_names"]
    assert len(names) == len(cleanup["own_databases"]) == 13
    db = asyncio.run(c.check_databases(pg["port"], names, pg["data_dir"], pg["pid"]))
    ports = c.closed_ports(cleanup["ports_closed"])
    c.protected(ROOT, initial["m3"])
    c.protected(PRIMARY, initial["primary"])
    DEST.mkdir()
    for name in manifest["files"]:
        target = DEST / c.safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RAW / name, target)
    shutil.copyfile(RAW / "retained-manifest.json", DEST / "retained-manifest.json")
    shutil.copyfile(__file__, DEST / "parent-retain.py")
    shutil.copyfile("/tmp/m3-parent-evidence-checks.py", DEST / "parent-evidence-checks.py")
    shutil.copyfile("/tmp/m3-task9-minimum-spec-pass-postcommit.json", DEST / "prior-spec-postcommit.json")
    REPORT.write_bytes(report)
    mapping = {str(p.relative_to(DEST)): c.sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    proof = dict(verified_at=datetime.now(UTC).isoformat(), head=HEAD, source_count=355,
                 source_sha256=SOURCE, raw_manifest_sha256=c.sha(mb),
                 raw_payload_sha256=manifest["payload_sha256"], raw_payload_count=595,
                 report_sha256=c.sha(report), retained_files=mapping, archive_check=archive,
                 attacks=attacks, independent_cases="7 distinct local variants; 5 same-category Active probes",
                 complete_equal_snapshot_pairs=19, preexisting_gitblobs_exact=4891,
                 exact_database_check=db, owned_ports_closed=ports,
                 page_gets=84, trace_gets=142, actual_asset_byte_checks=42,
                 secret_scan=dict(local_config_files=configs, distinct_values=len(secrets), matches=0),
                 role="parent byte-exact failure retention; not SPEC/CODE acceptance",
                 valid_failure="P1 incomplete frozen leaf authenticity",
                 promotion_write_bypass_not_proven=True, original_ui_failures_preserved=True,
                 new_model_requests=0, new_cost_usd="0", all_http_total="unknown")
    (DEST / "parent-retention.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({k: v for k, v in proof.items() if k not in ("retained_files", "archive_check", "attacks")}, indent=2))


if __name__ == "__main__":
    main()
