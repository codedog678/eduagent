"""Concrete-path NEW commits and acyclic implementation evidence freeze."""
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
A = R / "docs/superpowers/reports/task9-frozen-metrics-implementation-evidence"
S = R / "docs/superpowers/reports/task9-frozen-metrics-implementation-staging-evidence"
REPORT = R / "docs/superpowers/reports/2026-11-02-m3-task9-frozen-metrics-implementation.md"
RESULT = Path("/tmp/m3-task9-frozen-metrics-implementer-result.md")
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
sys.path.insert(0, str(E))
import final_audit as audit
import wave


def command(label, args, **kwargs):
    started = datetime.now(UTC).isoformat()
    with (E / (label + ".log")).open("xb") as out:
        proc = subprocess.run(args, cwd=R, stdout=out, stderr=subprocess.STDOUT, **kwargs)
    record = dict(command=args, cwd=str(R), started_at=started,
                  finished_at=datetime.now(UTC).isoformat(), exit=proc.returncode,
                  log_sha256=audit.sha((E / (label + ".log")).read_bytes()),
                  role="fresh implementer", model_requests=0, actual_model_cost_usd="0")
    audit.save(label + "-command.json", record)
    return proc.returncode


def check_protected():
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    checkpoint = json.loads((E / "metrics-source-before4.json").read_bytes())
    state = wave.snapshot()
    assert state["primary"] == initial["primary"]
    for key in ("venv", "vite", "vite_temp", "runtime"):
        assert state["m3"][key] == initial["m3"][key]
    assert state["m3"]["source"] == checkpoint["m3"]["source"]
    assert state["m3"]["source_metadata"] == checkpoint["m3"]["source_metadata"]
    assert audit.git("branch", "--show-current").decode().strip() == "feature/m3-trusted-policy-promotion"
    for name, record in json.loads((E / "historical-final-audit.json").read_bytes())["records"].items():
        assert audit.sha((R / name).read_bytes()) == record["sha256"]
    return state


def commit(label, title, body):
    text = f"git commit -F - <<'COMMIT_MESSAGE'\n{title}\n\n{body}\nCOMMIT_MESSAGE\n"
    assert command(label, ["/bin/bash", "-c", text]) == 0
    head = audit.git("rev-parse", "HEAD").decode().strip()
    parent = audit.git("rev-parse", "HEAD^").decode().strip()
    return head, parent


def postcommit(label, expected_parent):
    state = check_protected()
    head = state["m3"]["head"]
    assert audit.git("rev-parse", "HEAD^").decode().strip() == expected_parent
    assert not audit.git("status", "--porcelain")
    audit.helper.blobs(R, head, state["m3"]["tracked"])
    audit.helper.blobs(R, head, state["m3"]["source"])
    audit.helper.blobs(R.with_name("eduagent"), state["primary"]["head"], state["primary"]["tracked"])
    audit.save(label + "-postcommit.json", dict(head=head, parent=expected_parent,
        source_count=state["m3"]["source_count"], source_sha256=state["m3"]["source_sha256"],
        actual_gitblobs=len(state["m3"]["tracked"]), actual_primary_gitblobs=len(state["primary"]["tracked"]),
        clean=True, primary_index_venv_source_metadata_unchanged=True,
        both_source_caches_and_shared_runtime_unchanged=True, normal_hooks=True,
        amend=False, push=False, config_changes=False, hook_bypass=False,
        timestamp=datetime.now(UTC).isoformat()))
    return head


