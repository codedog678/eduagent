from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from core.agent_errors import AgentExecutionError
from core.coordination_models import LearningPlan, PlanStep
from core.distributed.expert_adopter import ExpertResultAdopter
from core.distributed.expert_contracts import (
    AssessmentCompleted,
    CurriculumCompleted,
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
from tests.test_memory_coordination import context, harness, seed


NOW = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)


def plan_for(role: ExpertRole) -> tuple[LearningPlan, PlanStep]:
    steps = []
    if role is not ExpertRole.TUTOR:
        steps.append(
            PlanStep(
                step_id="expert-step",
                agent=role.value,
                objective="Assess and plan",
            )
        )
    steps.append(
        PlanStep(
            step_id="tutor-step",
            agent="Tutor",
            objective="Explain",
            depends_on=["expert-step"] if steps else [],
        )
    )
    plan = LearningPlan(
        goal="Review",
        steps=steps,
        effective_policy_hash="b" * 64,
    )
    step = steps[0]
    return plan, step


def request_for(
    ctx,
    plan,
    step,
    *,
    role: ExpertRole,
    source_ref: str | None = None,
    authorized: list[str] | None = None,
) -> ExpertJobRequest:
    deadline = NOW + timedelta(minutes=1)
    authority = RunExecutionAuthority(
        distributed_run_id=uuid4(),
        run_fencing_token=1,
        trace_id="a" * 32,
        attempt_number=1,
        worker_id="parent-worker",
        parent_deadline_at=deadline,
    )
    ctx.execution_authority = authority
    records = (
        [
            HistoryRecord(
                source_ref=source_ref,
                role="user",
                recorded_at=NOW,
                knowledge_id=ctx.knowledge_id,
                content="Observed source",
            )
        ]
        if source_ref
        else []
    )
    return ExpertJobRequest(
        logical_key=f"{role.value.lower()}-job",
        learner_id=ctx.learner,
        step_id=step.step_id,
        role=role,
        objective=step.objective,
        plan_id=plan.plan_id,
        plan_version=plan.version,
        snapshot=ExpertSnapshot(
            learner_id=ctx.learner,
            knowledge_id=ctx.knowledge_id,
            current_input="Review",
            goal=plan.goal,
            effective_policy_hash=ctx.effective_policy_hash,
            practice_policy={
                "authorized_knowledge_ids": authorized
                or [ctx.knowledge_id],
            },
            history_records=records,
            verified_source_refs=[source_ref] if source_ref else [],
        ),
        budget=ExpertBudget(
            max_model_calls=2,
            max_tool_calls=2,
            max_output_tokens=800,
            max_context_tokens=6000,
            max_attempts=2,
            deadline_at=deadline,
        ),
        authority=authority,
    )


def usage() -> ExpertUsage:
    return ExpertUsage(
        model_calls=1,
        tool_calls=0,
        input_tokens=10,
        output_tokens=5,
        estimated_cost_usd=Decimal("0.01"),
        provider="test",
        model="test",
    )


def envelope(request, draft) -> ExpertTerminalEnvelope:
    return ExpertTerminalEnvelope(
        step_id=request.step_id,
        role=request.role,
        input_hash=request.input_hash,
        outcome="succeeded",
        draft=draft,
        usage=usage(),
        completed_at=NOW,
    )


def parent_context(harness):
    ctx = context(harness)
    ctx.effective_policy_hash = "b" * 64
    return ctx


def test_adopter_returns_parent_owned_result_and_binds_current_source(harness):
    source_ref = seed(harness.db)
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.ASSESSMENT)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.ASSESSMENT,
        source_ref=source_ref,
    )

    result = ExpertResultAdopter().adopt(
        ctx,
        step,
        plan,
        request,
        envelope(
            request,
            AssessmentCompleted(
                status="completed",
                findings=["Needs review"],
                source_refs=[source_ref],
            ),
        ),
    )

    assert result.task_id == step.step_id
    assert result.source_refs == [source_ref]
    assert ctx.source_refs == [source_ref]
    assert ctx.read_refs == [source_ref]


def test_adopter_rejects_source_outside_frozen_scope(harness):
    included = seed(harness.db, identifier="included")
    outside = seed(harness.db, identifier="outside")
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.ASSESSMENT)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.ASSESSMENT,
        source_ref=included,
    )

    with pytest.raises(
        AgentExecutionError,
        match="expert_sources_unverified",
    ) as caught:
        ExpertResultAdopter().adopt(
            ctx,
            step,
            plan,
            request,
            envelope(
                request,
                AssessmentCompleted(
                    status="completed",
                    findings=["Forged"],
                    source_refs=[outside],
                ),
            ),
        )

    assert caught.value.cause_type == "source_out_of_scope"


