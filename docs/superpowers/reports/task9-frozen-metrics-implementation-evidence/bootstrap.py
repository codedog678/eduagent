import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from datetime import UTC, datetime

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
BASE = "ffc607d4908dc50d3d7977d8056a7d33385b78e5"
ARCHIVE = ROOT / "docs/superpowers/reports/task9-chain-spec-failure-evidence"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def write(path, data):
    with path.open("x") as out:
        json.dump(data, out, indent=2)
        out.write("\n")


def metadata(path):
    entries = []
    if path.exists():
        for p in [path, *sorted(path.rglob("*"))]:
            s = p.lstat()
            entries.append((str(p.relative_to(path)), s.st_mode, s.st_size, s.st_mtime_ns, s.st_ino))
    return {"entries": len(entries), "sha256": sha(json.dumps(entries).encode())}


def snapshot():
    result = {}
    for name, root in (("m3", ROOT), ("primary", PRIMARY)):
        tracked = [p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p]
        extra = [p.decode() for p in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
                 if p and p.decode().startswith(("python/", "frontend/"))]
        mapping = {p: sha((root / p).read_bytes()) for p in tracked + extra}
        source = {p: h for p, h in mapping.items() if p.startswith(("python/", "frontend/"))}
        index = Path(git(root, "rev-parse", "--git-path", "index").decode().strip())
        if not index.is_absolute():
            index = root / index
        result[name] = {
            "head": git(root, "rev-parse", "HEAD").decode().strip(),
            "status": git(root, "status", "--porcelain").decode(),
            "tracked": {p: mapping[p] for p in tracked}, "extra_source": extra,
            "source": source, "source_count": len(source),
            "source_sha256": sha(json.dumps(sorted(source.items()), ensure_ascii=True, separators=(",", ":")).encode()),
            "index_sha256": sha(index.read_bytes()), "index_mtime_ns": index.stat().st_mtime_ns,
            "venv": metadata(root / ".venv"),
            "vite": metadata(root / "frontend/node_modules/.vite"),
            "vite_temp": metadata(root / "frontend/node_modules/.vite-temp"),
        }
    return result


if __name__ == "__main__":
    write(OWN / "initial-snapshot.json", snapshot())
    saved = OWN / "inherited"
    saved.mkdir()
    for path in ("python/core/distributed/ops_queries.py", "python/tests/distributed/test_ops_complete_chain.py"):
        target = saved / Path(path).name
        shutil.copy2(ROOT / path, target)
    (saved / "ops_queries.diff").write_bytes(git(ROOT, "diff", "--", "python/core/distributed/ops_queries.py"))
    shutil.copy2("/tmp/m3-task9-recovery-implementation-brief.md", saved / "implementation-brief.md")
    lost = [
        "/tmp/m3-task9-chain-fix-d3d669c4-4da2-41c0-8da8-91e9c4c92192",
        "/tmp/eduagent-m3-patched-runtime",
    ]
    write(OWN / "interruption.json", {
        "observed_at": datetime.now(UTC).isoformat(), "predecessor": "arun_6ae7dc7051536906a0739671",
        "predecessor_killed": "user-confirmed", "lost_paths": {p: Path(p).exists() for p in lost},
        "old_execution_counts_cost_times": "unknown; not reconstructed",
        "inherited_files": {p.name: sha(p.read_bytes()) for p in saved.iterdir()},
    })
    manifest_path = ARCHIVE / "retained-manifest.json"
    assert sha(manifest_path.read_bytes()) == "6c5abd6d891154cb090b2d17db5ea4f693df56374e2c9c650589cf3159e8d1f3"
    manifest = json.loads(manifest_path.read_text())
    files = manifest["files"]
    for p, h in files.items():
        data = (ARCHIVE / p).read_bytes()
        assert sha(data) == h, p
        assert git(ROOT, "show", BASE + ":" + str((ARCHIVE / p).relative_to(ROOT))) == data, p
    assert len(files) == 398
    assert sha(json.dumps(sorted(files.items()), ensure_ascii=True, separators=(",", ":")).encode()) == manifest["payload_sha256"]
    write(OWN / "old-archive-verification.json", {
        "count": len(files), "manifest_sha256": sha(manifest_path.read_bytes()),
        "payload_sha256": manifest["payload_sha256"], "all_payload_gitblob_match": True,
    })
    baseline = OWN / "baseline"
    baseline.mkdir()
    archive_bytes = git(ROOT, "archive", BASE, "--", "python", "frontend", "tools")
    (OWN / "baseline.tar").write_bytes(archive_bytes)
    with tarfile.open(OWN / "baseline.tar") as tar:
        tar.extractall(baseline, filter="data")
    paths = [p.decode() for p in git(ROOT, "ls-tree", "-r", "--name-only", BASE, "--", "python", "frontend").splitlines()]
    mapping = {}
    for p in paths:
        data = (baseline / p).read_bytes()
        assert data == git(ROOT, "show", BASE + ":" + p), p
        mapping[p] = sha(data)
    digest = sha(json.dumps(sorted(mapping.items()), ensure_ascii=True, separators=(",", ":")).encode())
    assert len(mapping) == 353 and digest == "1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65"
    write(OWN / "baseline-gitblob-verification.json", {
        "mode": "BASELINE_REPLAY", "freeze": BASE, "source_count": len(mapping),
        "source_sha256": digest, "source": mapping,
        "extra_test_not_in_baseline": "python/tests/distributed/test_ops_complete_chain.py",
    })
    shutil.copy2(ROOT / "python/tests/distributed/test_ops_complete_chain.py",
                 baseline / "python/tests/distributed/test_ops_complete_chain.py")
    scripts = [
        "review.py", "frontend_run.py", "safety.py", "conftest.py", "live_server.py",
        "test_independent_integrity.py", "test_chain_metadata.py", "test_spec_relations.py",
        "test_spec_corroboration.py", "test_code_attacks.py", "test_extra_code.py",
    ]
    for p in scripts:
        shutil.copy2(ARCHIVE / p, OWN / p)
    front = OWN / "frontend"
    front.mkdir()
    for p in git(ROOT, "ls-files", "-z", "--", "frontend").split(b"\0"):
        if not p:
            continue
        source = ROOT / p.decode()
        dest = front / source.relative_to(ROOT / "frontend")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for p in ("playwright.production.config.ts", "live-e2e/spec-health.spec.ts"):
        dest = front / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ARCHIVE / "frontend" / p, dest)
    print(json.dumps({"own": str(OWN), "initial": {k: v["source_sha256"] for k, v in snapshot().items()},
                      "baseline": digest, "old_payload_count": len(files)}))
