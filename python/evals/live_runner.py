"""真实模型评测入口和可中断的公开结果报告。"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import time

from config.settings import PROJECT_ROOT, settings
from core.llm_service import get_llm_service
from core.versions import public_runtime_config, runtime_metadata
from evals.io import write_json
from evals.live_budget import LiveBudget
from evals.live_cases import load_live_cases
from evals.live_executor import LiveExecutor
from evals.live_scorers import calls, score_live_case
from evals.runner import dataset_revision


def code_revision():
    digest = hashlib.sha256()
    for path in sorted((PROJECT_ROOT / "python").rglob("*.py")):
        if any(part in {".venv", "venv", "__pycache__", "build", "dist"} for part in path.parts):
            continue
        digest.update(str(path.relative_to(PROJECT_ROOT)).encode())
        digest.update(path.read_bytes())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                          capture_output=True, text=True, check=False).stdout.strip()
    return {"git_head": head, "python_source_sha256": digest.hexdigest(),
            "includes_working_tree": True}


def aggregate(results):
    groups = {}
    for role in ("agent_primary", "teaching_auxiliary"):
        subset = [r for r in results if r["evaluation_role"] == role]
        valid = [r for r in subset if r["status"] != "fixture_invalid"]
        groups[role] = {
            "total": len(subset), "valid_fixtures": len(valid),
            "automatic_passed": sum(r["automatic_passed"] for r in valid),
            "automatic_case_pass_rate": (
                sum(r["automatic_passed"] for r in valid) / len(valid) if valid else None
            ),
            "fully_passed": sum(r["status"] == "passed" for r in valid),
            "review_pending": sum(r["status"] == "review_pending" for r in valid),
            "failed": sum(r["status"] == "failed" for r in valid),
        }
    return groups


def write_live_markdown(path: Path, report: dict):
    lines = [
        "# Tutor 真实模型首批评测结果", "",
        f"生成时间：{report['generated_at']}。模型：`{report['model']}`，思考关闭。",
        "",
        "固定脚本模拟学生；本批测量 Agent 行为、状态契约和回复质量，不能证明真实学生学习效果。",
        "自动硬检查与语义审阅分开。`review_pending` 表示尚未完成语义审阅，不等同于整体通过。",
        "",
        "| 方向 | 有效场景 | 自动检查全部通过 | 语义待审阅 | 自动检查失败 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for key, name in (("agent_primary", "Agent 行为（主评测）"),
                      ("teaching_auxiliary", "教学回复（辅助）")):
        g = report["groups"][key]
        lines.append(f"| {name} | {g['valid_fixtures']} | {g['automatic_passed']} "
                     f"| {g['review_pending']} | {g['failed']} |")
    budget = report["budget"]
    lines.extend([
        "", f"模型请求：{budget['requests']}/{budget['max_requests']}；"
        f"输入 Token：{budget['usage'].get('input_tokens', 0)}；"
        f"输出 Token：{budget['usage'].get('output_tokens', 0)}。",
        f"估算费用：{budget['estimated_off_peak_cny']:.6f}–{budget['estimated_peak_cny']:.6f} 元"
        "（闲时至高峰定价区间，实际扣费以供应商账单为准）。"
        f"未确认请求预留：{budget['unconfirmed_reservation_cny']:.6f} 元。",
        "", "| 场景 | 结果 | 自动失败项 | 工具路径 |",
        "| --- | --- | --- | --- |",
    ])
    for result in report["results"]:
        failed = ",".join(c["id"] for c in result["hard_checks"] if c["passed"] is False) or "无"
        paths = [" → ".join(call["name"] for call in calls(step)) or "直接回复"
                 for step in result["observed"]["steps"].values() if step.get("action") == "converse"]
        lines.append(f"| {result['case_id']} | {result['status']} | {failed} | {' / '.join(paths)} |")
    for result in report["results"]:
        lines.extend(["", f"## {result['case_id']} · {result['title']}", ""])
        for sid, step in result["observed"]["steps"].items():
            if step.get("student_input"):
                lines.extend([f"**{sid} 学生输入**：{step['student_input']}", ""])
            response = step.get("result", {}).get("teaching_response", {}).get("response")
            if response:
                lines.extend([f"**{sid} 实际回复**：", "", response, ""])
            if step.get("status") != "completed":
                lines.append(f"步骤状态：`{step.get('status')}`；原因：`{step.get('stop_reason', '')}`。")
        lines.extend([
            "", "硬检查：",
            *[f"- {c['id']} `{c['status']}`：{c['rule']}" for c in result["hard_checks"]],
            "", "质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_live_suite(*, path: Path, output: Path | None = None,
                         max_requests: int = 42, max_cny: float = 3.0,
                         service=None, progress=None):
    cases = load_live_cases(path)
    service = service or get_llm_service()
    if (service.provider != "deepseek" or service.model != "deepseek-flash"
            or service.thinking != "disabled" or not service._has_remote_llm()):
        raise ValueError("live suite requires configured DeepSeek Flash with thinking disabled")
    budget = LiveBudget(max_requests=max_requests, max_cny=max_cny)
    fields = {
        "enable_tutor_tools": True, "enable_agent_llm_decisions": False,
        "enable_db_logging": False, "tutor_max_model_calls": 3, "tutor_max_tool_calls": 4,
        "tutor_context_budget_tokens": 6000, "tutor_max_output_tokens": 800,
    }
    previous = {key: getattr(settings, key) for key in fields}
    for key, value in fields.items():
        setattr(settings, key, value)
    results = []
    started = time.perf_counter()
    try:
        report = {
            "schema": "eduagent.tutor-live-result.v1",
            "generation_mode": "live_native_tools",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **runtime_metadata(settings),
            "code_revision": code_revision(), "dataset_revision": dataset_revision(path),
            "config": public_runtime_config(settings),
            "dataset_review_status": "user_authorized_in_conversation",
            "limitations": [
                "scripted fictional learners; not a learning-effect study",
                "semantic and quality judgments require separately attributed review",
                "single run per case; no repeatability or ablation estimate",
                "cost estimates are not provider billing records",
            ],
            "results": results,
        }
        for case in cases:
            case_started = time.perf_counter()
            ledger_start = len(budget.ledger)
            executor = LiveExecutor(case, service, budget)
            try:
                observed = await executor.execute()
            finally:
                executor.close()
            result = score_live_case(case, observed)
            result.update(observed=observed, duration_ms=(time.perf_counter() - case_started) * 1000,
                          metering=budget.ledger[ledger_start:])
            results.append(result)
            report.update(groups=aggregate(results), budget=budget.summary(),
                          total=len(results), duration_ms=(time.perf_counter() - started) * 1000)
            if output:
                write_json(output, report)
                write_live_markdown(output.with_suffix(".md"), report)
            if progress:
                progress(result, budget.summary())
        return report
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)
