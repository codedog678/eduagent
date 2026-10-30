"""冻结的 AI 语义裁判。硬检查仍由既有执行器评分，裁判不能覆盖硬失败。"""

import json
import re

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from evals.live_scorers import calls
from evals.optimization.budget import OptimizationStopped
from evals.optimization.judge_v3 import (
    JUDGE_V3_REPAIR_PROMPT,
    JUDGE_V3_PROMPT,
    Verdict,
    judge_once,
    not_observed_outcome,
    normalize_result,
    replay_outcome,
)
from evals.optimization.protocol import digest, file_digest
from evals.semantic_contract import require_rsi_contract
from evals.optimization.leakage import combine_judgment, load_contract


JUDGE_PROMPT = JUDGE_V3_PROMPT


def judge_protocol_digest() -> str:
    return digest({
        "judge_v3_sha256": file_digest(__file__.replace("scoring.py", "judge_v3.py")),
        "main_prompt": JUDGE_V3_PROMPT,
        "repair_prompt": JUDGE_V3_REPAIR_PROMPT,
    })


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticCheck(StrictModel):
    id: str
    passed: StrictBool
    reason: str = Field(min_length=1, max_length=600)
    evidence: str


class CallCheck(StrictModel):
    index: StrictInt
    selection_correct: StrictBool
    arguments_correct: StrictBool


class Decision(StrictModel):
    step_id: str
    required_tools_present: StrictBool
    calls: list[CallCheck]
    reason: str = Field(min_length=1, max_length=600)
    evidence: str


class Judgment(StrictModel):
    semantic: list[SemanticCheck]
    decisions: list[Decision]


def compact_steps(observed):
    return {
        sid: {
            "status": step.get("status"),
            "action": step.get("action"),
            "student_input": step.get("student_input"),
            "response": step.get("result", {}).get("teaching_response", {}).get("response", ""),
            "calls": calls(step), "tool_results": step.get("tool_results", []),
            "execution": step.get("result", {}).get("execution", {}),
        } for sid, step in observed["steps"].items()
    }


def evidence_text(steps):
    # 学生输入和参考事实不能替代 Agent 实际行为的证据。
    return "\n".join(
        step["response"] + "\n" + json.dumps(step["calls"], ensure_ascii=False)
        for step in steps.values()
    )


def evidence_matches(evidence: str, observed_text: str) -> bool:
    """允许带省略标记的有序摘录；每个非空片段仍必须逐字出现在实际输出中。"""
    if evidence in observed_text:
        return True
    parts = re.split(r"…+|\.{3,}", evidence)
    fragments = [part.strip() for part in parts if part.strip()]
    if len(fragments) < 2:
        return False
    offset = 0
    for fragment in fragments:
        found = observed_text.find(fragment, offset)
        if found < 0:
            return False
        offset = found + len(fragment)
    return True


def semantic_response_refs(check, case, evidence_refs: dict[str, str]) -> list[str]:
    """Bind one semantic check to only the response steps named by its frozen path."""
    path_steps = check.path.split(".", 1)[0].split("/")
    if path_steps and all(re.fullmatch(r"s\d+", step_id) for step_id in path_steps):
        step_ids = path_steps
    elif check.path.startswith("retrieval_"):
        step_ids = [
            step.id for step in case.steps
            if step.action == "converse" and not step.quiz_id
        ]
    elif check.path.startswith("hint_"):
        step_ids = [
            step.id for step in case.steps
            if step.action == "converse" and step.quiz_id
        ]
    else:
        raise ValueError(f"semantic check has no response-step binding: {check.id}")
    return [
        f"response:{step_id}"
        for step_id in step_ids
        if f"response:{step_id}" in evidence_refs
    ]


