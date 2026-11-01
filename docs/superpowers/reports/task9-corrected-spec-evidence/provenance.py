"""Independent frozen identity, raw XML accounting and isolation snapshots."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = Path("/Users/bytedance/Documents/trae_projects/eduagent")
OWN = Path("/tmp/m3-task9-corrected-spec-20261102")
EVIDENCE = OWN / "evidence"
HEAD = "e29bdb4d0c1b0e07b0e60a62ee61df3ae2e9915e"
PARENT = "38f48d763b4a9599aa215f98a2cba1b32003b1e7"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def digest(files):
    return sha(json.dumps(sorted(files.items()), separators=(",", ":"), ensure_ascii=True).encode())


def tracked(root, *paths):
    return {p: sha((root / p).read_bytes()) for p in
            git(root, "ls-files", *paths).decode().splitlines()}


def junit(path):
    root = ET.parse(path).getroot()
    suites = list(root.iter("testsuite"))
    cases = list(root.iter("testcase"))
    counts = {k: sum(int(s.get(k, 0)) for s in suites)
              for k in ("tests", "failures", "errors", "skipped")}
    assert counts["tests"] == len(cases), path
    for k, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
        assert counts[k] == sum(c.find(tag) is not None for c in cases), path
    return counts


def snapshot(label):
    sources = tracked(ROOT, "python", "frontend")
    assert len(sources) == 351
    assert digest(sources) == "8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582"
    assert git(ROOT, "rev-parse", "HEAD").decode().strip() == HEAD
    assert git(ROOT, "rev-parse", "HEAD^").decode().strip() == PARENT
    retained = tracked(ROOT, "docs/superpowers/reports/task9-ops-evidence",
                       "docs/superpowers/reports/task9-gate-order-fix-evidence",
                       "docs/superpowers/reports/2026-11-02-m3-task9-ops.md",
                       "docs/superpowers/reports/2026-11-02-m3-task9-gate-order-fix.md")
    for p, h in {**sources, **retained}.items():
        assert h == sha(git(ROOT, "show", f"HEAD:{p}")), p
    result = {
        "head": HEAD, "parent": PARENT, "m3_status": git(ROOT, "status", "--porcelain").decode(),
        "source": sources, "source_count": len(sources), "source_sha256": digest(sources),
        "retained": retained, "retained_sha256": digest(retained),
        "primary_head": git(PRIMARY, "rev-parse", "HEAD").decode().strip(),
        "primary_status": git(PRIMARY, "status", "--porcelain").decode(),
        "primary_source_sha256": digest(tracked(PRIMARY, "python", "frontend")),
        "protected_mtime_ns": {str(p): p.stat().st_mtime_ns for p in (
            PRIMARY / ".venv", PRIMARY / ".venv/lib/python3.11/site-packages",
            ROOT / "frontend/node_modules/.vite-temp", ROOT / ".git", PRIMARY / ".git/index",
            Path(git(ROOT, "rev-parse", "--git-path", "index").decode().strip()),
        ) if p.exists()},
    }
    assert result["primary_head"] == "2ff803c968d64741d149e5a1ce88a823d4d32422"
    assert result["m3_status"] == result["primary_status"] == ""
    (EVIDENCE / f"{label}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(label, len(sources), digest(sources), "clean")


def frozen():
    for rel, expected_count, expected_hash in (
        ("docs/superpowers/reports/task9-gate-order-fix-evidence", 165,
         "f3dfc50551894f9c5f504cd98b04c1988a40eff2aab379c4b8ba1a88b9afb5fb"),
    ):
        folder = ROOT / rel
        files = {str(p.relative_to(folder)): sha(p.read_bytes())
                 for p in folder.rglob("*") if p.is_file() and p.name != "manifest.json"}
        # Archived historical manifests are retained and included.
        files = {str(p.relative_to(folder)): sha(p.read_bytes()) for p in folder.rglob("*")
                 if p.is_file() and p != folder / "manifest.json"}
        assert len(files) == expected_count
        assert digest(files) == expected_hash
    manifest = json.loads((folder / "manifest.json").read_text())
    assert sha((folder / "manifest.json").read_bytes()) == "9b843383cec0844e90f9ebec9931d056693e35564656b40d35ddb47725c338f0"
    xml = {str(p.relative_to(ROOT)): {"counts": junit(p), "sha256": sha(p.read_bytes())}
           for d in ("task9-ops-evidence", "task9-gate-order-fix-evidence")
           for p in (ROOT / "docs/superpowers/reports" / d).rglob("*.xml")}
    for p in folder.rglob("*.xml"):
        assert junit(p) == manifest["junit"][str(p.relative_to(folder))]
    for p, counts in manifest["original_task9_junit"].items():
        assert junit(ROOT / p) == counts
    changed = git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", HEAD).decode().splitlines()
    assert len(changed) == 169
    assert [p for p in changed if p.startswith(("python/", "frontend/"))] == [
        "python/core/distributed/ops_queries.py", "python/tests/distributed/test_promotion_ops_api.py"]
    result = {"role": "independent archival verification, not rerun",
              "xml": xml, "xml_count": len(xml), "changed_paths": changed,
              "source_diff": git(ROOT, "diff", "HEAD^", "HEAD", "--", "python").decode()}
    (EVIDENCE / "frozen-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print("frozen bytes/37 raw XML/169 paths verified")


def manifest():
    runs = {}
    first = json.loads((EVIDENCE / "review-before.json").read_text())
    last = json.loads((EVIDENCE / "review-after.json").read_text())
    assert first == last
    for p in EVIDENCE.glob("*-before.json"):
        after = p.with_name(p.name.replace("-before.json", "-after.json"))
        assert after.exists(), after
        assert json.loads(p.read_text()) == json.loads(after.read_text()), p
        runs[p.stem.removesuffix("-before")] = "unchanged"
    files = {str(p.relative_to(EVIDENCE)): sha(p.read_bytes()) for p in EVIDENCE.rglob("*")
             if p.is_file() and p != EVIDENCE / "manifest.json"}
    xml = {str(p.relative_to(EVIDENCE)): junit(p) for p in EVIDENCE.rglob("*.xml")}
    result = {"role": "fresh independent full Task9 SPEC reviewer", "head": HEAD, "parent": PARENT,
              "files": files, "retained_count": len(files), "retained_sha256": digest(files),
              "junit": xml, "runs": runs, "source_sha256": first["source_sha256"]}
    (EVIDENCE / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"junit": xml, "runs": runs, "retained_count": len(files),
                      "retained_sha256": digest(files)}, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        snapshot(sys.argv[2])
    else:
        globals()[sys.argv[1]]()
