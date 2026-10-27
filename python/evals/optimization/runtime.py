"""复用长任务执行器的整链门禁；原始轨迹重评分，教学审阅单列。"""

from contextlib import contextmanager
import json
from pathlib import Path

from config.settings import settings
from core import llm_service
from core.policy_store import atomic_json, digest, exclusive
from core.tutor_policy import use_retrieval_rules
from core.versions import policy_runtime_hash
from evals.live_runner import code_revision
from evals.optimization.protocol import RUNTIME, file_digest

HARNESS_RUNTIME = {**RUNTIME, "enable_coordinator": True}
LONG_DATASET = Path(__file__).parents[1] / "datasets/harness_long_tasks_v1.jsonl"


@contextmanager
def runtime_scope(fields):
    previous = {key: getattr(settings, key) for key in fields}
    try:
        for key, value in fields.items():
            setattr(settings, key, value)
        yield
    finally:
        for key, value in previous.items():
            setattr(settings, key, value)


def component_runtime_hash():
    with runtime_scope(RUNTIME):
        return policy_runtime_hash(settings)


def deployment_runtime_hash():
    with runtime_scope(HARNESS_RUNTIME):
        return policy_runtime_hash(settings)


async def run_harness_evidence(campaign, service):
    """共享总预算；逐例缓存。审阅未完成时只产生待审证据，不能发布。"""
    with exclusive(campaign.root / ".campaign.lock"):
        campaign.verify_environment()
        campaign.budget.recover()
        return await _run_harness_evidence(campaign, service)


async def _run_harness_evidence(campaign, service):
    from evals.long_task_executor import LongTaskExecutor
    from evals.long_task_models import load_long_task_cases
    from evals.long_task_scorers import score_long_task
    from evals.long_task_runner import run_contract_suite
    deterministic = run_contract_suite()
    atomic_json(campaign.root / "deterministic.json", deterministic)
    if deterministic["passed"] != deterministic["total"]:
        raise ValueError("deterministic Harness contracts failed")
    cases = load_long_task_cases(LONG_DATASET)
    rows = {"baseline": [], "candidate": []}
    original = llm_service._llm_service
    policies = {"baseline": campaign.data["parent"]["components"], "candidate": campaign.data["candidate"]}
    try:
        llm_service._llm_service = service
        with runtime_scope(HARNESS_RUNTIME):
            for repeat in range(3):
                for i, case in enumerate(cases):
                    order = ("baseline", "candidate") if (repeat + i) % 2 == 0 else ("candidate", "baseline")
                    for label in order:
                        cache = campaign.root / "harness-cases" / f"{repeat}-{case.case_id}-{label}.json"
                        if cache.exists():
                            saved = json.loads(cache.read_text())
                            if (saved["binding"] != campaign.data["comparison_binding"]
                                    or digest(saved["row"]) != saved["row_hash"]):
                                raise ValueError("harness cache binding mismatch")
                            row = saved["row"]
                        else:
                            campaign.budget.require_requests(case.expected_model_requests_max)
                            with use_retrieval_rules(policies[label]["retrieval_rules"]):
                                executor = LongTaskExecutor(case, service, campaign.budget)
                                try:
                                    row = score_long_task(case, await executor.execute())
                                finally:
                                    executor.close()
                            row.update(repeat=repeat, policy_sha256=digest(policies[label]))
                            atomic_json(cache, {"binding": campaign.data["comparison_binding"],
                                                "row": row, "row_hash": digest(row)})
                        rows[label].append(row)
            report = {
                "binding": campaign.data["comparison_binding"], "rows": rows,
                "source_revision": code_revision()["python_source_sha256"],
                "runtime_hash": policy_runtime_hash(settings),
                "dataset_hash": file_digest(LONG_DATASET),
                "simulation": campaign.config["simulation"], "teaching_reviews": [],
                "deterministic": deterministic,
            }
            atomic_json(campaign.root / "harness-pending-review.json", report)
            return report
    finally:
        llm_service._llm_service = original


def verify_harness_evidence(value, campaign):
    from evals.long_task_models import load_long_task_cases
    from evals.long_task_scorers import score_long_task
    from evals.long_task_runner import aggregate_live, CONTRACT_TESTS
    if (value["binding"] != campaign.data["comparison_binding"] or value["simulation"]
            or value["source_revision"] != campaign.config["source_revision"]
            or value["runtime_hash"] != campaign.config["deployment_runtime_hash"]
            or value["dataset_hash"] != file_digest(LONG_DATASET)):
        raise ValueError("harness protocol binding mismatch")
    contracts = value["deterministic"]
    if (contracts["total"] != 8 or contracts["passed"] != 8
            or len(contracts["results"]) != 8
            or {r["case_id"] for r in contracts["results"]} != set(CONTRACT_TESTS)
            or any(r["status"] != "passed" or r["returncode"] != 0 for r in contracts["results"])):
        raise ValueError("deterministic Harness contracts incomplete")
    cases = {c.case_id: c for c in load_long_task_cases(LONG_DATASET)}
    expected = {(i, cid) for i in range(3) for cid in cases}
    for label, policy in (("baseline", campaign.data["parent"]["components"]),
                          ("candidate", campaign.data["candidate"])):
        rows = value["rows"][label]
        if len(rows) != len(expected) or {(r["repeat"], r["case_id"]) for r in rows} != expected:
            raise ValueError("harness paired coverage incomplete")
        for row in rows:
            computed = score_long_task(cases[row["case_id"]], row["observed"])
            if (any(row[key] != computed[key] for key in computed)
                    or row["policy_sha256"] != digest(policy)):
                raise ValueError("harness raw evidence does not match score")
    baseline = {(r["repeat"], r["case_id"]): r for r in value["rows"]["baseline"]}
    for row in value["rows"]["candidate"]:
        old = baseline[(row["repeat"], row["case_id"])]
        passed_checks = {a["id"] for a in old["assertions"] if a["passed"]}
        if any(a["id"] in passed_checks and not a["passed"] for a in row["assertions"]):
            raise ValueError("harness hard assertion regression")
    for repeat in range(3):
        rows = [r for r in value["rows"]["candidate"] if r["repeat"] == repeat]
        if not aggregate_live(rows)["meets_project_gate"]:
            raise ValueError("harness project gate failed")
    # 旧长任务自动断言不等同教学质量；显式审核每例准确性和间接泄露。
    reviews = value["teaching_reviews"]
    if (len(reviews) != len(expected)
            or {(r["repeat"], r["case_id"]) for r in reviews} != expected):
        raise ValueError("harness teaching review incomplete")
    candidates = {(r["repeat"], r["case_id"]): r for r in value["rows"]["candidate"]}
    for review in reviews:
        row = candidates[(review["repeat"], review["case_id"])]
        if (review["observed_hash"] != digest(row["observed"])
                or review["reviewer_kind"] not in {"human", "assistant"}
                or not review["reviewer"].strip() or not review["rationale"].strip()
                or review["accuracy_passed"] is not True
                or review["no_answer_leak"] is not True or review.get("disputed")):
            raise ValueError("harness teaching review failed or unbound")
