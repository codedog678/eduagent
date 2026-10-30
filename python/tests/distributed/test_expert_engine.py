import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from core.distributed.expert_contracts import (
    CurriculumCompleted,
    ExpertBudget,
    ExpertErrorCode,
    ExpertJobRequest,
    ExpertRole,
    ExpertSnapshot,
    ExpertUsage,
    HistoryRecord,
    RunExecutionAuthority,
    TutorDraft,
)
from core.distributed.expert_engine import ExpertEngine
from core.llm_service import NativeToolCall, NativeTurn


NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)


class Service:
    provider = "test"
    model = "bounded-model"

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = []

    async def tool_turn(self, messages, tools, max_tokens):
        self.calls.append((messages, tools, max_tokens))
        turn = self.turns.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        return turn


def tool_turn(*calls, usage=None, reasoning=None):
    return NativeTurn(
        stop_reason="tool_calls",
        tool_calls=[
            NativeToolCall(id=call_id, name=name, arguments=arguments)
            for call_id, name, arguments in calls
        ],
        reasoning_content=reasoning,
        usage=usage or {},
    )


def final(content, *, usage=None, reasoning=None):
    return NativeTurn(
        content=content,
        stop_reason="stop",
        reasoning_content=reasoning,
        usage=usage or {},
    )


def usage(**updates):
    values = {
        "model_calls": 0,
        "tool_calls": 0,
        "provider": "test",
        "model": "bounded-model",
    }
    values.update(updates)
    return ExpertUsage(**values)


def request(role=ExpertRole.ASSESSMENT, *, budget_updates=None, snapshot_updates=None):
    snapshot_values = {
        "learner_id": "student-1",
        "knowledge_id": "grammar_tenses",
        "current_input": "安排十分钟复习",
        "student_inputs": ["安排十分钟复习"],
        "goal": "复习时态",
        "constraints": ["十分钟"],
        "effective_policy_hash": "b" * 64,
        "practice_policy": {
            "allowed_knowledge_ids": ["grammar_tenses"],
            "required": False,
        },
        "knowledge_state": {"mastery": 0.4},
        "learner_profile": {"goal": "考试"},
        "review_queue": [{"knowledge_id": "grammar_tenses"}],
        "knowledge_context": {"knowledge_id": "grammar_tenses"},
        "history_records": [
            HistoryRecord(
                source_ref="message:own",
                role="user",
                recorded_at=NOW,
                knowledge_id="grammar_tenses",
                content="过去时态错误",
            )
        ],
    }
    snapshot_values.update(snapshot_updates or {})
    deadline = NOW + timedelta(minutes=1)
    budget_values = {
        "max_model_calls": 3,
        "max_tool_calls": 4,
        "max_output_tokens": 800,
        "max_context_tokens": 6000,
        "max_attempts": 3,
        "deadline_at": deadline,
    }
    budget_values.update(budget_updates or {})
    return ExpertJobRequest(
        logical_key="expert-step-1",
        learner_id="student-1",
        step_id="step-1",
        role=role,
        objective="完成冻结专家任务",
        plan_id="plan-1",
        plan_version=1,
        snapshot=ExpertSnapshot(**snapshot_values),
        budget=ExpertBudget(**budget_values),
        authority=RunExecutionAuthority(
            distributed_run_id=UUID("12345678-1234-5678-1234-567812345678"),
            run_fencing_token=3,
            trace_id="a" * 32,
            attempt_number=2,
            worker_id="run-worker-1",
            parent_deadline_at=deadline + timedelta(minutes=1),
        ),
    )


@pytest.mark.asyncio
async def test_assessment_searches_then_reads_before_citing_source():
    service = Service(
        tool_turn(("search", "search_learning_history", '{"query":"时态"}')),
        tool_turn(
            (
                "read",
                "read_learning_history",
                '{"source_ref":"message:own","offset":0,"limit":3000}',
            )
        ),
        final(
            '{"status":"completed","findings":["过去时态需要复习"],'
            '"source_refs":["message:own"],"uncertainty":""}'
        ),
    )

    envelope = await ExpertEngine(service, clock=lambda: NOW).execute(request())

    assert envelope.outcome == "succeeded"
    assert envelope.draft.source_refs == ["message:own"]
    assert envelope.usage.model_calls == 3
    assert envelope.usage.tool_calls == 2


@pytest.mark.asyncio
async def test_curriculum_accepts_action_and_assessment_rejects_same_schema():
    content = (
        '{"status":"completed","findings":["每天复习十分钟"],'
        '"proposed_actions":[{"knowledge_id":"grammar_tenses","difficulty":0.5}],'
        '"source_refs":[],"uncertainty":""}'
    )
    curriculum = await ExpertEngine(
        Service(final(content)), clock=lambda: NOW
    ).execute(request(ExpertRole.CURRICULUM))
    assessment = await ExpertEngine(
        Service(final(content), final(content)), clock=lambda: NOW
    ).execute(request(ExpertRole.ASSESSMENT))

    assert curriculum.outcome == "succeeded"
    assert isinstance(curriculum.draft, CurriculumCompleted)
    assert curriculum.draft.proposed_actions[0].knowledge_id == "grammar_tenses"
    assert assessment.outcome == "failed"
    assert assessment.error_code == ExpertErrorCode.EXPERT_ACTION_NOT_ALLOWED


