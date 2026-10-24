"""50 条扩展集的隔离、兼容性和负例检查；禁止供应商访问。"""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from config.settings import settings
from core import llm_service
from evals.io import DatasetError
from evals.live_budget import LiveBudget
from evals.live_cases import load_live_cases
from evals.live_executor import LiveExecutor
from evals.live_runner import run_live_suite
from evals.live_scorers import score_live_case
from evals.live_validation import fixture_service, validate_live_dataset
from tests.evals.test_live_eval import scripted_service


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "docs/evals/tutor-agent-50-review.jsonl"
ORIGINAL = ROOT / "docs/evals/tutor-live-12-review.jsonl"


def test_agent50_preserves_original_and_has_isolated_coverage():
    cases = load_live_cases(DATASET)
    assert len(cases) == 50 and all(c.role == "agent_primary" for c in cases)
    assert DATASET.read_bytes() == (ROOT / "python/evals/datasets/tutor_agent50_review.jsonl").read_bytes()
    assert DATASET.read_text().splitlines()[:8] == ORIGINAL.read_text().splitlines()[4:]
    assert sum(c.template_case_id is not None for c in cases) == 42
    assert sum(s.action == "converse" for c in cases for s in c.steps) == 64
    assert sum(c.expected_model_requests_max for c in cases) == 192
    manifest = json.loads((DATASET.parent / "tutor-agent-50-manifest.json").read_text())
    assert manifest["dataset_sha256"] == hashlib.sha256(DATASET.read_bytes()).hexdigest()
    assert manifest["semantic_scoring_status"] == "not_started"
    batches = manifest["proposed_future_batches"]
    assert len(batches) == 5 and all(b["worst_case_model_requests"] <= 42 for b in batches)
    assert [identifier for batch in batches for identifier in batch["case_ids"]] == [c.case_id for c in cases]
    counts = Counter(c.capability for c in cases[8:])
    assert counts == {
        "multi_turn_continuation": 12, "grounded_history": 7,
        "full_history_retrieval": 7, "tool_and_evidence_decision": 6,
        "injection_and_permissions": 6, "learning_evidence": 4,
    }
    # learner/quiz/message/session 可在本条重复引用，但不可跨场景重复。
    owners = {}
    for case in cases:
        facts = case.initial_facts
        ids = {case.learner_id, *(s.session_id for s in case.steps if s.session_id)}
        for item in facts.get("history", []) + facts.get("foreign_history", []):
            ids.update(item[key] for key in ("message_id", "session_id", "owner") if key in item)
        if facts.get("history_recipe"):
            recipe = facts["history_recipe"]
            ids.update([recipe["session_id"], recipe["target"]["message_id"]])
            ids.update(recipe["decoys"]["message_id_template"].format(index=i)
                       for i in range(1, recipe["decoys"]["count"] + 1))
        ids.update(s.quiz_id for s in case.steps if s.quiz_id)
        for identifier in ids:
            assert identifier not in owners, (identifier, case.case_id)
            owners[identifier] = case.case_id


@pytest.mark.parametrize("change", [
    {"template_case_id": "unknown"}, {"evaluation_role": None}, {"capability": None},
    {"difficulty": "hard"}, {"tool_decision_criteria": {}},
    {"learner_id": "real-student"}, {"expected_model_requests_max": 1},
])
def test_variant_rejects_incomplete_or_unsupported_contract(tmp_path, change):
    case = json.loads(DATASET.read_text().splitlines()[8])
    case.update(change)
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(case))
    with pytest.raises(DatasetError):
        load_live_cases(path)


def test_legacy_template_cannot_remap_and_learners_cannot_collide(tmp_path):
    legacy = json.loads(ORIGINAL.read_text().splitlines()[0])
    legacy["template_case_id"] = "live-05-missing-sentence-followup"
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(legacy))
    with pytest.raises(DatasetError):
        load_live_cases(path)
    pair = [json.loads(line) for line in DATASET.read_text().splitlines()[8:10]]
    pair[1]["learner_id"] = pair[0]["learner_id"]
    path.write_text("\n".join(json.dumps(case) for case in pair))
    with pytest.raises(DatasetError):
        load_live_cases(path)


