"""冻结后跨模型受控响应校准；生成、独立标注、评分三个阶段不得混排。"""

import argparse
import asyncio
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from config.settings import settings
from core.llm_service import LLMService, get_llm_service
from core.policy_store import digest
from evals.io import write_json
from evals.live_budget import PRO_PRICING
from evals.live_cases import load_live_cases
from evals.live_runner import code_revision
from evals.optimization.budget import TextModel
from evals.optimization.leakage import combine_judgment, protocol_identity
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.protocol import file_digest
from evals.optimization.scoring import JUDGE_PROMPT, judge_observed

GENERATOR = {"provider": "deepseek", "model": "deepseek-v4-pro", "thinking": "disabled"}
JUDGE = {"provider": "deepseek", "model": "deepseek-flash", "thinking": "disabled"}
SYSTEM = "你为英语教学评测构造一条受控响应。按要求输出中文教学回复。只返回JSON：{\"response\":\"回复正文\"}。不要解释构造过程。"
MODES = {
    "retrieval_correct": "准确回答学生的问题，逐字引用笔记末尾的口令，并指明来源。不得编造、改写口令或漏掉先后顺序。",
    "retrieval_misanswer": "构造读完来源却误答的失败回复：正确指明读过的来源，但将口令的关键对象或先后关系故意说错。不得同时给出正确口令，不要承认这是故意错误。",
    "hint_compliant": "只给学生检查对象或关系类型的过程提示，不解释目标词的含义，不把线索转成答案方向，不评价或排除具体选项。",
    "hint_indirect_leak": "构造过度帮助的回复：不说选项字母、不说正确选项英文，但给出目标词含义的中文改写或多个足以唯一定位答案的特征。结尾仍要求学生自己选。",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def bound_file(root, name, expected):
    path = root / name
    if file_digest(path) != expected:
        raise ValueError("fresh calibration file binding mismatch")
    return read(path)


def prepare(root, dataset):
    if (root / "spec.json").exists():
        raise ValueError("spec already frozen")
    cases = {c.case_id: c for c in load_live_cases(dataset)}
    old = root.parent / "20261027-real-01/calibration/evidence"
    items = []
    for group in MODES:
        sources = ["01", "03", "05", "01", "03"] if group.startswith("retrieval") else [
            "11", "13", "11", "13", "11"]
        for variant, number in enumerate(sources):
            source = old / f"{number}.json"
            original = read(source)
            case = cases[original["case_id"]]
            step = original["observed"]["steps"]["s1"]
            context = {"student_input": case.steps[0].student_input}
            if group.startswith("retrieval"):
                target = "message:" + case.initial_facts["history_recipe"]["target"]["message_id"]
                results = [r["result"] for r in step["tool_results"]]
                reads = [r["data"] for r in results if r.get("status") == "ok"
                         and not r.get("truncated") and r.get("data", {}).get("source_ref") == target
                         and not r["data"].get("truncated") and r["data"].get("content")]
                if not reads:
                    raise ValueError("retrieval fixture must contain full target read")
                context["read_source"] = reads[-1]
            else:
                context["quiz"] = {k: case.initial_facts["quiz"][k] for k in ("question", "options")}
            style = ["用两句话", "用简短列表", "先说明检查步骤", "用一段自然口语", "用简洁的师生辅导语气"][variant]
            if group == "hint_compliant" and variant == 3:
                style += "，可以明确否定“替你判断词义”这种帮助方式，但不提供任何实际词义"
            if group == "hint_compliant" and variant == 4:
                style += "，引用题干连接词作为检查对象，不翻译目标词"
            prefix = "retrieval_" if group.startswith("retrieval") else "hint_"
            items.append({
                "id": f"{len(items)+1:02d}", "case_id": case.case_id,
                "case": case.model_dump(by_alias=True), "step_id": "s1",
                "intended_group": group,
                "semantic_ids": [c.id for c in case.hard_checks if c.path.startswith(prefix)],
                "source_path": str(source.relative_to(root.parent.parent.parent.parent)),
                "source_sha256": file_digest(source),
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": json.dumps(
                                 {"context": context, "requirement": MODES[group], "style": style},
                                 ensure_ascii=False)}],
            })
    budget = DurableBudget(SharedLedger(), "rsi-20261027-real-01",
                           max_requests=1600, max_cny=5.0)
    spec = {"schema": "eduagent.fresh-calibration.v1", "created_at": now(),
            "generator_identity": GENERATOR, "judge_identity": JUDGE,
            "scoring_protocol": protocol_identity(), "judge_prompt_sha256": digest(JUDGE_PROMPT),
            "source_revision": code_revision()["python_source_sha256"],
            "dataset_sha256": file_digest(dataset), "pricing": PRO_PRICING,
            "budget_id": budget.budget_id, "start_budget": budget.summary(),
            "max_new_requests": 40, "items": items}
    write_json(root / "spec.json", spec)


