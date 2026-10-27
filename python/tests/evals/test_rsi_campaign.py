"""RSI 工程合同；全部模拟证据均明确不能获得真实发布资格。"""

import copy
import json
from pathlib import Path

import pytest

from core.policy_store import (BUILTIN_HASH, PolicyRegistry, artifact, atomic_json,
                               builtin_components, digest)
from evals.optimization.campaign import Campaign
from evals.optimization.gates import acceptance
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.loop import FailureQueue, ImprovementLoop
from evals.optimization.protocol import prepare_protocol, capability_name

DATASET = Path(__file__).parents[2] / "evals/datasets/tutor_agent50_rsi_v2.jsonl"


def create(tmp_path, **updates):
    protocol = tmp_path / "protocol.json"
    atomic_json(protocol, prepare_protocol(DATASET))
    config = {"max_requests": 1200, "max_cny": 10, "source_revision": "test",
              "runtime_hash": "test", "deployment_runtime_hash": "test",
              "simulation": True, "calibration_manifest": "", "max_metric_calls": 32,
              "minibatch": 1, **updates}
    registry = PolicyRegistry(tmp_path / "registry", runtime_hash="test", source_revision="test")
    return Campaign.create(tmp_path / "campaign", dataset=DATASET, protocol_path=protocol,
                           registry=registry, config=config, ledger=SharedLedger(tmp_path / "shared.sqlite"))


class FakeAdapter:
    calls = 0
    fail_at = None

    def __init__(self, cases, train_ids, budget, output, service=None):
        self.budget = budget

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def evaluate_rows(self, cases, policy):
        type(self).calls += 1
        index = self.budget.reserve_for("task", [], [], 10)
        if self.fail_at == self.calls:
            raise RuntimeError("simulated crash after request reservation")
        self.budget.settle(index, {"input_tokens": 1, "output_tokens": 1})
        passed = policy != builtin_components()
        return [{"case_id": c.case_id, "capability": capability_name(c),
                 "policy_sha256": digest(policy), "scoring_status": "completed",
                 "score": {"automatic_passed": True, "task_success": passed,
                           "score": float(passed), "decision_rate": 1}} for c in cases]


def start_dev(campaign):
    campaign.preflight()
    campaign.transition("searching", {"preflight_passed"})
    campaign.choose_candidate({"retrieval_rules": "先查找来源，再阅读全文并核对结论。"})


def test_budget_crash_shared_caps_and_unknown_reservation(tmp_path):
    store = SharedLedger(tmp_path / "ledger.sqlite")
    first = DurableBudget(store, "campaign", max_requests=3, max_cny=1)
    first.reserve_for("task", [], [], 10)
    resumed = DurableBudget(store, "campaign", max_requests=3, max_cny=1)
    resumed.recover()
    assert resumed.requests == 1 and resumed.ledger[0]["recovery_state"] == "unknown"
    assert resumed.unconfirmed_reservation_cny > 0
    index = resumed.reserve_for("judge", [], [], 10)
    resumed.settle(index, {"input_tokens": 10, "output_tokens": 5})
    first.reserve_for("reflection", [], [], 10)
    assert first.summary()["requests"] == 3
    from evals.optimization.budget import OptimizationStopped
    with pytest.raises(OptimizationStopped):
        resumed.reserve_for("task", [], [], 10)
    with pytest.raises(ValueError, match="frozen"):
        DurableBudget(store, "campaign", max_requests=4, max_cny=1)
    assert DurableBudget(store, "campaign", max_requests=3, max_cny=1).requests == 3


def test_holdout_is_global_and_failed_consumption_is_not_released(tmp_path):
    first = SharedLedger(tmp_path / "global.sqlite")
    first.consume_holdout("dataset", ["task1", "task2"], owner="one", binding="candidate")
    second = SharedLedger(tmp_path / "global.sqlite")
    second.consume_holdout("dataset", ["task1", "task2"], owner="one", binding="candidate")
    for dataset, signatures, owner, binding in [
        ("dataset", ["other"], "two", "candidate"),
        ("renamed", ["task1"], "two", "new"),
        ("dataset", ["task1", "task2"], "one", "new")]:
        with pytest.raises(ValueError, match="consumed"):
            second.consume_holdout(dataset, signatures, owner=owner, binding=binding)


