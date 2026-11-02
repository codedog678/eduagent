"""Seal independent SPEC evidence without modifying either protected tree."""

import asyncio
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
E = Path(__file__).parent
sys.path.insert(0, str(E))
import audit_spec as audit

R = audit.R
REPORT = Path("/tmp/m3-task9-leaf-authenticity-spec-result.md")
SEAL = Path("/tmp/m3-task9-leaf-authenticity-spec-seal.json")
VERIFY = Path("/tmp/m3-task9-leaf-authenticity-spec-verification.json")
SOURCE_SHA = "14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()


def save(path, value):
    with path.open("xb") as out:
        out.write(encoded(value))


def own_files():
    result = {}
    for path in sorted(E.rglob("*")):
        if path.is_symlink():
            raise AssertionError("Symlink in sealed evidence: " + str(path))
        if path.is_file() and path != E / "manifest.json":
            result[str(path.relative_to(E))] = sha(path.read_bytes())
    return result


def primary_blobs(state):
    mapping = state["primary"]["tracked"]
    data = subprocess.check_output(["git", "cat-file", "--batch"],
        cwd=R.with_name("eduagent"),
        input="".join(state["primary"]["head"] + ":" + p + "\n" for p in mapping).encode())
    pos = 0
    for path, digest in mapping.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", path
        size = int(header[2])
        pos = end + 1
        assert sha(data[pos:pos + size]) == digest, path
        pos += size + 1
    assert pos == len(data)


def protected():
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    final = json.loads((E / "final-protected-snapshot.json").read_bytes())
    current = audit.bootstrap.snapshot()
    assert initial == final == current
    assert current["m3"]["head"] == audit.HEAD and not current["m3"]["status"]
    assert current["m3"]["source_count"] == 357
    assert current["m3"]["source_sha256"] == SOURCE_SHA
    audit.prepare.verify_blobs(audit.HEAD, current["m3"]["tracked"])
    audit.prepare.verify_blobs(
        "1b8e4b745126c92cfd56f9f021388dd615d98791", current["m3"]["source"])
    primary_blobs(current)
    cleanup = json.loads((E / "spec-cleanup-final.json").read_bytes())
    pg = asyncio.run(audit.prepare.pg_identity())
    assert pg == cleanup["shared_pg"]
    databases = cleanup["exact_database_records"]
    assert len(databases) == 19
    assert not set(databases) & set(pg["before_database_names"])
    closed = {}
    for port in json.loads((E / "ports.json").read_bytes()).values():
        with socket.socket() as sock:
            closed[str(port)] = sock.connect_ex(("127.0.0.1", port)) != 0
    assert closed == cleanup["closed_ports"] and all(closed.values())
    for name in ("frontend/node_modules", "cache", "tmp", "npm-cache", "vite-cache"):
        assert not (E / name).exists()
    assert audit.bootstrap.snapshot() == current
    return dict(protected_complete_snapshot_equal=True, m3_actual_gitblobs=6503,
        primary_actual_gitblobs=1110, source_actual_product_blobs=357,
        exact_databases=19, exact_remaining=0, closed_ports=closed, shared_pg=pg,
        initial_snapshot_sha256=sha((E / "initial-snapshot.json").read_bytes()),
        final_snapshot_sha256=sha((E / "final-protected-snapshot.json").read_bytes()))


