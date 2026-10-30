import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.distributed.expert_contracts import ExpertSnapshot, HistoryRecord
from core.distributed.expert_snapshot import ExpertSnapshotBuilder, SnapshotToolExecutor
from core.llm_service import NativeToolCall
from core.output_safety import has_secret_shaped_key, public_value


NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)


def call(identifier, name, **arguments):
    return NativeToolCall(
        id=identifier,
        name=name,
        arguments=json.dumps(arguments),
    )


class FakeMemory:
    def profile(self, learner):
        return [
            {
                "source_ref": f"memory:{learner}",
                "content": "偏好短练习",
                "nested": {"api_key": "profile-secret"},
            }
        ]


class FakeHistory:
    def __init__(self):
        self.memory = FakeMemory()
        self.records = {
            "message:a-own": {
                "learner": "alice",
                "role": "user",
                "content": "时态错误；password: hunter2",
                "created": NOW.timestamp(),
            },
            "message:z-omitted": {
                "learner": "alice",
                "role": "assistant",
                "content": "很长的历史" * 500,
                "created": NOW.timestamp(),
            },
            "message:foreign": {
                "learner": "bob",
                "role": "user",
                "content": "其他学习者的内容",
                "created": NOW.timestamp(),
            },
        }

    def discovery(self, learner, knowledge, limit=20):
        return {
            "items": [
                {
                    "source_ref": source_ref,
                    "role": record["role"],
                    "created": record["created"],
                    "knowledge_id": knowledge,
                    "excerpt": record["content"][:20],
                }
                for source_ref, record in reversed(self.records.items())
                if record["learner"] == learner
            ][:limit]
        }

    def read(self, learner, source_ref, offset=0, limit=16000):
        record = self.records[source_ref]
        if record["learner"] != learner:
            raise LookupError(source_ref)
        content = record["content"][offset : offset + limit]
        return {
            "source_ref": source_ref,
            "role": record["role"],
            "content": content,
            "created": record["created"],
            "truncated": offset + limit < len(record["content"]),
            "next_cursor": offset + limit
            if offset + limit < len(record["content"])
            else None,
        }


def context():
    return SimpleNamespace(
        learner="alice",
        knowledge_id="grammar_tenses",
        input_text="安排十分钟复习",
        effective_policy_hash="b" * 64,
        model_state={"mastery": 0.4, "nested": {"access_token": "state-secret"}},
        profile_state={"goal": "考试", "cookieJar": "profile-cookie"},
        review_queue=[{"knowledge_id": "grammar_tenses", "priority": 1}],
        quiz=None,
        history=FakeHistory(),
        source_refs=[],
        read_evidence={},
        knowledge_graph=None,
        prepared_quiz=None,
        prepare_practice=lambda **_: pytest.fail("write callback must not run"),
    )


def plan():
    return SimpleNamespace(
        goal="复习时态",
        constraints=["十分钟"],
        student_inputs=["安排十分钟复习"],
        original_request="安排十分钟复习",
        practice_quiz_id=None,
    )


def test_freeze_builds_bounded_redacted_copy_without_parent_objects():
    ctx = context()
    original_state = json.loads(json.dumps(ctx.model_state))
    snapshot = ExpertSnapshotBuilder(
        max_snapshot_bytes=8_000,
        max_history_bytes=1_000,
    ).freeze(ctx, SimpleNamespace(agent="Assessment"), plan(), SimpleNamespace())
    dumped = snapshot.model_dump(mode="json")
    encoded = json.dumps(dumped, ensure_ascii=False).encode()

    assert len(encoded) <= 8_000
    assert [record.source_ref for record in snapshot.history_records] == [
        "message:a-own"
    ]
    assert "message:z-omitted" not in encoded.decode()
    assert "api_key" not in encoded.decode().lower()
    assert "access_token" not in encoded.decode().lower()
    assert "cookiejar" not in encoded.decode().lower()
    assert "hunter2" not in encoded.decode()
    assert ctx.model_state == original_state
    assert "prepare_practice" not in encoded.decode()


