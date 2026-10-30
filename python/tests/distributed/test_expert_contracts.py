from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from config.settings import Settings
from core.distributed.contracts import RunStatus
from core.distributed.expert_contracts import (
    AssessmentCompleted,
    ExpertBudget,
    ExpertJobRequest,
    ExpertRole,
    ExpertSnapshot,
    ExpertTerminalEnvelope,
    ExpertUsage,
    HistoryRecord,
    RunExecutionAuthority,
    TutorDraft,
)


NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)
PARENT_DEADLINE = NOW + timedelta(minutes=2)


def authority(**updates) -> RunExecutionAuthority:
    values = {
        "distributed_run_id": UUID("12345678-1234-5678-1234-567812345678"),
        "run_fencing_token": 3,
        "trace_id": "a" * 32,
        "attempt_number": 2,
        "worker_id": "run-worker-1",
        "parent_deadline_at": PARENT_DEADLINE,
    }
    values.update(updates)
    return RunExecutionAuthority.model_validate(values)


def snapshot(**updates) -> ExpertSnapshot:
    values = {
        "protocol_version": 1,
        "learner_id": "student-1",
        "knowledge_id": "grammar_tenses",
        "current_input": "安排十分钟复习",
        "student_inputs": ["安排十分钟复习"],
        "goal": "复习时态",
        "constraints": ["十分钟"],
        "effective_policy_hash": "b" * 64,
        "knowledge_state": {},
        "learner_profile": {},
        "review_queue": [],
        "knowledge_context": {},
        "quiz_context": None,
        "stable_memories": [],
        "history_records": [],
        "verified_source_refs": [],
    }
    values.update(updates)
    return ExpertSnapshot.model_validate(values)


def budget(**updates) -> ExpertBudget:
    values = {
        "max_model_calls": 3,
        "max_tool_calls": 4,
        "max_output_tokens": 800,
        "max_context_tokens": 6000,
        "max_attempts": 3,
        "deadline_at": NOW + timedelta(minutes=1),
    }
    values.update(updates)
    return ExpertBudget.model_validate(values)


def request(**updates) -> ExpertJobRequest:
    values = {
        "logical_key": "expert-step-1",
        "learner_id": "student-1",
        "step_id": "step-1",
        "role": ExpertRole.ASSESSMENT,
        "objective": "分析学习证据",
        "plan_id": "plan-1",
        "plan_version": 1,
        "ancestor_results": [],
        "snapshot": snapshot(),
        "budget": budget(),
        "authority": authority(),
        "parent_span_id": "c" * 16,
    }
    values.update(updates)
    return ExpertJobRequest.model_validate(values)


def test_job_hash_is_stable_and_extra_fields_are_forbidden():
    left = request()
    right = request(
        snapshot=snapshot(
            knowledge_state={"mastery": 0.3, "attempts": 2},
            learner_profile={"goal": "考试", "preference": "短练习"},
        )
    )
    reordered = request(
        snapshot=snapshot(
            learner_profile={"preference": "短练习", "goal": "考试"},
            knowledge_state={"attempts": 2, "mastery": 0.3},
        )
    )

    assert right.input_hash == reordered.input_hash
    assert left.input_hash != right.input_hash

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ExpertJobRequest.model_validate(
            {**left.model_dump(mode="python"), "database_url": "postgresql://secret"}
        )

    with pytest.raises(ValidationError, match="learner_id"):
        request(learner_id="other")


def test_tutor_draft_cannot_smuggle_public_response_metadata():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TutorDraft.model_validate(
            {
                "status": "completed",
                "content": "先复习现在完成时。",
                "source_refs": [],
                "dialogue_state": "answered",
            }
        )


def test_deadline_must_be_utc_and_not_after_parent_deadline():
    naive = datetime(2026, 10, 30, 8, 1)
    non_utc = datetime(2026, 10, 30, 16, 1, tzinfo=timezone(timedelta(hours=8)))

    with pytest.raises(ValidationError, match="UTC"):
        authority(parent_deadline_at=naive)
    with pytest.raises(ValidationError, match="UTC"):
        budget(deadline_at=non_utc)
    with pytest.raises(ValidationError, match="UTC"):
        HistoryRecord(
            source_ref="message:1",
            role="student",
            recorded_at=naive,
            content="复习时态",
        )
    with pytest.raises(ValidationError, match="UTC"):
        ExpertTerminalEnvelope(
            step_id="step-1",
            role=ExpertRole.ASSESSMENT,
            input_hash="d" * 64,
            outcome="failed",
            usage=ExpertUsage(
                model_calls=1,
                tool_calls=0,
                provider="openai",
                model="gpt-4o",
            ),
            completed_at=non_utc,
            error_code="provider_timeout",
        )
    with pytest.raises(ValidationError, match="parent deadline"):
        request(budget=budget(deadline_at=PARENT_DEADLINE + timedelta(seconds=1)))


def test_usage_preserves_unknown_tokens_instead_of_zero():
    usage = ExpertUsage(
        model_calls=1,
        tool_calls=0,
        provider="openai",
        model="gpt-4o",
    )

    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.estimated_cost_usd is None


def test_distributed_experts_require_distributed_run_plane():
    with pytest.raises(
        ValidationError, match="distributed experts require distributed run plane"
    ):
        Settings(_env_file=None, distributed_experts_enabled=True)


def test_waiting_expert_is_active_but_not_terminal():
    assert RunStatus.WAITING_EXPERT.active
    assert not RunStatus.WAITING_EXPERT.terminal


def test_terminal_envelope_has_one_unambiguous_outcome():
    values = {
        "step_id": "step-1",
        "role": ExpertRole.ASSESSMENT,
        "input_hash": "d" * 64,
        "usage": ExpertUsage(
            model_calls=1,
            tool_calls=0,
            provider="template",
            model="template",
        ),
        "completed_at": NOW,
    }
    draft = AssessmentCompleted(
        status="completed",
        findings=["使用已核实证据安排复习。"],
    )

    with pytest.raises(ValidationError, match="cannot include error_code"):
        ExpertTerminalEnvelope(
            **values,
            outcome="succeeded",
            draft=draft,
            error_code="expert_failed",
        )
    with pytest.raises(ValidationError, match="cannot include draft"):
        ExpertTerminalEnvelope(
            **values,
            outcome="failed",
            draft=draft,
            error_code="expert_failed",
        )
    with pytest.raises(ValidationError, match="enum"):
        ExpertTerminalEnvelope(
            **values,
            outcome="failed",
            error_code="arbitrary_worker_error",
        )


def test_expert_payload_maximum_cannot_exceed_global_queue_bytes():
    with pytest.raises(ValidationError, match="queued payload limit"):
        Settings(
            _env_file=None,
            distributed_enabled=True,
            distributed_experts_enabled=True,
            expert_max_payload_bytes=2048,
            expert_queued_payload_bytes_limit=1024,
        )
