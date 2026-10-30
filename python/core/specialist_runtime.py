"""Parent orchestration for frozen inline or durable expert execution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import time
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from config.settings import settings
from core.agent_errors import AgentExecutionError
from core.coordination_budget import specialist_limits
from core.run_context import RunExhausted

from core.distributed.contracts import canonical_hash
from core.distributed.expert_adopter import ExpertResultAdopter
from core.distributed.expert_contracts import (
    ExpertBudget,
    ExpertJobRequest,
    ExpertRole,
    RunExecutionAuthority,
)
from core.distributed.expert_engine import ExpertEngine
from core.distributed.expert_snapshot import ExpertSnapshotBuilder


class SpecialistRuntime:
    def __init__(self, ctx, service):
        self.ctx = ctx
        self.service = service
        self.snapshot_builder = ExpertSnapshotBuilder()
        self.adopter = ExpertResultAdopter()

    async def run(self, step, plan):
        ctx = self.ctx
        original = (
            ctx.role,
            ctx.task_id,
            ctx.max_model_calls,
            ctx.max_tool_calls,
        )
        started = time.monotonic()
        ctx.role, ctx.task_id = step.agent, step.step_id
        ctx.max_model_calls, ctx.max_tool_calls = specialist_limits(
            ctx,
            step,
            plan,
        )
        ctx.record(
            "agent_budget_allocated",
            step.agent,
            task_id=step.step_id,
            model_calls_available=max(
                0,
                ctx.max_model_calls - ctx.model_calls,
            ),
            tool_calls_available=max(
                0,
                ctx.max_tool_calls - ctx.tool_calls,
            ),
        )
        ctx.record(
            "agent_started",
            step.agent,
            parent_run_id=ctx.run_id,
            task_id=step.step_id,
            objective=step.objective,
        )
        status = "failed"
        failure_code = None
        cause_type = None
        try:
            result = await self._execute(step, plan)
            status = result.status
            failure_code = (
                result.error_code if result.status == "failed" else None
            )
            return result
        except AgentExecutionError as exc:
            failure_code = exc.code
            cause_type = exc.cause_type
            ctx.record(
                "expert_validation_failed",
                step.agent,
                task_id=step.step_id,
                error_code=exc.code,
                errors=exc.details,
            )
            raise
        except RunExhausted as exc:
            if str(exc) in {
                "model_call_budget",
                "tool_call_budget",
                "expert_context_budget",
            }:
                failure_code = "budget_exhausted"
                cause_type = type(exc).__name__
                raise AgentExecutionError(
                    failure_code,
                    cause_type,
                ) from exc
            raise
        finally:
            ctx.record(
                "agent_completed",
                step.agent,
                parent_run_id=ctx.run_id,
                task_id=step.step_id,
                status=status,
                stop_reason=status,
                error_code=failure_code,
                cause_type=cause_type,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
            (
                ctx.role,
                ctx.task_id,
                ctx.max_model_calls,
                ctx.max_tool_calls,
            ) = original

    async def native(self, step, plan, executor, upstream, refs):
        """Compatibility entry point; execution still uses the frozen engine."""
        del executor, upstream
        self.ctx.source_refs = list(
            dict.fromkeys([*self.ctx.source_refs, *sorted(refs)])
        )
        return await self._execute(step, plan)

    async def local(self, step, executor, refs):
        """Compatibility entry point for the former template path."""
        del executor
        self.ctx.source_refs = list(
            dict.fromkeys([*self.ctx.source_refs, *sorted(refs)])
        )
        plan = getattr(self.ctx, "_active_learning_plan", None)
        if plan is None:
            raise AgentExecutionError(
                "expert_result_invalid",
                "missing_plan",
            )
        return await self._execute(step, plan)

    async def _execute(self, step, plan):
        ctx = self.ctx
        try:
            request = self._request(step, plan)
        except ValidationError as exc:
            raise AgentExecutionError(
                "expert_schema_invalid",
                "frozen_request_invalid",
                [
                    {
                        "field": ".".join(map(str, error["loc"])),
                        "type": error["type"],
                    }
                    for error in exc.errors(
                        include_input=False,
                        include_url=False,
                    )
                ],
            ) from exc
        before_model = ctx.model_calls
        before_tool = ctx.tool_calls
        gateway = ctx.expert_gateway
        async with asyncio.timeout(ctx.remaining()):
            if gateway is None:
                envelope = await ExpertEngine(self.service).execute(request)
            else:
                envelope = await gateway.execute(request)
        self._charge_usage(
            envelope.usage,
            before_model=before_model,
            before_tool=before_tool,
        )
        self._record_diagnostics(
            step.agent,
            step.step_id,
            envelope.diagnostics,
        )
        return self.adopter.adopt(
            ctx,
            step,
            plan,
            request,
            envelope,
        )

    def _request(self, step, plan) -> ExpertJobRequest:
        ctx = self.ctx
        if (
            len(ctx.effective_policy_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in ctx.effective_policy_hash
            )
        ):
            ctx.effective_policy_hash = canonical_hash(
                {"mode": "inline-default-policy"}
            )
        ancestor_ids = self.ancestors(step, plan)
        ancestors = [
            result.model_dump(mode="json")
            for key, result in plan.results.items()
            if key in ancestor_ids and result.status == "completed"
        ]
        ctx.source_refs = list(dict.fromkeys([
            *ctx.source_refs,
            *[
                source_ref
                for result in ancestors
                for source_ref in result.get("source_refs", [])
            ],
        ]))
        authority = self._authority()
        snapshot = self.snapshot_builder.freeze(
            ctx,
            step,
            plan,
            authority,
        )
        model_budget = ctx.max_model_calls - ctx.model_calls
        tool_budget = ctx.max_tool_calls - ctx.tool_calls
        if model_budget < 1:
            raise AgentExecutionError(
                "budget_exhausted",
                "model_call_budget",
            )
        logical_key = canonical_hash(
            {
                "plan_id": plan.plan_id,
                "plan_version": plan.version,
                "step_id": step.step_id,
                "role": step.agent,
                "effective_policy_hash": ctx.effective_policy_hash,
            }
        )
        now = datetime.now(UTC)
        deadline = ctx.expert_deadlines.get(logical_key)
        if deadline is None:
            deadline = min(
                authority.parent_deadline_at,
                now
                + timedelta(
                    seconds=min(
                        ctx.remaining(),
                        settings.expert_max_job_seconds,
                    )
                ),
            )
            ctx.expert_deadlines[logical_key] = deadline
        if deadline <= now:
            raise AgentExecutionError(
                "budget_exhausted",
                "deadline",
            )
        return ExpertJobRequest(
            logical_key=logical_key,
            learner_id=ctx.learner,
            step_id=step.step_id,
            role=ExpertRole(step.agent),
            objective=step.objective,
            plan_id=plan.plan_id,
            plan_version=plan.version,
            ancestor_results=ancestors,
            snapshot=snapshot,
            budget=ExpertBudget(
                max_model_calls=min(
                    model_budget,
                    settings.specialist_max_model_calls,
                    6,
                ),
                max_tool_calls=min(
                    max(0, tool_budget),
                    settings.specialist_max_tool_calls,
                    10,
                ),
                max_output_tokens=settings.tutor_max_output_tokens,
                max_context_tokens=settings.tutor_context_budget_tokens,
                max_attempts=min(settings.distributed_max_attempts, 5),
                deadline_at=deadline,
            ),
            authority=authority,
        )

    def _authority(self) -> RunExecutionAuthority:
        ctx = self.ctx
        if ctx.execution_authority is not None:
            return ctx.execution_authority
        try:
            run_id = UUID(ctx.run_id)
        except ValueError:
            run_id = uuid5(
                NAMESPACE_URL,
                f"eduagent:inline:{ctx.run_id}",
            )
        remaining = ctx.remaining()
        parent_deadline = datetime.now(UTC) + timedelta(
            seconds=remaining
        )
        trace_id = hashlib.sha256(
            f"{ctx.run_id}:{ctx.attempt_id}".encode("utf-8")
        ).hexdigest()[:32]
        return RunExecutionAuthority(
            distributed_run_id=run_id,
            run_fencing_token=1,
            trace_id=trace_id,
            attempt_number=1,
            worker_id="inline-parent",
            parent_deadline_at=parent_deadline,
        )

    def _charge_usage(
        self,
        usage,
        *,
        before_model: int,
        before_tool: int,
    ) -> None:
        ctx = self.ctx
        observed_model = max(0, ctx.model_calls - before_model)
        observed_tool = max(0, ctx.tool_calls - before_tool)
        for _ in range(max(0, usage.model_calls - observed_model)):
            ctx.consume("model")
        for _ in range(max(0, usage.tool_calls - observed_tool)):
            ctx.consume("tool")
        ctx.record(
            "expert_usage_charged",
            ctx.role,
            task_id=ctx.task_id,
            model_calls=usage.model_calls,
            tool_calls=usage.tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=(
                str(usage.estimated_cost_usd)
                if usage.estimated_cost_usd is not None
                else None
            ),
            provider=usage.provider,
            model=usage.model,
            uncertain=usage.uncertain,
        )

    def _record_diagnostics(
        self,
        role: str,
        step_id: str,
        diagnostics: list[str],
    ) -> None:
        unread_repair = "draft_repair:unread_source" in diagnostics
        for diagnostic in diagnostics:
            kind, _, reason = diagnostic.partition(":")
            if diagnostic == (
                "draft_rejected:required_practice_action_missing"
            ):
                self.ctx.record(
                    "required_practice_action_missing",
                    role,
                    task_id=step_id,
                )
            elif kind == "draft_rejected":
                errors = (
                    [{"field": "source_refs", "type": "unread_source"}]
                    if reason == "expert_sources_unverified"
                    and unread_repair
                    else []
                )
                self.ctx.record(
                    "expert_draft_rejected",
                    role,
                    task_id=step_id,
                    error_code=reason,
                    errors=errors,
                )
            elif kind == "draft_repair":
                self.ctx.record(
                    "expert_draft_repair",
                    role,
                    task_id=step_id,
                    reason=reason,
                )
            elif kind == "tool_skipped":
                self.ctx.record(
                    "tool_skipped",
                    role,
                    task_id=step_id,
                    error_code=reason,
                )
            else:
                self.ctx.record(
                    "expert_engine_diagnostic",
                    role,
                    task_id=step_id,
                    code=diagnostic,
                )

    @staticmethod
    def ancestors(step, plan):
        by_id = {item.step_id: item for item in plan.steps}
        found = set()
        queue = list(step.depends_on)
        while queue:
            key = queue.pop()
            if key not in found:
                found.add(key)
                queue.extend(by_id[key].depends_on)
        return found
