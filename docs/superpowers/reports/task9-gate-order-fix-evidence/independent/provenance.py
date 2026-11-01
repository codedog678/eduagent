import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
EVIDENCE = ROOT / "docs/superpowers/reports/task9-ops-evidence"
manifest = json.loads((EVIDENCE / "manifest.json").read_text())
sha = lambda body: hashlib.sha256(body).hexdigest()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "38f48d763b4a9599aa215f98a2cba1b32003b1e7"
for field, base in [("source_files", ROOT), ("evidence_files", EVIDENCE)]:
    for rel, expected in manifest[field]:
        path = base / rel
        assert sha(path.read_bytes()) == expected, rel
        gitrel = str(path.relative_to(ROOT))
        assert sha(subprocess.check_output(["git", "show", f"HEAD:{gitrel}"], cwd=ROOT)) == expected
    combined = sha(json.dumps(sorted(manifest[field]), separators=(",", ":"), ensure_ascii=True).encode())
    assert combined == manifest[field.replace("_files", "_combined_sha256")]
    print(field, len(manifest[field]), combined)
for rel, expected in sorted(manifest["junit"].items()):
    root = ET.parse(EVIDENCE / rel).getroot()
    suites = list(root.iter("testsuite"))
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    cases = list(root.iter("testcase"))
    actual = {key: sum(c.find(key[:-1] if key != "skipped" else key) is not None for c in cases)
              for key in ("failures", "errors", "skipped")}
    assert all(counts[k] == expected[k] for k in counts), rel
    assert len(cases) == expected["testcases"]
    assert actual == {k: counts[k] for k in actual}
    print(rel, counts, sha((EVIDENCE / rel).read_bytes()))
changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=ROOT, text=True).splitlines()
owned = {p for p, _ in manifest["source_files"]}
owned.update(str((EVIDENCE / p).relative_to(ROOT)) for p, _ in manifest["evidence_files"])
owned.update([str((EVIDENCE / "manifest.json").relative_to(ROOT)),
              "docs/superpowers/reports/2026-11-02-m3-task9-ops.md"])
assert set(changed) == owned and len(changed) == 62
print("changed_paths=62; frozen working files and Git blobs match; PASS")
