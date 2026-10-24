"""从已有真实模型报告离线汇总 Agent 指标；不发起网络请求。"""

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = (
    "tutor-live12-20261025.json",
    "tutor-policy-v2-20261025.json",
    "tutor-policy-v3-20261025.json",
)
OUTPUT = ROOT / "agent-metrics-20261025.json"

# 固定本次三轮共用的参数结构；与 core/tutor_runtime.py 的 Pydantic 字段一致。
# 仅检验类型、必填字段、长度/范围和额外字段，不能判断工具/参数的任务语义。
SCHEMAS = {
    "search_learning_history": {
        "query": {"type": "string", "maxLength": 500},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "read_learning_history": {
        "source_ref": {"type": "string", "required": True, "minLength": 1, "maxLength": 128},
    },
    "get_knowledge_context": {},
    "get_quiz_context": {},
    "ask_student": {
        "question": {"type": "string", "required": True, "minLength": 1, "maxLength": 1500},
    },
}


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p95": None}
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "p50": statistics.median(values),
        "p95": values[math.ceil(0.95 * len(values)) - 1],
    }


def schema_valid(call):
    name, args = call["name"], call.get("arguments")
    if name not in SCHEMAS or type(args) is not dict:
        return False
    schema = SCHEMAS[name]
    if set(args) - set(schema):
        return False
    for field, rule in schema.items():
        if field not in args:
            if rule.get("required"):
                return False
            continue
        value = args[field]
        if rule["type"] == "string":
            if type(value) is not str:
                return False
            if not rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", math.inf):
                return False
        elif type(value) is not int or not rule["minimum"] <= value <= rule["maximum"]:
            return False
    return True


