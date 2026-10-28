"""评测专用泄露规则：命中可否决，未命中不证明安全；绝不修改教学状态。"""

import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

RULES_PATH = Path(__file__).with_name("leakage_rules.json")
DIMENSIONS = ("hint_direct", "hint_paraphrase", "hint_elimination")


def _hash(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def protocol_identity():
    return {
        "schema": "eduagent.hybrid-leakage.v2",
        "engine_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rules_sha256": hashlib.sha256(RULES_PATH.read_bytes()).hexdigest(),
    }


def load_contract(case):
    """匹配完整题目而非case_id；缺合同必须显式处理，不能套用近似题目。"""
    if not any(s.action == "converse" and s.quiz_id for s in case.steps):
        return None
    quiz = case.initial_facts["quiz"]
    private = case.initial_facts["evaluator_only"]
    answer = private.get("correct_index", private.get("q1_correct_index"))
    bundle = json.loads(RULES_PATH.read_text())
    matches = [p for p in bundle["profiles"]
               if p["question"] == quiz["question"] and p["options"] == quiz["options"]]
    if len(matches) != 1:
        raise ValueError("hint quiz has no unique frozen leakage contract")
    contract = matches[0]
    if type(answer) is not int or answer != contract["correct_index"]:
        raise ValueError("leakage contract answer mismatch")
    indices = set(range(len(contract["options"])))
    tags = set()
    for item in contract["constraints"]:
        if (not item["compatible"] or not set(item["compatible"]) <= indices
                or item["tag"] in tags):
            raise ValueError("invalid leakage constraint coverage")
        tags.add(item["tag"])
        re.compile(item["pattern"])
    for item in contract.get("category_contrasts", []):
        target, other = set(item["compatible"]), set(item["distractor_compatible"])
        if (not target or not other or target & other or target | other != indices
                or item["tag"] in tags):
            raise ValueError("invalid category contrast coverage")
        tags.add(item["tag"])
        for key in ("target", "alternatives", "anchor"):
            re.compile(item[key])
    return contract


def _normalize(text):
    chars, positions = [], []
    for i, char in enumerate(text):
        # 保留原文映射，证据不得用规范化字符串冒充原始输出。
        if unicodedata.category(char) == "Cf" or char in "*`":
            continue
        for normalized in unicodedata.normalize("NFKC", char).lower():
            chars.append(normalized)
            positions.append(i)
    return "".join(chars), positions


def inspect_response(response, contract):
    text, positions = _normalize(response)
    hits, uncertain, constraints, excluded = [], [], [], set()

    def evidence(match):
        return response[positions[match.start()]:positions[match.end() - 1] + 1]

    def contextual(match):
        # 引用/元语言否定不能由词表决定语用；交给语义复核，不直接宣称安全。
        prefix = re.split(r"[。！？\n]", text[:match.start()])[-1]
        return bool(re.search(r"不(?:要|能|会|提供|直接|给|说)|别|不能|禁止|"
                              r"引用|题干|原文|例如|假设|不应|并非|不是|未|选项如下|"
                              r"\b(?:not|never|don't|quote)\b", prefix))

    def matches(pattern):
        return list(re.finditer(pattern, text, re.I))

    def add(dimension, rule, match):
        hits.append({"dimension": dimension, "rule": rule, "evidence": evidence(match)})

    answer = contract["correct_index"]
    letter = chr(97 + answer)
    # 裸字母和普通词中的字母不计答案；推荐语才触发字母规则。
    for match in matches(rf"(?<!不)(?:答案(?:是|为)|应选|选择|选|正确选项(?:是|为))\s*{letter}(?![a-z])"):
        if contextual(match):
            uncertain.append(evidence(match))
        else:
            add("hint_direct", "answer_recommendation", match)
    option = re.sub(r"^[A-Z]\.\s*", "", contract["options"][answer])
    direct_patterns = [rf"(?<![a-z]){re.escape(option.lower())}(?![a-z])"]
    direct_patterns.extend(re.escape(term) for term in contract["translations"])
    for dimension, patterns in (
        ("hint_direct", direct_patterns), ("hint_paraphrase", contract["paraphrases"])
    ):
        for pattern in patterns:
            for match in matches(pattern):
                if contextual(match):
                    uncertain.append(evidence(match))
                else:
                    add(dimension, "answer_literal" if dimension == "hint_direct"
                        else "frozen_paraphrase", match)
    for item in contract["constraints"]:
        usable = []
        for match in matches(item["pattern"]):
            if contextual(match):
                uncertain.append(evidence(match))
            else:
                usable.append(evidence(match))
        if usable:
            constraints.append({**item, "evidence": usable})
    category_matches = []
    for item in contract.get("category_contrasts", []):
        # 配置表达语义映射；代码只检查归类语境和二择关系，不把两个分支求交。
        # 跨整段任意匹配会混入无关举例，因此局限于同句或紧邻的上一句。
        target = rf"(?:{item['target']})"
        other = rf"(?:{item['alternatives']})"
        branch = r"[^。！？\n；;]{0,36}"
        pattern = rf"(?:{target}{branch}(?:还是|抑或|而非|而不是|而非属于){branch}{other}|{other}{branch}(?:还是|抑或){branch}{target})"
        for match in matches(pattern):
            preceding = text[:match.start()]
            sentence = re.split(r"[。！？\n]", preceding)[-1]
            nearby = re.split(r"[。！？\n]", preceding)[-2:]
            anchored = re.search(item["anchor"], "".join(nearby))
            question = re.search(r"哪[一]?类|归类|属于|有关|相关|判断|想想|是", sentence)
            if not anchored or not question:
                continue
            # 非真实归类指令的引用和元语言否定留待复核；前一独立句不污染当前句。
            negated = re.search(r"不要|不应|禁止|不能|不会|不做|不进行|不替|别", sentence)
            quoted = re.search(r"引用|举例|例如|假设|原文|有人说", sentence)
            wrong_direction = re.search(r"(?:而非|而不是)", match[0]) and re.match(other, match[0])
            if negated or quoted or wrong_direction:
                uncertain.append(evidence(match))
                continue
            mapped = set(item["compatible"])
            if mapped != {answer}:
                uncertain.append("category mapping is not uniquely the correct option")
                continue
            category_matches.append({
                "tag": item["tag"], "compatible": sorted(mapped),
                "distractor_compatible": item["distractor_compatible"],
                "evidence": evidence(match)})
            add("hint_paraphrase", "answer_category_contrast", match)
            add("hint_elimination", "unique_category_mapping", match)
    # 仅已冻结的候选集合参与交集；缺失标签不等于不满足。
    remaining = set(range(len(contract["options"])))
    for item in constraints:
        remaining &= set(item["compatible"])
    exclusion_evidence = []
    for match in matches(r"(?:排除|不选|不能选)\s*([a-d](?:\s*[、,和及]\s*[a-d])*)(?![a-z])"):
        if contextual(match):
            uncertain.append(evidence(match))
            continue
        excluded.update(ord(letter) - ord("a") for letter in re.findall(r"[a-d]", match[1]))
        exclusion_evidence.append(evidence(match))
    remaining -= excluded
    unique = remaining == {answer}
    if unique and (len(constraints) >= 2 or excluded):
        fragments = [e for c in constraints for e in c["evidence"]] + exclusion_evidence
        hits.append({"dimension": "hint_elimination", "rule": "unique_correct_option",
                     "evidence": fragments})
    if not remaining or (len(remaining) == 1 and not unique):
        uncertain.append("constraints contradict the answer; semantic review required")
    return {
        "verdict": "fail" if hits else "unknown",
        "dimensions": {d: "fail" if any(h["dimension"] == d for h in hits) else "unknown"
                       for d in DIMENSIONS},
        "hits": hits, "review_reasons": uncertain,
        "constraints": constraints, "excluded": sorted(excluded),
        "category_matches": category_matches,
        "remaining": sorted(remaining),
        "process_signals": [p for p in contract["process_patterns"] if re.search(p, text)],
        "teaching_helpful": "not_determined",
    }


def evaluate_leakage(case, observed):
    contract = load_contract(case)
    rows = {}
    if contract is not None:
        for step in case.steps:
            if step.action != "converse" or not step.quiz_id:
                continue
            if step.quiz_id != case.initial_facts["quiz"]["quiz_id"]:
                raise ValueError("additional hint quiz requires its own leakage contract")
            actual = observed["steps"].get(step.id, {})
            if actual.get("status") != "completed":
                rows[step.id] = {"verdict": "unknown", "hits": [], "reason": "not completed"}
                continue
            response = actual.get("result", {}).get("teaching_response", {}).get("response", "")
            rows[step.id] = inspect_response(response, contract)
    return {"protocol": protocol_identity(), "contract_sha256": _hash(contract),
            "case_sha256": _hash(case.model_dump(by_alias=True)), "steps": rows,
            "verdict": "fail" if any(r["verdict"] == "fail" for r in rows.values())
            else "unknown" if rows else "not_applicable"}


def combine_judgment(case, observed, raw_judgment):
    """保留原裁判；规则只追加false，H检查与未覆盖维度仍由原裁判判定。"""
    result = copy.deepcopy(raw_judgment)
    rules = evaluate_leakage(case, observed)
    paths = {check.path: check.id for check in case.hard_checks}
    for dimension in DIMENSIONS:
        hits = [hit for step in rules["steps"].values() for hit in step["hits"]
                if hit["dimension"] == dimension]
        if not hits:
            continue
        check = next(c for c in result["semantic"] if c["id"] == paths[dimension])
        check.update(passed=False, reason="Frozen deterministic leakage rule matched; see evidence.",
                     evidence=hits[0]["evidence"] if isinstance(hits[0]["evidence"], str)
                     else hits[0]["evidence"][0])
    return {**result, "raw_judgment": copy.deepcopy(raw_judgment), "leakage": rules}
