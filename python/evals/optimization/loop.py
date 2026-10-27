"""离线结构化失败队列与有界循环；不收集学生正文或答案。"""

from pathlib import Path
from contextlib import contextmanager
import json
import sqlite3
import uuid

from core.policy_store import atomic_json, digest, exclusive
from evals.optimization.campaign import Campaign
from evals.optimization.ledger import DurableBudget

FAILURES = {"budget_exhausted", "schema_invalid", "unread_source", "missing_tool",
            "incorrect_answer", "indirect_leak", "capability_regression", "provider_error"}
CAPABILITIES = {"full_history_retrieval", "grounded_history", "multi_turn_continuation",
                "injection_and_permissions", "learning_evidence", "tool_and_evidence_decision"}


class FailureQueue:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS samples "
                       "(id TEXT PRIMARY KEY, body TEXT NOT NULL, campaign TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, *, evidence_digest, capability, failure, data_role):
        if (data_role != "development" or capability not in CAPABILITIES or failure not in FAILURES
                or len(evidence_digest) != 64
                or any(c not in "0123456789abcdef" for c in evidence_digest)):
            raise ValueError("only sanitized development failure metadata may enter the queue")
        # 白名单字段；不接受学生ID、正文、评分答案、工具原始载荷。
        record = {"evidence_digest": evidence_digest, "capability": capability,
                  "failure": failure, "data_role": data_role}
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO samples VALUES (?,?,NULL)",
                       (digest(record), json.dumps(record)))

    def pending(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT body FROM samples WHERE campaign IS NULL ORDER BY id")]

    def claim(self, records, campaign_id):
        with self.connect() as db:
            for record in records:
                owner = db.execute("SELECT campaign FROM samples WHERE id=?",
                                   (digest(record),)).fetchone()
                if owner and owner[0] == campaign_id:
                    continue
                cursor = db.execute("UPDATE samples SET campaign=? WHERE id=? AND campaign IS NULL",
                                    (campaign_id, digest(record)))
                if cursor.rowcount != 1:
                    raise ValueError("failure sample already claimed")


class ImprovementLoop:
    def __init__(self, root, *, queue, ledger, config):
        self.root, self.queue, self.ledger = Path(root), queue, ledger
        for key in ("max_generations", "min_new_samples", "max_stagnation", "max_failures"):
            if type(config.get(key)) is not int or config[key] < 1:
                raise ValueError("positive finite loop bounds required")
        self.config = config
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "loop.json"
        if path.exists():
            self.state = json.loads(path.read_text())
            if self.state["config"] != config:
                raise ValueError("loop limits are frozen")
        else:
            self.state = {"config": config, "budget_id": str(uuid.uuid4()), "status": "waiting",
                          "generations": [], "stagnation": 0, "failures": 0, "parent": None}
            self.save()
        self.budget = DurableBudget(ledger, self.state["budget_id"],
                                   max_requests=config["max_requests"], max_cny=config["max_cny"])

    def save(self):
        atomic_json(self.root / "loop.json", self.state)

    def run(self, create_campaign, execute_campaign):
        """回调复用 Campaign.execute；所有代数必须绑定同一持久预算。"""
        with exclusive(self.root / ".loop.lock"):
            while True:
                self.budget.summary()
                stop = ("budget" if self.budget.exhausted else
                        "stagnation" if self.state["stagnation"] >= self.config["max_stagnation"] else
                        "failures" if self.state["failures"] >= self.config["max_failures"] else None)
                if stop:
                    self.state.update(status="stopped", reason=stop)
                    self.save()
                    break
                active = self.state.get("active")
                if active:
                    campaign = Campaign.open(active)
                    self.queue.claim(self.state["active_samples"], campaign.data["id"])
                else:
                    if len(self.state["generations"]) >= self.config["max_generations"]:
                        self.state.update(status="stopped", reason="max_generations")
                        self.save()
                        break
                    records = self.queue.pending()
                    if len(records) < self.config["min_new_samples"]:
                        self.state.update(status="waiting", reason="insufficient_new_samples")
                        self.save()
                        break
                    campaign = create_campaign(
                        len(self.state["generations"]), self.state["parent"], records,
                        {"budget_id": self.state["budget_id"],
                         "max_requests": self.config["max_requests"], "max_cny": self.config["max_cny"]})
                    if (campaign.budget.budget_id != self.state["budget_id"]
                            or campaign.store.path != self.ledger.path):
                        raise ValueError("generation attempted to escape shared budget")
                    self.state.update(active=str(campaign.root), active_samples=records, status="running")
                    self.save()
                    self.queue.claim(records, campaign.data["id"])
                try:
                    execute_campaign(campaign)
                except Exception as exc:
                    self.state["failures"] += 1
                    self.state.update(status="interrupted", error_type=type(exc).__name__)
                    self.save()
                    if self.state["failures"] >= self.config["max_failures"]:
                        continue
                    # 不在同次调度中反复补发失败调用；下次显式恢复。
                    break
                status = campaign.data["state"]
                if status == "registered":
                    campaign.verify_eligibility()
                    self.state["parent"] = campaign.policy_artifact()["policy_hash"]
                    self.state["stagnation"] = 0
                elif status == "rejected":
                    self.state["stagnation"] += 1
                elif status == "stopped":
                    self.state.update(status="stopped", reason="campaign_stopped")
                    self.save()
                    break
                else:
                    self.state.update(status="waiting", reason="campaign_requires_evidence")
                    self.save()
                    break
                self.state["generations"].append({"campaign": str(campaign.root),
                                                  "status": status, "parent": self.state["parent"]})
                self.state.pop("active", None)
                self.state.pop("active_samples", None)
                self.save()
        return self.state
