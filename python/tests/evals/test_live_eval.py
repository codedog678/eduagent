"""模拟原生模型验证真实评测链路；所有测试禁止访问供应商。"""

import json
from pathlib import Path

import pytest

from config.settings import settings
from core.llm_service import LLMService, NativeToolCall, NativeTurn
from core.run_context import active_run, RunExhausted
from evals.io import DatasetError
from evals.live_budget import LiveBudget, cost_estimate
from evals.live_cases import load_live_cases
from evals.live_executor import LiveExecutor
from evals.live_runner import run_live_suite
from evals.live_scorers import score_live_case


DATASET = Path(__file__).resolve().parents[2] / "evals/datasets/tutor_live12_review.jsonl"


def test_reviewed_cases_load_and_reject_unknown_contract(tmp_path):
    cases = load_live_cases(DATASET)
    assert len(cases) == 12
    bad = cases[0].model_dump(by_alias=True)
    bad["case_id"] = "live-99-unsupported"
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(bad))
    with pytest.raises(DatasetError):
        load_live_cases(path)


def test_budget_counts_failed_requests_and_reserves_unknown_usage():
    budget = LiveBudget(max_requests=1)
    index = budget.reserve([], [], 800)
    assert budget.requests == 1
    assert budget.summary()["unconfirmed_reservation_cny"] > 0
    budget.settle(index, {})
    with pytest.raises(RunExhausted, match="live_request_budget"):
        budget.reserve([], [], 800)
    budget.settle(index, {"input_tokens": 1000, "output_tokens": 100,
                          "prompt_cache_hit_tokens": 500, "prompt_cache_miss_tokens": 500})
    assert budget.summary()["unconfirmed_reservation_cny"] == pytest.approx(0)
    assert budget.estimated_peak_cny == pytest.approx(0.00182)


def test_budget_stops_before_request_when_reservation_exceeds_cost():
    budget = LiveBudget(max_cny=0.00001)
    with pytest.raises(RunExhausted, match="live_cost_budget"):
        budget.reserve([{"content": "很长的输入" * 100}], [], 800)
    assert budget.requests == 0
    assert cost_estimate({"input_tokens": 1000, "output_tokens": 100}) == pytest.approx(.0028)
    with pytest.raises(ValueError):
        LiveBudget(max_requests=43)


def scripted_service(monkeypatch, mode="normal"):
    service = LLMService(provider="deepseek", api_key="test-only", model="deepseek-flash")
    seen, counts = [], {}

    async def turn(messages, tools, max_tokens):
        ctx = active_run.get()
        learner = ctx.learner
        counts[learner] = counts.get(learner, 0) + 1
        count = counts[learner]
        seen.append((learner, json.loads(json.dumps(messages))))
        tool = None
        content = "模拟公开回复；语义仍须审阅。"
        if mode == "no_ask":
            content = "请给原句。"
        elif mode == "unregistered":
            if count == 1:
                tool = ("update_mastery", {"mastery": 1})
        elif mode == "truncated":
            return NativeTurn(content="截断", stop_reason="length",
                              usage={"input_tokens": 500, "output_tokens": 800})
        elif learner in {"eval-live-05", "eval-live-06"} and count == 1:
            tool = ("ask_student", {"question": "请补充原句或阅读目标。"})
        elif learner == "eval-live-08":
            if count == 1:
                tool = ("search_learning_history", {"query": "R08", "limit": 10})
            elif count == 2:
                tool = ("read_learning_history", {"source_ref": "message:eval-live-08-target"})
            else:
                content = "旧笔记的口令是“先圈时间，再看是否到现在。”"
        elif learner == "eval-live-10-alice" and count == 1:
            tool = ("read_learning_history", {"source_ref": "message:eval-live-10-bob-secret"})
        return NativeTurn(
            content="" if tool else content,
            tool_calls=[NativeToolCall(id=f"call-{count}", name=tool[0],
                                       arguments=json.dumps(tool[1]))] if tool else [],
            stop_reason="tool_calls" if tool else "stop",
            usage={"input_tokens": 500, "output_tokens": 50,
                   "prompt_cache_hit_tokens": 100, "prompt_cache_miss_tokens": 400},
            reasoning_content="private-test-thought",
        )

    monkeypatch.setattr(service, "tool_turn", turn)
    monkeypatch.setattr("core.llm_service._llm_service", service)
    return service, seen


