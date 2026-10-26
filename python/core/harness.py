"""单进程执行边界：请求日志、原子检查点、超时和服务端测验。"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from config.settings import settings
from core.harness_migrations import migrate
from core.learner_model import KnowledgeState, LearnerModel
from core.learning_history import LearningHistory, public_data
from core.memory_retrieval import MemoryWorker
from core.run_context import RunContext, RunExhausted, active_run
from core.spaced_repetition import ReviewItem
from core.versions import runtime_metadata


class IssuedQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str = Field(min_length=1, max_length=6000)
    options: list[str] = Field(min_length=2, max_length=8)
    correct_index: StrictInt
    explanation: str = Field(default="", max_length=6000)


class LearningHarness:
    def __init__(self, orchestrator, path: str, timeout: float = 45,
                 quiz_ttl: float = 86400):
        self.orch = orchestrator
        self.timeout = timeout
        self.quiz_ttl = quiz_ttl
        self.lock = asyncio.Lock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # 拒绝多个 worker 使用同一检查点，避免进程间缓存覆盖。
        self._owner = open(path + ".lock", "a")
        try:
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._owner.close()
            raise RuntimeError("Harness store requires one server worker")
        try:
            self.db = sqlite3.connect(path)
            self.db.execute("PRAGMA journal_mode=WAL")
            migrate(self.db)
            self.history = LearningHistory(self.db)
            self.memory_worker = MemoryWorker(path)
        except BaseException:
            if hasattr(self, "db"):
                self.db.close()
            self._owner.close()
            raise
        with self.db:
            self.db.execute("UPDATE runs SET status='failed', error='interrupted before checkpoint' "
                            "WHERE status='running'")
            self.db.execute("UPDATE run_attempts SET status='failed',reason='interrupted',finished=? "
                            "WHERE status='running'", (time.time(),))

    def close(self):
        self.db.close()
        self._owner.close()

    def capture(self, learner):
        model = self.orch.get_learner_model_sync(learner)
        return {
            "knowledge": {k: s.model_dump(mode="json") for k, s in model.knowledge_states.items()},
            "metadata": model.metadata,
            "total_interactions": model.total_interactions,
            "agents": {a.name: a.get_state_for_save(learner) or {} for a in self.agents},
            "reviews": {k: v.model_dump(mode="json") for k, v in
                        self.orch.curriculum._review_items.get(learner, {}).items()},
            "errors": self.orch.assessment.get_error_patterns(learner),
        }

    @property
    def agents(self):
        return [self.orch.assessment, self.orch.tutor, self.orch.curriculum, self.orch.engagement]

    def restore(self, learner, state):
        model = LearnerModel(learner)
        model.knowledge_states = {k: KnowledgeState.model_validate(v)
                                  for k, v in state.get("knowledge", {}).items()}
        model.metadata = state.get("metadata", {})
        model.total_interactions = state.get("total_interactions", 0)
        self.orch.learner_models[learner] = model
        self.orch.memory_manager._cache[learner] = model
        for agent in self.agents:
            # 删除本轮增量，再从检查点恢复。
            for name in ("_conversation_history", "_topic_history", "_recent_submissions",
                         "_engagements", "_reminders"):
                getattr(agent, name, {}).pop(learner, None)
            for name in ("_student_attempts", "_hint_history"):
                table = getattr(agent, name, {})
                for key in list(table):
                    if key.startswith(learner + ":"):
                        del table[key]
            agent_state = state.get("agents", {}).get(agent.name, {})
            if agent_state:
                agent.load_state(learner, agent_state)
        self.orch.assessment._error_patterns[learner] = state.get("errors", [])
        self.orch.curriculum._review_items[learner] = {
            k: ReviewItem.model_validate(v) for k, v in state.get("reviews", {}).items()}

    def load(self, learner):
        if learner not in self.orch.learner_models:
            row = self.db.execute("SELECT state FROM checkpoints WHERE learner=?", (learner,)).fetchone()
            if row:
                self.restore(learner, json.loads(row[0]))

    async def run(self, learner, request_id, payload, operation):
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        async with self.lock:
            row = self.db.execute(
                "SELECT fingerprint,status,result FROM runs WHERE learner=? AND request=?",
                (learner, request_id)).fetchone()
            if row and row[0] != fingerprint:
                raise HTTPException(409, "request_id 已用于不同内容")
            if row and row[1] == "completed":
                return json.loads(row[2])
            self.load(learner)
            if learner not in self.orch.learner_models:
                if self.orch._db_initialized:
                    async with asyncio.timeout(self.timeout):
                        await self.orch.get_learner_model(learner)
                else:
                    self.orch.get_learner_model_sync(learner)
            before = json.loads(json.dumps(self.capture(learner)))
            previous_events = {event.id for event in self.orch.event_bus.get_history(limit=1000)}
            quiz_row = self.db.execute("SELECT body FROM quizzes WHERE id=? AND learner=?",
                                      (payload.get("quiz", payload.get("quiz_id", "")), learner)).fetchone()
            scoped_quiz = json.loads(quiz_row[0]) if quiz_row else {}
            knowledge = payload.get("knowledge_id", payload.get("knowledge",
                                    scoped_quiz.get("knowledge_id", "general")))
            session, thread = self.history.bind(
                learner, payload.get("session_id") or scoped_quiz.get("session_id"),
                payload.get("thread_id") or scoped_quiz.get("thread_id"), knowledge)
            ctx = RunContext(
                learner=learner,
                run_id=str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(["edu:run", learner, request_id]))),
                attempt_id=str(uuid.uuid4()), deadline=time.monotonic() + self.timeout,
                session_id=session, thread_id=thread, knowledge_id=knowledge, history=self.history,
                knowledge_graph=self.orch.curriculum.knowledge_graph,
                input_text=payload.get("text", ""),
                max_model_calls=settings.coordinator_max_model_calls,
                max_tool_calls=settings.coordinator_max_tool_calls,
            )
            metadata = runtime_metadata(settings)
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO runs "
                                "(learner,request,fingerprint,status,result,error,updated) "
                                "VALUES (?,?,?,'running',NULL,NULL,?)",
                                (learner, request_id, fingerprint, time.time()))
                self.db.execute(
                    "INSERT INTO run_attempts "
                    "(id,learner,request,run,status,reason,started,finished,"
                    "app_version,trace_schema_version,provider,model,config_fingerprint) "
                    "VALUES (?,?,?,?,?,NULL,?,NULL,?,?,?,?,?)",
                    (ctx.attempt_id, learner, request_id, ctx.run_id, "running",
                     time.time(), metadata["app_version"], metadata["trace_schema_version"],
                     metadata["provider"], metadata["model"],
                     metadata["config_fingerprint"]))
            token = active_run.set(ctx)
            ctx.record("run_started")
            try:
                async with asyncio.timeout(self.timeout):
                    result, quiz_update = await operation()
                result["execution"] = {
                    "request_id": request_id, "run_id": ctx.run_id, "attempt_id": ctx.attempt_id,
                    "session_id": ctx.session_id, "thread_id": ctx.thread_id, "status": "completed",
                    "dialogue_state": ctx.dialogue_state, "pending_question_id": ctx.pending_question,
                    "answered_question_id": ctx.answered_question_id,
                    "source_refs": ctx.source_refs, "retrieved_refs": ctx.retrieved_refs,
                    "read_refs": ctx.read_refs, "cited_refs": ctx.cited_refs, **metadata,
                }
                ctx.record("commit_started")
                # 学习状态、测验状态和可重放结果一起提交。
                with self.db:
                    self.history.open_scope(ctx)
                    if ctx.conversation:
                        self.history.commit_conversation(
                            ctx, payload["text"], result["teaching_response"]["response"])
                        if ctx.quiz:
                            evidence_ref = self.history.evidence(
                                ctx, "assistance", {"assisted": True, "source_refs": ctx.source_refs},
                                ctx.quiz["quiz_id"])
                            result["assistance"] = {"recorded": True, "source_ref": evidence_ref}
                    if result.get("learning_evidence"):
                        assessment = {**result["learning_evidence"],
                                      "knowledge_id": knowledge,
                                      "is_correct": result.get("evaluation", {}).get("is_correct"),
                                      "question": scoped_quiz.get("question", ""),
                                      "source_refs": ctx.source_refs}
                        if scoped_quiz and "selected" in payload:
                            assessment["student_answer"] = scoped_quiz["options"][payload["selected"]]
                        assessment_ref = self.history.evidence(ctx, "assessment", assessment, payload.get("quiz"))
                        if ctx.answered_question_id and result.get("evaluation", {}).get("is_correct"):
                            self.db.execute(
                                "UPDATE pending_questions SET answered_by=? WHERE id=? AND learner=?",
                                (assessment_ref, ctx.answered_question_id, learner))
                    self.db.execute(
                        "INSERT OR REPLACE INTO checkpoints (learner,state) VALUES (?,?)",
                                    (learner, json.dumps(self.capture(learner))))
                    if quiz_update:
                        quiz_id, quiz = quiz_update
                        self.db.execute(
                            "INSERT OR REPLACE INTO quizzes (id,learner,body) VALUES (?,?,?)",
                                        (quiz_id, learner, json.dumps(quiz)))
                    if ctx.plan:
                        self.db.execute(
                            "INSERT OR REPLACE INTO learning_plans VALUES (?,?,?,?,?,?,?)",
                            (ctx.plan["plan_id"], learner, ctx.plan_thread_id or ctx.thread_id, ctx.plan["version"],
                             ctx.plan["status"], json.dumps(ctx.plan, ensure_ascii=False), time.time()))
                    self.db.execute("UPDATE runs SET status='completed',result=?,updated=? "
                                    "WHERE learner=? AND request=?",
                                    (json.dumps(result), time.time(), learner, request_id))
                    ctx.record("run_completed", dialogue_state=ctx.dialogue_state)
                    self.history.save_steps(ctx)
                    self.db.execute("UPDATE run_attempts SET status='completed',finished=? WHERE id=?",
                                    (time.time(), ctx.attempt_id))
                return result
            except BaseException as exc:
                self.restore(learner, before)
                if ctx.steps and ctx.steps[-1]["kind"] == "run_completed":
                    ctx.steps.pop()
                trace = [event.model_dump(mode="json") for event in
                         self.orch.event_bus.get_history(learner_id=learner, limit=64)
                         if event.id not in previous_events]
                status = ("cancelled" if isinstance(exc, asyncio.CancelledError) else
                          "exhausted" if isinstance(exc, (RunExhausted, TimeoutError)) else "failed")
                reason = str(exc) if isinstance(exc, RunExhausted) else type(exc).__name__
                ctx.record("run_failed", status=status, reason=reason)
                with self.db:
                    self.db.execute("UPDATE runs SET status=?,error=?,result=?,updated=? "
                                    "WHERE learner=? AND request=?",
                                    (status, reason, json.dumps(public_data({"events": trace})),
                                     time.time(), learner, request_id))
                    self.history.save_steps(ctx)
                    self.db.execute("UPDATE run_attempts SET status=?,reason=?,finished=? WHERE id=?",
                                    (status, reason, time.time(), ctx.attempt_id))
                if isinstance(exc, HTTPException):
                    raise
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise HTTPException(503, "本次执行未完成，学习状态已回滚，请重试") from exc
            finally:
                active_run.reset(token)

    async def converse(self, learner, request_id, knowledge, text, session_id=None,
                       thread_id=None, quiz_id=None, kind="question"):
        payload = {"kind": kind, "knowledge_id": knowledge, "text": text,
                   "session_id": session_id, "thread_id": thread_id, "quiz_id": quiz_id}
        async def operation():
            ctx = active_run.get()
            from core.coordinator import Coordinator
            if not text.strip():
                raise HTTPException(422, "请输入问题或回应")
            ctx.conversation = True
            if re.search(r"(请)?记住[：:，, ]?|remember (that|my)", text, re.I):
                memory_kind = "goal" if re.search(r"目标|计划学|goal", text, re.I) else "preference"
                self.history.memory.propose(ctx, memory_kind, text[:1000], "current")
            ctx.model_state = self.orch.learner_models[learner].get_state(knowledge).model_dump(mode="json")
            model = self.orch.learner_models[learner]
            ctx.profile_state = {"knowledge_states": [
                state.model_dump(mode="json") for state in model.knowledge_states.values()]}
            ctx.review_queue = sorted(
                [{"knowledge_id": item.knowledge_id, "next_review": item.next_review.isoformat(),
                  "overdue_days": item.overdue_days, "reason": "scheduled_review_due"}
                 for item in self.orch.curriculum._review_items.get(learner, {}).values() if item.is_due],
                key=lambda item: -item["overdue_days"])
            async def prepare_practice(knowledge_id, difficulty=0.5):
                if ctx.quiz:
                    raise PermissionError("active_quiz")
                if ctx.prepared_quiz:
                    old_id, old = ctx.prepared_quiz
                    if old["knowledge_id"] != knowledge_id or old["difficulty"] != difficulty:
                        raise PermissionError("one_practice_per_run")
                    return self.public_question(old_id, old)
                public, update = await self.prepare_question(learner, knowledge_id, difficulty, "practice",
                                                              require_prerequisites=True)
                ctx.prepared_quiz = update
                return public
            ctx.prepare_practice = prepare_practice
            quiz = None
            bound_id = None
            if quiz_id:
                quiz = self.quiz(learner, quiz_id)
                bound_id = quiz_id
                if quiz["knowledge_id"] != knowledge:
                    raise HTTPException(422, "题目与知识点不匹配")
                if quiz["solved"] or quiz["revealed"]:
                    quiz = None
            else:
                # 旧客户端未发送题目 ID 时，也不能绕过受助记录。
                rows = self.db.execute("SELECT id,body FROM quizzes WHERE learner=? ORDER BY rowid DESC",
                                       (learner,)).fetchall()
                for identifier, body in rows:
                    candidate = json.loads(body)
                    if (candidate["knowledge_id"] == knowledge and not candidate["solved"]
                            and not candidate["revealed"] and
                            time.time() - candidate["created"] <= self.quiz_ttl):
                        bound_id, quiz = identifier, candidate
                        break
            if quiz:
                if (not thread_id and quiz.get("thread_id")
                        and not Coordinator.pending(ctx)
                        and not self.history.pending(learner, ctx.thread_id)):
                    _, ctx.thread_id = self.history.bind(
                        learner, ctx.session_id, quiz["thread_id"], knowledge)
                if quiz.get("mode") == "advance":
                    raise HTTPException(403, "独立测验期间请先作答，再进行本题讲解")
                # 仅在成功提交时更新受助状态；失败重试不污染测验。
                ctx.quiz = {**quiz, "quiz_id": bound_id}
                quiz["assisted"] = True
            from core.llm_service import get_llm_service
            pending_plan = Coordinator.pending(ctx) if settings.enable_coordinator else None
            pending_question = self.history.pending(learner, ctx.thread_id)
            if pending_plan or (not pending_question and
                                (kind == "task" or Coordinator.should_route(ctx, text))):
                ctx.record("task_routed", "Harness", route="Coordinator",
                           reason="awaiting_plan" if pending_plan else "task_intent")
                result = await Coordinator(ctx, get_llm_service()).run(text)
            else:
                ctx.record("task_routed", "Harness", route="Tutor",
                           reason="pending_question" if pending_question else "question_intent")
                method = self.orch.ask_question if kind in {"question", "task"} else self.orch.send_message
                result = (await method(learner, knowledge, text) if kind in {"question", "task"} else
                          await method(learner, text, knowledge))
            reply = result.get("teaching_response")
            if not reply or not reply.get("response", "").strip():
                raise RuntimeError("missing_teaching_response")
            if ctx.prepared_quiz:
                result["prepared_practice"] = self.public_question(*ctx.prepared_quiz)
            return result, (bound_id, quiz) if quiz else ctx.prepared_quiz
        return await self.run(learner, request_id, payload, operation)

    def run_status(self, learner, request_id):
        row = self.db.execute("SELECT status,result,error,updated FROM runs "
                              "WHERE learner=? AND request=?", (learner, request_id)).fetchone()
        if not row:
            raise HTTPException(404, "执行记录不存在")
        return {"request_id": request_id, "status": row[0],
                "result": json.loads(row[1]) if row[1] else None,
                "error": row[2], "updated": row[3]}

    def quiz(self, learner, quiz_id):
        row = self.db.execute("SELECT learner,body FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
        if not row or row[0] != learner:
            raise HTTPException(404, "测验不存在")
        quiz = json.loads(row[1])
        if time.time() - quiz["created"] > self.quiz_ttl:
            raise HTTPException(410, "测验已过期，请生成新题")
        return quiz

    async def generate(self, learner, request_id, knowledge, difficulty, mode="practice",
                       session_id=None, thread_id=None):
        async def operation():
            public, update = await self.prepare_question(learner, knowledge, difficulty, mode)
            return {"status": "ok", "quiz": public}, update
        return await self.run(learner, request_id, {"kind": "generate", "knowledge": knowledge,
                              "difficulty": difficulty, "mode": mode,
                              "session_id": session_id, "thread_id": thread_id}, operation)

    @staticmethod
    def public_question(quiz_id, quiz):
        return {"quiz_id": quiz_id, **{k: quiz[k] for k in
                                      ("question", "options", "knowledge_id", "difficulty")}}

    async def prepare_question(self, learner, knowledge, difficulty, mode, require_prerequisites=False):
        """领域内操作；仅父运行提交，专家不重新获取 Harness 锁。"""
        from core.llm_service import get_llm_service
        graph = self.orch.curriculum.knowledge_graph
        if knowledge not in graph.nodes:
            raise HTTPException(422, "未知知识点")
        if mode == "advance" or require_prerequisites:
            model = self.orch.learner_models[learner]
            mastered = {k for k, state in model.knowledge_states.items() if state.mastery >= 0.6}
            allowed = (knowledge in graph.get_ready_nodes(mastered) if mode == "advance" else
                       set(graph.nodes[knowledge].prerequisites) <= mastered)
            if not allowed:
                raise HTTPException(409, "前置知识尚未满足，请先练习基础知识点")
        raw = await get_llm_service().generate_question(knowledge, difficulty)
        if raw.get("source") == "fallback":
            raise HTTPException(422, "该知识点暂无可用题目，请选择其他知识点或配置模型")
        question = IssuedQuestion.model_validate(raw)
        if (not 0 <= question.correct_index < len(question.options)
                or any(not option.strip() for option in question.options)
                or len(set(question.options)) != len(question.options)):
            raise ValueError("invalid quiz options")
        ctx, quiz_id = active_run.get(), str(uuid.uuid4())
        quiz = {**question.model_dump(), "knowledge_id": knowledge, "difficulty": difficulty,
                "created": time.time(), "attempts": 0, "hints": 0, "revealed": False,
                "solved": False, "assisted": False, "mode": mode,
                "session_id": ctx.session_id,
                "thread_id": self.history.bind(learner, ctx.session_id, None, knowledge)[1]}
        if knowledge == ctx.knowledge_id:
            quiz["thread_id"] = ctx.thread_id
        return self.public_question(quiz_id, quiz), (quiz_id, quiz)

    async def answer(self, learner, request_id, quiz_id, selected, elapsed, confidence):
        async def operation():
            quiz = self.quiz(learner, quiz_id)
            if quiz["solved"] or quiz["revealed"]:
                raise HTTPException(409, "本题已结束，请开始新题")
            if selected < 0 or selected >= len(quiz["options"]):
                raise HTTPException(422, "选项无效")
            independent = quiz["attempts"] == 0 and quiz["hints"] == 0 and not quiz.get("assisted", False)
            correct = selected == quiz["correct_index"]
            quiz["attempts"] += 1
            quiz["solved"] = correct
            if correct:
                ctx = active_run.get()
                row = self.db.execute(
                    "SELECT body,thread_id FROM learning_plans WHERE learner_id=? "
                    "AND status='awaiting_student' AND json_extract(body,'$.practice_quiz_id')=?",
                    (learner, quiz_id)).fetchone()
                if row:
                    plan = json.loads(row[0])
                    ctx.plan_thread_id = row[1]
                    plan["version"] += 1
                    plan["status"] = "completed"
                    for step in plan["steps"]:
                        if step["status"] == "waiting":
                            step["status"] = "completed"
                    plan["outcome"] = ("completed" if not plan.get("checks") and all(
                        step["status"] == "completed" for step in plan["steps"]) else "partial")
                    ctx.plan = plan
                    pending = self.history.pending(learner, ctx.plan_thread_id)
                    ctx.answered_question_id = pending["id"] if pending else None
            feedback = ("判断正确。请用相同方法完成一道新题检验迁移。" if correct else
                        "这次还不正确。先检查题干中的关键线索，可以重试或主动请求提示。")
            result = await self.orch.submit_answer(
                learner, quiz["knowledge_id"], correct, elapsed,
                submission_context={"question": quiz["question"], "student_answer": quiz["options"][selected],
                                    "protected_quiz": True, "independent": independent},
                evaluation={"is_correct": correct, "feedback": feedback})
            result["learning_evidence"] = {
                "quiz_id": quiz_id, "attempt": quiz["attempts"], "independent": independent,
                "mastery_updated": independent, "hints_used": quiz["hints"],
                "assisted": quiz.get("assisted", False),
                "confidence": confidence,
                "outcome": "independent" if independent else "guided_practice",
            }
            # 输出只包含可公开的学习证据，避免后续 Agent 新增字段泄露答案。
            def public(value):
                if isinstance(value, dict):
                    return {k: public(v) for k, v in value.items()
                            if k not in {"correct_answer", "correct_index", "explanation"}}
                if isinstance(value, list):
                    return [public(v) for v in value]
                return value
            result = public(result)
            evidence = self.orch.learner_models[learner].metadata.setdefault("learning_evidence", [])
            evidence.append({**result["learning_evidence"], "is_correct": correct,
                             "knowledge_id": quiz["knowledge_id"], "timestamp": time.time(),
                             "elapsed": elapsed})
            del evidence[:-200]
            return result, (quiz_id, quiz)
        return await self.run(learner, request_id, {"kind": "answer", "quiz": quiz_id,
                              "selected": selected, "elapsed": elapsed, "confidence": confidence}, operation)

    async def support(self, learner, request_id, quiz_id, action):
        async def operation():
            quiz = self.quiz(learner, quiz_id)
            if quiz["revealed"] or (quiz["solved"] and action != "reveal"):
                raise HTTPException(409, "本题已结束，请开始新题")
            if action == "reveal":
                quiz["revealed"] = True
                text = f"参考答案：{quiz['options'][quiz['correct_index']]}。{quiz['explanation']}"
            else:
                if quiz.get("mode") == "advance":
                    raise HTTPException(403, "独立测验期间不能请求提示")
                quiz["hints"] += 1
                quiz["assisted"] = True
                hints = [
                    "先说清楚这道题要判断什么，再圈出题干中支持你选择的线索。",
                    "逐项排除：检查每个选项能否同时满足题干的语义和结构要求。",
                    "把候选选项代回原句，解释为什么适用，再检查另一个选项为什么不适用。",
                ]
                domain_hints = {
                    "vocab": "检查题目要求的是词义、反义还是搭配，结合语境与空格前后的词判断。",
                    "grammar": "先标出时间线索、主语与谓语关系，再检查候选形式是否满足这些约束。",
                    "reading": "先明确要抓主旨、细节还是推断，再选择与阅读目标对应的策略。",
                    "writing": "先检查表达目的，再判断各部分是否承担组织、支持和收束的功能。",
                }
                text = hints[min(quiz["hints"] - 1, 2)]
                if quiz["hints"] == 2:
                    text = domain_hints.get(quiz["knowledge_id"].split("_")[0], text)
            model = self.orch.learner_models[learner]
            key = "hints_used" if action == "hint" else "answers_revealed"
            model.metadata[key] = model.metadata.get(key, 0) + 1
            return {"status": "ok", "support": {"action": action, "text": text,
                    "hint_count": quiz["hints"], "finished": quiz["revealed"]}}, (quiz_id, quiz)
        return await self.run(learner, request_id, {"kind": action, "quiz": quiz_id}, operation)
