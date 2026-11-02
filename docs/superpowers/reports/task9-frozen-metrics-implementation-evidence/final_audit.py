"""Fresh implementer provenance checks, not independent acceptance."""
import ast
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
import subprocess
import sys
import tarfile
import tomllib
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import zipfile

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
HEAD = "ffc607d4908dc50d3d7977d8056a7d33385b78e5"
BASE = "8869166878a193a1c453376471cbe52c8fa84b3f"
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
sys.path.insert(0, str(E))
import wave
import prepare

spec = importlib.util.spec_from_file_location("parent_checks", "/tmp/m3-parent-evidence-checks.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
sha, combined = helper.sha, helper.combined


def save(name, value):
    with (E / name).open("x") as out:
        json.dump(value, out, indent=2, ensure_ascii=True, default=str)
        out.write("\n")


def git(*args):
    return helper.git(R, *args)


def retained_files(root):
    excluded = {"node_modules", "cache", "npm-cache", "pycache", "__pycache__",
                "vite-cache", ".vite", ".vite-temp"}
    return [p for p in sorted(root.rglob("*")) if p.is_file()
            and not excluded.intersection(p.relative_to(root).parts)]


def cases(data):
    root = ET.fromstring(data)
    rows = [{
        "classname": c.get("classname"), "name": c.get("name"), "seconds": c.get("time"),
        "outcome": next((e.tag for e in c if e.tag in {"failure", "error", "skipped"}), "passed"),
        "issues": [{"kind": e.tag, "type": e.get("type"), "message": e.get("message"), "text": e.text}
                   for e in c if e.tag in {"failure", "error", "skipped"}],
    } for c in root.iter("testcase")]
    count = Counter(c["outcome"] for c in rows)
    return dict(tests=len(rows), passed=count["passed"], failure=count["failure"],
                error=count["error"], skip=count["skipped"], testcases=rows,
                suite_seconds=sum(float(s.get("time", 0)) for s in root.iter("testsuite")))


def zip_records(data, name):
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist())), name
        for member in z.infolist():
            helper.safe_relative(member.filename)
            body = z.read(member)
            row = dict(bytes=len(body), sha256=sha(body), crc=member.CRC, directory=member.is_dir())
            if member.filename.endswith((".trace", ".network")):
                row["events"] = sum(1 for line in body.splitlines() if line.strip()
                                    and isinstance(json.loads(line), dict))
            result[member.filename] = row
    return result


def runtime():
    from packaging.requirements import Requirement
    before = wave.snapshot()
    commands = []
    for name, args in (("check", ["check"]), ("freeze", ["freeze", "--all"])):
        start = datetime.now(UTC).isoformat()
        cmd = [PY, "-m", "pip", *args]
        proc = subprocess.run(cmd, capture_output=True)
        with (E / f"runtime-pip-{name}.log").open("xb") as out:
            out.write(proc.stdout + proc.stderr)
        commands.append(dict(command=cmd, started_at=start, finished_at=datetime.now(UTC).isoformat(),
                             cwd=str(R), exit=proc.returncode))
        assert proc.returncode == 0
    project = tomllib.loads((R / "python/pyproject.toml").read_text())
    groups = dict(project=project["project"]["dependencies"],
                  dev=project["project"]["optional-dependencies"]["dev"],
                  build=project["build-system"]["requires"],
                  requirements=(R / "python/requirements.txt").read_text().splitlines(),
                  repair_floors=["anyio>=4.14.2", "certifi>=2026.10.18",
                                "pydantic-settings>=2.14.2", "setuptools>=84.1.0", "starlette>=1.3.1"])
    coverage = []
    for group, rows in groups.items():
        for text in rows:
            if not text.strip() or text.startswith("#"):
                continue
            req = Requirement(text)
            active = req.marker is None or req.marker.evaluate()
            installed = md.version(req.name) if active else None
            passed = not active or req.specifier.contains(installed, prereleases=True)
            assert passed, req.name
            coverage.append(dict(group=group, requirement=text, active=active,
                                 installed=installed, passed=passed))
    versions = {d.metadata["Name"]: d.version for d in md.distributions()}
    assert len(versions) == 58 and len(coverage) == 44 and sys.version_info[:3] == (3, 11, 17)
    assert wave.snapshot() == before
    node = "/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node"
    assert subprocess.check_output([node, "--version"]).decode().strip() == "v20.19.5"
    save("runtime-final-audit.json", dict(python=sys.version, executable=sys.executable,
        versions=versions, coverage=coverage, commands=commands, full_snapshot_unchanged=True,
        runtime_metadata=before["m3"]["runtime"], node=node, node_version="20.19.5",
        task10_vulnerability_audit=False))


