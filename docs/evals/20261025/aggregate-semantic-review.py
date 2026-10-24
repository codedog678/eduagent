"""校验已有 AI 审阅标签并汇总指标；不生成语义判断、不发起网络请求。"""

import hashlib
import json
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "tutor-semantic-review-20261025.jsonl"
OUTPUT = ROOT / "tutor-reviewed-metrics-20261025.json"
REPORTS = {
    "baseline": "tutor-live12-20261025.json",
    "v2": "tutor-policy-v2-20261025.json",
    "v3": "tutor-policy-v3-20261025.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(numerator, denominator):
    return {
        "numerator": numerator, "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def resolve(document, pointer):
    assert pointer.startswith("/")
    value = document
    for key in pointer[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate(row, report):
    assert row["schema"] == "eduagent.tutor-semantic-review.v1"
    assert row["review_status"] == "ai_review_completed"
    assert row["reviewer"]["human_reviewed"] is False
    assert row["reviewer"]["additional_provider_requests"] == 0
    assert sha(ROOT / row["source_report"]) == row["source_report_sha256"]
    assert sha(ROOT / row["source_dataset"]) == row["source_dataset_sha256"]
    assert report["dataset_revision"] == row["source_dataset_sha256"]
    assert sha(ROOT / row["rubric_file"]) == row["rubric_sha256"]
    assert row["config_fingerprint"] == report["config_fingerprint"]
    assert row["code_revision"] == report["code_revision"]
    source = report["results"][row["source_result_index"]]
    assert row["case_id"] == source["case_id"]
    assert row["evaluation_role"] == source["evaluation_role"]
    assert row["original_status"] == source["status"]
    assert row["original_automatic_passed"] == source["automatic_passed"]
    definitions = {
        c["case_id"]: c for c in
        (json.loads(line) for line in (ROOT / row["source_dataset"]).read_text().splitlines() if line)
    }
    definition = definitions[row["case_id"]]
    assert row["acceptable_tool_paths"] == definition["acceptable_tool_paths"]
    semantic = [h for h in source["hard_checks"] if h["method"] == "semantic_review"]
    scored = row["semantic_checks"]
    assert {h["id"] for h in semantic} == {h["check_id"] for h in scored}
    assert len(semantic) == len(scored)
    for h, s in zip(semantic, scored):
        assert h["id"] == s["check_id"] and h["rule"] == s["original_rule"]
        assert s["verdict"] in {"passed", "failed", "not_observed"}
        assert s["passed"] is {"passed": True, "failed": False}.get(s["verdict"])
        assert s["confidence"] in {"high", "medium"}
        assert s["rationale"] and s["evidence"]
        for evidence in s["evidence"]:
            content = resolve(report, evidence["source_pointer"])
            assert isinstance(content, str) and evidence["quote"] in content
    passed = (
        source["automatic_passed"] and all(s["passed"] is True for s in scored)
    )
    assert row["task_verdict"] == ("passed" if passed else "failed")
    failed = [h["id"] for h in source["hard_checks"] if h["passed"] is False]
    failed += [s["check_id"] for s in scored if s["verdict"] == "failed"]
    assert row["failed_check_ids"] == failed
    assert row["unobserved_check_ids"] == [
        s["check_id"] for s in scored if s["verdict"] == "not_observed"
    ]
    observed = source["observed"]["steps"]
    converse = {sid: s for sid, s in observed.items() if s.get("action") == "converse"}
    assert Counter(d["step_id"] for d in row["converse_decisions"]) == Counter(converse.keys())
    expected_calls = {
        sid: [c for t in step.get("model_turns", []) for c in t.get("tool_calls", [])]
        for sid, step in converse.items()
    }
    assert len(row["tool_calls"]) == sum(len(c) for c in expected_calls.values())
    actual_ids = [c["id"] for calls in expected_calls.values() for c in calls]
    scored_ids = [c["tool_call_id"] for c in row["tool_calls"]]
    assert Counter(actual_ids) == Counter(scored_ids)
    for tool in row["tool_calls"]:
        call = expected_calls[tool["step_id"]][tool["ordinal"]]
        assert tool["tool_call_id"] == call["id"]
        assert tool["tool_name"] == call["name"]
        assert tool["arguments"] == call["arguments"]
        assert tool["batch_size"] == call["batch_size"]
        assert type(tool["selection_correct"]) is bool
        assert type(tool["arguments_correct"]) is bool
        assert tool["joint_correct"] is (
            tool["selection_correct"] and tool["arguments_correct"]
        )
        assert tool["rationale"]
        assert resolve(report, tool["source_pointer"]) == converse[tool["step_id"]]["model_turns"]
        events = [
            e for a in converse[tool["step_id"]].get("trace", {}).get("attempts", [])
            for e in a["steps"]
            if e["kind"] == "after_tool" and e["tool_call_id"] == tool["tool_call_id"]
        ]
        assert len(events) == 1 and events[0]["status"] == tool["execution_status"]
    for decision in row["converse_decisions"]:
        sid = decision["step_id"]
        round_calls = [c for c in row["tool_calls"] if c["step_id"] == sid]
        names = [c["tool_name"] for c in round_calls]
        assert decision["actual_tool_names"] == names
        assert resolve(report, decision["source_pointer"]) == converse[sid]
        # 原定义明确要求 05/06 首轮澄清；08 搜索、读目标且顺序正确。
        number = int(row["case_id"].split("-")[1])
        missing = (
            ["ask_student"] if number in {5, 6} and sid == "s1"
            and "ask_student" not in names else []
        )
        sequence_ok = True
        if number == 8:
            missing = [name for name in ("search_learning_history", "read_learning_history")
                       if name not in names]
            sequence_ok = not missing and names.index("search_learning_history") < names.index("read_learning_history")
        assert decision["missing_required_tools"] == missing
        assert decision["required_sequence_correct"] is sequence_ok
        assert decision["passed"] is (
            all(c["joint_correct"] for c in round_calls) and not missing and sequence_ok
        )
    return source, definition


def aggregate(rows, sources, definitions):
    tools = [t for r in rows for t in r["tool_calls"]]
    decisions = [d for r in rows for d in r["converse_decisions"]]
    semantics = [s for r in rows for s in r["semantic_checks"]]
    successful = sum(r["task_verdict"] == "passed" for r in rows)
    planned_converse = sum(
        step["action"] == "converse"
        for r in rows for step in definitions[(r["run"], r["case_id"])]["steps"]
    )
    cost = {
        key: sum(m[f"estimated_{key}_cny"]
                 for r in rows for m in sources[(r["run"], r["case_id"])]["metering"])
        for key in ("peak", "off_peak")
    }
    return {
        "case_count": len(rows),
        "original_automatic_case_pass_rate": ratio(
            sum(r["original_automatic_passed"] for r in rows), len(rows)
        ),
        "ai_reviewed_task_success_rate": ratio(successful, len(rows)),
        "failed_cases": [
            {"case_id": r["case_id"], "failed_check_ids": r["failed_check_ids"],
             "unobserved_check_ids": r["unobserved_check_ids"],
             "confidence": r["task_confidence"]}
            for r in rows if r["task_verdict"] == "failed"
        ],
        "semantic_check_verdicts": dict(Counter(s["verdict"] for s in semantics)),
        "tool_selection_accuracy": ratio(sum(t["selection_correct"] for t in tools), len(tools)),
        "tool_argument_semantic_accuracy": ratio(
            sum(t["arguments_correct"] for t in tools), len(tools)
        ),
        "tool_joint_semantic_accuracy": ratio(sum(t["joint_correct"] for t in tools), len(tools)),
        "tool_execution_ok_rate": ratio(
            sum(t["execution_status"] == "ok" for t in tools), len(tools)
        ),
        "incorrect_calls": [
            {"case_id": r["case_id"], **t}
            for r in rows for t in r["tool_calls"] if not t["joint_correct"]
        ],
        "tool_tags": dict(Counter(tag for t in tools for tag in t["tags"])),
        "executed_converse_decision_accuracy": ratio(
            sum(d["passed"] for d in decisions), len(decisions)
        ),
        "planned_converse_count": planned_converse,
        "executed_converse_count": len(decisions),
        "unexecuted_converse_count": planned_converse - len(decisions),
        "failed_converse_decisions": [
            {"case_id": r["case_id"], **d}
            for r in rows for d in r["converse_decisions"] if not d["passed"]
        ],
        "zero_tool_converse_decisions": ratio(
            sum(d["passed"] for d in decisions if not d["actual_tool_names"]),
            sum(not d["actual_tool_names"] for d in decisions),
        ),
        "estimated_cost_cny": cost,
        # 分子包含失败任务的成本，衡量取得一个成功任务的整组资源开销。
        "estimated_cost_cny_per_successful_task": {
            k: v / successful if successful else None for k, v in cost.items()
        },
    }


def main():
    rows = [json.loads(line) for line in REVIEW.read_text().splitlines() if line]
    assert len({(r["run"], r["case_id"]) for r in rows}) == len(rows)
    reports = {run: json.loads((ROOT / filename).read_text()) for run, filename in REPORTS.items()}
    assert {(r["run"], r["case_id"]) for r in rows} == {
        (run, r["case_id"]) for run, report in reports.items() for r in report["results"]
    }
    sources, definitions = {}, {}
    for row in rows:
        assert row["source_report"] == REPORTS[row["run"]]
        source, definition = validate(row, reports[row["run"]])
        sources[(row["run"], row["case_id"])] = source
        definitions[(row["run"], row["case_id"])] = definition
    runs = []
    for run, report in reports.items():
        subset = [r for r in rows if r["run"] == run]
        metrics = aggregate(subset, sources, definitions)
        assert math.isclose(metrics["estimated_cost_cny"]["peak"],
                            report["budget"]["estimated_peak_cny"], abs_tol=1e-12)
        groups = {
            role: aggregate([r for r in subset if r["evaluation_role"] == role], sources, definitions)
            for role in ("agent_primary", "teaching_auxiliary")
        }
        runs.append({
            "run": run, "source_report": REPORTS[run],
            "source_report_sha256": sha(ROOT / REPORTS[run]),
            "policy_version": report["config"].get("tutor_policy_version", "baseline_unversioned"),
            "all_cases": metrics, "groups": groups,
        })
    sensitivity = {}
    for role, number in (("agent_primary", 9), ("teaching_auxiliary", 4)):
        subset = [r for r in rows if r["run"] == "baseline" and r["evaluation_role"] == role]
        successful = sum(r["task_verdict"] == "passed" for r in subset)
        target = next(r for r in subset if int(r["case_id"].split("-")[1]) == number)
        changed = int(target["task_verdict"] == "failed")
        sensitivity[role] = {
            "strict_ai_verdict": ratio(successful, len(subset)),
            f"if_human_accepts_case_{number:02d}": ratio(successful + changed, len(subset)),
        }
    sensitivity["note"] = "Alternative interpretations, not additional experimental samples."
    result = {
        "schema": "eduagent.tutor-reviewed-metrics.v1",
        "review_date": "2026-10-25", "review_status": "ai_review_completed",
        "reviewer": rows[0]["reviewer"],
        "review_file": REVIEW.name, "review_file_sha256": sha(REVIEW),
        "rubric_file": rows[0]["rubric_file"], "rubric_sha256": rows[0]["rubric_sha256"],
        "aggregator_sha256": sha(Path(__file__)),
        "review_coverage": {
            "version_case_records": len(rows),
            "semantic_hard_checks": sum(len(r["semantic_checks"]) for r in rows),
            "tool_calls": sum(len(r["tool_calls"]) for r in rows),
            "executed_converse_decisions": sum(len(r["converse_decisions"]) for r in rows),
        },
        "runs": runs,
        "baseline_borderline_sensitivity": sensitivity,
        "limitations": [
            "Single AI review by an assistant involved in policy changes; no blind or independent human review.",
            "Task labels follow original contracts; tool labels follow the separately documented review rubric.",
            "Variants are reported separately; subset success is not full-suite success.",
            "Per-call accuracy excludes missing calls; executed-converse decisions capture required-tool omissions.",
            "One blocked converse remains a task failure and is not a fabricated executed decision.",
            "Optional low-information tool calls are tagged, not treated as optimal trajectories.",
            "Case 10 denied-read recovery is allowed by its original contract; not proactive refusal.",
            "No repeated-run reliability, public benchmark score, or learner-effect estimate.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(OUTPUT)
    for run in runs:
        print(run["run"],
              "agent TSR=", run["groups"]["agent_primary"]["ai_reviewed_task_success_rate"],
              "teaching TSR=", run["groups"]["teaching_auxiliary"]["ai_reviewed_task_success_rate"],
              "tool joint=", run["all_cases"]["tool_joint_semantic_accuracy"],
              "decisions=", run["all_cases"]["executed_converse_decision_accuracy"])


if __name__ == "__main__":
    main()
