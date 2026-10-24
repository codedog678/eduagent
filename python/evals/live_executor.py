"""用真实 Harness 执行固定学生脚本，每条拥有独立临时 SQLite。"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time

from fastapi import HTTPException

from api.orchestrator import AgentOrchestrator
from core.harness import LearningHarness
from core.learner_model import LearnerModel
from core.learning_history import public_data
from core.run_context import RunContext, RunExhausted
from core.tutor_runtime import ContextBuilder
from evals.live_budget import LiveBudget
from evals.live_cases import LiveCase


class LiveExecutor:
    def __init__(self, case: LiveCase, service, budget: LiveBudget):
        self.case, self.service, self.budget = case, service, budget
        self._temporary = tempfile.TemporaryDirectory(prefix="eduagent-live-")
        self.orchestrator = AgentOrchestrator(enable_db_logging=False)
        self.harness = LearningHarness(
            self.orchestrator, str(Path(self._temporary.name) / "harness.sqlite3")
        )
        self.orchestrator.harness = self.harness
        self.turns, self.tool_results = [], []
        self.case_requests = 0
        self._original_turn = service.tool_turn
        self._overrides = {name: (name in service.__dict__, service.__dict__.get(name))
                           for name in ("tool_turn", "generate")}
        service.tool_turn = self._metered_turn
        service.generate = self._forbid_extra_generation
        try:
            self._seed()
        except BaseException:
            self.close()
            raise

    def close(self):
        for name, (had_override, value) in self._overrides.items():
            if had_override:
                setattr(self.service, name, value)
            else:
                del self.service.__dict__[name]
        self.harness.close()
        self._temporary.cleanup()

    async def _forbid_extra_generation(self, *args, **kwargs):
        raise RunExhausted("unexpected_non_tutor_model_request")

    async def _metered_turn(self, messages, tools, max_tokens):
        if self.case_requests >= self.case.expected_model_requests_max:
            raise RunExhausted("live_case_request_budget")
        # 仅保存公开工具结果与模型返回，系统提示和隐藏思考不进入报告。
        for message in messages:
            if message["role"] == "tool" and message["tool_call_id"] not in {
                item["tool_call_id"] for item in self.tool_results
            }:
                self.tool_results.append({
                    "tool_call_id": message["tool_call_id"],
                    "result": public_data(json.loads(message["content"])),
                })
        index = self.budget.reserve(messages, tools, max_tokens)
        self.case_requests += 1
        started = time.perf_counter()
        try:
            turn = await self._original_turn(messages, tools, max_tokens)
        except BaseException as exc:
            self.turns.append({"request_no": self.budget.ledger[index]["request_no"],
                               "error": type(exc).__name__, "tool_calls": [],
                               "duration_ms": (time.perf_counter() - started) * 1000})
            raise
        self.budget.settle(index, turn.usage)
        tool_calls = []
        for call in turn.tool_calls:
            try:
                arguments = public_data(json.loads(call.arguments))
                if not isinstance(arguments, dict):
                    arguments = {}
            except ValueError:
                arguments = {"invalid_json": True}
            tool_calls.append({"id": call.id, "name": call.name, "arguments": arguments,
                               "batch_size": len(turn.tool_calls)})
        self.turns.append({
            "request_no": self.budget.ledger[index]["request_no"],
            "content": turn.content, "tool_calls": tool_calls,
            "stop_reason": turn.stop_reason, "usage": turn.usage,
            "duration_ms": (time.perf_counter() - started) * 1000,
        })
        return turn

    def _fresh_learner(self, learner):
        model = LearnerModel(learner)
        model.get_state(self.case.knowledge_id)
        self.orchestrator.learner_models[learner] = model
        self.orchestrator.memory_manager._cache[learner] = model

    def _scope(self, learner, session, knowledge=None):
        knowledge = knowledge or self.case.knowledge_id
        session, thread = self.harness.history.bind(learner, session, None, knowledge)
        ctx = RunContext(learner=learner, run_id="fixture", attempt_id="fixture",
                         deadline=time.monotonic() + 45, session_id=session,
                         thread_id=thread, knowledge_id=knowledge)
        self.harness.history.open_scope(ctx)
        return ctx

    def _message(self, item, *, owner=None, knowledge=None):
        learner = owner or self.case.learner_id
        ctx = self._scope(learner, item["session_id"], knowledge)
        self.harness.db.execute(
            "INSERT INTO conversation_messages "
            "(id,learner,session,thread,run,role,content,created) VALUES (?,?,?,?,?,?,?,?)",
            (item["message_id"], learner, ctx.session_id, ctx.thread_id,
             "fixture", item["role"], item["content"], time.time()),
        )

    def _seed_quiz(self, source, correct_index, explanation=""):
        quiz = {**source, "correct_index": correct_index, "explanation": explanation,
                "knowledge_id": self.case.knowledge_id, "session_id": self.ctx.session_id,
                "thread_id": self.ctx.thread_id, "created": time.time()}
        with self.harness.db:
            self.harness.db.execute("INSERT INTO quizzes (id,learner,body) VALUES (?,?,?)",
                                    (quiz["quiz_id"], self.case.learner_id, json.dumps(quiz)))

    def _seed(self):
        facts = self.case.initial_facts
        self._fresh_learner(self.case.learner_id)
        with self.harness.db:
            self.ctx = self._scope(self.case.learner_id, self.case.steps[0].session_id)
            for item in facts.get("history", []):
                self._message(item)
            recipe = facts.get("history_recipe")
            if recipe:
                target = recipe["target"]
                repeat = target["content_repeat"]
                self._message({**target, "session_id": recipe["session_id"],
                               "content": target["content_prefix"] + repeat["text"] * repeat["count"]
                               + target["content_suffix"]})
                decoys = recipe["decoys"]
                for index in range(1, decoys["count"] + 1):
                    self._message({
                        "message_id": decoys["message_id_template"].format(index=index),
                        "session_id": recipe["session_id"], "role": decoys["role"],
                        "content": decoys["content_template"].format(index=index),
                    })
            for item in facts.get("foreign_history", []):
                self._fresh_learner(item["owner"])
                self._message(item, owner=item["owner"], knowledge=item["knowledge_id"])
        if facts.get("quiz"):
            private = facts["evaluator_only"]
            self._seed_quiz(facts["quiz"], private.get("correct_index", private.get("q1_correct_index")),
                            private.get("explanation", ""))

    def _quizzes(self):
        return {identifier: public_data(json.loads(body)) for identifier, body in
                self.harness.db.execute("SELECT id,body FROM quizzes WHERE learner=?",
                                        (self.case.learner_id,)).fetchall()}

    def _knowledge(self):
        return {learner: model.get_state(self.case.knowledge_id).model_dump(mode="json")
                for learner, model in self.orchestrator.learner_models.items()}

    def _evidence(self):
        return [{"source_ref": "evidence:" + row[0], "quiz_id": row[1],
                 "kind": row[2], "body": json.loads(row[3])}
                for row in self.harness.db.execute(
                    "SELECT id,quiz,kind,body FROM learning_evidence WHERE learner=? ORDER BY rowid",
                    (self.case.learner_id,)).fetchall()]

    def validate_fixture(self):
        knowledge = self._knowledge()[self.case.learner_id]
        self.ctx.history = self.harness.history
        self.ctx.model_state = knowledge
        quizzes = self._quizzes()
        if quizzes:
            self.ctx.quiz = next(iter(quizzes.values()))
        messages, selected = ContextBuilder().build(self.ctx, self.case.steps[0].student_input)
        serialized = json.dumps(messages, ensure_ascii=False)
        checks = {
            "default_knowledge": knowledge["mastery"] == 0.1 and knowledge["attempts"] == 0
            and knowledge["alpha"] == 1 and knowledge["beta"] == 9,
            "no_answer_fields_in_context": not any(
                f'"{key}"' in serialized for key in ("correct_index", "explanation")
            ),
            "no_preexisting_pending": self.harness.history.pending(
                self.case.learner_id, self.ctx.thread_id) is None,
        }
        if self.case.number == 7:
            checks["seeded_history_visible"] = self.case.history_source_refs <= {
                item["source_ref"] for item in selected
            }
        if self.case.number == 8:
            target_ref = self.case.target_source_ref
            target = self.harness.history.read(self.case.learner_id, target_ref)
            query, phrase = self.case.retrieval_expectations
            search = self.harness.history.search(self.case.learner_id, self.case.knowledge_id, query, 10)
            checks.update(
                target_not_in_initial=target_ref not in serialized,
                phrase_not_in_initial=phrase not in serialized,
                target_fits_read=len(target["content"]) <= 3000,
                phrase_beyond_excerpt=target["content"].find(phrase) >= 400,
                search_hides_phrase=phrase not in json.dumps(search, ensure_ascii=False),
                target_discoverable=any(item["source_ref"] == target_ref
                                        for item in search["items"]),
            )
        if self.case.number == 10:
            foreign = self.case.initial_facts["foreign_history"][0]
            _, marker = self.case.foreign_expectations
            checks["foreign_content_not_visible"] = (
                marker not in serialized and foreign["content"] not in serialized
            )
            try:
                self.harness.history.read(self.case.learner_id, "message:" + foreign["message_id"])
            except HTTPException as exc:
                checks["foreign_source_denied"] = exc.status_code == 404
            else:
                checks["foreign_source_denied"] = False
        return {"valid": all(checks.values()), "checks": checks,
                "initial_source_refs": [item["source_ref"] for item in selected]}

    async def execute(self):
        initial = {"knowledge": self._knowledge(), "quizzes": self._quizzes(),
                   "thread_id": self.ctx.thread_id}
        fixture = self.validate_fixture()
        observed = {"initial": initial, "fixture_validation": fixture, "steps": {}}
        if fixture["valid"]:
            for index, step in enumerate(self.case.steps):
                previous = observed["steps"].get(f"s{index}", {})
                previous_result = previous.get("result", {})
                allowed = index == 0 or previous.get("status") == "completed"
                if index == 1 and self.case.number in (5, 6):
                    allowed = allowed and previous_result.get("execution", {}).get(
                        "dialogue_state") == "awaiting_student"
                if step.action == "seed_new_quiz_local":
                    allowed = allowed and previous.get("quizzes", {}).get(
                        self.case.initial_facts["quiz"]["quiz_id"], {}).get("solved") is True
                if not allowed or self.budget.exhausted and step.action == "converse":
                    observed["steps"][step.id] = {
                        "status": "blocked_by_prior_step" if not allowed else "batch_budget_exhausted"
                    }
                    continue
                started = time.perf_counter()
                turn_start, tool_start = len(self.turns), len(self.tool_results)
                item = {"action": step.action, "student_input": step.student_input}
                request = self.case.case_id + "-" + step.id
                try:
                    if step.action == "converse":
                        result = await self.harness.converse(
                            self.case.learner_id, request, self.case.knowledge_id,
                            step.student_input, session_id=step.session_id, quiz_id=step.quiz_id,
                        )
                    elif step.action == "answer":
                        result = await self.harness.answer(
                            self.case.learner_id, request, step.quiz_id, **step.api_input
                        )
                    else:
                        source = self.case.initial_facts["evaluator_only"]["new_quiz_after_q1"]
                        self._seed_quiz(source, source["correct_index"], source["explanation"])
                        result = {"status": "seeded_locally"}
                    item.update(status="completed", result=public_data(result))
                except Exception as exc:
                    item.update(status="execution_failed", error=type(exc).__name__)
                if step.action != "seed_new_quiz_local":
                    try:
                        item["trace"] = self.harness.history.trace(self.case.learner_id, request)
                        if item["status"] != "completed":
                            attempt = item["trace"]["attempts"][-1]
                            item.update(status=attempt["status"], stop_reason=attempt["stop_reason"])
                    except HTTPException:
                        pass
                item.update(
                    model_turns=self.turns[turn_start:], tool_results=self.tool_results[tool_start:],
                    quizzes=self._quizzes(), knowledge=self._knowledge(), evidence=self._evidence(),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
                item["all_sources_readable"] = True
                for ref in item.get("result", {}).get("execution", {}).get("source_refs", []):
                    try:
                        self.harness.history.read(self.case.learner_id, ref)
                    except HTTPException:
                        item["all_sources_readable"] = False
                observed["steps"][step.id] = item
        observed["final"] = {
            "knowledge": self._knowledge(), "quizzes": self._quizzes(), "evidence": self._evidence(),
            "pending_questions": [
                {"id": row[0], "answered_by": row[1]} for row in self.harness.db.execute(
                    "SELECT id,answered_by FROM pending_questions WHERE learner=?",
                    (self.case.learner_id,)).fetchall()
            ],
            "assistant_history": [
                row[0] for row in self.harness.db.execute(
                    "SELECT content FROM conversation_messages WHERE learner=? AND role='assistant'",
                    (self.case.learner_id,)).fetchall()
            ],
        }
        return public_data(observed)
