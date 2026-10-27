"""从本轮不可信资料识别显式敏感载荷，统一处理模型输入和公开生成结果。"""

import re


PAYLOAD = re.compile(
    r"(?:口令|密码|密钥|私密令牌|api[_ -]?key|password|secret|access[_ -]?token)"
    r"\s*(?:是|为|[:：=])?\s*[`\"'“‘]?"
    r"([A-Za-z0-9][A-Za-z0-9_./+=-]{3,})", re.I)


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
