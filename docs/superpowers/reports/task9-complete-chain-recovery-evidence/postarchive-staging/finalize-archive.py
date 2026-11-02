import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
REL = "docs/superpowers/reports/task9-complete-chain-recovery-evidence"
ARCHIVE = ROOT / REL
REPORT = Path("/tmp/m3-task9-complete-chain-fix-result.md")
OWN = Path("/tmp/m3-task9-chain-recovery-d7c17eb6-6c53-4bca-9c54-26b53147cd36")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write(path, value):
    assert not path.exists()
    path.write_text(json.dumps(value, indent=2) + "\n")


initial_manifest = json.loads((ARCHIVE / "manifest.json").read_text())
for name, expected in initial_manifest["files"].items():
    assert sha((ARCHIVE / name).read_bytes()) == expected
staged_before = [p.decode() for p in git("diff", "--cached", "--name-only", "-z").split(b"\0") if p]
assert set(staged_before) == {REL + "/" + p for p in initial_manifest["files"]} | {REL + "/manifest.json"}
started = datetime.now(UTC).isoformat()
check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
assert check.returncode == 2
warnings = []
for line in check.stdout.splitlines():
    if line.startswith(REL + "/") and re.search(r":\d+: ", line):
        name = re.split(r":\d+: ", line, maxsplit=1)[0]
        assert name.endswith((".log", ".diff", ".xml")) or (
            "/red-production-poison-output/" in name and name.endswith("/error-context.md"))
        warnings.append(line)
assert warnings and not check.stderr
supplement = ARCHIVE / "postarchive-staging"
assert not supplement.exists()
supplement.mkdir()
shutil.copy2(Path(__file__), supplement / "finalize-archive.py")
(supplement / "raw-whitespace-check.log").write_text(check.stdout)
write(supplement / "verification.json", {
    "role": "implementer archive staging classification, not SPEC/CODE/security review",
    "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
    "command": ["git", "diff", "--cached", "--check"], "exit": check.returncode,
    "warnings": warnings, "classified_raw_only": True,
    "previous_attempt": "same staged diff check stopped before commit; tool output not copied as original raw",
    "this_check": "new actual read-only check, not reconstructed original execution",
    "raw_bytes_trimmed_or_rewritten": False, "hook_or_signature_bypass": False,
    "preexisting_staged_count": len(staged_before),
})
shutil.copy2(REPORT, ARCHIVE / "implementation-report.md")
manifest = initial_manifest
files = {str(p.relative_to(ARCHIVE)): sha(p.read_bytes())
         for p in sorted(ARCHIVE.rglob("*")) if p.is_file() and p.name != "manifest.json"}
# Nested parent manifests remain payload; exclude only the outer manifest.
for p in sorted(ARCHIVE.rglob("manifest.json")):
    if p != ARCHIVE / "manifest.json":
        files[str(p.relative_to(ARCHIVE))] = sha(p.read_bytes())
assert len(files) == 597
manifest["files"] = files
manifest["payload_count"] = len(files)
manifest["payload_sha256"] = sha(json.dumps(sorted(files.items()), ensure_ascii=True,
                                         separators=(",", ":")).encode())
manifest["report_sha256"] = sha(REPORT.read_bytes())
manifest["validity"]["json"] += 1
manifest["postarchive_supplement"] = {
    "scope": "three newly observed archive staging files; initial raw-only592 unchanged",
    "files": [str(p.relative_to(ARCHIVE)) for p in sorted(supplement.iterdir())],
}
(ARCHIVE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
assert REPORT.read_bytes() == (ARCHIVE / "implementation-report.md").read_bytes()
raw = json.loads((ARCHIVE / "retained-raw-manifest.json").read_text())
for name, expected in raw["files"].items():
    assert sha((ARCHIVE / name).read_bytes()) == expected
subprocess.run(["git", "add", "-f", "--", REL], cwd=ROOT, check=True)
staged = [p.decode() for p in git("diff", "--cached", "--name-only", "-z").split(b"\0") if p]
assert set(staged) == {REL + "/" + p for p in files} | {REL + "/manifest.json"}
patterns = {
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider_key": rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{28,}",
    "github_token": rb"\bgh[pousr]_[A-Za-z0-9]{30,}",
    "jwt": rb"\beyJ[A-Za-z0-9_-]{25,}\.eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}",
}
hits, members_checked = [], 0
for name in staged:
    path = ROOT / name
    assert not path.is_symlink()
    assert path.suffix not in (".sqlite", ".sqlite3", ".db", ".pyc")
    assert path.name not in (".env", ".DS_Store", "tool-install.log")
    content = {"file": path.read_bytes()}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            content.update({member: z.read(member) for member in z.namelist()})
            members_checked += len(z.namelist())
    for member, data in content.items():
        for pattern, expression in patterns.items():
            if re.search(expression, data):
                hits.append(dict(file=name, member=member, pattern=pattern))
assert not hits, hits
record = {
    "role": "implementer ordinary NEW archive commit; no independent acceptance",
    "staged_paths": staged, "staged_count": len(staged),
    "secret_patterns": list(patterns), "secret_hits": hits,
    "secret_scan_scope": "narrow staged content and ZIP members, not vulnerability audit",
    "zip_members_checked": members_checked,
    "raw_whitespace_retained": True, "hook_or_signature_bypass": False,
    "archive_payload_count": manifest["payload_count"],
    "archive_payload_sha256": manifest["payload_sha256"],
    "archive_manifest_sha256": sha((ARCHIVE / "manifest.json").read_bytes()),
    "report_sha256": manifest["report_sha256"],
    "parent": git("rev-parse", "HEAD").decode().strip(),
    "started_at": datetime.now(UTC).isoformat(),
    "command": ["bash", str(OWN / "commit-evidence.sh")],
}
with Path("/tmp/m3-task9-complete-chain-evidence-commit.log").open("x") as out:
    result = subprocess.run(record["command"], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT)
record.update(exit=result.returncode, finished_at=datetime.now(UTC).isoformat(),
              head=git("rev-parse", "HEAD").decode().strip())
write(Path("/tmp/m3-task9-complete-chain-evidence-commit.json"), record)
assert result.returncode == 0
print(json.dumps({k: record[k] for k in ("head", "parent", "exit", "staged_count",
                  "archive_payload_sha256", "archive_manifest_sha256", "report_sha256")}))
