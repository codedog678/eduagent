"""Fresh CODE audits; imported read-only parsers are not inherited green results."""
import asyncio
from datetime import UTC, datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlparse
import zipfile

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = R / "docs/superpowers/reports/task9-leaf-authenticity-spec-pass-evidence"
sys.path.insert(0, str(E))
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
import control
import bootstrap
import prepare
module_spec = importlib.util.spec_from_file_location("read_only_provenance_parsers", A / "audit_spec.py")
audit = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(audit)
audit.E = E
audit.HEAD = control.HEAD


def save(name, value):
    with (E / name).open("x") as output:
        json.dump(value, output, indent=2, ensure_ascii=True, default=str)
        output.write("\n")


def prepare_supplements():
    text = (A / "test_spec_boundary_supplement.py").read_text()
    assert text.count("m3_t9_spec9efa_") == 1
    (E / "test_code_boundary.py").write_text(text.replace("m3_t9_spec9efa_", "m3_t9_codee8c530_"))
    save("supplement-rebinding.json", dict(source=str(A / "test_spec_boundary_supplement.py"),
        source_sha256=audit.sha((A / "test_spec_boundary_supplement.py").read_bytes()),
        sole_replacement="owned UUID database prefix", setup_main_executed=False))


def historical():
    audit.historical()
    row = json.loads((E / "historical-full-raw-audit.json").read_bytes())
    path = R / "docs/superpowers/reports/task9-health-binding-fix-evidence/source-manifest.json"
    source = json.loads(path.read_bytes())
    assert audit.combined(source["files_sha256"]) == source["authoritative_sha256"]
    prepare.verify_blobs("2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d", source["files_sha256"])
    staging = R / "docs/superpowers/reports/task9-leaf-authenticity-fix-staging-evidence"
    v1 = json.loads((staging / "manifest-v1.json").read_bytes())
    assert audit.sha((staging / "finalize-docs-v1.py").read_bytes()) == v1["files"]["finalize-docs.py"]
    for name, record in row["manifests"].items():
        if name == str(path.relative_to(R)):
            continue
        if name == str((staging / "manifest-v1.json").relative_to(R)):
            assert len(record["mismatch"]) == 1 and not record["missing"]
        else:
            assert not record["missing"] and not record["mismatch"], name
    save("code-historical-corroboration.json", dict(
        role="fresh CODE byte/structure audit; historical executions never counted as owned",
        old_source_manifest_actual_gitblobs=352, old_source_manifest_root="repository-relative",
        retained_v1_exact_renamed_script=True, all_other_manifests_complete=True,
        records=len(row["records"]), invalid_json_preserved=row["preserved_invalid_json"]))


