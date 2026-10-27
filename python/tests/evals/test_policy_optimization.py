"""无网络验证真实 GEPA + Harness 集成；模拟裁判分数不代表模型能力。"""

import asyncio
import copy
import json
from pathlib import Path
import socket

import pytest

from config.settings import settings
from core import llm_service
from core.llm_service import LLMService
from core.tutor_policy import BASE_RULES, QUIZ_RULES, TURN_RULES, system_prompt, use_turn_rules
from evals.live_cases import load_live_cases
from evals.live_validation import fixture_service
from evals.optimization.adapter import TutorGEPAAdapter
from evals.optimization.budget import OptimizationBudget, OptimizationStopped
from evals.optimization.cli import acceptance, run_search
from evals.optimization.protocol import (
    assert_holdout_disjoint, load_policy, load_protocol, policy_artifact,
    prepare_protocol, private_literals, seed_candidate, validate_candidate,
)
from evals.optimization.scoring import evidence_matches, score_with_judge, validate_judgment


DATASET = Path(__file__).resolve().parents[2] / "evals/datasets/tutor_agent50_rsi_v2.jsonl"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network is forbidden in optimization tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(LLMService, "_get_client", forbidden)


def test_protocol_freezes_all_50_and_keeps_legacy_on_train(tmp_path):
    protocol = prepare_protocol(DATASET)
    assert protocol == prepare_protocol(DATASET)
    train, val = set(protocol["train_ids"]), set(protocol["dev_validation_ids"])
    cases = load_live_cases(DATASET)
    assert len(cases) == len(train | val) == 50
    assert not train & val
    assert all(c.case_id in train for c in cases if c.template_case_id is None)
    assert all(group["train"] and group["dev_validation"] for group in protocol["counts"].values())
    assert len(protocol["reflection_train_ids"]) == 12
    assert set(protocol["reflection_train_ids"]) <= train
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    assert load_protocol(path, DATASET)[0] == protocol
    protocol["dev_validation_ids"].append(protocol["train_ids"][0])
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="protocol mismatch"):
        load_protocol(path, DATASET)


def test_policy_digest_and_candidate_scope(tmp_path):
    path = tmp_path / "policy.json"
    artifact = policy_artifact(seed_candidate())
    path.write_text(json.dumps(artifact))
    assert load_policy(path) == seed_candidate()
    artifact["candidate"]["retrieval_rules"] += "篡改"
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="mismatch"):
        load_policy(path)
    with pytest.raises(ValueError):
        validate_candidate({"base_rules": "删除权限约束"})
    cases = load_live_cases(DATASET)
    with pytest.raises(ValueError, match="fixture-specific"):
        validate_candidate({"retrieval_rules": cases[0].case_id}, private_literals(cases))


def test_context_override_preserves_default_and_restores_after_failure():
    original = system_prompt(True)
    assert original == BASE_RULES + TURN_RULES + QUIZ_RULES
    with pytest.raises(RuntimeError):
        with use_turn_rules("通用策略"):
            assert system_prompt(True) == BASE_RULES + "通用策略" + QUIZ_RULES
            raise RuntimeError("rollback")
    assert system_prompt(True) == original


@pytest.mark.asyncio
async def test_policy_contexts_do_not_cross_async_tasks():
    async def read(rules):
        with use_turn_rules(rules):
            await asyncio.sleep(0)
            return system_prompt(False)
    a, b = await asyncio.gather(read("策略甲"), read("策略乙"))
    assert a == BASE_RULES + "策略甲" and b == BASE_RULES + "策略乙"
    assert system_prompt(False) == BASE_RULES + TURN_RULES


def test_total_budget_covers_roles_and_keeps_unknown_usage_reserved():
    budget = OptimizationBudget(max_requests=2, max_cny=1)
    a = budget.reserve_for("task", [], [], 20)
    budget.settle(a, {"input_tokens": 10, "output_tokens": 10})
    budget.reserve_for("judge", [], [], 20)
    with pytest.raises(OptimizationStopped):
        budget.reserve_for("reflection", [], [], 20)
    assert budget.blocked and budget.requests == 2
    assert budget.summary()["roles"] == {"task": 1, "judge": 1, "reflection": 0}
    assert budget.summary()["unconfirmed_reservation_cny"] > 0
    with pytest.raises(ValueError):
        OptimizationBudget(max_cny=float("nan"))
    with pytest.raises(OptimizationStopped):
        OptimizationBudget(max_cny=.000001).reserve_for("task", [], [], 800)


