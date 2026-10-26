"""校验 50 条 AI 审阅标签并复算指标；不执行模型或生成语义裁定。"""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
DATASET = ROOT.parents[1] / "tutor-agent-50-review.jsonl"
MANIFEST = ROOT.parents[1] / "tutor-agent-50-manifest.json"
RAW = ROOT / "tutor-agent50-live.json"
LABELS = ROOT / "tutor-agent50-semantic-review.jsonl"
OUTPUT = ROOT / "tutor-agent50-reviewed-metrics.json"
RUBRIC = ROOT.parent / "tutor-semantic-rubric-20261025.md"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(document, pointer):
    assert pointer.startswith("/")
    value = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def actual_calls(source):
    return [
        (sid, ti, ci, call)
        for sid, step in source["observed"]["steps"].items()
        for ti, turn in enumerate(step.get("model_turns", []))
        for ci, call in enumerate(turn.get("tool_calls", []))
    ]


def requirements(definition, sid):
    template = definition.get("template_case_id", definition["case_id"])
    number = int(template.split("-")[1])
    if number in {5, 6} and sid == "s1":
        return ["ask_student"]
    if number == 8:
        return ["search_learning_history", "read_learning_history"]
    private = definition["initial_facts"].get("evaluator_only", {})
    if number == 1 and isinstance(private, dict):
        if private.get("requires_history_search"):
            return ["search_learning_history"]
        if private.get("requires_knowledge_tool"):
            return ["get_knowledge_context"]
    return []


def validate(row, raw, definition):
    assert row["schema"] == "eduagent.agent50-semantic-review.v1"
    assert row["review_status"] == "ai_review_completed"
    assert row["reviewer"]["human_reviewed"] is False
    assert row["reviewer"]["additional_provider_requests"] == 0
    assert row["source_report_sha256"] == sha(RAW)
    assert row["source_dataset_sha256"] == sha(DATASET) == raw["dataset_revision"]
    assert row["rubric_sha256"] == sha(RUBRIC)
    assert row["config_fingerprint"] == raw["config_fingerprint"]
    assert row["code_revision"] == raw["code_revision"]
    index = row["source_result_index"]
    source = raw["results"][index]
    assert source["case_id"] == row["case_id"] == definition["case_id"]
    assert row["original_status"] == source["status"]
    assert row["original_automatic_passed"] is source["automatic_passed"]
    assert row["task_confidence"] in {"high", "medium"}
    expected = [c for c in source["hard_checks"] if c["method"] == "semantic_review"]
    assert len(expected) == len(row["semantic_checks"])
    for check, review in zip(expected, row["semantic_checks"]):
        assert check["id"] == review["check_id"] and check["rule"] == review["original_rule"]
        assert review["verdict"] in {"passed", "failed", "not_observed"}
        assert review["passed"] is {"passed": True, "failed": False}.get(review["verdict"])
        assert review["rationale"] and review["evidence"]
        assert review["confidence"] in {"high", "medium"}
        for evidence in review["evidence"]:
            content = resolve(raw, evidence["source_pointer"])
            assert isinstance(content, str) and evidence["quote"] in content
    calls = actual_calls(source)
    assert len(calls) == len(row["tool_calls"])
    assert Counter(c[3]["id"] for c in calls) == Counter(c["tool_call_id"] for c in row["tool_calls"])
    for (sid, ti, ci, call), review in zip(calls, row["tool_calls"]):
        assert review["step_id"] == sid
        assert review["tool_call_id"] == call["id"] and review["tool_name"] == call["name"]
        assert review["arguments"] == call["arguments"] and review["batch_size"] == call["batch_size"]
        assert resolve(raw, review["source_pointer"]) == call
        assert type(review["selection_correct"]) is bool and type(review["arguments_correct"]) is bool
        assert review["joint_correct"] is (review["selection_correct"] and review["arguments_correct"])
        assert review["confidence"] in {"high", "medium"} and review["rationale"]
        events = [event for attempt in source["observed"]["steps"][sid].get("trace", {}).get("attempts", [])
                  for event in attempt["steps"]
                  if event["kind"] == "after_tool" and event.get("tool_call_id") == call["id"]]
        assert review["execution_status"] == (events[-1]["status"] if events else "not_executed")
    converse = {sid: step for sid, step in source["observed"]["steps"].items()
                if step.get("action") == "converse" and step.get("model_turns")}
    assert Counter(d["step_id"] for d in row["converse_decisions"]) == Counter(converse.keys())
    for decision in row["converse_decisions"]:
        sid = decision["step_id"]
        tools = [tool for tool in row["tool_calls"] if tool["step_id"] == sid]
        names = [tool["tool_name"] for tool in tools]
        assert decision["actual_tool_names"] == names
        required = requirements(definition, sid)
        assert decision["missing_required_tools"] == [name for name in required if name not in names]
        if len(required) == 2:
            sequence = not decision["missing_required_tools"] and names.index(required[0]) < names.index(required[1])
        else:
            sequence = True
        assert decision["required_sequence_correct"] is sequence
        assert decision["passed"] is (all(t["joint_correct"] for t in tools)
                                      and not decision["missing_required_tools"] and sequence)
        assert decision["rationale"] and resolve(raw, decision["source_pointer"]) == converse[sid]
    passed = source["automatic_passed"] and all(c["passed"] is True for c in row["semantic_checks"])
    fixture_valid = source["observed"]["fixture_validation"]["valid"]
    verdict = "fixture_invalid" if not fixture_valid else "passed" if passed else "failed"
    assert row["task_verdict"] == verdict
    assert row["failed_check_ids"] == (
        [c["id"] for c in source["hard_checks"] if c["passed"] is False]
        + [c["check_id"] for c in row["semantic_checks"] if c["verdict"] == "failed"]
    )
    return source


