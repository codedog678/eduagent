"""用历史原始裁判作规则开发回归；不伪造新裁判提示或校准manifest。"""

import argparse
import json
from pathlib import Path

from evals.io import write_json
from evals.live_cases import load_live_cases
from evals.optimization.leakage import combine_judgment, protocol_identity
from evals.optimization.protocol import file_digest
from evals.optimization.scoring import validate_judgment


def replay(source, dataset, output):
    source, dataset, output = map(Path, (source, dataset, output))
    if output.exists():
        raise ValueError("never overwrite historical evidence")
    value = json.loads(source.read_text())
    cases = {c.case_id: c for c in load_live_cases(dataset)}
    if "slots" in value:
        labels = {r["id"]: r for r in json.loads(
            (source.parent / "labels.json").read_text())["items"]}
        items = [{**labels[s["id"]], **s} for s in value["slots"] if s["status"] == "scored"]
    else:
        items = value["items"]
    rows = []
    for index, item in enumerate(items, 1):
        path = source.parent / item["evidence_path"]
        if file_digest(path) != item["evidence_sha256"]:
            raise ValueError("historical source digest changed")
        record = json.loads(path.read_text())
        case = cases[record.get("case_id", record.get("case", {}).get("case_id"))]
        score = record["score"]
        raw = score.get("raw_judgment", {k: score[k] for k in ("semantic", "decisions")})
        validate_judgment(json.dumps(raw), case, record["observed"])
        combined = combine_judgment(case, record["observed"], raw)
        prefix = "hint_" if item["group"].startswith("hint_") else "retrieval_"
        selected = {c.id for c in case.hard_checks if c.path.startswith(prefix)}
        row = {"id": item.get("id", f"{index:02d}"), "case_id": case.case_id,
               "group": item["group"], "reference_passed": item["reference_passed"],
               "source_evidence_path": str(path), "source_evidence_sha256": file_digest(path),
               "historical_judge_prompt_sha256": score["judge_prompt_sha256"],
               "historical_judge_passed": all(c["passed"] for c in raw["semantic"] if c["id"] in selected),
               "hybrid_passed": all(c["passed"] for c in combined["semantic"] if c["id"] in selected),
               "teaching_checks_unchanged": all(c == raw["semantic"][i]
                   for i, c in enumerate(combined["semantic"]) if c["id"].startswith("H")),
               "current_rule_result": combined["leakage"]}
        rows.append(row)
    report = {"data_role": "development_rule_diagnostics", "passed": False,
              "status": "validation_required", "new_model_requests": 0,
              "current_scoring_protocol": protocol_identity(),
              "source_sha256": file_digest(source), "rows": rows, "total": len(rows),
              "historical_judge_matches": sum(r["historical_judge_passed"] == r["reference_passed"] for r in rows),
              "hybrid_matches": sum(r["hybrid_passed"] == r["reference_passed"] for r in rows),
              "limitation": "Historical judge + current rules only; no current-prompt model observations or independent gate."}
    write_json(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.source, args.dataset, args.output)
    print(json.dumps({k: result[k] for k in ("total", "hybrid_matches", "passed")}))