def test_three_pairs_majority_and_holdout_strictness():
    def rows(successes, decision=1):
        return [{"case_id": "a", "repeat": i, "capability": "full_history_retrieval",
                 "score": {"automatic_passed": True, "task_success": success,
                           "score": float(success), "decision_rate": decision}}
                for i, success in enumerate(successes)]
    baseline, candidate = rows([False, False, False]), rows([True, True, False])
    assert acceptance(baseline, candidate, holdout=True)["passed"]
    assert not acceptance(baseline, rows([True, False, False]))["passed"]
    assert acceptance(rows([True] * 3, .5), rows([True] * 3))["passed"]
    assert not acceptance(rows([True] * 3, .5), rows([True] * 3), holdout=True)["passed"]
    with pytest.raises(ValueError, match="three"):
        acceptance(baseline[:1], candidate[:1])
    with pytest.raises(ValueError, match="duplicate"):
        acceptance(baseline + baseline, candidate + candidate)


def test_campaign_cannot_skip_dev_or_inherit_candidate(tmp_path):
    campaign = create(tmp_path)
    with pytest.raises(ValueError, match="development"):
        campaign.compare_holdout("missing", None)
    with pytest.raises(ValueError, match="search"):
        campaign.choose_candidate({"retrieval_rules": "新策略"})
    start_dev(campaign)
    with pytest.raises(ValueError, match="qualification"):
        campaign.qualify("missing")
    with pytest.raises(ValueError, match="simulation"):
        campaign.verify_eligibility()
    saved = json.loads((campaign.root / "campaign.json").read_text())
    saved["config"]["max_requests"] += 1
    atomic_json(campaign.root / "campaign.json", saved)
    with pytest.raises(ValueError, match="binding"):
        Campaign.open(campaign.root)


def test_comparison_resume_reuses_complete_rows_charges_retry(tmp_path):
    campaign = create(tmp_path)
    start_dev(campaign)
    FakeAdapter.calls, FakeAdapter.fail_at = 0, 3
    with pytest.raises(RuntimeError, match="crash"):
        campaign.execute(None, adapter_factory=FakeAdapter)
    assert campaign.data["state"] == "interrupted" and campaign.budget.requests == 3
    FakeAdapter.fail_at = None
    resumed = Campaign.open(campaign.root)
    assert resumed.execute(None, adapter_factory=FakeAdapter) == "dev_passed"
    assert FakeAdapter.calls == 85  # 14例×3次×2策略 + 一次未知请求
    assert resumed.budget.requests == 85
    assert resumed.budget.ledger[2]["recovery_state"] == "unknown"
    assert resumed.verify_receipt("dev")["passed"]
    receipt = json.loads((resumed.root / "dev/receipt.json").read_text())
    receipt["rows"]["candidate"][0]["score"]["task_success"] = False
    atomic_json(resumed.root / "dev/receipt.json", receipt)
    with pytest.raises(ValueError, match="binding"):
        resumed.verify_receipt("dev")


def test_registry_tamper_atomic_pointer_default_off_and_rollback(tmp_path):
    registry = PolicyRegistry(tmp_path, runtime_hash="runtime", source_revision="source")
    assert registry.active()["policy_hash"] == BUILTIN_HASH
    value = artifact({"retrieval_rules": "读取后再引用"}, parent=BUILTIN_HASH,
                     protocol="protocol", runtime="runtime", source="source",
                     proposer="proposer", evidence={})
    path = tmp_path / "artifacts" / f"{value['policy_hash']}.json"
    atomic_json(path, value)
    assert registry.read(value["policy_hash"]) == value
    with pytest.raises(PermissionError):
        registry.activate(value["policy_hash"])
    with pytest.raises(FileNotFoundError):
        registry.activate(value["policy_hash"], release_enabled=True)
    assert registry.active()["policy_hash"] == BUILTIN_HASH
    changed = copy.deepcopy(value)
    changed["components"]["retrieval_rules"] = "篡改"
    atomic_json(path, changed)
    with pytest.raises(ValueError, match="mismatch"):
        registry.read(value["policy_hash"])
    atomic_json(path, value)
    # 模拟已经在途的旧指针，回退内置无需伪造真实资格。
    atomic_json(tmp_path / "active.json", {"policy_hash": value["policy_hash"], "previous": BUILTIN_HASH})
    registry.rollback(release_enabled=True)
    assert registry.active()["policy_hash"] == BUILTIN_HASH
    assert len(list((tmp_path / "events").glob("*.json"))) == 1


