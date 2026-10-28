"""只读重放已有真实裁判，生成规则+模型对照；无模型请求、无发布凭证。"""

import argparse
import json
from pathlib import Path

from evals.io import write_json
from evals.live_cases import load_live_cases
from evals.optimization.calibration import verify_manifest
from evals.optimization.leakage import combine_judgment, protocol_identity
from evals.optimization.protocol import digest, file_digest
from evals.optimization.scoring import JUDGE_PROMPT, judge_payload, validate_judgment


def replay(manifest_path, dataset_path, output):
    manifest_path, dataset_path, output = map(Path, (manifest_path, dataset_path, output))
    original = json.loads(manifest_path.read_text())
    cases = {c.case_id: c for c in load_live_cases(dataset_path)}
    records, items, comparisons = [], [], []
    # 所有输入先核验再写文件；新目录避免覆盖中断和历史证据。
    for item in original["items"]:
        source = manifest_path.parent / item["evidence_path"]
        if file_digest(source) != item["evidence_sha256"]:
            raise ValueError("source calibration digest mismatch")
        record = json.loads(source.read_text())
        case = cases[item["case_id"]]
        score = record["score"]
        if (score["judge_prompt_sha256"] != digest(JUDGE_PROMPT)
                or score["judge_input_sha256"] != digest(judge_payload(case, record["observed"]))):
            raise ValueError("source judge prompt or input changed")
        raw = {key: score[key] for key in ("semantic", "decisions")}
        validate_judgment(json.dumps(raw), case, record["observed"])
        combined = combine_judgment(case, record["observed"], raw)
        record = {**record, "case": case.model_dump(by_alias=True),
                  "source_evidence_sha256": item["evidence_sha256"],
                  "score": {**score, **combined}}
        # 校准记录不包含正式任务得分，避免保留旧派生值误作新成绩。
        for key in ("task_success", "score", "decision_rate"):
            record["score"].pop(key, None)
        records.append(record)
        selected = set(item["semantic_ids"])
        comparisons.append({
            "case_id": case.case_id, "group": item["group"],
            "reference_passed": item["reference_passed"],
            "raw_judge_passed": all(c["passed"] for c in raw["semantic"] if c["id"] in selected),
            "hybrid_passed": all(c["passed"] for c in combined["semantic"] if c["id"] in selected),
            "rules_verdict": combined["leakage"]["verdict"],
            "rule_hits": [h for s in combined["leakage"]["steps"].values() for h in s["hits"]],
            "teaching_checks": [c for c in combined["semantic"] if c["id"].startswith("H")],
        })
    output.mkdir(parents=True, exist_ok=False)
    for index, (item, record) in enumerate(zip(original["items"], records), 1):
        path = output / "evidence" / f"{index:02d}.json"
        write_json(path, record)
        items.append({**item, "evidence_path": str(path.relative_to(output)),
                      "evidence_sha256": file_digest(path)})
    write_json(output / "manifest.json", {
        "schema": "eduagent.hybrid-calibration.v1", "data_role": "development_replay",
        "scoring_protocol": protocol_identity(), "dataset_sha256": file_digest(dataset_path),
        "source_manifest_sha256": file_digest(manifest_path), "items": items,
    })
    report = verify_manifest(output / "manifest.json")
    report.update(new_model_requests=0, new_estimated_cny=0,
                  original_judge_agreement=sum(
                      r["raw_judge_passed"] == r["reference_passed"] for r in comparisons
                  ) / len(comparisons), comparisons=comparisons,
                  limitation="Replayed development evidence; no independent calibration or release qualification.")
    write_json(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.manifest, args.dataset, args.output)
    print(json.dumps({k: report[k] for k in
                      ("agreement", "matches", "passed", "status", "new_model_requests")}))
