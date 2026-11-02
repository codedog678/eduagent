"""Independent SPEC raw/provenance verification, not product implementation."""
import asyncio
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.metadata as md
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tomllib
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import zipfile

os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = R.with_name("eduagent")
HEAD = "9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f"
BASE = "855d5c6660343c24df0bef5ad4cf77160e83c566"
PY = "/tmp/eduagent-m3-patched-runtime/bin/python"
sys.path.insert(0, str(E))
import control
control.install_snapshot()
import bootstrap
import prepare


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, data):
    with (E / name).open("x") as out:
        json.dump(data, out, ensure_ascii=True, indent=2, default=str)
        out.write("\n")


def combined(files):
    return sha(json.dumps(sorted(files.items()), ensure_ascii=True,
                          separators=(",", ":")).encode())


def cases(data):
    root = ET.fromstring(data)
    result = []
    for case in root.iter("testcase"):
        result.append({
            "classname": case.get("classname"), "name": case.get("name"),
            "seconds": case.get("time"),
            "outcome": next((e.tag for e in case if e.tag in ("failure", "error", "skipped")), "passed"),
            "issues": [{"kind": e.tag, "type": e.get("type"), "message": e.get("message"),
                        "text": e.text} for e in case if e.tag in ("failure", "error", "skipped")],
        })
    count = Counter(c["outcome"] for c in result)
    return dict(tests=len(result), passed=count["passed"], failure=count["failure"],
                error=count["error"], skip=count["skipped"],
                suite_seconds=sum(float(s.get("time", 0)) for s in root.iter("testsuite")),
                testcases=result)


def archive_members(data, name):
    members = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None, name
        assert len(z.namelist()) == len(set(z.namelist())), name
        for member in z.infolist():
            assert not Path(member.filename).is_absolute() and ".." not in Path(member.filename).parts
            body = z.read(member)
            row = dict(sha256=sha(body), bytes=len(body), crc=member.CRC,
                       directory=member.is_dir())
            if member.filename.endswith((".network", ".trace")):
                row["events"] = len([json.loads(line) for line in body.splitlines() if line.strip()])
            members[member.filename] = row
    return members


