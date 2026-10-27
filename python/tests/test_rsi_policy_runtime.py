"""策略切换只影响新任务；待答与练习固定版本，失败不污染学习状态。"""

import json

import pytest

from config.settings import settings
from core.policy_store import BUILTIN_HASH, builtin_components, effective_hash
from core.run_context import active_run
from core.tutor_policy import current_retrieval_rules
from tests.test_learning_harness import harness


class RegistryFixture:
    """仅替代已校验的注册表读取；不创建真实发布凭证。"""
    def __init__(self):
        self.current = BUILTIN_HASH
        components = {"retrieval_rules": "测试策略：读取后再引用"}
        self.other = effective_hash(components)
        self.values = {BUILTIN_HASH: {"policy_hash": BUILTIN_HASH, "components": builtin_components()},
                       self.other: {"policy_hash": self.other, "components": components}}

    def read(self, key):
        if key not in self.values:
            raise ValueError("missing artifact")
        return self.values[key]

    def active(self):
        return self.read(self.current)


def use_registry(monkeypatch):
    registry = RegistryFixture()
    monkeypatch.setattr(settings, "policy_loading_enabled", True)
    monkeypatch.setattr("core.harness.PolicyRegistry", lambda *args, **kwargs: registry)
    return registry


@pytest.mark.asyncio
async def test_inflight_pending_cross_session_and_new_task_versions(harness, monkeypatch):
    registry = use_registry(monkeypatch)
    async def ask():
        ctx = active_run.get()
        assert ctx.effective_policy_hash == BUILTIN_HASH
        registry.current = registry.other
        assert current_retrieval_rules() == builtin_components()["retrieval_rules"]
        ctx.conversation, ctx.pending_question = True, "请补充材料"
        ctx.dialogue_state = "awaiting_student"
        return {"teaching_response": {"response": "请补充材料"}}, None
    first = await harness.run("student", "one", {"knowledge": "vocab_basic", "text": "帮我分析"}, ask)
    assert first["execution"]["effective_policy_hash"] == BUILTIN_HASH
    async def resume():
        ctx = active_run.get()
        assert ctx.effective_policy_hash == BUILTIN_HASH
        return {"status": "ok"}, None
    second = await harness.run("student", "two",
                               {"knowledge": "vocab_basic", "session_id": "new-session"}, resume)
    assert second["execution"]["effective_policy_hash"] == BUILTIN_HASH
    async def fresh():
        assert active_run.get().effective_policy_hash == registry.other
        return {"status": "ok"}, None
    result = await harness.run("new-student", "new", {"knowledge": "vocab_basic"}, fresh)
    assert result["execution"]["effective_policy_hash"] == registry.other
    assert current_retrieval_rules() == builtin_components()["retrieval_rules"]


@pytest.mark.asyncio
async def test_quiz_pin_survives_switch_and_rollback_preserves_learning(harness, monkeypatch):
    registry = use_registry(monkeypatch)
    registry.current = registry.other
    issued = await harness.generate("student", "issue", "vocab_basic", .5)
    quiz_id = issued["quiz"]["quiz_id"]
    quiz = harness.quiz("student", quiz_id)
    assert quiz["effective_policy_hash"] == registry.other
    registry.current = BUILTIN_HASH
    result = await harness.answer("student", "answer", quiz_id, quiz["correct_index"], 10, None)
    assert result["execution"]["effective_policy_hash"] == registry.other
    assert result["learning_evidence"]["mastery_updated"]
    state = harness.capture("student")
    assert await harness.answer("student", "answer", quiz_id, quiz["correct_index"], 10, None) == result
    assert harness.capture("student") == state
    assert harness.quiz("student", quiz_id)["solved"]


@pytest.mark.asyncio
async def test_missing_pinned_policy_fails_without_mutation(harness, monkeypatch):
    registry = use_registry(monkeypatch)
    registry.current = registry.other
    issued = await harness.generate("student", "issue", "vocab_basic", .5)
    quiz_id = issued["quiz"]["quiz_id"]
    before = harness.capture("student")
    registry.current = BUILTIN_HASH
    del registry.values[registry.other]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await harness.support("student", "hint", quiz_id, "hint")
    assert error.value.status_code == 503
    assert harness.capture("student") == before
    assert not harness.quiz("student", quiz_id)["assisted"]


@pytest.mark.asyncio
async def test_pending_plan_pin_is_read_before_operation(harness, monkeypatch):
    registry = use_registry(monkeypatch)
    thread = harness.history.bind("student", None, None, "vocab_basic")[1]
    with harness.db:
        harness.db.execute("INSERT INTO learning_plans VALUES (?,?,?,?,?,?,?)",
                           ("plan", "student", thread, 1, "awaiting_student",
                            json.dumps({"effective_policy_hash": BUILTIN_HASH}), 1))
    registry.current = registry.other
    async def operation():
        assert active_run.get().effective_policy_hash == BUILTIN_HASH
        return {"status": "ok"}, None
    result = await harness.run("student", "resume-plan", {"knowledge": "vocab_basic"}, operation)
    assert result["execution"]["effective_policy_hash"] == BUILTIN_HASH
