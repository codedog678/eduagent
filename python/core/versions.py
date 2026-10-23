"""公开执行契约使用的版本和非敏感配置指纹。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

APP_VERSION = "0.2.0"
TRACE_SCHEMA_VERSION = 1
EVAL_SCHEMA_VERSION = 1


def public_runtime_config(settings: Any) -> dict[str, Any]:
    """只返回会影响执行行为、但不包含凭据和服务地址的配置。"""
    return {
        "enable_agent_llm_decisions": settings.enable_agent_llm_decisions,
        "enable_tutor_tools": settings.enable_tutor_tools,
        "harness_max_steps": settings.harness_max_steps,
        "harness_timeout_seconds": settings.harness_timeout_seconds,
        "llm_timeout_seconds": settings.llm_timeout_seconds,
        "quiz_ttl_seconds": settings.quiz_ttl_seconds,
        "tutor_context_budget_tokens": settings.tutor_context_budget_tokens,
        "tutor_handler_timeout_seconds": settings.tutor_handler_timeout_seconds,
        "tutor_max_model_calls": settings.tutor_max_model_calls,
        "tutor_max_output_tokens": settings.tutor_max_output_tokens,
        "tutor_max_tool_calls": settings.tutor_max_tool_calls,
    }


def config_fingerprint(settings: Any) -> str:
    encoded = json.dumps(
        public_runtime_config(settings),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runtime_metadata(settings: Any) -> dict[str, Any]:
    return {
        "app_version": APP_VERSION,
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "provider": settings.configured_llm_provider,
        "model": settings.configured_llm_model,
        "config_fingerprint": config_fingerprint(settings),
    }
