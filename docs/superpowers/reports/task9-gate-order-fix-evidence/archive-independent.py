"""Retain the independent FAIL and sufficient raw material, byte for byte."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
DEST = ROOT / "docs/superpowers/reports/task9-gate-order-fix-evidence"
ORIGIN = Path("/tmp/m3-task9-spec-independent")
retained = []


def retain(src, relative):
    dst = DEST / relative
    assert not dst.exists(), dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert src.read_bytes() == dst.read_bytes()
    retained.append({
        "original_path": str(src), "archive_path": relative,
        "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
        "bytes": dst.stat().st_size,
    })


for name in ("m3-task9-spec-review-result.md", "m3-task9-gate-order-fix-brief.md",
             "m3-task9-implementer-result.md"):
    retain(Path("/tmp") / name, "independent/" + name)
for src in sorted(ORIGIN.rglob("*")):
    if not src.is_file():
        continue
    relative = src.relative_to(ORIGIN)
    if relative.parts[0] == "frontend" and not (
        relative.parts[1] == "live-e2e" or relative.name in {
            "playwright.config.ts", "playwright.live.config.ts", "vite.config.ts",
            "package.json", "package-lock.json",
        }
    ):
        continue
    retain(src, "independent/" + str(relative))

(DEST / "independent-retention.json").write_text(json.dumps({
    "retained": retained,
    "scope": "FAIL full text; all extant top-level raw logs/XML/fixture JSON/probes/runners; "
             "screenshots and failed traces; live e2e and frontend execution configuration",
    "not_retained": "Original frontend source/e2e copy, already removed node_modules, "
                    "dist and caches. Original independent-manifest.json is historical "
                    "and does not assert full retention here.",
    "isolation_exception": "Independent reviewer initially symlinked node_modules; "
                           "M3 ignored .vite-temp mtime was touched. Reviewer disclosed "
                           "this and reran with a physical tmp copy. Original FAIL section 7 retained verbatim.",
}, indent=2) + "\n")
print("independent retained", len(retained))
