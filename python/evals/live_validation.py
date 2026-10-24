"""用已知脚本验证预置、工具和状态链路；不测量任何模型能力。"""

import json
from pathlib import Path

from config.settings import settings
from core import llm_service
from core.llm_service import LLMService, NativeToolCall, NativeTurn
from evals.live_budget import LiveBudget
from evals.live_cases import LiveCase, load_live_cases
from evals.live_executor import LiveExecutor
from evals.live_runner import code_revision
from evals.live_scorers import score_live_case
from evals.runner import dataset_revision


def fixture_service(case: LiveCase) -> tuple[LLMService, list]:
    """工具动作依据预先编写的契约，不是模型推理；答案仅用于检验断言。"""
    service = LLMService(provider="template")
    seen = []

    async def forbid_generate(*args, **kwargs):
        raise RuntimeError("offline validation forbids extra generation")

    async def turn(messages, tools, max_tokens):
        seen.append(json.loads(json.dumps(messages)))
        count, tool = len(seen), None
        content = "离线脚本占位提示；语义没有评估。请检查题干中的结构或上下文线索。"
        if case.number in (5, 6) and count == 1:
            tool = ("ask_student", {"question": "请提供原句。" if case.number == 5 else "这次阅读要找什么？"})
        elif case.number == 8:
            query, quote = case.retrieval_expectations
            if count == 1:
                tool = ("search_learning_history", {"query": query, "limit": 10})
            elif count == 2:
                tool = ("read_learning_history", {"source_ref": case.target_source_ref})
            else:
                content = quote
        elif case.number == 10 and count == 1:
            tool = ("read_learning_history", {"source_ref": case.foreign_expectations[0]})
        elif case.number == 1 and count == 1:
            private = case.initial_facts.get("evaluator_only", {})
            if isinstance(private, dict) and private.get("requires_history_search"):
                query = "ABSENT41" if "ABSENT41" in case.steps[0].student_input else case.knowledge_id
                tool = ("search_learning_history", {"query": query, "limit": 10})
            elif isinstance(private, dict) and private.get("requires_knowledge_tool"):
                tool = ("get_knowledge_context", {})
        return NativeTurn(
            content="" if tool else content,
            tool_calls=[NativeToolCall(
                id=f"script-{count}", name=tool[0], arguments=json.dumps(tool[1])
            )] if tool else [],
            stop_reason="tool_calls" if tool else "stop", usage={},
        )

    # 模拟原生工具能力以进入真实工具执行分支；模板 provider 不创建远程客户端。
    service._has_remote_llm = lambda: True
    service.tool_turn, service.generate = turn, forbid_generate
    return service, seen


async def validate_live_dataset(path: Path) -> dict:
    cases = load_live_cases(path)
    fields = {
        "enable_tutor_tools": True, "enable_agent_llm_decisions": False,
        "enable_db_logging": False, "tutor_max_model_calls": 3, "tutor_max_tool_calls": 4,
        "tutor_context_budget_tokens": 6000, "tutor_max_output_tokens": 800,
    }
    previous = {key: getattr(settings, key) for key in fields}
    previous_service = llm_service._llm_service
    rows = []
    try:
        for key, value in fields.items():
            setattr(settings, key, value)
        for case in cases:
            service, seen = fixture_service(case)
            llm_service._llm_service = service
            executor = LiveExecutor(case, service, LiveBudget(max_requests=6))
            try:
                observed = await executor.execute()
                score = score_live_case(case, observed)
            finally:
                executor.close()
            rows.append({
                "case_id": case.case_id, "evaluation_role": case.role,
                "fixture_valid": observed["fixture_validation"]["valid"],
                "fixture_checks": observed["fixture_validation"]["checks"],
                "script_completed": score["execution_outcome"] == "completed",
                "automatic_contracts_valid": score["automatic_passed"],
                "scripted_turns": len(seen),
                "failed_checks": [c["id"] for c in score["hard_checks"] if c["passed"] is False],
                "semantic_review": "not_evaluated", "model_task_success": None,
                "model_tool_semantic_score": None,
            })
    finally:
        llm_service._llm_service = previous_service
        for key, value in previous.items():
            setattr(settings, key, value)
    return {
        "schema": "eduagent.live-dataset-validation.v1",
        "generation_mode": "evaluator_informed_scripted_validation",
        "provider_requests": 0, "dataset_revision": dataset_revision(path),
        "code_revision": code_revision(),
        "total": len(rows), "valid": sum(row["automatic_contracts_valid"] for row in rows),
        "limitations": [
            "Script actions and retrieval quotes are supplied by the evaluator.",
            "This validates fixtures and execution contracts, not model performance or reply semantics.",
        ],
        "results": rows,
    }
