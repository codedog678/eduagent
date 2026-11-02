import hashlib
import io
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from dotenv import dotenv_values
import review

OWN = review.OWN
ROOT = review.ROOT
report = Path("/tmp/m3-task9-complete-chain-spec-result.md")
assert b"WHOLESPECFAIL" in report.read_bytes()
assert not (OWN / "review-result.md").exists()
shutil.copyfile(report, OWN / "review-result.md")
assert report.read_bytes() == (OWN / "review-result.md").read_bytes()
summary = json.loads((OWN / "verification-summary.json").read_text())
resources = json.loads((OWN / "resource-after-cleanup.json").read_text())
assert summary["owned_database_invocations"] == 14
assert all(resources["ports_closed"].values())
assert resources["remaining_owned_browser_processes"] == []
source = json.loads((OWN / "initial-snapshot.json").read_text())
final = json.loads((OWN / "report-freeze-after.json").read_text())
assert {k: final[k] for k in source} == source
values = set()
for root in (ROOT, ROOT.with_name("eduagent")):
    for p in (root / ".env", root / "python/.env", root / ".env.local", root / "python/.env.local"):
        if p.is_file():
            values.update(v.encode() for k, v in dotenv_values(p).items() if v and
                          any(w in k for w in ("API_KEY", "API_TOKEN", "SIGNING_SECRET", "ASSIGNMENT_SECRET")))
files, xml, zip_members = {}, {}, {}
hits = []
for p in sorted(OWN.rglob("*")):
    assert not p.is_symlink(), p
    if not p.is_file():
        continue
    rel = str(p.relative_to(OWN))
    assert rel != "manifest.json"
    data = p.read_bytes()
    files[rel] = review.digest(data)
    if any(v in data for v in values):
        hits.append(rel)
    if p.suffix == ".xml":
        cases = list(ET.fromstring(data).iter("testcase"))
        xml[rel] = {"sha256": files[rel], "tests": len(cases),
                    "failure": sum(c.find("failure") is not None for c in cases),
                    "error": sum(c.find("error") is not None for c in cases),
                    "skip": sum(c.find("skipped") is not None for c in cases)}
    if p.suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
            members = {}
            for member in z.infolist():
                if member.is_dir():
                    continue
                content = z.read(member)
                members[member.filename] = review.digest(content)
                if any(v in content for v in values):
                    hits.append(rel + ":" + member.filename)
            zip_members[rel] = members
assert not hits
minimum_cases = list(ET.parse(OWN / "minimum.xml").getroot().iter("testcase"))
assert all("under-minimum exact Canary evidence must break entire Active chain" in c.find("failure").get("message")
           for c in minimum_cases if c.find("failure") is not None)
manifest = {
    "role": "fresh independent WHOLE Task9 SPEC reviewer retained raw",
    "verdict": "WHOLESPECFAIL", "generated_at": datetime.now(UTC).isoformat(),
    "head": review.HEAD, "product": "9ef34434cc72f270085d234d89eae5f22d3d6ecd",
    "base": "8869166878a193a1c453376471cbe52c8fa84b3f",
    "source_count": 354, "source_sha256": source["m3"]["source_sha256"],
    "files": files, "payload_count": len(files),
    "payload_sha256": review.digest(json.dumps(sorted(files.items()), ensure_ascii=True, separators=(",", ":")).encode()),
    "report_sha256": review.digest(report.read_bytes()),
    "external_report": str(report), "same_byte_report": "review-result.md",
    "xml": xml, "zip_members": zip_members,
    "commands_and_utc": "verification-summary.json suites and *-command.json",
    "invalid_attempts_preserved": ["preparation-attempt-boundary.json", "full.xml", "api291.xml"],
    "valid_product_failures": ["minimum.xml", "prod-minimum-zero.xml"],
    "minimum_unused_local_assert_not_acceptance_basis": True,
    "overlap_not_independent_samples": summary["overlap"],
    "model_calls": 0, "actual_model_cost_usd": "0", "all_http_requests": "unknown",
    "lost_predecessor_run_counts_cost": "unknown",
    "dependency_parent_scan_not_own_execution": True,
    "owned_database_invocations": 14, "cleanup": resources,
    "local_secret_distinct_values": len(values), "secret_hits": hits,
    "manifest_self_excluded": True, "source_hash_excludes_evidence": True}
review.write("manifest.json", manifest)
assert report.read_bytes() == (OWN / "review-result.md").read_bytes()
for p, h in files.items():
    assert review.digest((OWN / p).read_bytes()) == h
print(json.dumps({"verdict": manifest["verdict"], "payload_files": len(files),
                  "payload_sha256": manifest["payload_sha256"],
                  "report_sha256": manifest["report_sha256"],
                  "manifest_sha256": review.digest((OWN / "manifest.json").read_bytes()),
                  "same_bytes": True, "secret_hits": len(hits)}, indent=2))
