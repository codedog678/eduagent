"""带来源和版本的派生记忆；SQLite 原文始终是权威事实源。"""

import hashlib
import json
import re
import time
import uuid

from fastapi import HTTPException


def terms(text):
    """英文词项与中文一/二元词；避免 FTS 默认分词把中文整句当作一个词。"""
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    result = []
    for word in words:
        if re.match(r"[\u4e00-\u9fff]", word):
            result.extend(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        else:
            result.append(word)
    return list(dict.fromkeys(result))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def create_schema(db):
    for sql in (
        """CREATE TABLE memory_items (
        id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, kind TEXT NOT NULL,
        scope TEXT NOT NULL, knowledge_id TEXT NOT NULL, content TEXT NOT NULL,
        source_refs TEXT NOT NULL, origin_run_id TEXT, origin_role TEXT,
        evidence_type TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
        supersedes_id TEXT, valid_from REAL, valid_until REAL, updated_at REAL,
        extraction_model TEXT, extraction_prompt_version TEXT, confidence REAL)""",
        """CREATE INDEX memory_scope ON memory_items(learner_id, status, kind)""",
        """CREATE TABLE memory_chunks (
        chunk_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, knowledge_id TEXT NOT NULL,
        source_ref TEXT NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL,
        source_version INTEGER NOT NULL, created REAL NOT NULL)""",
        """CREATE VIRTUAL TABLE memory_fts USING fts5(chunk_id UNINDEXED, tokens)""",
        """CREATE TABLE memory_embeddings (
        chunk_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
        dimension INTEGER NOT NULL, content_hash TEXT NOT NULL, vector TEXT NOT NULL,
        PRIMARY KEY(chunk_id,provider,model))""",
        """CREATE TABLE memory_jobs (
        id INTEGER PRIMARY KEY, source_ref TEXT NOT NULL, source_version INTEGER NOT NULL,
        job_kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, next_retry_at REAL NOT NULL DEFAULT 0,
        last_error TEXT, usage TEXT, elapsed_ms REAL,
        UNIQUE(source_ref,source_version,job_kind))""",
        """CREATE TABLE learning_plans (
        id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, thread_id TEXT NOT NULL,
        version INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, updated REAL)""",
    ):
        db.execute(sql)
    # 已有原文也进入可靠作业队列，升级不要求用户重新发一次消息。
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, prefix in (("conversation_messages", "message"), ("learning_evidence", "evidence")):
        if table in tables:
            db.execute("INSERT INTO memory_jobs(source_ref,source_version,job_kind) "
                       f"SELECT '{prefix}:'||id,1,'index' FROM {table}")


class MemoryProposalError(ValueError):
    """可向模型返回的固定校验码，不包含输入原文或其他学习者数据。"""


class MemoryStore:
    def __init__(self, db):
        self.db = db

    def source(self, learner, ref):
        kind, _, identifier = ref.partition(":")
        if kind in {"message", "evidence"}:
            table = "conversation_messages" if kind == "message" else "learning_evidence"
            column = "content" if kind == "message" else "body"
            role = "role" if kind == "message" else "'evidence'"
            row = self.db.execute(
                f"SELECT s.{column},t.knowledge,s.created,{role},s.thread FROM {table} s "
                "JOIN learning_threads t ON s.thread=t.id AND s.learner=t.learner "
                "WHERE s.id=? AND s.learner=?", (identifier, learner)).fetchone()
            if row:
                return dict(content=row[0], knowledge_id=row[1], created=row[2],
                            role=row[3], thread_id=row[4], source_ref=ref, version=1)
        if kind == "memory":
            row = self.db.execute(
                "SELECT content,knowledge_id,updated_at,version,source_refs,kind,evidence_type,valid_until "
                "FROM memory_items "
                "WHERE id=? AND learner_id=? AND status='active' "
                "AND (valid_until IS NULL OR valid_until>?)", (identifier, learner, time.time())).fetchone()
            if row and all(self.source(learner, r) for r in json.loads(row[4])):
                return dict(content=row[0], knowledge_id=row[1], created=row[2],
                            role="memory", source_ref=ref, version=row[3],
                            source_refs=json.loads(row[4]), memory_id=identifier,
                            kind=row[5], evidence_type=row[6], valid_until=row[7])
        return None

    def enqueue(self, ref, version=1, kind="index"):
        self.db.execute("INSERT OR IGNORE INTO memory_jobs "
                        "(source_ref,source_version,job_kind) VALUES (?,?,?)", (ref, version, kind))

    def index(self, learner, ref):
        source = self.source(learner, ref)
        if not source:
            return
        text = source["content"]
        old_ids = {r[0] for r in self.db.execute(
            "SELECT chunk_id FROM memory_chunks WHERE source_ref=?", (ref,))}
        new_ids = set()
        for index, offset in enumerate(range(0, max(1, len(text)), 1100)):
            chunk_text = text[offset:offset+1200]
            chunk_id = digest(ref if index == 0 else f"{ref}#chunk{index}")
            new_ids.add(chunk_id)
            self.db.execute("DELETE FROM memory_fts WHERE chunk_id=?", (chunk_id,))
            self.db.execute("DELETE FROM memory_embeddings WHERE chunk_id=? AND content_hash<>?",
                            (chunk_id, digest(chunk_text)))
            self.db.execute("INSERT OR REPLACE INTO memory_chunks VALUES (?,?,?,?,?,?,?,?)",
                            (chunk_id, learner, source["knowledge_id"], ref, chunk_text, digest(chunk_text),
                             source["version"], source["created"]))
            indexed_text = self.search_text(source) if source["role"] == "evidence" else chunk_text
            self.db.execute("INSERT INTO memory_fts VALUES (?,?)",
                            (chunk_id, " ".join(terms(indexed_text))))
        for chunk_id in old_ids - new_ids:
            self.db.execute("DELETE FROM memory_fts WHERE chunk_id=?", (chunk_id,))
            self.db.execute("DELETE FROM memory_embeddings WHERE chunk_id=?", (chunk_id,))
            self.db.execute("DELETE FROM memory_chunks WHERE chunk_id=?", (chunk_id,))
        self.enqueue(ref, source["version"], "embed")

    def lexical(self, learner, knowledge, query, limit=20):
        tokens = terms(query)
        if not tokens:
            return []
        match = " OR ".join('"' + token + '"' for token in tokens[:32])
        # learner/知识点先过滤；稳定画像允许跨主题，其他内容保持知识范围。
        rows = self.db.execute(
            "SELECT c.source_ref,bm25(memory_fts),c.text FROM memory_fts "
            "JOIN memory_chunks c ON c.chunk_id=memory_fts.chunk_id "
            "WHERE memory_fts MATCH ? AND c.learner_id=? "
            "AND (c.knowledge_id=? OR c.knowledge_id='*') ORDER BY bm25(memory_fts) LIMIT ?",
            (match, learner, knowledge, limit * 3)).fetchall()
        result = []
        seen = set()
        for ref, score, chunk_text in rows:
            source = self.source(learner, ref)
            if source and chunk_text in source["content"] and ref not in seen:
                result.append({**source, "excerpt": chunk_text[:400], "match_score": -score})
                seen.add(ref)
            if len(result) == limit:
                break
        # 索引尚未建立的合法原文也可检索；不把无命中记录充作相关历史。
        unindexed = []
        for table, column, prefix in (("conversation_messages", "content", "message"),
                                      ("learning_evidence", "body", "evidence")):
            rows = self.db.execute(
                f"SELECT s.id,s.{column} FROM {table} s "
                "JOIN learning_threads t ON t.id=s.thread AND t.learner=s.learner "
                "LEFT JOIN memory_chunks c ON c.source_ref=?||s.id "
                "WHERE s.learner=? AND t.knowledge=? AND c.chunk_id IS NULL",
                (prefix + ":", learner, knowledge))
            for identifier, text in rows:
                source = self.source(learner, prefix + ":" + identifier)
                score = len(set(tokens) & set(terms(self.search_text(source))))
                if score:
                    unindexed.append({**source, "excerpt": text[:400], "match_score": score})
        unindexed.sort(key=lambda item: (-item["match_score"], -item["created"]))
        result.extend(unindexed[:limit])
        return result[:limit]

    @staticmethod
    def search_text(source):
        text = source["content"]
        if source["role"] == "evidence":
            data = json.loads(text)
            if data.get("is_correct") is False:
                text += " wrong error mistake 错误 错题"
            if data.get("independent") is True:
                text += " independent 独立"
            if data.get("assisted") is True:
                text += " assisted 受助"
        return text

    def profile(self, learner):
        refs = self.db.execute(
            "SELECT id FROM memory_items WHERE learner_id=? AND status='active' "
            "AND kind IN ('preference','goal') ORDER BY updated_at DESC LIMIT 12",
            (learner,)).fetchall()
        return [source for row in refs if (source := self.source(learner, "memory:" + row[0]))]

    def write_state(self, ctx):
        """描述已接受的提案；实际保存仍由回复后的父事务完成。"""
        items, staged_kinds = [], set()
        for proposal in ctx.memory_proposals:
            kind = proposal["kind"]
            active = self.db.execute(
                "SELECT 1 FROM memory_items WHERE learner_id=? AND kind=? AND status='active'",
                (ctx.learner, kind)).fetchone()
            conflict = bool((active or kind in staged_kinds) and not proposal["supersedes_id"])
            items.append({"kind": kind, "content": proposal["content"],
                          "requires_confirmation": conflict and not proposal["retract"],
                          "action": "retract" if proposal["retract"] else "save"})
            staged_kinds.add(kind)
        return {"state": "pending_commit" if items else "not_staged",
                "accepted_count": len(items), "items": items}

    def propose(self, ctx, kind, content, source_ref, supersedes_id=None, retract=False):
        """只接受原文中的明确陈述；模型不能自造来源或把自评转成掌握度。"""
        if kind not in {"preference", "goal", "episode"}:
            raise ValueError("unsupported_memory_kind")
        if retract and not supersedes_id:
            raise ValueError("retraction_requires_memory_id")
        if source_ref == "current":
            original = ctx.input_text
        else:
            source = self.source(ctx.learner, source_ref)
            if not source or source["role"] != "user":
                raise PermissionError("unavailable_source")
            original = source["content"]
        if not content.strip() or content not in original:
            raise MemoryProposalError("memory_requires_verbatim_student_statement")
        if supersedes_id:
            old = self.db.execute("SELECT kind FROM memory_items WHERE id=? AND learner_id=? "
                                  "AND status='active'", (supersedes_id, ctx.learner)).fetchone()
            if not old or old[0] != kind:
                raise PermissionError("unavailable_memory")
        proposal = dict(kind=kind, content=content, source_ref=source_ref,
                        supersedes_id=supersedes_id, retract=retract)
        # 自动暂存可能包含整条学生消息；模型再选取其中原话时复用该提案。
        # 参数和来源仍先经过校验，不能用已有提案放行改写或伪造内容。
        if not retract and any(
                p["kind"] == kind and p["source_ref"] == source_ref
                and p["supersedes_id"] == supersedes_id and not p["retract"]
                and content in p["content"] for p in ctx.memory_proposals):
            return {"staged": True, "already_staged": True, "content": content,
                    "evidence_type": "user_statement"}
        if proposal not in ctx.memory_proposals:
            ctx.memory_proposals.append(proposal)
        return {"staged": True, "content": content, "evidence_type": "user_statement"}

    def commit(self, ctx, user_ref):
        for proposal in ctx.memory_proposals:
            ref = user_ref if proposal["source_ref"] == "current" else proposal["source_ref"]
            if not self.source(ctx.learner, ref):
                raise ValueError("uncommitted_memory_source")
            previous = proposal["supersedes_id"]
            version = 1
            if previous:
                old = self.db.execute("SELECT version FROM memory_items WHERE id=? AND learner_id=? "
                                      "AND status='active'", (previous, ctx.learner)).fetchone()
                if not old:
                    raise ValueError("stale_memory_update")
                version = old[0] + 1
                self.db.execute("UPDATE memory_items SET status=?,updated_at=? WHERE id=?",
                                ("revoked" if proposal["retract"] else "superseded", time.time(), previous))
            if proposal["retract"]:
                continue
            # 没有指定替代对象的同类冲突保留候选，不悄悄覆盖旧偏好。
            conflict = self.db.execute(
                "SELECT 1 FROM memory_items WHERE learner_id=? AND kind=? AND status='active'",
                (ctx.learner, proposal["kind"])).fetchone()
            status = "candidate" if conflict and not previous else "active"
            identifier, now = str(uuid.uuid4()), time.time()
            self.db.execute("INSERT INTO memory_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (identifier, ctx.learner, proposal["kind"], "learner",
                             "*" if proposal["kind"] != "episode" else ctx.knowledge_id,
                             proposal["content"], json.dumps([ref]), ctx.run_id, "Tutor",
                             "user_statement", status, version, previous, now,
                             now + 30 * 86400 if proposal["kind"] == "episode" else None,
                             now, "verbatim", "v1", 1.0))
            self.index(ctx.learner, "memory:" + identifier)

    def read(self, learner, ref, offset=0, limit=3000):
        source = self.source(learner, ref)
        if not source:
            raise HTTPException(404, "历史证据不存在")
        text = source.pop("content")
        end = offset + limit
        return {**source, "content": text[offset:end], "truncated": end < len(text),
                "next_cursor": end if end < len(text) else None}

    def episode_sources(self, learner, ref):
        source = self.source(learner, ref)
        if not source or source["role"] == "memory":
            return []
        rows = self.db.execute(
            "SELECT id FROM conversation_messages WHERE learner=? AND thread=? AND created<=? "
            "ORDER BY created DESC LIMIT 6", (learner, source["thread_id"], source["created"])).fetchall()
        return [self.source(learner, "message:" + row[0]) for row in reversed(rows)]

    def save_episode(self, learner, anchor_ref, observations, model):
        """只保存经核验的原文摘录；摘要不产生新的学习事实或能力判断。"""
        sources = {s["source_ref"]: s for s in self.episode_sources(learner, anchor_ref)}
        if not sources or not observations:
            return
        for observation in observations:
            ref, quote = observation["source_ref"], observation["quote"]
            if ref not in sources or not quote.strip() or quote not in sources[ref]["content"]:
                raise ValueError("unsupported_episode_observation")
        refs = list(dict.fromkeys(item["source_ref"] for item in observations))
        content = "\n".join(f"{sources[o['source_ref']]['role']}：{o['quote']}" for o in observations)
        identifier, now = digest("episode:" + anchor_ref), time.time()
        self.db.execute(
            "INSERT OR IGNORE INTO memory_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (identifier, learner, "episode", "knowledge", sources[refs[0]]["knowledge_id"],
             content, json.dumps(refs), None, "MemoryExtractor", "quoted_observation",
             "active", 1, None, now, now + 30*86400, now, model, "episode-quotes-v1", None))
        self.index(learner, "memory:" + identifier)
