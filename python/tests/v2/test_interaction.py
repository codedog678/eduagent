"""测试外部交互模块。"""

import pytest
from interaction.dialog_manager import DialogManager
from interaction.proactive_guide import ProactiveGuide
from interaction.context_manager import ContextManager


def test_dialog_manager_creation():
    """测试对话管理器创建。"""
    manager = DialogManager()
    assert manager.max_context_tokens == 2000


def test_dialog_manager_start_dialog():
    """测试开始对话。"""
    manager = DialogManager()
    session_id = manager.start_dialog("test_learner")
    assert session_id


def test_dialog_manager_add_messages():
    """测试添加消息。"""
    manager = DialogManager()
    manager.start_dialog("test_learner")

    user_result = manager.add_user_message("test_learner", "Hello")
    assert user_result["turn_id"] == 1

    assistant_result = manager.add_assistant_message("test_learner", "Hi there!")
    assert assistant_result["turn_id"] == 2


def test_dialog_manager_get_context():
    """测试获取上下文。"""
    manager = DialogManager()
    manager.start_dialog("test_learner")

    manager.add_user_message("test_learner", "What is English?")
    manager.add_assistant_message("test_learner", "English is a language.")

    context = manager.get_context("test_learner")
    assert len(context) == 2
    assert context[0]["role"] == "user"
    assert context[1]["role"] == "assistant"


def test_dialog_manager_get_history():
    """测试获取历史。"""
    manager = DialogManager()
    manager.start_dialog("test_learner")

    manager.add_user_message("test_learner", "Message 1")
    manager.add_user_message("test_learner", "Message 2")

    history = manager.get_history("test_learner")
    assert len(history) == 2


def test_proactive_guide_creation():
    """测试主动引导创建。"""
    guide = ProactiveGuide()
    assert guide._messages == {}


def test_proactive_guide_review_reminder():
    """测试复习提醒。"""
    guide = ProactiveGuide()

    message = guide.create_review_reminder(
        learner_id="test_learner",
        knowledge_id="vocab_basic",
        days_overdue=2,
    )

    assert message.message_type == "review_reminder"
    assert "vocab_basic" in message.content


def test_proactive_guide_encouragement():
    """测试鼓励消息。"""
    guide = ProactiveGuide()

    message = guide.create_encouragement(
        learner_id="test_learner",
        streak=5,
    )

    assert message.message_type == "encouragement"
    assert "5" in message.content


def test_proactive_guide_get_unread():
    """测试获取未读消息。"""
    guide = ProactiveGuide()

    guide.create_review_reminder("test_learner", "vocab_basic")
    guide.create_encouragement("test_learner", streak=3)

    unread = guide.get_unread_messages("test_learner")
    assert len(unread) == 2


def test_proactive_guide_mark_read():
    """测试标记已读。"""
    guide = ProactiveGuide()

    message = guide.create_review_reminder("test_learner", "vocab_basic")
    guide.mark_as_read("test_learner", message.message_id)

    unread = guide.get_unread_messages("test_learner")
    assert len(unread) == 0


def test_context_manager_creation():
    """测试上下文管理器创建。"""
    manager = ContextManager()
    assert manager._contexts == {}


def test_context_manager_get_context():
    """测试获取上下文。"""
    manager = ContextManager()
    context = manager.get_context("test_learner")
    assert context.learner_id == "test_learner"


def test_context_manager_update_context():
    """测试更新上下文。"""
    manager = ContextManager()
    manager.update_context("test_learner", current_knowledge_id="vocab_basic")
    manager.update_mastery("test_learner", "vocab_basic", 0.6)

    context = manager.get_context("test_learner")
    assert context.current_knowledge_id == "vocab_basic"
    assert context.mastery == 0.6


def test_context_manager_set_current_topic():
    """测试设置当前主题。"""
    manager = ContextManager()
    manager.set_current_topic("test_learner", "vocab_basic")
    manager.set_current_topic("test_learner", "vocab_intermediate")

    context = manager.get_context("test_learner")
    assert context.current_knowledge_id == "vocab_intermediate"
    assert "vocab_basic" in context.recent_topics
    assert "vocab_intermediate" in context.recent_topics


def test_context_manager_serialize():
    """测试序列化。"""
    manager = ContextManager()
    manager.set_current_topic("test_learner", "vocab_basic")
    manager.update_mastery("test_learner", "vocab_basic", 0.6)

    data = manager.serialize("test_learner")
    assert data["learner_id"] == "test_learner"
    assert data["current_knowledge_id"] == "vocab_basic"
    assert data["mastery"] == 0.6
