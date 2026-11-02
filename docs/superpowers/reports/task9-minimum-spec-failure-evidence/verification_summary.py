import hashlib
import json
from pathlib import Path
from datetime import UTC, datetime
from xml.etree import ElementTree as ET
import review

OWN = review.OWN


def load(name):
    return json.loads((OWN / name).read_text())


initial = load("initial-snapshot.json")
final = load("final-after.json")
assert {k: final[k] for k in initial} == initial
pairs = {}
for before in OWN.glob("*-before.json"):
    label = before.name.removesuffix("-before.json")
    after = OWN / (label + "-after.json")
    if after.is_file():
        a, b = json.loads(before.read_text()), json.loads(after.read_text())
        assert {k: a[k] for k in initial} == initial
        assert {k: b[k] for k in initial} == initial
        pairs[label] = {"before_sha256": review.digest(before.read_bytes()),
                        "after_sha256": review.digest(after.read_bytes()), "equal_protected": True}
suites, identities = {}, {}
for p in OWN.glob("*.xml"):
    cases = list(ET.parse(p).getroot().iter("testcase"))
    label = p.stem
    key = {(c.get("classname"), c.get("name")) for c in cases}
    identities[label] = key
    cmd = OWN / (label + "-command.json")
    suites[label] = {"tests": len(cases), "passed": sum(not any(e.tag in {"failure", "error", "skipped"} for e in c) for c in cases),
                    "failures": sum(c.find("failure") is not None for c in cases),
                    "errors": sum(c.find("error") is not None for c in cases),
                    "skips": sum(c.find("skipped") is not None for c in cases),
                    "sha256": review.digest(p.read_bytes()), "command": json.loads(cmd.read_text()) if cmd.exists() else None}
assert suites["full-final"]["passed"] == 1840 and suites["api-final"]["passed"] == 291
assert suites["integrity-metadata"]["passed"] == 64
assert suites["minimum"]["failures"] == 3 and suites["minimum"]["passed"] == 1
assert suites["prod-minimum-zero"]["failures"] == 2
assert suites["ui54-screenshots"]["passed"] == 54
prod = [s for k, s in suites.items() if k.startswith("prod-") and k != "prod-minimum-zero"]
assert len(prod) == 6 and sum(s["passed"] for s in prod) == 12
minimum = {}
for p in (OWN / "minimum").glob("minimum-*.json"):
    proof = json.loads(p.read_text())
    assert proof["repository_accepts"] == proof["expected_trusted"]
    shown = [r for r in proof["active"]["gate_receipts"] if r["health_source"]]
    assert len(shown) == 2
    local = [r for r in proof["local"]["gate_receipts"] if r["health_source"] and r["status"] == "passed"]
    assert len(local) == 2
    minimum[p.name] = {"candidate": proof["candidate_count"], "stable": proof["stable_count"],
                       "repository_accepts": proof["repository_accepts"],
                       "actual_active_sources": len(shown), "actual_local_passed_sources": len(local),
                       "exact_receipt": proof["exact_receipt"], "exact_cost": proof["exact_cost"]}
dep = load("dependency-independent-check.json")
resources = load("resource-before-shutdown.json")
history = load("historical-and-recovery-raw-audit.json")
viewed = [f"screenshots/detail-{scenario}-{viewport}-left.png"
          for scenario in ("prod-current", "prod-history", "prod-synthetic", "prod-genuine-malformed",
                           "prod-genuine-valid", "prod-referenced-poison", "prod-minimum-zero")
          for viewport in ("desktop", "mobile")]
viewed += [f"screenshots/{name}-{viewport}.png" for name in ("policies", "policy-trace")
           for viewport in ("desktop", "mobile")]
assert all((OWN / p).is_file() for p in viewed)
summary = {
    "time": datetime.now(UTC).isoformat(), "role": "fresh independent WHOLE Task9 SPEC", "verdict": "WHOLESPECFAIL",
    "scope": review.HEAD, "base": "8869166878a193a1c453376471cbe52c8fa84b3f",
    "protected": {k: {"head": v["head"], "tracked": len(v["tracked"]), "source": v["source_count"],
                       "source_sha256": v["source_sha256"], "index_sha256": v["index_sha256"],
                       "index_mtime_ns": v["index_mtime_ns"], "venv": v["venv"],
                       "vite": v["vite"], "vite_temp": v["vite_temp"]} for k, v in initial.items()},
    "pairs": pairs, "final_equals_initial": True, "suites": suites, "minimum": minimum,
    "overlap": {"full_api_shared_identities": len(identities["full-final"] & identities["api-final"]),
                "api_only_identities": len(identities["api-final"] - identities["full-final"]),
                "ui_repeated_identities": len(identities["ui54"] & identities["ui54-screenshots"])},
    "dependencies": {"installed": dep["installed_count"], "constraints": len(dep["constraints"]),
                     "matched": all(c["matches"] for c in dep["constraints"]),
                     "parent_vulnerability_scan_not_my_execution": True},
    "owned_database_invocations": len(resources["postgres"]["declared_owned"]),
    "redis_recorded_exact_keys": len(resources["recorded_exact_keys"]),
    "redis_remaining_keys_before_shutdown": len(resources["actual_remaining_keys"]),
    "redis_unrecorded_remaining_keys": resources["remaining_unrecorded_keys"],
    "historical_files_byteexact": len(history["files"]),
    "historical_xml_count": sum(p.endswith(".xml") for p in history["files"]),
    "historical_trace_zip_count": sum(p.endswith(".zip") for p in history["files"]),
    "images_personally_viewed": [{"path": p, "sha256": review.digest((OWN / p).read_bytes())} for p in viewed],
    "model_calls": 0, "model_cost_usd": "0", "all_http_requests": "unknown",
    "interrupted_predecessor_counts_cost": "unknown; cannot reconstruct missing tmp"}
review.write("verification-summary.json", summary)
print(json.dumps({k: v for k, v in summary.items() if k not in ("suites", "pairs", "images_personally_viewed", "protected")}, indent=2))