def validate_judgment(raw: str, case, observed) -> Judgment:
    require_rsi_contract(case)
    judgment = Judgment.model_validate_json(raw)
    expected = {c.id for c in case.hard_checks if c.method == "semantic_review"}
    if ({c.id for c in judgment.semantic} != expected
            or len(judgment.semantic) != len(expected)):
        raise ValueError("semantic check coverage mismatch")
    steps = compact_steps(observed)
    executed = {sid: step for sid, step in steps.items()
                if step["action"] == "converse" and step["status"] == "completed"}
    if ({d.step_id for d in judgment.decisions} != set(executed)
            or len(judgment.decisions) != len(executed)):
        raise ValueError("decision coverage mismatch")
    text = evidence_text(steps)
    for check in judgment.semantic:
        if ((check.passed and not check.evidence.strip())
                or (check.evidence and not evidence_matches(check.evidence, text))):
            raise ValueError("semantic evidence is missing or not in observed output")
    for decision in judgment.decisions:
        step = executed[decision.step_id]
        expected_indices = set(range(len(step["calls"])))
        if ({c.index for c in decision.calls} != expected_indices
                or len(decision.calls) != len(expected_indices)):
            raise ValueError("tool call coverage mismatch")
        decision_text = evidence_text({decision.step_id: step}) + "\n" + json.dumps(
            step["tool_results"], ensure_ascii=False)
        if decision.evidence and not evidence_matches(decision.evidence, decision_text):
            raise ValueError("decision evidence is not in observed output")
    return judgment


def judge_payload(case, observed):
    steps = compact_steps(observed)
    criterion_ids = [
        f"semantic:{check.id}"
        for check in case.hard_checks
        if check.method == "semantic_review"
    ] + [
        f"decision:{step_id}"
        for step_id, step in steps.items()
        if step["action"] == "converse" and step["status"] == "completed"
    ]
    evidence_refs = {}
    for step_id, step in steps.items():
        if step["response"]:
            evidence_refs[f"response:{step_id}"] = step["response"]
        for index, call in enumerate(step["calls"]):
            evidence_refs[f"call:{step_id}:{index}"] = json.dumps(call, ensure_ascii=False)
        if step["action"] == "converse" and step["status"] == "completed" and not step["calls"]:
            evidence_refs[f"no_calls:{step_id}"] = json.dumps(
                {"step_id": step_id, "call_count": 0}, separators=(",", ":"))
    semantic_checks = [
        check for check in case.hard_checks if check.method == "semantic_review"
    ]
    semantic_by_id = {f"semantic:{check.id}": check for check in semantic_checks}
    criterion_evidence = {}
    for criterion_id in criterion_ids:
        if criterion_id.startswith("semantic:"):
            response_refs = semantic_response_refs(
                semantic_by_id[criterion_id], case, evidence_refs)
            criterion_evidence[criterion_id] = {
                "allowed_refs": response_refs,
                "required_refs": response_refs,
            }
        else:
            step_id = criterion_id.removeprefix("decision:")
            call_refs = [
                ref for ref in evidence_refs if ref.startswith(f"call:{step_id}:")
            ]
            required = call_refs or [f"no_calls:{step_id}"]
            criterion_evidence[criterion_id] = {
                "allowed_refs": required,
                "required_refs": required,
            }
    return {
        "criterion_ids": criterion_ids,
        "evidence_refs": evidence_refs,
        "criterion_evidence": criterion_evidence,
        "semantic_checks": [check.model_dump() for check in semantic_checks],
        "expected_behavior": case.expected_behavior,
        "acceptable_tool_paths": case.acceptable_tool_paths,
        "criteria": case.tool_decision_criteria,
        "decision_targets": [
            {"step_id": sid, "call_indices": list(range(len(calls(step))))}
            for sid, step in observed["steps"].items()
            if step.get("action") == "converse" and step.get("status") == "completed"
        ],
        "reference_facts_for_evaluation_only": case.initial_facts,
        "steps": steps,
        "evidence_candidates": {
            step_id: {
                "response": step["response"],
                "calls": [
                    json.dumps(call, ensure_ascii=False) for call in step["calls"]
                ],
            }
            for step_id, step in steps.items()
        },
    }


async def judge_observed(case, observed, text_model):
    """执行冻结裁判并校验证据；供正式评分与独立校准共用。"""
    payload = judge_payload(case, observed)
    return await judge_once(payload, text_model), payload


def judge_metadata(outcome, payload, *, call_count: int) -> dict:
    """Serialize the complete replayable Judge v3 protocol record."""
    return {
        "judge_protocol_version": 3,
        "judge_protocol_sha256": judge_protocol_digest(),
        "judge_verdict": outcome.result.verdict,
        "judge_reason_codes": outcome.result.reason_codes,
        "raw_judgment_v3": outcome.result.model_dump(mode="json"),
        "judge_diagnostics": {
            "raw_response": outcome.raw_response,
            "repair_response": outcome.repair_response,
            "validation_errors": outcome.validation_errors,
            "repaired": outcome.repaired,
        },
        "judge_call_count": call_count,
        "judge_prompt_sha256": digest(JUDGE_PROMPT),
        "judge_input_sha256": digest(payload),
    }


