"""
OpenAI LLM 适配器。

支持 OpenAI API 兼容的提供者（OpenAI、DeepSeek、MiniMax 等）。
"""

import logging
from typing import Optional

from llm.base import BaseLLM, LLMResponse, Message

logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    """OpenAI API 适配器。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """发送 OpenAI API 请求。"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(kwargs)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage = data.get("usage", {})

            return LLMResponse(
                content=message.get("content", ""),
                model=data.get("model", self.model),
                usage={
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                finish_reason=choice.get("finish_reason", ""),
                raw_response=data,
            )

        except Exception as e:
            logger.error("[OpenAI] Request failed: %s", e)
            raise

    def runtime_info(self) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "enabled": bool(self.api_key),
        }
