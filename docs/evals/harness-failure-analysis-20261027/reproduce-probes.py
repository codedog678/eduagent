"""针对已归档失败的离线事实核对；不调用模型，不修改运行时。"""

import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from fastapi import HTTPException
from config.settings import settings
from core.coordination_models import AgentResult, LearningPlan, PlanStep
from core.coordinator import Coordinator
from core.llm_service import get_llm_service
from evals.live_runner import code_revision
from evals.long_task_executor import LongTaskExecutor
from evals.long_task_models import load_long_task_cases
from evals.optimization.budget import OptimizationBudget

ARCHIVE = ROOT / "docs/evals/harness-long-runs/20261027-deepseek-flash"
OUT = ROOT / "docs/evals/harness-failure-analysis-20261027"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main():
    report = json.loads((ARCHIVE / "result.json").read_text())
    cases = load_long_task_cases(ARCHIVE / "dataset.jsonl")
    service = get_llm_service()
    assert service.provider == "template"
    settings.memory_retrieval_mode = "lexical"
    settings.memory_embedding_api_key = ""
    settings.siliconflow_api_key = ""
    settings.memory_worker_enabled = False
    settings.memory_rerank_enabled = False
    budget = OptimizationBudget(max_requests=120, max_cny=1.5)
    executions = []
    evidence = {
        "schema": "eduagent.harness-failure-analysis-evidence.v1",
        "analysis_date": "2026-10-27",
        "runtime_git_head": report["code_revision"]["git_head"],
        "python_source_sha256": code_revision()["python_source_sha256"],
        "source_result_sha256": sha(ARCHIVE / "result.json"),
        "data_role": "recorded_engineering_regression_fixtures",
        "method": "offline source inspection and isolated replay of recorded fixtures; no model responses synthesized",
        "provider_requests": 0,
        "original_result_modified": False,
        "is_new_live_evaluation": False,
    }
    assert evidence["python_source_sha256"] == report["code_revision"]["python_source_sha256"]
    try:
        l01 = LongTaskExecutor(cases[0], service, budget)
        executions.append(l01)
        queries = ["时态 错误 tense", "grammar_tenses", "", "since", "by the time", "过去时 将来时"]
        searches = []
        for query in queries:
            result = await l01.harness.history.retrieval.search(
                cases[0].learner_id, cases[0].knowledge_id, query, limit=10)
            searches.append({
                "query": query,
                "query_role": "recorded" if query in queries[:3] else "offline diagnostic alternative",
                "hit_refs": sorted(row["source_ref"] for row in result["items"]),
            })
        assert all(not row["hit_refs"] for row in searches[:3])
        assert searches[3]["hit_refs"] == ["message:l01-error-1"]
        assert searches[4]["hit_refs"] == ["message:l01-error-2"]
        assert searches[5]["hit_refs"] == ["message:l01-error-1", "message:l01-error-2"]
        evidence["L01_lexical_replay"] = {
            "index_chunks": l01.harness.db.execute("SELECT count(*) FROM memory_chunks").fetchone()[0],
            "queries": searches,
            "scope": "same learner and knowledge; new isolated database seeded from frozen fixtures",
            "conclusion": "recorded queries miss existing indexed texts; knowledge_id is a filter, not an indexed content term",
        }
        ctx = l01._scope(cases[0].initial_facts.history[0])
        coordinator = Coordinator(ctx, service)
        conflicts = []
        for text in ["采用已保存偏好，不能声称偏好缺失。", "学生没有学习偏好"]:
            plan = LearningPlan(
                goal="复习",
                constraints=[text],
                steps=[PlanStep(step_id="t", agent="Tutor", objective="表达复习安排")],
            )
            try:
                coordinator.bind_evidence(plan)
            except ValueError as exc:
                conflicts.append({"text": text, "result": str(exc)})
            else:
                conflicts.append({"text": text, "result": "accepted"})
        assert all(row["result"] == "planner_evidence_conflict" for row in conflicts)
        evidence["planning_regex_diagnostic"] = {
            "scope": "diagnostic sentences, not original missing model plan JSON",
            "cases": conflicts,
            "conclusion": "known preference negation instruction also matches missing-evidence regex",
            "causal_limit": "shows an implementation false-positive path; does not establish it caused L01 or L04",
        }
        # 恢复包装器，避免多个执行器共享同一服务对象时累积包装。
        l01.close()
        executions.remove(l01)
        l04 = LongTaskExecutor(cases[3], service, budget)
        executions.append(l04)
        recorded = report["live"]["results"][3]
        action = recorded["observed"]["final"]["plans"][0]["action_receipts"]["step-1"]["requested_action"]
        initial = l04._snapshot()["knowledge"]
        assert initial == recorded["observed"]["initial"]["knowledge"]
        graph = l04.orchestrator.curriculum.knowledge_graph
        prereqs = graph.nodes[action["knowledge_id"]].prerequisites
        mastered = {key for key, state in initial.items() if state["mastery"] >= .6}
        try:
            await l04.harness.prepare_question(
                cases[3].learner_id, action["knowledge_id"], action["difficulty"],
                "practice", require_prerequisites=True)
        except HTTPException as exc:
            replay = {"status_code": exc.status_code, "detail": exc.detail}
        else:
            raise AssertionError("recorded state must reject before question generation")
        assert replay == {"status_code": 409, "detail": "前置知识尚未满足，请先练习基础知识点"}
        evidence["L04_action_replay"] = {
            "recorded_action": action,
            "recorded_receipt_status": "denied",
            "recorded_error_code": "unavailable_or_not_allowed",
            "initial_knowledge": initial,
            "required_prerequisites": prereqs,
            "mastered_prerequisites": sorted(set(prereqs) & mastered),
            "replay": replay,
            "conclusion": "recorded action fails the prerequisite gate in the recorded initial state",
            "limit": "original HTTP detail was not archived; replay localizes the gate without replacing original trace",
        }
        failures, skips, allocations = [], [], []
        for row in report["live"]["results"]:
            for stage_id, stage in row["observed"]["stages"].items():
                steps = [step for attempt in (stage.get("trace") or {}).get("attempts", [])
                         for step in attempt["steps"]]
                for index, step in enumerate(steps):
                    if step.get("kind") == "agent_completed" and step.get("error_code") == "expert_result_invalid":
                        final_model = [item for item in steps[:index] if item.get("kind") == "after_model"][-1]
                        failures.append({
                            "case_id": row["case_id"], "stage_id": stage_id,
                            "task_id": step["task_id"], "role": step["agent"],
                            "error_code": step["error_code"], "cause_type": step["cause_type"],
                            "final_model_stop_reason": final_model["stop_reason"],
                            "trace_seq": step["seq"],
                        })
                    if step.get("kind") == "tool_skipped":
                        skips.append({"case_id": row["case_id"], "stage_id": stage_id, **step})
                    if step.get("kind") == "agent_budget_allocated":
                        allocations.append({"case_id": row["case_id"], "stage_id": stage_id, **step})
        assert len(failures) == 5 and all(row["final_model_stop_reason"] == "stop" for row in failures)
        evidence["expert_failures"] = failures
        evidence["expert_failure_role_counts"] = dict(Counter(row["role"] for row in failures))
        evidence["tool_skips"] = skips
        evidence["budget_allocations"] = allocations
        # schema 自身接受 completed+空 findings；运行时还要额外拒绝。
        empty = AgentResult.model_validate({"task_id": "diagnostic-only", "status": "completed"})
        evidence["expert_schema_gap"] = {
            "schema_accepts_completed_without_findings": empty.findings == [],
            "runtime_rejects_as": "incomplete_expert_result",
            "scope": "schema diagnostic, not an assertion about the unarchived five model payloads",
        }
        assert not budget.requests
        assert sha(ARCHIVE / "result.json") == evidence["source_result_sha256"]
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print(json.dumps({
            "provider_requests": 0,
            "original_expert_invalid_failures": len(failures),
            "tool_skips": len(skips),
            "l01_original_queries_miss": True,
            "l04_reproduced_status": replay["status_code"],
            "planning_regex_false_positive_reproduced": True,
            "evidence": str(OUT / "evidence.json"),
        }, ensure_ascii=False))
    finally:
        for executor in reversed(executions):
            executor.close()


asyncio.run(main())
