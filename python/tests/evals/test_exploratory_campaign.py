from types import SimpleNamespace
import json

import pytest

from core.policy_store import builtin_components
from evals.optimization.campaign import Campaign
from evals.optimization.exploratory import check_exploratory_calibration, describe_comparison
from tests.evals.test_rsi_campaign import create, FakeAdapter


def row(case_id, passed, repeat=0):
    return {"case_id": case_id, "repeat": repeat,
            "scoring_status": "unknown" if passed is None else "completed",
            "score": {"task_success": passed, "score": None if passed is None else float(passed),
                      "automatic_passed": True, "decision_rate": None if passed is None else 1}}


def test_unknowns_are_not_zero_or_success_and_bounds_include_missing():
    baseline = [row("a", False), row("b", True), row("c", False)]
    candidate = [row("a", True), row("b", None)]
    report = describe_comparison(baseline, candidate, {(0, c) for c in ("a", "b", "c")})
    assert report["complete_pairs"] == 1 and len(report["unknown_pairs"]) == 2
    assert report["net_wins"] == 1
    assert report["candidate"]["all_cases_success_rate_bounds"] == [1/3, 1]
    assert report["success_rate_delta_bounds"] == [-1/3, 1]
    assert not report["improvement_robust_to_unknown"]
    assert not report["promotion_eligible"]
    with pytest.raises(ValueError, match="duplicate"):
        describe_comparison(baseline + baseline, candidate, {(0, c) for c in ("a", "b", "c")})


def test_exploratory_calibration_accepts_observed_but_unqualified_evidence():
    report = {"passed": False, "agreement": .9545,
              "counts": {"retrieval_correct": 6, "retrieval_misanswer": 6,
                         "hint_compliant": 5, "hint_indirect_leak": 5}}
    assert check_exploratory_calibration(report)["admitted"]
    with pytest.raises(ValueError):
        check_exploratory_calibration({**report, "agreement": .5})


def test_exploration_never_enters_qualification(tmp_path):
    campaign = create(tmp_path, mode="exploratory")
    for operation in (lambda: campaign.compare_holdout("unused", None),
                      lambda: campaign.qualify("unused"), campaign.verify_eligibility,
                      campaign.policy_artifact, campaign.register):
        with pytest.raises(ValueError, match="exploratory"):
            operation()
    assert campaign.data["candidate"] is None


class ExplorationFake(FakeAdapter):
    proposals = 0
    reflected = []

    def __init__(self, cases, train_ids, budget, output, service=None):
        super().__init__(cases, train_ids, budget, output, service)
        self.train_ids = set(train_ids)

    def make_reflective_dataset(self, candidate, batch, components):
        ids = {r["case_id"] for r in batch.trajectories}
        assert ids <= self.train_ids
        type(self).reflected.append(ids)
        return {"retrieval_rules": []}

    def propose_new_texts(self, candidate, feedback, components):
        type(self).proposals += 1
        index = self.budget.reserve_for("reflection", [], [], 10)
        self.budget.settle(index, {"input_tokens": 1, "output_tokens": 1})
        return {"retrieval_rules": f"先检索再阅读全文，探索代数{self.proposals}。"}


def test_exploration_completes_two_generations_and_resume_without_repeating(tmp_path):
    campaign = create(tmp_path, mode="exploratory", exploration_generations=2, exploration_repeats=2)
    ExplorationFake.calls, ExplorationFake.fail_at = 0, 20
    ExplorationFake.proposals, ExplorationFake.reflected = 0, []
    with pytest.raises(RuntimeError, match="crash"):
        campaign.execute(None, adapter_factory=ExplorationFake)
    assert campaign.data["state"] == "interrupted"
    ExplorationFake.fail_at = None
    resumed = Campaign.open(campaign.root)
    assert resumed.execute(None, adapter_factory=ExplorationFake) == "exploration_completed"
    report = json.loads((resumed.root / "exploration/report.json").read_text())
    assert len(report["comparisons"]) == 2
    assert report["comparisons"]["candidate-1"]["complete_pairs"] == 28
    assert len(report["comparisons"]["candidate-1"]["wins"]) == 28
    assert report["candidate_for_review"] == "candidate-1"
    assert not report["promotion_eligible"]
    assert resumed.data["candidate"] is None
    assert ExplorationFake.calls == 121  # 120次观测，加一次中断；两个提案各一次。
    assert ExplorationFake.proposals == 2
    requests = resumed.budget.summary()["requests"]
    assert resumed.execute(None, adapter_factory=ExplorationFake) == "exploration_completed"
    assert resumed.budget.summary()["requests"] == requests


def test_unknown_cannot_enter_scalar_gepa_or_reflection(tmp_path):
    from core.llm_service import LLMService
    from evals.optimization.adapter import TutorGEPAAdapter
    from evals.optimization.budget import OptimizationBudget, OptimizationStopped
    with TutorGEPAAdapter([], [], OptimizationBudget(max_requests=5, max_cny=1),
                          tmp_path, service=LLMService()) as adapter:
        unknown = row("a", None)
        adapter.evaluate_rows = lambda *args: [unknown]
        with pytest.raises(OptimizationStopped, match="unknown"):
            adapter.evaluate([], builtin_components())
        with pytest.raises(ValueError, match="unknown"):
            adapter.make_reflective_dataset(builtin_components(),
                                           SimpleNamespace(trajectories=[unknown]),
                                           ["retrieval_rules"])


def test_real_adapter_preserves_judge_failure_as_unknown_only_when_enabled(tmp_path):
    from core.llm_service import LLMService
    from evals.live_cases import load_live_cases
    from evals.optimization.adapter import TutorGEPAAdapter
    from evals.optimization.budget import OptimizationBudget, OptimizationStopped
    from tests.evals.test_policy_optimization import mocked_service, DATASET
    case = load_live_cases(DATASET)[0]
    budget = OptimizationBudget(max_requests=30, max_cny=1)

    class InvalidJudge:
        async def complete(self, messages, **kwargs):
            index = budget.reserve_for("judge", messages, [], 20)
            budget.settle(index, {"input_tokens": 10, "output_tokens": 10})
            return '{"semantic": [], "decisions": []}'

    with TutorGEPAAdapter([case], [], budget, tmp_path / "strict", service=LLMService(),
                          text_model=InvalidJudge(), service_factory=mocked_service) as adapter:
        with pytest.raises(OptimizationStopped):
            adapter.evaluate_rows([case], builtin_components())
    with TutorGEPAAdapter([case], [], budget, tmp_path / "explore", service=LLMService(),
                          text_model=InvalidJudge(), service_factory=mocked_service) as adapter:
        adapter.tolerate_judge_failure = True
        adapter.reuse_completed = True
        result = adapter.evaluate_rows([case], builtin_components())[0]
        assert result["scoring_status"] == "unknown" and result["score"]["score"] is None
        assert result["score"]["task_success"] is None
        assert result["judge_diagnostic"]["raw_response"] == '{"semantic": [], "decisions": []}'
        requests = budget.requests
        assert adapter.evaluate_rows([case], builtin_components())[0] == result
        assert budget.requests == requests