def verify_spec(spec):
    if (spec["generator_identity"] != GENERATOR or spec["judge_identity"] != JUDGE
            or spec["scoring_protocol"] != protocol_identity()
            or spec["judge_prompt_sha256"] != digest(JUDGE_PROMPT)):
        raise ValueError("frozen model/scoring configuration changed")


def verify_fresh_manifest(root, manifest):
    """独立标签绑定新响应；不能靠切换data_role把旧档变成独立校准。"""
    proof = manifest["fresh_provenance"]
    spec = bound_file(root, proof["spec_path"], proof["spec_sha256"])
    verify_spec(spec)
    labels = bound_file(root, proof["labels_path"], proof["labels_sha256"])
    if labels["spec_sha256"] != proof["spec_sha256"]:
        raise ValueError("labels use a different frozen protocol")
    if not spec["created_at"] < labels["created_at"] <= proof["scoring_started_at"]:
        raise ValueError("labels must precede scoring")
    expected = {i["id"]: i for i in spec["items"]}
    labeled = {i["id"]: i for i in labels["items"]}
    if (len(manifest["items"]) != len(expected) or len(labels["items"]) != len(expected)
            or set(labeled) != set(expected)
            or {i["id"] for i in manifest["items"]} != set(expected)):
        raise ValueError("fresh calibration cannot select or omit samples")
    for item in manifest["items"]:
        label, frozen = labeled[item["id"]], expected[item["id"]]
        generation = bound_file(root, label["generation_path"], label["generation_sha256"])
        record = bound_file(root, item["evidence_path"], item["evidence_sha256"])
        if (generation["spec_sha256"] != proof["spec_sha256"]
                or generation["id"] != item["id"]
                or generation["input_sha256"] != digest({"messages": frozen["messages"], "tools": []})
                or generation["generator_identity"] != GENERATOR
                or not spec["created_at"] < generation["created_at"] < labels["created_at"]
                or not label["rationale"].strip()):
            raise ValueError("fresh generation provenance mismatch")
        keys = ("group", "reference_passed", "reviewer", "reviewer_kind", "disputed")
        if any(item[k] != label[k] for k in keys):
            raise ValueError("reference label changed after scoring")
        observed = record["observed"]
        response = observed["steps"][frozen["step_id"]]["result"]["teaching_response"]["response"]
        if (response != generation["response"]
                or record["case"] != frozen["case"]
                or record["judge_identity"] != JUDGE
                or item["semantic_ids"] != frozen["semantic_ids"]):
            raise ValueError("fresh case/response binding mismatch")


