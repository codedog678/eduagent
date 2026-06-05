"""
LLM 统一接口层。

提供 BaseLLM 抽象基类和 get_llm 工厂函数。
所有 LLM 提供者必须继承 BaseLLM 并实现 chat 方法。
"""

from llm.base import BaseLLM, LLMResponse, Message
from llm.factory import get_llm

__all__ = ["BaseLLM", "LLMResponse", "Message", "get_llm"]
