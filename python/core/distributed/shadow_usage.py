"""Aggregate only numeric counters; never expose provider bodies or event data."""
from decimal import Decimal, InvalidOperation


def summarize_shadow_usage(ctx):
    events = []
    for step in ctx.steps:
        if step["kind"] == "expert_usage_charged":
            # 内联专家已被 envelope 累计计费，去掉对应本地事件以免重复。
            observed = step.get("observed_model_calls", 0)
            for _ in range(min(observed, len(events))):
                events.pop()
            events.append((step.get("model_calls", 0), step))
        elif step["kind"] in {"model_usage", "after_model"}:
            usage = step.get("usage", {})
            events.append((1, usage if isinstance(usage, dict) else {}))
    covered = sum(calls for calls, _ in events)
    result = {"model_calls": ctx.model_calls, "tool_calls": ctx.tool_calls}
    decisions = [step for step in ctx.steps if step["kind"] == "structured_decision"]
    expert = [step for step in ctx.steps if step["kind"] == "expert_usage_charged"]
    structure_known = all(step.get("structured_decision_count") is not None
                          and step.get("unknown_decision_count") is not None for step in expert)
    result["structured_decision_count"] = (
        len(decisions) + sum(step["structured_decision_count"] for step in expert)
        if structure_known else None
    )
    result["unknown_decision_count"] = (
        sum(not step["valid"] for step in decisions) + sum(step["unknown_decision_count"] for step in expert)
        if structure_known else None
    )
    result["structured_result"] = (
        "unavailable" if not structure_known else
        "unknown" if result["unknown_decision_count"] else
        "valid" if result["structured_decision_count"] else "not_applicable"
    )
    for field, alias in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
        values = [usage.get(field, usage.get(alias)) for calls, usage in events if calls]
        result[field] = (
            sum(values) if covered == ctx.model_calls
            and all(type(value) is int and value >= 0 for value in values) else None
        )
    costs = []
    try:
        for calls, usage in events:
            if usage.get("uncertain"):
                raise ValueError("uncertain cost")
            if calls:
                cost = Decimal(str(usage.get("estimated_cost_usd", usage.get("cost"))))
                if not cost.is_finite() or cost < 0:
                    raise ValueError("unknown cost")
                costs.append(cost)
        result["cost"] = (
            str(sum(costs, Decimal(0))) if costs and covered == ctx.model_calls else None
        )
    except (ValueError, InvalidOperation):
        result["cost"] = None
    return result


def combine_usage(summaries):
    """Sum all retry attempts; incomplete attempts keep totals unknown."""
    complete = bool(summaries) and all(isinstance(value, dict) for value in summaries)
    summaries = [value for value in summaries if isinstance(value, dict)]
    result = {}
    for field in ("input_tokens", "output_tokens", "model_calls", "tool_calls",
                  "structured_decision_count", "unknown_decision_count"):
        values = [value.get(field) for value in summaries]
        result[field] = (sum(values) if complete and all(type(value) is int and value >= 0 for value in values)
                         else None)
    values = [value.get("cost") for value in summaries]
    try:
        costs = [Decimal(str(value)) for value in values]
        result["cost"] = (
            sum(costs, Decimal(0)) if complete and all(value.is_finite() and value >= 0 for value in costs)
            else None
        )
    except (ValueError, InvalidOperation):
        result["cost"] = None
    result["structured_result"] = (
        "unavailable" if result["structured_decision_count"] is None else
        "unknown" if result["unknown_decision_count"] else
        "valid" if result["structured_decision_count"] else "not_applicable"
    )
    return result