def product():
    state = check_protected()
    assert state["m3"]["head"] == audit.HEAD
    expected = {"python/core/distributed/ops_queries.py", "python/core/distributed/policy_health.py",
                "python/tests/distributed/test_ops_minimum_evidence.py",
                "python/tests/distributed/test_ops_frozen_metrics.py"}
    assert set(audit.git("diff", "--cached", "--name-only").decode().splitlines()) == expected
    assert command("product-diff-check", ["git", "diff", "--cached", "--check"]) == 0
    command("product-staged-diff", ["git", "diff", "--cached", "--binary"])
    head, parent = commit("product-commit", "fix(ops): authenticate complete frozen policy metrics",
        "Authenticate exact bounded observations with shared pure health formulas.\n"
        "Preserve genuine nonpass diagnostics and exact consumed-chain sources.\n"
        "Add PostgreSQL-backed full metric, schema and threshold GET attacks.\n"
        "Task9 implementation evidence is not independent acceptance; zero model requests.")
    assert parent == audit.HEAD
    assert postcommit("product", audit.HEAD) == head
    print(json.dumps(dict(product=head, parent=parent)))


def scan_new(paths):
    configs, values = audit.helper.secret_values((R, R.with_name("eduagent")))
    extra = rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b"
    import re
    for path in paths:
        data = path.read_bytes()
        audit.helper.scan_bytes(data, str(path), values)
        assert not re.search(extra, data), str(path)
        if path.suffix == ".zip":
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None
                for member in z.infolist():
                    audit.helper.safe_relative(member.filename)
                    if not member.is_dir():
                        content = z.read(member)
                        audit.helper.scan_bytes(content, str(path) + ":" + member.filename, values)
                        assert not re.search(extra, content), str(path)
    return dict(files=len(paths), distinct_actual_secret_values=len(values),
                local_config_files=configs, effective_matches=0)


def stage(label, paths, raw_root):
    args = ["git", "add", "--", *[str(p.relative_to(R)) for p in paths]]
    assert command(label + "-add", args) == 0
    tracked = audit.helper.names(R, "ls-files", "-z")
    expected = {str(p.relative_to(R)) for root in paths
                for p in (audit.retained_files(root) if root.is_dir() else [root])}
    missing = sorted(expected - tracked)
    if missing:
        assert command(label + "-add-exact-ignored", ["git", "add", "-f", "--", *missing]) == 0
    staged = set(audit.git("diff", "--cached", "--name-only").decode().splitlines())
    assert staged == expected, dict(missing=expected - staged, unexpected=staged - expected)
    secret = scan_new([R / n for n in sorted(staged)])
    raw_exit = command(label + "-raw-diff-check", ["git", "diff", "--cached", "--check"])
    assert raw_exit in (0, 2)
    nonraw = [n for n in staged if not (R / n).is_relative_to(raw_root)]
    if nonraw:
        assert command(label + "-nonraw-diff-check",
                       ["git", "diff", "--cached", "--check", "--", *sorted(nonraw)]) == 0
    audit.save(label + "-staging-proof.json", dict(staged_count=len(staged),
        exact_paths=sorted(staged), ignored_exact_paths=missing, new_bytes_secret_scan=secret,
        raw_original_whitespace_exit=raw_exit, nonraw_exit=0, raw_whitespace_preserved=True))


