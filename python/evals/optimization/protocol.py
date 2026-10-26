"""冻结开发划分、输入摘要和可修改范围。50 条开发任务不冒充留出集。"""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

from core.tutor_policy import BASE_RULES, QUIZ_RULES, TURN_RULES
from evals.live_cases import CASE_IDS, load_live_cases


SCHEMA = "eduagent.gepa.v1"
GEPA_VERSION = "0.1.4"
RUNTIME = {
    "enable_tutor_tools": True, "enable_agent_llm_decisions": False,
    "enable_db_logging": False, "enable_coordinator": False,
    "memory_retrieval_mode": "lexical", "memory_extraction_enabled": False,
    "memory_rerank_enabled": False, "memory_worker_enabled": False,
    "tutor_max_model_calls": 3, "tutor_max_tool_calls": 4,
    "tutor_context_budget_tokens": 6000, "tutor_max_output_tokens": 800,
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def file_digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seed_candidate() -> dict:
    return {"turn_rules": TURN_RULES}


def capability_name(case) -> str:
    # 原 8 条没有 capability 字段，按既有执行契约与新变体对齐能力组。
    return case.capability or {
        5: "multi_turn_continuation", 6: "multi_turn_continuation",
        7: "grounded_history", 8: "full_history_retrieval",
        9: "injection_and_permissions", 10: "injection_and_permissions",
        11: "learning_evidence", 12: "learning_evidence",
    }.get(case.number, "tool_and_evidence_decision")


def policy_artifact(candidate: dict) -> dict:
    validate_candidate(candidate)
    return {"schema": SCHEMA, "candidate": candidate, "policy_sha256": digest(candidate),
            "fixed_rules_sha256": digest([BASE_RULES, QUIZ_RULES])}


def validate_candidate(candidate: dict, forbidden: tuple[str, ...] = ()) -> None:
    if (not isinstance(candidate, dict) or set(candidate) != {"turn_rules"}
            or not isinstance(candidate["turn_rules"], str)
            or not candidate["turn_rules"].strip() or len(candidate["turn_rules"]) > 6000):
        raise ValueError("only a nonempty turn_rules component (<=6000 chars) is allowed")
    if any(text and text in candidate["turn_rules"] for text in forbidden):
        raise ValueError("candidate contains fixture-specific identifiers or private literals")


def load_policy(path: Path) -> dict:
    value = json.loads(path.read_text())
    if value != policy_artifact(value["candidate"]):
        raise ValueError("policy digest, fixed rules or schema mismatch")
    return value["candidate"]


def private_literals(cases) -> tuple[str, ...]:
    """禁止把样例标识、检索口令或私有标记写进通用策略。不是语义泄露检测器。"""
    values = set()
    for case in cases:
        values.update((case.case_id, case.learner_id))
        for step in case.steps:
            values.update(v for v in (step.session_id, step.quiz_id) if v)
        values.update(case.history_source_refs)
        if case.number == 8:
            values.update((case.target_source_ref, *case.retrieval_expectations))
        if case.number == 10:
            values.update(case.foreign_expectations)
    return tuple(sorted(values, key=lambda value: (-len(value), value)))


def prepare_protocol(path: Path, seed: int = 42) -> dict:
    cases = load_live_cases(path)
    groups = defaultdict(list)
    for case in cases:
        groups[capability_name(case)].append(case)
    rng = random.Random(seed)
    train, val, counts = [], [], {}
    for name, group in sorted(groups.items()):
        # 已用于人工调提示的旧案例只进入训练侧；仍明确整个集合属于开发数据。
        legacy = [c for c in group if c.case_id in CASE_IDS]
        fresh = sorted((c for c in group if c.case_id not in CASE_IDS),
                       key=lambda c: c.case_id)
        rng.shuffle(fresh)
        nval = min(len(fresh), max(1, round(len(group) * .3))) if fresh else 0
        val.extend(c.case_id for c in fresh[:nval])
        train.extend(c.case_id for c in legacy + fresh[nval:])
        counts[name] = {"train": len(group) - nval, "dev_validation": nval}
    if not train or not val:
        raise ValueError("dataset needs nonempty train and development validation splits")
    return {
        "schema": SCHEMA, "dataset_sha256": file_digest(path), "seed": seed,
        "train_ids": sorted(train), "dev_validation_ids": sorted(val),
        "counts": counts, "dataset_role": "development_only",
        "holdout": "must be supplied separately after development",
        "seed_policy": policy_artifact(seed_candidate()),
        "runtime": RUNTIME, "gepa_version": GEPA_VERSION,
        "scorer_sha256": file_digest(Path(__file__).with_name("scoring.py")),
    }


def load_protocol(path: Path, dataset: Path):
    protocol = json.loads(path.read_text())
    if protocol != prepare_protocol(dataset, protocol["seed"]):
        raise ValueError("protocol mismatch: dataset, split, rules or scorer changed; prepare again")
    cases = {c.case_id: c for c in load_live_cases(dataset)}
    return protocol, cases


def assert_holdout_disjoint(development, holdout):
    """拒绝相同 ID、学习者及只换 ID 的重复脚本；人工还需检查语义近重复。"""
    def signature(case):
        return digest({
            "knowledge": case.knowledge_id,
            "inputs": [s.student_input for s in case.steps if s.action == "converse"],
            "quiz": {k: case.initial_facts.get("quiz", {}).get(k)
                     for k in ("question", "options")},
        })
    ids = {c.case_id for c in development}
    learners = {c.learner_id for c in development}
    signatures = {signature(c) for c in development}
    if any(c.case_id in ids or c.learner_id in learners or signature(c) in signatures
           for c in holdout):
        raise ValueError("holdout overlaps development by ID, learner or task content")
