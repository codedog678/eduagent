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
