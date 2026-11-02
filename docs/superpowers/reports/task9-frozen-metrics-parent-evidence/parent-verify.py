"""父侧对冻结原件逐项复算；不运行产品，不授予 SPEC/CODE 验收。"""

import asyncio
from collections import Counter
from datetime import UTC, datetime
import importlib.metadata as md
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import zipfile

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.dont_write_bytecode = True
loader = importlib.util.spec_from_file_location("history", "/tmp/m3-historical-evidence-preflight.py")
h = importlib.util.module_from_spec(loader)
loader.loader.exec_module(h)
c, R, P = h.c, h.ROOT, h.PRIMARY
E = Path("/tmp/m3-task9-metrics-fix-41068737-e9a6-42a2-89f8-10d7dda22e11")
A = R / "docs/superpowers/reports/task9-frozen-metrics-implementation-evidence"
S = A.parent / "task9-frozen-metrics-implementation-staging-evidence"
REPORT = A.parent / "2026-11-02-m3-task9-frozen-metrics-implementation.md"
OUT = Path("/tmp/m3-task9-frozen-metrics-parent-verification.json")
HEAD = "5d6e717b3ea715524cfed2e7e2e4ee143499618e"
FREEZE = "be56f27b67ee3bc54db71388f68de86f70358313"
PRODUCT = "780087401022dcfb3be904dee9ee442675625dc6"
BASE = "ffc607d4908dc50d3d7977d8056a7d33385b78e5"
SOURCE = "788bbb025f2b26684e676fbafd6b8aded30054d0541aa8a72d786356e5fe43f0"
CHANGED = {
    "python/core/distributed/ops_queries.py", "python/core/distributed/policy_health.py",
    "python/tests/distributed/test_ops_minimum_evidence.py",
    "python/tests/distributed/test_ops_frozen_metrics.py",
}


def load(path):
    return json.loads(path.read_bytes())


def batch_blobs(root, revision, mapping):
    names = list(mapping)
    for offset in range(0, len(names), 300):
        c.blobs(root, revision, {p: mapping[p] for p in names[offset:offset + 300]})


def xml_rows(data):
    root = ET.fromstring(data)
    rows = [dict(
        classname=case.get("classname"), name=case.get("name"), seconds=case.get("time"),
        outcome=next((v.tag for v in case if v.tag in {"failure", "error", "skipped"}), "passed"),
        issues=[dict(kind=v.tag, type=v.get("type"), message=v.get("message"), text=v.text)
                for v in case if v.tag in {"failure", "error", "skipped"}],
    ) for case in root.iter("testcase")]
    return dict(**c.xml_counts(data), testcases=rows,
                suite_seconds=sum(float(s.get("time", 0)) for s in root.iter("testsuite")))


