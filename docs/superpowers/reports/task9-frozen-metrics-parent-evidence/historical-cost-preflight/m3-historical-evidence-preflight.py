"""只读复算面试历史证据；不评分Agent50、不请求模型、不授予发布资格。"""
import importlib.util
import json
import math
import os
import socket
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
PRIMARY = ROOT.with_name("eduagent")
OUT = Path("/tmp/m3-historical-evidence-preflight.json")
spec = importlib.util.spec_from_file_location("checks", "/tmp/m3-parent-evidence-checks.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def snapshot(root):
    index = Path(c.git(root, "rev-parse", "--git-path", "index").decode().strip())
    if not index.is_absolute():
        index = root / index
    return dict(
        head=c.git(root, "rev-parse", "HEAD").decode().strip(),
        status=c.git(root, "status", "--porcelain").decode(),
        tracked={p: c.sha((root / p).read_bytes()) for p in sorted(c.names(root, "ls-files", "-z"))},
        index_sha256=c.sha(index.read_bytes()), index_mtime_ns=index.stat().st_mtime_ns,
        venv=c.metadata(root / ".venv"), vite=c.metadata(root / "frontend/node_modules/.vite"),
        vite_temp=c.metadata(root / "frontend/node_modules/.vite-temp"))


def load(path):
    return json.loads(path.read_bytes())


def main():
    assert not OUT.exists()
    started = datetime.now(UTC).isoformat()
    state = dict(m3=snapshot(ROOT), primary=snapshot(PRIMARY))
    assert not state["m3"]["status"] and not state["primary"]["status"]
    assert state["m3"]["head"] == "c52aaababba238ec26282f8c560c8f565a60a09e"
    a = ROOT / "docs/evals/20261025/agent50-live"
    raw, runstate, protocol = (load(a / p) for p in
                               ("tutor-agent50-live.json", "run-state.json", "run-protocol.json"))
    dataset = ROOT / "docs/evals/tutor-agent-50-review.jsonl"
    definitions = [json.loads(x) for x in dataset.read_bytes().splitlines() if x.strip()]
    dataset_manifest = load(ROOT / "docs/evals/tutor-agent-50-manifest.json")
    assert c.sha(dataset.read_bytes()) == raw["dataset_revision"] == protocol["dataset_sha256"] == dataset_manifest["dataset_sha256"]
    assert len(definitions) == len(raw["results"]) == raw["total"] == runstate["saved_cases"] == 50
    ids = [x["case_id"] for x in definitions]
    assert len(set(ids)) == 50 and Counter(ids) == Counter(x["case_id"] for x in raw["results"])
    all_results, batch_summary = [], []
    for plan in protocol["batches"]:
        batch = load(a / f"batch-{plan['batch']}.json")
        assert batch["code_revision"] == raw["code_revision"] == protocol["code_revision"]
        for key in ("config_fingerprint", "config", "dataset_revision", "provider", "model"):
            assert batch[key] == raw[key]
        assert [x["case_id"] for x in batch["results"]] == plan["case_ids"] == batch["selected_case_ids"]
        assert len(batch["results"]) == batch["total"]
        assert sum(len(x["metering"]) for x in batch["results"]) == batch["budget"]["requests"]
        all_results.extend(batch["results"])
        batch_summary.append(dict(batch=plan["batch"], cases=batch["total"],
                                  requests=batch["budget"]["requests"]))
    assert all_results == raw["results"]
    assert raw["selected_case_ids"] == [x["case_id"] for x in all_results]
    meter = [row for case in all_results for row in case["metering"]]
    assert len(meter) == raw["budget"]["requests"] == runstate["model_requests"] == 82
    usage_status = dict(Counter(row["status"] for row in meter))
    assert usage_status == {"usage_recorded": 82}
    usage = {key: sum(row["usage"].get(key, 0) for row in meter) for key in raw["budget"]["usage"]}
    assert usage == raw["budget"]["usage"]
    costs = {}
    for period in ("peak", "off_peak"):
        key = f"estimated_{period}_cny"
        amount = sum(row[key] for row in meter)
        assert math.isclose(amount, raw["budget"][key], abs_tol=1e-12)
        costs[key] = amount
    assert math.isclose(costs["estimated_peak_cny"], runstate["estimated_peak_cny"], abs_tol=1e-12)
    assert raw["budget"]["billing_status"] == "estimate_only"
    automatic = sum(row["automatic_passed"] is True for row in all_results)
    assert automatic == runstate["automatic_contract_passed"] == 40
    assert runstate["automatic_contract_total"] == 50
    assert runstate["semantic_review_status"] == "paused_by_user"
    assert runstate["final_task_success_rate"] is None and runstate["tool_semantic_accuracy"] is None
    assert runstate["baseline_git_head"] == raw["code_revision"]["git_head"] == "48a02715195f41696917bf5693030cc761ccf349"
    assert runstate["python_source_sha256"] == raw["code_revision"]["python_source_sha256"]
    assert c.sha((ROOT / "docs/evals/20261025/tutor-semantic-rubric-20261025.md").read_bytes()) == protocol["rubric_sha256"]

    r = ROOT / "docs/evals/rsi-review-20261029/calibration-replay"
    manifest, saved = load(r / "manifest.json"), load(r / "report.json")
    original_dir = ROOT / "docs/evals/rsi-campaigns/20261027-real-01/calibration"
    original = load(original_dir / "manifest.json")
    assert c.sha((original_dir / "manifest.json").read_bytes()) == manifest["source_manifest_sha256"]
    assert len(original["items"]) == len(manifest["items"]) == len(saved["comparisons"]) == 20
    assert c.sha((ROOT / "python/evals/datasets/tutor_agent50_rsi_v2.jsonl").read_bytes()) == manifest["dataset_sha256"]
    paths = set(a.rglob("*")) | set(r.rglob("*"))
    paths |= {dataset, ROOT / "docs/evals/tutor-agent-50-manifest.json",
              ROOT / "docs/evals/20261025/tutor-semantic-rubric-20261025.md",
              ROOT / "docs/evals/build-agent50-dataset.py",
              ROOT / "python/evals/datasets/tutor_agent50_rsi_v2.jsonl",
              original_dir / "manifest.json", original_dir / "report.json"}
    controlled = 0
    for old, new in zip(original["items"], manifest["items"]):
        source_bytes = (original_dir / c.safe_relative(old["evidence_path"])).read_bytes()
        record_bytes = (r / c.safe_relative(new["evidence_path"])).read_bytes()
        assert c.sha(source_bytes) == old["evidence_sha256"]
        assert c.sha(record_bytes) == new["evidence_sha256"]
        source, record = json.loads(source_bytes), json.loads(record_bytes)
        assert record["source_evidence_sha256"] == old["evidence_sha256"]
        assert record["observed"] == source["observed"]
        assert record["score"]["raw_judgment"] == {
            "decisions": source["score"]["decisions"], "semantic": source["score"]["semantic"],
        }
        assert record["judge_identity"] == source["judge_identity"]
        assert new["reviewer_kind"] == "assistant"
        controlled += "controlled" in new["provenance"]
        paths.add(original_dir / old["evidence_path"])
    assert controlled == 6
    sys.path.insert(0, str(ROOT / "python"))
    from evals.optimization.calibration import verify_manifest
    from evals.optimization.leakage import protocol_identity
    from evals.live_cases import LiveCase
    current_identity = protocol_identity()
    historical_identity = manifest["scoring_protocol"]
    assert current_identity != historical_identity
    old_dir = Path("/tmp") / ("m3-historical-v1-" + str(uuid.uuid4()))
    old_dir.mkdir()
    old_blobs = {}
    for name, field in (("leakage.py", "engine_sha256"), ("leakage_rules.json", "rules_sha256")):
        content = c.git(ROOT, "show", "dd1dfb4:python/evals/optimization/" + name)
        assert c.sha(content) == historical_identity[field]
        (old_dir / name).write_bytes(content)
        old_blobs[name] = c.sha(content)
    old_spec = importlib.util.spec_from_file_location("frozen_v1_leakage", old_dir / "leakage.py")
    old_engine = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old_engine)
    assert old_engine.protocol_identity() == historical_identity
    # 该函数只读证据与重算规则；显式禁止网络，不恢复任何模型审阅。
    original_connect = socket.socket.connect
    def deny_connect(*args, **kwargs):
        raise AssertionError("historical provenance audit must not connect")
    socket.socket.connect = deny_connect
    try:
        try:
            verify_manifest(r / "manifest.json")
        except ValueError as exc:
            assert str(exc) == "calibration scoring protocol missing or changed"
            current_rejection = str(exc)
        else:
            raise AssertionError("current v2 must reject historical v1")
        for item in manifest["items"]:
            record = load(r / item["evidence_path"])
            case = LiveCase.model_validate(record["case"])
            case.validate_contract()
            assert case.model_dump(by_alias=True) == record["case"]
            combined = old_engine.combine_judgment(case, record["observed"], record["score"]["raw_judgment"])
            assert all(record["score"][k] == v for k, v in combined.items())
    finally:
        socket.socket.connect = original_connect
    verified = {k: saved[k] for k in ("agreement", "counts", "matches", "data_role",
                                    "status", "passed", "measured_passed")}
    assert verified["agreement"] == 1 and not verified["passed"] and verified["measured_passed"]
    assert verified["data_role"] == "development_replay" and verified["status"] == "validation_required"
    rows = saved["comparisons"]
    assert sum(row["raw_judge_passed"] == row["reference_passed"] for row in rows) == 17
    assert sum(row["hybrid_passed"] == row["reference_passed"] for row in rows) == 20
    assert saved["new_model_requests"] == saved["new_estimated_cny"] == 0
    assert not saved["independent_human_gold"]
    protected = snapshot(ROOT), snapshot(PRIMARY)
    assert protected == (state["m3"], state["primary"])
    paths = sorted(p for p in paths if p.is_file())
    hashes = {str(p.relative_to(ROOT)): c.sha(p.read_bytes()) for p in paths}
    c.blobs(ROOT, state["m3"]["head"], hashes)
    result = dict(started_at=started, finished_at=datetime.now(UTC).isoformat(),
                  role="parent read-only historical provenance; not final project acceptance",
                  observed_head=state["m3"]["head"], files=hashes, file_count=len(hashes),
                  payload_sha256=c.combined(hashes), samebyte_gitblobs=True,
                  protected_snapshot_before_after_equal=True,
                  agent50=dict(cases=50, requests=82, batch_summary=batch_summary,
                               automatic_contract_passed=40, automatic_contract_total=50,
                               observed_status_counts=dict(Counter(row["status"] for row in all_results)),
                               execution_outcome_counts=dict(Counter(row["execution_outcome"] for row in all_results)),
                               costs=costs, usage=usage, billing_status="estimate_only",
                               semantic_review_status="paused_by_user", final_task_success_rate=None,
                               tool_semantic_accuracy=None, semantic_labels_not_generated=True,
                               code_revision=raw["code_revision"],
                               authored_manifest_status_not_runtime_status=dataset_manifest["dataset_status"]),
                  rsi=dict(samples=20, controlled_responses=6, real_archived_responses=14,
                           raw_matches=17, hybrid_matches=20, current_rules_recomputed=False,
                           current_identity=current_identity,
                           current_verifier_rejection_expected=current_rejection,
                           historical_v1_full_overlay_recomputed=True,
                           historical_identity=historical_identity,
                           frozen_v1_source_revision="dd1dfb4", frozen_v1_sources=old_blobs,
                           isolated_v1_sources_directory=str(old_dir),
                           original_source_files_byte_exact=True,
                           raw_judgment_semantic_and_decision_fields_exact=True, validation=verified,
                           new_model_requests=0, new_cost_cny=0),
                  audit_new_model_requests=0, all_http_requests=0,
                  final_freeze_reverification_required=True,
                  prior_invalid_auxiliary_reads=[
                      dict(shell_id="7d0a2fb4c0462bb3cbaf5c60c021427e", exit_code=1,
                           reason="assumed cases field; live archive uses results"),
                      dict(shell_id="60fb81c06c1d14e6557a039433e08f18", exit_code=2,
                           reason="referenced nonexistent eval runner; no runner executed"),
                      dict(shell_id="40c1554371579750bc827138609c70d3", exit_code=1,
                           reason="old score stores decisions/semantic directly; raw_judgment added by replay"),
                      dict(shell_id="d0e90bb86b83357348de9baa45157889", exit_code=1,
                           reason="current hybrid v2 rejects historical v1 as required; not historical corruption")])
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("observed_head", "file_count", "payload_sha256",
                     "protected_snapshot_before_after_equal", "audit_new_model_requests",
                     "final_freeze_reverification_required")}, indent=2))


if __name__ == "__main__":
    main()