def verify_judge_metadata(score: dict, payload: dict):
    """Fail closed unless all frozen identity and replay fields are present and coherent."""
    if score.get("judge_protocol_version") != 3:
        raise ValueError("judge protocol version changed")
    if (score.get("judge_prompt_sha256") != digest(JUDGE_PROMPT)
            or score.get("judge_protocol_sha256") != judge_protocol_digest()):
        raise ValueError("judge protocol changed")
    if score.get("judge_input_sha256") != digest(payload):
        raise ValueError("judge input binding changed")
    try:
        result = replay_outcome(
            payload,
            diagnostics=score["judge_diagnostics"],
            judge_call_count=score["judge_call_count"],
            raw_judgment_v3=score["raw_judgment_v3"],
        )
    except KeyError as exc:
        raise ValueError("incomplete judge v3 provenance") from exc
    if (score.get("judge_verdict") != result.verdict
            or score.get("judge_reason_codes") != result.reason_codes):
        raise ValueError("judge v3 result metadata mismatch")
    return result


async def score_with_judge(case, observed, automatic, text_model):
    require_rsi_contract(case)
    load_contract(case)
    if not observed["fixture_validation"]["valid"]:
        raise OptimizationStopped("invalid fixture; fix the dataset before optimization")
    if automatic["execution_outcome"] != "completed":
        reasons = {item.get("reason") for item in automatic["execution_failures"]}
        # 固定上下文/工具/模型次数是任务约束：候选耗尽它们属于策略失败。
        # 全局请求/费用预算已由 Adapter 判停，不能把所有含 budget 的原因一概当基础设施故障。
        if any(reason and "timeout" in reason for reason in reasons):
            raise OptimizationStopped("execution timeout; incomplete infrastructure run")
        payload = judge_payload(case, observed)
        outcome = not_observed_outcome(payload)
        return {"score": 0.0, "task_success": False,
                "automatic_passed": automatic["automatic_passed"],
                "decision_rate": 0.0, "review_status": "not_observed",
                "semantic": [], "decisions": [],
                **judge_metadata(outcome, payload, call_count=0)}
    outcome, payload = await judge_observed(case, observed, text_model)
    normalized = normalize_result(outcome.result, payload)
    combined = combine_judgment(case, observed, normalized)
    unknown = outcome.result.verdict == Verdict.UNKNOWN
    task_success = (
        not unknown
        and outcome.result.verdict == Verdict.PASS
        and automatic["automatic_passed"]
        and all(c["passed"] for c in combined["semantic"])
    )
    decisions = [
        d["required_tools_present"]
        and all(c["selection_correct"] and c["arguments_correct"] for c in d["calls"])
        for d in normalized["decisions"]
    ]
    rate = sum(decisions) / len(decisions) if decisions else 0.0
    return {
        **combined, "task_success": task_success,
        "automatic_passed": automatic["automatic_passed"],
        "decision_rate": 0.0 if unknown else rate,
        # 有任何任务硬失败时得 0；工具决策只在完成任务后影响排序。
        "score": .8 + .2 * rate if task_success else 0.0,
        "review_status": "unknown" if unknown else "ai_reviewed",
        **judge_metadata(
            outcome, payload, call_count=2 if outcome.repair_response is not None else 1),
    }


def summarize(rows):
    if not rows:
        raise ValueError("cannot summarize an empty evaluation")
    by_capability = {}
    for capability in sorted({row["capability"] for row in rows}):
        subset = [row for row in rows if row["capability"] == capability]
        by_capability[capability] = {
            "total": len(subset),
            "task_success_rate": sum(r["score"]["task_success"] for r in subset) / len(subset),
        }
    return {
        "total": len(rows),
        "task_success_rate": sum(r["score"]["task_success"] for r in rows) / len(rows),
        "mean_score": sum(r["score"]["score"] for r in rows) / len(rows),
        "automatic_pass_rate": sum(r["score"]["automatic_passed"] for r in rows) / len(rows),
        "mean_decision_rate": sum(r["score"]["decision_rate"] for r in rows) / len(rows),
        "by_capability": by_capability,
    }
