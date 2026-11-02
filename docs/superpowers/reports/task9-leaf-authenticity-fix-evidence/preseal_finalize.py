import json
from pathlib import Path
import shutil
from datetime import UTC, datetime

import review

own = Path(__file__).parent
source = Path("/Users/bytedance/Library/Application Support/Trae CN/ModularData/ai-agent/command-execution/38530c7104d2ff50a52112ff28126387/output.log")
assert source.is_file()
shutil.copy2(source, own / "product-commit-tool.log")
review.write("product-commit-command.json", {
    "command_id": "38530c7104d2ff50a52112ff28126387",
    "command": "git commit -F - <<'EOF' (message below) EOF",
    "message": "fix(ops): authenticate complete bounded frozen health leaves\n\nShare pure canonical identity and cohort/window relationships with promotion\nvalidation. Reject invalid precise Active consumption without discarding valid\nlocal history or replacement evidence. Add 47 complete read-only PG HTTP GET\nregressions across both cohorts and gates.\n\nImplementer verification: backend 1911, API 362, integrity 131, final overlapping\nleaf/minimum 90, Node 20 build, UI 54 and PG production 24 pass. Evidence follows\nin a separate new documentation commit; independent Task9 acceptance pending.\n",
    "cwd": str(review.ROOT), "exit": 0, "observed_at": datetime.now(UTC).isoformat(),
    "precise_start_finish": "unknown; Git commit timestamps are actual Git metadata",
    "normal_hooks": True, "amend_push_config_or_bypass": False,
    "model_calls": 0, "model_cost_usd": "0",
})
review.write("cost-and-role-ledger.json", {
    "started_at": json.loads((own / "implementation-identity.json").read_bytes())["started_at"],
    "recorded_at": datetime.now(UTC).isoformat(),
    "role": "fresh leaf-fix implementer; not SPEC/CODE reviewer",
    "actual_model_requests": 0, "actual_model_cost_usd": "0",
    "http_total": "unknown; do not reinterpret uninstrumented or mocked HTTP as zero",
    "fixture_usd": "synthetic frozen evidence; not actual provider billing",
    "evaluation_role": "engineering development fixtures/replay, no liveprovider or release qualification",
    "Agent50": "paused; no new invocation",
    "production_http_count_scope": "final-verification.json browser GET counts and explicit request-context GETs; invalid configuration attempt also retained; API/full suites overlap",
    "unit_test_workflow_scope": "47 new tests are real PG HTTP API integration; no unit tests modified",
    "visual_selection_counts": "final-visual4.xml contains 2 Trace tests; final-policy-visual2.xml contains 2 Policies tests, not 4 each",
    "review_execution_metadata_note": "new_complete_get_regression inherited snapshot field names minimum file; actual commands/XML prove authenticity test inclusion",
    "obsolete_script_mains": "bootstrap.py/prepare.py are inherited utilities, only snapshot/metadata/pg_identity/verify_blobs functions used this run; their old setup main is not to be executed",
    "limitations": ["No Docker install or CI run claim", "No Task10 work",
                   "normal hook hardcoded two-second time limit is not proof of full scan",
                   "source SHA excludes docs/evidence to avoid circular hashes",
                   "self-containing documentation commit HEAD is resolved externally after normal commit"],
})
