"""受控跨代编排；已完成案例可恢复，留出只能从同版本开发凭证进入。"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from core.policy_store import BUILTIN_HASH, PolicyRegistry, artifact, atomic_json, digest, exclusive
from evals.live_cases import load_live_cases
from evals.optimization.adapter import PROPOSER_PROMPT, TutorGEPAAdapter
from evals.optimization.budget import OptimizationStopped
from evals.optimization.calibration import verify_manifest
from evals.optimization.gates import acceptance
from evals.optimization.ledger import DurableBudget, SharedLedger
from evals.optimization.protocol import (
    assert_holdout_disjoint, file_digest, load_protocol, validate_candidate,
)
from evals.semantic_contract import require_rsi_contract


def task_signature(case):
    return digest({"knowledge": case.knowledge_id,
                   "inputs": [s.student_input for s in case.steps if s.action == "converse"],
                   "quiz": {k: case.initial_facts.get("quiz", {}).get(k)
                            for k in ("question", "options")}})


class Campaign:
    @classmethod
    def create(cls, root, *, dataset, protocol_path, registry, config, ledger=None, parent_hash=None):
        root = Path(root).resolve()
        if root.exists():
            raise ValueError("campaign directory already exists")
        protocol, _ = load_protocol(Path(protocol_path), Path(dataset))
        parent = registry.read(parent_hash) if parent_hash else registry.active()
        if parent["policy_hash"] != BUILTIN_HASH and not (
                registry.root / "eligibility" / f"{parent['policy_hash']}.json").exists():
            raise ValueError("parent must be a registered eligible version")
        if parent["policy_hash"] != BUILTIN_HASH:
            receipt = json.loads((registry.root / "eligibility"
                                  / f"{parent['policy_hash']}.json").read_text())
            prior = cls.open(receipt["campaign"])
            prior.verify_eligibility()
            if (receipt["binding"] != prior.binding
                    or prior.policy_artifact()["policy_hash"] != parent["policy_hash"]):
                raise ValueError("parent eligibility binding mismatch")
        # 活跃父版本已注册；最佳开发候选没有此入口。
        registry.read(parent["policy_hash"])
        required = {"max_requests", "max_cny", "source_revision", "runtime_hash", "deployment_runtime_hash",
                    "calibration_manifest", "simulation", "max_metric_calls", "minibatch"}
        if not required <= config.keys():
            raise ValueError("incomplete campaign configuration")
        if config.get("mode", "qualification") not in {"qualification", "exploratory"}:
            raise ValueError("unknown campaign mode")
        if not config["simulation"]:
            if config.get("calibration_sha256") != file_digest(config["calibration_manifest"]):
                raise ValueError("freeze calibration manifest digest before creating campaign")
        if (config["source_revision"] != registry.source_revision
                or config["deployment_runtime_hash"] != registry.runtime_hash):
            raise ValueError("parent/runtime binding mismatch")
        value = {
            "id": str(uuid.uuid4()), "state": "prepared", "config": config,
            "dataset": str(Path(dataset).resolve()), "protocol": protocol,
            "parent": parent, "registry": str(registry.root.resolve()),
            "ledger": str((ledger or SharedLedger()).path), "events": [],
            "candidate": None, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        value["binding"] = digest({k: value[k] for k in
                                   ("id", "config", "protocol", "parent", "created_at",
                                    "dataset", "ledger", "registry")})
        root.mkdir(parents=True)
        atomic_json(root / "campaign.json", value)
        atomic_json(root / "protocol.json", protocol)
        return cls.open(root)

    @classmethod
    def open(cls, root):
        self = cls()
        self.root = Path(root).resolve()
        self.data = json.loads((self.root / "campaign.json").read_text())
        if self.data["binding"] != digest({k: self.data[k] for k in
                                           ("id", "config", "protocol", "parent", "created_at",
                                            "dataset", "ledger", "registry")}):
            raise ValueError("campaign binding changed")
        self.binding = self.data["binding"]
        self.config = self.data["config"]
        self.store = SharedLedger(self.data["ledger"])
        self.budget = DurableBudget(
            self.store, self.config.get("budget_id", self.data["id"]),
            max_requests=self.config["max_requests"], max_cny=self.config["max_cny"])
        return self

    def save(self):
        atomic_json(self.root / "campaign.json", self.data)

    def transition(self, target, allowed, **details):
        if self.data["state"] not in allowed:
            raise ValueError(f"invalid stage transition: {self.data['state']} -> {target}")
        self.data["events"].append({"from": self.data["state"], "to": target, **details,
                                    "at": datetime.now(timezone.utc).isoformat(),
                                    "budget": self.budget.summary()})
        self.data["state"] = target
        self.save()

    def preflight(self):
        self.verify_environment()
        self.transition("preflight_passed", {"prepared"})

    def verify_environment(self):
        load_protocol(self.root / "protocol.json", Path(self.data["dataset"]))
        if not self.config["simulation"]:
            from evals.live_runner import code_revision
            from evals.optimization.runtime import component_runtime_hash, deployment_runtime_hash
            if (code_revision()["python_source_sha256"] != self.config["source_revision"]
                    or component_runtime_hash() != self.config["runtime_hash"]
                    or deployment_runtime_hash() != self.config["deployment_runtime_hash"]):
                raise ValueError("code or runtime changed since campaign preparation")
            if file_digest(self.config["calibration_manifest"]) != self.config["calibration_sha256"]:
                raise ValueError("calibration manifest changed")
            report = verify_manifest(Path(self.config["calibration_manifest"]))
            if self.config.get("mode") == "exploratory":
                from evals.optimization.exploratory import check_exploratory_calibration
                check_exploratory_calibration(report)
            elif not report["passed"]:
                raise ValueError("real calibration is incomplete or failed")
            from config.settings import settings
            identity = {"provider": settings.configured_llm_provider,
                        "model": settings.configured_llm_model,
                        "thinking": settings.deepseek_thinking}
            if report["judge_identity"] != identity:
                raise ValueError("calibration used a different judge model/configuration")

    def _inputs(self):
        protocol, cases = load_protocol(self.root / "protocol.json", Path(self.data["dataset"]))
        if protocol != self.data["protocol"]:
            raise ValueError("campaign protocol changed")
        return protocol, cases

    def search(self, service, *, adapter_factory=TutorGEPAAdapter):
        from evals.optimization.cli import run_search
        protocol, cases = self._inputs()
        self.transition("searching", {"preflight_passed", "searching"})
        with adapter_factory(list(cases.values()), protocol["reflection_train_ids"], self.budget,
                             self.root / "search", service=service) as adapter:
            adapter.reuse_completed = True
            # 只传白名单结构化失败计数；无学生正文、答案或测试集轨迹。
            from collections import Counter
            from evals.optimization.loop import FAILURES, CAPABILITIES
            summaries = self.config.get("failure_summaries", [])
            if any(r["failure"] not in FAILURES or r["capability"] not in CAPABILITIES
                   or r["data_role"] != "development" for r in summaries):
                raise ValueError("invalid development failure summary")
            adapter.failure_summary = dict(Counter(r["failure"] for r in summaries))
            result = run_search(adapter, protocol, cases, parent=self.data["parent"]["components"],
                                max_metric_calls=self.config["max_metric_calls"],
                                minibatch=self.config["minibatch"], run_dir=str(self.root / "gepa"))
        self.choose_candidate(result.best_candidate)
        shutil.rmtree(self.root / "gepa", ignore_errors=True)

    def choose_candidate(self, candidate):
        if self.data["state"] != "searching":
            raise ValueError("candidate requires completed search stage")
        validate_candidate(candidate)
        self.data["candidate"] = candidate
        self.data["comparison_binding"] = digest({"campaign": self.binding, "candidate": candidate})
        self.transition("dev_comparing", {"searching"})

    def _comparison(self, role, cases, service, adapter_factory):
        output = self.root / role
        binding = self.data["comparison_binding"]
        rows = {"baseline": [], "candidate": []}
        policies = {"baseline": self.data["parent"]["components"], "candidate": self.data["candidate"]}
        remaining = sum(
            case.expected_model_requests_max + 1
            for repeat in range(3) for case in cases for label in policies
            if not (output / "completed" / f"{repeat}-{digest(case.case_id)}-{label}.json").exists())
        self.budget.require_requests(remaining)
        with adapter_factory(cases, [], self.budget, output, service=service) as adapter:
            for repeat in range(3):
                for index, case in enumerate(cases):
                    order = ("baseline", "candidate") if (repeat + index) % 2 == 0 else (
                        "candidate", "baseline")
                    for label in order:
                        cache = output / "completed" / f"{repeat}-{digest(case.case_id)}-{label}.json"
                        if cache.exists():
                            saved = json.loads(cache.read_text())
                            if saved["binding"] != binding or saved["row_hash"] != digest(saved["row"]):
                                raise ValueError("cached comparison evidence mismatch")
                            row = saved["row"]
                        else:
                            row = adapter.evaluate_rows([case], policies[label])[0]
                            row.update(repeat=repeat, comparison_label=label)
                            atomic_json(cache, {"binding": binding, "row": row, "row_hash": digest(row)})
                        rows[label].append(row)
        gate = acceptance(rows["baseline"], rows["candidate"], holdout=role == "holdout")
        receipt = {"binding": binding, "role": role, "rows": rows, "gate": gate}
        atomic_json(output / "receipt.json", receipt)
        self.data[role + "_receipt_hash"] = digest(receipt)
        self.save()
        return gate

    def verify_receipt(self, role):
        value = json.loads((self.root / role / "receipt.json").read_text())
        if (digest(value) != self.data[role + "_receipt_hash"]
                or value["binding"] != self.data["comparison_binding"]):
            raise ValueError("comparison receipt binding mismatch")
        _, development = self._inputs()
        cases = ([development[cid] for cid in self.data["protocol"]["dev_validation_ids"]]
                 if role == "dev" else load_live_cases(Path(self.data["holdout_path"])))
        expected = {c.case_id: c for c in cases}
        from evals.optimization.protocol import capability_name
        for label, policy in (("baseline", self.data["parent"]["components"]),
                              ("candidate", self.data["candidate"])):
            rows = value["rows"][label]
            if {(r["repeat"], r["case_id"]) for r in rows} != {
                    (i, cid) for i in range(3) for cid in expected}:
                raise ValueError("frozen comparison coverage mismatch")
            if any(r["policy_sha256"] != digest(policy)
                   or r["capability"] != capability_name(expected[r["case_id"]]) for r in rows):
                raise ValueError("policy/case identity mismatch")
            if not self.config["simulation"]:
                from evals.optimization.gates import verify_raw_row
                for row in rows:
                    verify_raw_row(row, expected[row["case_id"]])
                    from config.settings import settings
                    if row["judge_identity"] != {
                            "provider": settings.configured_llm_provider,
                            "model": settings.configured_llm_model, "thinking": settings.deepseek_thinking}:
                        raise ValueError("comparison used a different judge model/configuration")
        gate = acceptance(value["rows"]["baseline"], value["rows"]["candidate"],
                          holdout=role == "holdout")
        if value["gate"] != gate or not gate["passed"]:
            raise ValueError("comparison did not pass")
        return gate

    def compare_development(self, service, *, adapter_factory=TutorGEPAAdapter):
        if self.data["state"] != "dev_comparing":
            raise ValueError("development comparison out of order")
        protocol, cases = self._inputs()
        gate = self._comparison("dev", [cases[cid] for cid in protocol["dev_validation_ids"]],
                                service, adapter_factory)
        self.transition("dev_passed" if gate["passed"] else "rejected", {"dev_comparing"})
        return gate

    def compare_holdout(self, path, service, *, adapter_factory=TutorGEPAAdapter):
        self.require_qualification()
        if self.data["state"] not in {"dev_passed", "holdout_testing"}:
            raise ValueError("holdout requires passed development")
        self.verify_receipt("dev")
        cases = load_live_cases(Path(path))
        if len(cases) != 18:
            raise ValueError("holdout requires 18 frozen tasks")
        _, development = self._inputs()
        assert_holdout_disjoint(list(development.values()), cases)
        from collections import Counter
        from evals.optimization.protocol import capability_name
        counts = Counter(capability_name(c) for c in cases)
        if set(counts) != set(self.data["protocol"]["counts"]) or set(counts.values()) != {3}:
            raise ValueError("holdout requires three tasks per frozen capability")
        for case in cases:
            require_rsi_contract(case)
        # 必须先完成人工近重复审查；摘要绑定当前材料，不把字面去重当语义审查。
        if self.config.get("holdout_review_sha256") != file_digest(path):
            raise ValueError("holdout semantic-overlap review is missing")
        if not self.config.get("holdout_reviewer"):
            raise ValueError("holdout reviewer attribution required")
        holdout_hash = file_digest(path)
        if self.data.get("holdout_hash", holdout_hash) != holdout_hash:
            raise ValueError("cannot replace consumed holdout on resume")
        self.data.update(holdout_path=str(Path(path).resolve()), holdout_hash=holdout_hash)
        self.save()
        # 持久标记早于任何模型调用。部分运行只允许同 campaign/候选恢复。
        self.store.consume_holdout(holdout_hash, [task_signature(c) for c in cases],
                                   owner=self.data["id"], binding=self.data["comparison_binding"])
        self.transition("holdout_testing", {"dev_passed", "holdout_testing"})
        gate = self._comparison("holdout", cases, service, adapter_factory)
        self.transition("holdout_passed" if gate["passed"] else "rejected", {"holdout_testing"})
        return gate

    def qualify(self, harness_evidence):
        self.require_qualification()
        if self.data["state"] != "holdout_passed":
            raise ValueError("qualification requires holdout")
        source = Path(harness_evidence)
        value = json.loads(source.read_text())
        atomic_json(self.root / "harness.json", value)
        self.data["harness_hash"] = digest(value)
        self.save()
        self.verify_eligibility()
        self.data["artifact"] = artifact(
            self.data["candidate"], parent=self.data["parent"]["policy_hash"],
            protocol=digest(self.data["protocol"]), runtime=self.config["deployment_runtime_hash"],
            source=self.config["source_revision"], proposer=digest(PROPOSER_PROMPT),
            evidence={"campaign": str(self.root), "dev": self.data["dev_receipt_hash"],
                      "holdout": self.data["holdout_receipt_hash"], "harness": self.data["harness_hash"]})
        self.transition("eligible", {"holdout_passed"})

    def verify_eligibility(self):
        self.require_qualification()
        if self.config["simulation"]:
            raise ValueError("simulation cannot grant release eligibility")
        self.verify_environment()
        self.verify_receipt("dev")
        self.verify_receipt("holdout")
        if file_digest(self.data["holdout_path"]) != self.data["holdout_hash"]:
            raise ValueError("holdout dataset changed")
        if not verify_manifest(Path(self.config["calibration_manifest"]))["passed"]:
            raise ValueError("calibration gate failed")
        from evals.optimization.runtime import verify_harness_evidence
        value = json.loads((self.root / "harness.json").read_text())
        if digest(value) != self.data["harness_hash"]:
            raise ValueError("harness evidence changed")
        verify_harness_evidence(value, self)

    def policy_artifact(self):
        self.require_qualification()
        value = self.data["artifact"]
        expected = artifact(
            self.data["candidate"], parent=self.data["parent"]["policy_hash"],
            protocol=digest(self.data["protocol"]), runtime=self.config["deployment_runtime_hash"],
            source=self.config["source_revision"], proposer=digest(PROPOSER_PROMPT),
            evidence={"campaign": str(self.root), "dev": self.data["dev_receipt_hash"],
                      "holdout": self.data["holdout_receipt_hash"], "harness": self.data["harness_hash"]})
        expected["created_at"] = value["created_at"]
        expected["policy_hash"] = digest({k: v for k, v in expected.items() if k != "policy_hash"})
        if value != expected:
            raise ValueError("registered artifact does not match campaign evidence")
        return value

    def register(self):
        self.require_qualification()
        registry = PolicyRegistry(self.data["registry"], runtime_hash=self.config["deployment_runtime_hash"],
                                  source_revision=self.config["source_revision"])
        policy_hash = registry.register(self.policy_artifact(), self)
        self.transition("registered", {"eligible", "registered"}, policy_hash=policy_hash)
        return policy_hash

    def require_qualification(self):
        if self.config.get("mode") == "exploratory":
            raise ValueError("exploratory campaign cannot grant promotion or release eligibility")

    def execute(self, service, *, holdout=None, harness_evidence=None, adapter_factory=TutorGEPAAdapter):
        """串行恢复同一个 campaign；中断不释放预算，不删除已完成配对。"""
        with exclusive(self.root / ".campaign.lock"):
            self.data = Campaign.open(self.root).data
            if self.data["state"] == "interrupted":
                self.data["state"] = self.data["resume_state"]
                self.budget.recover()
                self.save()
            try:
                self.verify_environment()
                if self.config.get("mode") == "exploratory":
                    from evals.optimization.exploratory import run_exploration
                    return run_exploration(self, service, adapter_factory=adapter_factory)
                if self.data["state"] == "prepared":
                    self.preflight()
                if self.data["state"] in {"preflight_passed", "searching"}:
                    self.search(service, adapter_factory=adapter_factory)
                if self.data["state"] == "dev_comparing":
                    self.compare_development(service, adapter_factory=adapter_factory)
                if self.data["state"] in {"dev_passed", "holdout_testing"} and holdout:
                    self.compare_holdout(holdout, service, adapter_factory=adapter_factory)
                if self.data["state"] == "holdout_passed" and harness_evidence:
                    self.qualify(harness_evidence)
                if self.data["state"] == "eligible":
                    self.register()
            except BaseException as exc:
                self.data["resume_state"] = self.data["state"]
                self.transition("stopped" if isinstance(exc, OptimizationStopped)
                                and self.budget.exhausted else "interrupted",
                                {self.data["state"]}, error_type=type(exc).__name__)
                raise
        return self.data["state"]
