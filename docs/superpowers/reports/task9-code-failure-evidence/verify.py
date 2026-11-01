from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(files):
    return sha(json.dumps(sorted(files.items()), separators=(",", ":"), ensure_ascii=True).encode())


def junit(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    suites = list(root.iter("testsuite"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    actual = {
        "tests": len(cases),
        "failures": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skipped": sum(c.find("skipped") is not None for c in cases),
    }
    assert actual == counts, (path, actual, counts)
    return {"counts": counts, "sha256": sha(path.read_bytes())}


all_xml = {p.name: junit(p) for p in sorted(OWN.glob("*.xml"))}
matrix = defaultdict(Counter)
for case in ET.parse(OWN / "full-v2.xml").getroot().iter("testcase"):
    matrix[case.get("classname")]["tests"] += 1
    for tag in ("failure", "error", "skipped"):
        matrix[case.get("classname")][tag] += int(case.find(tag) is not None)
groups = Counter()
for name, count in matrix.items():
    groups[".".join(name.split(".")[:2])] += count["tests"]
(OWN / "backend-impact-matrix.json").write_text(json.dumps({
    "source": "full-v2.xml, fresh CODE reviewer execution",
    "module_count": len(matrix), "groups": groups, "modules": matrix,
}, indent=2) + "\n")

archive = ROOT / "docs/superpowers/reports/task9-corrected-spec-evidence"
manifest = json.loads((archive / "manifest.json").read_text())
for name, h in manifest["files"].items():
    assert sha((archive / name).read_bytes()) == h, name
assert len(manifest["files"]) == 94
assert digest(manifest["files"]) == "8bcc90f85f0f45394ce88d0db813529083b43cd7af87df849077fd366dc757a0"
archive_xml = {str(p.relative_to(ROOT)): junit(p) for dirname in (
    "task9-ops-evidence", "task9-gate-order-fix-evidence", "task9-corrected-spec-evidence"
) for p in (ROOT / "docs/superpowers/reports" / dirname).rglob("*.xml")}

pairs = {}
for before in sorted(OWN.glob("*-before.json")):
    after = before.with_name(before.name.replace("-before.json", "-after.json"))
    if after.exists():
        equal = json.loads(before.read_text()) == json.loads(after.read_text())
        assert equal, before
        pairs[before.stem.removesuffix("-before")] = "unchanged"

frontend = OWN / "frontend"
external_links = []
for p in (frontend / "node_modules").rglob("*"):
    if p.is_symlink() and not p.resolve().is_relative_to(frontend.resolve()):
        external_links.append(str(p))
assert not external_links
assert not (frontend / "node_modules").is_symlink()
sources = {str(p.relative_to(frontend)): sha(p.read_bytes()) for p in frontend.rglob("*")
           if p.is_file() and "node_modules" not in p.parts and "dist" not in p.parts}
tracked = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z", "frontend"]).decode().split("\0")
exact = []
for name in filter(None, tracked):
    relative = name.removeprefix("frontend/")
    if relative not in {"vite.config.ts", "playwright.config.ts"}:
        assert (ROOT / name).read_bytes() == (frontend / relative).read_bytes()
        exact.append(relative)
dist = {str(p.relative_to(frontend / "dist")): sha(p.read_bytes())
        for p in (frontend / "dist").rglob("*") if p.is_file()}
result = {
    "fresh_xml": all_xml, "fresh_backend_groups": groups, "backend_modules": len(matrix),
    "snapshot_pairs": pairs,
    "archive_role": "raw archival verification only, not my execution",
    "spec94_sha": digest(manifest["files"]),
    "spec_manifest_sha": sha((archive / "manifest.json").read_bytes()),
    "archived_report_sha": sha((archive / "review-result.md").read_bytes()),
    "archive_xml": archive_xml,
    "frontend": {
        "physical_copy": True, "external_dependency_symlinks": external_links,
        "byte_exact_tracked_files": exact,
        "execution_only_changes": ["vite.config.ts own port/cache/strictPort", "playwright.config.ts own port"],
        "package_lock_sha": sha((frontend / "package-lock.json").read_bytes()), "dist": dist, "dist_sha": digest(dist),
    },
}
(OWN / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: result[k] for k in ("fresh_xml", "fresh_backend_groups", "backend_modules", "snapshot_pairs",
                                       "spec94_sha", "spec_manifest_sha", "archived_report_sha")}, indent=2))
