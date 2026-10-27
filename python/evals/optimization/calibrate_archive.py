"""用冻结轨迹与当前真实裁判校准；只调用judge，不重新生成Tutor回答。"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path

from config.settings import settings
from core.llm_service import get_llm_service
from core.policy_store import atomic_json
from evals.io import write_json
from evals.live_cases import load_live_cases
from evals.live_scorers import score_live_case
from evals.optimization.budget import TextModel
from evals.optimization.calibration import verify_manifest
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.protocol import digest
from evals.optimization.scoring import JUDGE_PROMPT, judge_observed, validate_judgment


async def run(args):
    spec = json.loads(args.spec.read_text())
    cases = {case.case_id: case for case in load_live_cases(args.dataset)}
    service = get_llm_service()
    if (service.provider != "deepseek" or service.model != "deepseek-flash"
            or service.thinking != "disabled" or not service._has_remote_llm()):
        raise ValueError("calibration requires configured DeepSeek Flash with thinking disabled")
    budget = DurableBudget(SharedLedger(), spec["budget_id"],
                           max_requests=spec["max_requests"], max_cny=spec["max_cny"])
    text_model = TextModel(service, budget)
    output_items = []
    args.output.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(spec["items"], 1):
        source = args.spec.parent / item["source_path"]
        original = json.loads(source.read_text())
        case = cases[item["case_id"]]
        observed = copy.deepcopy(original["observed"])
        if "response_override" in item:
            observed["steps"][item["step_id"]]["result"]["teaching_response"]["response"] = (
                item["response_override"])
        automatic = score_live_case(case, observed)
        evidence = args.output / "evidence" / f"{index:02d}.json"
        if evidence.exists():
            cached = json.loads(evidence.read_text())
            score = cached.get("score", {})
            if (score.get("review_status") == "ai_reviewed"
                    and score.get("judge_prompt_sha256") == digest(JUDGE_PROMPT)):
                validate_judgment(json.dumps({
                    "semantic": score["semantic"], "decisions": score["decisions"],
                }), case, observed)
                output_items.append({
                    **{key: value for key, value in item.items()
                       if key not in {"source_path", "response_override"}},
                    "evidence_path": str(evidence.relative_to(args.output)),
                    "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                })
                print(f"[calibration {index}/{len(spec['items'])}] reused {item['group']} "
                      f"{case.case_id}", flush=True)
                continue
        try:
            judged, payload = await judge_observed(case, observed, text_model)
            score = {
                **judged.model_dump(), "review_status": "ai_reviewed",
                "judge_prompt_sha256": digest(JUDGE_PROMPT),
                "judge_input_sha256": digest(payload),
            }
        except BaseException as exc:
            interrupted = {
                "schema": "eduagent.rsi-calibration-evidence.v1",
                "case_id": case.case_id, "observed": observed, "automatic": automatic,
                "scoring_status": "interrupted", "error_type": type(exc).__name__,
                "judge_diagnostic": getattr(exc, "judge_diagnostic", None),
                "judge_identity": {"provider": service.provider, "model": service.model,
                                   "thinking": service.thinking},
                "calibration_provenance": item["provenance"],
            }
            write_json(evidence, interrupted)
            write_json(args.output / "budget.json", budget.summary())
            write_json(args.output / "request-ledger.json", {"requests": budget.ledger})
            raise
        record = {
            "schema": "eduagent.rsi-calibration-evidence.v1",
            "case_id": case.case_id, "observed": observed, "automatic": automatic, "score": score,
            "judge_identity": {"provider": service.provider, "model": service.model,
                               "thinking": service.thinking},
            "calibration_provenance": item["provenance"],
        }
        write_json(evidence, record)
        content = evidence.read_bytes()
        output_items.append({
            **{key: value for key, value in item.items()
               if key not in {"source_path", "response_override"}},
            "evidence_path": str(evidence.relative_to(args.output)),
            "evidence_sha256": hashlib.sha256(content).hexdigest(),
        })
        write_json(args.output / "budget.json", budget.summary())
        write_json(args.output / "request-ledger.json", {"requests": budget.ledger})
        print(f"[calibration {index}/{len(spec['items'])}] {item['group']} {case.case_id}",
              flush=True)
    manifest = {"schema": "eduagent.rsi-calibration-manifest.v1",
                "budget_id": spec["budget_id"], "items": output_items}
    write_json(args.output / "manifest.json", manifest)
    report = verify_manifest(args.output / "manifest.json")
    report.update(budget=budget.summary(), provider_requests=budget.requests)
    write_json(args.output / "report.json", report)
    return 0 if report["passed"] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    settings.memory_worker_enabled = False
    settings.memory_extraction_enabled = False
    settings.memory_retrieval_mode = "lexical"
    settings.memory_rerank_enabled = False
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