def collect(cases):
    steps = [s for r in cases for s in r["observed"]["steps"].values()]
    turns = [t for s in steps for t in s.get("model_turns", [])]
    calls = [c for t in turns for c in t.get("tool_calls", [])]
    events = [
        e for s in steps for a in s.get("trace", {}).get("attempts", [])
        for e in a["steps"] if e["kind"] == "after_tool"
    ]
    # 本批次每个工具调用均有唯一的结果事件，防止遗漏/重试导致分母混淆。
    assert len(calls) == len(events)
    assert Counter(c["id"] for c in calls) == Counter(e["tool_call_id"] for e in events)
    executions = [
        s["result"]["execution"] for s in steps if "execution" in s.get("result", {})
    ]
    converse = [s for s in steps if s.get("action") == "converse"]
    metering = [m for r in cases for m in r["metering"]]
    assert len(turns) == len(metering)
    assert all(m["status"] == "usage_recorded" for m in metering)
    usage = {
        key: sum(m["usage"].get(key, 0) for m in metering)
        for key in ("input_tokens", "output_tokens",
                    "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
    }
    assert usage["input_tokens"] == (
        usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"]
    )
    checks = [h for r in cases for h in r["hard_checks"] if h["method"] == "automatic"]
    cost = {
        "peak": sum(m["estimated_peak_cny"] for m in metering),
        "off_peak": sum(m["estimated_off_peak_cny"] for m in metering),
    }
    semantic = Counter(h["status"] for r in cases for h in r["hard_checks"]
                       if h["method"] == "semantic_review")
    return {
        "case_count": len(cases),
        "case_ids": [r["case_id"] for r in cases],
        "automatic_case_pass_rate": ratio(sum(r["automatic_passed"] for r in cases), len(cases)),
        "automatic_check_pass_rate": ratio(sum(h["passed"] is True for h in checks), len(checks)),
        "case_verdicts": dict(Counter(r["status"] for r in cases)),
        "semantic_check_statuses": dict(semantic),
        "task_success_rate": {
            "status": "not_finalized",
            "value": None,
            "reason": "Task contracts with pending semantic judgments are not complete TSR labels.",
        },
        "script_step_statuses": dict(Counter(s.get("status") for s in steps)),
        "harness_execution_completion_rate": ratio(
            sum(e["status"] == "completed" for e in executions), len(executions)
        ),
        "tool_call_count": len(calls),
        "tool_names": dict(Counter(c["name"] for c in calls)),
        "tool_return_statuses": dict(Counter(e["status"] for e in events)),
        "tool_execution_ok_rate": ratio(sum(e["status"] == "ok" for e in events), len(calls)),
        "tool_argument_schema_validity_rate": ratio(sum(schema_valid(c) for c in calls), len(calls)),
        "tool_semantic_accuracy": {"status": "unscored", "value": None},
        "model_request_count": len(turns),
        "converse_step_count": len(converse),
        "model_requests_per_case": len(turns) / len(cases),
        "model_requests_per_converse_step": len(turns) / len(converse),
        "tool_calls_per_case": len(calls) / len(cases),
        "tool_calls_per_converse_step": len(calls) / len(converse),
        "optimal_trajectory_efficiency": {"status": "unmeasured", "value": None},
        "latency_ms": {
            "case_wall_time": distribution([r["duration_ms"] for r in cases]),
            "executed_converse_wall_time": distribution([s["duration_ms"] for s in converse]),
            "model_request_wall_time": distribution([t["duration_ms"] for t in turns]),
        },
        "usage": usage,
        "estimated_cost_cny": cost,
        "estimated_cost_cny_per_case": {k: v / len(cases) for k, v in cost.items()},
        "cost_per_successful_task": {"status": "not_finalized", "value": None},
        "repeated_run_reliability": {"status": "unmeasured", "value": None},
        "tool_schema_failures": [
            {"name": c["name"], "tool_call_id": c["id"]}
            for c in calls if not schema_valid(c)
        ],
    }


def main():
    runs = []
    for filename in INPUTS:
        path = ROOT / filename
        raw = path.read_bytes()
        data = json.loads(raw)
        summary = collect(data["results"])
        assert summary["model_request_count"] == data["budget"]["requests"]
        assert summary["usage"] == data["budget"]["usage"]
        assert math.isclose(summary["estimated_cost_cny"]["peak"],
                            data["budget"]["estimated_peak_cny"], abs_tol=1e-12)
        groups = {
            role: collect([r for r in data["results"] if r["evaluation_role"] == role])
            for role in ("agent_primary", "teaching_auxiliary")
        }
        for role, group in groups.items():
            assert group["case_count"] == data["groups"][role]["total"]
            assert group["automatic_case_pass_rate"]["numerator"] == (
                data["groups"][role]["automatic_passed"]
            )
        runs.append({
            "input_file": filename,
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "generated_at": data["generated_at"],
            "model": data["model"],
            "provider": data["provider"],
            "generation_mode": data["generation_mode"],
            "policy_version": data["config"].get("tutor_policy_version", "baseline_unversioned"),
            "code_revision": data["code_revision"],
            "config_fingerprint": data["config_fingerprint"],
            "dataset_revision": data["dataset_revision"],
            "pricing": data["budget"]["pricing"],
            "all_cases": summary,
            "groups": groups,
        })
    out = {
        "report_date": "2026-10-25",
        "method": "offline_summary_of_existing_live_traces",
        "summarizer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "latency_percentile_method": "p50=median; p95=nearest_rank(ceil(0.95*n)); unit=ms",
        "schema_check_scope": "frozen type/required/length/range/extra-field checks; no task semantics",
        "frozen_tool_parameter_schemas": SCHEMAS,
        "limitations": [
            "Fictional learners and scripted tasks; no student learning-effect estimate.",
            "Each case is a single sample; versions/subsets must not be pooled for performance.",
            "Schema validity and tool return status do not establish tool semantic accuracy.",
            "Completed Harness executions do not establish end-to-end task success.",
            "No external benchmark score, reference optimal trajectories, or fault-injection suite.",
            "Costs use previously captured prices and usage; they are not billing records.",
            "Blocked scripted steps have no execution latency and are counted separately.",
        ],
        "runs": runs,
        # 只累计资源用量，不跨版本合并能力成绩。
        "total_resource_usage": {
            "model_requests": sum(r["all_cases"]["model_request_count"] for r in runs),
            "usage": {
                key: sum(r["all_cases"]["usage"][key] for r in runs)
                for key in runs[0]["all_cases"]["usage"]
            },
            "estimated_cost_cny": {
                key: sum(r["all_cases"]["estimated_cost_cny"][key] for r in runs)
                for key in ("peak", "off_peak")
            },
        },
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)
    for r in runs:
        a = r["all_cases"]
        print(r["policy_version"], "cases=", a["case_count"], "tools=", a["tool_call_count"],
              "schema=", a["tool_argument_schema_validity_rate"],
              "latency_ms=", a["latency_ms"]["case_wall_time"])


if __name__ == "__main__":
    main()