def archive():
    state = check_protected()
    assert not audit.git("status", "--porcelain")
    product = json.loads((E / "product-postcommit.json").read_bytes())["head"]
    assert state["m3"]["head"] == product
    audit.save("source-manifest.json", dict(role="complete source, excludes raw evidence",
        product=product, parent=audit.HEAD, files=state["m3"]["source"],
        source_count=358, source_sha256=audit.combined(state["m3"]["source"])))
    paths = audit.retained_files(E)
    scan = scan_new(paths)
    A.mkdir()
    files = {}
    for path in paths:
        name = str(path.relative_to(E))
        dest = A / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        assert path.read_bytes() == dest.read_bytes()
        files[name] = audit.sha(dest.read_bytes())
    manifest = dict(role="fresh implementation raw; not SPEC or CODE acceptance",
        product=product, starting_head=audit.HEAD, starting_parent="a3e2c0b0f510235cec8a98784afdb26b3bb6db79",
        files=files, payload_count=len(files), payload_sha256=audit.combined(files),
        source_count=358, source_sha256=state["m3"]["source_sha256"], scan=scan,
        excluded_owned_caches=["frontend/node_modules", "cache", "npm-cache", "pycache",
                               "__pycache__", "vite-cache", ".vite", ".vite-temp"],
        basetemp_evidence_preserved=True, model_requests=0, actual_model_cost_usd="0",
        global_http_requests="unknown", timestamp=datetime.now(UTC).isoformat(),
        manifest_excludes_itself=True, final_commit_proof_next_wave=True)
    with (A / "manifest.json").open("x") as out:
        json.dump(manifest, out, indent=2)
        out.write("\n")
    stage("freeze", [A], A)
    head, parent = commit("freeze-commit", "docs(task9): freeze complete frozen-metrics implementation evidence",
        f"Product {product}; source358 {state['m3']['source_sha256']}.\n"
        "Preserve original RED, final GREEN, intermediate and invalid attempts.\n"
        "Retain raw XML, GET bodies, Trace assets, resource and provenance checks.\n"
        "No independent Task9 acceptance, Task10, live evaluation or push.")
    assert parent == product
    postcommit("freeze", product)
    print(json.dumps(dict(freeze=head, parent=parent, payload_count=len(files),
                          payload_sha256=manifest["payload_sha256"])))


def handoff():
    state = check_protected()
    freeze = json.loads((E / "freeze-postcommit.json").read_bytes())["head"]
    assert state["m3"]["head"] == freeze
    assert REPORT.read_bytes() == RESULT.read_bytes()
    S.mkdir()
    names = [p for p in E.glob("freeze*") if p.is_file() and p.name != "freeze.py"]
    names += [E / "auxiliary-final-limitations.json"]
    files = {}
    for path in sorted(names):
        shutil.copy2(path, S / path.name)
        files[path.name] = audit.sha(path.read_bytes())
    manifest = dict(files=files, payload_count=len(files), payload_sha256=audit.combined(files),
        main_freeze=freeze, report_sha256=audit.sha(REPORT.read_bytes()),
        source_count=358, source_sha256=state["m3"]["source_sha256"],
        manifest_excludes_itself=True, handoff_commit_raw_to_parent_next_wave=True)
    with (S / "manifest.json").open("x") as out:
        json.dump(manifest, out, indent=2)
        out.write("\n")
    stage("handoff", [REPORT, S], S)
    head, parent = commit("handoff-commit", "docs(task9): record frozen-metrics implementation handoff",
        f"Implementation freeze {freeze}; concrete raw manifest and same-byte result.\n"
        "Preserve normal commit hook output and acyclic postcommit proof.\n"
        "Await parent verification and fresh WHOLE SPEC, then fresh WHOLE CODE.")
    assert parent == freeze
    postcommit("handoff", freeze)
    print(json.dumps(dict(handoff=head, parent=parent, report=str(REPORT))))


def cleanup():
    check_protected()
    manifest = json.loads((A / "manifest.json").read_bytes())
    for name, digest in manifest["files"].items():
        assert audit.sha((A / name).read_bytes()) == digest
        assert (E / name).read_bytes() == (A / name).read_bytes()
    removed = []
    for name in ("frontend/node_modules", "cache", "npm-cache", "pycache", "__pycache__", "vite-cache"):
        path = E / name
        if path.exists():
            assert path.resolve().is_relative_to(E.resolve())
            shutil.rmtree(path)
            removed.append(name)
    check_protected()
    audit.save("owned-cache-cleanup.json", dict(removed=removed, only_owned_caches=True,
        source_and_raw_retained=True, shared_pg_and_runtime_retained=True,
        final_ports_closed=audit.helper.closed_ports((62049, 62050, 62051)),
        timestamp=datetime.now(UTC).isoformat()))


if __name__ == "__main__":
    globals()[sys.argv[1]]()
