"""
Agent 基类 -- 所有Agent的公共接口和行为。

每个Agent都：
1. 有一个名称和角色描述
2. 连接到EventBus，订阅感兴趣的事件
3. 可以发布事件通知其他Agent
4. 有自己的处理逻辑（子类实现）

面试要点：
- 模板方法模式：基类定义骨架，子类实现细节
- 依赖注入：EventBus通过构造函数注入
- 单一职责原则：每个Agent只关注自己的领域
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel
from core.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 基类。

    子类需要实现：
    - subscribed_events: 返回自己订阅的事件类型列表
    - handle_event: 处理接收到的事件
    """

    def __init__(
        self,
        name: str,
        event_bus: EventBus,
        learner_models: dict[str, LearnerModel],
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self.name = name
        self.event_bus = event_bus
        self.learner_models = learner_models
        self.memory_manager = memory_manager
        self._register_handlers()
        logger.info("[%s] Agent initialized", self.name)

    def _register_handlers(self) -> None:
        """注册事件处理器到EventBus。"""
        for event_type in self.subscribed_events:
            self.event_bus.subscribe(event_type, self.handle_event)
            logger.debug("[%s] Subscribed to %s", self.name, event_type.value)

    @property
    @abstractmethod
    def subscribed_events(self) -> list[EventType]:
        """子类声明自己订阅哪些事件。"""
        ...

    @abstractmethod
    async def handle_event(self, event: Event) -> None:
        """子类实现事件处理逻辑。"""
        ...

    async def emit(
        self,
        event_type: EventType,
        learner_id: str,
        data: dict,
        correlation_id: str | None = None,
    ) -> None:
        """便捷方法：发布事件。"""
        event = Event(
            type=event_type,
            source=self.name,
            learner_id=learner_id,
            data=data,
            correlation_id=correlation_id,
        )
        await self.event_bus.publish(event)

    def get_learner_model(self, learner_id: str) -> LearnerModel:
        """获取学习者模型，不存在则创建。"""
        if learner_id not in self.learner_models:
            self.learner_models[learner_id] = LearnerModel(learner_id)
        return self.learner_models[learner_id]

    def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
        """
        获取需要保存的 Agent 状态。

        子类可以重写此方法来返回需要持久化的状态数据。

        Args:
            learner_id: 学习者ID

        Returns:
            状态字典，如果不需要保存则返回 None
        """
        return None

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        """
        从数据库加载 Agent 状态。

        子类可以重写此方法来恢复持久化的状态数据。

        Args:
            learner_id: 学习者ID
            state_data: 状态数据
        """
        pass