def main():
    assert not OUT.exists()
    started = datetime.now(UTC).isoformat()
    before = dict(m3=h.snapshot(R), primary=h.snapshot(P))
    assert before["m3"]["head"] == HEAD
    assert not before["m3"]["status"] and not before["primary"]["status"]
    for revision, parent in ((HEAD, FREEZE), (FREEZE, PRODUCT), (PRODUCT, BASE)):
        assert c.git(R, "rev-parse", revision + "^").decode().strip() == parent
    initial = load(A / "initial-snapshot.json")
    source_manifest = load(A / "source-manifest.json")
    source = source_manifest["files"]
    assert len(source) == 358 and c.combined(source) == SOURCE
    assert set(source) == c.names(R, "ls-files", "-z", "--", "python", "frontend")
    assert source_manifest["product"] == PRODUCT and source_manifest["parent"] == BASE
    assert CHANGED == c.names(R, "diff", "--name-only", "-z", BASE, PRODUCT)
    batch_blobs(R, BASE, initial["m3"]["tracked"])
    batch_blobs(R, PRODUCT, source)
    batch_blobs(R, HEAD, before["m3"]["tracked"])
    batch_blobs(P, before["primary"]["head"], before["primary"]["tracked"])
    assert len(initial["m3"]["tracked"]) == 8225
    assert len(before["m3"]["tracked"]) == 14889
    assert len(before["primary"]["tracked"]) == 1110
    for key, value in before["primary"].items():
        assert value == initial["primary"][key], key
    for path, timestamp in initial["primary"]["source_metadata"].items():
        assert (P / path).lstat().st_mtime_ns == timestamp
    for key in ("venv", "vite", "vite_temp"):
        assert before["m3"][key] == initial["m3"][key]
    for path, digest in initial["m3"]["tracked"].items():
        if path not in CHANGED:
            assert before["m3"]["tracked"][path] == digest, path
    docs = {str(p.relative_to(R)): c.sha(p.read_bytes())
            for folder in (A, S) for p in folder.rglob("*") if p.is_file()}
    docs[str(REPORT.relative_to(R))] = c.sha(REPORT.read_bytes())
    assert set(docs) == c.names(R, "diff", "--name-only", "-z", PRODUCT, HEAD)
    assert len(docs) == 6663
    assert REPORT.read_bytes() == Path("/tmp/m3-task9-frozen-metrics-implementer-result.md").read_bytes()
    configs, values = c.secret_values((R, P))
    manifests, archives = {}, {}
    for folder, expected_count, expected_sha in (
        (A, 6645, "72b8ebce324a513ef8898d5857e3e0c14f80f5926cb8a211d7590e4876f11522"),
        (S, 15, "48e67adf23e3068009d3ddcbe4d5b922767778011e12d90dbef49c4f80a3d75e"),
    ):
        manifest = load(folder / "manifest.json")
        assert "manifest.json" not in manifest["files"]
        assert manifest["payload_count"] == len(manifest["files"]) == expected_count
        assert manifest["payload_sha256"] == expected_sha
        assert set(manifest["files"]) == {str(p.relative_to(folder))
                                         for p in folder.rglob("*")
                                         if p.is_file() and p != folder / "manifest.json"}
        archives[folder.name] = c.check_archive(folder, manifest, values)
        manifests[folder.name] = c.sha((folder / "manifest.json").read_bytes())
    assert load(S / "manifest.json")["main_freeze"] == FREEZE
    assert load(S / "manifest.json")["report_sha256"] == c.sha(REPORT.read_bytes())
    audit = load(A / "execution-final-audit.json")
    assert len(audit["suites"]) == 49
    assert set(audit["suites"]) == set(archives[A.name]["xml"])
    for name, expected in audit["suites"].items():
        data = (A / name).read_bytes()
        assert c.sha(data) == expected["sha256"], name
        assert xml_rows(data) == {k: v for k, v in expected.items() if k != "sha256"}, name
    for name, count in audit["final_matrix"].items():
        assert archives[A.name]["xml"][name] == dict(
            tests=count, passed=count, failure=0, error=0, skip=0), name
    assert audit["final_matrix"]["green-backend.xml"] == 2080
    assert audit["final_matrix"]["green-api.xml"] == 492
    assert audit["final_matrix"]["green4-original42.xml"] == 42
    assert audit["final_matrix"]["green-ui.xml"] == 54
    assert archives[A.name]["xml"]["red-original42.xml"] == dict(
        tests=42, passed=6, failure=36, error=0, skip=0)
    for name in ("green-backend.xml", "green-api.xml"):
        rows = xml_rows((A / name).read_bytes())["testcases"]
        assert sum(row["classname"] == "tests.distributed.test_ops_frozen_metrics"
                   for row in rows) == 169
    final_pairs = 0
    pairs = audit["complete_byte_equal_pairs"]
    assert len(pairs) == 51
    for name, declaration in pairs.items():
        raw = (A / name).read_bytes()
        assert raw == (A / name.replace("-before.json", "-after.json")).read_bytes()
        assert c.sha(raw) == declaration["before_sha256"] == declaration["after_sha256"]
        state = json.loads(raw)
        assert state["primary"] == initial["primary"]
        local = state["m3"]
        assert c.combined(local["source"]) == local["source_sha256"] == declaration["source_sha256"]
        assert len(local["source"]) == local["source_count"] == declaration["source_count"]
        for key in ("venv", "vite", "vite_temp", "runtime"):
            assert local[key] == initial["m3"][key], (name, key)
        for path, digest in initial["m3"]["tracked"].items():
            if path not in CHANGED:
                assert local["tracked"][path] == digest, (name, path)
        assert declaration["final_source"] == (local["source"] == source)
        if declaration["final_source"]:
            final_pairs += 1
            for path, timestamp in local["source_metadata"].items():
                assert (R / path).lstat().st_mtime_ns == timestamp
    assert final_pairs == 24
    command_count = 0
    for name, declaration in audit["commands"].items():
        assert load(A / name) == declaration
        if "started_at" in declaration:
            assert datetime.fromisoformat(declaration["started_at"]) <= datetime.fromisoformat(declaration["finished_at"])
        command_count += 1
    assert load(A / "green-build-command.json")["exit"] == 0
    runtime = load(A / "runtime-final-audit.json")
    assert sys.version_info[:3] == (3, 11, 17)
    assert len(runtime["versions"]) == 58
    assert c.metadata(Path("/tmp/eduagent-m3-patched-runtime")) == runtime["runtime_metadata"] == initial["m3"]["runtime"]
    from packaging.requirements import Requirement
    assert len(runtime["coverage"]) == 44
    assert sum(row["group"] != "repair_floors" for row in runtime["coverage"]) == 39
    for name, version in runtime["versions"].items():
        assert md.version(name) == version, name
    for row in runtime["coverage"]:
        req = Requirement(row["requirement"])
        if row["active"]:
            assert md.version(req.name) in req.specifier
    assert c.git(R, "status", "--porcelain") == b""
    traces = {}
    assets_total = assets_final = zip_members = network_gets = 0
    for name, expected in audit["traces"].items():
        raw = (A / c.safe_relative(name)).read_bytes()
        assert c.sha(raw) == expected["sha256"]
        members, assets, bodies, gets, nongets = {}, [], [], 0, []
        with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
            assert zipped.testzip() is None
            assert len(zipped.namelist()) == len(set(zipped.namelist()))
            for info in zipped.infolist():
                c.safe_relative(info.filename)
                body = zipped.read(info)
                row = dict(bytes=len(body), sha256=c.sha(body), crc=info.CRC, directory=info.is_dir())
                if info.filename.endswith((".trace", ".network")):
                    events = [json.loads(line) for line in body.splitlines() if line.strip()]
                    assert all(isinstance(event, dict) for event in events)
                    row["events"] = len(events)
                members[info.filename] = row
                if not info.is_dir():
                    zip_members += 1
                if not info.filename.endswith(".network"):
                    continue
                for event in events:
                    snap = event.get("snapshot", {})
                    request, response = snap.get("request", {}), snap.get("response", {})
                    if not request:
                        continue
                    gets += request["method"] == "GET"
                    if request["method"] != "GET":
                        nongets.append(request)
                    content = response.get("content", {})
                    resource = content.get("_file") or content.get("_sha1")
                    if resource:
                        resource = resource if resource.startswith("resources/") else "resources/" + resource
                        payload = zipped.read(resource)
                        url = request["url"]
                        if expected["production"] and "/assets/" in url:
                            assert payload == (A / "frontend/dist" / urlparse(url).path.lstrip("/")).read_bytes()
                            assert response["status"] == 200
                            assets.append(dict(url=url, bytes=len(payload), sha256=c.sha(payload)))
                        if expected["production"] and ("/policies/deployments/" in url or
                                                       "/runs/" in url and url.endswith("/trace")):
                            assert response["status"] == 200
                            bodies.append(json.loads(payload))
        assert members == expected["members"]
        assert assets == expected["assets"] and bodies == expected["detail_bodies"]
        assert gets == expected["network_gets"] and nongets == expected["non_gets"]
        if expected["production"]:
            assert not nongets and assets and bodies
        assets_total += len(assets)
        assets_final += len(assets) if name.startswith("green-production-") else 0
        network_gets += gets
        traces[name] = dict(assets=assets, bodies=bodies)
    assert len(traces) == 176 and zip_members == 5816
    assert assets_total == 272 and assets_final == 136
    finals = mobile_final = pg_trace_final = 0
    for name, declaration in audit["productions"].items():
        record = load(A / name)
        trace = traces[declaration["trace"]]
        assert any(json.dumps(record["body"], sort_keys=True) == json.dumps(body, sort_keys=True)
                   for body in trace["bodies"])
        assert not record["errors"] and record["overflow"] <= 1
        assert all(req["method"] == "GET" for req in record["requests"])
        is_trace = declaration["actual_pg_trace"]
        assert (record["detailGet"] if is_trace else record["requestContext"]["detailGet"]) == 200
        for asset in record["assetEvidence"]:
            data = (A / "frontend/dist" / urlparse(asset["url"]).path.lstrip("/")).read_bytes()
            assert asset["sha256"] == c.sha(data) and asset["bytes"] == len(data) and asset["status"] == 200
            assert any(a["url"] == asset["url"] and a["sha256"] == asset["sha256"] for a in trace["assets"])
        if declaration["viewport"] == "mobile" and not is_trace:
            start, end = record["scrollBefore"][0], record["scrollAfter"][0]
            assert start["fullWidth"] > start["width"] and end["left"] > start["left"] >= 0
            mobile_final += declaration["final_source"]
        finals += declaration["final_source"]
        pg_trace_final += is_trace and declaration["final_source"]
    assert len(audit["productions"]) == 68 and finals == 34 and mobile_final == 16 and pg_trace_final == 2
    history = load(A / "historical-final-audit.json")
    historical_xml = historical_zips = historical_members = 0
    for name, expected in history["records"].items():
        raw = (R / c.safe_relative(name)).read_bytes()
        assert c.sha(raw) == expected["sha256"] == initial["m3"]["tracked"][name]
        if "xml" in expected:
            assert xml_rows(raw) == expected["xml"]
            historical_xml += 1
        if "members" in expected:
            historical_zips += 1
            with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
                assert zipped.testzip() is None
                for member in zipped.infolist():
                    body = zipped.read(member)
                    check = expected["members"][member.filename]
                    assert check["bytes"] == len(body) and check["sha256"] == c.sha(body)
                    historical_members += 1
    assert len(history["records"]) == 7005 and historical_xml == 270 and historical_zips == 826
    assert historical_members == 29194
    for name in history["manifests"]:
        path = R / name
        manifest = load(path)
        mapping = manifest.get("files", manifest.get("files_sha256"))
        if name.endswith("task9-health-binding-fix-evidence/source-manifest.json"):
            assert len(mapping) == 352 and c.combined(mapping) == manifest["authoritative_sha256"]
            batch_blobs(R, "2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d", mapping)
        else:
            for child, digest in mapping.items():
                target = path.parent / c.safe_relative(child)
                if not target.is_file() or c.sha(target.read_bytes()) != digest:
                    assert name.endswith("task9-leaf-authenticity-fix-staging-evidence/manifest-v1.json")
                    assert child == "finalize-docs.py"
                    target = path.parent / "finalize-docs-v1.py"
                assert c.sha(target.read_bytes()) == digest
            if "payload_sha256" in manifest:
                assert c.combined(mapping) == manifest["payload_sha256"]
    resources = load(A / "resources-supplement.json")
    shared = load(A / "shared-pg-identity.json")
    assert len(resources["exact_owned_databases"]) == 47
    assert all(re.fullmatch(r"m3_t9_metrics410687_[a-f0-9]{32}", name) and row["drop_exit"] == 0
               for name, row in resources["exact_owned_databases"].items())
    databases = asyncio.run(c.check_databases(shared["port"], resources["exact_owned_databases"],
                                              shared["data_dir"], shared["pid"]))
    ports = c.closed_ports((62049, 62050, 62051))
    cleanup = load(A / "resources-final-audit.json")
    assert cleanup["verified_config"] == cleanup["redis_identity"]["config"]
    assert cleanup["verified_config"]["save"] == "" and cleanup["verified_config"]["appendonly"] == "no"
    assert cleanup["shutdown_command"][-2:] == ["SHUTDOWN", "NOSAVE"] and cleanup["shutdown_exit"] == 0
    assert cleanup["ledger_incomplete_for_child_keys"] and not cleanup["flush_or_prefix_delete"]
    for line in (A / "redis-command-ledger.jsonl").read_bytes().splitlines():
        assert json.loads(line)["command"] not in {"FLUSHALL", "FLUSHDB"}
    # 全 current Git 原件及完整 ZIP/TAR 成员扫描；唯一精确旧 scanner literal 分类。
    file_map = {str(R / path): digest for path, digest in before["m3"]["tracked"].items()}
    file_map.update({str(P / path): digest for path, digest in before["primary"]["tracked"].items()})
    literal = str(R / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py")
    literal_sha = "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"
    classified, scanned_zips, scanned_members, tars, tar_members = [], 0, 0, 0, 0
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
                rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b"]

    def scan(data, name):
        assert all(value not in data for value in values), name
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, data):
                line = data[:match.start()].count(b"\n") + 1
                assert name == literal and index == 0 and line in (88, 89), (name, line, index)
                assert c.sha(data) == literal_sha
                classified.append(dict(path=name, line=line, sha256=literal_sha))

    for name, digest in file_map.items():
        path = Path(name)
        raw = path.read_bytes()
        assert c.sha(raw) == digest
        scan(raw, name)
        if path.suffix == ".zip":
            scanned_zips += 1
            with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
                assert zipped.testzip() is None
                for member in zipped.infolist():
                    c.safe_relative(member.filename)
                    if not member.is_dir():
                        scan(zipped.read(member), name + ":" + member.filename)
                        scanned_members += 1
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
                for member in archive.getmembers():
                    c.safe_relative(member.name)
                    if member.isfile():
                        scan(archive.extractfile(member).read(), name + ":" + member.name)
                        tar_members += 1
    assert len(classified) == 2
    assert before == dict(m3=h.snapshot(R), primary=h.snapshot(P))
    assert c.metadata(Path("/tmp/eduagent-m3-patched-runtime")) == runtime["runtime_metadata"]
    result = dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(),
        role="parent independently recomputed provenance; not SPEC/CODE acceptance",
        head=HEAD, parent=FREEZE, product=PRODUCT, product_parent=BASE,
        source_count=358, source_sha256=SOURCE, source_files=source, changed_paths=sorted(CHANGED),
        current_actual_gitblobs=14889, initial_actual_gitblobs=8225,
        primary_actual_gitblobs=1110, new_docs_gitblobs=len(docs), manifests=manifests,
        report_sha256=c.sha(REPORT.read_bytes()), archives=archives,
        complete_byte_equal_pairs=51, final_source_pairs=final_pairs,
        original_xml_node_records_recomputed=49, final_matrix=audit["final_matrix"],
        new_metrics_testcases_in_full_and_api=169, trace_zips=176, trace_members=zip_members,
        actual_network_gets=network_gets, actual_asset_body_comparisons=assets_total,
        final_asset_body_comparisons=assets_final, production_records=68,
        final_production_viewports=finals, final_mobile_actual_scroll=mobile_final,
        final_actual_pg_trace=pg_trace_final, execution_command_records=command_count,
        historical_files=7005, historical_manifests=len(history["manifests"]),
        historical_xml=historical_xml, historical_zips=historical_zips,
        historical_members=historical_members, historical_source_gitblobs=352,
        exact_database_check=databases, closed_ports=ports, redis_child_key_ledger_incomplete=True,
        readonly_runtime_distributions=58, requirements_declarations=39, additional_floors=5,
        secret_scan=dict(files=len(file_map), zips=scanned_zips, zip_members=scanned_members,
                         tars=tars, tar_members=tar_members, actual_values=len(values),
                         config_files=configs, matches=0, classified_exact_literals=classified),
        both_current_trees_index_venv_cache_before_after_equal=True, primary_initial_equal=True,
        raw_failures_preserved=True, no_model_requests=0, actual_model_cost_usd="0",
        global_http_requests="unknown", normal_hook_timeout_not_full_scan_pass=True,
        actual_visual_image_review="pending separate actual view_image calls",
    )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "head", "source_count", "source_sha256", "current_actual_gitblobs", "new_docs_gitblobs",
        "complete_byte_equal_pairs", "final_source_pairs", "final_matrix",
        "final_production_viewports", "final_asset_body_comparisons",
        "final_mobile_actual_scroll", "exact_database_check", "secret_scan",
    )}, indent=2))


if __name__ == "__main__":
    main()