def snapshot():
    return ExpertSnapshot(
        learner_id="alice",
        knowledge_id="grammar_tenses",
        current_input="安排复习",
        student_inputs=["安排复习"],
        goal="复习时态",
        constraints=["十分钟"],
        effective_policy_hash="b" * 64,
        knowledge_state={"mastery": 0.4},
        learner_profile={"goal": "考试"},
        review_queue=[{"knowledge_id": "grammar_tenses"}],
        knowledge_context={"knowledge_id": "grammar_tenses"},
        history_records=[
            HistoryRecord(
                source_ref="message:own",
                role="user",
                recorded_at=NOW,
                knowledge_id="grammar_tenses",
                content="过去时态错误",
            )
        ],
    )


@pytest.mark.asyncio
async def test_executor_exposes_only_role_scoped_snapshot_reads():
    executor = SnapshotToolExecutor(snapshot(), role="Assessment")

    assert set(executor.tool_names) == {
        "search_learning_history",
        "read_learning_history",
        "get_knowledge_context",
        "get_learner_profile",
    }
    assert "prepare_practice" not in executor.tool_names
    assert (await executor.read("message:foreign"))["error_code"] == "source_unavailable"
    assert (await executor.read("message:omitted"))["error_code"] == "source_unavailable"
    assert (
        await executor.execute(call("review", "get_review_queue"))
    )["error_code"] == "unavailable_or_not_allowed"


@pytest.mark.asyncio
async def test_search_excerpts_are_not_citable_until_full_read():
    frozen = snapshot()
    original_dump = frozen.model_dump()
    executor = SnapshotToolExecutor(frozen, role="Curriculum")

    found = await executor.execute(
        call("search", "search_learning_history", query="时态")
    )
    assert found["status"] == "ok"
    assert found["data"]["items"][0]["discovery_only"] is True
    assert found["source_refs"] == []
    assert "message:own" not in executor.verified_source_refs

    read = await executor.execute(
        call("read", "read_learning_history", source_ref="message:own")
    )
    assert read["status"] == "ok"
    assert "message:own" in executor.verified_source_refs
    assert frozen.model_dump() == original_dump


@pytest.mark.asyncio
async def test_partial_reads_are_not_citable_until_ranges_cover_full_record():
    frozen = snapshot().model_copy(
        update={
            "history_records": [
                HistoryRecord(
                    source_ref="message:long",
                    role="user",
                    recorded_at=NOW,
                    knowledge_id="grammar_tenses",
                    content="x" * 150,
                )
            ]
        }
    )
    executor = SnapshotToolExecutor(frozen, role="Assessment")

    first = await executor.execute(
        call(
            "read-first",
            "read_learning_history",
            source_ref="message:long",
            offset=0,
            limit=100,
        )
    )
    second = await executor.execute(
        call(
            "read-second",
            "read_learning_history",
            source_ref="message:long",
            offset=100,
            limit=100,
        )
    )

    assert first["truncated"] is True
    assert first["source_refs"] == []
    assert second["source_refs"] == ["message:long"]
    assert executor.verified_source_refs == ("message:long",)


@pytest.mark.asyncio
async def test_executor_rejects_bad_arguments_and_duplicate_call_ids():
    executor = SnapshotToolExecutor(snapshot(), role="Tutor")

    malformed = await executor.execute(
        NativeToolCall(id="", name="get_knowledge_context", arguments="{}")
    )
    invalid = await executor.execute(
        call("bad-args", "search_learning_history", limit="5")
    )
    await executor.execute(call("duplicate", "get_knowledge_context"))
    duplicate = await executor.execute(call("duplicate", "get_learner_profile"))

    assert malformed["status"] == "invalid_arguments"
    assert malformed["error_code"] == "invalid_call_id"
    assert invalid["status"] == "invalid_arguments"
    assert duplicate["status"] == "invalid_arguments"
    assert duplicate["error_code"] == "duplicate_call_id"


def test_public_value_is_recursive_redacted_and_does_not_mutate_input():
    value = {
        "visible": "密码: hunter2",
        "nested": [
            {
                "Authorization": "Bearer private",
                "correct_answer": "B",
                "safe": "hunter2",
            }
        ],
    }
    original = json.loads(json.dumps(value))

    clean = public_value(value)

    assert clean == {
        "visible": "密码: [敏感载荷已隐藏]",
        "nested": [{"safe": "[敏感载荷已隐藏]"}],
    }
    assert not has_secret_shaped_key(clean)
    assert value == original
