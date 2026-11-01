from types import SimpleNamespace

import pytest

from core.distributed.shadow_repository import redacted_summary
from core.distributed.shadow_usage import summarize_shadow_usage


def summarize(steps, model_calls=3, tool_calls=2):
    return summarize_shadow_usage(SimpleNamespace(
        steps=steps, model_calls=model_calls, tool_calls=tool_calls,
    ))


def test_shadow_usage_consumes_real_kinds_once_and_strips_event_bodies():
    result = summarize([
        {"kind": "model_usage", "usage": {"prompt_tokens": 11, "completion_tokens": 5,
                                        "cost": "0.001", "response": "private"}},
        {"kind": "after_model", "usage": {"input_tokens": 13, "output_tokens": 7,
                                        "cost": "0.002"}},
        {"kind": "expert_usage_charged", "model_calls": 1,
         "input_tokens": 17, "output_tokens": 9, "estimated_cost_usd": "0.003"},
        {"kind": "budget_used", "resource": "model", "used": 3},
        {"kind": "model_turn", "usage": {"input_tokens": 999, "output_tokens": 999}},
    ])
    assert result == {
        "model_calls": 3, "tool_calls": 2,
        "input_tokens": 41, "output_tokens": 21, "cost": "0.006",
    }


@pytest.mark.parametrize("missing", ["input_tokens", "output_tokens", "cost"])
def test_shadow_usage_unknown_fields_stay_null_without_losing_known_counters(missing):
    usage = {"input_tokens": 13, "output_tokens": 7, "cost": "0.002"}
    usage.pop(missing)
    result = summarize([{"kind": "after_model", "usage": usage}], model_calls=1)
    assert result[missing] is None
    assert result["model_calls"] == 1 and result["tool_calls"] == 2
    for field in {"input_tokens", "output_tokens", "cost"} - {missing}:
        assert result[field] == usage[field]


def test_shadow_usage_no_model_calls_does_not_invent_provider_cost():
    assert summarize([], model_calls=0, tool_calls=0) == {
        "model_calls": 0, "tool_calls": 0,
        "input_tokens": 0, "output_tokens": 0, "cost": None,
    }


def test_shadow_usage_uncovered_model_attempt_keeps_counts_but_unknown_tokens():
    result = summarize([{"kind": "model_usage", "usage": {
        "input_tokens": 11, "output_tokens": 5, "cost": "0.001",
    }}], model_calls=2)
    assert result == {
        "model_calls": 2, "tool_calls": 2,
        "input_tokens": None, "output_tokens": None, "cost": None,
    }


@pytest.mark.parametrize("raw", [True, -1, "private", "NaN", "Infinity", {}, []])
def test_shadow_durable_summary_rejects_non_numeric_or_unsafe_values(raw):
    result = redacted_summary({
        **dict.fromkeys(("cost", "latency_seconds", "input_tokens", "output_tokens"), raw),
        "model_calls": 3, "tool_calls": 2, "response": "private",
        "structured_result": "valid", "permission_outcome": "private",
    }, status="completed")
    assert all(result[field] is None for field in (
        "cost", "latency_seconds", "input_tokens", "output_tokens",
    ))
    assert result["model_calls"] == 3 and result["tool_calls"] == 2
    assert result["structured_result"] == "unavailable"
    assert result["permission_outcome"] == "isolated"
    assert "response" not in result