@pytest.mark.asyncio
async def test_agent50_all_fixtures_execute_without_network_and_scores_remain_unmeasured(monkeypatch):
    def forbid(*args, **kwargs):
        raise AssertionError("provider network forbidden")

    monkeypatch.setattr(httpx.AsyncClient, "request", forbid)
    monkeypatch.setattr(httpx.Client, "request", forbid)
    previous_service = llm_service._llm_service
    previous_setting = settings.enable_agent_llm_decisions
    report = await validate_live_dataset(DATASET)
    assert report["total"] == report["valid"] == 50
    assert report["provider_requests"] == 0
    assert sum(r["scripted_turns"] for r in report["results"]) == 88
    assert all(r["model_task_success"] is None and r["model_tool_semantic_score"] is None
               and r["semantic_review"] == "not_evaluated" for r in report["results"])
    assert llm_service._llm_service is previous_service
    assert settings.enable_agent_llm_decisions == previous_setting


@pytest.mark.asyncio
async def test_variant_sources_quotes_and_private_markers_use_own_fixtures(monkeypatch):
    monkeypatch.setattr(settings, "enable_tutor_tools", True)
    monkeypatch.setattr(settings, "enable_agent_llm_decisions", False)
    for case in load_live_cases(DATASET):
        if not case.template_case_id or case.number not in (7, 8, 10, 12):
            continue
        service, seen = fixture_service(case)
        monkeypatch.setattr(llm_service, "_llm_service", service)
        executor = LiveExecutor(case, service, LiveBudget(max_requests=6))
        temporary = Path(executor._temporary.name)
        try:
            observed = await executor.execute()
            assert score_live_case(case, observed)["automatic_passed"]
            context = json.dumps(seen, ensure_ascii=False)
            assert '"correct_index"' not in context and '"explanation"' not in context
            if case.number == 8:
                assert case.retrieval_expectations[1] not in json.dumps(seen[0], ensure_ascii=False)
                wrong = deepcopy(observed)
                wrong["steps"]["s1"]["result"]["teaching_response"]["response"] = "先圈时间，再看是否到现在"
                assert score_live_case(case, wrong)["hard_checks"][3]["passed"] is False
            if case.number == 7:
                wrong = deepcopy(observed)
                wrong["steps"]["s1"]["result"]["execution"]["source_refs"] = ["message:eval-live-07-old-user"]
                assert score_live_case(case, wrong)["hard_checks"][1]["passed"] is False
            if case.number == 10:
                assert case.foreign_expectations[1] not in context
                wrong = deepcopy(observed)
                wrong["steps"]["s1"]["result"]["teaching_response"]["response"] = case.foreign_expectations[1]
                assert score_live_case(case, wrong)["hard_checks"][1]["passed"] is False
            if case.number == 12:
                q2 = case.initial_facts["evaluator_only"]["new_quiz_after_q1"]
                assert q2["quiz_id"] not in context and q2["question"] not in context
        finally:
            executor.close()
        assert not temporary.exists()


@pytest.mark.asyncio
async def test_live_selection_is_recorded_and_unknown_ids_fail_before_any_request(monkeypatch):
    service, seen = scripted_service(monkeypatch)
    selected = ["live-01-tense-contrast", "live-05-missing-sentence-followup"]
    report = await run_live_suite(path=ORIGINAL, service=service, case_ids=selected)
    assert report["selected_case_ids"] == selected and report["total"] == 2
    assert report["budget"]["requests"] == 3
    before = len(seen)
    for ids in ([], ["unknown"], [selected[0], selected[0]]):
        with pytest.raises(ValueError, match="case selection"):
            await run_live_suite(path=ORIGINAL, service=service, case_ids=ids)
    assert len(seen) == before
