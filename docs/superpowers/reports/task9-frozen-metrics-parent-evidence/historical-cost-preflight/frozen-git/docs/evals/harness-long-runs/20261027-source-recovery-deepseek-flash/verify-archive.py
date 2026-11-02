"""离线复算本轮归档和旧档 v2 派生评分；不请求模型，不修改历史档案。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys


ARCHIVE = Path(__file__).resolve().parent
ROOT = ARCHIVE.parents[3]
sys.path.insert(0, str(ROOT / "python"))

from evals.live_runner import code_revision
from evals.long_task_models import load_long_task_cases, public_case
from evals.long_task_runner import aggregate_live
from evals.long_task_scorers import SCORER_VERSION, score_long_task


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def request_cost(usage, rates):
    hit = usage.get("prompt_cache_hit_tokens", 0)
    total = usage["input_tokens"]
    assert 0 <= hit <= total
    return (
        hit * rates["input_hit"] + (total - hit) * rates["input_miss"]
        + usage["output_tokens"] * rates["output"]
    ) / 1_000_000


def snapshot(data, cases, result_path):
    original = data["live"]["results"]
    assert [row["case_id"] for row in original] == [case.case_id for case in cases]
    rescored = [
        score_long_task(case, row["observed"])
        for case, row in zip(cases, original, strict=True)
    ]
    return {
        "run_id": result_path.parent.name,
        "source_result_sha256": digest(result_path),
        "generated_at": data["generated_at"],
        "code_revision": data["code_revision"],
        "config_fingerprint": data["config_fingerprint"],
        "original_scorer_version": data.get("scorer_version", "unversioned_v1"),
        "original_metrics": data["live"]["metrics"],
        "rescored_version": SCORER_VERSION,
        "rescored_metrics": aggregate_live(rescored),
        "budget": data["budget"],
        "cases": [{
            "case_id": row["case_id"],
            "original_status": old["status"],
            "rescored_status": row["status"],
            "task_success": row["task_success"],
            "plan_completed": row["plan_completed"],
            "assertions": row["assertions"],
            "sources": row["sources"],
            "metrics": row["metrics"],
        } for old, row in zip(original, rescored, strict=True)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    protocol = read(ARCHIVE / "run-protocol.json")
    report = read(ARCHIVE / "result.json")
    audit = read(ARCHIVE / "agent-audit.json")
    execution = read(ARCHIVE / "execution-metadata.json")
    cases = load_long_task_cases(ARCHIVE / "dataset.jsonl")
    results = report["live"]["results"]

    assert report["frozen_cases"] == [public_case(case) for case in cases]
    assert report["dataset_revision"] == protocol["dataset_sha256"] == digest(
        ARCHIVE / "dataset.jsonl"
    )
    assert report["scorer_version"] == protocol["scorer_version"] == SCORER_VERSION
    assert report["code_revision"]["git_head"] == protocol["runtime_git_head"]
    current_source = code_revision()["python_source_sha256"]
    assert current_source == protocol["python_source_sha256"]
    assert current_source == report["code_revision"]["python_source_sha256"]
    assert report["provider"] == protocol["provider"] == "deepseek"
    assert report["model"] == protocol["model"] == "deepseek-flash"
    assert report["config"]["model_options"]["thinking"] == protocol["thinking"] == "disabled"
    assert report["deterministic"]["passed"] == report["deterministic"]["total"] == 8
    assert [row["case_id"] for row in results] == protocol["order"]
    for case, row in zip(cases, results, strict=True):
        assert score_long_task(case, row["observed"]) == row
    assert aggregate_live(results) == report["live"]["metrics"]
    assert not protocol["evolution"]

    # 按原报告计算费用，业务失败或缺失用量均保留，不能假设所有请求成功。
    budget = report["budget"]
    rates = budget["pricing"]["per_million_tokens"]
    requests = []
    for row in results:
        for stage_id, stage in row["observed"]["stages"].items():
            for request in stage["model_requests"]:
                usage = request.get("usage", {})
                confirmed = {"input_tokens", "output_tokens"} <= usage.keys()
                requests.append({
                    "case_id": row["case_id"], "stage_id": stage_id,
                    "request_no": request["request_no"], "kind": request["kind"],
                    "status": request["status"], "error": request.get("error"),
                    "role": "task", "usage": usage,
                    "usage_confirmed": confirmed, "duration_ms": request["duration_ms"],
                    **{
                        f"estimated_{period}_cny": request_cost(usage, rates[period])
                        if confirmed else None
                        for period in ("off_peak", "peak")
                    },
                })
    requests.sort(key=lambda row: row["request_no"])
    assert [row["request_no"] for row in requests] == list(range(1, budget["requests"] + 1))
    assert len(requests) == budget["requests"] == report["live"]["metrics"]["model_calls"]
    confirmed_requests = [row for row in requests if row["usage_confirmed"]]
    usage_keys = set(budget["usage"])
    assert {key: sum(row["usage"].get(key, 0) for row in confirmed_requests)
            for key in usage_keys} == budget["usage"]
    for period in ("off_peak", "peak"):
        key = f"estimated_{period}_cny"
        close(sum(row[key] for row in confirmed_requests), budget[key])
    if len(confirmed_requests) == len(requests):
        close(budget["unconfirmed_reservation_cny"], 0)
    assert budget["max_requests"] == protocol["max_requests"]
    assert budget["max_cny"] == protocol["max_cny"]
    assert budget["requests"] <= protocol["max_requests"]
    assert budget["estimated_peak_cny"] + budget["unconfirmed_reservation_cny"] <= protocol["max_cny"]
    assert budget["roles"] == {"task": len(requests), "judge": 0, "reflection": 0}
    assert all(row["metrics"]["model_calls"] <= protocol["max_requests_per_case"] for row in results)

    assert not audit["human_reviewed"] and not audit["independent_model_judge"]
    assert not audit["raw_automatic_scores_modified"]
    assert len(audit["cases"]) == len(results)
    for row, reviewed in zip(results, audit["cases"], strict=True):
        assert row["case_id"] == reviewed["case_id"]
        assert row["status"] == reviewed["automatic_status"]
        assert reviewed["failed_assertions"] == [
            item["id"] for item in row["assertions"] if not item["passed"]
        ]
        assert any(plan["outcome"] == reviewed["engineering_outcome"]
                   for plan in row["observed"]["final"]["plans"])
        assert row["observed"]["initial"]["knowledge"] == row["observed"]["final"]["knowledge"]
        if reviewed["engineering_outcome"] == "completed":
            assert row["plan_completed"]
        if reviewed["engineering_outcome"] == "awaiting_student":
            # 待答是实际计划状态；澄清问题阻断原交付时，自动任务仍可失败。
            assert any(p["outcome"] == "awaiting_student"
                       for p in row["observed"]["final"]["plans"])
        for evidence_path in reviewed["evidence_paths"]:
            value = report
            for field, index in re.findall(r"([A-Za-z_][A-Za-z_0-9]*)|\[(\d+)\]", evidence_path):
                value = value[field] if field else value[int(index)]
            assert value is not None, evidence_path
    assert audit["summary"]["outcome_counts"] == dict(Counter(
        row["engineering_outcome"] for row in audit["cases"]
    ))
    assert audit["summary"]["automatic_passed"] == report["live"]["metrics"]["task_successes"]
    expected_exit = 0 if report["live"]["metrics"]["meets_project_gate"] else 1
    assert execution["formal_cli_exit_code"] == expected_exit
    assert execution["completed_case_order"] == protocol["order"]
    assert execution["reruns"] == execution["evolution_requests"] == 0

    trace_steps = [
        step for row in results for stage in row["observed"]["stages"].values()
        for attempt in (stage.get("trace") or {}).get("attempts", []) for step in attempt["steps"]
    ]
    branch_counts = {
        "unnecessary_assessment_simplification": sum(
            step["kind"] == "plan_simplified"
            and step.get("reason") == "unnecessary_assessment" for step in trace_steps),
        "unread_source_draft_repair": sum(
            step["kind"] == "expert_draft_repair"
            and step.get("reason") == "unread_source" for step in trace_steps),
        "invalid_schema_draft_repair": sum(
            step["kind"] == "expert_draft_repair"
            and step.get("reason") == "invalid_schema" for step in trace_steps),
        "unread_source_draft_rejection": sum(
            step["kind"] == "expert_draft_rejected"
            and any(error.get("type") == "unread_source"
                    for error in step.get("errors", [])) for step in trace_steps),
        "planner_fallback": sum(step["kind"] == "plan_fallback" for step in trace_steps),
        "nonblocking_practice_clarification": sum(
            step["kind"] == "plan_fallback"
            and step.get("reason") == "nonblocking_practice_clarification" for step in trace_steps),
        "tutor_output_repair": sum(step["kind"] == "tutor_output_repair" for step in trace_steps),
        "required_practice_action_repair": sum(
            step["kind"] == "expert_draft_repair"
            and step.get("reason") == "required_practice_action_missing" for step in trace_steps),
    }
    assert audit["summary"]["live_branch_counts"] == branch_counts
    assessments = [item["body"] for item in results[4]["observed"]["final"]["evidence"]
                   if item["kind"] == "assessment"]
    assert len(assessments) == 2
    assert all(item["assisted"] and not item["independent"] and not item["mastery_updated"]
               for item in assessments)
    assert sorted(item["is_correct"] for item in assessments) == [False, True]

    current_path = ARCHIVE / "result.json"
    snapshots, prior_verification = [], []
    for relative_path in protocol["prior_runs"]:
        path = (ARCHIVE / relative_path).resolve()
        original = read(path)
        manifest = read(path.parent / "manifest.json")
        for name, info in manifest["artifacts"].items():
            assert digest(path.parent / name) == info["sha256"], (path.parent.name, name)
        assert original["dataset_revision"] == report["dataset_revision"]
        assert original["config"] == report["config"]
        assert original["config_fingerprint"] == report["config_fingerprint"]
        assert original["budget"]["pricing"] == budget["pricing"]
        prior_verification.append({
            "run_id": path.parent.name, "manifest_sha256": digest(path.parent / "manifest.json"),
            "validated_artifacts": len(manifest["artifacts"]), "all_hashes_match": True,
        })
        snapshots.append(snapshot(original, cases, path))
    snapshots.append(snapshot(report, cases, current_path))
    previous, current = snapshots[-2], snapshots[-1]
    comparison = {
        "schema": "eduagent.harness-long-task-comparison.v2",
        "scorer_version": SCORER_VERSION, "data_role": protocol["data_role"],
        "same_dataset": True, "same_config": True, "same_frozen_tariff": True,
        "dataset_sha256": report["dataset_revision"],
        "runs": snapshots, "prior_archive_hash_verification": prior_verification,
        "current_assistant_audit": audit["summary"],
        "deltas_from_previous_same_scorer": {
            "task_successes": current["rescored_metrics"]["task_successes"]
            - previous["rescored_metrics"]["task_successes"],
            "model_requests": budget["requests"] - previous["budget"]["requests"],
            "tool_calls": current["rescored_metrics"]["tool_calls"]
            - previous["rescored_metrics"]["tool_calls"],
            "estimated_peak_cny": budget["estimated_peak_cny"]
            - previous["budget"]["estimated_peak_cny"],
            "estimated_cost_relative_change": budget["estimated_peak_cny"]
            / previous["budget"]["estimated_peak_cny"] - 1,
        },
        "limits": [
            "Reused six engineering regression cases, one live run per case, not holdout or statistical evidence.",
            "Prior observed data rescored offline only; original archives and automatic scores unchanged.",
            "Assistant audit is not human review or an independent model judge.",
            "Redundancy is equal-parameter model calls divided by runtime after_tool calls, not semantic waste.",
            "Permission violations count selected frozen assertions, not all permissions.",
            "Costs use a frozen estimated tariff, not provider billing; unconfirmed reservations remain explicit.",
        ],
    }
    ledger = {
        "schema": "eduagent.harness-long-task-cost-ledger.v2",
        "run_id": protocol["run_id"], "generated_at": report["generated_at"],
        "code_revision": report["code_revision"], "dataset_revision": report["dataset_revision"],
        "billing_status": "estimate_only", "pricing": budget["pricing"],
        "requests": requests, "summary": budget,
    }
    verification = {
        "schema": "eduagent.harness-long-task-verification.v2",
        "run_id": protocol["run_id"], "source_result_sha256": digest(current_path),
        "runtime_git_head": protocol["runtime_git_head"],
        "python_source_sha256": current_source,
        "scorer_version": SCORER_VERSION,
        "scorer_sha256": digest(ROOT / "python/evals/long_task_scorers.py"),
        "raw_score_and_aggregate_match": True, "validated_cases": len(cases),
        "recorded_script_stages": sum(len(row["observed"]["stages"]) for row in results),
        "stage_status_counts": dict(Counter(
            stage["status"] for row in results for stage in row["observed"]["stages"].values()
        )),
        "request_numbers_contiguous": True, "request_count": len(requests),
        "request_status_counts": dict(Counter(row["status"] for row in requests)),
        "confirmed_usage_requests": len(confirmed_requests),
        "unconfirmed_usage_requests": len(requests) - len(confirmed_requests),
        "token_and_cost_totals_match": True,
        "dataset_config_and_model_match_protocol": True,
        "runtime_python_diff_empty_at_archival": not subprocess.check_output(
            ["git", "diff", protocol["runtime_git_head"], "--", "python"], cwd=ROOT
        ).strip(),
        "execution": execution, "run_stop_reason": report.get("stop_reason"),
        "backend_regression": {
            "passed": 370, "skipped": 2,
            "warnings": ["existing PytestCollectionWarning for TestAgent"],
            "provider_requests": 0, "evidence": "backend-regression.txt",
        },
        "deterministic_contracts": report["deterministic"],
        "prior_archive_hash_verification": prior_verification,
        "offline_verification_provider_requests": 0,
        "all_cases_knowledge_state_unchanged": True,
        "guided_assessment_count": len(assessments),
        "live_repair_branch_counts": branch_counts,
        "current_conversation_formal_totals": {
            "requests": protocol["current_conversation_tracked_before_run"]["formal_requests"]
            + len(requests),
            "estimated_peak_cny": protocol["current_conversation_tracked_before_run"]
            ["formal_estimated_peak_cny"] + budget["estimated_peak_cny"],
            "other_test_network_usage": "C34 unmetered usage and possible charge unknown",
        },
    }
    assert verification["runtime_python_diff_empty_at_archival"]
    for name, content in {
        "cost-ledger.json": ledger, "comparison-summary.json": comparison,
        "verification.json": verification,
    }.items():
        if args.verify_only:
            assert read(ARCHIVE / name) == content, name
        else:
            (ARCHIVE / name).write_text(
                json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    roles = {
        "dataset.jsonl": "frozen_dataset",
        "protocol.md": "frozen_run_protocol",
        "run-protocol.json": "frozen_machine_readable_protocol",
        "backend-regression.txt": "pre_run_backend_test_output",
        "dataset-validation.json": "pre_run_dataset_validation",
        "formal-run.txt": "unchanged_formal_cli_output",
        "execution-metadata.json": "observed_formal_execution_metadata",
        "result.json": "unchanged_formal_result",
        "result.md": "unchanged_automatic_report",
        "agent-audit.json": "assistant_offline_audit_not_human_or_independent_judge",
        "analysis.md": "engineering_analysis",
        "cost-ledger.json": "per_request_estimated_cost_ledger",
        "comparison-summary.json": "offline_eight_run_comparison_with_scorer_v2",
        "verification.json": "offline_verification",
        "verify-archive.py": "offline_reproduction_script",
    }
    assert {p.name for p in ARCHIVE.iterdir() if p.is_file()} - {"manifest.json"} == set(roles)
    manifest = {
        "schema": "eduagent.harness-long-task-archive.v2",
        "run_id": protocol["run_id"], "runtime_git_head": protocol["runtime_git_head"],
        "data_role": protocol["data_role"], "model": report["model"],
        "thinking": protocol["thinking"], "scorer_version": SCORER_VERSION,
        "formal_run_generated_at": report["generated_at"],
        "artifacts": {name: {"role": role, "sha256": digest(ARCHIVE / name)}
                      for name, role in roles.items()},
        "notes": [
            "Failures retained; no reruns or evolution.",
            "Formal scores unchanged; historical v2 rescoring is derived only.",
            "Runtime/source/model/data/limits frozen before live evaluation.",
            "All archive files except this manifest have SHA256 entries.",
            "Costs are estimated, not provider billing records.",
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
        "verified": True, "cases": len(cases), "requests": len(requests),
        "automatic_passed": report["live"]["metrics"]["task_successes"],
        "historical_v2_passed": [
            item["rescored_metrics"]["task_successes"] for item in snapshots[:-1]
        ],
        "provider_requests_added": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
