"""以 Harness SQLite 为事实源的公开教学历史与来源检索。"""

import json
import re
import time
import uuid

from fastapi import HTTPException


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
        db.executescript("""
            CREATE TABLE IF NOT EXISTS learning_sessions (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS learning_threads (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, knowledge TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, session TEXT NOT NULL,
                thread TEXT NOT NULL, run TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS messages_scope
                ON conversation_messages(learner,thread,created);
            CREATE TABLE IF NOT EXISTS learning_evidence (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, thread TEXT NOT NULL,
                run TEXT NOT NULL, quiz TEXT, kind TEXT NOT NULL, body TEXT NOT NULL,
                created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS evidence_scope
                ON learning_evidence(learner,thread,created);
            CREATE TABLE IF NOT EXISTS run_attempts (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, request TEXT NOT NULL,
                run TEXT NOT NULL, status TEXT NOT NULL, reason TEXT,
                started REAL NOT NULL, finished REAL);
            CREATE TABLE IF NOT EXISTS run_steps (
                attempt TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY(attempt,seq));
            CREATE TABLE IF NOT EXISTS pending_questions (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, thread TEXT NOT NULL,
                run TEXT NOT NULL, question TEXT NOT NULL, answered_by TEXT);
        """)

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
        self.db.execute("INSERT OR IGNORE INTO learning_sessions VALUES (?,?,?)",
                        (ctx.session_id, ctx.learner, time.time()))
        self.db.execute("INSERT OR IGNORE INTO learning_threads VALUES (?,?,?)",
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
        # 知识点前置过滤；词项匹配和时间排序可解释，避免先引入向量库。
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", query.lower())[:16]
        rows = self.db.execute(
            "SELECT m.id,m.thread,m.role,m.content,m.created FROM conversation_messages m "
            "JOIN learning_threads t ON t.id=m.thread "
            "WHERE m.learner=? AND t.learner=? AND t.knowledge=? ORDER BY m.rowid DESC LIMIT 200",
            (learner, learner, knowledge)).fetchall()
        records = [("message:" + row[0], *row[1:]) for row in rows]
        evidence_rows = self.db.execute(
            "SELECT e.id,e.thread,e.body,e.created FROM learning_evidence e "
            "JOIN learning_threads t ON t.id=e.thread "
            "WHERE e.learner=? AND t.learner=? AND t.knowledge=? AND e.kind='assessment' "
            "ORDER BY e.rowid DESC LIMIT 200", (learner, learner, knowledge)).fetchall()
        records.extend(("evidence:" + row[0], row[1], "evidence", row[2], row[3])
                       for row in evidence_rows)
        records.sort(key=lambda row: row[4], reverse=True)
        scored = [(sum(token in row[3].lower() for token in tokens), i, row)
                  for i, row in enumerate(records)]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return {"items": [{"source_ref": row[0], "thread_id": row[1],
                           "role": row[2], "excerpt": row[3][:400], "created": row[4],
                           "match_score": score}
                          for score, _, row in scored[:max(1, min(limit, 10))]]}

    def read(self, learner, source_ref):
        kind, _, identifier = source_ref.partition(":")
        if kind == "message":
            row = self.db.execute(
                "SELECT role,content,thread FROM conversation_messages WHERE id=? AND learner=?",
                (identifier, learner)).fetchone()
            if row:
                return {"source_ref": source_ref, "role": row[0], "content": row[1][:3000],
                        "thread_id": row[2]}
        elif kind == "evidence":
            row = self.db.execute("SELECT kind,body FROM learning_evidence WHERE id=? AND learner=?",
                                  (identifier, learner)).fetchone()
            if row:
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
            self.db.execute("INSERT OR REPLACE INTO run_steps VALUES (?,?,?)",
                            (ctx.attempt_id, step["seq"], json.dumps(public_data(step), ensure_ascii=False)))

    def commit_conversation(self, ctx, text, reply):
        self.open_scope(ctx)
        user_id = str(uuid.uuid4())
        for identifier, role, content in ((user_id, "user", text),
                                          (str(uuid.uuid4()), "assistant", reply)):
            self.db.execute("INSERT INTO conversation_messages VALUES (?,?,?,?,?,?,?,?)",
                            (identifier, ctx.learner, ctx.session_id, ctx.thread_id,
                             ctx.run_id, role, content, time.time()))
        if ctx.answered_question_id:
            self.db.execute("UPDATE pending_questions SET answered_by=? "
                            "WHERE id=? AND learner=? AND thread=? AND answered_by IS NULL",
                            (user_id, ctx.answered_question_id, ctx.learner, ctx.thread_id))
        if ctx.pending_question:
            self.db.execute("INSERT INTO pending_questions VALUES (?,?,?,?,?,NULL)",
                            (ctx.pending_question, ctx.learner, ctx.thread_id, ctx.run_id, reply))

    def evidence(self, ctx, kind, body, quiz=None):
        identifier = str(uuid.uuid4())
        self.open_scope(ctx)
        self.db.execute("INSERT INTO learning_evidence VALUES (?,?,?,?,?,?,?,?)",
                        (identifier, ctx.learner, ctx.thread_id, ctx.run_id, quiz, kind,
                         json.dumps(public_data(body), ensure_ascii=False), time.time()))
        return "evidence:" + identifier

    def trace(self, learner, request):
        attempts = self.db.execute(
            "SELECT id,run,status,reason,started,finished FROM run_attempts "
            "WHERE learner=? AND request=? ORDER BY rowid", (learner, request)).fetchall()
        if not attempts:
            raise HTTPException(404, "执行记录不存在")
        return {"request_id": request, "attempts": [
            {"attempt_id": row[0], "run_id": row[1], "status": row[2], "stop_reason": row[3],
             "started": row[4], "finished": row[5], "steps": [
                 json.loads(step[0]) for step in self.db.execute(
                     "SELECT body FROM run_steps WHERE attempt=? ORDER BY seq", (row[0],)).fetchall()]}
            for row in attempts]}
