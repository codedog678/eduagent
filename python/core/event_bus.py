"""同进程发布订阅：每轮独立优先级队列，handler 顺序执行，失败中止。"""

import asyncio
import logging
import uuid
import heapq
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from pydantic import BaseModel, Field
from core.run_context import RunExhausted, active_run

logger = logging.getLogger(__name__)


class EventPriority(int, Enum):
    """事件优先级。"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3  #预留


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
    HINT_PROVIDED = "tutor.hint_provided"
    SOCRATIC_QUESTION = "tutor.socratic_question"

    # Curriculum Agent 事件
    REVIEW_SCHEDULED = "curriculum.review_scheduled"
    NEXT_TOPIC = "curriculum.next_topic"
    REVIEW_REMINDER = "curriculum.review_reminder"
    LEARNING_PATH_UPDATE = "curriculum.learning_path_update"

    # Engagement Agent 事件
    ENGAGEMENT_ALERT = "engagement.alert"
    ENCOURAGEMENT = "engagement.encouragement"
    PACE_ADJUSTMENT = "engagement.pace_adjustment"
    EMOTION_DETECTED = "engagement.emotion_detected"

    # Feedback Agent 事件
    FEEDBACK_GENERATED = "feedback.generated"

    # Session 事件
    SESSION_START = "session.start"
    SESSION_END = "session.end"


class Event(BaseModel):
    """事件数据模型。"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType  # 事件类型，必须是EventType枚举中的值
    source: str  # 发布事件的Agent名称
    timestamp: datetime = Field(default_factory=datetime.now)  # 发布时间
    learner_id: str
    data: dict[str, Any] = Field(default_factory=dict)   # 事件数据
    correlation_id: str | None = None  # 用于追踪事件链ID
    parent_event_id: str | None = None
    priority: EventPriority = EventPriority.NORMAL  # 事件优先级
# 一次答题可能触发 6-8 个事件，这些事件的 correlation_id 都相同。事后可以用这个ID把整条链路捞出来

EventHandler = Callable[[Event], Coroutine[Any, Any, None]]
#类型检查工具 必须是异步函数 必须接收 Event 参数


class ExecutionError(RuntimeError):
    """事件链未完整执行，调用方必须回滚本地学习状态。"""


_active_queue: ContextVar = ContextVar("event_queue", default=None)

