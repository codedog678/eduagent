"""
主动引导模块。

根据学习者状态主动推送学习建议和提醒。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProactiveMessage(BaseModel):
    """主动推送消息。"""

    message_id: str
    learner_id: str
    message_type: str  # "review_reminder" | "encouragement" | "suggestion" | "alert"
    content: str
    priority: str = "normal"  # "low" | "normal" | "high" | "urgent"
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False


class ProactiveGuide:
    """
    主动引导模块。

    职责：
    1. 生成复习提醒
    2. 发送鼓励消息
    3. 提供学习建议
    4. 检测异常并报警
    """

    def __init__(self) -> None:
        self._messages: dict[str, list[ProactiveMessage]] = {}  # learner_id -> messages
        self._last_reminder: dict[str, datetime] = {}  # learner_id -> last reminder time

    def create_review_reminder(
        self,
        learner_id: str,
        knowledge_id: str,
        days_overdue: int = 0,
    ) -> ProactiveMessage:
        """创建复习提醒。"""
        if days_overdue > 0:
            content = f"你已经 {days_overdue} 天没有复习 {knowledge_id} 了，建议现在复习一下。"
            priority = "high" if days_overdue > 3 else "normal"
        else:
            content = f"是时候复习 {knowledge_id} 了。"
            priority = "normal"

        message = ProactiveMessage(
            message_id=f"review_{learner_id}_{knowledge_id}_{datetime.now().timestamp()}",
            learner_id=learner_id,
            message_type="review_reminder",
            content=content,
            priority=priority,
            metadata={"knowledge_id": knowledge_id, "days_overdue": days_overdue},
        )

        self._add_message(learner_id, message)
        return message

    def create_encouragement(
        self,
        learner_id: str,
        reason: str = "",
        streak: int = 0,
    ) -> ProactiveMessage:
        """创建鼓励消息。"""
        if streak > 0:
            content = f"太棒了！你已经连续答对 {streak} 题了，继续保持！"
        elif reason:
            content = f"做得很好！{reason}"
        else:
            content = "你正在进步，继续努力！"

        message = ProactiveMessage(
            message_id=f"encourage_{learner_id}_{datetime.now().timestamp()}",
            learner_id=learner_id,
            message_type="encouragement",
            content=content,
            priority="low",
            metadata={"reason": reason, "streak": streak},
        )

        self._add_message(learner_id, message)
        return message

    def create_suggestion(
        self,
        learner_id: str,
        suggestion: str,
        context: Optional[dict] = None,
    ) -> ProactiveMessage:
        """创建学习建议。"""
        message = ProactiveMessage(
            message_id=f"suggest_{learner_id}_{datetime.now().timestamp()}",
            learner_id=learner_id,
            message_type="suggestion",
            content=suggestion,
            priority="normal",
            metadata=context or {},
        )

        self._add_message(learner_id, message)
        return message

    def create_alert(
        self,
        learner_id: str,
        alert_type: str,
        content: str,
    ) -> ProactiveMessage:
        """创建报警消息。"""
        message = ProactiveMessage(
            message_id=f"alert_{learner_id}_{datetime.now().timestamp()}",
            learner_id=learner_id,
            message_type="alert",
            content=content,
            priority="high",
            metadata={"alert_type": alert_type},
        )

        self._add_message(learner_id, message)
        return message

    def get_unread_messages(self, learner_id: str) -> list[dict]:
        """获取未读消息。"""
        messages = self._messages.get(learner_id, [])
        unread = [m for m in messages if not m.is_read]
        return [
            {
                "message_id": m.message_id,
                "message_type": m.message_type,
                "content": m.content,
                "priority": m.priority,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata,
            }
            for m in unread
        ]

    def mark_as_read(self, learner_id: str, message_id: str) -> bool:
        """标记消息为已读。"""
        messages = self._messages.get(learner_id, [])
        for m in messages:
            if m.message_id == message_id:
                m.is_read = True
                return True
        return False

    def should_send_reminder(self, learner_id: str, min_interval_minutes: int = 30) -> bool:
        """检查是否应该发送提醒。"""
        last_time = self._last_reminder.get(learner_id)
        if last_time is None:
            return True

        elapsed = (datetime.now() - last_time).total_seconds() / 60
        return elapsed >= min_interval_minutes

    def _add_message(self, learner_id: str, message: ProactiveMessage) -> None:
        """添加消息。"""
        if learner_id not in self._messages:
            self._messages[learner_id] = []
        self._messages[learner_id].append(message)

        # 更新最后提醒时间
        if message.message_type == "review_reminder":
            self._last_reminder[learner_id] = datetime.now()

        logger.info(
            "[ProactiveGuide] Created %s message for learner %s",
            message.message_type,
            learner_id,
        )
