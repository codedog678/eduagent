"""长任务数据、评分和 CLI 基础行为。"""

from pathlib import Path
import json

import pytest

from core import llm_service
from core.llm_service import LLMResponse, LLMService, NativeTurn
from core.run_context import active_run
from evals.long_task_executor import LongTaskExecutor
from evals.long_task_models import load_long_task_cases
from evals.long_task_runner import validate_long_dataset
from evals.long_task_scorers import score_long_task
from evals.optimization.budget import OptimizationBudget


DATASET = Path(__file__).resolve().parents[2] / "evals/datasets/harness_long_tasks_v1.jsonl"


def test_frozen_long_task_dataset_loads_in_fixed_order():
    cases = load_long_task_cases(DATASET)
    assert [case.case_id for case in cases] == [f"L0{i}" for i in range(1, 7)]
    assert len({case.learner_id for case in cases}) == 6
    assert all(case.expected_model_requests_max == 20 for case in cases)


def test_long_task_validation_is_offline_and_versioned():
    report = validate_long_dataset(DATASET)
    assert report["schema"] == "eduagent.harness-long-task-validation.v1"
    assert report["provider_requests"] == 0
    assert report["valid"] == report["total"] == 6
    assert len(report["dataset_revision"]) == 64


@pytest.mark.asyncio
async def test_l05_scripted_end_to_end_closes_guided_plan(monkeypatch):
    case = load_long_task_cases(DATASET)[4]
    service = LLMService(
        provider="deepseek", api_key="test-only", model="deepseek-flash"
    )

    async def generate(prompt, **kwargs):
        active_run.get().consume("model")
        data = json.loads(prompt)
        assert "request" in data
        return LLMResponse(content=json.dumps({
            "goal": data["request"],
            "steps": [
                {"step_id": "c", "agent": "Curriculum", "objective": "准备基础词汇练习"},
                {"step_id": "t", "agent": "Tutor", "objective": "说明练习要求",
                 "depends_on": ["c"]},
            ],
        }), model="mock", usage={"prompt_tokens": 200, "completion_tokens": 80})

    async def turn(messages, tools, max_tokens):
        active_run.get().consume("model")
        if "Curriculum专家" in messages[0]["content"]:
            content = json.dumps({
                "task_id": "c", "status": "completed", "findings": ["练习被动语态"],
                "source_refs": [],
                "proposed_actions": [{"knowledge_id": "vocab_basic", "difficulty": .5}],
            })
        else:
            content = "先完成刚准备的练习，再根据反馈收尾。"
        return NativeTurn(
            content=content, stop_reason="stop",
            usage={"input_tokens": 300, "output_tokens": 60},
        )

    service.generate = generate
    service.tool_turn = turn
    monkeypatch.setattr(llm_service, "_llm_service", service)
    executor = LongTaskExecutor(
        case, service, OptimizationBudget(max_requests=20, max_cny=1.5)
    )
    try:
        observed = await executor.execute()
        score = score_long_task(case, observed)
    finally:
        executor.close()
    assert score["status"] == "passed", json.dumps(
        {"assertions": score["assertions"], "stages": observed["stages"]},
        ensure_ascii=False, default=str,
    )
    assert score["plan_completed"]
    assert score["metrics"]["model_calls"] == 3
    assert score["metrics"]["tool_calls"] >= 3
