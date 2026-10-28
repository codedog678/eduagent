"""实际响应审阅后、首次评分前冻结参考标签；构造意图不是标签。"""

from pathlib import Path

from evals.io import write_json
from evals.optimization.calibrate_fresh import now, read
from evals.optimization.protocol import file_digest

ROOT = Path(__file__).resolve().parent
RATIONALES = [
    "原文逐字为先画物品方向，再选借入或借出；来源N34正确，无冲突结论。",
    "引用N38末尾原文先圈提交物，再找接收方；来源正确。",
    "引用N33末尾原文先找承受者，再核对be与过去分词；来源正确。",
    "准确引述N34原文及位置。",
    "准确引述N38原文及位置。",
    "已提供完整N34读取证据，但回答将先画方向后选择颠倒为先选择后画方向。",
    "已提供完整N38读取证据，但回答将先圈提交物后找接收方颠倒。",
    "先正确引用N33，但最终所以口令原文应该是先找be动词与原文先找承受者矛盾；正确引文不能抵消错误结论。",
    "完整读取N34后仍将两个步骤的顺序颠倒。",
    "完整读取N38后仍将两个步骤的顺序颠倒。",
    "只指明对比关系与检查对象，未把噪声或城市特征映射为目标词义，未排除选项。",
    "实际已给出给予/帮助的行为类别，唯一对应giving；与情绪/状态对照排除了其余类别，因此不是合规提示。",
    "列出多种关系类型供学习者检查，未指定实际目标语义方向或评价选项，仍需学生判断。",
    "开头否认排除不能抵消后文；给予相对情绪/安静已对应giving并排除其余选项，实际泄露。",
    "供应商返回35个空格，无法解析JSON且没有教学响应；不猜标签，不重试、不替换。",
    "明确给出正确选项英文peaceful，是直接泄露；不能冒充仅有间接线索的样本。",
    "愿意分享、乐于助人、不吝啬与给予组合唯一定位giving，是间接释义泄露。",
    "明确给出peaceful，并提供安静/宁静等义，是直接泄露；不计入纯间接覆盖。",
    "大方、愿意付出、不吝啬、愿意给予均指向giving，学生无需再推断。",
    "直接给出目标词中文义宁静/平静/安静，与唯一选项peaceful等义；属于未出现选项英文的释义泄露。",
]


def main():
    output = ROOT / "labels.json"
    if output.exists() or (ROOT / "diagnostic-scoring-start.json").exists():
        raise ValueError("reference labels are immutable")
    items = []
    for index, rationale in enumerate(RATIONALES, 1):
        path = ROOT / "generated" / f"{index:02d}.json"
        if index <= 5:
            group = "retrieval_correct"
        elif index <= 10:
            group = "retrieval_misanswer"
        elif index in (11, 13):
            group = "hint_compliant"
        elif index in (16, 18):
            group = "hint_direct_leak"
        elif index == 15:
            group = None
        else:
            group = "hint_indirect_leak"
        items.append({
            "id": f"{index:02d}", "generation_path": str(path.relative_to(ROOT)),
            "generation_sha256": file_digest(path), "group": group,
            "reference_passed": group in ("retrieval_correct", "hint_compliant") if group else None,
            "status": "generation_invalid" if index == 15 else "labeled",
            "reviewer": "GPT-6 assistant response review before scoring",
            "reviewer_kind": "assistant", "disputed": False, "rationale": rationale})
    write_json(output, {
        "created_at": now(), "spec_sha256": file_digest(ROOT / "spec.json"),
        "independent_human_gold": False, "judge_results_seen": False,
        "items": items})


if __name__ == "__main__":
    main()
