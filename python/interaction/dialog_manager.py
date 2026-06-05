"""
对话管理器。

管理多轮对话状态和上下文。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DialogTurn(BaseModel):
    """对话轮次。"""

    turn_id: int
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DialogSession(BaseModel):
    """对话会话。"""

    session_id: str
    learner_id: str
    turns: list[DialogTurn] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)

    def add_turn(self, role: str, content: str, metadata: Optional[dict] = None) -> DialogTurn:
        """添加对话轮次。"""
        turn = DialogTurn(
            turn_id=len(self.turns) + 1,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.turns.append(turn)
        self.last_active = datetime.now()
        return turn

    def get_recent_turns(self, limit: int = 10) -> list[DialogTurn]:
        """获取最近的对话轮次。"""
        return self.turns[-limit:]

    def get_context_window(self, max_tokens: int = 2000) -> list[dict]:
        """获取上下文窗口（控制 token 数量）。"""
        recent = self.get_recent_turns(20)
        context = []

        # 倒序遍历，直到达到 token 限制
        total_tokens = 0
        for turn in reversed(recent):
            # 估算 token 数量（简单实现：1个字符≈0.5个token）
            estimated_tokens = len(turn.content) * 0.5
            if total_tokens + estimated_tokens > max_tokens:
                break
            context.insert(0, {
                "role": turn.role,
                "content": turn.content,
            })
            total_tokens += estimated_tokens

        return context


class DialogManager:
    """
    对话管理器。

    职责：
    1. 管理多轮对话状态
    2. 维护对话上下文
    3. 控制上下文窗口大小
    4. 提供对话历史查询
    """

    def __init__(self, max_context_tokens: int = 2000) -> None:
        self._sessions: dict[str, DialogSession] = {}  # session_id -> session
        self._learner_sessions: dict[str, str] = {}  # learner_id -> session_id
        self.max_context_tokens = max_context_tokens

    def start_dialog(self, learner_id: str, session_id: Optional[str] = None) -> str:
        """开始新的对话。"""
        import uuid

        if session_id is None:
            session_id = str(uuid.uuid4())

        session = DialogSession(
            session_id=session_id,
            learner_id=learner_id,
        )
        self._sessions[session_id] = session
        self._learner_sessions[learner_id] = session_id

        logger.info("Started dialog session %s for learner %s", session_id, learner_id)
        return session_id

    def add_user_message(self, learner_id: str, content: str, metadata: Optional[dict] = None) -> dict:
        """添加用户消息。"""
        session = self._get_or_create_session(learner_id)
        turn = session.add_turn("user", content, metadata)
        return {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp.isoformat(),
        }

    def add_assistant_message(self, learner_id: str, content: str, metadata: Optional[dict] = None) -> dict:
        """添加助手消息。"""
        session = self._get_or_create_session(learner_id)
        turn = session.add_turn("assistant", content, metadata)
        return {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp.isoformat(),
        }

    def get_context(self, learner_id: str) -> list[dict]:
        """获取对话上下文。"""
        session = self._get_or_create_session(learner_id)
        return session.get_context_window(self.max_context_tokens)

    def get_history(self, learner_id: str, limit: int = 20) -> list[dict]:
        """获取对话历史。"""
        session = self._get_or_create_session(learner_id)
        recent = session.get_recent_turns(limit)
        return [
            {
                "turn_id": turn.turn_id,
                "role": turn.role,
                "content": turn.content,
                "timestamp": turn.timestamp.isoformat(),
            }
            for turn in recent
        ]

    def update_context(self, learner_id: str, key: str, value: Any) -> None:
        """更新对话上下文。"""
        session = self._get_or_create_session(learner_id)
        session.context[key] = value

    def get_context_value(self, learner_id: str, key: str) -> Optional[Any]:
        """获取对话上下文值。"""
        session = self._get_or_create_session(learner_id)
        return session.context.get(key)

    def end_dialog(self, learner_id: str) -> dict:
        """结束对话。"""
        session_id = self._learner_sessions.get(learner_id)
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            return {
                "session_id": session_id,
                "total_turns": len(session.turns),
                "duration": (session.last_active - session.created_at).total_seconds(),
            }
        return {"error": "No active dialog session"}

    def _get_or_create_session(self, learner_id: str) -> DialogSession:
        """获取或创建对话会话。"""
        session_id = self._learner_sessions.get(learner_id)
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        # 创建新会话
        session_id = self.start_dialog(learner_id)
        return self._sessions[session_id]