def historical():
    before = wave.snapshot()
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    helper.blobs(R, HEAD, initial["m3"]["tracked"])
    records, invalid = {}, []
    for path in sorted((R / "docs/superpowers/reports").rglob("*")):
        if not path.is_file() or "task9" not in str(path.relative_to(R)):
            continue
        name, data = str(path.relative_to(R)), path.read_bytes()
        assert sha(data) == initial["m3"]["tracked"][name], name
        row = dict(sha256=sha(data), bytes=len(data))
        if path.suffix in {".json", ".jsonl", ".ndjson"}:
            try:
                parsed = (json.loads(data) if path.suffix == ".json" else
                          [json.loads(line) for line in data.splitlines() if line.strip()])
                row["json_type"] = type(parsed).__name__
            except json.JSONDecodeError as exc:
                row["preserved_parse_error"] = str(exc)
                invalid.append(name)
        elif path.suffix == ".xml":
            row["xml"] = cases(data)
        elif path.suffix == ".zip":
            row["members"] = zip_records(data, name)
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                row["tar_members"] = {}
                for member in tar.getmembers():
                    helper.safe_relative(member.name)
                    if member.isfile():
                        body = tar.extractfile(member).read()
                        row["tar_members"][member.name] = dict(bytes=len(body), sha256=sha(body))
        elif path.suffix != ".png":
            data.decode("utf-8")
            row["text_read_full"] = True
        records[name] = row
    manifests = {}
    source_manifest = "docs/superpowers/reports/task9-health-binding-fix-evidence/source-manifest.json"
    for path in sorted((R / "docs/superpowers/reports").rglob("*manifest*.json")):
        if "task9" not in str(path):
            continue
        data = json.loads(path.read_bytes())
        mapping = data.get("files", data.get("files_sha256"))
        if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values()):
            continue
        rel = str(path.relative_to(R))
        if rel == source_manifest:
            assert combined(mapping) == data["authoritative_sha256"]
            helper.blobs(R, "2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d", mapping)
            manifests[rel] = dict(sha256=sha(path.read_bytes()), declared=len(mapping),
                checked_actual_original_gitblobs=len(mapping), current_source_comparison=False)
            continue
        source_root = path.parent
        checked, renamed = 0, {}
        for name, digest in mapping.items():
            target = source_root / helper.safe_relative(name)
            if target.is_file() and sha(target.read_bytes()) == digest:
                checked += 1
                continue
            assert rel.endswith("task9-leaf-authenticity-fix-staging-evidence/manifest-v1.json")
            assert name == "finalize-docs.py"
            original = path.parent / "finalize-docs-v1.py"
            assert sha(original.read_bytes()) == digest
            renamed[name] = original.name
        if "payload_sha256" in data:
            assert combined(mapping) == data["payload_sha256"], rel
        manifests[rel] = dict(sha256=sha(path.read_bytes()), declared=len(mapping),
                             checked=checked, exact_renamed_original=renamed)
    paths = set(git("diff", "--name-only", BASE, "--", "python", "frontend", "tools", ".github")
                .decode().splitlines()) | set(initial["m3"]["extra_source"])
    paths.add("python/tests/distributed/test_ops_frozen_metrics.py")
    scope = {}
    for name in sorted(paths):
        path = R / name
        if not path.is_file():
            scope[name] = dict(deleted=True)
            continue
        text = path.read_text()
        row = dict(sha256=sha(text.encode()), bytes=len(text.encode()), lines=len(text.splitlines()),
                   read_full=True)
        if path.suffix == ".py":
            tree = ast.parse(text)
            row["functions"] = [{"name": n.name, "line": n.lineno, "end_line": n.end_lineno}
                                for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        scope[name] = row
    helper.blobs(R.with_name("eduagent"), initial["primary"]["head"], initial["primary"]["tracked"])
    assert wave.snapshot() == before
    save("historical-final-audit.json", dict(role="implementer provenance only, not reviewer PASS",
        actual_initial_gitblobs=len(initial["m3"]["tracked"]),
        actual_primary_gitblobs=len(initial["primary"]["tracked"]), records=records,
        manifests=manifests, preserved_invalid_json=invalid, task8_to_current_scope=scope,
        source_manifest_actual_old_gitblobs=352, full_snapshot_unchanged=True,
        xml_count=sum("xml" in r for r in records.values()),
        zip_count=sum("members" in r for r in records.values()),
        zip_member_count=sum(len(r.get("members", {})) for r in records.values())))


def execution():
    before = wave.snapshot()
    final_source = json.loads((E / "metrics-source-before4.json").read_bytes())["m3"]["source"]
    suites = {p.name: dict(sha256=sha(p.read_bytes()), **cases(p.read_bytes()))
              for p in sorted(E.glob("*.xml"))}
    expected = {"green-backend.xml": 2080, "green-api.xml": 492, "green-integrity.xml": 131,
                "green-boundaries.xml": 67, "green-ui.xml": 54, "green4-original42.xml": 42}
    expected.update({p.name: 2 for p in E.glob("green-production-*.xml")})
    assert len(expected) == 23
    for name, count in expected.items():
        row = suites[name]
        assert row["tests"] == row["passed"] == count
        assert row["failure"] == row["error"] == row["skip"] == 0
    assert (suites["red-original42.xml"]["passed"], suites["red-original42.xml"]["failure"]) == (6, 36)
    pairs, checkpoints = {}, {}
    for path in sorted(E.glob("*-before.json")):
        after = E / path.name.replace("-before.json", "-after.json")
        assert path.read_bytes() == after.read_bytes(), path.name
        state = json.loads(path.read_bytes())
        assert state["primary"] == json.loads((E / "initial-snapshot.json").read_bytes())["primary"]
        source_digest = combined(state["m3"]["source"])
        checkpoints[source_digest] = state["m3"]["source_count"]
        pairs[path.name] = dict(before_sha256=sha(path.read_bytes()), after_sha256=sha(after.read_bytes()),
                               source_sha256=source_digest, source_count=state["m3"]["source_count"],
                               byte_equal=True, final_source=state["m3"]["source"] == final_source)
    commands = {}
    for path in sorted(E.glob("*-command.json")):
        row = json.loads(path.read_bytes())
        if "started_at" in row:
            assert datetime.fromisoformat(row["started_at"]) <= datetime.fromisoformat(row["finished_at"])
        commands[path.name] = row
    assert commands["green-build-command.json"]["exit"] == 0
    traces = {}
    for path in sorted(E.rglob("trace.zip")):
        data, name = path.read_bytes(), str(path.relative_to(E))
        production = "production-" in name
        assets, bodies, gets, nongets = [], [], 0, []
        members = zip_records(data, name)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                if not member.endswith(".network"):
                    continue
                for line in z.read(member).splitlines():
                    if not line.strip():
                        continue
                    snap = json.loads(line).get("snapshot", {})
                    req, resp = snap.get("request", {}), snap.get("response", {})
                    if not req:
                        continue
                    gets += req["method"] == "GET"
                    if req["method"] != "GET":
                        nongets.append(req)
                    content = resp.get("content", {})
                    resource = content.get("_file") or content.get("_sha1")
                    if not resource:
                        continue
                    resource = resource if resource.startswith("resources/") else "resources/" + resource
                    body, url = z.read(resource), req["url"]
                    if production and "/assets/" in url:
                        assert body == (E / "frontend/dist" / urlparse(url).path.lstrip("/")).read_bytes()
                        assert resp["status"] == 200
                        assets.append(dict(url=url, bytes=len(body), sha256=sha(body)))
                    if production and ("/policies/deployments/" in url or
                                       "/runs/" in url and url.endswith("/trace")):
                        assert resp["status"] == 200
                        bodies.append(json.loads(body))
        if production:
            assert not nongets and assets and bodies, name
        traces[name] = dict(sha256=sha(data), members=members, production=production,
                           network_gets=gets, assets=assets, detail_bodies=bodies, non_gets=nongets)
    productions = {}
    for path in sorted(E.glob("production-*.json")):
        if path.name == "production-batch.json":
            continue
        row = json.loads(path.read_bytes())
        is_trace = path.name.startswith("production-trace-")
        label, viewport = path.stem.removeprefix("production-trace-" if is_trace else "production-").rsplit("-", 1)
        matched = [n for n in traces if n.startswith(label + "-output/") and viewport in n]
        assert len(matched) == 1, path.name
        trace = traces[matched[0]]
        assert row["body"] in trace["detail_bodies"]
        assert not row["errors"] and row["overflow"] <= 1
        assert all(r["method"] == "GET" for r in row["requests"])
        assert (row["detailGet"] if is_trace else row["requestContext"]["detailGet"]) == 200
        assert len(row["assetEvidence"]) == 3
        for asset in row["assetEvidence"]:
            data = (E / "frontend/dist" / urlparse(asset["url"]).path.lstrip("/")).read_bytes()
            assert asset["sha256"] == sha(data) and asset["bytes"] == len(data) and asset["status"] == 200
            assert any(a["url"] == asset["url"] and a["sha256"] == asset["sha256"] for a in trace["assets"])
        if viewport == "mobile" and not is_trace:
            first, last = row["scrollBefore"][0], row["scrollAfter"][0]
            assert first["fullWidth"] > first["width"]
            assert 0 <= first["left"] <= first["fullWidth"] - first["width"]
            assert last["left"] > first["left"]
        productions[path.name] = dict(trace=matched[0], exact_body=True, viewport=viewport,
            final_source=label.startswith("green-"), actual_pg_trace=is_trace,
            scroll_before=row.get("scrollBefore"), scroll_after=row.get("scrollAfter"),
            fixture_current=row["body"].get("is_current"), release_eligible=False)
    assert len(productions) == 68 and sum(r["final_source"] for r in productions.values()) == 34
    invalid = []
    for path in retained_files(E):
        if path.suffix == ".json":
            try:
                json.loads(path.read_bytes())
            except json.JSONDecodeError as exc:
                invalid.append(dict(path=str(path.relative_to(E)), sha256=sha(path.read_bytes()), error=str(exc)))
    assert wave.snapshot() == before
    save("execution-final-audit.json", dict(suites=suites, final_matrix=expected,
        complete_byte_equal_pairs=pairs, source_checkpoints=checkpoints, commands=commands,
        traces=traces, productions=productions, preserved_invalid_json=invalid,
        production_asset_response_bodies=sum(len(t["assets"]) for t in traces.values()),
        final_production_asset_response_bodies=sum(len(t["assets"]) for n, t in traces.items()
                                                  if n.startswith("green-production-")),
        model_requests=0, actual_model_cost_usd="0", global_http_requests="unknown",
        overlapping_test_denominators_not_summed=True, engineering_green_not_acceptance=True))


def resources():
    import redis
    before = wave.snapshot()
    records = {}
    for path in E.glob("*-command.json"):
        row = json.loads(path.read_bytes())
        if "db" in row:
            assert re.fullmatch(r"m3_t9_metrics410687_[a-f0-9]{32}", row["db"])
            assert row["drop_exit"] == 0 and row["db"] not in records
            records[row["db"]] = dict(command_record=path.name, drop_exit=0)
    shared = asyncio.run(prepare.pg_identity())
    original = json.loads((E / "shared-pg-identity.json").read_bytes())
    for key in ("pid", "data_dir", "version", "port"):
        assert shared[key] == original[key]
    pg = asyncio.run(helper.check_databases(shared["port"], records, shared["data_dir"], shared["pid"]))
    identity = json.loads((E / "owned-redis-identity.json").read_bytes())
    client = redis.Redis(host="127.0.0.1", port=identity["port"], decode_responses=True)
    info, config = client.info("server"), client.config_get("save", "appendonly", "dir")
    assert (info["process_id"], info["run_id"]) == (identity["pid"], identity["run_id"])
    assert config == identity["config"] and config["save"] == "" and config["appendonly"] == "no"
    assert int((E / "redis-service/redis.pid").read_text()) == identity["pid"]
    keys = sorted(client.scan_iter())
    ledger = [json.loads(line) for line in (E / "redis-command-ledger.jsonl").read_bytes().splitlines()]
    assert not any(r["command"] in {"FLUSHALL", "FLUSHDB"} for r in ledger)
    streams = sorted({json.loads(line)["stream"] for line in (E / "redis-owned.jsonl").read_bytes().splitlines()})
    assert all(not client.exists(s) for s in streams)
    command = ["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1", "-p", str(identity["port"]),
               "SHUTDOWN", "NOSAVE"]
    proc = subprocess.run(command, capture_output=True)
    assert proc.returncode == 0
    ports = helper.closed_ports(json.loads((E / "ports.json").read_bytes()).values())
    assert wave.snapshot() == before
    save("resources-final-audit.json", dict(exact_owned_databases=records, database_check=pg,
        shared_pg_retained=True, redis_identity=identity, verified_config=config,
        keys_before_shutdown=keys, ledger_rows=len(ledger), ledger_incomplete_for_child_keys=True,
        streams=streams, shutdown_command=command, shutdown_exit=0, closed_ports=ports,
        flush_or_prefix_delete=False, full_snapshot_unchanged=True))
    save("precommit-protected-snapshot.json", before)


def secrets():
    configs, values = helper.secret_values((R, R.with_name("eduagent")))
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    files = {str(R / n): sha((R / n).read_bytes()) for n in initial["m3"]["tracked"]}
    files.update({str(R / n): sha((R / n).read_bytes())
                  for n in json.loads((E / "metrics-source-before4.json").read_bytes())["m3"]["source"]})
    files.update({str(R.with_name("eduagent") / n): h for n, h in initial["primary"]["tracked"].items()})
    files.update({str(p): sha(p.read_bytes()) for p in retained_files(E)})
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
                rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b"]
    literal = R / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py"
    literal_sha = "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"
    assert sha(literal.read_bytes()) == literal_sha
    helper.blobs(R, HEAD, {str(literal.relative_to(R)): literal_sha})
    secrets_found, effective, classified = [], [], []
    zips = members = tars = tar_members = 0

    def check(data, name):
        for value in values:
            if value in data:
                secrets_found.append(name)
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, data):
                line = data[:match.start()].count(b"\n") + 1
                if name == str(literal) and index == 0 and line in (88, 89):
                    assert sha(data) == literal_sha and b"assert " in data.splitlines()[line - 1]
                    classified.append(dict(path=name, line=line, pattern_index=index,
                                           sha256=literal_sha, kind="exact old scanner literal"))
                else:
                    effective.append(dict(path=name, line=line, pattern_index=index))

    for name, digest in files.items():
        path, data = Path(name), Path(name).read_bytes()
        assert sha(data) == digest
        check(data, name)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None
                for member in z.infolist():
                    helper.safe_relative(member.filename)
                    if not member.is_dir():
                        check(z.read(member), name + ":" + member.filename)
                        members += 1
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                for member in tar.getmembers():
                    helper.safe_relative(member.name)
                    if member.isfile():
                        check(tar.extractfile(member).read(), name + ":" + member.name)
                        tar_members += 1
    save("secret-final-audit.json", dict(files=len(files), file_hashes=files,
        zip_files=zips, zip_members=members, tar_files=tars, tar_members=tar_members,
        local_config_files=configs, distinct_actual_secret_values=len(values),
        actual_secret_match_paths=secrets_found, effective_pattern_matches=effective,
        classified_exact_literals=classified, values_never_echoed=True,
        normal_hook_timeout_not_claimed_as_complete_scan=True))
    assert not secrets_found and not effective and len(classified) == 2
    print(json.dumps(dict(files=len(files), zips=zips, members=members, tars=tars,
        tar_members=tar_members, secret_values=len(values), effective_matches=0)))