@pytest.mark.asyncio
async def test_tutor_returns_strict_tutor_draft():
    envelope = await ExpertEngine(
        Service(
            final(
                '{"status":"completed","content":"先复习过去时。",'
                '"source_refs":[],"uncertainty":""}'
            )
        ),
        clock=lambda: NOW,
    ).execute(request(ExpertRole.TUTOR))

    assert envelope.outcome == "succeeded"
    assert isinstance(envelope.draft, TutorDraft)
    assert envelope.draft.content == "先复习过去时。"


@pytest.mark.asyncio
async def test_consumed_budget_limits_work_but_usage_reports_only_new_calls():
    consumed = usage(
        model_calls=1,
        tool_calls=2,
        input_tokens=100,
        output_tokens=50,
    )
    service = Service(
        tool_turn(
            ("context", "get_knowledge_context", "{}"),
            usage={"input_tokens": 7, "output_tokens": 3},
        ),
        final(
            '{"status":"completed","findings":["使用快照完成诊断"],'
            '"source_refs":[],"uncertainty":""}',
            usage={"input_tokens": 11},
        ),
    )

    envelope = await ExpertEngine(service, clock=lambda: NOW).execute(
        request(budget_updates={"max_model_calls": 3, "max_tool_calls": 3}),
        consumed=consumed,
    )

    assert envelope.outcome == "succeeded"
    assert envelope.usage.model_calls == 2
    assert envelope.usage.tool_calls == 1
    assert envelope.usage.input_tokens == 18
    assert envelope.usage.output_tokens is None


@pytest.mark.asyncio
async def test_model_and_tool_budget_exhaustion_are_failed_envelopes():
    model_limited = await ExpertEngine(
        Service(tool_turn(("context", "get_knowledge_context", "{}"))),
        clock=lambda: NOW,
    ).execute(request(budget_updates={"max_model_calls": 1}))
    tool_limited = await ExpertEngine(
        Service(
            tool_turn(
                ("one", "get_knowledge_context", "{}"),
                ("two", "get_learner_profile", "{}"),
            ),
            final(
                '{"status":"completed","findings":["按现有快照保守判断"],'
                '"source_refs":[],"uncertainty":""}'
            ),
        ),
        clock=lambda: NOW,
    ).execute(request(budget_updates={"max_tool_calls": 1}))

    assert model_limited.outcome == "failed"
    assert model_limited.error_code == ExpertErrorCode.BUDGET_EXHAUSTED
    assert model_limited.usage.model_calls == 1
    assert model_limited.usage.tool_calls == 0
    assert tool_limited.outcome == "succeeded"
    assert tool_limited.usage.tool_calls == 1
    assert "tool_skipped:budget_exhausted" in tool_limited.diagnostics


@pytest.mark.asyncio
async def test_duplicate_tool_ids_and_unread_citations_are_rejected():
    duplicate = await ExpertEngine(
        Service(
            tool_turn(
                ("same", "get_knowledge_context", "{}"),
                ("same", "get_learner_profile", "{}"),
            )
        ),
        clock=lambda: NOW,
    ).execute(request())
    unread = await ExpertEngine(
        Service(
            final(
                '{"status":"completed","findings":["引用搜索摘要"],'
                '"source_refs":["message:own"],"uncertainty":""}'
            ),
            final(
                '{"status":"completed","findings":["仍引用搜索摘要"],'
                '"source_refs":["message:own"],"uncertainty":""}'
            ),
        ),
        clock=lambda: NOW,
    ).execute(request())

    assert duplicate.outcome == "failed"
    assert duplicate.error_code == ExpertErrorCode.TOOL_ARGUMENT_INVALID
    assert duplicate.usage.tool_calls == 2
    assert unread.outcome == "failed"
    assert unread.error_code == ExpertErrorCode.EXPERT_SOURCES_UNVERIFIED
    assert unread.diagnostics == [
        "draft_rejected:expert_sources_unverified",
        "draft_repair:unread_source",
        "draft_rejected:expert_sources_unverified",
    ]


@pytest.mark.asyncio
async def test_usage_is_exact_and_private_reasoning_or_raw_errors_never_escape():
    success = await ExpertEngine(
        Service(
            final(
                '{"status":"completed","findings":["完成"],'
                '"source_refs":[],"uncertainty":""}',
                usage={"input_tokens": 13, "output_tokens": 5},
                reasoning="PRIVATE-REASONING",
            )
        ),
        clock=lambda: NOW,
    ).execute(request())
    failure = await ExpertEngine(
        Service(RuntimeError("secret-api-key PRIVATE-REASONING")),
        clock=lambda: NOW,
    ).execute(request())

    assert success.usage == usage(
        model_calls=1,
        input_tokens=13,
        output_tokens=5,
    )
    assert success.diagnostics == []
    assert failure.outcome == "failed"
    assert failure.error_code == ExpertErrorCode.PROVIDER_UNAVAILABLE
    assert failure.usage.model_calls == 1
    assert "PRIVATE" not in failure.model_dump_json()
    assert "secret-api-key" not in failure.model_dump_json()


