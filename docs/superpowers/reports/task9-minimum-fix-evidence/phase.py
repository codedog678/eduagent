import sys
import bootstrap
import review

result = bootstrap.snapshot()
initial = __import__("json").loads((review.OWN / "initial-snapshot.json").read_text())
assert result["primary"] == initial["primary"]
for key in ("venv", "vite", "vite_temp"):
    assert result["m3"][key] == initial["m3"][key]
changed = {p for p, h in result["m3"]["tracked"].items()
           if initial["m3"]["tracked"].get(p) != h}
changed.update(result["m3"]["extra_source"])
assert changed <= {
    "python/core/distributed/ops_queries.py",
    "python/tests/distributed/test_ops_minimum_evidence.py",
}, changed
review.write(sys.argv[1] + ".json", result)
print(result["m3"]["source_count"], result["m3"]["source_sha256"], sorted(changed))
