"""DeepSeek Flash 配置、真实 SDK 序列化和连通性脚本的离线验证。"""

import importlib
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError, AsyncOpenAI
from pydantic import ValidationError

from config.settings import LLM_ENV_KEYS, Settings
from core.llm_service import LLMService, NativeToolCall, NativeTurn
from core.versions import config_fingerprint, public_runtime_config


TOOLS = [{"type": "function", "function": {
    "name": "get_knowledge_context", "description": "读取知识点",
    "parameters": {"type": "object", "properties": {}},
}}]


@pytest.fixture(autouse=True)
def isolated_model_env(monkeypatch):
    for key in (*LLM_ENV_KEYS, "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
                "DEEPSEEK_THINKING", "DEEPSEEK_REASONING_EFFORT"):
        monkeypatch.delenv(key, raising=False)


def test_explicit_deepseek_selection_overrides_other_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stale-test-key")
    monkeypatch.setenv("LLM_PROVIDER", " DEEPSEEK ")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    cfg = Settings(_env_file=None, deepseek_model="deepseek-v4-pro")
    assert cfg.configured_llm_provider == "deepseek"
    assert cfg.configured_llm_model == "deepseek-v4-pro"
    assert cfg.llm_enabled and cfg.llm_config_source == "env"
    assert "test-only" not in repr(cfg) and "stale-test-key" not in repr(cfg)


def test_missing_explicit_key_does_not_fall_back():
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY is required") as error:
        Settings(_env_file=None, llm_provider="deepseek", openai_api_key="stale-test-key")
    assert "stale-test-key" not in str(error.value)


@pytest.mark.parametrize("kwargs,provider", [
    ({}, "template"),
    ({"deepseek_api_key": "test-only"}, "deepseek"),
    ({"openai_api_key": "old", "deepseek_api_key": "test-only"}, "openai"),
    ({"llm_provider": "template", "deepseek_api_key": "test-only"}, "template"),
])
def test_auto_priority_and_forced_template(kwargs, provider):
    assert Settings(_env_file=None, **kwargs).configured_llm_provider == provider


@pytest.mark.parametrize("kwargs", [
    {"llm_provider": "unknown"},
    {"deepseek_reasoning_effort": "low"},
    {"deepseek_thinking": "auto"},
])
def test_invalid_model_configuration_rejected(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


@pytest.mark.asyncio
async def test_main_and_legacy_factory_use_same_deepseek_config(monkeypatch):
    config_module = importlib.import_module("config.settings")
    import core.llm_service as service_module
    from llm.factory import get_llm
    import llm.factory as legacy_module

    cfg = Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="test-only",
                   deepseek_model="deepseek-flash", deepseek_thinking="enabled",
                   deepseek_reasoning_effort="max")
    monkeypatch.setattr(config_module, "settings", cfg)
    monkeypatch.setattr(legacy_module, "settings", cfg)
    monkeypatch.setattr(service_module, "_llm_service", None)
    service = service_module.get_llm_service()
    try:
        assert service.provider == "deepseek" and service.model == cfg.deepseek_model
        assert str(service._client.base_url).rstrip("/") == cfg.deepseek_base_url
        assert service._client.max_retries == 0
        assert service._client.timeout == cfg.llm_timeout_seconds
        assert service.thinking == "enabled" and service.reasoning_effort == "max"
        legacy = get_llm()
        assert legacy.runtime_info()["provider"] == "deepseek"
        assert legacy.base_url == service.base_url
        assert legacy.model == service.model
        assert legacy.reasoning_effort == service.reasoning_effort
        assert legacy.thinking == service.thinking
        assert "test-only" not in json.dumps(service.runtime_info())
    finally:
        await service._client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("thinking", ["disabled", "enabled"])
