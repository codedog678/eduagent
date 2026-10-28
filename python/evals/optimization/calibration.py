"""裁判校准核验：不足样本、争议或未知标签不伪装为通过。"""

import argparse
import hashlib
import json
from pathlib import Path

from evals.io import write_json

GROUPS = ("retrieval_correct", "retrieval_misanswer", "hint_compliant", "hint_indirect_leak")


def calibration_report(rows):
    seen, counts, matches = set(), dict.fromkeys(GROUPS, 0), dict.fromkeys(GROUPS, 0)
    reviewers, disputed = set(), 0
    for row in rows:
        if row["group"] not in GROUPS:
            raise ValueError("unknown calibration group")
        # 同一轨迹不能换名字或分组重复凑样本。
        fingerprint = hashlib.sha256(row["response"].encode()).hexdigest()
        if not row["response"].strip() or fingerprint in seen:
            raise ValueError("empty or duplicate calibration trajectory")
        seen.add(fingerprint)
        if row["reviewer_kind"] not in {"assistant", "human"} or not row["reviewer"].strip():
            raise ValueError("explicit reviewer attribution required")
        reviewers.add(row["reviewer_kind"])
        if type(row["reference_passed"]) is not bool or type(row["judge_passed"]) is not bool:
            raise ValueError("reference and observed judgment must be booleans")
        if row.get("disputed", False):
            disputed += 1
            continue
        group = row["group"]
        if row["reference_passed"] != (group in {"retrieval_correct", "hint_compliant"}):
            raise ValueError("reference label contradicts calibration group")
        counts[group] += 1
        matches[group] += row["reference_passed"] == row["judge_passed"]
    total = sum(counts.values())
    agreement = sum(matches.values()) / total if total else None
    complete = all(value >= 5 for value in counts.values()) and not disputed
    passed = bool(complete and agreement >= .9
                  and matches["retrieval_misanswer"] == counts["retrieval_misanswer"]
                  and matches["hint_indirect_leak"] / counts["hint_indirect_leak"] >= .8)
    return {
        "status": "passed" if passed else "failed" if complete else "incomplete",
        "passed": passed, "counts": counts, "matches": matches, "agreement": agreement,
        "disputed": disputed, "reviewer_kinds": sorted(reviewers),
        "independent_human_gold": bool(rows) and reviewers == {"human"} and not disputed,
        "limitation": "Assistant labels are not independent human gold; calibration is not a holdout evaluation.",
    }


def verify_manifest(path: Path):
    """标签绑定已存原始执行与原始裁判；校验摘要，不接受未落盘的结果。"""
    manifest = json.loads(path.read_text())
    if manifest.get("data_role") == "independent_calibration":
        from evals.optimization.calibrate_fresh import verify_fresh_manifest
        verify_fresh_manifest(path.parent, manifest)
    rows = []
    identities = []
    hybrid = manifest.get("scoring_protocol") is not None
    if hybrid:
        from evals.optimization.leakage import protocol_identity
        from evals.live_cases import LiveCase
        if manifest["scoring_protocol"] != protocol_identity():
            raise ValueError("calibration leakage protocol changed")
    for item in manifest["items"]:
        evidence = path.parent / item["evidence_path"]
        content = evidence.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["evidence_sha256"]:
            raise ValueError("calibration evidence digest mismatch")
        record = json.loads(content)
        from evals.optimization.scoring import JUDGE_PROMPT
        from evals.optimization.protocol import digest
        if (record["score"].get("judge_prompt_sha256") != digest(JUDGE_PROMPT)
                or record["score"].get("review_status") != "ai_reviewed"):
            raise ValueError("calibration evidence uses a different or unobserved judge")
        identity = record.get("judge_identity")
        if not identity or any(identity != prior for prior in identities):
            raise ValueError("calibration judge identity missing or mixed")
        identities.append(identity)
        if hybrid:
            from evals.optimization.leakage import combine_judgment
            from evals.optimization.scoring import judge_payload, validate_judgment
            case = LiveCase.model_validate(record["case"])
            case.validate_contract()
            if (case.case_id != item["case_id"]
                    or record["score"]["judge_input_sha256"] != digest(
                        judge_payload(case, record["observed"]))):
                raise ValueError("calibration case/input binding mismatch")
            raw = record["score"]["raw_judgment"]
            validate_judgment(json.dumps(raw), case, record["observed"])
            combined = combine_judgment(case, record["observed"], raw)
            if any(record["score"].get(key) != combined[key] for key in combined):
                raise ValueError("calibration hybrid evidence mismatch")
        response = record["observed"]["steps"][item["step_id"]]["result"]["teaching_response"]["response"]
        checks = {c["id"]: c for c in record["score"]["semantic"]}
        semantic_ids = item.get("semantic_ids", [item["check_id"]])
        if hybrid:
            prefix = "hint_" if item["group"].startswith("hint_") else "retrieval_"
            required = {c.id for c in case.hard_checks if c.path.startswith(prefix)}
            if not required or set(semantic_ids) != required:
                raise ValueError("hybrid calibration requires all frozen dimensions")
        if (not semantic_ids or set(semantic_ids) - set(checks)
                or len(semantic_ids) != len(set(semantic_ids))):
            raise ValueError("calibration semantic coverage mismatch")
        # 正例要求该能力的全部冻结维度通过；负例只要其中一项被识别为失败。
        # 这样“未直接给答案但通过改写泄露”不会被单项检查伪装成合规。
        observed_passed = all(checks[identifier]["passed"] for identifier in semantic_ids)
        rows.append({**item, "response": response, "judge_passed": observed_passed})
    report = calibration_report(rows)
    # 旧协议或参与规则设计的资料只能回归复评；命中20条不等于独立校准。
    eligible = hybrid and manifest.get("data_role") == "independent_calibration"
    return {**report, "measured_passed": report["passed"],
            "passed": report["passed"] and eligible,
            "status": report["status"] if eligible else "validation_required",
            "data_role": manifest.get("data_role", "legacy"),
            "judge_identity": identities[0] if identities else None,
            "scoring_protocol": manifest.get("scoring_protocol")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify_manifest(args.manifest)
    write_json(args.output, report)
    raise SystemExit(0 if report["passed"] else 2)
