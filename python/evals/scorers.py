"""不依赖评审模型的确定性契约评分器。"""

from __future__ import annotations

import re
from typing import Any

from evals.models import EvalCase, ScoreDetail

_SIGNAL_PATTERNS = {
    "mistake_identification": (
        r"\b(issue|mistake|error|not quite|incorrect|check the)\b",
        r"(错误|问题|不对|检查)",
    ),
    "guidance": (
        r"\b(check|consider|because|look at|compare|remember|try)\b",
        r"(检查|考虑|因为|观察|比较|回忆|尝试|先)",
    ),
    "actionability": (
        r"\b(try|revise|check|write|choose|explain|identify|next)\b",
        r"(尝试|修改|检查|写出|选择|解释|找出|下一步|请)",
    ),
    "encouraging": (
        r"\b(good try|nice attempt|keep going|you can|well done)\b",
        r"(不错|继续|做得好|可以做到)",
    ),
}


def _value_at(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
            continue
        raise KeyError(path)
    return current


def _contains(value: Any, expected: Any) -> bool:
    if isinstance(value, str):
        return str(expected) in value
    if isinstance(value, (list, tuple, set)):
        return expected in value
    if isinstance(value, dict):
        return expected in value
    return False


def contract_score(case: EvalCase, observed: dict[str, Any]) -> ScoreDetail | None:
    expected = case.expected
    check_groups = ("equals", "truthy", "falsey", "contains", "absent")
    if not any(group in expected for group in check_groups):
        return None

    checks: dict[str, bool] = {}
    for path, wanted in expected.get("equals", {}).items():
        try:
            checks[f"equals:{path}"] = _value_at(observed, path) == wanted
        except KeyError:
            checks[f"equals:{path}"] = False
    for path in expected.get("truthy", []):
        try:
            checks[f"truthy:{path}"] = bool(_value_at(observed, path))
        except KeyError:
            checks[f"truthy:{path}"] = False
    for path in expected.get("falsey", []):
        try:
            checks[f"falsey:{path}"] = not bool(_value_at(observed, path))
        except KeyError:
            checks[f"falsey:{path}"] = False
    for path, wanted in expected.get("contains", {}).items():
        try:
            checks[f"contains:{path}"] = _contains(_value_at(observed, path), wanted)
        except KeyError:
            checks[f"contains:{path}"] = False
    for path in expected.get("absent", []):
        try:
            _value_at(observed, path)
            checks[f"absent:{path}"] = False
        except KeyError:
            checks[f"absent:{path}"] = True

    passed = all(checks.values())
    failed = [name for name, result in checks.items() if not result]
    return ScoreDetail(
        scorer="contract",
        passed=passed,
        checks=checks,
        message="" if passed else "failed checks: " + ", ".join(failed),
    )


def detect_signals(text: str, protected_answers: list[str] | None = None) -> set[str]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    signals = {
        signal
        for signal, patterns in _SIGNAL_PATTERNS.items()
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)
    }
    for answer in protected_answers or []:
        answer = re.sub(r"\s+", " ", answer.strip().lower())
        if answer and answer in normalized:
            signals.add("answer_reveal")
            break
    return signals


def policy_score(case: EvalCase, observed: dict[str, Any]) -> ScoreDetail | None:
    required = set(case.expected.get("required_signals", []))
    forbidden = set(case.expected.get("forbidden_signals", []))
    if not required and not forbidden:
        return None
    text = str(observed.get("response", ""))
    signals = detect_signals(text, case.input.get("protected_answers", []))
    checks = {
        **{f"required:{signal}": signal in signals for signal in sorted(required)},
        **{f"forbidden:{signal}": signal not in signals for signal in sorted(forbidden)},
    }
    passed = all(checks.values())
    return ScoreDetail(
        scorer="policy",
        passed=passed,
        checks=checks,
        message="" if passed else f"detected signals: {sorted(signals)}",
    )


def label_agreement_score(
    case: EvalCase, observed: dict[str, Any]
) -> ScoreDetail | None:
    if case.kind != "labeled_response":
        return None
    annotations = case.expected.get("annotations", {})
    signals = detect_signals(
        str(observed.get("response", "")),
        case.input.get("protected_answers", []),
    )
    predicted = {
        "Mistake_Identification": "Yes" if "mistake_identification" in signals else "No",
        "Mistake_Location": "Yes" if "mistake_identification" in signals else "No",
        "Revealing_of_the_Answer": "Yes" if "answer_reveal" in signals else "No",
        "Providing_Guidance": "Yes" if "guidance" in signals else "No",
        "Actionability": "Yes" if "actionability" in signals else "No",
        "Tutor_Tone": "Encouraging" if "encouraging" in signals else "Neutral",
    }
    checks: dict[str, bool] = {}
    for dimension, prediction in predicted.items():
        if dimension not in annotations:
            continue
        gold = str(annotations[dimension])
        if dimension == "Revealing_of_the_Answer" and gold.startswith("Yes"):
            gold = "Yes"
        checks[dimension] = prediction == gold
    agreement = sum(checks.values()) / len(checks) if checks else 0.0
    threshold = float(case.expected.get("min_agreement", 0.0))
    return ScoreDetail(
        scorer="label_agreement",
        passed=agreement >= threshold,
        checks=checks,
        metrics={"agreement": agreement},
        message=f"rule-label agreement {agreement:.3f}; not a teaching-quality score",
    )


def score_case(case: EvalCase, observed: dict[str, Any]) -> list[ScoreDetail]:
    details = [
        detail
        for detail in (
            contract_score(case, observed),
            policy_score(case, observed),
            label_agreement_score(case, observed),
        )
        if detail is not None
    ]
    if not details:
        return [
            ScoreDetail(
                scorer="configuration",
                passed=False,
                message="case defines no supported expectations",
            )
        ]
    return details
