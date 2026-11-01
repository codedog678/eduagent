"""Capture byte equality and temporary dependency/cache ownership."""
import json
from pathlib import Path
from provenance import ROOT, OWN, EVIDENCE, digest, git, sha

front = OWN / "frontend"
paths = git(ROOT, "ls-files", "frontend").decode().splitlines()
same = {}
for path in paths:
    local = front / Path(path).relative_to("frontend")
    if local.name in {"vite.config.ts", "playwright.config.ts"}:
        continue
    assert local.read_bytes() == (ROOT / path).read_bytes(), path
    same[path] = sha(local.read_bytes())
assert len(same) == 29
for name in ("vite.config.ts", "playwright.config.ts"):
    actual = (front / name).read_text()
    assert actual == (EVIDENCE / "execution-config" / name).read_text()
    expected = (ROOT / "frontend" / name).read_text()
    if name == "vite.config.ts":
        actual = actual.replace("  cacheDir: '/tmp/m3-task9-corrected-spec-20261102/vite-cache',\n", "")
    actual = actual.replace("33290", "3000")
    assert actual == expected, name
assert not (front / "node_modules").is_symlink()
outside = []
for p in (front / "node_modules").rglob("*"):
    if p.is_symlink() and not p.resolve().is_relative_to(OWN.resolve()):
        outside.append(str(p))
assert outside == []
dist = {str(p.relative_to(front / "dist")): sha(p.read_bytes())
        for p in (front / "dist").rglob("*") if p.is_file()}
result = {"tracked_unchanged_count": len(same), "tracked_unchanged": same,
          "configuration_changes": "only own cacheDir and dev port 33290; live port 33291",
          "dependency_symlink": False, "external_dependency_symlinks": outside,
          "dependency_realpath": str((front / "node_modules").resolve()),
          "dist": dist, "dist_sha256": digest(dist),
          "lock_sha256": sha((front / "package-lock.json").read_bytes())}
(EVIDENCE / "frontend-isolation.json").write_text(json.dumps(result, indent=2) + "\n")
print("29 frontend files byte-exact; own dependency bytes; dist", len(dist), digest(dist))
