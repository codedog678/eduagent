"""模型交接只传必要事实；持久化计划和原始专家结果保持完整。"""

from core.output_safety import register_untrusted, safe_value


def compact_results(results):
    return [{key: result[key] for key in (
        "task_id", "status", "findings", "source_refs", "uncertainty", "needs_input",
        "error_code", "practice") if key in result and result[key] not in (None, "", [])}
        for result in results]


def read_evidence(ctx):
    """只复用本轮成功读取且未分页截断的证据，不将搜索摘要当作原文。"""
    return list(ctx.read_evidence.values())


def model_value(ctx, value):
    register_untrusted(ctx, value)
    return safe_value(ctx, value)
