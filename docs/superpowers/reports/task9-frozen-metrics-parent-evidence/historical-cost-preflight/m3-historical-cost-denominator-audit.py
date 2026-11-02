"""父侧固定 Git 原件的费用和分母复算；不执行模型、语义评分或产品。"""

import ast
import importlib.util
import json
import os
import posixpath
import socket
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.dont_write_bytecode = True
loader = importlib.util.spec_from_file_location(
    "history_checks", "/tmp/m3-historical-evidence-preflight.py"
)
h = importlib.util.module_from_spec(loader)
loader.loader.exec_module(h)
c, ROOT, PRIMARY = h.c, h.ROOT, h.PRIMARY
REV = "ffc607d4908dc50d3d7977d8056a7d33385b78e5"
OUT = Path("/tmp/m3-historical-cost-denominator-ffc607")
BASE = "docs/evals/harness-long-runs/20261027-source-recovery-deepseek-flash"
TOLERANCE = Decimal("0.000000000001")


def close_decimal(actual, expected):
    # 旧账本采用 float；保留原尾数，仅允许 1e-12 元的复算误差。
    assert abs(Decimal(str(actual)) - expected) <= TOLERANCE


def estimate(usage, pricing, period):
    assert {"input_tokens", "output_tokens"} <= usage.keys()
    assert all(type(v) is int and v >= 0 for v in usage.values())
    total, output = usage["input_tokens"], usage["output_tokens"]
    hit = usage.get("prompt_cache_hit_tokens", 0)
    assert 0 <= hit <= total
    if "prompt_cache_miss_tokens" in usage:
        assert hit + usage["prompt_cache_miss_tokens"] == total
    rates = pricing["per_million_tokens"][period]
    return (Decimal(total - hit) * Decimal(str(rates["input_miss"]))
            + Decimal(hit) * Decimal(str(rates["input_hit"]))
            + Decimal(output) * Decimal(str(rates["output"]))) / 1_000_000


