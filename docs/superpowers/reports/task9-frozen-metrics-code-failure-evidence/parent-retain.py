"""父侧核原始 CODE FAIL、原字节归档及 NEW commit 后复核；不授予验收。"""

import argparse
import asyncio
from collections import Counter
from datetime import UTC, datetime
import importlib.util
import io
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
loader = importlib.util.spec_from_file_location("checks", "/tmp/m3-parent-evidence-checks.py")
c = importlib.util.module_from_spec(loader)
loader.loader.exec_module(c)
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
E = Path("/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814")
HEAD = "a3e2c0b0f510235cec8a98784afdb26b3bb6db79"
PRODUCT = "1b8e4b745126c92cfd56f9f021388dd615d98791"
DEST = ROOT / "docs/superpowers/reports/task9-frozen-metrics-code-failure-evidence"
REPORT = DEST.parent / "2026-11-02-m3-task9-frozen-metrics-code-failure.md"
PROOF = Path("/tmp/m3-task9-metrics-code-parent-verification.json")
RESULT = Path("/tmp/m3-task9-leaf-authenticity-code-result.md")
SEAL = Path(str(E) + "-seal.json")
FINAL = Path(str(E) + "-final-verification.json")
OLD_LITERAL = ROOT / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py"
OLD_LITERAL_SHA = "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"
PATTERNS = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
    rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b",
]


def read(name):
    return json.loads((E / name).read_bytes())


def protect(state, archival=False):
    c.protected(PRIMARY, state["primary"])
    c.worktree(ROOT, state["m3"]["tracked"])
    if not archival:
        c.protected(ROOT, state["m3"])
    else:
        for key, relative in (("venv", ".venv"), ("vite", "frontend/node_modules/.vite"),
                              ("vite_temp", "frontend/node_modules/.vite-temp")):
            assert c.metadata(ROOT / relative) == state["m3"][key]
    for key, root in (("m3", ROOT), ("primary", PRIMARY)):
        for path, stamp in state[key]["source_metadata"].items():
            assert (root / path).lstat().st_mtime_ns == stamp, (key, path)
    assert c.metadata(Path("/tmp/eduagent-m3-patched-runtime")) == state["m3"]["runtime"]


def cases(data):
    root = ET.fromstring(data)
    rows = []
    for case in root.iter("testcase"):
        rows.append(dict(
            classname=case.get("classname"), name=case.get("name"), seconds=case.get("time"),
            outcome=next((e.tag for e in case if e.tag in ("failure", "error", "skipped")), "passed"),
            issues=[dict(kind=e.tag, type=e.get("type"), message=e.get("message"), text=e.text)
                    for e in case if e.tag in ("failure", "error", "skipped")],
        ))
    counts = Counter(row["outcome"] for row in rows)
    return dict(tests=len(rows), passed=counts["passed"], failure=counts["failure"],
                error=counts["error"], skip=counts["skipped"],
                suite_seconds=sum(float(s.get("time", 0)) for s in root.iter("testsuite")),
                testcases=rows)


def scan(data, name, secrets, classified):
    assert not any(value in data for value in secrets), name
    for index, pattern in enumerate(PATTERNS):
        for match in re.finditer(pattern, data):
            line = data[:match.start()].count(b"\n") + 1
            if name == str(OLD_LITERAL) and index == 0 and line in (88, 89):
                assert c.sha(data) == OLD_LITERAL_SHA
                assert b"assert " in data.splitlines()[line - 1]
                classified.add((name, line, OLD_LITERAL_SHA))
            else:
                raise AssertionError(("secret pattern match", name, line, index))


def zip_members(data, name, secrets, classified):
    records = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None, name
        assert len(archive.namelist()) == len(set(archive.namelist())), name
        for member in archive.infolist():
            c.safe_relative(member.filename)
            content = archive.read(member)
            scan(content, name + ":" + member.filename, secrets, classified)
            record = dict(sha256=c.sha(content), bytes=len(content), crc=member.CRC,
                          directory=member.is_dir())
            if member.filename.endswith((".network", ".trace")):
                record["events"] = len([json.loads(line) for line in content.splitlines() if line.strip()])
            records[member.filename] = record
    return records


