"""python -m evals.optimization.cli：prepare / optimize / compare。"""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import tempfile

from config.settings import settings
from core.llm_service import get_llm_service
from core.versions import public_runtime_config
from evals.io import write_json
from evals.live_cases import load_live_cases
from evals.live_runner import code_revision
from evals.optimization.adapter import TutorGEPAAdapter
from evals.optimization.budget import OptimizationBudget, OptimizationStopped
from evals.optimization.protocol import (
    GEPA_VERSION, SCHEMA, assert_holdout_disjoint, digest, file_digest,
    load_policy, load_protocol, policy_artifact, prepare_protocol, seed_candidate,
)
from evals.optimization.scoring import summarize


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets/tutor_agent50_review.jsonl"


def run_search(adapter, protocol, cases, *, max_metric_calls=160, minibatch=3, run_dir=None):
    import gepa
    if version("gepa") != GEPA_VERSION:
        raise ValueError(f"install the verified dependency gepa=={GEPA_VERSION}")
    train = [cases[cid] for cid in protocol["train_ids"]]
    val = [cases[cid] for cid in protocol["dev_validation_ids"]]
    if minibatch < 1 or minibatch > len(train) or max_metric_calls <= len(val):
        raise ValueError("invalid minibatch or metric budget too small to go beyond seed validation")
    # 采用真实 GEPA 搜索/候选选择；Adapter 自定义反思请求用于统一计费。
    iteration_requests = 2 * minibatch * 7 + sum(c.expected_model_requests_max + 1 for c in val) + 1
    return gepa.optimize(
        seed_candidate=seed_candidate(), trainset=train, valset=val, adapter=adapter,
        reflection_minibatch_size=minibatch, max_metric_calls=max_metric_calls,
        candidate_selection_strategy="pareto", module_selector="round_robin",
        skip_perfect_score=False, use_merge=False, cache_evaluation=False,
        seed=protocol["seed"], raise_on_exception=True, run_dir=run_dir,
        stop_callbacks=lambda state: (
            adapter.budget.requests + iteration_requests > adapter.budget.max_requests
            or adapter.budget.exhausted
        ),
    )


def acceptance(baseline_rows, candidate_rows):
    if ([(r["repeat"], r["case_id"]) for r in baseline_rows]
            != [(r["repeat"], r["case_id"]) for r in candidate_rows]):
        raise ValueError("paired comparison coverage mismatch")
    baseline, candidate = summarize(baseline_rows), summarize(candidate_rows)
    regressions = [
        {"repeat": b["repeat"], "case_id": b["case_id"]}
        for b, c in zip(baseline_rows, candidate_rows)
        if b["score"]["automatic_passed"] and not c["score"]["automatic_passed"]
    ]
    group_regressions = [
        name for name, score in baseline["by_capability"].items()
        if candidate["by_capability"][name]["task_success_rate"] < score["task_success_rate"]
    ]
    improved = (
        candidate["task_success_rate"] > baseline["task_success_rate"]
        or candidate["task_success_rate"] == baseline["task_success_rate"]
        and candidate["mean_score"] > baseline["mean_score"]
    )
    passed = improved and not regressions and not group_regressions
    return {
        "passed": passed, "baseline": baseline, "candidate": candidate,
        "automatic_regressions": regressions, "capability_regressions": group_regressions,
        "policy": "strict improvement, zero paired automatic regressions, no capability TSR decrease",
        "interpretation": "AI-judged engineering gate, not statistical significance or learning gains",
    }


def configured_service():
    service = get_llm_service()
    if (service.provider != "deepseek" or service.model != "deepseek-flash"
            or service.thinking != "disabled" or not service._has_remote_llm()):
        raise ValueError("requires configured DeepSeek Flash with thinking disabled")
    return service