def historical():
    before = bootstrap.snapshot()
    assert before == json.loads((E / "initial-snapshot.json").read_bytes())
    current = before["m3"]["tracked"]
    prepare.verify_blobs(HEAD, current)
    old = json.loads((R / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence/initial-snapshot.json").read_bytes())
    prepare.verify_blobs(BASE, old["m3"]["tracked"])
    records, manifests, invalid = {}, {}, []
    reports = R / "docs/superpowers/reports"
    for path in sorted(reports.rglob("*")):
        if not path.is_file() or "task9" not in str(path.relative_to(reports)):
            continue
        data = path.read_bytes()
        name = str(path.relative_to(R))
        assert sha(data) == current[name], name
        row = dict(sha256=sha(data), bytes=len(data))
        if path.suffix in (".json", ".jsonl", ".ndjson"):
            try:
                parsed = ([json.loads(line) for line in data.splitlines() if line.strip()]
                          if path.suffix != ".json" else json.loads(data))
                row["json_type"] = type(parsed).__name__
            except json.JSONDecodeError as exc:
                row["parse_error"] = str(exc)
                invalid.append(dict(path=name, error=str(exc), sha256=row["sha256"]))
        elif path.suffix == ".xml":
            row["xml"] = cases(data)
        elif path.suffix == ".zip":
            row["members"] = archive_members(data, name)
        elif path.suffix == ".tar" or path.name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                row["tar_members"] = {}
                for member in tar.getmembers():
                    assert not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                    if member.isfile():
                        body = tar.extractfile(member).read()
                        row["tar_members"][member.name] = dict(bytes=len(body), sha256=sha(body))
        elif path.suffix != ".png":
            data.decode("utf-8")
            row["text_read_full"] = True
        records[name] = row
    for path in sorted(reports.rglob("*manifest*.json")):
        if "task9" not in str(path):
            continue
        data = json.loads(path.read_bytes())
        mapping = data.get("files", data.get("files_sha256"))
        if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values()):
            continue
        checked, missing, mismatch = [], [], []
        for name, digest in mapping.items():
            target = path.parent / name
            if target.is_file():
                actual = sha(target.read_bytes())
                if actual == digest:
                    checked.append(name)
                else:
                    preserved = [str(p.relative_to(R)) for p in path.parent.glob("*")
                                 if p.is_file() and sha(p.read_bytes()) == digest]
                    mismatch.append(dict(path=name, expected=digest, actual=actual,
                                         samebyte_retained_paths=preserved))
            else:
                missing.append(name)
        if data.get("payload_sha256") is not None:
            assert combined(mapping) == data["payload_sha256"], str(path)
        manifests[str(path.relative_to(R))] = dict(sha256=sha(path.read_bytes()),
            declared=len(mapping), checked=len(checked), missing=missing, mismatch=mismatch,
            payload_sha256=combined(mapping))
    assert bootstrap.snapshot() == before
    save("historical-full-raw-audit.json", dict(
        role="fresh SPEC byte/structure provenance only; historical executions not owned",
        current_actual_gitblobs=len(current), prior_actual_gitblobs=len(old["m3"]["tracked"]),
        records=records, manifests=manifests, preserved_invalid_json=invalid,
        xml_count=sum("xml" in r for r in records.values()),
        zip_count=sum("members" in r for r in records.values()),
        zip_member_count=sum(len(r.get("members", {})) for r in records.values()),
        full_before_after_equal=True, model_requests=0, actual_cost_usd="0"))
    print(json.dumps(dict(history_files=len(records), manifests=len(manifests),
        invalid_json=len(invalid), xml=sum("xml" in r for r in records.values()),
        zips=sum("members" in r for r in records.values()))))


def execution():
    suites = {p.name: {"sha256": sha(p.read_bytes()), **cases(p.read_bytes())}
              for p in sorted(E.glob("*.xml"))}
    expected = {"spec-full.xml": 1911, "spec-api.xml": 362, "spec-integrity.xml": 131,
                "spec-leaf-minimum.xml": 90, "spec-ui.xml": 54, "spec-visual.xml": 4}
    for name, count in expected.items():
        row = suites[name]
        assert row["tests"] == row["passed"] == count
        assert row["failure"] == row["error"] == row["skip"] == 0
    for name in [n for n in suites if n.startswith("spec-production")]:
        row = suites[name]
        assert row["tests"] == row["passed"] == 2 and not any(row[k] for k in ("failure", "error", "skip"))
    assert len([n for n in suites if n.startswith("spec-production")]) == 12
    for name in ("spec-full.xml", "spec-api.xml"):
        assert sum(c["classname"] == "tests.distributed.test_ops_leaf_authenticity"
                   for c in suites[name]["testcases"]) == 47
    pairs = {}
    for path in sorted(E.glob("*-before.json")):
        after = E / path.name.replace("-before", "-after")
        assert path.read_bytes() == after.read_bytes(), path.name
        state = json.loads(path.read_bytes())
        assert state["primary"] == json.loads((E / "initial-snapshot.json").read_bytes())["primary"]
        pairs[path.name] = dict(before_sha256=sha(path.read_bytes()), after_sha256=sha(after.read_bytes()), byte_equal=True)
    commands = {}
    for path in sorted(E.glob("*-command.json")):
        row = json.loads(path.read_bytes())
        assert datetime.fromisoformat(row["started_at"]) <= datetime.fromisoformat(row["finished_at"])
        commands[path.name] = row
    traces = {}
    for path in sorted(E.rglob("trace.zip")):
        data = path.read_bytes()
        members = archive_members(data, str(path))
        matches, network_gets, detail_bodies = [], 0, []
        production = "spec-production" in str(path)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if not name.endswith(".network"):
                    continue
                for line in z.read(name).splitlines():
                    if not line.strip():
                        continue
                    snap = json.loads(line).get("snapshot", {})
                    request, response = snap.get("request", {}), snap.get("response", {})
                    if not request:
                        continue
                    if production:
                        assert request["method"] == "GET", str(path)
                    network_gets += request["method"] == "GET"
                    url = request.get("url", "")
                    content = response.get("content", {})
                    resource = content.get("_file") or content.get("_sha1")
                    if not resource:
                        continue
                    resource = resource if resource.startswith("resources/") else "resources/" + resource
                    body = z.read(resource)
                    if production and "/assets/" in url:
                        relative = urlparse(url).path.lstrip("/")
                        assert ".." not in Path(relative).parts
                        assert body == (E / "frontend/dist" / relative).read_bytes()
                        assert response["status"] == 200
                        matches.append(dict(url=url, bytes=len(body), sha256=sha(body), resource=resource))
                    if production and "/policies/deployments/" in url:
                        assert response["status"] == 200
                        detail_bodies.append(json.loads(body))
        traces[str(path.relative_to(E))] = dict(sha256=sha(data), members=members,
            production=production, network_gets=network_gets, assets=matches,
            detail_bodies=detail_bodies)
        if production:
            assert matches and detail_bodies, str(path)
    productions = {}
    expected_gates = {
        "leaf_active_bad": set(), "leaf_local_bad": {"shadow_health"},
        "leaf_local_valid": {"canary_health", "shadow_health"},
        "leaf_active_valid": {"canary_health", "shadow_health"},
        "leaf_shadow_valid": {"shadow_health"},
    }
    for path in sorted(E.glob("production-spec-*.json")):
        row = json.loads(path.read_bytes())
        label, viewport = path.name.removeprefix("production-").removesuffix(".json").rsplit("-", 1)
        names = [name for name in traces if name.startswith(label + "-output/") and viewport in name]
        assert len(names) == 1
        trace = traces[names[0]]
        assert row["body"] in trace["detail_bodies"]
        assert not row["errors"] and row["overflow"] <= 1
        assert all(r["method"] == "GET" for r in row["requests"])
        assert row["requestContext"] == {"detailGet": 200, "assetGets": 3}
        for item in row["assetEvidence"]:
            body = (E / "frontend/dist" / urlparse(item["url"]).path.lstrip("/")).read_bytes()
            assert item["sha256"] == row["hashes"][item["url"]] == sha(body)
            assert item["bytes"] == len(body) and item["status"] == 200
            assert any(m["url"] == item["url"] and m["sha256"] == item["sha256"] for m in trace["assets"])
        if row["scenario"] in expected_gates:
            gates = {r["gate_type"] for r in row["body"]["gate_receipts"] if r["health_source"]}
            assert gates == expected_gates[row["scenario"]]
        if viewport == "mobile":
            first, last = row["scrollBefore"][0], row["scrollAfter"][0]
            assert first["fullWidth"] > first["width"]
            assert 0 <= first["left"] <= first["fullWidth"] - first["width"]
            assert last["left"] > first["left"]
        productions[path.name] = dict(trace=names[0], scenario=row["scenario"],
            viewport=viewport, page_gets=len(row["requests"]), explicit_gets=4,
            scroll_before=row["scrollBefore"], scroll_after=row["scrollAfter"],
            errors=row["errors"], overflow=row["overflow"], exact_detail_body=True)
    assert len(productions) == 24
    save("execution-full-audit.json", dict(suites=suites, complete_byte_equal_pairs=pairs,
        commands=commands, traces=traces, productions=productions,
        page_gets=sum(r["page_gets"] for r in productions.values()),
        production_network_gets=sum(t["network_gets"] for t in traces.values() if t["production"]),
        production_asset_response_bodies=sum(len(t["assets"]) for t in traces.values()),
        explicit_production_gets=96, all_http="unknown", overlap_not_summed=True,
        model_requests=0, actual_cost_usd="0", fixture_release_eligible=False))
    print(json.dumps(dict(xml=len(suites), pairs=len(pairs), trace=len(traces),
        members=sum(len(t["members"]) for t in traces.values()),
        asset_bodies=sum(len(t["assets"]) for t in traces.values()), production=len(productions))))


def runtime():
    from packaging.requirements import Requirement
    before = bootstrap.metadata(Path(PY).parent.parent)
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(E / "pycache")}
    commands = []
    for label, args in (("pip-check", ["-m", "pip", "check"]), ("pip-freeze", ["-m", "pip", "freeze", "--all"])):
        started = datetime.now(UTC).isoformat()
        proc = subprocess.run([PY, *args], capture_output=True, env=env)
        (E / ("spec-runtime-" + label + ".log")).write_bytes(proc.stdout + proc.stderr)
        commands.append(dict(command=[PY, *args], started_at=started,
            finished_at=datetime.now(UTC).isoformat(), exit=proc.returncode))
        assert proc.returncode == 0
    project = tomllib.loads((R / "python/pyproject.toml").read_text())
    groups = dict(project=project["project"]["dependencies"],
        dev=project["project"]["optional-dependencies"]["dev"],
        build=project["build-system"]["requires"],
        requirements=(R / "python/requirements.txt").read_text().splitlines(),
        repair_floors=["anyio>=4.14.2", "certifi>=2026.10.18", "pydantic-settings>=2.14.2",
                       "setuptools>=84.1.0", "starlette>=1.3.1"])
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
    after = bootstrap.metadata(Path(PY).parent.parent)
    assert before == after and len(versions) == 58 and len(coverage) == 44
    assert sum(r["group"] != "repair_floors" for r in coverage) == 39
    assert sys.version_info[:3] == (3, 11, 17)
    save("spec-runtime-final.json", dict(python=sys.version, executable=sys.executable,
        versions=versions, coverage=coverage, commands=commands, before=before, after=after,
        task10_vulnerability_audit=False, runtime_unchanged=True))
    print(json.dumps(dict(runtime=58, declarations=39, extra_floors=5, pip_check=0)))