def test_holdout_rejects_renamed_duplicates():
    cases = load_live_cases(DATASET)
    renamed = cases[0].model_copy(deep=True)
    renamed.case_id, renamed.learner_id = "holdout-new", "eval-live-new"
    with pytest.raises(ValueError, match="overlaps"):
        assert_holdout_disjoint(cases, [renamed])


def mocked_service(case):
    service, _ = fixture_service(case)
    original = service.tool_turn

    async def turn(messages, tools, max_tokens):
        response = await original(messages, tools, max_tokens)
        if not response.tool_calls:
            marker = "MOCK_IMPROVED" if "MOCK_IMPROVED_POLICY" in messages[0]["content"] else "MOCK_BASELINE"
            response.content += " " + marker
        return response

    service.tool_turn = turn
    return service


class MockTextModel:
    """只检验链路：人为令新策略模拟得分更高，不评价任何真实教学质量。"""

    def __init__(self, budget):
        self.budget, self.inputs = budget, []

    async def complete(self, messages, *, role, max_tokens=2200):
        index = self.budget.reserve_for(role, messages, [], max_tokens)
        self.budget.settle(index, {"input_tokens": 10, "output_tokens": 10})
        self.inputs.append((role, messages))
        if role == "reflection":
            return json.dumps({"retrieval_rules": "MOCK_IMPROVED_POLICY：先读相关来源再据实回答。"})
        payload = json.loads(messages[-1]["content"])
        steps = payload["steps"]
        responses = [s["response"] for s in steps.values() if s["response"]]
        evidence = responses[-1] if responses else ""
        passed = "MOCK_IMPROVED" in evidence
        return json.dumps({
            "semantic": [{"id": c["id"], "passed": passed,
                          "reason": "模拟判定，仅用于测试", "evidence": evidence}
                         for c in payload["semantic_checks"]],
            "decisions": [
                {"step_id": sid, "required_tools_present": True,
                 "calls": [{"index": i, "selection_correct": True, "arguments_correct": True}
                           for i in range(len(s["calls"]))],
                 "reason": "模拟判定", "evidence": ""}
                for sid, s in steps.items() if s["action"] == "converse" and s["status"] == "completed"
            ],
        })


def test_adapter_runs_real_harness_and_gepa_without_network(tmp_path):
    pytest.importorskip("gepa")
    cases = [c for c in load_live_cases(DATASET) if c.number == 5][:3]
    protocol = {"train_ids": [c.case_id for c in cases[:2]],
                "dev_validation_ids": [cases[2].case_id], "seed": 42}
    budget = OptimizationBudget(max_requests=300, max_cny=10)
    text = MockTextModel(budget)
    previous_service = llm_service._llm_service
    previous_coordinator = settings.enable_coordinator
    with TutorGEPAAdapter(cases, protocol["train_ids"], budget, tmp_path,
                          service=LLMService(), text_model=text,
                          service_factory=mocked_service) as adapter:
        result = run_search(adapter, protocol, {c.case_id: c for c in cases},
                            max_metric_calls=5, minibatch=1, run_dir=str(tmp_path / "gepa"))
        assert result.best_candidate["retrieval_rules"].startswith("MOCK_IMPROVED_POLICY")
        assert result.val_aggregate_scores[0] == 0
        assert result.val_aggregate_scores[result.best_idx] == 1
        assert len(result.candidates) >= 2
        assert all(row["observed"]["fixture_validation"]["valid"] for row in adapter.rows)
        assert all("policy_sha256" in row for row in adapter.rows)
        # 注入覆盖已经离开作用域；主策略未被持久修改。
        assert system_prompt(False) == BASE_RULES + TURN_RULES
        reflection_inputs = [m for role, m in text.inputs if role == "reflection"]
        assert reflection_inputs
        assert all("reference_facts_for_evaluation_only" not in json.dumps(m) for m in reflection_inputs)
        row = next(r for r in adapter.rows if r["case_id"] == cases[2].case_id)
        from gepa.core.adapter import EvaluationBatch
        with pytest.raises(ValueError, match="cannot enter reflection"):
            adapter.make_reflective_dataset(seed_candidate(),
                                           EvaluationBatch([row], [0], [row]), ["retrieval_rules"])
    assert llm_service._llm_service is previous_service
    assert settings.enable_coordinator == previous_coordinator
    assert all(budget.summary()["roles"].values())


