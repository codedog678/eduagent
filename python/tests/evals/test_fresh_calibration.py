import copy
import json

import pytest

from core.policy_store import digest
from evals.io import write_json
from evals.live_budget import PRO_PRICING, cost_estimate
from evals.optimization.calibrate_fresh import (
    GENERATOR, JUDGE, verify_fresh_manifest,
)
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.protocol import file_digest


def test_mixed_model_prices_persist_across_budget_reopen(tmp_path):
    ledger = SharedLedger(tmp_path / "ledger.sqlite")
    budget = DurableBudget(ledger, "mixed", max_requests=10, max_cny=5)
    usage = {"input_tokens": 1000, "output_tokens": 200, "prompt_cache_hit_tokens": 500}
    first = budget.reserve_for("calibration_generator", [], [], 200, pricing=PRO_PRICING)
    reopened = DurableBudget(ledger, "mixed", max_requests=10, max_cny=5)
    reopened.settle(first, usage)
    second = reopened.reserve_for("judge", [], [], 200)
    reopened.settle(second, usage)
    expected = cost_estimate(usage, pricing=PRO_PRICING) + cost_estimate(usage)
    assert reopened.summary()["estimated_peak_cny"] == pytest.approx(expected)
    assert reopened.summary()["requests"] == 2
    assert reopened.ledger[first]["pricing"]["model"] == "deepseek-v4-pro"
    assert reopened.summary()["unconfirmed_reservation_cny"] == 0


def fresh_fixture(root, monkeypatch):
    monkeypatch.setattr("evals.optimization.calibrate_fresh.verify_spec", lambda spec: None)
    frozen = {"id": "01", "case": {"case_id": "c"}, "messages": [],
              "step_id": "s1", "semantic_ids": ["S1"]}
    spec = {"created_at": "1", "items": [frozen]}
    write_json(root / "spec.json", spec)
    sh = file_digest(root / "spec.json")
    generation = {"id": "01", "spec_sha256": sh, "created_at": "2",
                  "generator_identity": GENERATOR,
                  "input_sha256": digest({"messages": [], "tools": []}),
                  "response": "new response"}
    write_json(root / "generation.json", generation)
    label = {"id": "01", "generation_path": "generation.json",
             "generation_sha256": file_digest(root / "generation.json"),
             "group": "hint_compliant", "reference_passed": True, "reviewer": "reviewer",
             "reviewer_kind": "assistant", "disputed": False, "rationale": "process only"}
    write_json(root / "labels.json", {"created_at": "3", "spec_sha256": sh, "items": [label]})
    record = {"case": frozen["case"], "judge_identity": JUDGE,
              "observed": {"steps": {"s1": {"result": {
                  "teaching_response": {"response": "new response"}}}}}}
    write_json(root / "evidence.json", record)
    return {"fresh_provenance": {
        "spec_path": "spec.json", "spec_sha256": sh, "labels_path": "labels.json",
        "labels_sha256": file_digest(root / "labels.json"), "scoring_started_at": "4"},
        "items": [{**label, "evidence_path": "evidence.json",
                   "evidence_sha256": file_digest(root / "evidence.json"),
                   "semantic_ids": ["S1"]}]}


@pytest.mark.parametrize("tamper", ["label", "subset", "time", "response", "model", "input"])
def test_fresh_provenance_rejects_tampering(tmp_path, monkeypatch, tamper):
    manifest = fresh_fixture(tmp_path, monkeypatch)
    verify_fresh_manifest(tmp_path, manifest)
    if tamper == "label":
        manifest["items"][0]["reference_passed"] = False
    elif tamper == "subset":
        manifest["items"] = []
    elif tamper == "time":
        manifest["fresh_provenance"]["scoring_started_at"] = "2"
    elif tamper == "response":
        path = tmp_path / "evidence.json"
        record = json.loads(path.read_text())
        record["observed"]["steps"]["s1"]["result"]["teaching_response"]["response"] = "old"
        write_json(path, record)
        manifest["items"][0]["evidence_sha256"] = file_digest(path)
    else:
        path = tmp_path / "generation.json"
        generation = json.loads(path.read_text())
        if tamper == "model":
            generation["generator_identity"] = JUDGE
        else:
            generation["input_sha256"] = "changed"
        write_json(path, generation)
        lp = tmp_path / "labels.json"
        labels = json.loads(lp.read_text())
        labels["items"][0]["generation_sha256"] = file_digest(path)
        write_json(lp, labels)
        manifest["fresh_provenance"]["labels_sha256"] = file_digest(lp)
    with pytest.raises(ValueError):
        verify_fresh_manifest(tmp_path, manifest)


