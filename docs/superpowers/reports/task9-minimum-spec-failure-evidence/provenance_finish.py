import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from datetime import UTC, datetime
import review

OWN = review.OWN
ROOT = review.ROOT


def blobs(root, revision, mapping):
    data = subprocess.check_output(
        ["git", "cat-file", "--batch"], cwd=root,
        input="".join(f"{revision}:{p}\n" for p in mapping).encode())
    pos = 0
    for name, digest in mapping.items():
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        assert len(header) == 3 and header[1] == b"blob", name
        size = int(header[2])
        pos = end + 1
        assert review.digest(data[pos:pos + size]) == digest, name
        pos += size + 1
    assert pos == len(data)


initial = json.loads((OWN / "initial-snapshot.json").read_text())
for key, root in (("m3", ROOT), ("primary", ROOT.with_name("eduagent"))):
    blobs(root, initial[key]["head"], initial[key]["tracked"])
archive = ROOT / "docs/superpowers/reports/task9-complete-chain-recovery-evidence"
baseline = json.loads((archive / "baseline-gitblob-verification.json").read_text())
mapping = {}
with tarfile.open(archive / "baseline.tar") as tar:
    for member in tar:
        if member.isfile():
            assert not member.name.startswith("/") and ".." not in Path(member.name).parts
            mapping[member.name] = review.digest(tar.extractfile(member).read())
blobs(ROOT, baseline["freeze"], mapping)
assert len(mapping) == 358
assert {p: h for p, h in mapping.items() if p.startswith(("python/", "frontend/"))} == baseline["source"]
diff = subprocess.check_output(
    ["git", "diff", "8869166878a193a1c453376471cbe52c8fa84b3f", review.HEAD, "--", "python", "frontend"], cwd=ROOT)
with (OWN / "whole-task9-source.diff").open("xb") as f:
    f.write(diff)
check = subprocess.run(
    ["git", "diff", "--check", "8869166878a193a1c453376471cbe52c8fa84b3f.." + review.HEAD,
     "--", "python", "frontend"], cwd=ROOT, capture_output=True)
assert check.returncode == 0
review.write("final-independent-provenance.json", {
    "time": datetime.now(UTC).isoformat(), "role": "fresh SPEC reviewer, independent provenance execution",
    "m3_all_current_gitblobs": len(initial["m3"]["tracked"]),
    "primary_all_current_gitblobs": len(initial["primary"]["tracked"]),
    "archive_tar_sha256": review.digest((archive / "baseline.tar").read_bytes()),
    "baseline_freeze": baseline["freeze"], "tar_files_gitblob_match": mapping,
    "baseline_python_frontend": len(baseline["source"]),
    "whole_source_diff_sha256": review.digest(diff),
    "diff_check_exit": check.returncode, "diff_check_stdout": check.stdout.decode(),
    "diff_check_stderr": check.stderr.decode(),
    "baseline_execution_role": "archived implementer replay, NOT mine",
    "optional_gepa_constraint": {"requirement": "gepa==0.1.4", "installed": "0.1.4", "matches": True}})
review.snapshot("report-freeze-after")
print(json.dumps({"m3_gitblobs": 3374, "primary_gitblobs": 1110, "baseline_tar_blobs": len(mapping),
                  "diff_check_exit": check.returncode}))
