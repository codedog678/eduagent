"""
DeepSeek LLM 适配器。

DeepSeek 使用 OpenAI 兼容 API。
"""

from llm.openai_adapter import OpenAILLM


class DeepSeekLLM(OpenAILLM):
    """DeepSeek API 适配器，继承 OpenAI 兼容接口。"""

    def __init__(self, api_key: str, model: str = "deepseek-chat") -> None:
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
        )

    def runtime_info(self) -> dict:
        return {
            "provider": "deepseek",
            "model": self.model,
            "enabled": bool(self.api_key),
        }