def matrices():
    original = json.loads((E / "execution-final-audit.json").read_bytes())
    suites = {}
    for path in sorted(E.glob("*.xml")):
        row = {"sha256": sha(path.read_bytes()), **audit.cases(path.read_bytes())}
        assert row == original["suites"][path.name]
        suites[path.name] = row
    assert len(suites) == 21
    commands = {}
    for path in sorted(E.glob("*-command.json")):
        row = json.loads(path.read_bytes())
        assert datetime.fromisoformat(row["started_at"]) <= datetime.fromisoformat(row["finished_at"])
        commands[path.name] = dict(raw_sha256=sha(path.read_bytes()), raw=row,
            aggregate_exit=row.get("exit", "unknown; original field not recorded"))
    runtime = json.loads((E / "spec-runtime-final.json").read_bytes())
    commands["spec-runtime-final.json:commands"] = runtime["commands"]
    changes = subprocess.check_output(["git", "diff", "--name-only",
        "8869166878a193a1c453376471cbe52c8fa84b3f", audit.HEAD, "--", "python", "frontend"],
        cwd=R).decode().splitlines()
    assert len(changes) == 21
    save(E / "verification-matrix.json", dict(
        role="Independent FINAL_SOURCE WHOLE SPEC; not CODE or final acceptance",
        whole_base="8869166878a193a1c453376471cbe52c8fa84b3f",
        whole_head=audit.HEAD, changed_source_paths=changes,
        suites=suites, overlap_not_summed=True, all_http="unknown",
        effective_final_suites=19, preserved_auxiliary_failed_suites=2))
    save(E / "command-ledger-final.json", dict(commands=commands,
        reading_command_utc="unknown when not originally timed",
        setup_aggregate_exit="not originally recorded; setup assertions and after snapshot retained",
        batch_aggregate_exit="not originally recorded; individual subprocess exit codes retained",
        all_http="unknown", model_requests=0, actual_cost_usd="0",
        overlap_not_summed=True))


def verify_payload(mapping):
    assert own_files() == mapping
    members, suites = {}, {}
    for name, digest in mapping.items():
        path = E / name
        body = path.read_bytes()
        assert sha(body) == digest, name
        if path.suffix == ".zip":
            members[name] = audit.archive_members(body, name)
        elif path.suffix == ".xml":
            suites[name] = audit.cases(body)
    original = json.loads((E / "execution-final-audit.json").read_bytes())
    assert set(suites) == set(original["suites"])
    for name, row in suites.items():
        expected = dict(original["suites"][name])
        del expected["sha256"]
        assert expected == row
    assert len(members) == 82
    assert sum(len(v) for v in members.values()) == 2937
    assert (E / "review-result.md").read_bytes() == REPORT.read_bytes()
    return dict(files=len(mapping), xml_count=len(suites), xml_testcases_reparsed=True,
        zip_count=len(members), zip_member_count=sum(len(v) for v in members.values()),
        zip_crc_all_members_verified=True, report_byte_equal=True,
        per_zip_member_tables="execution-final-audit.json:traces")