class EventBus:
    """
    异步事件总线，支持发布-订阅模式。

    核心设计：
    1. 每个Agent注册自己感兴趣的事件类型
    2. 发布事件时，总线将事件分发给所有订阅者
    3. 支持事件历史记录（Event Sourcing基础）
    4. 支持事件优先级分发
    5. 支持事件日志持久化到PostgreSQL
    6. 支持 correlation_id 追踪事件链
    """

    MAX_HISTORY = 1000  # 最大历史记录数，防止内存泄漏

    def __init__(self, enable_db_logging: bool = False, max_steps: int = 64,
                 handler_timeout: float = 15.0) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {}  #订阅表：哪个事件类型有哪些处理函数
        self._event_history: list[Event] = [] #内存中的事件历史（最近1000条）
        self._lock = asyncio.Lock()  # 用于异步处理锁
        self._enable_db_logging = enable_db_logging  #是否把事件持久化到 PostgreSQL
        self._correlation_chains: dict[str, list[Event]] = {}  # correlation_id -> 事件链
        self.max_steps = max_steps
        self.handler_timeout = handler_timeout

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅某类事件：Agent 在初始化时调用这个方法，告诉 EventBus自己对哪些事件感兴趣。
        有这类事件时调用 handler(event)方法 处理
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
        logger.info("Handler subscribed to %s", event_type.value)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅：Agent 在退出时调用这个方法，告诉 EventBus自己不再对这些事件感兴趣。"""
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    async def publish(self, event: Event) -> None:
        # 子事件只入队；当前 handler 退出并释放 Agent 锁后才执行。
        run = active_run.get()
        if run:
            event.correlation_id = run.run_id
            event.parent_event_id = run.parent_event_id
        active = _active_queue.get()
        if active is not None and active["bus"] is self:
            if active["count"] >= self.max_steps:
                raise ExecutionError("event step budget exceeded")
            if event.learner_id != active["learner"]:
                raise ExecutionError("cross-learner event rejected")
            event.correlation_id = active["correlation"]
            active["count"] += 1
            heapq.heappush(active["queue"], (-event.priority.value, active["count"], event))
            return
        active = {"bus": self, "queue": [], "count": 1, "learner": event.learner_id,
                  "correlation": event.correlation_id}
        heapq.heappush(active["queue"], (-event.priority.value, 1, event))
        token = _active_queue.set(active)
        try:
            while active["queue"]:
                _, _, queued = heapq.heappop(active["queue"])
                await self._dispatch(queued)
        finally:
            _active_queue.reset(token)

    async def _dispatch(self, event: Event) -> None:
        """
        发布事件到总线，异步通知所有订阅者。

        关键设计：
        1. 按订阅顺序通知所有订阅者
        2. 支持优先级分发（高优先级事件优先处理）
        3. 支持 correlation_id 追踪事件链
        """
        run = active_run.get()
        if run:
            run.record("event_dispatched", event.source, event_id=event.id,
                       event_type=event.type.value, parent_event_id=event.parent_event_id)
        # 加锁保护事件历史；handler 按订阅顺序执行。
        async with self._lock:
            self._event_history.append(event)
            # 限制历史记录数量，防止内存泄漏
            if len(self._event_history) > self.MAX_HISTORY:
                self._event_history = self._event_history[-self.MAX_HISTORY:]

            # 追踪事件链
            if event.correlation_id:
                if event.correlation_id not in self._correlation_chains:
                    self._correlation_chains[event.correlation_id] = []
                self._correlation_chains[event.correlation_id].append(event)
                if len(self._correlation_chains) > self.MAX_HISTORY:
                    del self._correlation_chains[next(iter(self._correlation_chains))]
                self._correlation_chains[event.correlation_id] = (
                    self._correlation_chains[event.correlation_id][-self.MAX_HISTORY:]
                )

        logger.info(
            "[EventBus] %s -> %s (learner=%s, priority=%s, correlation=%s)",
            event.source,
            event.type.value,
            event.learner_id,
            event.priority.name,
            event.correlation_id or "none",
        )

        # 如果启用了数据库日志，异步写入EventLog表
        if self._enable_db_logging:
            await self._log_event_to_db(event)

        # 顺序通知所有订阅者
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            logger.debug("No handlers for event type %s", event.type.value)
            return

        # 固定订阅顺序便于重现；失败立即中止，不把部分结果冒充成功。
        for handler in handlers:
            await self._safe_handle(handler, event)

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
        """按顺序执行 handler，异常中止本轮，由 Harness 回滚。"""
        run = active_run.get()
        agent = getattr(getattr(handler, "__self__", None), "name",
                        getattr(handler, "__qualname__", type(handler).__name__))
        started = asyncio.get_running_loop().time()
        if run:
            run.record("handler_started", agent, event_id=event.id)
            run.parent_event_id = event.id
        try:
            timeout = self.handler_timeout
            if run and run.conversation and agent == "TutorAgent":
                from config.settings import settings
                timeout = min(settings.tutor_handler_timeout_seconds, run.remaining())
            await asyncio.wait_for(handler(event), timeout=timeout)
            if run:
                run.record("handler_completed", agent, event_id=event.id,
                           duration_ms=round((asyncio.get_running_loop().time() - started) * 1000))
        except Exception as exc:
            logger.exception(
                "Error in handler for event %s from %s",
                event.type.value,
                event.source,
            )
            if run:
                run.record("handler_failed", agent, event_id=event.id, reason=type(exc).__name__)
            if isinstance(exc, (ExecutionError, RunExhausted, TimeoutError)):
                raise
            raise ExecutionError(f"{event.type.value}: {type(exc).__name__}") from exc
        finally:
            if run:
                run.parent_event_id = None

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
        self._correlation_chains.clear()

    def get_correlation_chain(self, correlation_id: str) -> list[Event]:
        """获取指定 correlation_id 的事件链。"""
        return self._correlation_chains.get(correlation_id, [])

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
        if not self._enable_db_logging:
            return self.get_history(learner_id, event_type, correlation_id, limit)
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