def test_adopter_rejects_source_deleted_after_result_acceptance(harness):
    source_ref = seed(harness.db)
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.ASSESSMENT)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.ASSESSMENT,
        source_ref=source_ref,
    )
    accepted = envelope(
        request,
        AssessmentCompleted(
            status="completed",
            findings=["Was valid"],
            source_refs=[source_ref],
        ),
    )
    with harness.db:
        harness.db.execute(
            "DELETE FROM conversation_messages WHERE id='one'"
        )

    with pytest.raises(AgentExecutionError, match="source_unavailable"):
        ExpertResultAdopter().adopt(
            ctx,
            step,
            plan,
            request,
            accepted,
        )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("plan", "plan_version_mismatch"),
        ("policy", "policy_hash_mismatch"),
        ("authority", "parent_authority_stale"),
    ],
)
def test_adopter_revalidates_parent_identity(
    harness,
    mutation,
    reason,
):
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.ASSESSMENT)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.ASSESSMENT,
    )
    if mutation == "plan":
        plan.version += 1
    elif mutation == "policy":
        ctx.effective_policy_hash = "c" * 64
    else:
        ctx.execution_authority = request.authority.model_copy(
            update={"run_fencing_token": 2}
        )

    with pytest.raises(AgentExecutionError) as caught:
        ExpertResultAdopter().adopt(
            ctx,
            step,
            plan,
            request,
            envelope(
                request,
                AssessmentCompleted(
                    status="completed",
                    findings=["Draft"],
                ),
            ),
        )

    assert caught.value.cause_type == reason


def test_adopter_rejects_curriculum_draft_smuggled_for_assessment(harness):
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.ASSESSMENT)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.ASSESSMENT,
    )
    smuggled = CurriculumCompleted(
        status="completed",
        findings=["Draft"],
        proposed_actions=[
            {"knowledge_id": ctx.knowledge_id, "difficulty": 0.5}
        ],
    )

    with pytest.raises(
        AgentExecutionError,
        match="expert_action_not_allowed",
    ):
        ExpertResultAdopter().adopt(
            ctx,
            step,
            plan,
            request,
            envelope(request, smuggled),
        )


def test_adopter_keeps_curriculum_action_as_unexecuted_parent_proposal(harness):
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.CURRICULUM)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.CURRICULUM,
        authorized=["foreign-topic"],
    )
    draft = CurriculumCompleted(
        status="completed",
        findings=["Draft"],
        proposed_actions=[
            {"knowledge_id": "foreign-topic", "difficulty": 0.5}
        ],
    )

    adopted = ExpertResultAdopter().adopt(
        ctx,
        step,
        plan,
        request,
        envelope(request, draft),
    )

    assert adopted.proposed_actions[0].knowledge_id == "foreign-topic"


def test_tutor_adoption_returns_draft_not_public_reply(harness):
    source_ref = seed(harness.db)
    ctx = parent_context(harness)
    plan, step = plan_for(ExpertRole.TUTOR)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.TUTOR,
        source_ref=source_ref,
    )
    draft = TutorDraft(
        status="completed",
        content=f"Review this source {source_ref}",
        source_refs=[source_ref],
    )

    adopted = ExpertResultAdopter().adopt(
        ctx,
        step,
        plan,
        request,
        envelope(request, draft),
    )

    assert type(adopted) is TutorDraft
    assert not hasattr(adopted, "generation_mode")


def test_tutor_adoption_rejects_inline_citation_not_declared_by_draft(harness):
    source_ref = seed(harness.db)
    ctx = parent_context(harness)
    ctx.source_refs = [source_ref]
    plan, step = plan_for(ExpertRole.TUTOR)
    request = request_for(
        ctx,
        plan,
        step,
        role=ExpertRole.TUTOR,
        source_ref=source_ref,
    )
    draft = TutorDraft(
        status="completed",
        content=f"Review this source {source_ref}",
        source_refs=[],
    )

    with pytest.raises(
        AgentExecutionError,
        match="expert_sources_unverified",
    ) as caught:
        ExpertResultAdopter().adopt(
            ctx,
            step,
            plan,
            request,
            envelope(request, draft),
        )

    assert caught.value.cause_type == "tutor_citation_undeclared"