def resources2():
    original = json.loads((E / "resources-final-audit.json").read_bytes())
    records = dict(original["exact_owned_databases"])
    for path in sorted(E.glob("*-lifecycle.json")):
        row = json.loads(path.read_bytes())
        assert re.fullmatch(r"m3_t9_metrics410687_[a-f0-9]{32}", row["db"])
        assert row["drop_exit"] == 0 and row["db"] not in records
        records[row["db"]] = dict(lifecycle_record=path.name, drop_exit=0,
                                 server_pid=row["server_pid"], server_exit=row["server_exit"])
    assert len(records) == 47
    pg = original["database_check"]
    checked = asyncio.run(helper.check_databases(pg["shared_pg_port"], records,
        json.loads((E / "shared-pg-identity.json").read_bytes())["data_dir"], pg["shared_pg_pid"]))
    closed = helper.closed_ports(json.loads((E / "ports.json").read_bytes()).values())
    save("resources-supplement.json", dict(exact_owned_databases=records, database_check=checked,
        closed_ports=closed, redis_shutdown_already_authenticated="resources-final-audit.json",
        supplementary_count_note="13 pytest command records plus 34 production lifecycle records",
        no_additional_shutdown_or_delete=True))


if __name__ == "__main__":
    action = sys.argv[1]
    started = datetime.now(UTC).isoformat()
    exit_code = 1
    try:
        {"historical2": historical, "execution2": execution}.get(action, globals().get(action))()
        exit_code = 0
    finally:
        save("audit-" + action + "-command.json", dict(command=sys.argv, cwd=os.getcwd(),
            started_at=started, finished_at=datetime.now(UTC).isoformat(), exit=exit_code,
            role="fresh implementer, not reviewer", model_requests=0, actual_model_cost_usd="0"))
