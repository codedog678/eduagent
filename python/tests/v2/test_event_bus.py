"""测试事件总线改进。"""

import pytest
from core.event_bus import Event, EventBus, EventType, EventPriority


def test_event_priority():
    """测试事件优先级。"""
    assert EventPriority.LOW.value == 0
    assert EventPriority.NORMAL.value == 1
    assert EventPriority.HIGH.value == 2
    assert EventPriority.CRITICAL.value == 3


def test_event_creation_with_priority():
    """测试带优先级的事件创建。"""
    event = Event(
        type=EventType.STUDENT_SUBMISSION,
        source="test",
        learner_id="test_learner",
        data={"knowledge_id": "vocab_basic"},
        priority=EventPriority.HIGH,
    )
    assert event.priority == EventPriority.HIGH
    assert event.type == EventType.STUDENT_SUBMISSION


def test_event_creation_with_correlation_id():
    """测试带 correlation_id 的事件创建。"""
    event = Event(
        type=EventType.STUDENT_SUBMISSION,
        source="test",
        learner_id="test_learner",
        data={"knowledge_id": "vocab_basic"},
        correlation_id="test_correlation_123",
    )
    assert event.correlation_id == "test_correlation_123"


@pytest.mark.asyncio
async def test_event_bus_correlation_chain():
    """测试事件总线的事件链追踪。"""
    bus = EventBus()

    # 创建第一个事件
    event1 = Event(
        type=EventType.STUDENT_SUBMISSION,
        source="test",
        learner_id="test_learner",
        data={"knowledge_id": "vocab_basic"},
        correlation_id="chain_123",
    )
    await bus.publish(event1)

    # 创建第二个事件
    event2 = Event(
        type=EventType.MASTERY_UPDATED,
        source="test",
        learner_id="test_learner",
        data={"mastery": 0.6},
        correlation_id="chain_123",
    )
    await bus.publish(event2)

    # 获取事件链
    chain = bus.get_correlation_chain("chain_123")
    assert len(chain) == 2
    assert chain[0].type == EventType.STUDENT_SUBMISSION
    assert chain[1].type == EventType.MASTERY_UPDATED


def test_new_event_types():
    """测试新增的事件类型。"""
    # 测试新的事件类型存在
    assert hasattr(EventType, 'HINT_PROVIDED')
    assert hasattr(EventType, 'SOCRATIC_QUESTION')
    assert hasattr(EventType, 'LEARNING_PATH_UPDATE')
    assert hasattr(EventType, 'EMOTION_DETECTED')
    assert hasattr(EventType, 'FEEDBACK_GENERATED')
    assert hasattr(EventType, 'SESSION_START')
    assert hasattr(EventType, 'SESSION_END')
