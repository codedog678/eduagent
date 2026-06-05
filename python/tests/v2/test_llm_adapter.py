"""测试 LLM 适配层。"""

import pytest
from llm.base import BaseLLM, LLMResponse, Message


def test_message_creation():
    """测试消息创建。"""
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_llm_response_creation():
    """测试 LLM 响应创建。"""
    response = LLMResponse(
        content="Test response",
        model="test-model",
        usage={"input_tokens": 10, "output_tokens": 20},
    )
    assert response.content == "Test response"
    assert response.model == "test-model"
    assert response.usage["input_tokens"] == 10


def test_template_llm():
    """测试模板 LLM。"""
    from llm.template_adapter import TemplateLLM

    llm = TemplateLLM()
    info = llm.runtime_info()
    assert info["provider"] == "template"
    assert info["enabled"] is True


@pytest.mark.asyncio
async def test_template_llm_chat():
    """测试模板 LLM 对话。"""
    from llm.template_adapter import TemplateLLM

    llm = TemplateLLM()
    messages = [Message(role="user", content="什么是英语？")]
    response = await llm.chat(messages)
    assert response.content
    assert response.model == "template"