def secrets():
    spec = importlib.util.spec_from_file_location("read_only_secret_helpers", "/tmp/m3-parent-evidence-checks.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    configs, values = helper.secret_values((R, PRIMARY))
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    tracked = {str(R / name): digest for name, digest in initial["m3"]["tracked"].items()}
    own = {str(p): sha(p.read_bytes()) for p in E.rglob("*") if p.is_file()
           and not any(part in {"node_modules", "cache", "tmp", "npm-cache", "pycache", "vite-cache"}
                       for part in p.relative_to(E).parts)}
    files = {**tracked, **own}
    patterns = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b",
    ]
    literal_path = R / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py"
    literal_data = prepare.git("show", HEAD + ":" + str(literal_path.relative_to(R)))
    assert literal_path.read_bytes() == literal_data
    assert sha(literal_data) == "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"
    hits, secrets_found, patterns_found, zips, members, tars, tar_members = [], [], [], 0, 0, 0, 0

    def check(data, name):
        for value in values:
            if value in data:
                secrets_found.append(name)
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, data):
                line = data[:match.start()].count(b"\n") + 1
                if name == str(literal_path) and index == 0 and line in (88, 89):
                    assert b"assert " in data.splitlines()[line - 1]
                    hits.append(dict(path=name, line=line, pattern_index=index,
                        file_sha256=sha(data), kind="exact frozen scanner assertion literal; no key body"))
                else:
                    patterns_found.append(dict(path=name, line=line, pattern_index=index))

    for name, digest in files.items():
        path = Path(name)
        data = path.read_bytes()
        assert sha(data) == digest
        check(data, name)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None
                for member in z.infolist():
                    if not member.is_dir():
                        check(z.read(member), name + ":" + member.filename)
                        members += 1
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        check(tar.extractfile(member).read(), name + ":" + member.name)
                        tar_members += 1
    save("spec-secret-final.json", dict(files=len(files), file_hashes=files,
        zip_files=zips, zip_members=members, tar_files=tars, tar_members=tar_members,
        local_config_files=configs, distinct_actual_secret_values=len(values),
        secret_matches=len(secrets_found), secret_match_paths=secrets_found,
        effective_pattern_matches=len(patterns_found), pattern_match_paths=patterns_found,
        raw_literal_hits=len(hits), classified_exact_literals=hits,
        hook_timeout_not_claimed_as_pass=True, values_not_echoed=True))
    assert not secrets_found and not patterns_found and len(hits) == 2
    print(json.dumps(dict(files=len(files), zip_files=zips, zip_members=members,
        actual_values=len(values), secret_matches=0, effective_patterns=0, raw_literals=len(hits))))