def summarize(rows, sources, definitions):
    valid = [r for r in rows if r["task_verdict"] != "fixture_invalid"]
    tools = [tool for r in valid for tool in r["tool_calls"]]
    decisions = [decision for r in valid for decision in r["converse_decisions"]]
    durations = [sources[r["case_id"]]["duration_ms"] / 1000 for r in rows]
    passed = sum(r["task_verdict"] == "passed" for r in valid)
    costs = {period: sum(m[f"estimated_{period}_cny"]
                       for r in rows for m in sources[r["case_id"]]["metering"]
                       if m.get("status") == "usage_recorded")
             for period in ("peak", "off_peak")}
    planned = sum(s["action"] == "converse" for r in rows for s in definitions[r["case_id"]]["steps"])
    return {
        "cases": len(rows), "valid_fixtures": len(valid),
        "task_success_rate": ratio(passed, len(valid)),
        "automatic_contract_pass_rate": ratio(sum(r["original_automatic_passed"] for r in valid), len(valid)),
        "tool_selection_accuracy": ratio(sum(t["selection_correct"] for t in tools), len(tools)),
        "tool_argument_semantic_accuracy": ratio(sum(t["arguments_correct"] for t in tools), len(tools)),
        "tool_joint_semantic_accuracy": ratio(sum(t["joint_correct"] for t in tools), len(tools)),
        "executed_converse_decision_accuracy": ratio(sum(d["passed"] for d in decisions), len(decisions)),
        "planned_converse_steps": planned, "executed_converse_steps": len(decisions),
        "tool_execution_statuses": dict(Counter(t["execution_status"] for t in tools)),
        "tool_names": dict(Counter(t["tool_name"] for t in tools)),
        "semantic_check_verdicts": dict(Counter(c["verdict"] for r in valid for c in r["semantic_checks"])),
        "case_latency_seconds": {"mean": statistics.mean(durations) if durations else None,
                                 "median": statistics.median(durations) if durations else None,
                                 "p95_nearest_rank": sorted(durations)[math.ceil(.95 * len(durations)) - 1] if durations else None},
        "model_requests": sum(len(sources[r["case_id"]]["metering"]) for r in rows),
        "estimated_cny": costs,
        "failed_cases": [{"case_id": r["case_id"], "failed_check_ids": r["failed_check_ids"],
                         "unobserved_check_ids": [s["check_id"] for s in r["semantic_checks"] if s["verdict"] == "not_observed"]}
                        for r in valid if r["task_verdict"] == "failed"],
    }


