"""Seal the independent CODE result only after all evidence is retained."""

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shutil
import sys

import bootstrap
import final_checks
import prepare
import review

OWN, ROOT = review.OWN, review.ROOT
EXTERNAL = Path("/tmp/m3-task9-minimum-code-result.md")
FINDING = {
    "title": "冻结叶子真实性校验不完整，错误认证 local 和 Active 消费链",
    "file": "python/core/distributed/ops_queries.py",
    "start_line": 583, "end_line": 596,
    "severity": "P1", "category": "BUSINESS_SEMANTICS", "confidence": 10,
    "rationale": (
        "有界叶校验只检查格式、部分身份、排序/计数和 Decimal cost，未核验 canonical "
        "observation_key、Canary 同分布/非 production namespace、Shadow 同 parent pairing、"
        "window start/end 和 passed window 空 triggered_thresholds。真实 PostgreSQL append-only "
        "fixture 保留原合法证据，新增真实 FK Run/observation，按替换 keys 重算窗口与收据哈希。"
        "权威 helper 拒绝 7 种无效 leaf，但完整 GET 200 仍输出 passed/local。另独立 5 项 "
        "Canary Active 断言全部失败，返回 Canary/Shadow 两条 passed/consumed_chain，合法 "
        "Canary/Shadow 和 Active 双来源对照通过。原 XML/完整 GET/commands 留 fresh-leaf 与 "
        "fresh-active。原回归和新 SPEC PASS 不抵消反例。未证明写晋级绕过，P1 为明确条件性"
        "可信证据投影错误。"
    ),
    "suggestion": (
        "补齐有界纯读的 canonical 身份、namespace/distribution、parent pairing 和 "
        "window 关系谓词，可与权威 helper 共享验证组件；精确 Canary 失败后整条 Active "
        "依赖链不可认证。保留独立合法 Shadow 历史和非 passed local 对照，新增完整 GET 回归；"
        "不调 command、不无界 replay evaluator、不借新合法 leaf 或前端删行。"
    ),
    "code_snippet": "\n".join((ROOT / "python/core/distributed/ops_queries.py")
                              .read_text().splitlines()[582:596]),
    "actual": "authority rejects; GET local passed; Active has Canary and Shadow consumed_chain",
    "expected": "invalid local gate absent; invalid exact Canary breaks whole Active consumed chain",
    "evidence": ["fresh-leaf.xml", "fresh-active.xml",
                 "fresh-active/active-noncanonical_key.json"],
}


def artifacts():
    assert EXTERNAL.exists()
    assert not (OWN / "review-result.md").exists()
    shutil.copyfile(EXTERNAL, OWN / "review-result.md")
    assert EXTERNAL.read_bytes() == (OWN / "review-result.md").read_bytes()
    diff = (OWN / "whole-task9-source.diff").read_text()
    name, spans = None, []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            name = line[6:]
        elif name == FINDING["file"] and line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, count = int(match[1]), int(match[2] or 1)
            spans.append((start, start + count - 1))
    assert any(start <= FINDING["end_line"] and end >= FINDING["start_line"] for start, end in spans)
    assert FINDING["end_line"] <= len((ROOT / FINDING["file"]).read_text().splitlines())
    for group in (1, 2, 3, 4):
        with (OWN / "group" / f"group_{group}.jsonl").open("x") as out:
            if group == 2:
                out.write(json.dumps(FINDING, ensure_ascii=False) + "\n")
    with (OWN / "comments.jsonl").open("x") as out:
        out.write(json.dumps(FINDING, ensure_ascii=False) + "\n")
    review.write("final_comments.json", [FINDING])
    visuals = []
    for label in ("current", "history", "approval-malformed", "genuine-malformed",
                  "genuine-valid", "referenced-poison", "minimum-zero"):
        for viewport in ("desktop", "mobile"):
            path = OWN / "screenshots" / f"detail-prod-final-{label}-{viewport}-left.png"
            visuals.append({"path": str(path.relative_to(OWN)),
                "sha256": final_checks.sha(path.read_bytes()),
                "actual_view_image_inspected": True,
                "viewport": viewport, "scenario": label})
    for label in ("policies", "policy-trace"):
        for viewport in ("desktop", "mobile"):
            path = OWN / "screenshots" / f"{label}-{viewport}.png"
            visuals.append({"path": str(path.relative_to(OWN)),
                "sha256": final_checks.sha(path.read_bytes()),
                "actual_view_image_inspected": True,
                "viewport": viewport, "scenario": label})
    review.write("actual-visual-inspections.json", {
        "time_recorded": datetime.now(UTC).isoformat(), "images": visuals,
        "view_image_count": len(visuals),
        "notes": [
            "Genuine valid Active shows precise Canary/Shadow consumed sources.",
            "Malformed approval, referenced poison and zero minimum show no consumed health sources.",
            "Mobile tables scroll internally; screenshot is not proof of initial scrollLeft zero.",
            "Trace viewport shows stored immutable binding, not a current-head substitution.",
        ],
    })
    old = ROOT / "docs/superpowers/reports/task9-minimum-spec-failure-evidence/test_minimum_evidence.py"
    owned = OWN / "test_minimum_evidence.py"
    import difflib
    review.write("minimum-probe-independent-provenance.json", {
        "original_sha256": final_checks.sha(old.read_bytes()),
        "owned_sha256": final_checks.sha(owned.read_bytes()),
        "original_gitblob_equal": old.read_bytes() == review.git(
            ROOT, "show", review.HEAD + ":" + str(old.relative_to(ROOT))),
        "gate_specific_correction": "do not reject independent legal Shadow history",
        "diff": "".join(difflib.unified_diff(
            old.read_text().splitlines(keepends=True), owned.read_text().splitlines(keepends=True))),
    })
    report_md = f"""# 独立 WHOLE CODE 评审

结论：**WHOLECODEFAIL**。1 个 P1，置信度 10/10。
范围：Task8 acceptance 至 `{review.HEAD}` 的全部 Task9，17 源路径及完整原证据。

## [P1] {FINDING['title']}

位置：`{FINDING['file']}:583-596`；调用链 `:483-521,724-731`。

{FINDING['rationale']}

```python
{FINDING['code_snippet']}
```

修复建议：{FINDING['suggestion']}

全后端1864、API315、完整链111、下限28、最终UI54、真实PG七场景双视口14均通过；
新local7种有效FAIL和独立Active5项FAIL不能被常规green抵消。重复/重叠不相加。
完整命令/UTC/XML/SHA/清理/限制见同字节主报告 `review-result.md`。
未commit/push/实施修复/Task10/模型请求或授予Task9验收。
"""
    with (OWN / "review-overview.md").open("x") as out:
        out.write(report_md)
    review.write("cross-group-diff-validation.json", {
        "time": datetime.now(UTC).isoformat(), "new_side_hunks": spans,
        "finding_in_whole_diff": True, "valid_line_range": True,
        "deduplicated_findings": 1, "groups_completed_locally": [1, 2, 3, 4],
        "typescript_rules_applied": True, "no_external_assumption_for_finding": True,
        "no_product_write_or_commit": True,
    })


