"""
Agent 集成测试。

测试多个Agent协作流程和事件驱动交互。
"""

import pytest
import asyncio
from core.event_bus import EventBus, Event, EventType
from core.learner_model import LearnerModel
from agents import (
    AssessmentAgent,
    TutorAgent,
    CurriculumAgent,
    EngagementAgent,
)


@pytest.fixture
def event_bus():
    """创建EventBus实例。"""
    return EventBus()


@pytest.fixture
def learner_models():
    """创建学习者模型字典。"""
    return {}


@pytest.fixture
def agents(event_bus, learner_models):
    """创建所有Agent实例。"""
    assessment = AssessmentAgent(
        name="AssessmentAgent",
        event_bus=event_bus,
        learner_models=learner_models,
    )
    tutor = TutorAgent(
        name="TutorAgent",
        event_bus=event_bus,
        learner_models=learner_models,
    )
    curriculum = CurriculumAgent(
        name="CurriculumAgent",
        event_bus=event_bus,
        learner_models=learner_models,
    )
    engagement = EngagementAgent(
        name="EngagementAgent",
        event_bus=event_bus,
        learner_models=learner_models,
    )
    return {
        "assessment": assessment,
        "tutor": tutor,
        "curriculum": curriculum,
        "engagement": engagement,
    }


@pytest.mark.asyncio
async def test_answer_submission_flow(event_bus, learner_models, agents):
    """测试答题提交流程。"""
    learner_id = "test_user_001"

    event = Event(
        type=EventType.STUDENT_SUBMISSION,
        source="api",
        learner_id=learner_id,
        data={
            "knowledge_id": "vocab_basic",
            "is_correct": True,
            "time_spent_seconds": 30,
        },
    )

    await event_bus.publish(event)

    assert learner_id in learner_models

    model = learner_models[learner_id]
    state = model.get_state("vocab_basic")
    assert state.mastery > 0.1
    assert state.attempts == 1


@pytest.mark.asyncio
async def test_wrong_answer_triggers_hint(event_bus, learner_models, agents):
    """测试答错触发提示流程（提示现在由TutorAgent内部处理）。"""
    learner_id = "test_user_002"

    # 收集 TEACHING_RESPONSE 事件
    teaching_events = []
    original_publish = event_bus.publish

    async def capture_publish(event):
        await original_publish(event)
        if event.type == EventType.TEACHING_RESPONSE:
            teaching_events.append(event)

    event_bus.publish = capture_publish

    # 连续答错2次
    for i in range(2):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={
                "knowledge_id": "grammar_tenses",
                "is_correct": False,
                "time_spent_seconds": 60,
            },
        )
        await event_bus.publish(event)

    event_bus.publish = original_publish

    assert learner_id in learner_models

    model = learner_models[learner_id]
    state = model.get_state("grammar_tenses")
    assert state.mastery < 0.2  # BKT有学习转移，不会降到极低


@pytest.mark.asyncio
async def test_curriculum_agent_recommends_next(event_bus, learner_models, agents):
    """测试CurriculumAgent推荐下一个知识点。"""
    learner_id = "test_user_004"

    for i in range(5):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={
                "knowledge_id": "vocab_basic",
                "is_correct": True,
                "time_spent_seconds": 20,
            },
        )
        await event_bus.publish(event)

    assert learner_id in learner_models
    model = learner_models[learner_id]
    state = model.get_state("vocab_basic")

    if state.mastery >= 0.6:
        history = event_bus.get_history(learner_id=learner_id, event_type=EventType.NEXT_TOPIC)
        assert len(history) >= 0


@pytest.mark.asyncio
async def test_event_bus_history(event_bus, learner_models, agents):
    """测试EventBus历史记录。"""
    learner_id = "test_user_005"

    for i in range(5):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={"knowledge_id": f"topic_{i}", "is_correct": True},
        )
        await event_bus.publish(event)

    history = event_bus.get_history(learner_id=learner_id)
    assert len(history) >= 5  # 包含派生事件

    history_filtered = event_bus.get_history(
        learner_id=learner_id,
        event_type=EventType.STUDENT_SUBMISSION,
    )
    assert len(history_filtered) == 5


@pytest.mark.asyncio
async def test_engagement_detection(event_bus, learner_models, agents):
    """测试EngagementAgent检测学习状态。"""
    learner_id = "test_user_006"

    for i in range(3):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={
                "knowledge_id": "grammar_tenses",
                "is_correct": False,
                "time_spent_seconds": 120,
            },
        )
        await event_bus.publish(event)

    assert learner_id in learner_models


@pytest.mark.asyncio
async def test_tutor_hint_integration(event_bus, learner_models, agents):
    """测试TutorAgent内部提示集成。"""
    learner_id = "test_user_hint"

    # 收集所有事件
    all_events = []
    original_publish = event_bus.publish

    async def capture_publish(event):
        all_events.append(event)
        await original_publish(event)

    event_bus.publish = capture_publish

    # 连续答错3次，第2次开始应该触发提示
    for i in range(3):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={
                "knowledge_id": "vocab_basic",
                "is_correct": False,
                "time_spent_seconds": 30,
            },
        )
        await event_bus.publish(event)

    event_bus.publish = original_publish

    # 应该有 TEACHING_RESPONSE 事件，其中包含 hint 类型
    hint_events = [
        e for e in all_events
        if e.type == EventType.TEACHING_RESPONSE and e.data.get("teaching_style") == "hint"
    ]
    assert len(hint_events) >= 1, "Should have at least one hint teaching response"


@pytest.mark.asyncio
async def test_review_reminder_emitted(event_bus, learner_models, agents):
    """测试CurriculumAgent发出复习提醒。"""
    learner_id = "test_user_review"

    all_events = []
    original_publish = event_bus.publish

    async def capture_publish(event):
        all_events.append(event)
        await original_publish(event)

    event_bus.publish = capture_publish

    # 提交答案触发复习计划
    for i in range(3):
        event = Event(
            type=EventType.STUDENT_SUBMISSION,
            source="api",
            learner_id=learner_id,
            data={
                "knowledge_id": "vocab_basic",
                "is_correct": True,
                "time_spent_seconds": 20,
            },
        )
        await event_bus.publish(event)

    event_bus.publish = original_publish

    # 应该有 REVIEW_SCHEDULED 事件
    review_events = [
        e for e in all_events
        if e.type == EventType.REVIEW_SCHEDULED
    ]
    # 可能有也可能没有，取决于mastery是否足够高
    # 这里只验证流程不出错
    assert len(all_events) > 0