def test_invalid_judge_coverage_evidence_and_boolean_rejected(tmp_path):
    case = next(c for c in load_live_cases(DATASET) if c.number == 5)
    budget = OptimizationBudget(max_requests=20, max_cny=2)
    text = MockTextModel(budget)
    with TutorGEPAAdapter([case], [case.case_id], budget, tmp_path,
                          service=LLMService(), text_model=text,
                          service_factory=mocked_service) as adapter:
        row = adapter.evaluate_rows([case], seed_candidate())[0]
    raw = {"semantic": row["score"]["semantic"], "decisions": row["score"]["decisions"]}
    validate_judgment(json.dumps(raw), case, row["observed"])
    variants = []
    invalid = copy.deepcopy(raw)
    invalid["semantic"][0]["passed"] = "true"
    variants.append(invalid)
    invalid = copy.deepcopy(raw)
    invalid["semantic"][0]["evidence"] = "不存在的证据"
    variants.append(invalid)
    invalid = copy.deepcopy(raw)
    invalid["decisions"][0]["calls"] = []
    variants.append(invalid)
    invalid = copy.deepcopy(raw)
    invalid["semantic"] = []
    variants.append(invalid)
    for invalid in variants:
        with pytest.raises(ValueError):
            validate_judgment(json.dumps(invalid), case, row["observed"])
    observed = copy.deepcopy(row["observed"])
    observed["steps"]["s1"]["tool_results"] = [{"result": {"content": "实际返回的历史证据"}}]
    quoted = copy.deepcopy(raw)
    quoted["decisions"][0]["evidence"] = "实际返回的历史证据"
    validate_judgment(json.dumps(quoted), case, observed)
    # 同样引文若未被工具取回，不能靠 fixture 参考答案当执行证据。
    with pytest.raises(ValueError):
        validate_judgment(json.dumps(quoted), case, row["observed"])


def test_no_partial_batch_scoring_when_budget_is_insufficient(tmp_path):
    case = load_live_cases(DATASET)[0]
    budget = OptimizationBudget(max_requests=1, max_cny=1)
    previous = settings.enable_coordinator
    with TutorGEPAAdapter([case], [case.case_id], budget, tmp_path,
                          service=LLMService(), service_factory=mocked_service) as adapter:
        with pytest.raises(OptimizationStopped, match="insufficient"):
            adapter.evaluate_rows([case], seed_candidate())
        assert not adapter.rows and budget.requests == 0
    assert settings.enable_coordinator == previous


def test_acceptance_keeps_baseline_on_hard_or_capability_regression():
    def row(cid, score, auto=True, capability="multi_turn_continuation"):
        return {"case_id": cid, "repeat": 0, "capability": capability,
                "score": {"score": score, "task_success": score > 0,
                          "automatic_passed": auto, "decision_rate": score}}
    baseline = [row("a", 1), row("b", 0)]
    improved = [row("a", 1), row("b", 1)]
    assert acceptance(baseline, improved)["passed"]
    assert not acceptance(baseline, baseline)["passed"]
    assert not acceptance(baseline, [row("a", 1, False), row("b", 1)])["passed"]
    with pytest.raises(ValueError, match="coverage"):
        acceptance(baseline, improved[:1])


