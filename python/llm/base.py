"""
LLM 抽象基类。

所有 LLM 提供者必须继承 BaseLLM 并实现 chat 方法。
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """对话消息。"""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResponse(BaseModel):
    """LLM 响应。"""

    content: str
    model: str = ""
    usage: dict = Field(default_factory=dict)
    finish_reason: str = ""
    raw_response: Optional[dict] = None


class BaseLLM(ABC):
    """LLM 抽象基类，所有提供者必须实现。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """
        发送对话请求。

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 提供者特定参数

        Returns:
            LLMResponse
        """
        ...

    @abstractmethod
    def runtime_info(self) -> dict:
        """
        返回运行时信息，用于健康检查和日志。

        Returns:
            dict: {provider, model, enabled}
        """
        ...

    async def health_check(self) -> bool:
        """
        健康检查，默认实现返回 True。
        子类可覆写以执行实际检查。
        """
        return True