def cleanup():
    import redis
    records = {}
    for path in E.glob("*.json"):
        try:
            row = json.loads(path.read_bytes())
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "db" in row:
            assert row["db"].startswith("m3_t9_spec9efa_") and row["drop_exit"] == 0
            assert row["db"] not in records
            records[row["db"]] = dict(file=path.name, drop_exit=row["drop_exit"])
    shared = asyncio.run(prepare.pg_identity())
    assert not set(records) & set(shared["before_database_names"])
    identity = json.loads((E / "owned-redis-identity.json").read_bytes())
    client = redis.Redis(host="127.0.0.1", port=identity["port"], decode_responses=True)
    info = client.info("server")
    config = client.config_get("save", "appendonly", "dir")
    assert (info["process_id"], info["run_id"]) == (identity["pid"], identity["run_id"])
    assert config == identity["config"] and config["save"] == "" and config["appendonly"] == "no"
    assert int((E / "redis-service/redis.pid").read_text()) == identity["pid"]
    keys = sorted(client.scan_iter())
    ledger = [json.loads(line) for line in (E / "redis-command-ledger.jsonl").read_bytes().splitlines()]
    assert not any(r["command"] in {"FLUSHALL", "FLUSHDB"} for r in ledger)
    streams = sorted({json.loads(line)["stream"] for line in (E / "redis-owned.jsonl").read_bytes().splitlines()})
    assert all(not client.exists(key) for key in streams)
    proc = subprocess.run(["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1",
        "-p", str(identity["port"]), "SHUTDOWN", "NOSAVE"], capture_output=True)
    assert proc.returncode == 0
    ports = json.loads((E / "ports.json").read_bytes())
    closed = {}
    for port in ports.values():
        with socket.socket() as sock:
            closed[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert all(closed.values())
    removed = []
    for name in ("frontend/node_modules", "frontend/dist/.vite", "cache", "npm-cache", "tmp",
                 "pycache", "__pycache__", "vite-cache"):
        path = E / name
        if path.exists():
            assert path.resolve().is_relative_to(E.resolve())
            shutil.rmtree(path)
            removed.append(name)
    final = bootstrap.snapshot()
    assert final == json.loads((E / "initial-snapshot.json").read_bytes())
    prepare.verify_blobs(HEAD, final["m3"]["tracked"])
    data = subprocess.check_output(["git", "cat-file", "--batch"], cwd=PRIMARY,
        input="".join(final["primary"]["head"] + ":" + p + "\n" for p in final["primary"]["tracked"]).encode())
    pos = 0
    for p, digest in final["primary"]["tracked"].items():
        end = data.index(b"\n", pos)
        size = int(data[pos:end].split()[2])
        pos = end + 1
        assert sha(data[pos:pos + size]) == digest
        pos += size + 1
    assert pos == len(data)
    save("spec-cleanup-final.json", dict(exact_database_records=records,
        exact_database_count=len(records), exact_remaining=0, shared_pg=shared,
        redis_identity=identity, verified_config=config, keys_before_shutdown=keys,
        incomplete_subprocess_key_ledger=True, ledger_rows=len(ledger), streams=streams,
        shutdown_command="SHUTDOWN NOSAVE", shutdown_exit=proc.returncode,
        flush_or_prefix_delete=False, closed_ports=closed, removed_owned_caches=removed,
        retained=["all raw", "frontend/dist", "scripts", "traces", "screenshots"],
        m3_actual_gitblobs=6503, primary_actual_gitblobs=1110, protected_before_after_equal=True))
    save("final-protected-snapshot.json", final)
    print(json.dumps(dict(databases=len(records), remaining=0, redis_stopped=True,
                          protected=True, shared_pg_retained=True)))


if __name__ == "__main__":
    action = sys.argv[1]
    started = datetime.now(UTC).isoformat()
    exit_code = 1
    try:
        globals()[action]()
        exit_code = 0
    finally:
        label = sys.argv[2] if len(sys.argv) > 2 else action
        save("audit-" + label + "-command.json", dict(command=sys.argv, cwd=os.getcwd(),
            started_at=started, finished_at=datetime.now(UTC).isoformat(), exit=exit_code,
            model_requests=0, actual_cost_usd="0"))