def test_queue_sanitized_dedup_and_loop_wait_stop(tmp_path):
    queue = FailureQueue(tmp_path / "queue.sqlite")
    kwargs = {"evidence_digest": "a" * 64, "capability": "full_history_retrieval",
              "failure": "unread_source", "data_role": "development"}
    queue.enqueue(**kwargs)
    queue.enqueue(**kwargs)
    assert len(queue.pending()) == 1
    with pytest.raises(ValueError):
        queue.enqueue(**{**kwargs, "data_role": "holdout"})
    store = SharedLedger(tmp_path / "shared.sqlite")
    loop = ImprovementLoop(tmp_path / "loop", queue=queue, ledger=store, config={
        "max_generations": 1, "min_new_samples": 2, "max_stagnation": 1, "max_failures": 1,
        "max_requests": 1, "max_cny": 1})
    never = lambda *args: pytest.fail("must not launch")
    assert loop.run(never, never)["status"] == "waiting"
    loop.budget.reserve_for("task", [], [], 1)
    assert loop.run(never, never)["reason"] == "budget"


def test_loop_rejection_stops_at_stagnation_and_shares_budget(tmp_path):
    queue = FailureQueue(tmp_path / "queue.sqlite")
    queue.enqueue(evidence_digest="a" * 64, capability="grounded_history",
                  failure="unread_source", data_role="development")
    store = SharedLedger(tmp_path / "shared.sqlite")
    loop = ImprovementLoop(tmp_path / "loop", queue=queue, ledger=store, config={
        "max_generations": 5, "min_new_samples": 1, "max_stagnation": 1, "max_failures": 1,
        "max_requests": 100, "max_cny": 1})
    def factory(index, parent, records, caps):
        campaign = create(tmp_path / f"generation-{index}", **caps)
        return campaign
    def reject(campaign):
        campaign.transition("rejected", {"prepared"})
    # 同一个路径才是共享账本；子目录账本被拒绝。
    with pytest.raises(ValueError, match="escape"):
        loop.run(factory, reject)


def test_loop_stagnation_and_fault_are_bounded(tmp_path):
    for outcome in ("reject", "crash"):
        directory = tmp_path / outcome
        campaign = create(directory)
        queue = FailureQueue(directory / "queue.sqlite")
        queue.enqueue(evidence_digest="b" * 64, capability="grounded_history",
                      failure="unread_source", data_role="development")
        loop = ImprovementLoop(directory / "loop", queue=queue, ledger=campaign.store, config={
            "max_generations": 2, "min_new_samples": 1, "max_stagnation": 1, "max_failures": 1,
            "max_requests": 1200, "max_cny": 10})
        # 创建时注入共享 budget_id，模拟生成工厂的正式参数。
        config = {**campaign.config, "budget_id": loop.state["budget_id"]}
        registry = PolicyRegistry(directory / "registry", runtime_hash="test", source_revision="test")
        def factory(*args):
            return Campaign.create(directory / "loop-campaign", dataset=DATASET,
                                   protocol_path=directory / "protocol.json", registry=registry,
                                   config=config, ledger=campaign.store)
        def execute(value):
            if outcome == "crash":
                raise RuntimeError("fixture fault")
            value.transition("rejected", {"prepared"})
        state = loop.run(factory, execute)
        assert state["status"] == "stopped"
        assert state["reason"] == ("failures" if outcome == "crash" else "stagnation")
        assert not queue.pending()


def test_full_simulated_dev_holdout_path_still_cannot_release(tmp_path):
    from evals.live_cases import load_live_cases
    from evals.optimization.protocol import file_digest
    groups = {}
    for case in load_live_cases(DATASET):
        if case.template_case_id:
            groups.setdefault(capability_name(case), []).append(case)
    holdout = []
    for capability, group in groups.items():
        for index, original in enumerate(group[:3]):
            case = original.model_copy(deep=True)
            case.case_id = "holdout-" + original.case_id
            case.learner_id = "eval-live-holdout-" + original.learner_id
            for step in case.steps:
                if step.action == "converse":
                    step.student_input += f"（仅用于合同测试的不同材料 {capability}-{index}）"
            holdout.append(case)
    path = tmp_path / "holdout.jsonl"
    path.write_text("\n".join(c.model_dump_json(by_alias=True) for c in holdout))
    campaign = create(tmp_path, holdout_review_sha256=file_digest(path),
                      holdout_reviewer="simulation fixture, not a real semantic review")
    start_dev(campaign)
    FakeAdapter.calls, FakeAdapter.fail_at = 0, None
    assert campaign.compare_development(None, adapter_factory=FakeAdapter)["passed"]
    assert campaign.compare_holdout(path, None, adapter_factory=FakeAdapter)["passed"]
    assert campaign.data["state"] == "holdout_passed"
    assert campaign.verify_receipt("holdout")["passed"]
    with pytest.raises(ValueError, match="simulation"):
        campaign.verify_eligibility()
    assert campaign.budget.requests == (14 + 18) * 3 * 2


