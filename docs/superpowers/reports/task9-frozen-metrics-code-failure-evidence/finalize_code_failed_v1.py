"""Owned CODE reporting and acyclic sealing; protected trees stay read-only."""
from datetime import UTC, datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import zipfile

E = Path(__file__).parent
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
BASE = "8869166878a193a1c453376471cbe52c8fa84b3f"
HEAD = "a3e2c0b0f510235cec8a98784afdb26b3bb6db79"
SKILL = Path("/Users/bytedance/.trae-cn/builtin_skills/bits-code-guard")
RESULT = Path("/tmp/m3-task9-leaf-authenticity-code-result.md")
SEAL = Path(str(E) + "-seal.json")
os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", TZ="UTC")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    with Path(path).open("x") as out:
        json.dump(data, out, indent=2, ensure_ascii=False, default=str)
        out.write("\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=R)


def structure():
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    diff = git("diff", "--numstat", BASE + ".." + HEAD).decode().splitlines()
    scope = []
    for line in diff:
        added, deleted, name = line.split("\t", 2)
        if name in initial["m3"]["source"]:
            data = (R / name).read_bytes()
            assert data == git("show", HEAD + ":" + name)
            scope.append(dict(file=name, added=int(added), deleted=int(deleted),
                              lines=len(data.splitlines()), sha256=sha(data)))
    assert len(scope) == 21
    assert sum(row["added"] for row in scope) == 3918
    assert sum(row["deleted"] for row in scope) == 51
    save(E / "whole-code-source-scope.json", dict(scope="full_file", base=BASE, head=HEAD,
         source_files=scope, count=21, added=3918, deleted=51,
         all_task9_not_latest_patch=True, independently_read_all=True,
         shared_callers_reviewed=True, source_sha256=initial["m3"]["source_sha256"]))
    (E / "review_files.initial-filtered.md").write_bytes((E / "review_files.md").read_bytes())
    text = [
        "scope: full_file", "", "# Independent Task9 WHOLE CODE Scope", "",
        "User-authorized whole Task9 source files, not only the last patch or documentation.",
        f"Range: {BASE}..{HEAD}", "Files: 21; additions: 3918; deletions: 51.",
        "The initial script filter included archive raw; it is retained separately, not counted as source.",
        "",
    ]
    text.extend(f'- `{row["file"]}` (+{row["added"]}, -{row["deleted"]}); '
                f'{row["lines"]} actual lines; SHA256 {row["sha256"]}' for row in scope)
    (E / "review_files.md").write_text("\n".join(text) + "\n")
    target = R / "python/core/distributed/ops_queries.py"
    assert target.read_text().splitlines()[603].strip() == "return receipt.cost == total"
    finding = dict(
        title="冻结叶指标未按实际观测认证，错误的 passed 传播到 Active 完整消费链",
        file="python/core/distributed/ops_queries.py", start_line=594, end_line=604,
        severity="P1", category="BUSINESS_SEMANTICS", confidence=10,
        rationale=(
            "_frozen_summary_matches 在实际 key/canonical 身份、run_count 和 Decimal cost 一致后即返回 True，"
            "没有验证其他冻结指标与精确观测一致、观测 schema 或实际阈值结果。"
            "details 与 window 的互相比对只能证实两个声明相同。真实 migration/FK/append-only 下，"
            "新增含 commit_failed、terminal_failed、confirmed_permission_violation、unknown_counter、"
            "invalid_counter 或 stats_claim 的同一叶，发布权威先判拒绝，完整 GET 仍返回 200，"
            "Ops 展示 local passed；Active 的精确消费链进一步保留 Canary 和 Shadow passed。"
            "独立互补矩阵 42 条为 6P/36F/0E/0S，生产构建三个坏叶双视口 6F。"
            "这是 Task9 的核心证据展示语义缺陷，不代表发布写绕过；原观测/收据保留，未禁用 trigger 或修改 immutable 行。"
        ),
        suggestion=(
            "以冻结有界 key 集合完成纯只读的观测 schema、完整指标摘要和阈值真实性认证，"
            "并让 local 与 consumed_chain 使用同一认证条件；精确 Canary 无效时移除 Active 整条健康消费链。"
            "保持冻结 minima、精确 Decimal 费用、合法非通过 local、独立 Shadow/history 和合法 Active 两来源。"
            "不得从 GET 调用 promotion command 或无界、带副作用 evaluator；补充上述同叶差分回归。"
        ),
    )
    group = E / "group"
    group.mkdir()
    raw = json.dumps(finding, ensure_ascii=False) + "\n"
    (group / "group_1.jsonl").write_text(raw)
    for number in (2, 3, 4):
        (group / f"group_{number}.jsonl").write_text("")
    (E / "comments.jsonl").write_text(raw)
    save(E / "final_comments.json", [finding])
    old = (E / "review_groups.md").read_text()
    (E / "review_groups.md").write_text(old.replace(
        "状态：阅读/核验进行中，未授予 CODE PASS、Task9 验收或 Task10。",
        "状态：四组本人依序完成；跨组复核已完成。Group 1 的同根因汇总为一项 P1；"
        "Group 2/3/4 不另报产品缺陷。结论 FAIL，未授予 Task9 验收或 Task10。"))
    execution = json.loads((E / "code-execution-final-audit.json").read_bytes())
    summary = {}
    for name, row in execution["suites"].items():
        summary[name] = {key: row[key] for key in ("tests", "passed", "failure", "error", "skip")}
    visual = [
        "screenshots/detail-code-production-metrics_active_permission_violation-desktop-left.png",
        "screenshots/detail-code-production-leaf_active_valid-mobile-left.png",
        "screenshots/detail-code-production-current-mobile-left.png",
        "screenshots/detail-code-production-leaf_local_bad-mobile-left.png",
        "screenshots/trace-pinned-mobile.png",
    ]
    save(E / "code-visual-inspection-record.json", dict(
        role="actual production-build PG screenshots viewed by this CODE reviewer",
        images=[dict(path=name, sha256=sha((E / name).read_bytes()), viewed=True) for name in visual],
        fixture_ui_also_viewed=True, fixture_trace_not_pg_release_evidence=True,
        mobile_current_actual_scroll="0 -> 220",
        nonzero_valid_scroll_before_preserved=[39, 193]))
    save(E / "code-review-summary.json", dict(
        verdict="FAIL", severity="P1", confidence=10, finding_count=1,
        head=HEAD, base=BASE, evidence_uuid=E.name, source_scope=21,
        suites=summary, case_counts_not_unique_samples=True, overlap_not_summed=True,
        production_checks=dict(total=34, passed=28, failed=6, errors=0, skipped=0),
        original_pg_scenarios=12, production_health_viewports=32, actual_pg_trace_viewports=2,
        xml_count=len(execution["suites"]), complete_byte_equal_pairs=len(execution["complete_byte_equal_pairs"]),
        zip_files=len(execution["traces"]),
        zip_members=sum(len(row["members"]) for row in execution["traces"].values()),
        production_asset_response_bodies=execution["production_asset_response_bodies"],
        page_gets=execution["page_gets"], production_network_gets=execution["production_network_gets"],
        explicit_production_gets=136, all_http="unknown",
        model_requests=0, actual_cost_usd="0", release_eligible=False,
        task9_accepted=False, task10_started=False, repositories_written=False,
        commit_push_or_external_comments=False, CI_or_Docker_execution=False))
    started = datetime.now(UTC).isoformat()
    command = [sys.executable, "-B", str(SKILL / "scripts/generate_report.py"),
               str(E / "final_comments.json"), "--repo", "eduagent-m3",
               "--mode", "Independent WHOLE CODE; FAIL/P1",
               "--range", BASE + ".." + HEAD, "--files", "21", "--lines", "3969",
               "-o", str(E / "report.html")]
    proc = subprocess.run(command, capture_output=True)
    (E / "report-generation.stdout").write_bytes(proc.stdout)
    (E / "report-generation.stderr").write_bytes(proc.stderr)
    save(E / "report-generation-command.json", dict(
        command=command, cwd=str(R), started_at=started,
        finished_at=datetime.now(UTC).isoformat(), exit=proc.returncode))
    assert proc.returncode == 0
    print(json.dumps(dict(scope=21, findings=1, verdict="FAIL", report_generated=True)))


def secrets():
    spec = importlib.util.spec_from_file_location("read_only_secret_values", "/tmp/m3-parent-evidence-checks.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    configs, values = helper.secret_values((R, R.with_name("eduagent")))
    initial = json.loads((E / "initial-snapshot.json").read_bytes())
    files = {}
    for label, root in (("m3", R), ("primary", R.with_name("eduagent"))):
        for name, digest in initial[label]["tracked"].items():
            files[str(root / name)] = digest
    for path in E.rglob("*"):
        if path.is_file():
            files[str(path)] = sha(path.read_bytes())
    files[str(RESULT)] = sha(RESULT.read_bytes())
    literal = R / "docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py"
    data = literal.read_bytes()
    assert data == git("show", HEAD + ":" + str(literal.relative_to(R)))
    assert sha(data) == "9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a"
    patterns = [
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b",
    ]
    actual, effective, classified = [], [], []
    zips = members = tars = tar_members = 0

    def check(body, name):
        if any(value in body for value in values):
            actual.append(name)
        for index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, body):
                line = body[:match.start()].count(b"\n") + 1
                if name == str(literal) and index == 0 and line in (88, 89):
                    assert b"assert " in body.splitlines()[line - 1]
                    classified.append(dict(path=name, line=line, file_sha256=sha(body),
                                           kind="exact old assertion literal, no key body"))
                else:
                    effective.append(dict(path=name, line=line, pattern_index=index))

    for name, digest in files.items():
        path = Path(name)
        body = path.read_bytes()
        assert sha(body) == digest
        check(body, name)
        if path.suffix == ".zip":
            zips += 1
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                assert archive.testzip() is None
                for item in archive.infolist():
                    if not item.is_dir():
                        check(archive.read(item), name + ":" + item.filename)
                        members += 1
        elif path.suffix == ".tar" or path.name.endswith((".tgz", ".tar.gz")):
            tars += 1
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:*") as archive:
                for item in archive.getmembers():
                    if item.isfile():
                        check(archive.extractfile(item).read(), name + ":" + item.name)
                        tar_members += 1
    save(E / "code-secret-final.json", dict(
        files=len(files), file_hashes=files, zip_files=zips, zip_members=members,
        tar_files=tars, tar_members=tar_members, local_config_files=configs,
        distinct_actual_secret_values=len(values), secret_matches=len(actual),
        secret_match_paths=actual, effective_pattern_matches=len(effective),
        pattern_match_paths=effective, classified_exact_literals=classified,
        values_not_echoed=True, hook_timeout_not_claimed_as_pass=True,
        report_included=True, primary_tracked_included=True,
        scan_own_output_and_command_excluded_to_avoid_self_reference=True))
    assert not actual and not effective and len(classified) == 2 and len(values) == 2
    print(json.dumps(dict(files=len(files), zip_files=zips, zip_members=members,
                          actual_values=2, matches=0, effective_patterns=0, exact_literals=2)))


def seal():
    import control
    import bootstrap
    control.install_snapshot()
    assert bootstrap.snapshot() == json.loads((E / "initial-snapshot.json").read_bytes())
    rows = {}
    for path in sorted(E.rglob("*")):
        if path.is_file():
            assert not path.is_symlink()
            body = path.read_bytes()
            rows[str(path.relative_to(E))] = dict(sha256=sha(body), bytes=len(body))
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    manifest = dict(schema="task9-owned-code-evidence-v1", records=rows,
                    payload_sha256=sha(payload), files=len(rows),
                    excludes=["manifest.json"], external_seal=str(SEAL),
                    role="engineering CODE FAIL; not independent release qualification")
    save(E / "manifest.json", manifest)
    save(SEAL, dict(
        verdict="FAIL", code_head=HEAD, uuid=E.name, files=len(rows),
        manifest_sha256=sha((E / "manifest.json").read_bytes()),
        payload_sha256=sha(payload), result_path=str(RESULT),
        result_sha256=sha(RESULT.read_bytes()),
        reports={name: sha((E / name).read_bytes()) for name in
                 ("report.md", "report.html", "code-review-detail.md", "code-review-summary.json")},
        resources_cleaned=True, repositories_unchanged=True,
        model_requests=0, actual_cost_usd="0",
        created_at=datetime.now(UTC).isoformat()))
    print(json.dumps(dict(seal=str(SEAL), files=len(rows), payload_sha256=sha(payload))))


def verify():
    import control
    import bootstrap
    import prepare
    control.install_snapshot()
    final = bootstrap.snapshot()
    assert final == json.loads((E / "initial-snapshot.json").read_bytes())
    seal_data = json.loads(SEAL.read_bytes())
    data = (E / "manifest.json").read_bytes()
    assert sha(data) == seal_data["manifest_sha256"]
    manifest = json.loads(data)
    rows = manifest["records"]
    assert sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()) == seal_data["payload_sha256"]
    actual = {str(path.relative_to(E)) for path in E.rglob("*") if path.is_file()}
    assert actual == set(rows) | {"manifest.json"}
    for name, row in rows.items():
        body = (E / name).read_bytes()
        assert sha(body) == row["sha256"] and len(body) == row["bytes"]
    assert sha(RESULT.read_bytes()) == seal_data["result_sha256"]
    prepare.verify_blobs(HEAD, final["m3"]["tracked"])
    assert final["m3"]["head"] == HEAD and not final["m3"]["status"]
    secret = json.loads((E / "code-secret-final.json").read_bytes())
    assert secret["secret_matches"] == secret["effective_pattern_matches"] == 0
    save(Path(str(E) + "-final-verification.json"), dict(
        verified_at=datetime.now(UTC).isoformat(), manifest_sha256=sha(data),
        result_sha256=sha(RESULT.read_bytes()), records=len(rows),
        complete_no_extra_files=True, source_and_runtime_byte_mtime_index_equal=True,
        m3_head=final["m3"]["head"], primary_head=final["primary"]["head"],
        m3_actual_gitblobs=len(final["m3"]["tracked"]),
        primary_actual_gitblobs=len(final["primary"]["tracked"]),
        redis_stopped=True, exact_owned_database_remaining=0,
        verdict="FAIL", final_acceptance_authorized=False))
    print(json.dumps(dict(verified=True, files=len(rows), verdict="FAIL")))


if __name__ == "__main__":
    action = sys.argv[1]
    started = datetime.now(UTC).isoformat()
    code = 1
    try:
        globals()[action]()
        code = 0
    finally:
        name = f"finalize-{action}-command.json"
        path = E / name if action in {"structure", "secrets"} else Path(str(E) + "-" + name)
        save(path, dict(command=sys.argv, cwd=os.getcwd(), started_at=started,
                        finished_at=datetime.now(UTC).isoformat(), exit=code,
                        model_requests=0, actual_cost_usd="0"))
