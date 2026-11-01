"""Independently verify historical RED/GREEN provenance; never rerun it."""
import json
from provenance import ROOT, EVIDENCE, sha

folder = ROOT / "docs/superpowers/reports/task9-gate-order-fix-evidence"
pairs = {}
for before in folder.glob("*-before.json"):
    after = before.with_name(before.name.replace("-before.json", "-after.json"))
    assert after.exists()
    a, b = json.loads(before.read_text()), json.loads(after.read_text())
    assert a == b, before
    pairs[before.stem.removesuffix("-before")] = {
        "before_sha256": sha(before.read_bytes()),
        "after_sha256": sha(after.read_bytes()),
        "same_parsed_state": True,
    }
assert len(pairs) == 13
red = json.loads((folder / "red-gate-order-valid-before.json").read_text())
green = json.loads((folder / "green-gate-order-before.json").read_text())
changes = [p for p in red["source"] if red["source"][p] != green["source"][p]]
assert changes == ["python/core/distributed/ops_queries.py"]
assert red["source"].keys() == green["source"].keys()
for p in ("primary_head", "primary_source_sha256", "primary_status",
          "protected_mtime_ns", "original_task9"):
    assert red[p] == green[p]
test = "python/tests/distributed/test_promotion_ops_api.py"
assert green["source"][test] == sha((ROOT / test).read_bytes())
assert green["source_sha256"] == "8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582"
result = {
    "role": "archival independent byte/state verification only, not fresh execution",
    "snapshot_pairs": pairs, "red_to_green_changed_sources": changes,
    "red_green_and_frozen_test_sha256": green["source"][test],
    "original_fail_report_sha256": sha((folder / "independent/m3-task9-spec-review-result.md").read_bytes()),
}
(EVIDENCE / "archive-provenance-check.json").write_text(json.dumps(result, indent=2) + "\n")
print("13 archival pairs identical; valid RED/GREEN changed only OpsQueries; tests match frozen bytes")