def test_health_monitor_minimum_window_and_old_policy_isolation(tmp_path):
    from core.policy_health import PolicyHealthMonitor
    class Registry:
        root = tmp_path
        def __init__(self):
            self.current, self.rollbacks = "candidate", 0
        def active(self):
            return {"policy_hash": self.current}
        def rollback(self, **kwargs):
            self.current = "parent"
            self.rollbacks += 1
    registry = Registry()
    monitor = PolicyHealthMonitor(registry, window=4, min_samples=3, max_commit_failure_rate=.5)
    assert not monitor.observe("candidate", "commit_failed", release_enabled=True)
    assert not monitor.observe("candidate", "completed", release_enabled=True)
    assert monitor.observe("candidate", "commit_failed", release_enabled=True)
    assert registry.rollbacks == 1
    assert not monitor.observe("candidate", "confirmed_permission_violation", release_enabled=True)
    assert registry.rollbacks == 1


def test_search_cache_recovers_completed_evaluation_without_request(tmp_path):
    from core.llm_service import LLMService
    from evals.live_cases import load_live_cases
    from evals.optimization.adapter import TutorGEPAAdapter
    from evals.optimization.budget import OptimizationBudget
    from tests.evals.test_policy_optimization import MockTextModel, mocked_service
    case = load_live_cases(DATASET)[0]
    budget = OptimizationBudget(max_requests=30, max_cny=1)
    def make():
        return TutorGEPAAdapter([case], [case.case_id], budget, tmp_path,
                                service=LLMService(), text_model=MockTextModel(budget),
                                service_factory=mocked_service)
    with make() as adapter:
        adapter.reuse_completed = True
        first = adapter.evaluate_rows([case], builtin_components())
    requests = budget.requests
    with make() as adapter:
        adapter.reuse_completed = True
        second = adapter.evaluate_rows([case], builtin_components())
    assert second == first and budget.requests == requests


def test_registry_registration_parent_inheritance_and_artifact_binding(tmp_path, monkeypatch):
    campaign = create(tmp_path)
    start_dev(campaign)
    # 明确模拟外部验收器，仅检验注册/继承数据链路，不落盘真实资格声明。
    monkeypatch.setattr(Campaign, "verify_eligibility", lambda self: None)
    campaign.data.update(state="holdout_passed", dev_receipt_hash="dev",
                         holdout_receipt_hash="holdout")
    path = tmp_path / "harness-fixture.json"
    atomic_json(path, {"simulation_fixture": True})
    campaign.qualify(path)
    policy_hash = campaign.register()
    registry = PolicyRegistry(tmp_path / "registry", runtime_hash="test", source_revision="test")
    registry.activate(policy_hash, release_enabled=True)
    child = Campaign.create(tmp_path / "child", dataset=DATASET, protocol_path=tmp_path / "protocol.json",
                            registry=registry, config=campaign.config, ledger=campaign.store)
    assert child.data["parent"]["policy_hash"] == policy_hash
    assert child.data["parent"]["components"] == campaign.data["candidate"]
    registry.rollback(release_enabled=True)
    assert registry.active()["policy_hash"] == BUILTIN_HASH
    campaign.data["artifact"]["components"] = builtin_components()
    with pytest.raises(ValueError, match="artifact"):
        campaign.policy_artifact()


def test_real_manifest_rejects_missing_or_mixed_model_identity(tmp_path):
    from evals.optimization.calibration import verify_manifest
    from evals.optimization.protocol import file_digest
    from evals.optimization.scoring import JUDGE_PROMPT
    evidence = tmp_path / "row.json"
    record = {
        "score": {"judge_prompt_sha256": digest(JUDGE_PROMPT), "review_status": "ai_reviewed",
                  "semantic": [{"id": "S1", "passed": True}]},
        "observed": {"steps": {"s1": {"result": {"teaching_response": {"response": "测试证据"}}}}},
    }
    atomic_json(evidence, record)
    manifest = tmp_path / "manifest.json"
    atomic_json(manifest, {"items": [{"evidence_path": "row.json",
                                     "evidence_sha256": file_digest(evidence),
                                     "step_id": "s1", "check_id": "S1"}]})
    with pytest.raises(ValueError, match="identity"):
        verify_manifest(manifest)
