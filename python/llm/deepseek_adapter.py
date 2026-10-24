"""
DeepSeek LLM 适配器。

DeepSeek 使用 OpenAI 兼容 API。
"""

from llm.base import LLMResponse, Message
from llm.openai_adapter import OpenAILLM


class DeepSeekLLM(OpenAILLM):
    """DeepSeek API 适配器，继承 OpenAI 兼容接口。"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-flash",
        base_url: str = "https://api.deepseek.com",
        thinking: str = "disabled",
        reasoning_effort: str = "high",
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self.thinking = thinking
        self.reasoning_effort = reasoning_effort

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        kwargs.setdefault("thinking", {"type": self.thinking})
        if kwargs["thinking"]["type"] == "enabled":
            kwargs.setdefault("reasoning_effort", self.reasoning_effort)
            temperature = None
        response = await super().chat(messages, temperature, max_tokens, **kwargs)
        # 旧接口只提供可见回复，不暴露供应商的内部思考字段。
        return response.model_copy(update={"raw_response": None})

    def runtime_info(self) -> dict:
        return {
            "provider": "deepseek",
            "model": self.model,
            "enabled": bool(self.api_key),
        }