@pytest.mark.asyncio
async def test_deadline_context_and_template_paths_are_conservative():
    expired = await ExpertEngine(
        Service(), clock=lambda: NOW + timedelta(minutes=2)
    ).execute(request())
    oversized = await ExpertEngine(
        Service(), clock=lambda: NOW
    ).execute(request(budget_updates={"max_context_tokens": 1000}))

    class TemplateService:
        provider = "template"
        model = "template"

    local = await ExpertEngine(
        TemplateService(), clock=lambda: NOW
    ).execute(request(ExpertRole.TUTOR))

    assert expired.error_code == ExpertErrorCode.DEADLINE_EXPIRED
    assert oversized.error_code == ExpertErrorCode.BUDGET_EXHAUSTED
    assert local.outcome == "succeeded"
    assert local.usage.model_calls == 0
    assert local.draft.status == "completed"
    assert "基础教学模板" in local.draft.content


@pytest.mark.asyncio
async def test_invalid_schema_repairs_once_without_replaying_private_draft():
    private = "PRIVATE-INVALID-DRAFT"
    service = Service(
        final(
            '{"status":"completed","findings":["'
            + private
            + '"],"extra":"forbidden"}'
        ),
        final(
            '{"status":"completed","findings":["修正后的结论"],'
            '"source_refs":[],"uncertainty":""}'
        ),
    )

    envelope = await ExpertEngine(
        service,
        clock=lambda: NOW,
    ).execute(request())

    assert envelope.outcome == "succeeded"
    assert envelope.draft.findings == ["修正后的结论"]
    assert "draft_repair:invalid_schema" in envelope.diagnostics
    assert private not in str(service.calls[1][0])


@pytest.mark.asyncio
async def test_initial_prompt_contains_excerpt_not_full_history_record():
    marker = "PRIVATE-FULL-RECORD-TAIL"
    long_content = "候选摘要" + "x" * 500 + marker
    service = Service(
        final(
            '{"status":"completed","findings":["通用结论"],'
            '"source_refs":[],"uncertainty":""}'
        )
    )

    await ExpertEngine(service, clock=lambda: NOW).execute(
        request(
            snapshot_updates={
                "history_records": [
                    HistoryRecord(
                        source_ref="message:long",
                        role="user",
                        recorded_at=NOW,
                        knowledge_id="grammar_tenses",
                        content=long_content,
                    )
                ]
            }
        )
    )

    prompt = str(service.calls[0][0])
    assert "候选摘要" in prompt
    assert marker not in prompt


@pytest.mark.asyncio
async def test_inline_and_worker_entrypoints_match_for_same_frozen_request():
    content = (
        '{"status":"completed","findings":["相同冻结输入"],'
        '"source_refs":[],"uncertainty":""}'
    )
    frozen = request()

    inline = await ExpertEngine(
        Service(final(content)),
        clock=lambda: NOW,
    ).execute(frozen)

    class WorkerEntrypoint:
        async def execute(self, job_request):
            return await ExpertEngine(
                Service(final(content)),
                clock=lambda: NOW,
            ).execute(job_request)

    worker = await WorkerEntrypoint().execute(frozen)

    assert inline.input_hash == worker.input_hash == frozen.input_hash
    assert inline.draft == worker.draft
    assert inline.usage == worker.usage


@pytest.mark.asyncio
async def test_external_task_cancellation_is_not_converted_to_terminal_result():
    started = asyncio.Event()

    class BlockingService(Service):
        async def tool_turn(self, messages, tools, max_tokens):
            started.set()
            await asyncio.Future()

    task = asyncio.create_task(
        ExpertEngine(
            BlockingService(),
            clock=lambda: NOW,
        ).execute(request())
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_result_finishing_after_deadline_is_not_successful():
    current = {"value": NOW}
    frozen = request()

    class DeadlineCrossingService(Service):
        async def tool_turn(self, messages, tools, max_tokens):
            current["value"] = frozen.budget.deadline_at
            return final(
                '{"status":"completed","findings":["too late"],'
                '"source_refs":[],"uncertainty":""}',
                usage={"input_tokens": 3, "output_tokens": 2},
            )

    envelope = await ExpertEngine(
        DeadlineCrossingService(),
        clock=lambda: current["value"],
    ).execute(frozen)

    assert envelope.outcome == "failed"
    assert envelope.error_code == ExpertErrorCode.DEADLINE_EXPIRED
    assert envelope.usage.model_calls == 1