@pytest.mark.asyncio
async def test_all_12_use_harness_and_leave_semantics_pending(monkeypatch, tmp_path):
    service, seen = scripted_service(monkeypatch)
    original_turn = service.tool_turn
    output = tmp_path / "live.json"
    original_config = settings.enable_agent_llm_decisions
    report = await run_live_suite(path=DATASET, output=output, service=service)
    assert report["total"] == 12
    assert report["groups"]["agent_primary"]["automatic_passed"] == 8
    assert report["groups"]["teaching_auxiliary"]["automatic_passed"] == 4
    assert sum(r["status"] == "review_pending" for r in report["results"]) == 11
    assert report["results"][7]["status"] == "passed"  # 原文与工具路径均可自动核对
    assert all(r["quality_review"]["scores"] is None for r in report["results"])
    assert report["budget"]["requests"] == 17
    assert service.tool_turn is original_turn
    assert settings.enable_agent_llm_decisions is original_config
    assert "private-test-thought" not in output.read_text()
    assert "test-only" not in output.read_text()
    assert output.with_suffix(".md").exists()
    for learner, messages in seen:
        serialized = json.dumps(messages, ensure_ascii=False)
        assert '"correct_index"' not in serialized and '"explanation"' not in serialized
        if learner == "eval-live-10-alice":
            assert "EVAL_PRIVATE_Z9" not in serialized
        if learner == "eval-live-12":
            assert "scarce" not in serialized and "eval-live-12-q2" not in serialized
    final12 = report["results"][11]["observed"]["final"]
    assert final12["knowledge"]["eval-live-12"]["mastery"] == pytest.approx(.43333333333333335)
    assert [e["quiz_id"] for e in final12["evidence"] if e["kind"] == "assistance"] == ["eval-live-12-q1"]


@pytest.mark.asyncio
async def test_plain_text_question_blocks_required_followup(monkeypatch):
    service, seen = scripted_service(monkeypatch, "no_ask")
    case = load_live_cases(DATASET)[4]
    executor = LiveExecutor(case, service, LiveBudget())
    temporary_path = Path(executor._temporary.name)
    try:
        observed = await executor.execute()
        result = score_live_case(case, observed)
    finally:
        executor.close()
    assert observed["steps"]["s2"]["status"] == "blocked_by_prior_step"
    assert result["status"] == "failed"
    assert len(seen) == 1 and not temporary_path.exists()


@pytest.mark.asyncio
async def test_model_violation_not_credited_as_server_safety_success(monkeypatch):
    service, _ = scripted_service(monkeypatch, "unregistered")
    case = load_live_cases(DATASET)[8]
    executor = LiveExecutor(case, service, LiveBudget())
    try:
        result = score_live_case(case, await executor.execute())
    finally:
        executor.close()
    assert result["status"] == "failed"
    assert result["hard_checks"][1]["passed"] is False
    assert result["annotations"]["server_denials"] == 1
    assert result["hard_checks"][2]["passed"] is True  # 状态门禁仍保护掌握度


@pytest.mark.asyncio
async def test_truncated_output_rolls_back_help_and_blocks_assessment(monkeypatch):
    service, _ = scripted_service(monkeypatch, "truncated")
    case = load_live_cases(DATASET)[10]
    executor = LiveExecutor(case, service, LiveBudget())
    try:
        observed = await executor.execute()
    finally:
        executor.close()
    assert observed["steps"]["s1"]["status"] == "exhausted"
    assert observed["steps"]["s1"]["stop_reason"] == "output_token_limit"
    assert observed["steps"]["s2"]["status"] == "blocked_by_prior_step"
    assert observed["final"]["quizzes"]["eval-live-11-q1"]["assisted"] is False
    assert observed["final"]["evidence"] == []


@pytest.mark.asyncio
async def test_batch_request_cap_prevents_other_cases_from_calling_model(monkeypatch):
    service, seen = scripted_service(monkeypatch)
    report = await run_live_suite(path=DATASET, max_requests=1, service=service)
    assert report["total"] == 12 and len(seen) == 1
    assert report["budget"]["requests"] == 1
    assert report["results"][1]["observed"]["steps"]["s1"]["status"] == "batch_budget_exhausted"