def main():
    assert not OUT.exists(), "审计输出必须新建，不覆盖前次证据"
    started = datetime.now(UTC).isoformat()
    primary_before = h.snapshot(PRIMARY)
    assert not primary_before["status"]
    runtime_before = c.metadata(Path("/tmp/eduagent-m3-patched-runtime"))
    m3_head_before = c.git(ROOT, "rev-parse", "HEAD").decode().strip()
    blobs, historical_sources = {}, {}

    def read_bytes(path):
        path = posixpath.normpath(path)
        c.safe_relative(path)
        if path not in blobs:
            blobs[path] = c.git(ROOT, "show", f"{REV}:{path}")
        return blobs[path]

    def read(path):
        return json.loads(read_bytes(path))

    protocol = read(BASE + "/run-protocol.json")
    current_result_path = BASE + "/result.json"
    paths = [posixpath.normpath(BASE + "/" + p) for p in protocol["prior_runs"]]
    paths.append(current_result_path)
    assert len(set(paths)) == len(paths) == 8
    run_rows, request_rows, total_manifest_artifacts = [], [], 0
    latest_dataset_sha = c.sha(read_bytes(BASE + "/dataset.jsonl"))
    prior_connect = socket.socket.connect

    def deny_connect(*args, **kwargs):
        raise AssertionError("费用历史复算禁止网络")

    socket.socket.connect = deny_connect
    try:
        for path in paths:
            parent = posixpath.dirname(path)
            result = read(path)
            manifest = read(parent + "/manifest.json")
            manifest_artifacts = 0
            for name, info in manifest["artifacts"].items():
                c.safe_relative(name)
                assert c.sha(read_bytes(parent + "/" + name)) == info["sha256"]
                manifest_artifacts += 1
            total_manifest_artifacts += manifest_artifacts
            assert result["dataset_revision"] == latest_dataset_sha
            assert result["provider"] == "deepseek"
            assert result["model"] == manifest["model"] == "deepseek-flash"
            assert result["config"] == read(current_result_path)["config"]
            assert result["config_fingerprint"] == read(current_result_path)["config_fingerprint"]
            assert result["budget"]["pricing"] == read(current_result_path)["budget"]["pricing"]
            source_rev = result["code_revision"]["git_head"]
            source_path = f"historical-source/{source_rev}/python/evals/live_budget.py"
            if source_path not in historical_sources:
                historical_sources[source_path] = c.git(
                    ROOT, "show", f"{source_rev}:python/evals/live_budget.py"
                )
            # AST 读取价格常量，不 import 历史产品模块。
            source_tree = ast.parse(historical_sources[source_path])
            pricing = next(ast.literal_eval(node.value) for node in source_tree.body
                           if isinstance(node, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "PRICING"
                                   for t in node.targets))
            assert pricing == result["budget"]["pricing"]
            rows = []
            for case in result["live"]["results"]:
                for stage_id, stage in case["observed"]["stages"].items():
                    for request in stage["model_requests"]:
                        rows.append(dict(case_id=case["case_id"], stage_id=stage_id,
                                         request_no=request["request_no"],
                                         kind=request["kind"], status=request["status"],
                                         error=request.get("error"), usage=request.get("usage", {}),
                                         duration_ms=request["duration_ms"]))
            rows.sort(key=lambda row: row["request_no"])
            budget = result["budget"]
            assert [row["request_no"] for row in rows] == list(range(1, budget["requests"] + 1))
            assert len(rows) == budget["requests"] == result["live"]["metrics"]["model_calls"]
            ledger = read(parent + "/cost-ledger.json")
            assert ledger["summary"] == budget
            assert ledger["code_revision"] == result["code_revision"]
            assert ledger["dataset_revision"] == result["dataset_revision"]
            assert len(ledger["requests"]) == len(rows)
            confirmed = 0
            totals = {"off_peak": Decimal(0), "peak": Decimal(0)}
            for row, saved in zip(rows, ledger["requests"], strict=True):
                for key, value in row.items():
                    assert saved.get(key) == value, (parent, row["request_no"], key)
                known = {"input_tokens", "output_tokens"} <= row["usage"].keys()
                if ledger["schema"] == "eduagent.harness-long-task-cost-ledger.v2":
                    assert saved["usage_confirmed"] == known
                else:
                    assert ledger["schema"] == "eduagent.harness-long-task-cost-ledger.v1"
                    assert "usage_confirmed" not in saved
                    # v1 没有确认字段；从原 usage 字段复算，不补造旧字段。
                    assert known
                recomputed = {}
                for period in totals:
                    value = estimate(row["usage"], pricing, period) if known else None
                    recomputed[period] = str(value) if value is not None else None
                    if value is None:
                        assert saved[f"estimated_{period}_cny"] is None
                    else:
                        close_decimal(saved[f"estimated_{period}_cny"], value)
                        totals[period] += value
                confirmed += known
                request_rows.append(dict(
                    run_id=parent.rsplit("/", 1)[-1], source_revision=source_rev,
                    case_id=row["case_id"], stage_id=row["stage_id"],
                    request_no=row["request_no"], status=row["status"],
                    error_present=row["error"] is not None, kind=row["kind"],
                    usage=row["usage"], usage_confirmed=known, estimates_cny=recomputed,
                    origin=f"{path}:live.results[].observed.stages.{row['stage_id']}.model_requests[]",
                ))
            usage_keys = set(budget["usage"])
            computed_usage = {key: sum(row["usage"].get(key, 0) for row in rows
                                       if {"input_tokens", "output_tokens"} <= row["usage"].keys())
                              for key in usage_keys}
            assert computed_usage == budget["usage"]
            for period, amount in totals.items():
                close_decimal(budget[f"estimated_{period}_cny"], amount)
            assert budget["billing_status"] == ledger["billing_status"] == "estimate_only"
            run_rows.append(dict(
                run_id=parent.rsplit("/", 1)[-1], result_path=path,
                generated_at=result["generated_at"], code_revision=result["code_revision"],
                original_manifest_data_role=manifest.get("data_role"),
                comparison_data_role=protocol["data_role"],
                scorer_version=result.get("scorer_version", "unversioned_v1"),
                cases=len(result["live"]["results"]), requests=len(rows),
                request_status_counts=dict(Counter(row["status"] for row in rows)),
                confirmed_requests=confirmed, unknown_usage_requests=len(rows) - confirmed,
                estimates_cny={period: str(amount) for period, amount in totals.items()},
                usage=computed_usage, unconfirmed_reservation_cny=budget["unconfirmed_reservation_cny"],
                manifest_artifacts_checked=manifest_artifacts,
                original_ledger_schema=ledger["schema"],
                usage_confirmation_explicit_in_ledger=ledger["schema"].endswith(".v2"),
            ))
        last_five = run_rows[-5:]
        first_three = run_rows[:3]
        assert sum(r["requests"] for r in last_five[:-1]) == protocol[
            "current_conversation_tracked_before_run"]["formal_requests"] == 117
        before_peak = sum(Decimal(r["estimates_cny"]["peak"]) for r in last_five[:-1])
        close_decimal(protocol["current_conversation_tracked_before_run"]["formal_estimated_peak_cny"],
                      before_peak)
        assert sum(r["requests"] for r in last_five) == 147
        assert sum(r["requests"] for r in first_three) == 104
        assert sum(r["requests"] for r in run_rows) == len(request_rows) == 251
        verification = read(BASE + "/verification.json")
        assert verification["current_conversation_formal_totals"]["requests"] == 147
        final_five_peak = sum(Decimal(r["estimates_cny"]["peak"]) for r in last_five)
        close_decimal(verification["current_conversation_formal_totals"]["estimated_peak_cny"],
                      final_five_peak)

        agent_dir = "docs/evals/20261025/agent50-live"
        agent = read(agent_dir + "/tutor-agent50-live.json")
        state = read(agent_dir + "/run-state.json")
        agent_protocol = read(agent_dir + "/run-protocol.json")
        assert state["semantic_review_status"] == "paused_by_user"
        assert state["final_task_success_rate"] is state["tool_semantic_accuracy"] is None
        agent_totals = {"off_peak": Decimal(0), "peak": Decimal(0)}
        cases, meters = [], []
        agent_groups = []
        for declared in agent_protocol["batches"]:
            batch = read(agent_dir + f"/batch-{declared['batch']}.json")
            assert [r["case_id"] for r in batch["results"]] == declared["case_ids"]
            batch_meters = [meter for case in batch["results"] for meter in case["metering"]]
            assert len(batch_meters) == batch["budget"]["requests"]
            agent_groups.append(dict(batch=declared["batch"], cases=len(batch["results"]),
                                     requests=len(batch_meters)))
            cases.extend(batch["results"])
            meters.extend(batch_meters)
        assert cases == agent["results"] and len(cases) == 50
        for case in cases:
            for meter in case["metering"]:
                assert meter["status"] == "usage_recorded"
                for period in agent_totals:
                    amount = estimate(meter["usage"], agent["budget"]["pricing"], period)
                    close_decimal(meter[f"estimated_{period}_cny"], amount)
                    agent_totals[period] += amount
        assert len(meters) == agent["budget"]["requests"] == state["model_requests"] == 82
        assert {k: sum(m["usage"].get(k, 0) for m in meters)
                for k in agent["budget"]["usage"]} == agent["budget"]["usage"]
        for period, amount in agent_totals.items():
            close_decimal(agent["budget"][f"estimated_{period}_cny"], amount)
        assert agent["budget"]["billing_status"] == "estimate_only"
    finally:
        socket.socket.connect = prior_connect

    # 已运行的实现者可以修改 M3；只证明固定 Git 原件，绝不冒充两树均未变化。
    primary_after = h.snapshot(PRIMARY)
    runtime_after = c.metadata(Path("/tmp/eduagent-m3-patched-runtime"))
    assert primary_after == primary_before
    assert runtime_after == runtime_before
    mapping = {p: c.sha(data) for p, data in blobs.items()}
    c.blobs(ROOT, REV, mapping)
    for path, data in historical_sources.items():
        revision = path.split("/")[1]
        actual = c.git(ROOT, "show", f"{revision}:python/evals/live_budget.py")
        assert actual == data
    configs, values = c.secret_values((ROOT, PRIMARY))
    for name, data in {**blobs, **historical_sources}.items():
        c.scan_bytes(data, name, values)
    OUT.mkdir()
    for group, content in (("frozen-git", blobs), ("historical-sources", historical_sources)):
        for path, data in content.items():
            target = OUT / group / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    (OUT / "primary-before.json").write_text(json.dumps(primary_before, indent=2) + "\n")
    (OUT / "primary-after.json").write_text(json.dumps(primary_after, indent=2) + "\n")
    result = dict(
        started_at=started, finished_at=datetime.now(UTC).isoformat(),
        role="parent historical cost-and-denominator preflight; not final acceptance",
        frozen_revision=REV, frozen_files=mapping, frozen_file_count=len(mapping),
        frozen_payload_sha256=c.combined(mapping),
        historical_sources={p: c.sha(data) for p, data in historical_sources.items()},
        manifest_artifacts_checked=total_manifest_artifacts,
        primary_full_snapshot_equal=True, shared_runtime_metadata_equal=True,
        m3_current_head_before=m3_head_before,
        m3_current_head_after=c.git(ROOT, "rev-parse", "HEAD").decode().strip(),
        m3_worktree_immutability_claimed=False, runs=run_rows, requests=request_rows,
        last_five=dict(requests=147, cases_executed=30, unique_cases=6,
                       estimates_cny={period: str(sum(Decimal(r["estimates_cny"][period])
                                                      for r in last_five))
                                      for period in ("off_peak", "peak")}),
        eight_runs=dict(requests=251, cases_executed=48, unique_cases=6,
                        estimates_cny={period: str(sum(Decimal(r["estimates_cny"][period])
                                                       for r in run_rows))
                                       for period in ("off_peak", "peak")}),
        agent50=dict(cases=50, requests=82, batches=agent_groups,
                     usage=agent["budget"]["usage"], unknown_usage_requests=0,
                     estimates_cny={p: str(v) for p, v in agent_totals.items()},
                     semantic_review_status=state["semantic_review_status"],
                     final_task_success_rate=None, tool_semantic_accuracy=None),
        verification_tolerance_cny=str(TOLERANCE), historical_float_bytes_preserved=True,
        source_pricing_constant_checked_by_ast=True,
        pricing_source_network_reverification=False, new_model_requests=0, http_requests=0,
        unknown_other_network_usage="C34 unmetered usage and possible charge remain unknown",
        billing_status="estimate_only", final_freeze_reverification_required=True,
        actual_secret_config_files=configs, actual_secret_values_checked=len(values),
        invalid_auxiliary_commands=[
            dict(shell_id="f77f646e4b480fbb04c7de0bc8f4b7cb", exit_code=1,
                 reason="zsh unmatched optional file glob; no product or model executed"),
            dict(shell_id="e8716a239566a0828cabdb29bdf2848e", exit_code=1,
                 reason="audit assumed v2 usage_confirmed in two v1 ledgers; corrected to schema-specific reading",
                 raw_error="KeyError: 'usage_confirmed'",
                 affected_original_archives_unchanged=True),
            dict(shell_id="2ec0896a786bda48e54d11694a41294f", exit_code=1,
                 reason="earliest manifest has no data_role; retain original null and cite latest comparison protocol separately",
                 raw_error="KeyError: 'data_role'",
                 affected_original_archives_unchanged=True),
        ],
    )
    (OUT / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    markdown = [
        "# 历史费用与比较分母复算",
        "",
        f"固定 Git `{REV}`。从原逐请求用量按历史冻结价格用 Decimal 重算；"
        "原 float 尾数保持不变，单笔与汇总允许误差 1e-12 元。未请求模型或网络，"
        "未评分 Agent50，未执行产品。本材料是最终审计准备，须在最终版本重核。",
        "",
        "| 统计范围 | 实际请求 | 场景分母 | 估价区间（元） |",
        "| --- | ---: | --- | --- |",
    ]
    for key, label, denominator in (
        ("last_five", "第五轮分析所在对话的五轮", "30 次执行、重复使用 6 例"),
        ("eight_runs", "八轮同评分比较的原模型请求", "48 次执行、重复使用 6 例"),
        ("agent50", "Agent50 五批次", "50 例，语义审阅仍暂停"),
    ):
        row = result[key]
        costs = row["estimates_cny"]
        markdown.append(f"| {label} | {row['requests']} | {denominator} | "
                        f"{costs['off_peak']}–{costs['peak']} |")
    markdown += [
        "",
        "147 次由最后五轮真实请求合计得到；八轮比较另外包含较早三轮的 104 次，"
        "合计 251 次。两者统计范围不同。不能把复用的 48 次执行称 48 个独立留出场景；"
        "本审计不把 Agent50 和八轮请求相加成所有会话的全局总账。",
        "",
        "费用是按 2026-10-25 历史冻结价格的估算，未访问价格网址重新验证，"
        "不是当前价格或供应商账单。缺缓存命中字段的已确认用量按 miss 估价；"
        "未知用量保留 unknown。C34 旧测试网络用量及可能费用仍未知。",
        "",
        "逐笔原件、8 个运行身份、状态和费用重算见 audit.json 与 frozen-git/；"
        "每份历史 estimator 的实际 Git 原字节保存在 historical-sources/。"
        "这里只验证费用/分母/字节，不重算八轮自动评分，也不授予当前 Judge v3 发布资格。",
        "",
        f"本次 {len(mapping)} 个冻结原件、{total_manifest_artifacts} 项 manifest 条目、"
        f"{len(historical_sources)} 份历史价格源码已核验。primary 全 tracked/index/venv/"
        "Vite cache 快照前后相等，共享 runtime 元数据相等。M3 实现者正在运行，"
        "本报告仅证明固定 Git 原件，没有宣称 M3 工作树未变化。",
        "",
        f"冻结原件摘要 `{c.combined(mapping)}`。",
    ]
    (OUT / "report.md").write_text("\n".join(markdown) + "\n")
    for path in OUT.rglob("*"):
        if path.is_file():
            c.scan_bytes(path.read_bytes(), str(path.relative_to(OUT)), values)
    print(json.dumps({k: result[k] for k in (
        "frozen_revision", "frozen_file_count", "manifest_artifacts_checked",
        "frozen_payload_sha256", "last_five", "eight_runs", "agent50",
        "primary_full_snapshot_equal", "shared_runtime_metadata_equal",
        "new_model_requests", "http_requests",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