def execution():
    suites = {p.name: dict(sha256=audit.sha(p.read_bytes()), **audit.cases(p.read_bytes()))
              for p in sorted(E.glob("*.xml"))}
    for name, count in dict(full=1911, api=362, integrity=131, **{"leaf-minimum": 90},
                            ui=54, boundary=9).items():
        row = suites["code-" + name + ".xml"]
        assert row["tests"] == row["passed"] == count
        assert not any(row[k] for k in ("failure", "error", "skip"))
    row = suites["code-complement.xml"]
    assert (row["tests"], row["passed"], row["failure"], row["error"], row["skip"]) == (42, 6, 36, 0, 0)
    for name in ("code-full.xml", "code-api.xml"):
        assert sum(c["classname"] == "tests.distributed.test_ops_leaf_authenticity"
                   for c in suites[name]["testcases"]) == 47
    pairs = {}
    for path in sorted(E.glob("*-before.json")):
        after = E / path.name.replace("-before", "-after")
        assert path.read_bytes() == after.read_bytes(), path.name
        pairs[path.name] = dict(before_sha256=audit.sha(path.read_bytes()),
                               after_sha256=audit.sha(after.read_bytes()), byte_equal=True)
    commands = {}
    for path in sorted(E.glob("*-command.json")):
        row = json.loads(path.read_bytes())
        assert datetime.fromisoformat(row["started_at"]) <= datetime.fromisoformat(row["finished_at"])
        commands[path.name] = row
    traces = {}
    for path in sorted(E.rglob("trace.zip")):
        data = path.read_bytes()
        members = audit.archive_members(data, str(path))
        production = "code-production" in str(path)
        assets, bodies, gets, other = [], [], 0, []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if not name.endswith(".network"):
                    continue
                for line in archive.read(name).splitlines():
                    if not line.strip():
                        continue
                    snap = json.loads(line).get("snapshot", {})
                    request, response = snap.get("request", {}), snap.get("response", {})
                    if not request:
                        continue
                    gets += request["method"] == "GET"
                    if request["method"] != "GET":
                        other.append(request)
                    url = request.get("url", "")
                    content = response.get("content", {})
                    resource = content.get("_file") or content.get("_sha1")
                    if not resource:
                        continue
                    resource = resource if resource.startswith("resources/") else "resources/" + resource
                    body = archive.read(resource)
                    if production and "/assets/" in url:
                        assert body == (E / "frontend/dist" / urlparse(url).path.lstrip("/")).read_bytes()
                        assert response["status"] == 200
                        assets.append(dict(url=url, bytes=len(body), sha256=audit.sha(body)))
                    if production and ("/policies/deployments/" in url or
                                       "/runs/" in url and url.endswith("/trace")):
                        assert response["status"] == 200
                        bodies.append(json.loads(body))
        if production:
            assert not other and assets and bodies, str(path)
        traces[str(path.relative_to(E))] = dict(sha256=audit.sha(data), members=members,
            production=production, network_gets=gets, assets=assets, detail_bodies=bodies,
            non_get_requests=other)
    productions = {}
    for path in sorted(E.glob("production-code-*.json")):
        row = json.loads(path.read_bytes())
        label, viewport = path.name.removeprefix("production-").removesuffix(".json").rsplit("-", 1)
        matches = [n for n in traces if n.startswith(label + "-output/") and viewport in n]
        assert len(matches) == 1
        trace = traces[matches[0]]
        assert row["body"] in trace["detail_bodies"]
        assert row["requestContext"] == dict(detailGet=200, assetGets=3)
        assert not row["errors"] and row["overflow"] <= 1
        assert all(r["method"] == "GET" for r in row["requests"])
        for asset in row["assetEvidence"]:
            data = (E / "frontend/dist" / urlparse(asset["url"]).path.lstrip("/")).read_bytes()
            assert asset["sha256"] == row["hashes"][asset["url"]] == audit.sha(data)
            assert asset["bytes"] == len(data) and asset["status"] == 200
            assert any(a["url"] == asset["url"] and a["sha256"] == asset["sha256"] for a in trace["assets"])
        if viewport == "mobile":
            first, last = row["scrollBefore"][0], row["scrollAfter"][0]
            assert first["fullWidth"] > first["width"]
            assert 0 <= first["left"] <= first["fullWidth"] - first["width"]
            assert last["left"] > first["left"]
        failure = row["scenario"].startswith("metrics_") and row["scenario"] != "metrics_active_valid"
        suite = suites[label + ".xml"]
        assert (suite["tests"], suite["passed"], suite["failure"], suite["error"], suite["skip"]) == (
            2, 0 if failure else 2, 2 if failure else 0, 0, 0)
        productions[path.name] = dict(trace=matches[0], scenario=row["scenario"], viewport=viewport,
            page_gets=len(row["requests"]), explicit_gets=4, scroll_before=row["scrollBefore"],
            scroll_after=row["scrollAfter"], valid_product_failure=failure, exact_detail_body=True)
    assert len(productions) == 32
    actual_traces = {}
    for path in E.glob("production-trace-code-*.json"):
        row = json.loads(path.read_bytes())
        viewport = path.stem.rsplit("-", 1)[1]
        matches = [name for name in traces if name.startswith("code-production-trace_pinned-output/") and viewport in name]
        assert len(matches) == 1 and row["body"] in traces[matches[0]]["detail_bodies"]
        assert row["detailGet"] == 200 and not row["errors"] and row["overflow"] <= 1
        assert all(r["method"] == "GET" for r in row["requests"])
        for item in row["assetEvidence"]:
            data = (E / "frontend/dist" / urlparse(item["url"]).path.lstrip("/")).read_bytes()
            assert item["sha256"] == audit.sha(data) and item["bytes"] == len(data) and item["status"] == 200
        actual_traces[path.name] = row
    assert len(actual_traces) == 2
    assert suites["code-production-trace_pinned.xml"]["passed"] == 2
    save("code-execution-final-audit.json", dict(suites=suites, complete_byte_equal_pairs=pairs,
        commands=commands, traces=traces, productions=productions,
        page_gets=sum(r["page_gets"] for r in productions.values()),
        production_network_gets=sum(t["network_gets"] for t in traces.values() if t["production"]),
        production_asset_response_bodies=sum(len(t["assets"]) for t in traces.values()),
        actual_pg_traces=actual_traces, explicit_production_gets=136,
        all_http="unknown", overlap_not_summed=True,
        model_requests=0, actual_cost_usd="0", fixture_release_eligible=False))
    print(json.dumps(dict(xml=len(suites), pairs=len(pairs), trace=len(traces),
        members=sum(len(t["members"]) for t in traces.values()), production=len(productions),
        asset_bodies=sum(len(t["assets"]) for t in traces.values()),
        valid_complementary_failures=36, valid_production_failures=6)))