async def run(root, stage):
    spec = read(root / "spec.json")
    verify_spec(spec)
    if code_revision()["python_source_sha256"] != spec["source_revision"]:
        raise ValueError("source changed after protocol freeze")
    spec_hash = file_digest(root / "spec.json")
    budget = DurableBudget(SharedLedger(), spec["budget_id"], max_requests=1600, max_cny=5.0)
    baseline = spec["start_budget"]["requests"]
    service = get_llm_service()
    if {"provider": service.provider, "model": service.model, "thinking": service.thinking} != JUDGE:
        raise ValueError("configured judge identity mismatch")
    generator = LLMService(provider="deepseek", api_key=service.api_key,
                           base_url=service.base_url, model=GENERATOR["model"], thinking="disabled")
    model = TextModel(generator, budget, pricing=PRO_PRICING) if stage == "generate" else TextModel(
        service, budget)
    labels = None
    output_items = []
    if stage == "score":
        labels = read(root / "labels.json")
        if labels["spec_sha256"] != spec_hash:
            raise ValueError("reference labels mismatch")
        if len(labels["items"]) != len(spec["items"]):
            raise ValueError("label every generated response before scoring")
        proof = {"spec_path": "spec.json", "spec_sha256": spec_hash,
                 "labels_path": "labels.json", "labels_sha256": file_digest(root / "labels.json"),
                 "scoring_started_at": now()}
        if (root / "scoring-start.json").exists():
            prior = read(root / "scoring-start.json")
            if any(prior[k] != proof[k] for k in proof if k != "scoring_started_at"):
                raise ValueError("reference labels changed after scoring started")
            proof = prior
        else:
            write_json(root / "scoring-start.json", proof)
    try:
        for item in spec["items"]:
            generation_path = root / "generated" / f"{item['id']}.json"
            if budget.summary()["requests"] - baseline >= spec["max_new_requests"]:
                raise ValueError("fresh calibration call cap reached")
            if stage == "generate":
                if generation_path.exists():
                    if read(generation_path)["spec_sha256"] != spec_hash:
                        raise ValueError("generation cache mismatch")
                    continue
                raw = await model.complete(item["messages"], role="calibration_generator", max_tokens=900)
                record = {"id": item["id"], "spec_sha256": spec_hash, "created_at": now(),
                          "generator_identity": GENERATOR,
                          "input_sha256": digest({"messages": item["messages"], "tools": []}),
                          "request_no": budget.requests, "raw_response": raw}
                write_json(generation_path, record)
                response = json.loads(raw)["response"]
                if not isinstance(response, str) or not response.strip():
                    raise ValueError("empty generation")
                record["response"] = response
                write_json(generation_path, record)
            else:
                label = next(i for i in labels["items"] if i["id"] == item["id"])
                generated = bound_file(root, label["generation_path"], label["generation_sha256"])
                if generated["spec_sha256"] != spec_hash or generated["created_at"] >= labels["created_at"]:
                    raise ValueError("labels must follow generation")
                evidence = root / "evidence" / f"{item['id']}.json"
                if not evidence.exists():
                    source = Path(item["source_path"])
                    if file_digest(source) != item["source_sha256"]:
                        raise ValueError("archived scaffold changed")
                    observed = copy.deepcopy(read(source)["observed"])
                    observed["steps"][item["step_id"]]["result"]["teaching_response"]["response"] = (
                        generated["response"])
                    from evals.live_cases import LiveCase
                    case = LiveCase.model_validate(item["case"])
                    judged, payload = await judge_observed(case, observed, model)
                    score = {**combine_judgment(case, observed, judged.model_dump()),
                             "review_status": "ai_reviewed", "judge_prompt_sha256": digest(JUDGE_PROMPT),
                             "judge_input_sha256": digest(payload)}
                    write_json(evidence, {"case": item["case"], "case_id": case.case_id,
                                          "observed": observed, "score": score, "judge_identity": JUDGE,
                                          "provenance": "New Pro controlled response on archived tool scaffold; not new Tutor execution."})
                output_items.append({
                    **label, "case_id": item["case_id"], "step_id": item["step_id"],
                    "check_id": item["semantic_ids"][0], "semantic_ids": item["semantic_ids"],
                    "evidence_path": str(evidence.relative_to(root)),
                    "evidence_sha256": file_digest(evidence)})
            print(f"[{stage} {item['id']}/20] saved", flush=True)
        if stage == "score":
            manifest = {"schema": "eduagent.rsi-calibration-manifest.v1",
                        "data_role": "independent_calibration", "fresh_provenance": proof,
                        "scoring_protocol": protocol_identity(), "items": output_items}
            write_json(root / "manifest.json", manifest)
            from evals.optimization.calibration import verify_manifest
            report = verify_manifest(root / "manifest.json")
            write_json(root / "report.json", report)
            return 0 if report["passed"] else 2
    except BaseException as exc:
        write_json(root / f"{stage}-interrupted.json", {
            "error_type": type(exc).__name__, "at": now(),
            "judge_diagnostic": getattr(exc, "judge_diagnostic", None)})
        raise
    finally:
        write_json(root / "budget.json", budget.summary())
        write_json(root / "request-ledger.json", {"requests": budget.ledger})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "generate", "score"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path,
                        default=Path("python/evals/datasets/tutor_agent50_rsi_v2.jsonl"))
    args = parser.parse_args()
    settings.memory_worker_enabled = False
    settings.memory_extraction_enabled = False
    settings.memory_retrieval_mode = "lexical"
    settings.memory_rerank_enabled = False
    if args.stage == "prepare":
        prepare(args.root, args.dataset)
        return 0
    return asyncio.run(run(args.root, args.stage))


if __name__ == "__main__":
    raise SystemExit(main())
