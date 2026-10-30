"""从本轮不可信资料识别显式敏感载荷，统一处理模型输入和公开生成结果。"""

import re
from typing import Any


PAYLOAD = re.compile(
    r"(?:口令|密码|密钥|私密令牌|api[_ -]?key|password|secret|access[_ -]?token)"
    r"\s*(?:是|为|[:：=])?\s*[`\"'“‘]?"
    r"([A-Za-z0-9][A-Za-z0-9_./+=-]{3,})", re.I)

PRIVATE_PUBLIC_KEYS = frozenset({
    "correct_answer",
    "correct_index",
    "explanation",
    "system_prompt",
    "thinking",
})
SECRET_KEY = re.compile(
    r"(?:token|secret|password|authorization|cookie|api[_-]?key)",
    re.I,
)


def secret_shaped_key(key: object) -> bool:
    """秘密形状的键在任何嵌套层级都不能进入公开快照。"""
    return isinstance(key, str) and bool(SECRET_KEY.search(key))


def has_secret_shaped_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            secret_shaped_key(key) or has_secret_shaped_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(has_secret_shaped_key(item) for item in value)
    return False


def public_value(value: Any) -> Any:
    """纯函数式复制公开数据，同时移除私有键并隐藏显式敏感载荷。"""
    payloads: set[str] = set()

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            for nested in item.values():
                collect(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                collect(nested)
        elif isinstance(item, str):
            payloads.update(match.rstrip(".") for match in PAYLOAD.findall(item))

    collect(value)

    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: clean(nested)
                for key, nested in item.items()
                if str(key).lower() not in PRIVATE_PUBLIC_KEYS
                and not secret_shaped_key(key)
            }
        if isinstance(item, (list, tuple)):
            return [clean(nested) for nested in item]
        if isinstance(item, str):
            for payload in sorted(payloads, key=len, reverse=True):
                item = item.replace(payload, "[敏感载荷已隐藏]")
        return item

    result = clean(value)
    if has_secret_shaped_key(result):
        raise ValueError("secret-shaped key survived public-data redaction")
    return result


def register_untrusted(ctx, value):
    """只从当前授权来源提取明确标记的载荷，不读取其他学生资料。"""
    if isinstance(value, dict):
        for item in value.values():
            register_untrusted(ctx, item)
    elif isinstance(value, list):
        for item in value:
            register_untrusted(ctx, item)
    elif isinstance(value, str):
        before = len(ctx.sensitive_payloads)
        ctx.sensitive_payloads.update(item.rstrip(".") for item in PAYLOAD.findall(value))
        if len(ctx.sensitive_payloads) > before:
            ctx.record("untrusted_payload_detected", "Harness",
                       payload_count=len(ctx.sensitive_payloads))


def safe_value(ctx, value):
    if isinstance(value, dict):
        return {key: safe_value(ctx, item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_value(ctx, item) for item in value]
    if isinstance(value, str):
        for payload in sorted(ctx.sensitive_payloads, key=len, reverse=True):
            value = value.replace(payload, "[敏感载荷已隐藏]")
    return value


def guard_public(ctx, result):
    """在父事务提交前处理全部公开结果及计划，事件仅记录数量。"""
    clean = safe_value(ctx, result)
    if clean != result:
        ctx.record("public_output_redacted", "Harness", payload_count=len(ctx.sensitive_payloads))
    ctx.plan = safe_value(ctx, ctx.plan)
    ctx.expert_results = safe_value(ctx, ctx.expert_results)
    ctx.steps = safe_value(ctx, ctx.steps)
    return clean
