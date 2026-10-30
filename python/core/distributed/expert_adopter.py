"""Revalidate an untrusted expert draft against current parent authority."""

from __future__ import annotations

import re
from typing import Any, Literal, get_args, get_origin

from core.agent_errors import AgentExecutionError
from core.coordination_models import AgentResult

from .expert_contracts import (
    AssessmentCompleted,
    CurriculumCompleted,
    ExpertFailed,
    ExpertJobRequest,
    ExpertNeedsInput,
    ExpertRole,
    ExpertTerminalEnvelope,
    TutorDraft,
)

_CITATION = re.compile(r"(?:message|evidence|memory):[A-Za-z0-9_-]+")


class ExpertResultAdopter:
    """Convert a frozen draft into a parent-owned domain result."""

    def adopt(
        self,
        ctx,
        step,
        plan,
        request: ExpertJobRequest,
        envelope: ExpertTerminalEnvelope,
    ) -> AgentResult | TutorDraft:
        self._validate_identity(ctx, step, plan, request, envelope)
        if envelope.outcome == "failed":
            code = envelope.error_code.value if envelope.error_code else "expert_failed"
            self._reject(ctx, request, "terminal_failure", self._public_code(code))

        draft = envelope.draft
        if draft is None:
            self._reject(ctx, request, "draft_missing", "expert_result_invalid")
        self._validate_role(ctx, request, draft)
        self._validate_sources(ctx, request, draft.source_refs)
        if (
            isinstance(draft, TutorDraft)
            and draft.content
            and not set(_CITATION.findall(draft.content))
            <= set(draft.source_refs)
        ):
            self._reject(
                ctx,
                request,
                "tutor_citation_undeclared",
                "expert_sources_unverified",
            )
        ctx.source_refs = list(
            dict.fromkeys([*ctx.source_refs, *draft.source_refs])
        )
        ctx.read_refs = list(
            dict.fromkeys([*ctx.read_refs, *draft.source_refs])
        )
        records = {
            record.source_ref: record
            for record in request.snapshot.history_records
        }
        for source_ref in draft.source_refs:
            record = records.get(source_ref)
            if record is not None:
                ctx.read_evidence[source_ref] = {
                    "source_ref": source_ref,
                    "role": record.role,
                    "recorded_at": record.recorded_at.isoformat(),
                    "knowledge_id": record.knowledge_id,
                    "content": record.content,
                    "truncated": False,
                    "next_cursor": None,
                }

        if request.role is ExpertRole.TUTOR:
            return draft

        proposed_actions = (
            list(draft.proposed_actions)
            if isinstance(draft, CurriculumCompleted)
            else []
        )
        body: dict[str, Any] = {
            "task_id": step.step_id,
            **draft.model_dump(mode="python"),
            "proposed_actions": proposed_actions,
        }
        if isinstance(draft, ExpertFailed):
            body["error_code"] = self._public_code(draft.error_code.value)
        result = AgentResult.model_validate(body)
        return result

    def _validate_identity(
        self,
        ctx,
        step,
        plan,
        request: ExpertJobRequest,
        envelope: ExpertTerminalEnvelope,
    ) -> None:
        checks = (
            (request.learner_id == ctx.learner, "learner_mismatch"),
            (
                request.snapshot.learner_id == ctx.learner,
                "snapshot_learner_mismatch",
            ),
            (request.step_id == step.step_id, "request_step_mismatch"),
            (envelope.step_id == step.step_id, "result_step_mismatch"),
            (request.role.value == step.agent, "request_role_mismatch"),
            (envelope.role == request.role, "result_role_mismatch"),
            (request.objective == step.objective, "objective_mismatch"),
            (request.plan_id == plan.plan_id, "plan_id_mismatch"),
            (request.plan_version == plan.version, "plan_version_mismatch"),
            (
                request.snapshot.effective_policy_hash
                == ctx.effective_policy_hash,
                "policy_hash_mismatch",
            ),
            (
                not plan.effective_policy_hash
                or plan.effective_policy_hash == ctx.effective_policy_hash,
                "plan_policy_hash_mismatch",
            ),
            (
                envelope.input_hash == request.input_hash,
                "input_hash_mismatch",
            ),
        )
        for valid, reason in checks:
            if not valid:
                self._reject(ctx, request, reason, "expert_result_invalid")

        current = getattr(ctx, "execution_authority", None)
        if current is not None and current != request.authority:
            self._reject(
                ctx,
                request,
                "parent_authority_stale",
                "delegate_unavailable",
            )
        if current is None and not request.authority.worker_id.startswith(
            "inline-"
        ):
            self._reject(
                ctx,
                request,
                "parent_authority_missing",
                "delegate_unavailable",
            )

    def _validate_role(
        self,
        ctx,
        request: ExpertJobRequest,
        draft,
    ) -> None:
        shared = (ExpertNeedsInput, ExpertFailed)
        if request.role is ExpertRole.ASSESSMENT:
            valid = type(draft) is AssessmentCompleted or isinstance(
                draft,
                shared,
            )
        elif request.role is ExpertRole.CURRICULUM:
            valid = type(draft) is CurriculumCompleted or isinstance(
                draft,
                shared,
            )
        else:
            valid = type(draft) is TutorDraft
        if not valid:
            self._reject(
                ctx,
                request,
                "draft_role_mismatch",
                "expert_action_not_allowed"
                if isinstance(draft, CurriculumCompleted)
                else "expert_result_invalid",
            )

    def _validate_sources(
        self,
        ctx,
        request: ExpertJobRequest,
        source_refs: list[str],
    ) -> None:
        frozen_scope = {
            record.source_ref
            for record in request.snapshot.history_records
        }
        frozen_scope.update(
            item["source_ref"]
            for item in request.snapshot.stable_memories
            if isinstance(item, dict)
            and isinstance(item.get("source_ref"), str)
        )
        if not set(source_refs) <= frozen_scope:
            self._reject(
                ctx,
                request,
                "source_out_of_scope",
                "expert_sources_unverified",
            )
        if any(
            not ctx.history.memory.source(ctx.learner, ref)
            for ref in source_refs
        ):
            self._reject(
                ctx,
                request,
                "source_unavailable",
                "source_unavailable",
            )

    @staticmethod
    def _public_code(code: str) -> str:
        def literal_values(annotation) -> set[str]:
            if get_origin(annotation) is Literal:
                return set(get_args(annotation))
            return {
                value
                for item in get_args(annotation)
                for value in literal_values(item)
            }

        allowed = literal_values(
            AgentResult.model_fields["error_code"].annotation
        )
        return code if code in allowed else "expert_failed"

    @staticmethod
    def _reject(
        ctx,
        request: ExpertJobRequest,
        reason: str,
        code: str,
    ) -> None:
        ctx.record(
            "expert.adoption_rejected",
            "Coordinator",
            task_id=request.step_id,
            role=request.role.value,
            input_hash=request.input_hash,
            reason=reason,
        )
        raise AgentExecutionError(code, reason)