def main():
    raw = json.loads(RAW.read_text())
    manifest = json.loads(MANIFEST.read_text())
    definitions = {c["case_id"]: c for c in (json.loads(line) for line in DATASET.read_text().splitlines())}
    rows = [json.loads(line) for line in LABELS.read_text().splitlines()]
    assert len(rows) == len(raw["results"]) == 50
    assert Counter(row["case_id"] for row in rows) == Counter(definitions.keys())
    assert Counter(s["case_id"] for s in raw["results"]) == Counter(definitions.keys())
    sources = {row["case_id"]: validate(row, raw, definitions[row["case_id"]]) for row in rows}
    meta = {c["case_id"]: c for c in manifest["cases"]}
    for row in rows:
        assert row["capability"] == meta[row["case_id"]]["capability"]
        assert row["is_original"] == meta[row["case_id"]]["is_original"]
    summary = summarize(rows, sources, definitions)
    assert summary["model_requests"] == raw["budget"]["requests"]
    for period in ("peak", "off_peak"):
        assert math.isclose(summary["estimated_cny"][period], raw["budget"][f"estimated_{period}_cny"], abs_tol=1e-12)
    result = {
        "schema": "eduagent.agent50-reviewed-metrics.v1", "review_status": "ai_review_completed",
        "reviewer": rows[0]["reviewer"], "model": raw["model"], "code_revision": raw["code_revision"],
        "config_fingerprint": raw["config_fingerprint"], "dataset_sha256": sha(DATASET),
        "source_report_sha256": sha(RAW), "review_labels_sha256": sha(LABELS),
        "rubric_sha256": sha(RUBRIC), "aggregator_sha256": sha(Path(__file__)),
        "overall": summary,
        "capabilities": {key: summarize([r for r in rows if r["capability"] == key], sources, definitions)
                         for key in manifest["capability_counts"]},
        "origin": {key: summarize([r for r in rows if r["is_original"] == original], sources, definitions)
                   for key, original in (("legacy_8", True), ("new_42", False))},
        "difficulty_new_cases": {
            key: summarize([r for r in rows if not r["is_original"] and meta[r["case_id"]]["difficulty"] == key],
                           sources, definitions) for key in ("basic", "intermediate", "advanced")
        },
        "budget": raw["budget"],
        "incorrect_tool_calls": [{"case_id": r["case_id"], **t} for r in rows for t in r["tool_calls"] if not t["joint_correct"]],
        "failed_converse_decisions": [{"case_id": r["case_id"], **d} for r in rows for d in r["converse_decisions"] if not d["passed"]],
        "medium_confidence_cases": [r["case_id"] for r in rows if r["task_confidence"] == "medium"],
        "limitations": [
            "Single AI review; no independent human review or blinded assessment.",
            "Developer-authored fictional scripts using nine contract templates; not a holdout or real learner study.",
            "One run per case; no reliability or ablation estimate.",
            "Actual-call semantic accuracy excludes missing calls; per-converse decisions count required-tool omissions.",
            "Denied external reads are reported separately from proactive model refusal.",
            "Costs are estimates from usage, not provider billing records.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in (
        "task_success_rate", "tool_selection_accuracy", "tool_argument_semantic_accuracy",
        "tool_joint_semantic_accuracy", "executed_converse_decision_accuracy", "model_requests"
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
