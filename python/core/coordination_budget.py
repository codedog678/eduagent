"""按剩余步骤分配父预算，保留结论、Tutor 和明确要求的备题额度。"""

import re

from config.settings import settings


def practice_required(ctx, plan):
    # 只能由原任务和学生补充确定必要性，模型生成的步骤不能升级任务。
    return bool(re.search(
        r"备题|准备.{0,12}(?:题|练习)|生成.{0,12}(?:题|练习)|"
        r"(?:安排|给我).{0,8}(?:一|两|几)[道题].{0,4}(?:题|练习)?|"
        r"(?:prepare|generate).{0,20}(?:quiz|question|exercise)",
        " ".join([ctx.input_text, plan.original_request or ""] + plan.student_inputs), re.I))


def practice_policy(ctx, plan):
    """资格来自服务端状态，选择授权只来自学生输入，不能来自模型的目标/发现。"""
    from core.tool_executor import ToolExecutor

    inputs = [plan.original_request or "", *plan.student_inputs, ctx.input_text]
    clauses = [clause for text in inputs for clause in re.split(r"[。；\n，,]", text)]
    affirmative = [clause for clause in clauses
                   if not re.search(r"不要|不得|不允许|不能|不想|don't|do not", clause, re.I)]
    locked = any(re.search(
        r"(?:只|仅).{0,8}(?:目标|当前|这个|该|时态|词汇|写作|略读)|"
        r"不要.{0,8}(?:换|切换|替换)|(?:only|keep).{0,12}(?:target|current)", clause, re.I)
        for clause in clauses)
    selection = not locked and any(re.search(
        r"最优先.{0,8}知识点|(?:先|优先)(?:练|学习|复习).{0,8}(?:基础|前置|先修)|"
        r"(?:选择|挑选).{0,8}(?:基础|前置|先修)|"
        r"(?:highest.priority|prerequisite).{0,12}(?:topic|practice|exercise)", clause, re.I)
        for clause in affirmative)
    executor = ToolExecutor(ctx)
    snapshot = executor.knowledge_context(ctx.knowledge_id)
    authorized = {ctx.knowledge_id}
    # 支持学生明确点名另一知识点，维持已有跨知识点练习/原计划收尾链路。
    if not locked and ctx.knowledge_graph:
        for key, node in ctx.knowledge_graph.nodes.items():
            if any(key in clause or node.name in clause for clause in affirmative):
                authorized.add(key)
    if selection:
        authorized.update(item["knowledge_id"] for item in snapshot["prerequisite_context"]
                          if item["practice_allowed"])
    eligible = sorted(key for key in authorized if executor.knowledge_context(key)["practice_allowed"])
    return {"required": practice_required(ctx, plan),
            "target_knowledge_id": ctx.knowledge_id,
            "allow_prerequisite_selection": selection,
            "authorized_knowledge_ids": sorted(authorized),
            "allowed_knowledge_ids": eligible}


def practice_reserve(ctx, plan):
    return int(
        not ctx.prepared_quiz and not plan.practice_quiz_id
        and practice_required(ctx, plan)
    )


def remaining_cost(ctx, plan):
    steps = [step for step in plan.steps if step.status == "pending"]
    experts = sum(step.agent != "Tutor" for step in steps)
    practice = practice_reserve(ctx, plan)
    # 专家可用一次无工具请求消费已提供的快照/上游证据；委派本身也计工具。
    return (
        experts + settings.coordinator_tutor_model_reserve + practice,
        len(steps) + settings.coordinator_tutor_tool_reserve + practice,
    )


def feasible(ctx, plan):
    ctx.remaining()
    models, tools = remaining_cost(ctx, plan)
    return (ctx.model_calls + models <= ctx.max_model_calls
            and ctx.tool_calls + tools <= ctx.max_tool_calls)


def specialist_limits(ctx, step, plan):
    remaining = [item for item in plan.steps if item.status == "pending"
                 and item.step_id != step.step_id]
    future_experts = sum(item.agent != "Tutor" for item in remaining)
    practice = practice_reserve(ctx, plan)
    # 当前委派已扣费；给后续每个专家与最终 Tutor 留下委派工具额度。
    models = ctx.max_model_calls - settings.coordinator_tutor_model_reserve - future_experts - practice
    tools = ctx.max_tool_calls - settings.coordinator_tutor_tool_reserve - len(remaining) - practice
    return (
        min(models, ctx.model_calls + settings.specialist_max_model_calls),
        min(tools, ctx.tool_calls + settings.specialist_max_tool_calls),
    )
