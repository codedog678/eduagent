"""
Agent 基类。

所有 Agent 必须继承 BaseAgent 并实现抽象方法。
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent 状态。"""

    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"


class AgentStatus(BaseModel):
    """Agent 状态信息。"""

    state: AgentState = AgentState.IDLE
    last_active: Optional[datetime] = None
    total_processed: int = 0
    total_errors: int = 0
    current_task: str = ""


class BaseAgent(ABC):
    """
    Agent 抽象基类。

    所有 Agent 必须：
    1. 继承 BaseAgent
    2. 实现 handle_event 方法
    3. 实现 get_subscribed_events 方法
    4. 调用 register() 注册到 EventBus
    """

    def __init__(
        self,
        name: str,
        event_bus: EventBus,
        description: str = "",
        learner_models: dict[str, LearnerModel] | None = None,
    ) -> None:
        self.name = name
        self.event_bus = event_bus
        self.description = description
        self.learner_models = learner_models if learner_models is not None else {}
        self.status = AgentStatus()
        self._lock = None  # 延迟初始化

    @abstractmethod
    async def handle_event(self, event: Event) -> Optional[dict[str, Any]]:
        """
        处理事件。

        Args:
            event: 要处理的事件

        Returns:
            处理结果（可选）
        """
        ...

    @abstractmethod
    def get_subscribed_events(self) -> list[EventType]:
        """
        获取订阅的事件类型列表。

        Returns:
            事件类型列表
        """
        ...

    def register(self) -> None:
        """注册到事件总线。"""
        for event_type in self.get_subscribed_events():
            self.event_bus.subscribe(event_type, self._safe_handle)
        logger.info(
            "[%s] Registered to EventBus, subscribed to %d event types",
            self.name,
            len(self.get_subscribed_events()),
        )

    def unregister(self) -> None:
        """从事件总线取消注册。"""
        for event_type in self.get_subscribed_events():
            self.event_bus.unsubscribe(event_type, self._safe_handle)
        logger.info("[%s] Unregistered from EventBus", self.name)

    async def _safe_handle(self, event: Event) -> None:
        """安全执行事件处理。"""
        import asyncio

        # 如果没有锁，创建一个
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            self.status.state = AgentState.PROCESSING
            self.status.last_active = datetime.now()
            self.status.current_task = f"Processing {event.type.value}"

            try:
                result = await self.handle_event(event)
                self.status.total_processed += 1

                # 发布结果事件（如果有）
                if result and "events" in result:
                    for event_data in result["events"]:
                        await self._publish_result_event(
                            event_type=EventType(event_data["type"]),
                            learner_id=event.learner_id,
                            data=event_data.get("data", {}),
                            correlation_id=event.correlation_id,
                        )

            except Exception as e:
                self.status.total_errors += 1
                self.status.state = AgentState.ERROR
                logger.exception("[%s] Error handling event: %s", self.name, e)
                raise

            finally:
                self.status.state = AgentState.IDLE
                self.status.current_task = ""

    async def _publish_result_event(
        self,
        event_type: EventType,
        learner_id: str,
        data: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        """发布结果事件。"""
        event = Event(
            type=event_type,
            source=self.name,
            learner_id=learner_id,
            data=data,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)

    async def emit(
        self,
        event_type: EventType,
        learner_id: str,
        data: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        """兼容旧 Agent 基类的便捷发布接口。"""
        await self._publish_result_event(event_type, learner_id, data, correlation_id)

    def get_learner_model(self, learner_id: str) -> LearnerModel:
        """获取学习者模型，不存在则创建。"""
        if learner_id not in self.learner_models:
            self.learner_models[learner_id] = LearnerModel(learner_id)
        return self.learner_models[learner_id]

    def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
        """获取需要持久化的 Agent 状态。子类可重写。"""
        return None

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        """恢复持久化的 Agent 状态。子类可重写。"""
        pass

    def get_status(self) -> dict:
        """获取 Agent 状态。"""
        return {
            "name": self.name,
            "description": self.description,
            "state": self.status.state.value,
            "last_active": self.status.last_active.isoformat() if self.status.last_active else None,
            "total_processed": self.status.total_processed,
            "total_errors": self.status.total_errors,
            "current_task": self.status.current_task,
            "subscribed_events": [e.value for e in self.get_subscribed_events()],
        }