def seal():
    report = OWN / "review-result.md"
    assert report.read_bytes() == EXTERNAL.read_bytes()
    scan = json.loads((OWN / "independent-secret-postreport.json").read_bytes())
    assert scan["local_secret_values_distinct"] == 2
    assert scan["secret_matches"] == scan["pattern_matches"] == 0
    assert scan["raw_pattern_literal_hits"] == 2
    snapshot = bootstrap.snapshot()
    assert snapshot == json.loads((OWN / "initial-snapshot.json").read_bytes())
    prepare.verify_blobs(review.HEAD, snapshot["m3"]["tracked"])
    deps = json.loads((OWN / "dependencies-independent.json").read_bytes())
    assert bootstrap.metadata(Path(review.PY).parent.parent) == deps["runtime_readonly_before_after"]
    cleanup = json.loads((OWN / "cleanup-independent.json").read_bytes())
    assert cleanup["own_uuid_database_count"] == 13 and not cleanup["database_check"]["remaining"]
    for port in (56737, 56738, 56739):
        import socket
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
    entries = {str(p.relative_to(OWN)): final_checks.sha(p.read_bytes())
               for p in final_checks.ref.retained_paths() if p.name != "retained-manifest.json"}
    review.write("retained-manifest.json", {
        "time": datetime.now(UTC).isoformat(), "command": sys.argv, "role": "fresh WHOLE CODE reviewer",
        "verdict": "WHOLECODEFAIL", "head": review.HEAD, "files": entries, "file_count": len(entries),
        "payload_sha256": final_checks.sha(json.dumps(sorted(entries.items()),
            ensure_ascii=True, separators=(",", ":")).encode()),
        "report_sha256": final_checks.sha(report.read_bytes()), "same_byte_report": report.name,
        "external_report": str(EXTERNAL), "self_excluded_no_hash_cycle": True,
        "actual_model_requests": 0, "actual_model_cost_usd": "0", "all_http_total": "unknown",
    })
    path = OWN / "retained-manifest.json"
    manifest = json.loads(path.read_bytes())
    for name, digest in manifest["files"].items():
        assert final_checks.sha((OWN / name).read_bytes()) == digest, name
    print(json.dumps({
        "verdict": "WHOLECODEFAIL", "findings": 1, "P1": 1, "confidence": 10,
        "file_count": manifest["file_count"], "payload_sha256": manifest["payload_sha256"],
        "manifest_sha256": final_checks.sha(path.read_bytes()),
        "report_sha256": manifest["report_sha256"], "head": review.HEAD,
        "m3_source_count": snapshot["m3"]["source_count"],
        "m3_source_sha256": snapshot["m3"]["source_sha256"],
        "m3_tracked_gitblob_verified": len(snapshot["m3"]["tracked"]),
        "primary_tracked_protected": len(snapshot["primary"]["tracked"]),
        "all_retained_bytes_verified": True, "whole_start_end_equal": True,
        "owned_databases_remaining": 0, "owned_services_stopped": True,
        "shared_pg_and_runtime_preserved": True, "secret_matches": 0,
        "raw_scanner_literal_hits": scan["raw_pattern_literal_hits"],
        "no_task9_acceptance_task10_or_product_writes": True,
    }, indent=2))


if __name__ == "__main__":
    {"artifacts": artifacts, "seal": seal}[sys.argv[1]]()