def cleanup():
    import redis
    control.install_snapshot()
    records = {}
    for path in E.glob("*.json"):
        row = json.loads(path.read_bytes())
        if isinstance(row, dict) and "db" in row:
            assert row["db"].startswith("m3_t9_codee8c530_") and row["drop_exit"] == 0
            assert row["db"] not in records
            records[row["db"]] = dict(file=path.name, drop_exit=0)
    shared = asyncio.run(prepare.pg_identity())
    assert not set(records) & set(shared["before_database_names"])
    original_pg = json.loads((E / "shared-pg-identity.json").read_bytes())
    for key in ("pid", "data_dir", "version", "port"):
        assert shared[key] == original_pg[key]
    identity = json.loads((E / "owned-redis-identity.json").read_bytes())
    client = redis.Redis(host="127.0.0.1", port=identity["port"], decode_responses=True)
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert (info["process_id"], info["run_id"]) == (identity["pid"], identity["run_id"])
    assert config == identity["config"] and config["save"] == "" and config["appendonly"] == "no"
    assert int((E / "redis-service/redis.pid").read_text()) == identity["pid"]
    keys = sorted(client.scan_iter())
    ledger = [json.loads(line) for line in (E / "redis-command-ledger.jsonl").read_bytes().splitlines()]
    assert not any(row["command"] in {"FLUSHALL", "FLUSHDB"} for row in ledger)
    streams = sorted({json.loads(line)["stream"] for line in (E / "redis-owned.jsonl").read_bytes().splitlines()})
    assert all(not client.exists(key) for key in streams)
    proc = subprocess.run(["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1",
        "-p", str(identity["port"]), "SHUTDOWN", "NOSAVE"], capture_output=True)
    assert proc.returncode == 0
    closed = {}
    for port in json.loads((E / "ports.json").read_bytes()).values():
        with socket.socket() as sock:
            closed[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(closed.values())
    removed = []
    for name in ("frontend/node_modules", "frontend/dist/.vite", "cache", "npm-cache",
                 "tmp", "pycache", "__pycache__", "vite-cache"):
        path = E / name
        if path.exists():
            assert path.resolve().is_relative_to(E.resolve())
            shutil.rmtree(path)
            removed.append(name)
    final = bootstrap.snapshot()
    assert final == json.loads((E / "initial-snapshot.json").read_bytes())
    prepare.verify_blobs(control.HEAD, final["m3"]["tracked"])
    prepare.verify_blobs(control.PRODUCT, final["m3"]["source"])
    data = subprocess.check_output(["git", "cat-file", "--batch"], cwd=R.with_name("eduagent"),
        input="".join(final["primary"]["head"] + ":" + p + "\n" for p in final["primary"]["tracked"]).encode())
    pos = 0
    for name, digest in final["primary"]["tracked"].items():
        end = data.index(b"\n", pos)
        size = int(data[pos:end].split()[2])
        pos = end + 1
        assert audit.sha(data[pos:pos + size]) == digest
        pos += size + 1
    assert pos == len(data)
    save("code-cleanup-final.json", dict(exact_database_records=records,
        exact_database_count=len(records), exact_remaining=0, shared_pg=shared,
        redis_identity=identity, verified_config=config, keys_before_shutdown=keys,
        incomplete_subprocess_key_ledger=True, ledger_rows=len(ledger), streams=streams,
        shutdown_command="SHUTDOWN NOSAVE", shutdown_exit=0, flush_or_prefix_delete=False,
        closed_ports=closed, removed_owned_caches=removed,
        m3_actual_gitblobs=len(final["m3"]["tracked"]),
        primary_actual_gitblobs=len(final["primary"]["tracked"]), protected_before_after_equal=True))
    save("final-protected-snapshot.json", final)
    print(json.dumps(dict(databases=len(records), remaining=0, redis_stopped=True,
                          protected=True, shared_pg_retained=True)))


if __name__ == "__main__":
    action = sys.argv[1]
    started = datetime.now(UTC).isoformat()
    exit_code = 1
    try:
        if action in {"runtime", "secrets"}:
            getattr(audit, action)()
        else:
            globals()[action]()
        exit_code = 0
    finally:
        save("code-audit-" + action + "-command.json", dict(command=sys.argv, cwd=os.getcwd(),
            started_at=started, finished_at=datetime.now(UTC).isoformat(), exit=exit_code,
            model_requests=0, actual_cost_usd="0"))
