"""按预设窗口处理已确认的发布异常；不把工具拒绝当作权限突破。"""

import json
from pathlib import Path

from core.policy_store import atomic_json, exclusive


class PolicyHealthMonitor:
    def __init__(self, registry, *, window=50, min_samples=20, max_commit_failure_rate=.1):
        if (type(window) is not int or type(min_samples) is not int
                or not 1 <= min_samples <= window or not 0 < max_commit_failure_rate <= 1):
            raise ValueError("invalid rollback monitoring bounds")
        self.registry = registry
        self.window, self.min_samples = window, min_samples
        self.threshold = max_commit_failure_rate
        self.path = Path(registry.root) / "health.json"

    def observe(self, policy_hash, outcome, *, release_enabled=False):
        if outcome not in {"completed", "commit_failed", "confirmed_permission_violation"}:
            raise ValueError("unknown release health observation")
        with exclusive(self.path.with_suffix(".lock")):
            state = json.loads(self.path.read_text()) if self.path.exists() else {"samples": {}}
            rows = state["samples"].setdefault(policy_hash, [])
            rows.append(outcome)
            del rows[:-self.window]
            triggered = (outcome == "confirmed_permission_violation"
                         or len(rows) >= self.min_samples
                         and rows.count("commit_failed") / len(rows) >= self.threshold)
            active = self.registry.active()["policy_hash"]
            # 只回退发生异常的活跃版本；旧会话迟到结果不影响新版本。
            if triggered and policy_hash == active:
                state["trigger"] = {"policy_hash": policy_hash, "outcome": outcome,
                                    "samples": len(rows), "enabled": release_enabled}
                atomic_json(self.path, state)
                if release_enabled:
                    self.registry.rollback(release_enabled=True)
                    return True
            atomic_json(self.path, state)
            return False
