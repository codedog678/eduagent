import json
from pathlib import Path
import re
from datetime import UTC, datetime

from review import OWN, digest, write

result_path = Path("/tmp/m3-task9-source-integrity-spec-result.md")
text = result_path.read_text()
inventory = json.loads((OWN / "independent-verification.json").read_text())
assert text.startswith("# WHOLE Task9 SPEC FAIL")
assert len(inventory["suites"]) == 16
assert len(inventory["snapshots"]) == 34
assert "16自有XML" in text
assert "第35份" in text
assert json.loads((OWN / "final-source-after.json").read_text()) == json.loads((OWN / "full-before.json").read_text())
for name, suite in inventory["suites"].items():
    sha = suite["sha256"]
    assert sha in text, name
    assert digest((OWN / name).read_bytes()) == sha
    row = next(line for line in text.splitlines() if sha in line and line.startswith("|"))
    count = "/".join(str(suite[k]) for k in ("tests", "passed", "failures", "errors", "skips"))
    assert count in row, (name, count)
for match in re.finditer(r"\b[0-9a-f]{50,}\b", text):
    assert len(match.group()) in {64}, match.group()
proof = json.loads((OWN / "independent-integrity/referenced-active-sample_count.json").read_text())
assert proof["actual_hash"] == proof["stored_hash"]
assert proof["actual_hash"] in text
assert proof["referenced_health"] in text and proof["original_health"] in text
assert proof["poison"] == {"sample_count": 0}
assert len([r for r in proof["body"]["gate_receipts"] if r["health_source"]]) == 1
assert inventory["accounting"]["actual_model_requests"] == 0
assert inventory["accounting"]["page_http"] == 72
assert inventory["accounting"]["explicit_context_http"] == 50
cleanup = json.loads((OWN / "cleanup-verification.json").read_text())
assert len(cleanup["exact_databases"]) == 14
assert len(cleanup["exact_streams"]) == 248
assert not cleanup["db_remaining"] and not any(cleanup["redis_after"].values())
assert all(cleanup["ports_connect_ex"].values())
for removed in cleanup["removed_own_paths"]:
    assert not (OWN / removed).exists()
assert len(json.loads((OWN / "own-trace-audit.json").read_text())) == 70
if (OWN / "review-result.md").exists():
    assert (OWN / "review-result.md").read_bytes() == result_path.read_bytes()
record = {"recorded_at": datetime.now(UTC).isoformat(), "result_path": str(result_path),
          "result_sha256": digest(result_path.read_bytes()), "conclusion": "WHOLESPECFAIL",
          "xml_count": 16, "xml_sha_and_counts_match_report": True,
          "source_snapshots": 35, "final_snapshot_equal": True,
          "actual_model_requests": 0, "cleanup_verified": True, "raw_evidence_retained": True}
write("final-check.json", record)
print(json.dumps(record, indent=2))
