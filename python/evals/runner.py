"""评测样例执行、评分和聚合报告。"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from pathlib import Path

from config.settings import settings
from core.learning_history import public_data
from core.versions import config_fingerprint
from evals.executors import BuiltinExecutor
from evals.io import builtin_dataset_path, load_cases
from evals.models import EvalReport, EvalResult
from evals.scorers import score_case


def dataset_revision(path: str | Path | None) -> str:
    source = Path(path) if path else builtin_dataset_path()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def run_suite(
    *,
    path: str | Path | None = None,
    suite: str = "builtin",
) -> EvalReport:
    cases = load_cases(path, suite=suite)
    executor = BuiltinExecutor()
    results: list[EvalResult] = []
    try:
        for case in cases:
            started = time.perf_counter()
            try:
                observed = await executor.execute(case)
                details = score_case(case, observed)
            except Exception as exc:
                observed = {"error": type(exc).__name__}
                details = score_case(case, observed)
                for detail in details:
                    detail.passed = False
                    detail.message = (
                        f"case execution failed: {type(exc).__name__}; "
                        + detail.message
                    ).strip()
            passed = bool(details) and all(detail.passed for detail in details)
            score = sum(detail.passed for detail in details) / len(details)
            results.append(EvalResult(
                case_id=case.case_id,
                suite=case.suite,
                kind=case.kind,
                tags=case.tags,
                passed=passed,
                score=score,
                details=details,
                observed=public_data(observed),
                duration_ms=(time.perf_counter() - started) * 1000,
            ))
    finally:
        executor.close()

    tag_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0}
    )
    for result in results:
        for tag in result.tags:
            tag_counts[tag]["total"] += 1
            tag_counts[tag]["passed" if result.passed else "failed"] += 1
    tag_metrics = {
        tag: {
            **counts,
            "pass_rate": counts["passed"] / counts["total"],
        }
        for tag, counts in sorted(tag_counts.items())
    }
    passed_count = sum(result.passed for result in results)
    return EvalReport(
        suite=suite,
        dataset_revision=dataset_revision(path),
        provider=settings.configured_llm_provider,
        model=settings.configured_llm_model,
        generation_mode="offline_builtin",
        config_fingerprint=config_fingerprint(settings),
        total=len(results),
        passed=passed_count,
        failed=len(results) - passed_count,
        pass_rate=passed_count / len(results),
        tag_metrics=tag_metrics,
        results=results,
    )
