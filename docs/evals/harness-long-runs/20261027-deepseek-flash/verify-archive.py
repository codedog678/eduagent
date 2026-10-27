"""离线复算归档；不修改原始结果，不调用模型。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


ARCHIVE = Path(__file__).resolve().parent
ROOT = ARCHIVE.parents[3]
sys.path.insert(0, str(ROOT / "python"))

from evals.live_runner import code_revision
from evals.long_task_models import load_long_task_cases, public_case
from evals.long_task_runner import aggregate_live
from evals.long_task_scorers import score_long_task


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def request_cost(usage, rates):
    hit = usage.get("prompt_cache_hit_tokens", 0)
    total = usage["input_tokens"]
    assert 0 <= hit <= total
    return (
        hit * rates["input_hit"]
        + (total - hit) * rates["input_miss"]
        + usage["output_tokens"] * rates["output"]
    ) / 1_000_000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = read(ARCHIVE / "result.json")
    protocol = read(ARCHIVE / "run-protocol.json")
    audit = read(ARCHIVE / "agent-audit.json")
    prior_path = (ARCHIVE / protocol["prior_run"]).resolve()
    prior = read(prior_path)
    cases = load_long_task_cases(ARCHIVE / "dataset.jsonl")
    results = report["live"]["results"]
    assert report["frozen_cases"] == [public_case(case) for case in cases]
    assert report["dataset_revision"] == protocol["dataset_sha256"] == digest(
        ARCHIVE / "dataset.jsonl"
    )
    assert report["dataset_revision"] == prior["dataset_revision"]
    assert report["config"] == prior["config"]
    assert report["config_fingerprint"] == prior["config_fingerprint"]
    assert report["code_revision"]["git_head"] == protocol["runtime_git_head"]
    current_source = code_revision()["python_source_sha256"]
    assert current_source == report["code_revision"]["python_source_sha256"]
    assert report["provider"] == protocol["provider"] == "deepseek"
    assert report["model"] == protocol["model"] == "deepseek-flash"
    assert report["config"]["model_options"]["thinking"] == "disabled"
    assert not report.get("stop_reason")
    assert report["deterministic"]["passed"] == report["deterministic"]["total"] == 8
    assert [row["case_id"] for row in results] == protocol["order"]
    for case, row in zip(cases, results, strict=True):
        assert score_long_task(case, row["observed"]) == row
    assert aggregate_live(results) == report["live"]["metrics"]

    budget = report["budget"]
    rates = budget["pricing"]["per_million_tokens"]
    requests = []
    for row in results:
        for stage_id, stage in row["observed"]["stages"].items():
            assert stage["status"] == "completed"
            for request in stage["model_requests"]:
                assert request["status"] == "completed"
                assert "input_tokens" in request["usage"]
                assert "output_tokens" in request["usage"]
                usage = request["usage"]
                requests.append({
                    "case_id": row["case_id"],
                    "stage_id": stage_id,
                    "request_no": request["request_no"],
                    "kind": request["kind"],
                    "status": request["status"],
                    "role": "task",
                    "usage": usage,
                    "duration_ms": request["duration_ms"],
                    "estimated_off_peak_cny": request_cost(usage, rates["off_peak"]),
                    "estimated_peak_cny": request_cost(usage, rates["peak"]),
                })
    requests.sort(key=lambda row: row["request_no"])
    assert [row["request_no"] for row in requests] == list(range(1, 32))
    assert len(requests) == budget["requests"] == report["live"]["metrics"]["model_calls"]
    totals = {
        key: sum(row["usage"].get(key, 0) for row in requests)
        for key in ("input_tokens", "output_tokens", "prompt_cache_hit_tokens")
    }
    assert totals == budget["usage"]
    for period in ("off_peak", "peak"):
        key = f"estimated_{period}_cny"
        close(sum(row[key] for row in requests), budget[key])
    assert budget["unconfirmed_reservation_cny"] == 0
    assert budget["requests"] <= protocol["max_requests"]
    assert budget["estimated_peak_cny"] <= protocol["max_cny"]
    assert budget["roles"] == {"task": 31, "judge": 0, "reflection": 0}
    assert all(row["metrics"]["model_calls"] <= 20 for row in results)
    assert len(audit["cases"]) == 6
    assert not audit["human_reviewed"] and not audit["independent_model_judge"]
    assert not audit["raw_automatic_scores_modified"]
    for row, reviewed in zip(results, audit["cases"], strict=True):
        assert row["case_id"] == reviewed["case_id"]
        assert row["status"] == reviewed["automatic_status"]
        if reviewed["engineering_outcome"] == "completed":
            assert row["plan_completed"]
    outcome_counts = Counter(row["engineering_outcome"] for row in audit["cases"])
    assert outcome_counts == {"completed": 1, "partial": 1, "failed": 4}
    for outcome in outcome_counts:
        assert audit["summary"][f"engineering_{'lifecycle_completed' if outcome == 'completed' else outcome}"] == outcome_counts[outcome]
    assert audit["summary"]["automatic_passed"] == report["live"]["metrics"]["task_successes"]
    l02_plan = results[1]["observed"]["final"]["plans"][-1]
    assert l02_plan["status"] == "completed" and l02_plan["outcome"] == "partial"
    assert not report["live"]["metrics"]["meets_project_gate"]

    def snapshot(data):
        metrics = data["live"]["metrics"]
        return {
            "generated_at": data["generated_at"],
            "code_revision": data["code_revision"],
            "automatic_metrics": metrics,
            "automatic_status_counts": dict(Counter(
                row["status"] for row in data["live"]["results"]
            )),
            "deterministic_passed": data["deterministic"]["passed"],
            "redundant_calls_numerator": sum(
                row["metrics"]["redundant_tool_calls"] for row in data["live"]["results"]
            ),
            "plan_completion_denominator": sum(
                row["case_id"] != "L01" and bool(row["observed"]["final"]["plans"])
                for row in data["live"]["results"]
            ),
            "recovery_denominator": 2,
            "budget": data["budget"],
            "cases": [{
                "case_id": row["case_id"],
                "automatic_status": row["status"],
                "plan_completed": row["plan_completed"],
                "metrics": row["metrics"],
            } for row in data["live"]["results"]],
        }

    comparison = {
        "schema": "eduagent.harness-long-task-comparison.v1",
        "data_role": protocol["data_role"],
        "same_dataset": True,
        "same_config": True,
        "dataset_sha256": report["dataset_revision"],
        "config_fingerprint": report["config_fingerprint"],
        "prior_result_sha256": digest(prior_path),
        "current_result_sha256": digest(ARCHIVE / "result.json"),
        "prior": snapshot(prior),
        "current": snapshot(report),
        "current_assistant_audit": audit["summary"],
        "deltas": {
            "automatic_passed": 2,
            "model_requests": budget["requests"] - prior["budget"]["requests"],
            "tool_calls": report["live"]["metrics"]["tool_calls"] - prior["live"]["metrics"]["tool_calls"],
            "input_tokens": totals["input_tokens"] - prior["budget"]["usage"]["input_tokens"],
            "output_tokens": totals["output_tokens"] - prior["budget"]["usage"]["output_tokens"],
            "estimated_peak_cny": budget["estimated_peak_cny"] - prior["budget"]["estimated_peak_cny"],
            "estimated_cost_relative_increase": budget["estimated_peak_cny"] / prior["budget"]["estimated_peak_cny"] - 1,
        },
        "limits": [
            "single reused regression run per case; no statistical or holdout claim",
            "L02 automatic pass is partial business output",
            "redundancy counts model-proposed equal-parameter calls divided by runtime after_tool calls; not a semantic waste measure",
            "permission_violations counts selected frozen assertions, not all permission decisions",
            "cost estimates use the same frozen tariff, not provider billing",
        ],
    }
    ledger = {
        "schema": "eduagent.harness-long-task-cost-ledger.v1",
        "run_id": protocol["run_id"],
        "generated_at": report["generated_at"],
        "code_revision": report["code_revision"],
        "dataset_revision": report["dataset_revision"],
        "billing_status": "estimate_only",
        "pricing": budget["pricing"],
        "requests": requests,
        "summary": budget,
    }
    verification = {
        "schema": "eduagent.harness-long-task-verification.v1",
        "run_id": protocol["run_id"],
        "source_result_sha256": digest(ARCHIVE / "result.json"),
        "runtime_git_head": protocol["runtime_git_head"],
        "python_source_sha256": current_source,
        "scorer_sha256": digest(ROOT / "python/evals/long_task_scorers.py"),
        "raw_score_and_aggregate_match": True,
        "validated_cases": len(cases),
        "completed_script_stages": sum(len(row["observed"]["stages"]) for row in results),
        "request_numbers_contiguous": True,
        "request_count": len(requests),
        "all_requests_completed_and_usage_confirmed": True,
        "token_and_cost_totals_match": True,
        "dataset_config_and_model_match_protocol": True,
        "runtime_python_diff_empty_at_archival": not subprocess.check_output(
            ["git", "diff", protocol["runtime_git_head"], "--", "python"], cwd=ROOT
        ).strip(),
        "formal_cli_exit_code": 1,
        "formal_cli_exit_reason": "project_gate_not_met",
        "run_interrupted": False,
        "backend_regression": {
            "passed": 287, "skipped": 2, "duration_seconds": 26.62,
            "warnings": ["existing PytestCollectionWarning for TestAgent"],
            "provider_requests": 0,
            "evidence_origin": "pre-run terminal observation in this session; raw terminal output not archived",
            "rerun_during_archival": False,
        },
        "deterministic_contracts": report["deterministic"],
        "offline_verification_provider_requests": 0,
    }
    assert verification["runtime_python_diff_empty_at_archival"]
    derived = {
        "cost-ledger.json": ledger,
        "comparison-summary.json": comparison,
        "verification.json": verification,
    }
    for name, content in derived.items():
        if args.verify_only:
            assert read(ARCHIVE / name) == content, name
        else:
            (ARCHIVE / name).write_text(
                json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    roles = {
        "dataset.jsonl": "frozen_dataset",
        "protocol.md": "frozen_original_design",
        "run-protocol.json": "frozen_regression_run_protocol",
        "result.json": "unchanged_formal_result",
        "result.md": "unchanged_automatic_report",
        "agent-audit.json": "assistant_offline_audit_not_human_or_independent_judge",
        "analysis.md": "engineering_analysis",
        "cost-ledger.json": "per_request_estimated_cost_ledger",
        "comparison-summary.json": "offline_two_run_comparison",
        "verification.json": "offline_verification_and_execution_metadata",
        "verify-archive.py": "offline_reproduction_script",
    }
    manifest = {
        "schema": "eduagent.harness-long-task-archive.v1",
        "run_id": protocol["run_id"],
        "runtime_git_head": protocol["runtime_git_head"],
        "data_role": protocol["data_role"],
        "model": report["model"],
        "thinking": "disabled",
        "formal_run_generated_at": report["generated_at"],
        "artifacts": {
            name: {"role": role, "sha256": digest(ARCHIVE / name)}
            for name, role in roles.items()
        },
        "notes": [
            "All formal failures retained; no reruns or evolution.",
            "Automatic scores unchanged; assistant engineering audit is separate.",
            "CLI exit 1 means project gate not met; formal run completed.",
            "Source digest includes filesystem Python bytes; includes_working_tree is not a dirty-tree indicator.",
            "Costs are estimates, not provider billing records.",
        ],
    }
    if args.verify_only:
        assert read(ARCHIVE / "manifest.json") == manifest
    else:
        (ARCHIVE / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "verified": True, "cases": 6, "requests": 31,
        "automatic_passed": 2, "engineering_completed": 1,
        "provider_requests_added": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
