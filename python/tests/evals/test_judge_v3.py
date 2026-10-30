"""Judge v3 的 fail-closed 合同测试。"""

import copy
import json

import pytest
from pydantic import ValidationError

from evals.optimization.judge_v3 import (
    JudgeV3Result,
    Verdict,
    judge_once,
    not_observed_outcome,
    normalize_result,
    replay_outcome,
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
    "criterion_evidence": {
        "semantic:H5": {
            "allowed_refs": ["response:s1"],
            "required_refs": [],
        },
        "decision:s1": {
            "allowed_refs": ["call:s1:0"],
            "required_refs": ["call:s1:0"],
        },
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
        criterion_evidence=PAYLOAD["criterion_evidence"],
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
        "criterion_evidence",
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


@pytest.mark.parametrize("mutation", [
    "raw", "repair", "errors", "repaired", "calls", "final",
])
def test_replay_rejects_any_provenance_tampering(mutation):
    invalid = json.dumps({**VALID, "unexpected": True})
    diagnostics = {
        "raw_response": invalid,
        "repair_response": json.dumps(VALID),
        "validation_errors": [],
        "repaired": True,
    }
    try:
        validate_result(
            invalid,
            expected_criterion_ids=PAYLOAD["criterion_ids"],
            allowed_evidence_refs=set(PAYLOAD["evidence_refs"]),
            criterion_evidence=PAYLOAD["criterion_evidence"],
        )
    except ValueError as exc:
        from evals.optimization.judge_v3 import _validation_error
        diagnostics["validation_errors"] = [_validation_error(exc)]
    calls = 2
    final = copy.deepcopy(VALID)
    if mutation == "raw":
        diagnostics["raw_response"] = json.dumps(VALID)
    elif mutation == "repair":
        diagnostics["repair_response"] = "invalid"
    elif mutation == "errors":
        diagnostics["validation_errors"] = ["forged"]
    elif mutation == "repaired":
        diagnostics["repaired"] = False
    elif mutation == "calls":
        calls = 1
    else:
        final["criterion_results"][0]["rationale"] = "forged"
    with pytest.raises(ValueError):
        replay_outcome(
            PAYLOAD,
            diagnostics=diagnostics,
            judge_call_count=calls,
            raw_judgment_v3=final,
        )


def replay_record(outcome, judge_call_count):
    diagnostics = outcome.model_dump(mode="json", exclude={"result"})
    return replay_outcome(
        PAYLOAD,
        diagnostics=diagnostics,
        judge_call_count=judge_call_count,
        raw_judgment_v3=outcome.result.model_dump(mode="json"),
    )


def test_replay_accepts_zero_call_not_observed():
    outcome = not_observed_outcome(PAYLOAD)

    assert replay_record(outcome, 0) == outcome.result


@pytest.mark.asyncio
async def test_replay_accepts_one_call_first_valid():
    outcome = await judge_once(PAYLOAD, FakeTextModel([json.dumps(VALID)]))

    assert replay_record(outcome, 1) == outcome.result
    assert outcome.result.verdict == Verdict.PASS


@pytest.mark.asyncio
async def test_replay_accepts_two_calls_repair_valid():
    invalid = json.dumps({**VALID, "unexpected": True})
    outcome = await judge_once(
        PAYLOAD, FakeTextModel([invalid, json.dumps(VALID)]))

    assert replay_record(outcome, 2) == outcome.result
    assert outcome.repaired is True


@pytest.mark.asyncio
async def test_replay_accepts_two_invalid_calls_as_deterministic_unknown():
    outcome = await judge_once(PAYLOAD, FakeTextModel(["not-json", '{"schema_version":3}']))

    replayed = replay_record(outcome, 2)

    assert replayed == outcome.result
    assert replayed.verdict == Verdict.UNKNOWN
    assert replayed.reason_codes == ["invalid_schema"]


@pytest.mark.parametrize("judge_call_count", [
    True,
    False,
    1.0,
    2.0,
    "1",
    "-1",
    -1,
])
def test_replay_rejects_non_strict_or_negative_judge_call_count(judge_call_count):
    outcome = not_observed_outcome(PAYLOAD)

    with pytest.raises(ValueError, match="type or range"):
        replay_record(outcome, judge_call_count)


def test_criterion_evidence_is_nonempty_typed_and_covers_all_calls():
    empty = copy.deepcopy(VALID)
    empty["criterion_results"][0]["evidence_refs"] = []
    with pytest.raises(ValueError, match="requires evidence"):
        validated(empty)

    cross_type = copy.deepcopy(VALID)
    cross_type["criterion_results"][0]["evidence_refs"] = ["call:s1:0"]
    with pytest.raises(ValueError, match="wrong criterion or type"):
        validated(cross_type)

    payload = copy.deepcopy(PAYLOAD)
    payload["evidence_refs"]["call:s1:1"] = '{"name":"read_memory"}'
    payload["criterion_evidence"]["decision:s1"]["allowed_refs"].append("call:s1:1")
    payload["criterion_evidence"]["decision:s1"]["required_refs"].append("call:s1:1")
    with pytest.raises(ValueError, match="coverage"):
        validate_result(
            json.dumps(VALID),
            expected_criterion_ids=payload["criterion_ids"],
            allowed_evidence_refs=set(payload["evidence_refs"]),
            criterion_evidence=payload["criterion_evidence"],
        )


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
