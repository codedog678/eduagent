"""共享 SQLite 总账。消费与请求预留在远程调用前提交，目录不是隔离边界。"""

import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from evals.optimization.budget import OptimizationBudget
from core.policy_store import digest

DEFAULT_LEDGER = Path.home() / ".eduagent/rsi/ledger.sqlite"


class SharedLedger:
    def __init__(self, path=DEFAULT_LEDGER):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS holdouts
                    (signature TEXT PRIMARY KEY, owner TEXT NOT NULL, binding TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def consume_holdout(self, dataset_hash, signatures, *, owner, binding):
        keys = ["dataset:" + dataset_hash] + ["task:" + s for s in signatures]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate holdout tasks")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for key in keys:
                row = db.execute("SELECT owner,binding FROM holdouts WHERE signature=?", (key,)).fetchone()
                if row and row != (owner, binding):
                    raise ValueError("holdout already consumed by another campaign/candidate")
            for key in keys:
                db.execute("INSERT OR IGNORE INTO holdouts VALUES (?,?,?)", (key, owner, binding))


class DurableBudget(OptimizationBudget):
    """多个阶段共用同一 budget_id；每次读改写均在同一个事务内。"""

    def __init__(self, ledger, budget_id, *, max_requests, max_cny):
        super().__init__(max_requests=max_requests, max_cny=max_cny)
        self.store, self.budget_id = ledger, budget_id
        with ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM budgets WHERE id=?", (budget_id,)).fetchone()
            if row:
                self._load(json.loads(row[0]))
            else:
                db.execute("INSERT INTO budgets VALUES (?,?)", (budget_id, json.dumps(self._state())))

    def _state(self):
        return {key: getattr(self, key) for key in (
            "max_requests", "max_cny", "requests", "estimated_peak_cny", "estimated_off_peak_cny",
            "unconfirmed_reservation_cny", "ledger")}

    def _load(self, state):
        if (state["max_requests"], state["max_cny"]) != (self.max_requests, self.max_cny):
            raise ValueError("shared budget limits are frozen")
        for key, value in state.items():
            setattr(self, key, value)

    def _transaction(self, action):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._load(json.loads(db.execute("SELECT body FROM budgets WHERE id=?",
                                            (self.budget_id,)).fetchone()[0]))
            result = action()
            db.execute("UPDATE budgets SET body=? WHERE id=?",
                       (json.dumps(self._state()), self.budget_id))
            return result

    def recover(self):
        def mark():
            for row in self.ledger:
                if row["status"] == "unconfirmed":
                    row["recovery_state"] = "unknown"
        self._transaction(mark)

    def reserve_for(self, role, messages, tools, max_tokens, *, pricing=None):
        def reserve():
            index = super(DurableBudget, self).reserve_for(
                role, messages, tools, max_tokens, pricing=pricing)
            self.ledger[index]["input_sha256"] = digest({"messages": messages, "tools": tools})
            return index
        return self._transaction(reserve)

    def settle(self, index, usage):
        return self._transaction(lambda: super(DurableBudget, self).settle(index, usage))

    def require_requests(self, count):
        return self._transaction(lambda: super(DurableBudget, self).require_requests(count))

    def summary(self):
        return self._transaction(lambda: super(DurableBudget, self).summary())
