"""
上下文管理器。

管理学习会话的上下文信息。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LearningContext(BaseModel):
    """学习上下文。"""

    learner_id: str
    current_knowledge_id: str = ""
    mastery: float = 0.0
    session_start: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    recent_topics: list[str] = Field(default_factory=list)
    error_patterns: list[dict] = Field(default_factory=list)
    engagement_state: str = "neutral"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextManager:
    """
    上下文管理器。

    职责：
    1. 维护学习者当前学习上下文
    2. 提供上下文查询接口
    3. 支持上下文序列化和恢复
    """

    def __init__(self) -> None:
        self._contexts: dict[str, LearningContext] = {}  # learner_id -> context

    def get_context(self, learner_id: str) -> LearningContext:
        """获取学习上下文。"""
        if learner_id not in self._contexts:
            self._contexts[learner_id] = LearningContext(learner_id=learner_id)
        return self._contexts[learner_id]

    def update_context(self, learner_id: str, **kwargs) -> None:
        """更新学习上下文。"""
        context = self.get_context(learner_id)
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)
        context.last_activity = datetime.now()

    def set_current_topic(self, learner_id: str, knowledge_id: str) -> None:
        """设置当前学习主题。"""
        context = self.get_context(learner_id)
        context.current_knowledge_id = knowledge_id

        # 更新最近主题列表
        if knowledge_id not in context.recent_topics:
            context.recent_topics.append(knowledge_id)
            # 保持最近10个主题
            context.recent_topics = context.recent_topics[-10:]

    def update_mastery(self, learner_id: str, knowledge_id: str, mastery: float) -> None:
        """更新掌握度。"""
        context = self.get_context(learner_id)
        if context.current_knowledge_id == knowledge_id:
            context.mastery = mastery

    def add_error_pattern(self, learner_id: str, pattern: dict) -> None:
        """添加错误模式。"""
        context = self.get_context(learner_id)
        context.error_patterns.append(pattern)
        # 保持最近20个错误模式
        context.error_patterns = context.error_patterns[-20:]

    def update_engagement_state(self, learner_id: str, state: str) -> None:
        """更新参与度状态。"""
        context = self.get_context(learner_id)
        context.engagement_state = state

    def get_context_for_llm(self, learner_id: str) -> dict:
        """获取用于 LLM 的上下文。"""
        context = self.get_context(learner_id)
        return {
            "learner_id": context.learner_id,
            "current_topic": context.current_knowledge_id,
            "mastery": context.mastery,
            "recent_topics": context.recent_topics[-5:],
            "engagement_state": context.engagement_state,
            "session_duration_minutes": (datetime.now() - context.session_start).total_seconds() / 60,
        }

    def serialize(self, learner_id: str) -> dict:
        """序列化上下文。"""
        context = self.get_context(learner_id)
        return context.model_dump()

    def deserialize(self, learner_id: str, data: dict) -> None:
        """反序列化上下文。"""
        self._contexts[learner_id] = LearningContext(**data)

    def clear_context(self, learner_id: str) -> None:
        """清除上下文。"""
        if learner_id in self._contexts:
            del self._contexts[learner_id]
