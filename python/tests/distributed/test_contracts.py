import pytest
from pydantic import ValidationError

from config.settings import Settings
from core.distributed.contracts import (
    DistributedRunRequest,
    RunOperation,
    RunStatus,
    canonical_hash,
)


def request(**updates):
    value = {
        "learner_id": "student-1",
        "request_id": "request-1",
        "operation": RunOperation.LEARNING_TASK,
        "payload": {
            "learner_id": "student-1",
            "request_id": "request-1",
            "knowledge_id": "grammar_tenses",
            "question": "安排十分钟复习",
        },
    }
    value.update(updates)
    return DistributedRunRequest.model_validate(value)


def test_canonical_hash_ignores_mapping_order():
    left = canonical_hash({"b": 2, "a": {"y": 1, "x": 0}})
    right = canonical_hash({"a": {"x": 0, "y": 1}, "b": 2})
    assert left == right


def test_learning_task_scope_must_match_envelope():
    with pytest.raises(ValidationError, match="payload learner_id"):
        request(
            payload={
                "learner_id": "other",
                "request_id": "request-1",
                "knowledge_id": "grammar_tenses",
                "question": "安排复习",
            }
        )


def test_terminal_statuses_are_explicit():
    assert RunStatus.COMPLETED.terminal
    assert RunStatus.CANCELLED.terminal
    assert not RunStatus.RUNNING.terminal


def test_distributed_settings_require_safe_heartbeat_and_database_url():
    settings = Settings(
        _env_file=None,
        database_url="",
        distributed_enabled=True,
        distributed_database_url="postgresql://db.example/edu_agent",
        distributed_lease_seconds=10,
        distributed_heartbeat_seconds=4,
    )
    assert (
        settings.effective_distributed_database_url
        == "postgresql+asyncpg://db.example/edu_agent"
    )

    with pytest.raises(ValidationError, match="less than half"):
        Settings(
            _env_file=None,
            distributed_enabled=True,
            distributed_lease_seconds=10,
            distributed_heartbeat_seconds=5,
        )

    with pytest.raises(ValidationError, match="database URL is required"):
        Settings(
            _env_file=None,
            database_url="",
            distributed_database_url="",
            distributed_enabled=True,
        )

    with pytest.raises(ValidationError, match="postgresql\\+asyncpg"):
        Settings(
            _env_file=None,
            database_url="sqlite+aiosqlite:///local.db",
            distributed_enabled=True,
        )


def test_learning_task_payload_is_strict_and_bounded():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        request(
            payload={
                "learner_id": "student-1",
                "request_id": "request-1",
                "knowledge_id": "grammar_tenses",
                "question": "安排复习",
                "unknown": True,
            }
        )

    with pytest.raises(ValidationError, match="string_too_long"):
        request(
            payload={
                "learner_id": "student-1",
                "request_id": "request-1",
                "knowledge_id": "grammar_tenses",
                "question": "问" * 4001,
            }
        )

    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        request(request_id="contains spaces")
