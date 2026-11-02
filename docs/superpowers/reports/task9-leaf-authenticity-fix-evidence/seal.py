import json
from pathlib import Path
import shutil
import sys
from datetime import UTC, datetime

import artifact_checks
import bootstrap
import review

OWN, ROOT = review.OWN, review.ROOT
DEST = ROOT / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence"
REPORT = ROOT / "docs/superpowers/reports/2026-11-02-m3-task9-leaf-authenticity-fix.md"
TMP_REPORT = Path("/tmp/m3-task9-leaf-authenticity-fix-result.md")


def files():
    result = {}
    for p in sorted(OWN.rglob("*")):
        if p.is_symlink():
            raise AssertionError(str(p))
        if p.is_file() and p != OWN / "manifest.json":
            result[str(p.relative_to(OWN))] = review.digest(p.read_bytes())
    return result


def prepare():
    assert not (OWN / "manifest.json").exists()
    scan = artifact_checks.scan((name, (OWN / name).read_bytes()) for name in files())
    review.write("raw-secret-scan.json", {**scan, "time": datetime.now(UTC).isoformat(),
                 "scope": "all owned retained bytes, including every ZIP member; actual secrets never output"})
    review.write("seal-command.json", dict(command=[review.PY, str(OWN / "seal.py"), "prepare"],
                 cwd=str(OWN), time=datetime.now(UTC).isoformat(), model_calls=0,
                 model_cost_usd="0", http_total="unknown", role="implementer evidence sealing"))
    mapping = files()
    freeze = json.loads((OWN / "product-freeze.json").read_bytes())
    review.write("manifest.json", dict(schema_version=1, files=mapping, file_count=len(mapping),
        payload_sha256=review.digest(json.dumps(sorted(mapping.items()), ensure_ascii=True,
                              separators=(",", ":")).encode()),
        product=freeze["product"], parent=freeze["parent"], source_count=freeze["source_count"],
        source_sha256=freeze["source_sha256"], role="implementer engineering evidence; independent reviews pending",
        model_calls=0, model_cost_usd="0", http_total="unknown",
        self_and_report_excluded="manifest cannot hash itself; same-byte report separately verified in postcommit sidecar"))
    manifest = OWN / "manifest.json"
    print(json.dumps({"file_count": len(mapping), "manifest_sha256": review.digest(manifest.read_bytes()),
                      "payload_sha256": json.loads(manifest.read_bytes())["payload_sha256"], "scan": scan}))


def persist():
    manifest = json.loads((OWN / "manifest.json").read_bytes())
    assert files() == manifest["files"], "raw changed after seal"
    assert TMP_REPORT.is_file() and not DEST.exists() and not REPORT.exists()
    shutil.copytree(OWN, DEST)
    shutil.copy2(TMP_REPORT, REPORT)
    for name, digest in manifest["files"].items():
        assert review.digest((DEST / name).read_bytes()) == digest
    assert (DEST / "manifest.json").read_bytes() == (OWN / "manifest.json").read_bytes()
    assert REPORT.read_bytes() == TMP_REPORT.read_bytes()
    print(json.dumps({"archive": str(DEST), "raw_count": manifest["file_count"],
        "report_sha256": review.digest(REPORT.read_bytes()),
        "manifest_sha256": review.digest((DEST / "manifest.json").read_bytes())}))


if __name__ == "__main__":
    {"prepare": prepare, "persist": persist}[sys.argv[1]]()
