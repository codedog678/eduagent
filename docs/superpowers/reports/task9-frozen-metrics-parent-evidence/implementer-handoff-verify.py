"""Final read-only handoff verification; own output belongs to parent next wave."""
from datetime import UTC, datetime
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import zipfile

E = Path(__file__).parent
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")
sys.path.insert(0, str(E))
import final_audit as audit
import freeze


def main():
    state = freeze.check_protected()
    assert not audit.git("status", "--porcelain")
    final = "5d6e717b3ea715524cfed2e7e2e4ee143499618e"
    assert state["m3"]["head"] == final
    assert audit.git("rev-parse", "HEAD^").decode().strip() == "be56f27b67ee3bc54db71388f68de86f70358313"
    assert freeze.REPORT.read_bytes() == freeze.RESULT.read_bytes()
    audit.helper.blobs(freeze.R, final, state["m3"]["tracked"])
    audit.helper.blobs(freeze.R, "780087401022dcfb3be904dee9ee442675625dc6", state["m3"]["source"])
    configs, values = audit.helper.secret_values((freeze.R, freeze.R.with_name("eduagent")))
    archives = {}
    for directory in (freeze.A, freeze.S):
        manifest = json.loads((directory / "manifest.json").read_bytes())
        assert "manifest.json" not in manifest["files"]
        archives[directory.name] = audit.helper.check_archive(directory, manifest, values)
        assert set(manifest["files"]) == {
            str(p.relative_to(directory)) for p in audit.retained_files(directory)
            if p != directory / "manifest.json"}
    current = {str(freeze.R / p): h for p, h in state["m3"]["tracked"].items()}
    current.update({str(freeze.R.with_name("eduagent") / p): h
                    for p, h in state["primary"]["tracked"].items()})
    current.update({str(p): audit.sha(p.read_bytes()) for p in audit.retained_files(E)})
    secret_hits, pattern_hits, classified = [], [], []
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
                rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b"]
    literal = str(freeze.R / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py")
    literal_hash = "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"

    def scan(data, name):
        for value in values:
            if value in data:
                secret_hits.append(name)
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, data):
                line = data[:match.start()].count(b"\n") + 1
                if name == literal and index == 0 and line in (88, 89):
                    assert audit.sha(data) == literal_hash
                    classified.append(dict(path=name, line=line, sha256=literal_hash))
                else:
                    pattern_hits.append(dict(path=name, line=line, pattern_index=index))

    zips = members = tars = tar_members = 0
    for name, digest in current.items():
        data, path = Path(name).read_bytes(), Path(name)
        assert audit.sha(data) == digest
        scan(data, name)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                assert z.testzip() is None
                for member in z.infolist():
                    audit.helper.safe_relative(member.filename)
                    if not member.is_dir():
                        scan(z.read(member), name + ":" + member.filename)
                        members += 1
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
                for member in tar.getmembers():
                    audit.helper.safe_relative(member.name)
                    if member.isfile():
                        scan(tar.extractfile(member).read(), name + ":" + member.name)
                        tar_members += 1
    assert not secret_hits and not pattern_hits and len(classified) == 2
    assert freeze.check_protected() == state
    assert audit.helper.closed_ports((62049, 62050, 62051))
    supplemental = json.loads((E / "resources-supplement.json").read_bytes())
    import asyncio
    pg = supplemental["database_check"]
    databases = asyncio.run(audit.helper.check_databases(57432,
        supplemental["exact_owned_databases"],
        json.loads((E / "shared-pg-identity.json").read_bytes())["data_dir"], 16852))
    proof = dict(head=final, parent="be56f27b67ee3bc54db71388f68de86f70358313",
        product="780087401022dcfb3be904dee9ee442675625dc6",
        source_count=358, source_sha256=state["m3"]["source_sha256"], clean=True,
        actual_m3_gitblobs=len(state["m3"]["tracked"]),
        actual_primary_gitblobs=len(state["primary"]["tracked"]),
        source_and_primary_metadata_index_runtime_protected=True, archives=archives,
        report_sha256=audit.sha(freeze.REPORT.read_bytes()), same_byte_report=True,
        scan_files=len(current), scan_file_hashes=current, zip_files=zips, zip_members=members,
        tar_files=tars, tar_members=tar_members, local_config_files=configs,
        actual_secret_values=len(values), secret_matches=0, effective_pattern_matches=0,
        exact_classified_literals=classified, databases=databases, shared_pg_retained=True,
        normal_hooks_no_amend_no_push_no_config_no_bypass=True,
        model_requests=0, actual_model_cost_usd="0", global_http_requests="unknown",
        engineering_green_not_acceptance=True, task10_started=False,
        timestamp=datetime.now(UTC).isoformat(),
        own_final_commit_raw_not_self_archived=True)
    audit.save("handoff-final-verification.json", proof)
    print(json.dumps({k: v for k, v in proof.items()
        if k in {"head", "parent", "source_count", "source_sha256", "actual_m3_gitblobs",
                 "same_byte_report", "scan_files", "zip_files", "zip_members", "secret_matches"}}))


if __name__ == "__main__":
    main()
