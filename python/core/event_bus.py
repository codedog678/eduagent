"""
事件驱动总线 -- Mesh架构的核心通信层。

所有Agent通过EventBus发布/订阅事件，实现双向异步通信。
这是Mesh架构区别于Supervisor架构的关键：没有中心调度者，
每个Agent自主决定响应哪些事件。

面试要点：
- 发布-订阅模式 vs 请求-响应模式
- 异步解耦的优势：松耦合、可扩展、容错
- 事件溯源（Event Sourcing）的基本思想
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """系统中所有事件类型的枚举定义。"""

    # 学生交互事件
    STUDENT_SUBMISSION = "student.submission"
    STUDENT_QUESTION = "student.question"
    STUDENT_MESSAGE = "student.message"

    # Assessment Agent 事件
    ASSESSMENT_COMPLETE = "assessment.complete"
    MASTERY_UPDATED = "assessment.mastery_updated"
    WEAKNESS_DETECTED = "assessment.weakness_detected"

    # Tutor Agent 事件
    TEACHING_RESPONSE = "tutor.teaching_response"

    # Curriculum Agent 事件
    REVIEW_SCHEDULED = "curriculum.review_scheduled"
    NEXT_TOPIC = "curriculum.next_topic"
    REVIEW_REMINDER = "curriculum.review_reminder"

    # Engagement Agent 事件
    ENGAGEMENT_ALERT = "engagement.alert"
    ENCOURAGEMENT = "engagement.encouragement"
    PACE_ADJUSTMENT = "engagement.pace_adjustment"


class Event(BaseModel):
    """事件数据模型。"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    source: str  # 发布事件的Agent名称
    timestamp: datetime = Field(default_factory=datetime.now)
    learner_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None  # 用于追踪事件链


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    异步事件总线，支持发布-订阅模式。

    核心设计：
    1. 每个Agent注册自己感兴趣的事件类型
    2. 发布事件时，总线将事件分发给所有订阅者
    3. 支持事件历史记录（Event Sourcing基础）
    4. 支持事件过滤和优先级（可选扩展）
    5. 支持事件日志持久化到PostgreSQL
    """

    MAX_HISTORY = 1000  # 最大历史记录数，防止内存泄漏

    def __init__(self, enable_db_logging: bool = False) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._event_history: list[Event] = []
        self._lock = asyncio.Lock()
        self._enable_db_logging = enable_db_logging

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅某类事件。"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.info("Handler subscribed to %s", event_type.value)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅。"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """
        发布事件到总线，异步通知所有订阅者。

        关键设计：使用 asyncio.gather 并发通知所有订阅者，
        而不是串行调用，提高吞吐量。
        """
        async with self._lock:
            self._event_history.append(event)
            # 限制历史记录数量，防止内存泄漏
            if len(self._event_history) > self.MAX_HISTORY:
                self._event_history = self._event_history[-self.MAX_HISTORY:]

        logger.info(
            "[EventBus] %s -> %s (learner=%s)",
            event.source,
            event.type.value,
            event.learner_id,
        )

        # 如果启用了数据库日志，异步写入EventLog表
        if self._enable_db_logging:
            await self._log_event_to_db(event)

        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            logger.debug("No handlers for event type %s", event.type.value)
            return

        tasks = [self._safe_handle(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _log_event_to_db(self, event: Event) -> None:
        """
        将事件写入EventLog表（事件溯源）。

        使用独立 session，避免 session 生命周期问题。

        Args:
            event: 要记录的事件
        """
        try:
            from models.session import async_session
            from models.database import EventLog

            async with async_session() as session:
                event_log = EventLog(
                    event_id=event.id,
                    event_type=event.type.value,
                    source=event.source,
                    learner_id=event.learner_id,
                    data=event.data,
                    correlation_id=event.correlation_id,
                    created_at=event.timestamp,
                )
                session.add(event_log)
                await session.commit()
                logger.debug("[EventBus] Event %s logged to database", event.id)
        except Exception as e:
            logger.error("[EventBus] Failed to log event to database: %s", e)
            # 不影响事件分发，继续执行

    async def _safe_handle(self, handler: EventHandler, event: Event) -> None:
        """安全执行handler，捕获异常避免影响其他订阅者。"""
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "Error in handler for event %s from %s",
                event.type.value,
                event.source,
            )

    def get_history(
        self,
        learner_id: str | None = None,
        event_type: EventType | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        """查询事件历史，支持按学习者和事件类型过滤。"""
        events = self._event_history
        if learner_id:
            events = [e for e in events if e.learner_id == learner_id]
        if event_type:
            events = [e for e in events if e.type == event_type]
        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]
        return events[-limit:]

    def clear_history(self) -> None:
        """清空事件历史（用于测试）。"""
        self._event_history.clear()

    async def get_event_history_from_db(
        self,
        learner_id: str | None = None,
        event_type: EventType | None = None,
        correlation_id: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        """
        从PostgreSQL查询事件历史。

        使用独立 session 查询。

        Args:
            learner_id: 按学习者ID过滤
            event_type: 按事件类型过滤
            limit: 返回最大数量

        Returns:
            Event列表
        """
        try:
            from models.session import async_session
            from models.database import EventLog
            from sqlalchemy import select

            async with async_session() as session:
                query = select(EventLog)
                if learner_id:
                    query = query.where(EventLog.learner_id == learner_id)
                if event_type:
                    query = query.where(EventLog.event_type == event_type.value)
                if correlation_id:
                    query = query.where(EventLog.correlation_id == correlation_id)
                query = query.order_by(EventLog.created_at.desc()).limit(limit)

                result = await session.execute(query)
                rows = result.scalars().all()

                events = []
                for row in rows:
                    event = Event(
                        id=row.event_id,
                        type=EventType(row.event_type),
                        source=row.source,
                        learner_id=row.learner_id,
                        data=row.data or {},
                        correlation_id=row.correlation_id,
                        timestamp=row.created_at,
                    )
                    events.append(event)

                events.reverse()
                logger.debug("[EventBus] Retrieved %d events from database", len(events))
                return events

        except Exception as e:
            logger.error("[EventBus] Failed to query event history from database: %s", e)
            # 降级到内存历史
            return self.get_history(learner_id, event_type, correlation_id, limit)