def metadata_scan(data):
    spec = importlib.util.spec_from_file_location(
        "sealed_secret_values", E / "read-only-secret-dependency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _, values = module.secret_values((R, R.with_name("eduagent")))
    assert len(values) == 2
    assert all(value not in data for value in values)
    for pattern in (
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b",
    ):
        assert re.search(pattern, data) is None


def seal():
    with (E / "review-result.md").open("xb") as out:
        out.write(REPORT.read_bytes())
    dependency = Path("/tmp/m3-parent-evidence-checks.py")
    body = dependency.read_bytes()
    with (E / "read-only-secret-dependency.py").open("xb") as out:
        out.write(body)
    save(E / "secret-helper-provenance.json", dict(original_path=str(dependency),
        sha256=sha(body), preserved_path="read-only-secret-dependency.py",
        functions_used=["secret_values"], original_main_not_invoked=True))
    matrices()
    started = datetime.now(UTC).isoformat()
    state = protected()
    save(E / "post-report-protected-check.json", dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(), exit=0, **state))
    original_save = audit.save

    def post_scan_save(name, value):
        assert name == "spec-secret-final.json"
        original_save("post-report-secret-scan.json", value)

    started = datetime.now(UTC).isoformat()
    audit.save = post_scan_save
    try:
        audit.secrets()
    finally:
        audit.save = original_save
    save(E / "post-report-scan-command.json", dict(command=[sys.executable, "-B", str(E / "seal_spec.py"), "seal:actual-secret-scan"],
        cwd=os.getcwd(), started_at=started, finished_at=datetime.now(UTC).isoformat(),
        exit=0, model_requests=0, actual_cost_usd="0", all_http="unknown"))
    mapping = own_files()
    manifest = dict(schema="independent-task9-whole-spec-v1",
        role="WHOLE SPEC PASS only; parent verification and NEW archive still required",
        whole_base="8869166878a193a1c453376471cbe52c8fa84b3f",
        head=audit.HEAD, product="1b8e4b745126c92cfd56f9f021388dd615d98791",
        source_count=357, source_sha256=SOURCE_SHA,
        payload_count=len(mapping), files=mapping, payload_sha256=audit.combined(mapping),
        report_path="review-result.md", report_sha256=mapping["review-result.md"],
        manifest_excludes_itself=True, model_requests=0, actual_cost_usd="0",
        all_http="unknown", overlap_not_summed=True, release_eligible=False)
    metadata_scan(encoded(manifest))
    save(E / "manifest.json", manifest)
    checked = verify_payload(mapping)
    current = protected()
    assert current == state
    scan = json.loads((E / "post-report-secret-scan.json").read_bytes())
    metadata_scan((E / "post-report-secret-scan.json").read_bytes())
    metadata_scan((E / "post-report-scan-command.json").read_bytes())
    return dict(result="WHOLE SPEC PASS", head=audit.HEAD,
        product=manifest["product"], whole_base=manifest["whole_base"],
        source_count=357, source_sha256=SOURCE_SHA, evidence=str(E),
        report_path=str(REPORT), report_sha256=manifest["report_sha256"],
        payload_count=len(mapping), payload_sha256=manifest["payload_sha256"],
        manifest_path=str(E / "manifest.json"), manifest_sha256=sha((E / "manifest.json").read_bytes()),
        payload_verification=checked, post_report_protected=current,
        post_report_secret_scan={k: scan[k] for k in (
            "files", "zip_files", "zip_members", "tar_files", "tar_members",
            "distinct_actual_secret_values", "secret_matches", "effective_pattern_matches",
            "raw_literal_hits", "values_not_echoed")},
        generated_metadata_secret_scan="manifest/scan/command/sidecar actual values and patterns zero",
        parent_verification_required=True, new_docs_archive_required=True,
        code_not_authorized=True, task9_final_acceptance=False,
        task10_not_started=True, model_requests=0, actual_cost_usd="0",
        agent50="paused", all_http="unknown", release_eligible=False)


def verify():
    prior = json.loads(SEAL.read_bytes())
    manifest = json.loads((E / "manifest.json").read_bytes())
    assert sha((E / "manifest.json").read_bytes()) == prior["manifest_sha256"]
    assert manifest["payload_sha256"] == audit.combined(manifest["files"]) == prior["payload_sha256"]
    assert manifest["payload_count"] == len(manifest["files"]) == prior["payload_count"]
    state = protected()
    assert state == prior["post_report_protected"]
    return dict(result="SEALED SPEC EVIDENCE VERIFIED", evidence=str(E),
        manifest_sha256=prior["manifest_sha256"], payload_sha256=prior["payload_sha256"],
        report_sha256=sha(REPORT.read_bytes()),
        payload_verification=verify_payload(manifest["files"]),
        protected_and_resources_reverified=True, model_requests=0,
        actual_cost_usd="0", all_http="unknown", code_not_authorized=True)


if __name__ == "__main__":
    started = datetime.now(UTC).isoformat()
    action = sys.argv[1]
    target = SEAL if action == "seal" else VERIFY
    try:
        result = {"seal": seal, "verify": verify}[action]()
    except BaseException as exc:
        failure = dict(command=[sys.executable, "-B", *sys.argv],
            started_at=started, finished_at=datetime.now(UTC).isoformat(), exit=1,
            exception_type=type(exc).__name__, message=str(exc),
            model_requests=0, actual_cost_usd="0")
        save(target.with_name(target.stem + "-failed-" + str(os.getpid()) + ".json"), failure)
        raise
    result["command"] = [sys.executable, "-B", *sys.argv]
    result["cwd"] = os.getcwd()
    result["started_at"] = started
    result["finished_at"] = datetime.now(UTC).isoformat()
    result["exit"] = 0
    metadata_scan(encoded(result))
    save(target, result)
    print(json.dumps(dict(result=result["result"],
        payload=result["payload_verification"]["files"], xml=21, zip=82,
        zip_members=2937, output=str(target))))