def run_remote(args):
    protocol, cases = load_protocol(args.protocol, args.dataset)
    candidate = None
    evaluation_cases = [cases[cid] for cid in protocol["dev_validation_ids"]]
    origin = None
    if args.command == "compare":
        if args.repeats < 1:
            raise ValueError("repeats must be positive")
        candidate = load_policy(args.candidate)
        origin = json.loads((args.origin_run / "run.json").read_text())
        if (origin["status"] != "completed"
                or origin["protocol_sha256"] != digest(protocol)
                or origin["best_policy_sha256"] != digest(candidate)):
            raise ValueError("candidate must match a completed optimization and its frozen protocol")
        if args.holdout:
            evaluation_cases = load_live_cases(args.holdout)
            assert_holdout_disjoint(list(cases.values()), evaluation_cases)
    service = configured_service()
    budget = OptimizationBudget(max_requests=args.max_requests, max_cny=args.max_cny)
    if args.command == "compare":
        budget.require_requests(
            2 * args.repeats * sum(c.expected_model_requests_max + 1 for c in evaluation_cases)
        )
    args.output.mkdir(parents=True, exist_ok=False)
    record = {
        "schema": SCHEMA, "status": "running", "command": args.command,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(protocol), "code_revision": code_revision(),
        "provider": service.provider, "model": service.model, "thinking": service.thinking,
        "gepa_version": GEPA_VERSION,
        "limits": {"max_requests": args.max_requests, "max_cny": args.max_cny},
        "evaluation_role": "development_validation",
    }
    write_json(args.output / "protocol.json", protocol)
    write_json(args.output / "baseline-policy.json", policy_artifact(seed_candidate()))
    try:
        all_cases = list(cases.values()) + (
            evaluation_cases if args.command == "compare" and args.holdout else []
        )
        with TutorGEPAAdapter(all_cases, protocol["train_ids"], budget, args.output,
                              service=service) as adapter:
            record["runtime"] = public_runtime_config(settings)
            if origin:
                for field in ("runtime", "provider", "model", "thinking"):
                    if origin[field] != record[field]:
                        raise ValueError(f"comparison runtime changed: {field}")
                if (origin["code_revision"]["python_source_sha256"]
                        != record["code_revision"]["python_source_sha256"]):
                    raise ValueError("source changed since optimization; start a new experiment")
            write_json(args.output / "run.json", record)
            if args.command == "optimize":
                record["search"] = {"max_metric_calls": args.max_metric_calls,
                                    "minibatch": args.minibatch, "seed": protocol["seed"]}
                write_json(args.output / "run.json", record)
                # GEPA 状态/缓存是中间产物，退出后清理；公开轨迹与策略单独持久化。
                with tempfile.TemporaryDirectory(prefix="eduagent-gepa-") as cache:
                    result = run_search(adapter, protocol, cases,
                                        max_metric_calls=args.max_metric_calls,
                                        minibatch=args.minibatch, run_dir=cache)
                best = result.best_candidate
                write_json(args.output / "best-policy.json", policy_artifact(best))
                record.update(
                    best_policy_sha256=digest(best),
                    best_validation_score=result.val_aggregate_scores[result.best_idx],
                    baseline_validation_score=result.val_aggregate_scores[0],
                    candidate_count=len(result.candidates),
                    validation_scores=result.val_aggregate_scores,
                    selection="development_candidate_only",
                    metric_calls=result.total_metric_calls,
                )
            else:
                if args.holdout:
                    holdout_hash = file_digest(args.holdout)
                    # 对同一优化结果的一次留出集验收包含事先指定的全部重复。
                    # 开始请求前封存；失败也不允许悄悄重跑并挑选结果。
                    with (args.origin_run / "holdout-used.json").open("x") as handle:
                        json.dump({"dataset_sha256": holdout_hash,
                                   "repeats": args.repeats,
                                   "candidate_sha256": digest(candidate)}, handle)
                    record.update(evaluation_role="holdout",
                                  holdout_sha256=holdout_hash)
                record.update(repeats=args.repeats, candidate_sha256=digest(candidate),
                              case_ids=[c.case_id for c in evaluation_cases])
                write_json(args.output / "run.json", record)
                rows = {"baseline": [], "candidate": []}
                for repeat in range(args.repeats):
                    for index, case in enumerate(evaluation_cases):
                        order = ("baseline", "candidate") if (repeat + index) % 2 == 0 else (
                            "candidate", "baseline")
                        for label in order:
                            policy = seed_candidate() if label == "baseline" else candidate
                            row = adapter.evaluate_rows([case], policy)[0]
                            row.update(repeat=repeat, comparison_label=label)
                            write_json(args.output / "evaluations"
                                       / f"{row['evaluation_index']:05d}.json", row)
                            rows[label].append(row)
                gate = acceptance(rows["baseline"], rows["candidate"])
                write_json(args.output / "comparison.json", {
                    **gate, "role": record["evaluation_role"], "repeats": args.repeats,
                })
                eligible = gate["passed"] and record["evaluation_role"] == "holdout"
                # 仅产生可审阅选择文件，绝不覆盖 tutor_policy.py 或线上配置。
                write_json(args.output / "selected-policy.json",
                           policy_artifact(candidate if eligible else seed_candidate()))
                record["selection"] = (
                    "eligible_for_release_review" if eligible else
                    "development_improved_needs_holdout" if gate["passed"] else "keep_baseline"
                )
                record["gate_passed"] = gate["passed"]
            record["status"] = "completed"
    except OptimizationStopped as exc:
        record.update(status="stopped", reason=str(exc), selection="no_selection")
    except BaseException as exc:
        record.update(status="error", error_type=type(exc).__name__, selection="no_selection")
        raise
    finally:
        record["budget"] = budget.summary()
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(args.output / "budget.json", budget.summary())
        write_json(args.output / "request-ledger.json", {"requests": budget.ledger})
        write_json(args.output / "run.json", record)
    print(json.dumps({"status": record["status"], "output": str(args.output),
                      "selection": record.get("selection"),
                      "requests": budget.requests}, ensure_ascii=False))
    return 0 if record["status"] == "completed" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="冻结开发划分，不调用模型")
    prepare.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--output", type=Path, required=True)
    for name in ("optimize", "compare"):
        p = sub.add_parser(name, help="执行离线批量模型请求（产生供应商费用）")
        p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
        p.add_argument("--protocol", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--max-requests", type=int, default=1200)
        p.add_argument("--max-cny", type=float, default=10.0)
        if name == "optimize":
            p.add_argument("--max-metric-calls", type=int, default=160)
            p.add_argument("--minibatch", type=int, default=3)
        else:
            p.add_argument("--candidate", type=Path, required=True)
            p.add_argument("--origin-run", type=Path, required=True)
            p.add_argument("--holdout", type=Path)
            p.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.output.exists():
            raise ValueError("refusing to overwrite an existing protocol")
        protocol = prepare_protocol(args.dataset, args.seed)
        write_json(args.output, protocol)
        print(json.dumps({"train": len(protocol["train_ids"]),
                          "dev_validation": len(protocol["dev_validation_ids"]),
                          "provider_requests": 0}, ensure_ascii=False))
        return 0
    return run_remote(args)


if __name__ == "__main__":
    raise SystemExit(main())