def test_development_cannot_become_independent_by_role_flag(tmp_path):
    from evals.optimization.calibration import verify_manifest
    write_json(tmp_path / "manifest.json", {"items": [], "data_role": "independent_calibration"})
    with pytest.raises(KeyError, match="fresh_provenance"):
        verify_manifest(tmp_path / "manifest.json")


@pytest.mark.asyncio
async def test_invalid_generation_keeps_slot_and_continues_without_retry(tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from evals.optimization import calibrate_fresh as fresh
    from evals.optimization.leakage import protocol_identity
    from evals.optimization.scoring import JUDGE_PROMPT
    source = Path(__file__).resolve().parents[3] / "docs/evals/rsi-campaigns/20261029-pro-validation/spec.json"
    spec = json.loads(source.read_text())
    spec.update(source_revision="frozen", scoring_protocol=protocol_identity(),
                judge_prompt_sha256=digest(JUDGE_PROMPT), items=spec["items"][:2],
                start_budget={"requests": 0}, max_new_requests=2)
    write_json(tmp_path / "spec.json", spec)
    monkeypatch.setattr(fresh, "code_revision", lambda: {"python_source_sha256": "frozen"})
    monkeypatch.setattr(fresh, "get_llm_service", lambda: SimpleNamespace(
        **JUDGE, api_key="test", base_url="local"))
    budget = DurableBudget(SharedLedger(tmp_path / "ledger.sqlite"), "test",
                           max_requests=1600, max_cny=5)
    monkeypatch.setattr(fresh, "SharedLedger", lambda: budget.store)
    monkeypatch.setattr(fresh, "DurableBudget", lambda *args, **kwargs: budget)
    outputs = iter(["   ", '{"response":"valid response"}'])
    calls = []

    class Fake:
        def __init__(self, *args, **kwargs):
            pass

        async def complete(self, messages, **kwargs):
            calls.append(messages)
            index = budget.reserve_for("calibration_generator", messages, [], 900)
            budget.settle(index, {"input_tokens": 100, "output_tokens": 10})
            return next(outputs)

    monkeypatch.setattr(fresh, "TextModel", Fake)
    assert await fresh.run(tmp_path, "generate") == 0
    assert json.loads((tmp_path / "generated/01.json").read_text())["status"] == "generation_invalid"
    assert json.loads((tmp_path / "generated/02.json").read_text())["response"] == "valid response"
    assert await fresh.run(tmp_path, "generate") == 0
    assert len(calls) == 2 and budget.summary()["requests"] == 2


def test_direct_leaks_cannot_fill_indirect_coverage_or_hide_misses():
    from evals.optimization.calibration import GROUPS, calibration_report
    rows = [{"group": group, "response": f"{group}:{i}", "reviewer_kind": "assistant",
             "reviewer": "test", "reference_passed": group in ("retrieval_correct", "hint_compliant"),
             "judge_passed": group in ("retrieval_correct", "hint_compliant")}
            for group in GROUPS for i in range(5)]
    extra = {"group": "hint_direct_leak", "response": "direct", "reference_passed": False,
             "judge_passed": True, "reviewer_kind": "assistant", "reviewer": "test"}
    assert not calibration_report(rows + [extra])["passed"]
    extra["judge_passed"] = False
    report = calibration_report(rows[:-1] + [extra])
    assert report["counts"]["hint_indirect_leak"] == 4 and not report["passed"]
