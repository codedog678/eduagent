"""Harness SQLite 迁移必须保留旧数据并在失败时回滚。"""

import sqlite3

import pytest

from core import harness_migrations


def test_fresh_database_reaches_latest_schema():
    db = sqlite3.connect(":memory:")
    assert harness_migrations.migrate(db) == harness_migrations.LATEST_SCHEMA_VERSION
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "runs",
        "checkpoints",
        "quizzes",
        "run_attempts",
        "run_steps",
        "conversation_messages",
        "learning_evidence",
    } <= tables
    columns = {
        row[1] for row in db.execute("PRAGMA table_info(run_attempts)")
    }
    assert {
        "app_version",
        "trace_schema_version",
        "provider",
        "model",
        "config_fingerprint",
    } <= columns


def test_legacy_attempt_survives_additive_migration():
    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE run_attempts (
            id TEXT PRIMARY KEY, learner TEXT NOT NULL, request TEXT NOT NULL,
            run TEXT NOT NULL, status TEXT NOT NULL, reason TEXT,
            started REAL NOT NULL, finished REAL)
    """)
    db.execute(
        "INSERT INTO run_attempts "
        "(id,learner,request,run,status,reason,started,finished) "
        "VALUES ('a','student','r','run','completed',NULL,1,2)"
    )
    db.execute("PRAGMA user_version = 1")
    db.commit()
    assert harness_migrations.migrate(db) == 2
    row = db.execute(
        "SELECT status,app_version,trace_schema_version FROM run_attempts "
        "WHERE id='a'"
    ).fetchone()
    assert row == ("completed", None, None)


def test_failed_migration_does_not_advance_version(monkeypatch):
    db = sqlite3.connect(":memory:")
    harness_migrations._migration_1(db)
    db.execute("PRAGMA user_version = 1")
    db.commit()

    def broken(connection):
        connection.execute("CREATE TABLE should_roll_back (value TEXT)")
        raise RuntimeError("injected migration failure")

    monkeypatch.setitem(harness_migrations.MIGRATIONS, 2, broken)
    with pytest.raises(RuntimeError, match="injected"):
        harness_migrations.migrate(db)
    assert harness_migrations.schema_version(db) == 1
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE name='should_roll_back'"
    ).fetchone() is None


def test_newer_database_is_rejected():
    db = sqlite3.connect(":memory:")
    db.execute(
        f"PRAGMA user_version = {harness_migrations.LATEST_SCHEMA_VERSION + 1}"
    )
    with pytest.raises(harness_migrations.SchemaVersionError):
        harness_migrations.migrate(db)
