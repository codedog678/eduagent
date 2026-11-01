import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OWN = Path(__file__).parent
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def digest(mapping):
    return hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args]).decode().strip()


def tree(root):
    files = git(root, "ls-files", "-z").split("\0")
    files = [p for p in files if p]
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files}
    source = {p: h for p, h in hashes.items() if p.startswith(("python/", "frontend/"))}
    index = Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    return {
        "head": git(root, "rev-parse", "HEAD"),
        "status": git(root, "status", "--porcelain"),
        "index_sha": hashlib.sha256(index.read_bytes()).hexdigest(),
        "index_mtime_ns": index.stat().st_mtime_ns,
        "tracked_sha": digest(hashes),
        "source_count": len(source),
        "source_sha": digest(source),
        "source_authoritative_sha": hashlib.sha256(
            json.dumps(sorted(source.items()), separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest(),
        "source_files": source,
        "git_blob_exact": all(
            subprocess.check_output(["git", "-C", str(root), "show", f"HEAD:{p}"]) == (root / p).read_bytes()
            for p in source
        ),
    }


def metadata(path):
    result = {}
    if path.exists():
        for current, dirs, files in os.walk(path):
            for name in dirs + files:
                p = Path(current) / name
                s = p.lstat()
                result[str(p.relative_to(path))] = [s.st_size, s.st_mtime_ns, s.st_mode]
    return {"count": len(result), "sha": digest(result)}


if __name__ == "__main__":
    state = {
        "m3": tree(ROOT), "primary": tree(PRIMARY),
        "venv": metadata(PRIMARY / ".venv"),
        "m3_vite_temp": metadata(ROOT / "frontend/node_modules/.vite-temp"),
        "m3_vite_cache": metadata(ROOT / "frontend/node_modules/.vite"),
    }
    (OWN / f"{sys.argv[1]}.json").write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps({k: {n: v for n, v in value.items() if n != "source_files"} for k, value in state.items()}, indent=2))
