"""测试 Agent 基类。"""

import pytest
from agents.base import BaseAgent, AgentState, AgentStatus
from core.event_bus import Event, EventBus, EventType


class TestAgent(BaseAgent):
    """测试用 Agent。"""

    def __init__(self, event_bus):
        super().__init__(
            name="TestAgent",
            event_bus=event_bus,
            description="测试 Agent",
        )
        self.handled_events = []

    def get_subscribed_events(self):
        return [EventType.STUDENT_SUBMISSION]

    async def handle_event(self, event):
        self.handled_events.append(event)
        return {"test": "result"}


def test_agent_creation():
    """测试 Agent 创建。"""
    bus = EventBus()
    agent = TestAgent(bus)

    assert agent.name == "TestAgent"
    assert agent.description == "测试 Agent"
    assert agent.status.state == AgentState.IDLE


def test_agent_status():
    """测试 Agent 状态。"""
    bus = EventBus()
    agent = TestAgent(bus)

    status = agent.get_status()
    assert status["name"] == "TestAgent"
    assert status["state"] == "idle"
    assert status["total_processed"] == 0


def test_agent_registration():
    """测试 Agent 注册。"""
    bus = EventBus()
    agent = TestAgent(bus)

    agent.register()
    assert EventType.STUDENT_SUBMISSION in bus._subscribers

    agent.unregister()
    assert EventType.STUDENT_SUBMISSION not in bus._subscribers


@pytest.mark.asyncio
async def test_agent_event_handling():
    """测试 Agent 事件处理。"""
    bus = EventBus()
    agent = TestAgent(bus)

    event = Event(
        type=EventType.STUDENT_SUBMISSION,
        source="test",
        learner_id="test_learner",
        data={"knowledge_id": "vocab_basic"},
    )

    await agent.handle_event(event)
    assert len(agent.handled_events) == 1
    assert agent.handled_events[0].type == EventType.STUDENT_SUBMISSION


def test_agent_subscribed_events():
    """测试 Agent 订阅的事件类型。"""
    bus = EventBus()
    agent = TestAgent(bus)

    events = agent.get_subscribed_events()
    assert EventType.STUDENT_SUBMISSION in events