async def test_deepseek_sdk_request_body_and_visible_response(monkeypatch, thinking):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "deepseek-flash",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": " 看时间线索。 ",
                                     "reasoning_content": "private-reasoning"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50,
                      "prompt_cache_hit_tokens": 8, "prompt_cache_miss_tokens": 12},
        })
    async with AsyncOpenAI(
        api_key="test-only", base_url="https://deepseek.test", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as client:
        service = LLMService(provider="deepseek", api_key="test-only", thinking=thinking)
        service._client = client
        # 确定注入 MockTransport 后，允许 generate 走真实 SDK 序列化。
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        turn = await service.tool_turn([{"role": "user", "content": "怎么判断？"}], TOOLS, 800)
        reply = await service.generate("怎么判断？", system_prompt="导师", max_tokens=800)
    assert turn.reasoning_content == ("private-reasoning" if thinking == "enabled" else None)
    assert "private-reasoning" not in turn.model_dump_json()
    assert "private-reasoning" not in repr(turn)
    assert reply.content == "看时间线索。"
    assert "private-reasoning" not in reply.model_dump_json()
    assert turn.usage == {"input_tokens": 20, "output_tokens": 30,
                          "prompt_cache_hit_tokens": 8, "prompt_cache_miss_tokens": 12}
    for request in requests:
        assert request.url.path == "/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-flash"
        assert body["thinking"] == {"type": thinking}
        if thinking == "enabled":
            assert body["reasoning_effort"] == "high" and "temperature" not in body
        else:
            assert "temperature" in body and "reasoning_effort" not in body
        assert body["max_tokens"] == 800
    assert json.loads(requests[0].content)["tool_choice"] == "auto"
    assert json.loads(requests[0].content)["tools"] == TOOLS


@pytest.mark.asyncio
@pytest.mark.parametrize("thinking", ["disabled", "enabled"])
async def test_legacy_adapter_sends_same_thinking_options_without_raw_reasoning(monkeypatch, thinking):
    from llm.base import Message
    from llm.deepseek_adapter import DeepSeekLLM

    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "model": "deepseek-flash",
            "choices": [{"finish_reason": "stop", "message": {
                "content": "公开回答", "reasoning_content": "private-reasoning"}}],
        })
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(respond), **kwargs))
    adapter = DeepSeekLLM(api_key="test-only", thinking=thinking, reasoning_effort="max")
    reply = await adapter.chat([Message(role="user", content="解释")])
    assert reply.content == "公开回答" and reply.raw_response is None
    assert "private-reasoning" not in reply.model_dump_json()
    assert requests[0]["model"] == "deepseek-flash"
    assert requests[0]["thinking"] == {"type": thinking}
    if thinking == "enabled":
        assert requests[0]["reasoning_effort"] == "max" and "temperature" not in requests[0]
    else:
        assert "reasoning_effort" not in requests[0] and requests[0]["temperature"] == 0.7


@pytest.mark.asyncio
async def test_deepseek_api_error_is_not_a_successful_native_turn():
    count = 0
    def respond(request):
        nonlocal count
        count += 1
        return httpx.Response(429, json={"error": {"message": "test-rate-limit"}})
    async with AsyncOpenAI(
        api_key="test-only", base_url="https://deepseek.test", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as client:
        service = LLMService(provider="deepseek", api_key="test-only")
        service._client = client
        with pytest.raises(APIStatusError):
            await service.tool_turn([{"role": "user", "content": "讲解"}], TOOLS, 800)
    assert count == 1


def test_effective_thinking_options_are_part_of_public_config_fingerprint():
    disabled = Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="test-only")
    enabled = disabled.model_copy(update={"deepseek_thinking": "enabled"})
    maximum = enabled.model_copy(update={"deepseek_reasoning_effort": "max"})
    other_key = disabled.model_copy(update={"deepseek_api_key": "another-test-key"})
    assert config_fingerprint(disabled) != config_fingerprint(enabled)
    assert config_fingerprint(enabled) != config_fingerprint(maximum)
    assert config_fingerprint(disabled) == config_fingerprint(other_key)
    assert config_fingerprint(disabled) == config_fingerprint(
        disabled.model_copy(update={"deepseek_reasoning_effort": "max"}))
    public = json.dumps(public_runtime_config(disabled))
    assert "test-only" not in public and "api.deepseek.com" not in public


@pytest.mark.asyncio
async def test_config_diagnostic_is_offline_and_hides_credentials(monkeypatch, capsys):
    import core.llm_service as module
    from test_llm_config import main

    service = LLMService(provider="deepseek", api_key="diagnostic-test-secret")
    monkeypatch.setattr(module, "get_llm_service", lambda: service)
    assert await main() == 0
    output = capsys.readouterr().out
    assert "未发送请求" in output and "diagnostic-test-secret" not in output
    assert service._client is None


@pytest.mark.asyncio
async def test_config_diagnostic_reports_invalid_config_without_exposing_input(monkeypatch, capsys):
    import core.llm_service as module
    from test_llm_config import main

    def invalid_config():
        raise ValueError("diagnostic-test-secret")
    monkeypatch.setattr(module, "get_llm_service", invalid_config)
    assert await main() == 2
    assert "diagnostic-test-secret" not in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("turn,status", [
    (NativeTurn(content="完整回答", stop_reason="stop"), 0),
    (NativeTurn(content="截断回答", stop_reason="length"), 1),
    (NativeTurn(content="", stop_reason="stop"), 1),
    (NativeTurn(stop_reason="tool_calls", tool_calls=[
        NativeToolCall(id="c", name="get_knowledge_context", arguments="{}")]), 0),
    (NativeTurn(stop_reason="tool_calls", tool_calls=[]), 1),
    (NativeTurn(stop_reason="tool_calls", tool_calls=[
        NativeToolCall(id="c", name="unexpected_tool", arguments="{}")]), 1),
])
async def test_live_diagnostic_accepts_valid_replies_and_tools(monkeypatch, turn, status):
    import core.llm_service as module
    from test_llm_config import main

    async def tool_turn(*args, **kwargs):
        return turn
    service = SimpleNamespace(
        runtime_info=lambda: {"llm_enabled": True, "provider": "deepseek"},
        tool_turn=tool_turn,
    )
    monkeypatch.setattr(module, "get_llm_service", lambda: service)
    assert await main(live=True) == status
