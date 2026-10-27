"""双层长任务评测入口、增量报告和可读摘要。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from config.settings import PROJECT_ROOT, settings
from core.llm_service import get_llm_service
from core.versions import public_runtime_config, runtime_metadata
from evals.io import write_json
from evals.live_runner import code_revision
from evals.long_task_executor import LongTaskExecutor
from evals.long_task_models import load_long_task_cases, public_case
from evals.long_task_scorers import SCORER_VERSION, score_long_task
from evals.optimization.budget import OptimizationBudget, OptimizationStopped
from evals.runner import dataset_revision


CONTRACT_TESTS = {
    "D01": "test_d01_atomic_three_agent_chain",
    "D02": "test_d02_bounded_replan",
    "D03": "test_d03_read_retry_write_no_retry",
    "D04": "test_d04_commit_failure_zero_residue",
    "D05": "test_d05_idempotent_replay_and_conflict",
    "D06": "test_d06_restart_marks_interruption_and_resumes_plan",
    "D07": "test_d07_stale_source_invalidates_dependents",
    "D08": "test_d08_cross_knowledge_practice_completes_plan",
}


def validate_long_dataset(path: Path) -> dict:
    cases = load_long_task_cases(path)
    return {
        "schema": "eduagent.harness-long-task-validation.v1",
        "provider_requests": 0,
        "dataset_revision": dataset_revision(path),
        "total": len(cases),
        "valid": len(cases),
        "cases": [public_case(case) for case in cases],
    }


def run_contract_suite() -> dict:
    rows = []
    test_file = PROJECT_ROOT / "python/tests/evals/test_long_task_contracts.py"
    for contract, name in CONTRACT_TESTS.items():
        started = time.perf_counter()
        process = subprocess.run(
            [sys.executable, "-m", "pytest", f"{test_file}::{name}", "-q"],
            cwd=PROJECT_ROOT / "python", capture_output=True, text=True, check=False,
            env={**__import__("os").environ, "LLM_PROVIDER": "template"},
        )
        output = (process.stdout + "\n" + process.stderr).strip()
        rows.append({
            "case_id": contract,
            "status": "passed" if process.returncode == 0 else "contract_failed",
            "returncode": process.returncode,
            "duration_ms": (time.perf_counter() - started) * 1000,
            "output_tail": output[-2000:],
        })
    return {
        "total": len(rows), "passed": sum(row["status"] == "passed" for row in rows),
        "results": rows,
    }


def aggregate_live(results):
    plans = [
        result for result in results
        if result["case_id"] != "L01"
        and result.get("observed", {}).get("final", {}).get("plans")
    ]
    recoveries = [result for result in results if result["case_id"] in {"L02", "L04"}]
    model_calls = sum(row["metrics"]["model_calls"] for row in results)
    tool_calls = sum(row["metrics"]["tool_calls"] for row in results)
    redundant = sum(row["metrics"]["redundant_tool_calls"] for row in results)
    permission_violations = sum(
        assertion["id"] in {"injection_not_executed", "mastery_unchanged"}
        and not assertion["passed"]
        for result in results for assertion in result["assertions"]
    )
    task_successes = sum(row["task_success"] for row in results)
    critical = {
        row["case_id"]: row["task_success"] for row in results
        if row["case_id"] in {"L02", "L05"}
    }
    metrics = {
        "total": len(results),
        "task_successes": task_successes,
        "task_success_rate": task_successes / len(results) if results else None,
        "plan_completion_rate": (
            sum(row["plan_completed"] for row in plans) / len(plans) if plans else None
        ),
        "recovery_success_rate": (
            sum(row["task_success"] for row in recoveries) / len(recoveries) if recoveries else None
        ),
        "model_calls": model_calls, "tool_calls": tool_calls,
        "redundant_tool_rate": redundant / tool_calls if tool_calls else 0,
        "permission_violations": permission_violations,
    }
    metrics["meets_project_gate"] = (
        len(results) == 6 and task_successes >= 5
        and critical == {"L02": True, "L05": True}
        and (metrics["plan_completion_rate"] or 0) >= .8
        and metrics["recovery_success_rate"] == 1
        and permission_violations == 0
    )
    return metrics


def write_markdown(path: Path, report: dict):
    contract = report["deterministic"]
    live = report.get("live") or {}
    metrics = live.get("metrics", {})
    lines = [
        "# Harness 长任务双层评测结果", "",
        f"生成时间：{report['generated_at']}。",
        "",
        f"确定性合同：{contract['passed']}/{contract['total']} 通过。",
    ]
    if live:
        budget = report["budget"]
        lines.extend([
            f"真实模型任务：{metrics['task_successes']}/{metrics['total']} 成功；"
            f"模型请求 {budget['requests']}/{budget['max_requests']}。",
            f"估算费用：{budget['estimated_off_peak_cny']:.6f}–"
            f"{budget['estimated_peak_cny']:.6f} 元。",
            "",
            "| 场景 | 状态 | 模型调用 | 工具调用 | 冗余调用 |",
            "| --- | --- | ---: | ---: | ---: |",
        ])
        for row in live["results"]:
            item = row["metrics"]
            lines.append(
                f"| {row['case_id']} | {row['status']} | {item['model_calls']} | "
                f"{item['tool_calls']} | {item['redundant_tool_calls']} |"
            )
            lines.extend(["", f"## {row['case_id']} · {row['title']}", ""])
            for assertion in row["assertions"]:
                lines.append(
                    f"- {'通过' if assertion['passed'] else '失败'} `{assertion['id']}`："
                    f"{assertion['rule']}"
                )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_long_suite(*, path: Path, output: Path, max_requests=120, max_cny=1.5,
                         service=None, progress=None):
    deterministic = run_contract_suite()
    report = {
        "schema": "eduagent.harness-long-task-result.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_revision": code_revision(),
        "scorer_version": SCORER_VERSION,
        "dataset_revision": dataset_revision(path),
        "deterministic": deterministic,
        "live": None,
        "limitations": [
            "scripted fictional learners; not a learning-effect study",
            "single real-model run per case; failures are retained rather than rerun",
            "cost estimates are not provider billing records",
        ],
    }
    write_json(output, report)
    write_markdown(output.with_suffix(".md"), report)
    if deterministic["passed"] != deterministic["total"]:
        report["stop_reason"] = "deterministic_contract_gate_failed"
        write_json(output, report)
        write_markdown(output.with_suffix(".md"), report)
        return report

    cases = load_long_task_cases(path)
    service = service or get_llm_service()
    if (service.provider != "deepseek" or service.model != "deepseek-flash"
            or service.thinking != "disabled" or not service._has_remote_llm()):
        raise ValueError("long-task live suite requires DeepSeek Flash with thinking disabled")
    budget = OptimizationBudget(max_requests=max_requests, max_cny=max_cny)
    fields = {
        "enable_tutor_tools": True, "enable_agent_llm_decisions": False,
        "enable_db_logging": False, "memory_retrieval_mode": "lexical",
        "memory_rerank_enabled": False, "memory_embedding_api_key": "",
        "siliconflow_api_key": "", "memory_worker_enabled": False,
    }
    previous = {key: getattr(settings, key) for key in fields}
    results = []
    try:
        for key, value in fields.items():
            setattr(settings, key, value)
        report.update(
            **runtime_metadata(settings),
            config=public_runtime_config(settings),
            frozen_cases=[public_case(case) for case in cases],
        )
        for case in cases:
            executor = LongTaskExecutor(case, service, budget)
            try:
                try:
                    observed = await executor.execute()
                    result = score_long_task(case, observed)
                except OptimizationStopped as exc:
                    report["stop_reason"] = str(exc)
                    report["live"] = {"metrics": aggregate_live(results), "results": results}
                    report["budget"] = budget.summary()
                    write_json(output, report)
                    write_markdown(output.with_suffix(".md"), report)
                    return report
            finally:
                executor.close()
            results.append(result)
            report["live"] = {"metrics": aggregate_live(results), "results": results}
            report["budget"] = budget.summary()
            write_json(output, report)
            write_markdown(output.with_suffix(".md"), report)
            if progress:
                progress(result, report["budget"])
        return report
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
