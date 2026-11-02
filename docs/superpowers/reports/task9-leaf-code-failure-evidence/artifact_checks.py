import difflib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime

from dotenv import dotenv_values
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT


def secrets():
    values = set()
    configs = 0
    for root in (ROOT, ROOT.with_name("eduagent")):
        for name in (".env", "python/.env", ".env.local", "python/.env.local"):
            path = root / name
            if path.is_file():
                configs += 1
                values.update(value.encode() for key, value in dotenv_values(path).items()
                              if value and any(word in key for word in (
                                  "API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")))
    values.update(value.encode() for key, value in os.environ.items()
                  if value and len(value) >= 8 and any(word in key for word in (
                      "API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")))
    return configs, values


def scan(entries):
    configs, values = secrets()
    hits, zip_count, member_count = [], 0, 0
    patterns = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
        rb"\bgithub_pat_[A-Za-z0-9_]{50,}\b",
        rb"\bAKIA[0-9A-Z]{16}\b",
        rb"\bsk-[A-Za-z0-9_-]{32,}\b",
    ]
    def check(name, data):
        if any(value in data for value in values) or any(re.search(p, data) for p in patterns):
            hits.append(name)
    count = 0
    for name, data in entries:
        count += 1
        check(name, data)
        if name.endswith(".zip"):
            zip_count += 1
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None, name
                for member in archive.infolist():
                    if not member.is_dir():
                        member_count += 1
                        check(name + ":" + member.filename, archive.read(member))
    assert not hits, hits
    return dict(files=count, zip_count=zip_count, zip_members=member_count,
                local_config_files=configs, local_secret_values_distinct=len(values),
                secret_matches=0, pattern_matches=0)


if sys.argv[1] == "stage":
    names = review.git(ROOT, "diff", "--cached", "--name-only", "-z").split(b"\0")
    names = [name.decode() for name in names if name]
    result = scan((name, review.git(ROOT, "show", ":" + name)) for name in names)
    result.update(time=datetime.now(UTC).isoformat(), staged_paths=names)
    review.write(sys.argv[2] + ".json", result)
    print(json.dumps(result))
elif sys.argv[1] == "provenance":
    original = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence/test_minimum_evidence.py"
    current = OWN / "test_minimum_evidence.py"
    diff = "".join(difflib.unified_diff(
        original.read_text().splitlines(keepends=True), current.read_text().splitlines(keepends=True),
        fromfile=str(original.relative_to(ROOT)), tofile="owned/test_minimum_evidence.py"))
    (OWN / "minimum-probe-owned.diff").write_text(diff)
    (OWN / "product-fix.diff").write_bytes(review.git(ROOT, "diff", "--cached"))
    review.write("minimum-probe-provenance.json", {
        "original_sha256": prepare.sha(original.read_bytes()),
        "owned_sha256": prepare.sha(current.read_bytes()),
        "diff_sha256": prepare.sha(diff.encode()),
        "semantic_correction": "local invalid Canary tests only canary_health; independent legitimate Shadow retained",
        "original_overbroad_assertion_not_acceptance": True,
        "red_invalid_fixture_retained": "invalid-attempt-minimum-test.py",
        "red_invalid_fixture_reason": "baseline observation_key reused; fresh observation UUID fixed before valid RED",
    })
