"""
模板 LLM 适配器。

当没有配置任何远程 LLM 时使用，基于本地模板生成回复。
"""

import logging
import random

from llm.base import BaseLLM, LLMResponse, Message

logger = logging.getLogger(__name__)


class TemplateLLM(BaseLLM):
    """模板 LLM，基于预定义模板生成回复。"""

    FEEDBACK_TEMPLATES = [
        "你的答案是{result}。{explanation}继续加油！",
        "{result}！{explanation}建议你复习一下相关知识点。",
        "回答{result}。{explanation}多练习几次会更好。",
    ]

    ENCOURAGEMENTS = [
        "做得很好！继续保持！",
        "进步很大，坚持下去！",
        "不要灰心，每次练习都是进步！",
        "你正在正确的道路上，继续努力！",
        "错误是学习的一部分，从中吸取教训！",
    ]

    HINTS = [
        "试着从基础概念开始思考。",
        "仔细阅读题目，注意关键词。",
        "可以尝试分解问题，一步步解决。",
        "回忆一下相关的公式或规则。",
        "看看有没有类似的例题可以参考。",
    ]

    EXPLANATIONS = [
        "这个知识点的核心是理解基本概念，然后通过练习巩固。",
        "建议先复习基础部分，再尝试更难的题目。",
        "多做几道类似的题目，你会发现规律。",
    ]

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """基于模板生成回复。"""
        # 获取最后一条用户消息
        user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                user_msg = m.content
                break

        # 根据上下文选择回复策略
        content = self._generate_response(user_msg, messages)

        return LLMResponse(
            content=content,
            model="template",
            usage={"input_tokens": 0, "output_tokens": 0},
            finish_reason="stop",
        )

    def _generate_response(self, user_msg: str, messages: list[Message]) -> str:
        """根据消息上下文生成回复。"""
        msg_lower = user_msg.lower()

        # 问答类
        if any(kw in msg_lower for kw in ["什么是", "怎么理解", "解释", "为什么"]):
            explanation = random.choice(self.EXPLANATIONS)
            return f"关于你的问题：{user_msg}\n\n{explanation}"

        # 提示类
        if any(kw in msg_lower for kw in ["提示", "hint", "帮帮我", "不会"]):
            return f"这是给你的提示：{random.choice(self.HINTS)}"

        # 鼓励类
        if any(kw in msg_lower for kw in ["太难了", "不会做", "沮丧", "烦"]):
            return random.choice(self.ENCOURAGEMENTS)

        # 默认回复
        return f"收到你的消息：{user_msg}\n\n{random.choice(self.EXPLANATIONS)}"

    def runtime_info(self) -> dict:
        return {
            "provider": "template",
            "model": "template",
            "enabled": True,
        }
