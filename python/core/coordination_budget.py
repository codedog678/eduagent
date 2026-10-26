"""按剩余步骤分配父预算，保留结论、Tutor 和明确要求的备题额度。"""

import re

from config.settings import settings


def practice_reserve(ctx, plan):
    return int(
        not ctx.prepared_quiz and not plan.practice_quiz_id
        and bool(re.search(
            r"备题|准备.{0,12}(?:题|练习)|生成.{0,12}(?:题|练习)|"
            r"(?:prepare|generate).{0,20}(?:quiz|question|exercise)",
            " ".join([ctx.input_text, plan.goal] + [
                step.objective for step in plan.steps if step.status == "pending"
            ]), re.I))
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
