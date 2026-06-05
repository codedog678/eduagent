"""
Tutor Service。

封装辅导相关的业务逻辑，包含苏格拉底式教学法。
"""

import logging
from typing import Optional

from core.event_bus import Event, EventType
from core.llm_service import get_llm_service
from services.learner_service import LearnerService

logger = logging.getLogger(__name__)


class TutorService:
    """辅导业务逻辑层。"""

    def __init__(self) -> None:
        self.learner_service = LearnerService()
        self._hint_usage: dict[str, int] = {}

    async def ask_question(
        self,
        learner_id: str,
        knowledge_id: str,
        question: str,
        context: Optional[dict] = None,
    ) -> dict:
        """回答学生问题。"""
        llm_service = get_llm_service()

        # 获取学习者上下文
        learner_model = await self.learner_service.get_learner_model(learner_id)
        mastery = learner_model.get_mastery(knowledge_id)

        # 构建上下文
        full_context = {
            "question": question,
            "mastery": mastery,
            "knowledge_id": knowledge_id,
        }
        if context:
            full_context.update(context)

        # 生成回答
        response = await llm_service.generate_tutor_response(
            question=question,
            context=full_context,
        )

        # 构建事件
        events = [{
            "type": EventType.TEACHING_RESPONSE.value,
            "data": {
                "question": question,
                "response": response.get("response", ""),
                "explanation": response.get("explanation", ""),
            },
        }]

        return {
            "response": response.get("response", ""),
            "explanation": response.get("explanation", ""),
            "encouragement": response.get("encouragement", ""),
            "next_steps": response.get("next_steps", []),
            "key_points": response.get("key_points", []),
            "events": events,
        }

    async def get_hint(
        self,
        learner_id: str,
        knowledge_id: str,
        question: str,
    ) -> dict:
        """获取提示。"""
        # 更新提示使用次数
        self._hint_usage[learner_id] = self._hint_usage.get(learner_id, 0) + 1

        llm_service = get_llm_service()

        # 获取学习者上下文
        learner_model = await self.learner_service.get_learner_model(learner_id)
        mastery = learner_model.get_mastery(knowledge_id)

        # 生成提示
        hint = await llm_service.generate_hint(
            question=question,
            knowledge_id=knowledge_id,
            mastery=mastery,
        )

        # 构建事件
        events = [{
            "type": EventType.HINT_PROVIDED.value,
            "data": {
                "question": question,
                "hint": hint.get("hint", ""),
                "hint_level": hint.get("hint_level", 1),
            },
        }]

        return {
            "hint": hint.get("hint", ""),
            "hint_level": hint.get("hint_level", 1),
            "events": events,
        }

    async def get_encouragement(
        self,
        learner_id: str,
        reason: str = "",
    ) -> dict:
        """获取鼓励。"""
        llm_service = get_llm_service()

        encouragement = await llm_service.generate_encouragement(reason=reason)

        events = [{
            "type": EventType.ENCOURAGEMENT.value,
            "data": {
                "reason": reason,
                "encouragement": encouragement,
            },
        }]

        return {
            "encouragement": encouragement,
            "events": events,
        }

    def get_hint_usage(self, learner_id: str) -> int:
        """获取提示使用次数。"""
        return self._hint_usage.get(learner_id, 0)
