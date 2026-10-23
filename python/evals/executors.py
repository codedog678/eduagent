"""内置样例使用的真实 Harness 场景执行器。"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from api.orchestrator import AgentOrchestrator
from core.harness import LearningHarness
from core.learning_history import public_data
from core.llm_service import get_llm_service
from core.run_context import RunExhausted, active_run
from core.tutor_runtime import TOOL_SPECS
from evals.models import EvalCase


class BuiltinExecutor:
    """每次评测运行使用隔离的临时 SQLite，并强制关闭远程模型。"""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="eduagent-eval-")
        self.orchestrator = AgentOrchestrator()
        self.harness = LearningHarness(
            self.orchestrator,
            str(Path(self._temporary.name) / "harness.sqlite3"),
        )
        self.orchestrator.harness = self.harness
        self.service = get_llm_service()
        self._had_remote_override = "_has_remote_llm" in self.service.__dict__
        self._remote_override = self.service.__dict__.get("_has_remote_llm")
        self.service._has_remote_llm = lambda: False

    def close(self) -> None:
        self.harness.close()
        if self._had_remote_override:
            self.service._has_remote_llm = self._remote_override
        else:
            del self.service.__dict__["_has_remote_llm"]
        self._temporary.cleanup()

    async def execute(self, case: EvalCase) -> dict[str, Any]:
        if case.kind in {"tutor_response", "labeled_response"}:
            return {"response": str(case.input.get("candidate_response", ""))}
        scenario = str(case.input.get("scenario", ""))
        method = getattr(self, f"_scenario_{scenario}", None)
        if method is None:
            raise ValueError(f"unsupported builtin scenario: {scenario}")
        return public_data(await method(case))

    async def _direct_run(
        self,
        case: EvalCase,
        operation: Callable[[], Awaitable[tuple[dict[str, Any], None]]],
        *,
        learner: str | None = None,
        request: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.harness.run(
            learner or f"learner-{case.case_id}",
            request or case.case_id,
            payload or {"kind": "eval", "case_id": case.case_id},
            operation,
        )

    async def _scenario_cross_session_thread(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        first = await self.harness.converse(
            learner, case.case_id + "-1", "grammar_tenses", "How do tenses differ?",
            session_id="session-one",
        )
        second = await self.harness.converse(
            learner, case.case_id + "-2", "grammar_tenses", "Continue that explanation.",
            session_id="session-two",
        )
        return {
            "same_thread": first["execution"]["thread_id"] == second["execution"]["thread_id"],
            "source_refs": second["execution"]["source_refs"],
            "message_count": len(self.harness.history.messages(learner)["items"]),
        }

    async def _scenario_replay_same_result(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        request = case.case_id + "-request"
        first = await self.harness.converse(
            learner, request, "vocab_basic", "What does abundant mean?"
        )
        second = await self.harness.converse(
            learner, request, "vocab_basic", "What does abundant mean?"
        )
        return {
            "same_result": first == second,
            "message_count": len(self.harness.history.messages(learner)["items"]),
        }

    async def _scenario_source_owner_isolation(self, case: EvalCase) -> dict[str, Any]:
        owner = f"owner-{case.case_id}"
        await self.harness.converse(
            owner, case.case_id + "-seed", "vocab_basic", "Discuss this word."
        )
        source_ref = self.harness.history.messages(owner)["items"][0]["source_ref"]
        denied = False
        try:
            self.harness.history.read(f"other-{case.case_id}", source_ref)
        except HTTPException as exc:
            denied = exc.status_code == 404
        return {"denied": denied, "source_ref_exposed": bool(source_ref)}

    async def _scenario_pending_question(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        question_id = case.case_id + "-pending"

        async def operation():
            ctx = active_run.get()
            ctx.conversation = True
            ctx.dialogue_state = "awaiting_student"
            ctx.pending_question = question_id
            return {
                "teaching_response": {"response": "Which time marker do you see?"}
            }, None

        result = await self._direct_run(
            case,
            operation,
            learner=learner,
            payload={
                "kind": "question",
                "knowledge_id": "grammar_tenses",
                "text": "Why is this tense used?",
            },
        )
        pending = self.harness.history.pending(
            learner, result["execution"]["thread_id"]
        )
        return {
            "execution_status": result["execution"]["status"],
            "dialogue_state": result["execution"]["dialogue_state"],
            "pending_id": pending["id"] if pending else None,
        }

    async def _scenario_public_redaction(self, case: EvalCase) -> dict[str, Any]:
        redacted = public_data({
            "visible": "ok",
            "api_key": "secret",
            "nested": {
                "authorization": "bearer secret",
                "correct_index": 2,
                "explanation": "protected",
                "safe": True,
            },
        })
        serialized = json.dumps(redacted, sort_keys=True)
        return {
            "visible": redacted.get("visible"),
            "nested_safe": redacted.get("nested", {}).get("safe"),
            "contains_sensitive": any(
                key in serialized
                for key in ("api_key", "authorization", "correct_index", "explanation")
            ),
        }

    async def _scenario_quiz_answer_hidden(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        generated = await self.harness.generate(
            learner, case.case_id + "-generate", "vocab_basic", 0.5
        )
        quiz_id = generated["quiz"]["quiz_id"]
        quiz = self.harness.quiz(learner, quiz_id)
        result = await self.harness.answer(
            learner,
            case.case_id + "-answer",
            quiz_id,
            quiz["correct_index"],
            10,
            None,
        )
        serialized = json.dumps(result, ensure_ascii=False)
        return {
            "completed": result["execution"]["status"] == "completed",
            "has_correct_index": "correct_index" in serialized,
            "has_explanation": "explanation" in serialized,
        }

    async def _scenario_advance_hint_denied(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        quiz_id = case.case_id + "-quiz"
        body = {
            "question": "Choose the correct form.",
            "options": ["A. goes", "B. went"],
            "correct_index": 1,
            "explanation": "Past tense.",
            "knowledge_id": "grammar_tenses",
            "difficulty": 0.5,
            "created": time.time(),
            "attempts": 0,
            "hints": 0,
            "revealed": False,
            "solved": False,
            "assisted": False,
            "mode": "advance",
            "session_id": "",
            "thread_id": "",
        }
        with self.harness.db:
            self.harness.db.execute(
                "INSERT INTO quizzes (id,learner,body) VALUES (?,?,?)",
                (quiz_id, learner, json.dumps(body)),
            )
        status_code = None
        try:
            await self.harness.support(
                learner, case.case_id + "-hint", quiz_id, "hint"
            )
        except HTTPException as exc:
            status_code = exc.status_code
        return {
            "status_code": status_code,
            "hints": self.harness.quiz(learner, quiz_id)["hints"],
        }

    async def _scenario_tool_scope_hidden(self, case: EvalCase) -> dict[str, Any]:
        schemas = [
            model.model_json_schema()
            for model, _ in TOOL_SPECS.values()
        ]
        serialized = json.dumps(schemas, sort_keys=True)
        return {
            "learner_parameter_absent": '"learner"' not in serialized,
            "schema_count": len(schemas),
        }

    async def _scenario_idempotent_operation(self, case: EvalCase) -> dict[str, Any]:
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            return {"status": "ok", "calls": calls}, None

        learner = f"learner-{case.case_id}"
        request = case.case_id + "-request"
        payload = {"kind": "eval", "value": 1}
        first = await self._direct_run(
            case, operation, learner=learner, request=request, payload=payload
        )
        second = await self._direct_run(
            case, operation, learner=learner, request=request, payload=payload
        )
        return {"calls": calls, "same_result": first == second}

    async def _scenario_request_conflict(self, case: EvalCase) -> dict[str, Any]:
        async def operation():
            return {"status": "ok"}, None

        learner = f"learner-{case.case_id}"
        request = case.case_id + "-request"
        await self._direct_run(
            case, operation, learner=learner, request=request,
            payload={"kind": "eval", "value": 1},
        )
        status_code = None
        try:
            await self._direct_run(
                case, operation, learner=learner, request=request,
                payload={"kind": "eval", "value": 2},
            )
        except HTTPException as exc:
            status_code = exc.status_code
        return {"status_code": status_code}

    async def _scenario_failure_rollback(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"
        model = self.orchestrator.get_learner_model_sync(learner)
        before = model.total_interactions

        async def operation():
            model.total_interactions += 1
            raise RuntimeError("injected eval failure")

        status_code = None
        try:
            await self._direct_run(case, operation, learner=learner)
        except HTTPException as exc:
            status_code = exc.status_code
        restored = self.orchestrator.learner_models[learner]
        return {
            "status_code": status_code,
            "rolled_back": restored.total_interactions == before,
        }

    async def _scenario_budget_exhaustion(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"

        async def operation():
            raise RunExhausted("eval_budget")

        try:
            await self._direct_run(case, operation, learner=learner)
        except HTTPException:
            pass
        status = self.harness.run_status(learner, case.case_id)
        trace = self.harness.history.trace(learner, case.case_id)
        return {
            "status": status["status"],
            "stop_reason": trace["attempts"][0]["stop_reason"],
        }

    async def _scenario_completed_trace_metadata(self, case: EvalCase) -> dict[str, Any]:
        async def operation():
            return {"status": "ok"}, None

        result = await self._direct_run(case, operation)
        return {"execution": result["execution"]}

    async def _scenario_failed_attempt_trace(self, case: EvalCase) -> dict[str, Any]:
        learner = f"learner-{case.case_id}"

        async def operation():
            raise ValueError("injected")

        try:
            await self._direct_run(case, operation, learner=learner)
        except HTTPException:
            pass
        trace = self.harness.history.trace(learner, case.case_id)
        return {"attempt": trace["attempts"][0]}

    async def _scenario_trace_sequence(self, case: EvalCase) -> dict[str, Any]:
        async def operation():
            active_run.get().record("eval_marker", marker="visible")
            return {"status": "ok"}, None

        await self._direct_run(case, operation)
        trace = self.harness.history.trace(
            f"learner-{case.case_id}", case.case_id
        )
        steps = trace["attempts"][0]["steps"]
        return {
            "ordered": [step["seq"] for step in steps] == list(
                range(1, len(steps) + 1)
            ),
            "kinds": [step["kind"] for step in steps],
        }

    async def _scenario_trace_redaction(self, case: EvalCase) -> dict[str, Any]:
        async def operation():
            active_run.get().record(
                "eval_secret",
                api_key="secret",
                authorization="bearer secret",
                correct_index=1,
                visible="ok",
            )
            return {"status": "ok"}, None

        await self._direct_run(case, operation)
        trace = self.harness.history.trace(
            f"learner-{case.case_id}", case.case_id
        )
        serialized = json.dumps(trace, sort_keys=True)
        return {
            "contains_secret": any(
                marker in serialized
                for marker in (
                    '"api_key"',
                    '"authorization"',
                    '"correct_index"',
                    "bearer secret",
                )
            ),
            "contains_visible": "visible" in serialized,
        }
