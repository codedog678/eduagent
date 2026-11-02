"""持久保留已核验父侧原件，新增文档，不改变实现或旧证据。"""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import UTC, datetime

os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("checks", "/tmp/m3-parent-evidence-checks.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
R = Path("/Users/bytedance/Documents/trae_projects/eduagent-m3")
BASE = "5d6e717b3ea715524cfed2e7e2e4ee143499618e"
E = Path("/tmp/m3-task9-metrics-fix-41068737-e9a6-42a2-89f8-10d7dda22e11")
OUT = R / "docs/superpowers/reports/task9-frozen-metrics-parent-evidence"
REPORT = OUT.parent / "2026-11-02-m3-task9-frozen-metrics-parent-verification.md"
COST = Path("/tmp/m3-historical-cost-denominator-ffc607")


def main():
    assert not OUT.exists() and not REPORT.exists()
    assert c.git(R, "rev-parse", "HEAD").decode().strip() == BASE
    assert not c.git(R, "status", "--porcelain")
    proof_path = Path("/tmp/m3-task9-frozen-metrics-parent-verification.json")
    proof = json.loads(proof_path.read_bytes())
    assert proof["head"] == BASE and proof["source_count"] == 358
    assert proof["both_current_trees_index_venv_cache_before_after_equal"]
    sources = {
        "parent-verification.json": proof_path,
        "parent-verify.py": Path("/tmp/m3-task9-frozen-metrics-parent-verify.py"),
        "parent-retain.py": Path(__file__),
        "implementer-handoff-postcommit.json": E / "handoff-postcommit.json",
        "implementer-handoff-commit.log": E / "handoff-commit.log",
        "implementer-handoff-final-verification.json": E / "handoff-final-verification.json",
        "implementer-handoff-verify.py": E / "handoff_verify.py",
    }
    seal = json.loads((COST / "parent-payload-manifest.json").read_bytes())
    assert seal["file_count"] == 140
    assert c.combined(seal["files"]) == seal["payload_sha256"]
    assert seal["payload_sha256"] == "a85bcb1cf3f0ddf91b4cefb4ccb7e20e39724e68876bbc7f397c56d7699c5fdf"
    for name, digest in seal["files"].items():
        assert c.sha((COST / name).read_bytes()) == digest
    for path in COST.rglob("*"):
        if path.is_file():
            sources["historical-cost-preflight/" + str(path.relative_to(COST))] = path
    configs, values = c.secret_values((R, R.with_name("eduagent")))
    OUT.mkdir()
    files = {}
    for name, source in sources.items():
        target = OUT / c.safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert target.read_bytes() == source.read_bytes()
        files[name] = c.sha(target.read_bytes())
    pictures = [
        ("detail-green-production-metrics_active_permission_violation-desktop.png",
         "实际查看；两健康 gate 为 unknown，没有显示坏 Canary 的 consumed 健康链。"
         "部署仍是历史 Active fixture、当前 head 是 Canary，不能称发布写成功或绕过。"),
        ("detail-green-production-leaf_active_valid-mobile-left.png",
         "实际查看；合法 Shadow 与 Canary 两个 consumed 来源标签可见。"),
        ("detail-green-production-metrics_active_valid-mobile-left.png",
         "实际查看；两个健康 gate passed，但左侧截图来源文字裁切，不能声称标签全文可见。"),
        ("trace-pinned-mobile.png",
         "实际查看；固定 deployment/policy、stable/production 与 worker_id test-fixture 可见。"
         "该 PNG 属最终 PG Trace；较早 standalone PNG 未独立留存，早期 ZIP 仍在。"),
    ]
    original = R / "docs/superpowers/reports/task9-frozen-metrics-implementation-evidence"
    visual = dict(role="parent actual local image inspection, not independent acceptance",
                  images=[dict(path=str((original / "screenshots" / name).relative_to(R)),
                               sha256=c.sha((original / "screenshots" / name).read_bytes()),
                               judgment=judgment) for name, judgment in pictures],
                  actual_view_image_calls=4,
                  actual_mobile_scroll_source="parent-verification.json:final_mobile_actual_scroll",
                  read_only_followup="fresh SPEC should probe genuine health-worker fail windows "
                  "with optional hard_failures keys and predecessor hard violations outside the rolling "
                  "candidate/stable set; no failure or pass conclusion is inferred here")
    data = (json.dumps(visual, ensure_ascii=False, indent=2) + "\n").encode()
    (OUT / "parent-visual-notes.json").write_bytes(data)
    files["parent-visual-notes.json"] = c.sha(data)
    text = """# Task9 完整指标修复：父侧冻结与原件核验

父侧已核验工程冻结和原始材料；这不是独立规格或代码审查，不授予 Task9 验收。
接续顺序仍为 fresh WHOLE SPEC → 新 PASS 父核并 NEW 归档 → fresh WHOLE CODE。

产品 `780087401022dcfb3be904dee9ee442675625dc6`，父 `ffc607d4908dc50d3d7977d8056a7d33385b78e5`；
主证据 `be56f27b67ee3bc54db71388f68de86f70358313`；
交接 `5d6e717b3ea715524cfed2e7e2e4ee143499618e`，父为主证据。
完整源码 358 files，SHA `788bbb025f2b26684e676fbafd6b8aded30054d0541aa8a72d786356e5fe43f0`。

| 核验对象 | 父侧独立复算 |
| --- | --- |
| 实际 Git blob | 当前 M3 14889、起始 8225、primary 1110；新增文档 6663；仅四个产品文件变化 |
| 主与补充 payload | 6645 与 15 文件；manifest 逐项匹配，均不包含自己 |
| 原始执行证据 | 49 XML 每个 testcase/outcome/issues/time；51 完整快照原字节相等，其中 24 对属于最终源码 |
| 最终矩阵 | backend 2080、API 492、integrity 131、boundaries 67、原42互补42、UI54，均无失败/错误/跳过 |
| 保留失败 | 原互补 6P/36F；所有中间失败、setup 与辅助错误不覆盖、不与最终分母相加 |
| 浏览器原件 | 176 ZIP / 5816 members 的 CRC、SHA、事件与实际网络正文；共272资产比对，最终136 |
| 最终真实 PG 生产构建 | 17场景×2视口=34，16手机健康场景真实横滚、2实际 pinned Trace 视口 |
| 历史原件 | 7005 files / 19 manifests / 270 XML / 826 ZIP / 29194 members；旧352-source清单对原Git版本 |
| 资源 | 47精确UUID库实际 remaining0；共享PG16.15/57432/PID16852保留；62049/62050/62051关闭 |
| 运行环境 | Python3.11.17、58dist、39声明+5修复floor；两当前树tracked/index/venv/cache和runtime首末一致 |
| 秘密扫描 | 两actual值、15999 current Git原件、1002ZIP/35010members、1TAR/358members；有效命中0 |

秘密模式只分类旧固定 Git blob 的 scanner assertion 两行，未扩大白名单。
Redis 自有非持久服务经身份/配置验证后 SHUTDOWN NOSAVE；子进程 key 账本不完整，
不能说逐 key 删除。原 raw XML/log/HTML 空格不重写；正常 hook 超时不等于完整扫描通过。

实际查看四张关键图，判断及截图 SHA 在 parent-visual-notes.json。
合法 metrics Active 左侧手机图来源文本裁切，不称整段可见；合法 leaf Active 图两来源标签可见。
Active fixture 的 is_current=false/head仍Canary 如实保留，不能称实际晋级写入。
父侧另标记 fresh SPEC 需探测真实 health worker 的 hard_failures/前序硬违规窗口，
这里只列检查议题，不预判其展示为 PASS 或 FAIL。

新增历史费用准备完整原件随本次持久归档：124固定 Git 原件/108manifest条目/8历史价格源码；
五轮147请求、八轮251请求，分别0.50906508–1.01813016与0.76513228–1.53026456元估价。
两者有重叠、只重复6例；Agent50另82请求，语义仍paused/null。
原v1缺确认字段、最早manifest缺data_role均保留，未回填旧档。
费用按2026-10-25历史冻结价格，不是当前价或供应商账单；C34旧联网费用仍unknown。

本轮0新模型、actual USD 0；全局HTTP数unknown。未Docker/CI实跑、未正式v3资格或教学效果验证。
完整父核、实施者交接提交后的raw与代码、历史费用原件均位于同层
`task9-frozen-metrics-parent-evidence/`。本报告与manifest不循环包含自身提交身份；
新提交之后的真实HEAD/日志交下一波归档。
"""
    REPORT.write_text(text)
    for path in [REPORT, *[OUT / name for name in files]]:
        raw = path.read_bytes()
        c.scan_bytes(raw, str(path), values)
        assert not re.search(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})\b", raw)
    manifest = dict(role="parent provenance only, not SPEC/CODE acceptance",
                    verified_head=BASE, product=proof["product"], source_count=358,
                    source_sha256=proof["source_sha256"], files=files, payload_count=len(files),
                    payload_sha256=c.combined(files), report_sha256=c.sha(REPORT.read_bytes()),
                    actual_secret_values_checked=len(values), config_files=configs,
                    secret_matches=0, manifest_excludes_itself=True,
                    new_commit_proof_next_wave=True, timestamp=datetime.now(UTC).isoformat())
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    c.scan_bytes((OUT / "manifest.json").read_bytes(), "manifest.json", values)
    print(json.dumps({k: manifest[k] for k in (
        "verified_head", "product", "source_count", "source_sha256", "payload_count",
        "payload_sha256", "report_sha256", "actual_secret_values_checked", "secret_matches",
    )}, indent=2))


if __name__ == "__main__":
    main()