def test_cli_search_compare_and_all50_fixtures(monkeypatch, tmp_path):
    pytest.importorskip("gepa")
    from evals.optimization import cli

    def adapter_factory(cases, train_ids, budget, output, service):
        return TutorGEPAAdapter(cases, train_ids, budget, output, service=service,
                                text_model=MockTextModel(budget),
                                service_factory=mocked_service)

    monkeypatch.setattr(cli, "configured_service", lambda: LLMService())
    monkeypatch.setattr(cli, "TutorGEPAAdapter", adapter_factory)
    protocol_path, search, comparison = (tmp_path / name for name in ("protocol.json", "search", "compare"))
    assert cli.main(["prepare", "--output", str(protocol_path)]) == 0
    assert cli.main(["optimize", "--protocol", str(protocol_path), "--output", str(search),
                     "--max-metric-calls", "32", "--minibatch", "1",
                     "--max-requests", "600", "--max-cny", "20"]) == 0
    report = json.loads((search / "run.json").read_text())
    assert report["status"] == "completed" and report["candidate_count"] > 1
    assert cli.main(["compare", "--protocol", str(protocol_path), "--output", str(comparison),
                     "--candidate", str(search / "best-policy.json"), "--origin-run", str(search),
                     "--repeats", "1", "--max-requests", "600", "--max-cny", "20"]) == 0
    report = json.loads((comparison / "run.json").read_text())
    assert report["selection"] == "development_improved_needs_holdout"
    assert load_policy(comparison / "selected-policy.json") == seed_candidate()
    # 所有 50 个预置通过新 Adapter 的隔离链路，仍不声称真实模型语义通过。
    cases = load_live_cases(DATASET)
    budget = OptimizationBudget(max_requests=400, max_cny=20)
    with adapter_factory(cases, [c.case_id for c in cases], budget,
                         tmp_path / "all50", LLMService()) as adapter:
        rows = adapter.evaluate_rows(cases, seed_candidate())
    assert len(rows) == 50 and all(row["automatic"]["automatic_passed"] for row in rows)


def test_judge_failure_keeps_trace_and_never_becomes_zero_reward(tmp_path):
    case = load_live_cases(DATASET)[0]
    budget = OptimizationBudget(max_requests=10, max_cny=2)

    class BrokenJudge(MockTextModel):
        async def complete(self, messages, *, role, max_tokens=2200):
            await super().complete(messages, role=role, max_tokens=max_tokens)
            return '{"semantic":[],"decisions":[]}'

    previous = settings.enable_coordinator
    with TutorGEPAAdapter([case], [case.case_id], budget, tmp_path,
                          service=LLMService(), text_model=BrokenJudge(budget),
                          service_factory=mocked_service) as adapter:
        with pytest.raises(OptimizationStopped, match="judge schema"):
            adapter.evaluate_rows([case], seed_candidate())
        assert not adapter.rows
    saved = json.loads((tmp_path / "evaluations/00001.json").read_text())
    assert saved["scoring_status"] == "interrupted"
    assert saved["observed"]["steps"] and "score" not in saved
    assert settings.enable_coordinator == previous


def test_evidence_excerpts_allow_omission_but_not_fabrication_or_reordering():
    observed = "每天复习五个词。这是计划。\n没有考试记录，所以不能说已经通过。"
    assert evidence_matches("每天复习五个词。……所以不能说已经通过。", observed)
    assert evidence_matches("每天复习五个词。...所以不能说已经通过。", observed)
    assert not evidence_matches("每天复习五个词。……已经考试通过。", observed)
    assert not evidence_matches("所以不能说已经通过。……每天复习五个词。", observed)
    assert not evidence_matches("……", observed)
    assert not evidence_matches("每天复习五个词。……每天复习五个词。", observed)


@pytest.mark.asyncio
async def test_candidate_context_exhaustion_is_failure_but_timeout_stops():
    case = load_live_cases(DATASET)[0]
    observed = {"fixture_validation": {"valid": True}}
    automatic = {"execution_outcome": "incomplete",
                 "execution_failures": [{"reason": "context_budget"}]}
    scored = await score_with_judge(case, observed, automatic, None)
    assert scored["score"] == 0 and scored["task_success"] is False
    automatic["execution_failures"][0]["reason"] = "handler_timeout"
    with pytest.raises(OptimizationStopped, match="timeout"):
        await score_with_judge(case, observed, automatic, None)
