"""内置评测数据、评分和真实 Harness 场景。"""

import json

import pytest

from evals.io import DatasetError, load_cases
from evals.models import EvalCase
from evals.runner import run_suite
from evals.scorers import detect_signals, score_case


def test_builtin_dataset_has_expected_groups():
    cases = load_cases()
    assert len(cases) == 20
    assert len({case.case_id for case in cases}) == 20
    groups = {tag for case in cases for tag in case.tags}
    assert {"pedagogy", "dialogue", "safety", "reliability", "trace"} <= groups


def test_loader_reports_line_and_duplicate(tmp_path):
    case = load_cases()[0].model_dump(mode="json")
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(
        json.dumps(case) + "\n" + json.dumps(case) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match=r":2: duplicate case_id"):
        load_cases(duplicate)

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"schema_version": 99}\n', encoding="utf-8")
    with pytest.raises(DatasetError, match=r":1:"):
        load_cases(malformed)


def test_policy_scorer_detects_guidance_without_answer_reveal():
    case = EvalCase.model_validate({
        "schema_version": 1,
        "case_id": "policy-unit-001",
        "suite": "unit",
        "kind": "tutor_response",
        "input": {"protected_answers": ["gone"]},
        "expected": {
            "required_signals": ["guidance", "actionability"],
            "forbidden_signals": ["answer_reveal"],
        },
        "source": {"name": "test", "license": "MIT"},
    })
    observed = {
        "response": "Check the verb after have, then try the sentence again."
    }
    details = score_case(case, observed)
    assert all(detail.passed for detail in details)
    assert "answer_reveal" in detect_signals(
        "The missing word is gone.", ["gone"]
    )


@pytest.mark.asyncio
async def test_builtin_suite_runs_offline_against_real_harness():
    report = await run_suite()
    assert report.total == 20
    assert report.failed == 0, [
        (result.case_id, [detail.message for detail in result.details])
        for result in report.results
        if not result.passed
    ]
    assert report.pass_rate == 1
    serialized = report.model_dump_json()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
