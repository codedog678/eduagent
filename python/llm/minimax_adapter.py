"""
MiniMax LLM 适配器。

MiniMax 使用 OpenAI 兼容 API。
"""

from llm.openai_adapter import OpenAILLM


class MiniMaxLLM(OpenAILLM):
    """MiniMax API 适配器，继承 OpenAI 兼容接口。"""

    def __init__(self, api_key: str, model: str = "MiniMax-M2.7") -> None:
        super().__init__(
            api_key=api_key,
            base_url="https://api.minimax.chat/v1",
            model=model,
        )

    def runtime_info(self) -> dict:
        return {
            "provider": "minimax",
            "model": self.model,
            "enabled": bool(self.api_key),
        }
