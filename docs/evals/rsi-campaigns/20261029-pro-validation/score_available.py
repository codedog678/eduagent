"""本批次失败后的诊断：全量记录20个槽位，空响应不评分，不授予Campaign资格。"""

import asyncio
import copy
import json
from pathlib import Path

from config.settings import settings
from core.llm_service import get_llm_service
from evals.io import write_json
from evals.live_cases import LiveCase
from evals.optimization.budget import TextModel
from evals.optimization.calibrate_fresh import JUDGE, now, read, verify_spec, bound_file
from evals.optimization.calibration import calibration_report
from evals.optimization.leakage import combine_judgment
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.protocol import digest, file_digest
from evals.optimization.scoring import JUDGE_PROMPT, judge_observed


async def main():
    root = Path(__file__).resolve().parent
    spec = read(root / "spec.json")
    verify_spec(spec)
    sh = file_digest(root / "spec.json")
    labels = read(root / "labels.json")
    assert labels["spec_sha256"] == sh
    assert {i["id"] for i in labels["items"]} == {i["id"] for i in spec["items"]}
    proof = {"spec_sha256": sh, "labels_sha256": file_digest(root / "labels.json"),
             "scoring_started_at": now(), "purpose": "diagnostic_only",
             "script_sha256": file_digest(__file__)}
    start = root / "diagnostic-scoring-start.json"
    if start.exists():
        prior = read(start)
        assert all(proof[k] == prior[k] for k in proof if k != "scoring_started_at")
        proof = prior
    else:
        write_json(start, proof)
    assert labels["created_at"] < proof["scoring_started_at"]
    settings.memory_worker_enabled = False
    settings.memory_extraction_enabled = False
    settings.memory_retrieval_mode = "lexical"
    settings.memory_rerank_enabled = False
    service = get_llm_service()
    assert {"provider": service.provider, "model": service.model, "thinking": service.thinking} == JUDGE
    budget = DurableBudget(SharedLedger(), spec["budget_id"], max_requests=1600, max_cny=5)
    model = TextModel(service, budget)
    rows, slots = [], []
    try:
        for item, label in zip(spec["items"], labels["items"]):
            assert item["id"] == label["id"]
            generated = bound_file(root, label["generation_path"], label["generation_sha256"])
            assert generated["spec_sha256"] == sh
            if label["status"] != "labeled":
                slots.append({"id": item["id"], "status": label["status"]})
                continue
            response = generated["response"]
            assert response and label["rationale"] and not label["disputed"]
            evidence = root / "diagnostic-evidence" / f"{item['id']}.json"
            if evidence.exists():
                record = read(evidence)
                assert record["binding"] == proof
            else:
                assert budget.summary()["requests"] - spec["start_budget"]["requests"] < 40
                source = Path(item["source_path"])
                assert file_digest(source) == item["source_sha256"]
                observed = copy.deepcopy(read(source)["observed"])
                observed["steps"][item["step_id"]]["result"]["teaching_response"]["response"] = response
                case = LiveCase.model_validate(item["case"])
                try:
                    judged, payload = await judge_observed(case, observed, model)
                    score = {**combine_judgment(case, observed, judged.model_dump()),
                             "review_status": "ai_reviewed",
                             "judge_prompt_sha256": digest(JUDGE_PROMPT),
                             "judge_input_sha256": digest(payload)}
                    record = {"binding": proof, "case": item["case"], "observed": observed,
                              "score": score, "judge_identity": JUDGE, "status": "scored"}
                except Exception as exc:
                    record = {"binding": proof, "case": item["case"], "observed": observed,
                              "judge_identity": JUDGE, "status": "score_failed",
                              "error_type": type(exc).__name__,
                              "judge_diagnostic": getattr(exc, "judge_diagnostic", None)}
                write_json(evidence, record)
            slots.append({"id": item["id"], "status": record["status"],
                          "evidence_path": str(evidence.relative_to(root)),
                          "evidence_sha256": file_digest(evidence)})
            if record["status"] == "scored":
                checks = {s["id"]: s for s in record["score"]["semantic"]}
                raw_checks = {s["id"]: s for s in record["score"]["raw_judgment"]["semantic"]}
                rows.append({**label, "response": response,
                             "judge_passed": all(checks[k]["passed"] for k in item["semantic_ids"]),
                             "raw_judge_passed": all(raw_checks[k]["passed"] for k in item["semantic_ids"]),
                             "rules_status": record["score"]["leakage"]["verdict"]})
            print(f"[diagnostic {item['id']}/20] {record['status']}", flush=True)
    finally:
        write_json(root / "budget.json", budget.summary())
        write_json(root / "request-ledger.json", {"requests": budget.ledger})
        measured = calibration_report([r for r in rows if r["group"] != "hint_direct_leak"])
        write_json(root / "report.json", {
            **measured, "passed": False, "status": "incomplete",
            "data_role": "independent_calibration_diagnostic", "binding": proof,
            "generator_identity": spec["generator_identity"], "judge_identity": JUDGE,
            "campaign_search_started": False, "slots": slots, "rows": rows,
            "reason": "Frozen group coverage failed; no replacement sampling or Campaign admission.",
            "all_valid_agreement": (sum(r["judge_passed"] == r["reference_passed"] for r in rows)
                                    / len(rows) if rows else None),
            "budget": budget.summary()})


if __name__ == "__main__":
    asyncio.run(main())
