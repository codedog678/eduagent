"""
Session Service。

封装会话相关的业务逻辑。
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from core.event_bus import Event, EventType

logger = logging.getLogger(__name__)


class LearningSession:
    """学习会话。"""

    def __init__(self, session_id: str, learner_id: str) -> None:
        self.session_id = session_id
        self.learner_id = learner_id
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.events: list[Event] = []
        self.interactions: list[dict] = []

    def add_event(self, event: Event) -> None:
        """添加事件。"""
        self.events.append(event)

    def add_interaction(self, interaction: dict) -> None:
        """添加交互记录。"""
        self.interactions.append(interaction)

    def end(self) -> dict:
        """结束会话。"""
        self.end_time = datetime.now()
        return self.get_summary()

    def get_summary(self) -> dict:
        """获取会话摘要。"""
        duration = (self.end_time or datetime.now()) - self.start_time
        return {
            "session_id": self.session_id,
            "learner_id": self.learner_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration.total_seconds(),
            "total_events": len(self.events),
            "total_interactions": len(self.interactions),
        }


class SessionService:
    """会话业务逻辑层。"""

    def __init__(self) -> None:
        self._sessions: dict[str, LearningSession] = {}  # session_id -> session
        self._learner_sessions: dict[str, str] = {}  # learner_id -> session_id

    def start_session(self, learner_id: str) -> dict:
        """开始新的学习会话。"""
        # 如果已有活跃会话，先结束
        if learner_id in self._learner_sessions:
            old_session_id = self._learner_sessions[learner_id]
            if old_session_id in self._sessions:
                self._sessions[old_session_id].end()

        # 创建新会话
        session_id = str(uuid4())
        session = LearningSession(session_id, learner_id)
        self._sessions[session_id] = session
        self._learner_sessions[learner_id] = session_id

        logger.info("Started session %s for learner %s", session_id, learner_id)

        return {
            "session_id": session_id,
            "start_time": session.start_time.isoformat(),
        }

    def end_session(self, learner_id: str) -> dict:
        """结束学习会话。"""
        session_id = self._learner_sessions.get(learner_id)
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            summary = session.end()

            # 清理
            del self._learner_sessions[learner_id]
            # 保留 session 数据一段时间，以便查询

            logger.info("Ended session %s for learner %s", session_id, learner_id)
            return summary

        return {"error": "No active session found"}

    def get_active_session(self, learner_id: str) -> Optional[LearningSession]:
        """获取活跃会话。"""
        session_id = self._learner_sessions.get(learner_id)
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return None

    def add_event(self, learner_id: str, event: Event) -> None:
        """向活跃会话添加事件。"""
        session = self.get_active_session(learner_id)
        if session:
            session.add_event(event)

    def add_interaction(self, learner_id: str, interaction: dict) -> None:
        """向活跃会话添加交互记录。"""
        session = self.get_active_session(learner_id)
        if session:
            session.add_interaction(interaction)

    def get_session_history(self, learner_id: str, limit: int = 10) -> list[dict]:
        """获取会话历史。"""
        # 简单实现：返回最近的会话摘要
        sessions = [
            s for s in self._sessions.values()
            if s.learner_id == learner_id
        ]
        sessions.sort(key=lambda s: s.start_time, reverse=True)

        return [s.get_summary() for s in sessions[:limit]]
