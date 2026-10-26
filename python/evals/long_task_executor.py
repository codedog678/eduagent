"""用真实 Harness 执行长任务脚本，支持跨进程生命周期恢复。"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time

from api.orchestrator import AgentOrchestrator
from core.harness import LearningHarness
from core.learning_history import public_data
from core.run_context import RunContext, RunExhausted
from evals.long_task_models import LongTaskCase
from evals.optimization.budget import OptimizationStopped


def _usage(value: dict) -> dict:
    if not value or not any(
        key in value for key in ("input_tokens", "prompt_tokens", "output_tokens",
                                  "completion_tokens")
    ):
        return {}
    return {
        "input_tokens": value.get("input_tokens", value.get("prompt_tokens", 0)),
        "output_tokens": value.get("output_tokens", value.get("completion_tokens", 0)),
        **({"prompt_cache_hit_tokens": value["prompt_cache_hit_tokens"]}
           if isinstance(value.get("prompt_cache_hit_tokens"), int) else {}),
    }


class LongTaskExecutor:
    def __init__(self, case: LongTaskCase, service, budget):
        self.case, self.service, self.budget = case, service, budget
        self._temporary = tempfile.TemporaryDirectory(prefix=f"eduagent-{case.case_id.lower()}-")
        self.path = str(Path(self._temporary.name) / "harness.sqlite3")
        self.case_requests = 0
        self.model_records: list[dict] = []
        self._overrides = {
            name: (name in service.__dict__, service.__dict__.get(name))
            for name in ("tool_turn", "generate")
        }
        self._original_turn = service.tool_turn
        self._original_generate = service.generate
        service.tool_turn = self._metered_turn
        service.generate = self._metered_generate
        self._open()
        try:
            self._seed()
        except BaseException:
            self.close()
            raise

    def _open(self):
        self.orchestrator = AgentOrchestrator(enable_db_logging=False)
        self.harness = LearningHarness(self.orchestrator, self.path)
        self.orchestrator.harness = self.harness

    def close(self):
        for name, (had_override, value) in self._overrides.items():
            if had_override:
                setattr(self.service, name, value)
            elif name in self.service.__dict__:
                del self.service.__dict__[name]
        if getattr(self, "harness", None):
            self.harness.close()
            self.harness = None
        self._temporary.cleanup()

    def restart(self):
        self.harness.close()
        self.harness = None
        self._open()

    def _reserve(self, messages, tools, max_tokens, kind):
        if self.case_requests >= self.case.expected_model_requests_max:
            raise RunExhausted("long_task_case_request_budget")
        index = self.budget.reserve_for("task", messages, tools, max_tokens)
        self.case_requests += 1
        return index, {
            "request_no": self.budget.ledger[index]["request_no"],
            "kind": kind,
            "started": time.time(),
        }

    async def _metered_turn(self, messages, tools, max_tokens):
        index, record = self._reserve(messages, tools, max_tokens, "native_tool_turn")
        started = time.perf_counter()
        try:
            turn = await self._original_turn(messages, tools, max_tokens)
        except BaseException as exc:
            record.update(status="error", error=type(exc).__name__,
                          duration_ms=(time.perf_counter() - started) * 1000)
            self.model_records.append(record)
            raise
        self.budget.settle(index, _usage(turn.usage))
        usage = _usage(turn.usage)
        record.update(
            status="completed", stop_reason=turn.stop_reason, usage=usage,
            tool_calls=[{
                "id": call.id, "name": call.name,
                "arguments": public_data(self._arguments(call.arguments)),
            } for call in turn.tool_calls],
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        self.model_records.append(record)
        return turn

    async def _metered_generate(self, prompt, system_prompt=None, temperature=.7, max_tokens=1000):
        messages = ([{"role": "system", "content": system_prompt}] if system_prompt else [])
        messages.append({"role": "user", "content": prompt})
        index, record = self._reserve(messages, [], max_tokens, "structured_generate")
        started = time.perf_counter()
        try:
            response = await self._original_generate(
                prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens
            )
        except BaseException as exc:
            record.update(status="error", error=type(exc).__name__,
                          duration_ms=(time.perf_counter() - started) * 1000)
            self.model_records.append(record)
            raise
        usage = _usage(response.usage)
        self.budget.settle(index, usage)
        record.update(status="completed", usage=usage,
                      duration_ms=(time.perf_counter() - started) * 1000)
        self.model_records.append(record)
        return response

    @staticmethod
    def _arguments(raw):
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {"invalid_json": True}

    def _scope(self, message):
        session, thread = self.harness.history.bind(
            self.case.learner_id, message.session_id, None, message.knowledge_id
        )
        ctx = RunContext(
            learner=self.case.learner_id, run_id="fixture", attempt_id="fixture",
            deadline=time.monotonic() + 45, session_id=session, thread_id=thread,
            knowledge_id=message.knowledge_id, history=self.harness.history,
        )
        self.harness.history.open_scope(ctx)
        return ctx

    def _seed(self):
        self.orchestrator.get_learner_model_sync(self.case.learner_id).get_state(
            self.case.knowledge_id
        )
        refs = {}
        with self.harness.db:
            for message in self.case.initial_facts.history:
                ctx = self._scope(message)
                self.harness.db.execute(
                    "INSERT INTO conversation_messages "
                    "(id,learner,session,thread,run,role,content,created) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (message.message_id, self.case.learner_id, ctx.session_id, ctx.thread_id,
                     "fixture", message.role, message.content, time.time()),
                )
                ref = "message:" + message.message_id
                self.harness.history.memory.index(self.case.learner_id, ref)
                refs[message.message_id] = (ref, ctx)
            for memory in self.case.initial_facts.memories:
                ref, ctx = refs[memory.source_message_id]
                self.harness.history.memory.propose(
                    ctx, memory.kind, memory.content, ref
                )
                self.harness.history.memory.commit(ctx, ref)

    def _trace(self, request):
        try:
            return self.harness.history.trace(self.case.learner_id, request)
        except Exception:
            return None

    def _snapshot(self):
        learner = self.case.learner_id
        self.harness.load(learner)
        model = self.orchestrator.get_learner_model_sync(learner)
        plans = [
            public_data(json.loads(row[0])) for row in self.harness.db.execute(
                "SELECT body FROM learning_plans WHERE learner_id=? ORDER BY updated", (learner,)
            ).fetchall()
        ]
        quizzes = {
            identifier: public_data(json.loads(body))
            for identifier, body in self.harness.db.execute(
                "SELECT id,body FROM quizzes WHERE learner=?", (learner,)
            ).fetchall()
        }
        return {
            "knowledge": {
                key: state.model_dump(mode="json")
                for key, state in model.knowledge_states.items()
            },
            "plans": plans,
            "quizzes": quizzes,
            "memories": public_data(self.harness.history.memory.profile(learner)),
            "pending_questions": [
                {"id": row[0], "thread_id": row[1], "answered_by": row[2]}
                for row in self.harness.db.execute(
                    "SELECT id,thread,answered_by FROM pending_questions "
                    "WHERE learner=? ORDER BY rowid", (learner,)
                ).fetchall()
            ],
            "evidence": [
                {"quiz_id": row[0], "kind": row[1], "body": json.loads(row[2])}
                for row in self.harness.db.execute(
                    "SELECT quiz,kind,body FROM learning_evidence "
                    "WHERE learner=? ORDER BY rowid", (learner,)
                ).fetchall()
            ],
            "messages": [
                {"role": row[0], "content": row[1], "thread_id": row[2]}
                for row in self.harness.db.execute(
                    "SELECT role,content,thread FROM conversation_messages "
                    "WHERE learner=? ORDER BY rowid", (learner,)
                ).fetchall()
            ],
        }

    async def execute(self):
        observed = {"initial": self._snapshot(), "stages": {}}
        quiz_id = None
        for stage in self.case.stages:
            started = time.perf_counter()
            model_start = len(self.model_records)
            item = {"action": stage.action}
            try:
                if stage.action == "converse":
                    result = await self.harness.converse(
                        self.case.learner_id, stage.request_id, self.case.knowledge_id,
                        stage.student_input, session_id=stage.session_id,
                    )
                    if result.get("prepared_practice"):
                        quiz_id = result["prepared_practice"]["quiz_id"]
                elif stage.action == "restart":
                    self.restart()
                    result = {"status": "restarted"}
                elif stage.action == "process_memory":
                    await self.harness.memory_worker.process_once()
                    result = {"status": "processed"}
                else:
                    if not quiz_id:
                        raise ValueError("practice_not_available")
                    quiz = self.harness.quiz(self.case.learner_id, quiz_id)
                    if stage.action == "hint":
                        result = await self.harness.support(
                            self.case.learner_id, stage.request_id, quiz_id, "hint"
                        )
                    else:
                        selected = quiz["correct_index"]
                        if stage.action == "answer_wrong":
                            selected = (selected + 1) % len(quiz["options"])
                        result = await self.harness.answer(
                            self.case.learner_id, stage.request_id, quiz_id,
                            selected, 12, .6,
                        )
                item.update(status="completed", result=public_data(result))
            except Exception as exc:
                cause = exc
                while cause.__cause__ is not None:
                    cause = cause.__cause__
                if isinstance(cause, OptimizationStopped):
                    raise cause
                item.update(
                    status=("provider_error" if type(cause).__module__.startswith(
                        ("httpx", "openai")
                    ) else "execution_failed"),
                    error=type(cause).__name__,
                )
            item.update(
                duration_ms=(time.perf_counter() - started) * 1000,
                model_requests=self.model_records[model_start:],
                snapshot=self._snapshot(),
            )
            if stage.request_id:
                item["trace"] = self._trace(stage.request_id)
            observed["stages"][stage.id] = item
            if item["status"] != "completed":
                break
        observed["final"] = self._snapshot()
        return public_data(observed)
