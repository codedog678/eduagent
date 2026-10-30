"""Judge v3 的 fail-closed 合同测试。"""

import copy
import json

import pytest
from pydantic import ValidationError

from evals.optimization.judge_v3 import (
    JudgeV3Result,
    Verdict,
    judge_once,
    normalize_result,
    validate_result,
)


VALID = {
    "schema_version": 3,
    "verdict": "pass",
    "reason_codes": ["all_criteria_passed"],
    "criterion_results": [
        {
            "criterion_id": "semantic:H5",
            "verdict": "pass",
            "evidence_refs": ["response:s1"],
            "rationale": "The response cites the observed behavior.",
        },
        {
            "criterion_id": "decision:s1",
            "verdict": "pass",
            "evidence_refs": ["call:s1:0"],
            "rationale": "The required call is present and scoped.",
        },
    ],
}

PAYLOAD = {
    "criterion_ids": ["semantic:H5", "decision:s1"],
    "evidence_refs": {
        "response:s1": "Observed response.",
        "call:s1:0": '{"name":"search_memory","arguments":{"query":"past work"}}',
    },
    "steps": {
        "s1": {
            "calls": [{"name": "search_memory", "arguments": {"query": "past work"}}],
        },
    },
}


def validated(value=VALID):
    return validate_result(
        json.dumps(value),
        expected_criterion_ids=PAYLOAD["criterion_ids"],
        allowed_evidence_refs=set(PAYLOAD["evidence_refs"]),
    )


def test_valid_v3_judgment_normalizes_to_existing_score_shape():
    result = validated()
    normalized = normalize_result(result, PAYLOAD)

    assert normalized == {
        "semantic": [{
            "id": "H5",
            "passed": True,
            "reason": "The response cites the observed behavior.",
            "evidence": "Observed response.",
        }],
        "decisions": [{
            "step_id": "s1",
            "required_tools_present": True,
            "calls": [{
                "index": 0,
                "selection_correct": True,
                "arguments_correct": True,
            }],
            "reason": "The required call is present and scoped.",
            "evidence": "",
        }],
    }


def test_verdict_reason_and_criteria_must_agree():
    failed_criterion = copy.deepcopy(VALID)
    failed_criterion["criterion_results"][0]["verdict"] = "fail"
    with pytest.raises(ValueError, match="contradicts"):
        validated(failed_criterion)

    insufficient_pass = copy.deepcopy(VALID)
    insufficient_pass["reason_codes"] = ["insufficient_evidence"]
    with pytest.raises(ValueError, match="reason codes"):
        validated(insufficient_pass)


def test_evidence_refs_must_exist_in_current_payload():
    unknown_reference = copy.deepcopy(VALID)
    unknown_reference["criterion_results"][0]["evidence_refs"] = ["response:other"]
    with pytest.raises(ValueError, match="evidence"):
        validated(unknown_reference)

    extra_field = copy.deepcopy(VALID)
    extra_field["unexpected"] = True
    with pytest.raises(ValidationError):
        validated(extra_field)

    empty_rationale = copy.deepcopy(VALID)
    empty_rationale["criterion_results"][0]["rationale"] = ""
    with pytest.raises(ValidationError):
        validated(empty_rationale)


class FakeTextModel:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def complete(self, messages, *, role, max_tokens=2200):
        self.calls.append({"messages": messages, "role": role, "max_tokens": max_tokens})
        return next(self.responses)


@pytest.mark.asyncio
async def test_one_bounded_repair_can_fix_schema_only():
    invalid = {**VALID, "unexpected": True}
    text_model = FakeTextModel([json.dumps(invalid), json.dumps(VALID)])

    outcome = await judge_once(PAYLOAD, text_model)

    assert outcome.result.verdict == Verdict.PASS
    assert outcome.repaired is True
    assert outcome.raw_response == json.dumps(invalid)
    assert outcome.repair_response == json.dumps(VALID)
    assert len(text_model.calls) == 2
    repair_payload = json.loads(text_model.calls[1]["messages"][-1]["content"])
    assert set(repair_payload) == {
        "invalid_json",
        "validation_errors",
        "allowed_criterion_ids",
        "allowed_evidence_refs",
    }
    assert "steps" not in repair_payload


@pytest.mark.asyncio
async def test_second_invalid_response_becomes_unknown_with_diagnostics():
    text_model = FakeTextModel(["not-json", '{"schema_version":3}'])

    outcome = await judge_once(PAYLOAD, text_model)

    assert outcome.result.verdict == Verdict.UNKNOWN
    assert outcome.result.reason_codes == ["invalid_schema"]
    assert [item.criterion_id for item in outcome.result.criterion_results] == PAYLOAD["criterion_ids"]
    assert all(item.verdict == Verdict.UNKNOWN for item in outcome.result.criterion_results)
    assert outcome.raw_response == "not-json"
    assert outcome.repair_response == '{"schema_version":3}'
    assert outcome.repaired is False
    assert len(outcome.validation_errors) == 2
    assert len(text_model.calls) == 2


@pytest.mark.asyncio
async def test_unknown_never_counts_as_task_success():
    text_model = FakeTextModel(["not-json", "still-not-json"])
    outcome = await judge_once(PAYLOAD, text_model)

    automatic = {"automatic_passed": True}
    task_success = (
        automatic["automatic_passed"]
        and outcome.result.verdict == Verdict.PASS
    )

    assert task_success is False
    assert JudgeV3Result.model_validate(outcome.result).verdict == Verdict.UNKNOWN