def verify():
    assert not PROOF.exists()
    started = datetime.now(UTC).isoformat()
    state = read("initial-snapshot.json")
    assert state["m3"]["head"] == HEAD and len(state["m3"]["tracked"]) == 7296
    assert c.combined(state["m3"]["source"]) == state["m3"]["source_sha256"]
    assert state["m3"]["source_count"] == len(state["m3"]["source"]) == 357
    protect(state)
    c.blobs(ROOT, HEAD, state["m3"]["tracked"])
    c.blobs(ROOT, PRODUCT, state["m3"]["source"])
    c.blobs(PRIMARY, state["primary"]["head"], state["primary"]["tracked"])
    seal = json.loads(SEAL.read_bytes())
    mb = (E / "manifest.json").read_bytes()
    manifest = json.loads(mb)
    records = manifest["records"]
    assert c.sha(mb) == seal["manifest_sha256"]
    assert c.sha(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()) == seal["payload_sha256"] == manifest["payload_sha256"]
    assert len(records) == manifest["files"] == seal["files"] == 917
    assert {str(p.relative_to(E)) for p in E.rglob("*") if p.is_file()} == set(records) | {"manifest.json"}
    report = RESULT.read_bytes()
    assert c.sha(report) == seal["result_sha256"]
    for name, digest in seal["reports"].items():
        assert c.sha((E / name).read_bytes()) == digest
    config_files, secrets = c.secret_values((ROOT, PRIMARY))
    classified = set()
    own_zips = own_members = 0
    for name, declaration in records.items():
        data = (E / c.safe_relative(name)).read_bytes()
        assert c.sha(data) == declaration["sha256"] and len(data) == declaration["bytes"], name
        scan(data, str(E / name), secrets, classified)
        if name.endswith(".zip"):
            own_zips += 1
            own_members += len(zip_members(data, str(E / name), secrets, classified))
    assert (own_zips, own_members) == (92, 3251)
    audit = read("code-execution-final-audit.json")
    suites = {p.name: cases(p.read_bytes()) for p in E.glob("*.xml")}
    assert len(suites) == 25
    for name, actual in suites.items():
        assert {k: v for k, v in audit["suites"][name].items() if k != "sha256"} == actual, name
        assert audit["suites"][name]["sha256"] == c.sha((E / name).read_bytes())
    assert (suites["code-complement.xml"]["passed"], suites["code-complement.xml"]["failure"]) == (6, 36)
    for name, count in {
        "code-full.xml": 1911, "code-api.xml": 362, "code-integrity.xml": 131,
        "code-leaf-minimum.xml": 90, "code-boundary.xml": 9, "code-ui.xml": 54,
    }.items():
        assert suites[name]["tests"] == suites[name]["passed"] == count
    production = {n: v for n, v in suites.items() if n.startswith("code-production-")}
    assert (sum(v["tests"] for v in production.values()), sum(v["passed"] for v in production.values()),
            sum(v["failure"] for v in production.values())) == (34, 28, 6)
    assert len(audit["complete_byte_equal_pairs"]) == 26
    for name, declared in audit["complete_byte_equal_pairs"].items():
        before = (E / name).read_bytes()
        after = (E / name.replace("-before", "-after")).read_bytes()
        assert before == after and c.sha(before) == declared["before_sha256"] == declared["after_sha256"]
        phase = json.loads(before)
        assert {key: phase[key] for key in state} == state, name
    assert read("final-protected-snapshot.json") == state
    for name, row in audit["commands"].items():
        assert read(name) == row
        assert datetime.fromisoformat(row["started_at"]) <= datetime.fromisoformat(row["finished_at"])
    asset_bodies = network_gets = 0
    for name, declaration in audit["traces"].items():
        path = E / c.safe_relative(name)
        assert c.sha(path.read_bytes()) == declaration["sha256"]
        assert zip_members(path.read_bytes(), str(path), secrets, classified) == declaration["members"]
        actual_assets, actual_bodies, gets, other = [], [], 0, []
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith(".network"):
                    continue
                for line in archive.read(member).splitlines():
                    if not line.strip():
                        continue
                    snapshot = json.loads(line).get("snapshot", {})
                    req, resp = snapshot.get("request", {}), snapshot.get("response", {})
                    if not req:
                        continue
                    gets += req["method"] == "GET"
                    if req["method"] != "GET":
                        other.append(req)
                    url = req.get("url", "")
                    resource = resp.get("content", {}).get("_file") or resp.get("content", {}).get("_sha1")
                    if not resource:
                        continue
                    resource = resource if resource.startswith("resources/") else "resources/" + resource
                    body = archive.read(resource)
                    if declaration["production"] and "/assets/" in url:
                        relative = c.safe_relative(urlparse(url).path.lstrip("/"))
                        assert resp["status"] == 200 and body == (E / "frontend/dist" / relative).read_bytes()
                        actual_assets.append(dict(url=url, bytes=len(body), sha256=c.sha(body)))
                    if declaration["production"] and (
                        "/policies/deployments/" in url or "/runs/" in url and url.endswith("/trace")
                    ):
                        assert resp["status"] == 200
                        actual_bodies.append(json.loads(body))
        assert actual_assets == declaration["assets"] and actual_bodies == declaration["detail_bodies"]
        assert gets == declaration["network_gets"] and other == declaration["non_get_requests"]
        asset_bodies += len(actual_assets)
        network_gets += gets if declaration["production"] else 0
    assert (asset_bodies, network_gets) == (136, 340)
    assert len(audit["productions"]) == 32 and len(audit["actual_pg_traces"]) == 2
    page_gets = mobile_scroll = 0
    for name, row in audit["productions"].items():
        raw = read(name)
        assert raw["body"] in audit["traces"][row["trace"]]["detail_bodies"]
        assert not raw["errors"] and raw["overflow"] <= 1
        assert raw["scrollBefore"] == row["scroll_before"] and raw["scrollAfter"] == row["scroll_after"]
        assert all(req["method"] == "GET" for req in raw["requests"])
        assert len(raw["requests"]) == row["page_gets"]
        if row["viewport"] == "mobile":
            assert raw["scrollAfter"][0]["left"] > raw["scrollBefore"][0]["left"]
            mobile_scroll += 1
        page_gets += row["page_gets"]
    assert (page_gets, mobile_scroll) == (192, 16)
    for name, raw in audit["actual_pg_traces"].items():
        assert read(name) == raw and raw["detailGet"] == 200
        assert not raw["errors"] and all(r["method"] == "GET" for r in raw["requests"])
    historic = read("historical-full-raw-audit.json")
    xml_count = zip_count = member_count = 0
    for name, row in historic["records"].items():
        data = (ROOT / c.safe_relative(name)).read_bytes()
        assert c.sha(data) == row["sha256"] and len(data) == row["bytes"], name
        if "xml" in row:
            assert cases(data) == row["xml"], name
            xml_count += 1
        if "members" in row:
            assert zip_members(data, str(ROOT / name), secrets, classified) == row["members"], name
            zip_count += 1
            member_count += len(row["members"])
    assert (len(historic["records"]), xml_count, zip_count, member_count) == (6076, 245, 734, 25943)
    old = json.loads((ROOT / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence/initial-snapshot.json").read_bytes())
    c.blobs(ROOT, old["m3"]["head"], old["m3"]["tracked"])
    assert len(old["m3"]["tracked"]) == 5492
    for key, root in (("m3", ROOT), ("primary", PRIMARY)):
        for name, digest in state[key]["tracked"].items():
            data = (root / name).read_bytes()
            assert c.sha(data) == digest
            scan(data, str(root / name), secrets, classified)
    assert len(classified) == 2
    for path in (RESULT, SEAL, FINAL, Path(__file__),
                 Path("/tmp/m3-task9-leaf-spec-pass-postcommit.json"),
                 Path("/tmp/m3-task9-leaf-spec-pass-commit.log")):
        scan(path.read_bytes(), str(path), secrets, classified)
    cleanup = read("code-cleanup-final.json")
    names = list(cleanup["exact_database_records"])
    assert len(names) == 23 and all(row["drop_exit"] == 0 for row in cleanup["exact_database_records"].values())
    pg = cleanup["shared_pg"]
    db = asyncio.run(c.check_databases(pg["port"], names, pg["data_dir"], pg["pid"]))
    ports = c.closed_ports(cleanup["closed_ports"])
    assert cleanup["shutdown_command"] == "SHUTDOWN NOSAVE" and cleanup["shutdown_exit"] == 0
    assert not cleanup["flush_or_prefix_delete"] and cleanup["incomplete_subprocess_key_ledger"]
    for name in ("code-visual-inspection-record.json", "code-visual-fixture-inspection.json"):
        for image in read(name)["images"]:
            assert c.sha((E / image["path"]).read_bytes()) == image["sha256"]
    images = [
        "screenshots/detail-code-production-metrics_active_permission_violation-desktop-left.png",
        "screenshots/detail-code-production-leaf_active_valid-mobile-left.png",
        "screenshots/detail-code-production-current-mobile-left.png",
        "screenshots/trace-pinned-mobile.png",
    ]
    protect(state)
    proof = dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(),
        role="parent CODE FAIL provenance only; Task9 not accepted",
        head=HEAD, product=PRODUCT, source_count=357, source_sha256=state["m3"]["source_sha256"],
        existing_actual_gitblobs=7296, prior_actual_gitblobs=5492, primary_actual_gitblobs=1110,
        report_sha256=c.sha(report), raw_manifest_sha256=c.sha(mb),
        raw_payload_sha256=seal["payload_sha256"], raw_payload_count=917,
        xml_suites=25, complete_byte_equal_pairs=26, zip_files=92, zip_members=3251,
        historic_files=6076, historic_xml=245, historic_zip=734, historic_zip_members=25943,
        valid_complementary_failures=36, valid_production_failures=6,
        production_checks=34, asset_response_bodies=136, production_network_gets=340,
        page_gets=192, mobile_scroll_records=16, actual_pg_trace_records=2,
        parent_actual_viewed_images={n: c.sha((E / n).read_bytes()) for n in images},
        exact_database_check=db, closed_ports=ports,
        secret_scan=dict(config_files=config_files, distinct_actual_values=len(secrets),
                         matches=0, classified_exact_old_literals=sorted(classified)),
        normal_hook_timeout_not_complete_scan=True,
        model_requests=0, actual_cost_usd="0", all_http="unknown", overlap_not_summed=True,
        both_trees_source_index_mtime_venv_cache_runtime_protected=True,
        task9_accepted=False, task10_started=False,
        preserved_parent_auxiliary_attempts=[dict(
            shell_id="f3801ecd3accac680863d892192dfe66", exit=1,
            actual_error="AssertionError: code-api-before.json",
            reason="phase snapshot has an additional execution field; complete before/after bytes equal, both full protected tree objects equal initial",
            product_failure=False,
        )],
    )
    PROOF.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


def retain():
    assert not DEST.exists() and not REPORT.exists()
    proof = json.loads(PROOF.read_bytes())
    state = read("initial-snapshot.json")
    protect(state)
    manifest = read("manifest.json")
    DEST.mkdir()
    for name, row in manifest["records"].items():
        target = DEST / c.safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (E / name).read_bytes()
        assert c.sha(data) == row["sha256"] and len(data) == row["bytes"]
        target.write_bytes(data)
    extras = {
        E / "manifest.json": "manifest.json",
        SEAL: "reviewer-external-seal.json",
        FINAL: "reviewer-final-verification.json",
        PROOF: "parent-verification.json",
        Path(__file__): "parent-retain.py",
        Path("/tmp/m3-parent-evidence-checks.py"): "parent-evidence-checks.py",
        Path("/tmp/m3-task9-leaf-spec-pass-postcommit.json"): "prior-spec-pass-postcommit.json",
        Path("/tmp/m3-task9-leaf-spec-pass-commit.log"): "prior-spec-pass-commit.log",
        Path("/tmp/m3-task9-metrics-code-archive-supplement.py"): "parent-archive-supplement.py",
        Path("/tmp/m3-task9-metrics-code-archive-supplement.json"): "parent-archive-supplement.json",
    }
    for path, name in extras.items():
        shutil.copyfile(path, DEST / name)
    REPORT.write_bytes(RESULT.read_bytes())
    assert c.sha(REPORT.read_bytes()) == proof["report_sha256"]
    retained = {str(p.relative_to(DEST)): c.sha(p.read_bytes()) for p in DEST.rglob("*") if p.is_file()}
    (DEST / "parent-retained-manifest.json").write_text(json.dumps(
        dict(files=retained, payload_sha256=c.combined(retained), report_sha256=proof["report_sha256"],
             parent=HEAD, role="CODE FAIL retention; not acceptance"), indent=2) + "\n")
    print(json.dumps(dict(retained=len(retained), destination=str(DEST), report=str(REPORT))))


def postcommit(tip):
    state = read("initial-snapshot.json")
    assert c.git(ROOT, "rev-parse", "HEAD").decode().strip() == tip
    assert c.git(ROOT, "rev-parse", tip + "^").decode().strip() == HEAD
    assert not c.git(ROOT, "status", "--porcelain")
    retained = json.loads((DEST / "parent-retained-manifest.json").read_bytes())
    assert c.combined(retained["files"]) == retained["payload_sha256"]
    mapping = dict(state["m3"]["tracked"])
    prefix = str(DEST.relative_to(ROOT)) + "/"
    mapping.update({prefix + p: digest for p, digest in retained["files"].items()})
    mapping[prefix + "parent-retained-manifest.json"] = c.sha((DEST / "parent-retained-manifest.json").read_bytes())
    mapping[str(REPORT.relative_to(ROOT))] = retained["report_sha256"]
    assert c.names(ROOT, "ls-files", "-z") == set(mapping)
    c.worktree(ROOT, mapping)
    c.blobs(ROOT, tip, mapping)
    assert c.names(ROOT, "diff", "--name-only", "-z", HEAD, tip) == set(mapping) - set(state["m3"]["tracked"])
    assert not c.git(ROOT, "diff", HEAD, tip, "--", "python", "frontend", "tools")
    protect(state, archival=True)
    out = Path("/tmp/m3-task9-metrics-code-fail-postcommit.json")
    assert not out.exists()
    out.write_text(json.dumps(dict(
        verified_at=datetime.now(UTC).isoformat(), head=tip, parent=HEAD, product=PRODUCT,
        actual_gitblobs=len(mapping), new_docs_paths=len(mapping) - len(state["m3"]["tracked"]),
        source_count=357, source_sha256=state["m3"]["source_sha256"],
        report_sha256=retained["report_sha256"],
        role="parent CODE FAIL postcommit provenance; Task9 not accepted",
        primary_source_index_venv_cache_runtime_unchanged=True,
    ), indent=2) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retain", action="store_true")
    parser.add_argument("--verify-head")
    args = parser.parse_args()
    if args.verify_head:
        postcommit(args.verify_head)
    elif args.retain:
        retain()
    else:
        verify()
