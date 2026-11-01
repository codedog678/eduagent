"""Generate deterministic Task9 provenance from structured JUnit and file hashes."""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
SOURCES = (
    "frontend/e2e/ops.spec.ts",
    "frontend/src/ops/OpsApp.tsx",
    "frontend/src/ops/PoliciesView.tsx",
    "frontend/src/ops/RunsView.tsx",
    "frontend/src/ops/TraceView.tsx",
    "frontend/src/ops/api.ts",
    "frontend/src/ops/ops.css",
    "frontend/src/ops/types.ts",
    "python/api/ops_routes.py",
    "python/core/distributed/ops_contracts.py",
    "python/core/distributed/ops_queries.py",
    "python/tests/distributed/test_ops_api.py",
    "python/tests/distributed/test_promotion_ops_api.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combined(pairs):
    return hashlib.sha256(json.dumps(
        pairs, ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")).hexdigest()


source_pairs = [(path, digest(ROOT / path)) for path in SOURCES]
files = [
    (str(path.relative_to(EVIDENCE)), digest(path))
    for path in sorted(EVIDENCE.rglob("*"))
    if path.is_file() and path.name != "manifest.json"
]
results = {}
for path in sorted(EVIDENCE.glob("*.xml")):
    root = ET.parse(path).getroot()
    suites = [suite for suite in root.iter("testsuite") if not list(suite.iter("testsuite"))[1:]]
    cases = list(root.iter("testcase"))
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    results[path.name] = {
        "tests": sum(int(suite.get("tests", 0)) for suite in suites),
        "failures": sum(int(suite.get("failures", 0)) for suite in suites),
        "errors": sum(int(suite.get("errors", 0)) for suite in suites),
        "skipped": sum(int(suite.get("skipped", 0)) for suite in suites),
        "suite_seconds": sum(float(suite.get("time", 0)) for suite in suites),
        "testcases": len(cases),
        "passed_testcases": len(cases) - failures - errors - skipped,
        "sha256": digest(path),
    }
manifest = {
    "scope": "Task9 synthetic development verification, not release qualification",
    "source_combined_sha256": combined(source_pairs),
    "source_files": source_pairs,
    "evidence_combined_sha256": combined(files),
    "evidence_files": files,
    "junit": results,
    "python_version": sys.version,
    "python_packages": {
        package: version(package) for package in (
            "pytest", "pytest-asyncio", "SQLAlchemy", "asyncpg", "fastapi", "pydantic", "redis",
        )
    },
    "formal_model_requests": 0,
    "formal_model_cost_usd": "0",
}
(EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({
    "source_combined_sha256": manifest["source_combined_sha256"],
    "evidence_combined_sha256": manifest["evidence_combined_sha256"],
    "junit": results,
    "python_version": sys.version,
    "python_packages": manifest["python_packages"],
}, indent=2))
