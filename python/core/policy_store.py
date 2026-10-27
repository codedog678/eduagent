"""不可变策略包与原子指针；不导入评测执行器，不接触学习状态。"""

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from core.tutor_policy import RETRIEVAL_RULES, fixed_components


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def validate_components(components):
    if (not isinstance(components, dict) or set(components) != {"retrieval_rules"}
            or not isinstance(components["retrieval_rules"], str)
            or not 0 < len(components["retrieval_rules"].strip()) <= 6000):
        raise ValueError("invalid retrieval component")


def builtin_components():
    return {"retrieval_rules": RETRIEVAL_RULES}


def effective_hash(components):
    return digest({"components": components, "fixed_components": fixed_components()})


BUILTIN_HASH = effective_hash(builtin_components())


def artifact(components, *, parent, protocol, runtime, source, proposer, evidence):
    validate_components(components)
    body = {
        "schema_version": 1, "parent_policy_hash": parent, "components": components,
        "fixed_components_hash": digest(fixed_components()), "proposer_hash": proposer,
        "protocol_hash": protocol, "runtime_hash": runtime, "source_revision": source,
        "data_role": "holdout_validated", "evidence_paths": evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {**body, "policy_hash": digest(body)}


class PolicyRegistry:
    def __init__(self, root, *, runtime_hash, source_revision):
        self.root = Path(root)
        self.runtime_hash, self.source_revision = runtime_hash, source_revision

    def read(self, policy_hash):
        if policy_hash == BUILTIN_HASH:
            return {"policy_hash": BUILTIN_HASH, "components": builtin_components()}
        if (not isinstance(policy_hash, str) or len(policy_hash) != 64
                or any(c not in "0123456789abcdef" for c in policy_hash)):
            raise ValueError("invalid policy hash")
        value = json.loads((self.root / "artifacts" / f"{policy_hash}.json").read_text())
        body = {k: v for k, v in value.items() if k != "policy_hash"}
        validate_components(value["components"])
        if (value["schema_version"] != 1 or value["data_role"] != "holdout_validated"
                or value["policy_hash"] != policy_hash or digest(body) != policy_hash
                or value["fixed_components_hash"] != digest(fixed_components())
                or value["runtime_hash"] != self.runtime_hash
                or value["source_revision"] != self.source_revision):
            raise ValueError("policy digest or runtime compatibility mismatch")
        return value

    def active(self):
        pointer = self.root / "active.json"
        policy_hash = json.loads(pointer.read_text())["policy_hash"] if pointer.exists() else BUILTIN_HASH
        if policy_hash != BUILTIN_HASH and not (
                self.root / "eligibility" / f"{policy_hash}.json").exists():
            raise ValueError("active policy was never registered")
        return self.read(policy_hash)

    def register(self, value, campaign):
        # 从原始配对记录重新计算资格，不能传一个 passed=true 代替证据。
        campaign.verify_eligibility()
        expected = campaign.policy_artifact()
        if value != expected:
            raise ValueError("artifact is not bound to eligible campaign")
        self.read(value["parent_policy_hash"])
        path = self.root / "artifacts" / f"{value['policy_hash']}.json"
        with exclusive(self.root / ".registry.lock"):
            if path.exists() and json.loads(path.read_text()) != value:
                raise ValueError("immutable policy collision")
            atomic_json(path, value)
            self.read(value["policy_hash"])
            atomic_json(self.root / "eligibility" / f"{value['policy_hash']}.json",
                        {"campaign": str(campaign.root.resolve()), "binding": campaign.binding})
        return value["policy_hash"]

    def activate(self, policy_hash, *, release_enabled=False, reason="release"):
        if not release_enabled:
            raise PermissionError("policy release is disabled")
        self.read(policy_hash)
        if policy_hash != BUILTIN_HASH:
            # 资格记录只由 register 写入；加载时仍复核完整证据。
            from evals.optimization.campaign import Campaign
            receipt = json.loads((self.root / "eligibility" / f"{policy_hash}.json").read_text())
            campaign = Campaign.open(receipt["campaign"])
            campaign.verify_eligibility()
            if (campaign.binding != receipt["binding"]
                    or campaign.policy_artifact()["policy_hash"] != policy_hash):
                raise ValueError("release evidence changed")
        with exclusive(self.root / ".registry.lock"):
            pointer_path = self.root / "active.json"
            previous = (json.loads(pointer_path.read_text())["policy_hash"]
                        if pointer_path.exists() else BUILTIN_HASH)
            pointer = {"policy_hash": policy_hash, "previous": previous, "reason": reason,
                       "at": datetime.now(timezone.utc).isoformat()}
            # 日志先落盘；异常时 active 始终是一个完整旧值或新值。
            atomic_json(self.root / "events" / f"{digest(pointer)}.json", pointer)
            atomic_json(self.root / "active.json", pointer)

    def rollback(self, *, release_enabled=False):
        pointer = json.loads((self.root / "active.json").read_text())
        self.activate(pointer["previous"], release_enabled=release_enabled, reason="rollback")
