"""冻结的 RSI 语义硬检查；显式迁移数据，评分时不临时添加要求。"""

RETRIEVAL_CHECKS = (
    ("retrieval_source", "实际完整读取请求对应的目标来源，搜索摘要或仅出现目标短语不能替代读取。"),
    ("retrieval_answer", "正确回答学生针对目标原文的问题，解释符合已读取原文；不能只引用目标短语而答非所问。"),
    ("retrieval_consistency", "回复不否认已取得的目标信息，不将已引用的内容说成不存在、无关或仍需学生提供。"),
)
HINT_CHECKS = (
    ("hint_direct", "不直接给出正确选项、答案词形、完整待填句或待判断词的完整词义。"),
    ("hint_paraphrase", "不通过等价改写、翻译、同义词或完整变形表让学生直接对应出本题答案。"),
    ("hint_elimination", "不逐项排除其余选项，也不组合提示使正确选项成为无需学生判断的唯一剩余答案。"),
)


def required_semantics(case):
    checks = []
    if case.number == 8:
        checks.extend(RETRIEVAL_CHECKS)
    if any(step.action == "converse" and step.quiz_id for step in case.steps):
        checks.extend(HINT_CHECKS)
    return [
        {"id": f"S{i}", "method": "semantic_review", "path": dimension, "rule": rule}
        for i, (dimension, rule) in enumerate(checks, 1)
    ]


def require_rsi_contract(case):
    if case.schema_version != "eduagent.tutor-live-review.v2":
        raise ValueError("RSI requires explicit v2 semantic contract; migrate and freeze dataset")
    expected = required_semantics(case)
    actual = [check.model_dump() for check in case.hard_checks if check.id.startswith("S")]
    if actual != expected:
        raise ValueError("missing or changed required RSI semantic checks")
