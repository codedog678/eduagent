"""单进程执行边界：请求日志、原子检查点、超时和服务端测验。"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from core.learner_model import KnowledgeState, LearnerModel
from core.spaced_repetition import ReviewItem


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
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                learner TEXT, request TEXT, fingerprint TEXT, status TEXT,
                result TEXT, error TEXT, updated REAL,
                PRIMARY KEY (learner, request));
            CREATE TABLE IF NOT EXISTS checkpoints (learner TEXT PRIMARY KEY, state TEXT);
            CREATE TABLE IF NOT EXISTS quizzes (id TEXT PRIMARY KEY, learner TEXT, body TEXT);
        """)
        with self.db:
            self.db.execute("UPDATE runs SET status='failed', error='interrupted before checkpoint' "
                            "WHERE status='running'")

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
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,'running',NULL,NULL,?)",
                                (learner, request_id, fingerprint, time.time()))
            try:
                async with asyncio.timeout(self.timeout):
                    result, quiz_update = await operation()
                result["execution"] = {"request_id": request_id, "status": "completed"}
                # 学习状态、测验状态和可重放结果一起提交。
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?)",
                                    (learner, json.dumps(self.capture(learner))))
                    if quiz_update:
                        quiz_id, quiz = quiz_update
                        self.db.execute("INSERT OR REPLACE INTO quizzes VALUES (?,?,?)",
                                        (quiz_id, learner, json.dumps(quiz)))
                    self.db.execute("UPDATE runs SET status='completed',result=?,updated=? "
                                    "WHERE learner=? AND request=?",
                                    (json.dumps(result), time.time(), learner, request_id))
                return result
            except BaseException as exc:
                self.restore(learner, before)
                trace = [event.model_dump(mode="json") for event in
                         self.orch.event_bus.get_history(learner_id=learner, limit=64)
                         if event.id not in previous_events]
                with self.db:
                    self.db.execute("UPDATE runs SET status='failed',error=?,result=?,updated=? "
                                    "WHERE learner=? AND request=?",
                                    (type(exc).__name__, json.dumps({"events": trace}),
                                     time.time(), learner, request_id))
                if isinstance(exc, HTTPException):
                    raise
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise HTTPException(503, "本次执行未完成，学习状态已回滚，请重试") from exc

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

    async def generate(self, learner, request_id, knowledge, difficulty, mode="practice"):
        async def operation():
            from core.llm_service import get_llm_service
            if knowledge not in self.orch.curriculum.knowledge_graph.nodes:
                raise HTTPException(422, "未知知识点")
            if mode == "advance":
                model = self.orch.learner_models[learner]
                mastered = {k for k, state in model.knowledge_states.items() if state.mastery >= 0.6}
                ready = self.orch.curriculum.knowledge_graph.get_ready_nodes(mastered)
                if knowledge not in ready:
                    raise HTTPException(409, "前置知识尚未满足，请先练习基础知识点")
            raw = await get_llm_service().generate_question(knowledge, difficulty)
            if raw.get("source") == "fallback":
                raise HTTPException(422, "该知识点暂无可用题目，请选择其他知识点或配置模型")
            question = IssuedQuestion.model_validate(raw)
            if (not 0 <= question.correct_index < len(question.options)
                    or any(not option.strip() for option in question.options)
                    or len(set(question.options)) != len(question.options)):
                raise ValueError("invalid quiz options")
            quiz_id = str(uuid.uuid4())
            quiz = {**question.model_dump(), "knowledge_id": knowledge, "difficulty": difficulty,
                    "created": time.time(), "attempts": 0, "hints": 0, "revealed": False,
                    "solved": False}
            public = {k: quiz[k] for k in ("question", "options", "knowledge_id", "difficulty")}
            return {"status": "ok", "quiz": {**public, "quiz_id": quiz_id}}, (quiz_id, quiz)
        return await self.run(learner, request_id, {"kind": "generate", "knowledge": knowledge,
                              "difficulty": difficulty, "mode": mode}, operation)

    async def answer(self, learner, request_id, quiz_id, selected, elapsed, confidence):
        async def operation():
            quiz = self.quiz(learner, quiz_id)
            if quiz["solved"] or quiz["revealed"]:
                raise HTTPException(409, "本题已结束，请开始新题")
            if selected < 0 or selected >= len(quiz["options"]):
                raise HTTPException(422, "选项无效")
            independent = quiz["attempts"] == 0 and quiz["hints"] == 0
            correct = selected == quiz["correct_index"]
            quiz["attempts"] += 1
            quiz["solved"] = correct
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
                quiz["hints"] += 1
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
