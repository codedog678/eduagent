"""独立诊断步骤只来自学生任务，不能由模型自行升级普通学习安排。"""

import re


def assessment_requested(text):
    clauses = re.split(r"[。；\n，,]", text)
    return any(
        not re.search(r"不要|无需|不需要|不想|don't|do not", clause, re.I)
        and re.search(
            r"诊断|测评|测验|错题|错误|薄弱|"
            r"(?:评估|分析|检查).{0,12}(?:水平|能力|掌握|表现|问题)|"
            r"(?:历史|过去|上次).{0,12}(?:表现|成绩|作答)|"
            r"diagnos|assessment|mistake|error|weakness|"
            r"(?:assess|evaluate).{0,16}(?:level|skill|performance)",
            clause, re.I)
        for clause in clauses)


def simplify_initial_plan(ctx, plan, assessment_needed):
    """仅简化尚未执行的初始草稿；保留澄清，不能删除旧计划失败或成果。"""
    if (assessment_needed or plan.results or plan.action_receipts
            or any(step.status != "pending" for step in plan.steps)):
        return plan
    removed = {step.step_id: step for step in plan.steps if step.agent == "Assessment"}
    if not removed:
        return plan

    def retained_dependencies(keys):
        dependencies = []
        for key in keys:
            dependencies.extend(retained_dependencies(removed[key].depends_on)
                                if key in removed else [key])
        return list(dict.fromkeys(dependencies))

    plan.steps = [step for step in plan.steps if step.step_id not in removed]
    for step in plan.steps:
        step.depends_on = retained_dependencies(step.depends_on)
    ctx.record("plan_simplified", "Coordinator", reason="unnecessary_assessment",
               removed_task_ids=sorted(removed))
    return plan
