"""Preserve raw whitespace while checking every staged diagnostic and code path."""
import json
from pathlib import Path
import subprocess

from finalize import ARCHIVE, REPORT, SOURCE
from review import HEAD, OWN, ROOT, digest, git, write

raw_check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = raw_check.stdout.decode()
(OWN / "stage-whitespace.log").write_bytes(raw_check.stdout)
diagnostics = [line.split(":")[0] for line in output.splitlines() if not line.startswith("+")]
assert raw_check.returncode == 2 and diagnostics
assert all(name.startswith(str(ARCHIVE.relative_to(ROOT)) + "/")
           and name.endswith((".xml", ".log")) for name in diagnostics), diagnostics
subprocess.run(["git", "diff", "--cached", "--check", "--", *SOURCE,
                str(REPORT.relative_to(ROOT))], cwd=ROOT, check=True)
record = {
    "initial_stage_attempt": "all byte-exact paths staged; full diff --check failed on raw XML/log whitespace",
    "full_check_exit": raw_check.returncode, "diagnostics": len(diagnostics),
    "diagnostic_files": sorted(set(diagnostics)), "source_and_report_check_exit": 0,
    "secret_pattern_scan_exit": 1, "secret_pattern_scan": "no matching real-key patterns; no env files retained",
    "raw_bytes_unchanged": True, "no_git_config_or_hooks_bypass": True,
}
write("precommit-stage-verification.json", record)
for name in ("stage-freeze.py", "stage-whitespace.log", "precommit-stage-verification.json"):
    (ARCHIVE / name).write_bytes((OWN / name).read_bytes())
manifest_path = ARCHIVE / "manifest.json"
manifest = json.loads(manifest_path.read_text())
for name in ("stage-freeze.py", "stage-whitespace.log", "precommit-stage-verification.json"):
    manifest["files_sha256"][name] = digest((ARCHIVE / name).read_bytes())
manifest["payload_sha256"] = digest(json.dumps(sorted(manifest["files_sha256"].items()),
                                              ensure_ascii=True, separators=(",", ":")).encode())
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
names = SOURCE + [str(REPORT.relative_to(ROOT))] + [
    str(path.relative_to(ROOT)) for path in sorted(ARCHIVE.rglob("*")) if path.is_file()
]
for start in range(0, len(names), 100):
    subprocess.run(["git", "add", "-f", "--", *names[start:start + 100]], cwd=ROOT, check=True)
staged = [p.decode() for p in git(ROOT, "diff", "--cached", "--name-only", "-z").split(b"\0") if p]
assert set(staged) == set(names)
for name in staged:
    assert (ROOT / name).read_bytes() == git(ROOT, "show", ":" + name)
for name, sha in manifest["files_sha256"].items():
    assert digest((ARCHIVE / name).read_bytes()) == sha
write("staged-files.json", {"parent": HEAD, "files": staged, "staged_gitblob_byte_exact": True})
print(json.dumps({"staged": len(staged), "payload_files": len(manifest["files_sha256"]),
                  "payload_sha256": manifest["payload_sha256"], "raw_diagnostic_files": sorted(set(diagnostics))},
                 indent=2))
