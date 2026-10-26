"""以 Harness SQLite 为事实源的公开教学历史与来源检索。"""

import json
import re
import time
import uuid

from fastapi import HTTPException
from core.memory_store import MemoryStore
from core.memory_retrieval import MemoryRetrieval


def public_data(value):
    """不将答案密钥和内部载荷写入公开轨迹。"""
    if isinstance(value, dict):
        return {key: public_data(item) for key, item in value.items()
                if key not in {"correct_answer", "correct_index", "explanation",
                               "api_key", "authorization", "system_prompt", "thinking"}}
    if isinstance(value, list):
        return [public_data(item) for item in value]
    return value


class LearningHistory:
    def __init__(self, db):
        self.db = db
        self.memory = MemoryStore(db)
        self.retrieval = MemoryRetrieval(db)

    def bind(self, learner, session, thread, knowledge):
        # 默认主题跨会话稳定；显式 ID 也必须验证归属。
        session = session or str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(["edu:session", learner])))
        thread = thread or str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(["edu:thread", learner, knowledge])))
        owner = self.db.execute("SELECT learner FROM learning_sessions WHERE id=?", (session,)).fetchone()
        scope = self.db.execute("SELECT learner,knowledge FROM learning_threads WHERE id=?", (thread,)).fetchone()
        if (owner and owner[0] != learner) or (scope and scope != (learner, knowledge)):
            raise HTTPException(404, "会话或主题不存在")
        return session, thread

    def open_scope(self, ctx):
        self.db.execute(
            "INSERT OR IGNORE INTO learning_sessions (id,learner,created) VALUES (?,?,?)",
                        (ctx.session_id, ctx.learner, time.time()))
        self.db.execute(
            "INSERT OR IGNORE INTO learning_threads (id,learner,knowledge) VALUES (?,?,?)",
                        (ctx.thread_id, ctx.learner, ctx.knowledge_id))

    def messages(self, learner, thread=None, limit=20, before=None, knowledge=None):
        limit = max(1, min(limit, 20))
        where, params = "learner=?", [learner]
        if thread:
            where += " AND thread=?"
            params.append(thread)
        if knowledge:
            where += " AND thread IN (SELECT id FROM learning_threads WHERE learner=? AND knowledge=?)"
            params.extend([learner, knowledge])
        if before is not None:
            where += " AND rowid<?"
            params.append(before)
        rows = self.db.execute(
            f"SELECT rowid,id,session,thread,role,content,created FROM conversation_messages "
            f"WHERE {where} ORDER BY rowid DESC LIMIT ?", (*params, limit + 1)).fetchall()
        selected = rows[:limit]
        return {"items": [{"cursor": r[0], "source_ref": "message:" + r[1],
                           "session_id": r[2], "thread_id": r[3], "role": r[4],
                           "content": r[5][:3000], "created": r[6]} for r in reversed(selected)],
                "next_cursor": selected[-1][0] if len(rows) > limit else None}

    def search(self, learner, knowledge, query="", limit=5):
        return {"items": [{k: v for k, v in item.items() if k != "content"} for item in
                          self.memory.lexical(learner, knowledge, query, max(1, min(limit, 10)))]}

    def read(self, learner, source_ref, offset=0, limit=3000):
        if offset or limit != 3000 or source_ref.startswith("memory:"):
            return self.memory.read(learner, source_ref, offset, limit)
        kind, _, identifier = source_ref.partition(":")
        if kind == "message":
            row = self.db.execute(
                "SELECT role,content,thread FROM conversation_messages WHERE id=? AND learner=?",
                (identifier, learner)).fetchone()
            if row:
                return {"source_ref": source_ref, "role": row[0], "content": row[1][:limit],
                        "thread_id": row[2], "truncated": len(row[1]) > limit,
                        "next_cursor": limit if len(row[1]) > limit else None}
        elif kind == "evidence":
            row = self.db.execute("SELECT kind,body FROM learning_evidence WHERE id=? AND learner=?",
                                  (identifier, learner)).fetchone()
            if row:
                if len(row[1]) > limit:
                    return self.memory.read(learner, source_ref, offset, limit)
                return {"source_ref": source_ref, "kind": row[0], "data": json.loads(row[1])}
        raise HTTPException(404, "历史证据不存在")

    def pending(self, learner, thread):
        row = self.db.execute(
            "SELECT id,question,run FROM pending_questions "
            "WHERE learner=? AND thread=? AND answered_by IS NULL ORDER BY rowid DESC LIMIT 1",
            (learner, thread)).fetchone()
        return {"id": row[0], "question": row[1], "run_id": row[2]} if row else None

    def save_steps(self, ctx):
        for step in ctx.steps:
            self.db.execute(
                "INSERT OR REPLACE INTO run_steps (attempt,seq,body) VALUES (?,?,?)",
                            (ctx.attempt_id, step["seq"], json.dumps(public_data(step), ensure_ascii=False)))

    def commit_conversation(self, ctx, text, reply):
        self.open_scope(ctx)
        user_id = str(uuid.uuid4())
        for identifier, role, content in ((user_id, "user", text),
                                          (str(uuid.uuid4()), "assistant", reply)):
            self.db.execute(
                "INSERT INTO conversation_messages "
                "(id,learner,session,thread,run,role,content,created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                            (identifier, ctx.learner, ctx.session_id, ctx.thread_id,
                             ctx.run_id, role, content, time.time()))
            self.memory.index(ctx.learner, "message:" + identifier)
        self.memory.commit(ctx, "message:" + user_id)
        from config.settings import settings
        count = self.db.execute("SELECT count(*) FROM conversation_messages WHERE learner=? AND thread=?",
                                (ctx.learner, ctx.thread_id)).fetchone()[0]
        if settings.memory_extraction_enabled and (
                count % settings.memory_episode_message_threshold < 2 or ctx.memory_proposals):
            self.memory.enqueue("message:" + identifier, kind="extract")
        if ctx.answered_question_id:
            self.db.execute("UPDATE pending_questions SET answered_by=? "
                            "WHERE id=? AND learner=? AND thread=? AND answered_by IS NULL",
                            (user_id, ctx.answered_question_id, ctx.learner, ctx.thread_id))
        if ctx.pending_question:
            self.db.execute(
                "INSERT INTO pending_questions "
                "(id,learner,thread,run,question,answered_by) VALUES (?,?,?,?,?,NULL)",
                            (ctx.pending_question, ctx.learner, ctx.thread_id, ctx.run_id, reply))

    def evidence(self, ctx, kind, body, quiz=None):
        identifier = str(uuid.uuid4())
        self.open_scope(ctx)
        self.db.execute(
            "INSERT INTO learning_evidence "
            "(id,learner,thread,run,quiz,kind,body,created) VALUES (?,?,?,?,?,?,?,?)",
                        (identifier, ctx.learner, ctx.thread_id, ctx.run_id, quiz, kind,
                         json.dumps(public_data(body), ensure_ascii=False), time.time()))
        self.memory.index(ctx.learner, "evidence:" + identifier)
        return "evidence:" + identifier

    def trace(self, learner, request):
        attempts = self.db.execute(
            "SELECT id,run,status,reason,started,finished,app_version,"
            "trace_schema_version,provider,model,config_fingerprint FROM run_attempts "
            "WHERE learner=? AND request=? ORDER BY rowid", (learner, request)).fetchall()
        if not attempts:
            raise HTTPException(404, "执行记录不存在")
        return {"request_id": request, "attempts": [
            {"attempt_id": row[0], "run_id": row[1], "status": row[2], "stop_reason": row[3],
             "started": row[4], "finished": row[5], "app_version": row[6],
             "trace_schema_version": row[7], "provider": row[8], "model": row[9],
             "config_fingerprint": row[10], "steps": [
                 json.loads(step[0]) for step in self.db.execute(
                     "SELECT body FROM run_steps WHERE attempt=? ORDER BY seq", (row[0],)).fetchall()]}
            for row in attempts]}
