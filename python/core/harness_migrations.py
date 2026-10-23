"""Harness SQLite 的顺序、事务化、向前兼容迁移。"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

LATEST_SCHEMA_VERSION = 2


class SchemaVersionError(RuntimeError):
    """数据库版本无法由当前代码安全读取。"""


def _migration_1(db: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS runs (
            learner TEXT, request TEXT, fingerprint TEXT, status TEXT,
            result TEXT, error TEXT, updated REAL,
            PRIMARY KEY (learner, request))
        """,
        "CREATE TABLE IF NOT EXISTS checkpoints (learner TEXT PRIMARY KEY, state TEXT)",
        "CREATE TABLE IF NOT EXISTS quizzes (id TEXT PRIMARY KEY, learner TEXT, body TEXT)",
        """
        CREATE TABLE IF NOT EXISTS learning_sessions (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, created REAL NOT NULL)
        """,
        """
        CREATE TABLE IF NOT EXISTS learning_threads (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, knowledge TEXT NOT NULL)
        """,
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, session TEXT NOT NULL,
            thread TEXT NOT NULL, run TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created REAL NOT NULL)
        """,
        """
        CREATE INDEX IF NOT EXISTS messages_scope
        ON conversation_messages(learner,thread,created)
        """,
        """
        CREATE TABLE IF NOT EXISTS learning_evidence (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, thread TEXT NOT NULL,
            run TEXT NOT NULL, quiz TEXT, kind TEXT NOT NULL, body TEXT NOT NULL,
            created REAL NOT NULL)
        """,
        """
        CREATE INDEX IF NOT EXISTS evidence_scope
        ON learning_evidence(learner,thread,created)
        """,
        """
        CREATE TABLE IF NOT EXISTS run_attempts (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, request TEXT NOT NULL,
            run TEXT NOT NULL, status TEXT NOT NULL, reason TEXT,
            started REAL NOT NULL, finished REAL)
        """,
        """
        CREATE TABLE IF NOT EXISTS run_steps (
            attempt TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY(attempt,seq))
        """,
        """
        CREATE TABLE IF NOT EXISTS pending_questions (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, thread TEXT NOT NULL,
            run TEXT NOT NULL, question TEXT NOT NULL, answered_by TEXT)
        """,
    )
    for statement in statements:
        db.execute(statement)


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _migration_2(db: sqlite3.Connection) -> None:
    additions = {
        "app_version": "TEXT",
        "trace_schema_version": "INTEGER",
        "provider": "TEXT",
        "model": "TEXT",
        "config_fingerprint": "TEXT",
    }
    current = _columns(db, "run_attempts")
    for name, column_type in additions.items():
        if name not in current:
            db.execute(
                f"ALTER TABLE run_attempts ADD COLUMN {name} {column_type}"
            )


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_1,
    2: _migration_2,
}


def schema_version(db: sqlite3.Connection) -> int:
    return int(db.execute("PRAGMA user_version").fetchone()[0])


def migrate(db: sqlite3.Connection) -> int:
    current = schema_version(db)
    if current > LATEST_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Harness schema {current} is newer than supported "
            f"{LATEST_SCHEMA_VERSION}"
        )
    for target in range(current + 1, LATEST_SCHEMA_VERSION + 1):
        migration = MIGRATIONS[target]
        db.execute("BEGIN IMMEDIATE")
        try:
            migration(db)
            db.execute(f"PRAGMA user_version = {target}")
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return schema_version(db)
