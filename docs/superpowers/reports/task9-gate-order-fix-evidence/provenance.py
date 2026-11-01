"""Record source identity per run and byte-exact retention, without secrets."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = Path("/Users/bytedance/Documents/trae_projects/eduagent")
EVIDENCE = ROOT / "docs/superpowers/reports/task9-gate-order-fix-evidence"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args]).decode().strip()


def digest(files):
    return sha(json.dumps(sorted(files.items()), separators=(",", ":"), ensure_ascii=True).encode())


def source(root):
    paths = git(root, "ls-files", "python", "frontend").splitlines()
    return {p: sha((root / p).read_bytes()) for p in paths}


def original():
    paths = git(ROOT, "ls-tree", "-r", "--name-only", "38f48d7",
                "docs/superpowers/reports/task9-ops-evidence",
                "docs/superpowers/reports/2026-11-02-m3-task9-ops.md").splitlines()
    result = {}
    for path in paths:
        data = (ROOT / path).read_bytes()
        frozen = subprocess.check_output(["git", "-C", str(ROOT), "show", f"38f48d7:{path}"])
        assert data == frozen, path
        result[path] = sha(data)
    return result


def snapshot(label):
    sources = source(ROOT)
    primary = source(PRIMARY)
    result = {
        "head": git(ROOT, "rev-parse", "HEAD"),
        "source": sources, "source_count": len(sources), "source_sha256": digest(sources),
        "original_task9": original(),
        "primary_head": git(PRIMARY, "rev-parse", "HEAD"),
        "primary_status": git(PRIMARY, "status", "--porcelain"),
        "primary_source_sha256": digest(primary),
        "protected_mtime_ns": {
            str(p): p.stat().st_mtime_ns for p in [
                PRIMARY / ".venv", PRIMARY / ".venv/lib/python3.11/site-packages",
                ROOT / "frontend/node_modules/.vite-temp",
            ] if p.exists()
        },
    }
    (EVIDENCE / f"{label}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(label, result["source_count"], result["source_sha256"])


def junit(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    cases = list(root.iter("testcase"))
    counts = {key: sum(int(s.get(key, 0)) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    assert counts["tests"] == len(cases), path
    for key, tag in [("failures", "failure"), ("errors", "error"), ("skipped", "skipped")]:
        assert counts[key] == sum(c.find(tag) is not None for c in cases), path
    return counts


def manifest():
    files = {str(p.relative_to(EVIDENCE)): sha(p.read_bytes())
             for p in sorted(EVIDENCE.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    xml = {}
    for p in EVIDENCE.rglob("*.xml"):
        xml[str(p.relative_to(EVIDENCE))] = junit(p)
    runs = {}
    for p in sorted(EVIDENCE.glob("*-before.json")):
        after = p.with_name(p.name.replace("-before.json", "-after.json"))
        assert after.exists(), after
        before, end = json.loads(p.read_text()), json.loads(after.read_text())
        for key in ("source", "original_task9", "primary_head", "primary_status",
                    "primary_source_sha256", "protected_mtime_ns"):
            assert before[key] == end[key], (p.name, key)
        runs[p.stem.removesuffix("-before")] = {
            "source_count": before["source_count"], "source_sha256": before["source_sha256"],
            "before": p.name, "after": after.name, "unchanged": True,
        }
    retained = json.loads((EVIDENCE / "independent-retention.json").read_text())
    for entry in retained["retained"]:
        assert files[entry["archive_path"]] == entry["sha256"], entry
        assert sha(Path(entry["original_path"]).read_bytes()) == entry["sha256"], entry
    sources = source(ROOT)
    for label, run in runs.items():
        if not label.startswith("red-gate-order"):
            assert run["source_sha256"] == digest(sources), label
    original_files = original()
    original_xml = {p: junit(ROOT / p) for p in original_files if p.endswith(".xml")}
    valid_red = json.loads((EVIDENCE / "red-gate-order-valid-before.json").read_text())["source"]
    changed = [p for p in sources if valid_red[p] != sources[p]]
    assert changed == ["python/core/distributed/ops_queries.py"], changed
    frozen_ops = subprocess.check_output([
        "git", "-C", str(ROOT), "show", "38f48d7:python/core/distributed/ops_queries.py",
    ])
    assert valid_red["python/core/distributed/ops_queries.py"] == sha(frozen_ops)
    first = json.loads((EVIDENCE / "red-gate-order-before.json").read_text())
    last = json.loads((EVIDENCE / "cleanup-check-after.json").read_text())
    for key in ("original_task9", "primary_head", "primary_status",
                "primary_source_sha256", "protected_mtime_ns"):
        assert first[key] == last[key], key
    result = {
        "role": "authorized repair implementer, not Task9 acceptance reviewer",
        "parent": "38f48d763b4a9599aa215f98a2cba1b32003b1e7",
        "source": sources, "source_count": len(sources), "source_sha256": digest(sources),
        "files": files, "retained_count": len(files), "retained_sha256": digest(files),
        "junit": xml, "runs": runs, "original_task9": original_files,
        "original_task9_junit": original_xml,
        "valid_red_to_green_changed_source": changed,
        "primary_and_original_evidence_preserved_across_entire_repair": True,
        "retained_original_independent_files_still_byte_identical": True,
        "independent_retention": retained,
        "self_exclusion": "manifest excludes itself; source excludes reports/evidence",
    }
    (EVIDENCE / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"source_count": len(sources), "source_sha256": digest(sources),
                      "retained_count": len(files), "retained_sha256": digest(files),
                      "junit": xml, "runs": runs}, indent=2))


if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        snapshot(sys.argv[2])
    elif sys.argv[1] == "manifest":
        manifest()
