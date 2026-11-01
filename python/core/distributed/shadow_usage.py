"""Aggregate only numeric counters; never expose provider bodies or event data."""
from decimal import Decimal, InvalidOperation


def summarize_shadow_usage(ctx):
    events = []
    for step in ctx.steps:
        if step["kind"] == "expert_usage_charged":
            events.append((step.get("model_calls", 0), step))
        elif step["kind"] in {"model_usage", "after_model"}:
            usage = step.get("usage", {})
            events.append((1, usage if isinstance(usage, dict) else {}))
    covered = sum(calls for calls, _ in events)
    result = {"model_calls": ctx.model_calls, "tool_calls": ctx.tool_calls}
    for field, alias in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
        values = [usage.get(field, usage.get(alias)) for calls, usage in events if calls]
        result[field] = (
            sum(values) if covered == ctx.model_calls
            and all(type(value) is int and value >= 0 for value in values) else None
        )
    costs = []
    try:
        for calls, usage in events:
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
