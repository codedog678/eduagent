# Task9 S1-S3 Implementation Freeze

本文件仅为新实现者的实现和执行记录，不是 SPEC/CODE 审查，不授予 Task9 acceptance。
父侧须针对新冻结提交执行 fresh WHOLE SPEC；仅其 PASS 后才执行 fresh WHOLE CODE。
未启动 Task10、Agent50、模型请求、生产发布或 push。

## 身份与范围

- 唯一产品工作树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 分支：`feature/m3-trusted-policy-promotion`。
- 起始/NEWcommit parent：`3444cf1967f9b5c9d64fde824dd4b53333a29143`。
- 该 parent 的 parent：`2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d`。
- 修改前完整 352 source SHA：`78fb2d84827b0e9c32df1bebbee9d4840f5eff301100da0a9f5489a0146b4357`。
- 最终完整 **353 source** SHA：`1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65`。
- 自有 raw：`/tmp/m3-task9-fix-48fc04af-9228-4c6b-90bb-bb7109644afa`，下文称 E。
- 原始报告完整读取：`task9-health-binding-spec-failure-evidence/review-result.md`。
- 3444cf1 的全部 206 原归档路径逐字节核验并保留；没有覆盖旧固定 OWN 或旧 collector。

仅三项产品/测试路径：

1. `python/core/distributed/ops_queries.py`。
2. `python/tests/distributed/test_ops_health_binding.py`。
3. `python/tests/distributed/test_ops_source_integrity.py`，新增 67 项真实 PG 回归。

其余新增路径仅本报告与 `task9-source-integrity-fix-evidence/` 自有留档。
具体全部文件清单在该目录 `manifest.json`；最终 commit、staged 文件和 Gitblob
核验在 E 的 `freeze-verification.json` 及 `/tmp/m3-task9-source-integrity-fix-result.md`。
提交自身 hash 的 postcommit 记录在 E，不伪造自引用的仓库内 commit hash。

## 实现

### S1

`_transition_identity` 从 immutable 前序/目标部署重建完整 `PromotionCommand`：
command_id、environment、expected_version、current_state、target_state、
traffic_basis_points、actor、reason 全部进入已有契约的 canonical command hash。
不再只比较 approval 和 audit 的两个自由声明相等。

核对 audit 的 command/deployment/environment/event/time、actor/reason、strict int
from/to versions、immutable required_receipts 与目标迁移所需健康项。Shadow→Canary
与 Canary→Active 使用相同纯身份关系检查。候选/稳定 policy、threshold body/hash、
salt、previousStable 和时间边界保持一致。

Active approval 额外核对 authenticated issuer/model/data_role、零费用、
与已消费 Canary health 的 sample_count、精确 command_id/hash、actor/reason、
Canary deployment/version/threshold、receipt/evidence hash。两条真实合法来源继续可见。
Ops 不重新执行资格 gate、健康判定或任何状态写入。

既有 synthetic Active “valid” 夹具原先只有两个相同的任意 hash 且缺少 required。
现仅在新记录插入前构造完整规范命令/required 正向对照，保留原断链断言；
未 UPDATE immutable fixture、停用 trigger、降低 cohort/阈值或隐藏全部来源。

### S2

按 artifact 四维与 issued_at 时间范围，先以 issued_at/created_at/receipt_id 降序
选择 latest；无法识别的 details 数组/null/缺失/非字符串/非法 command_id 保守遮蔽，
再验证具体绑定。可明确识别的其它 command 不串用。没有 passed filter 或旧 pass fallback。

审批 latest 遮蔽范围是当前读取时间，消费健康来源仍使用迁移时刻 cutoff。
后续 Canary health 不替换已消费冻结来源；当前 local invalid/nonpass 仍不借旧来源。
资格 F1 四维/三键逻辑未改。原始 approval.status 与验证后的 health_source 明确分离：
malformed approval 可以原始展示 passed，但不会认证为健康消费来源。

### S3

`_frozen_summary_matches` 检查冻结 candidate/stable key 列表、严格 run_count、
唯一性与 window_max_runs，receipt.sample_count 与 candidate key/统计精确一致。
仅以 PK key 集合读取至多 `2 * window_max_runs` 个 observation，检查 cohort、
policy、deployment、metric version、时间/顺序和有限非负 Decimal 费用，精确求和
与 receipt.cost 比较。不使用 rounded mean 乘 count，不补零、不重放 evaluator。

Active local 的稳定 baseline 只允许已消费 Canary 冻结 stable keys；真实 Active local
以及历史/最新来源回归保持可见。unknown 费用/计数保守不可用。
DTO/TS/frontend 产品协议未扩展，raw details/actor/reason/namespace 未投影。

## 实际执行

Python 3.11.17：`/tmp/eduagent-m3-patched-runtime/bin/python`；
PG16.15 `127.0.0.1:55432` postgres；Redis `127.0.0.1:56379/0`；
Node **20.19.5**，Vite7.3.7/plugin5.2/React18 锁未变。
仅设置 DISTRIBUTED_TEST_DATABASE_URL，显式移除生产 DATABASE_URL。
每个 pytest invocation 独占 UUID DB、finally drop；cache/basetemp/JUnit 指向 E。

以下 T/P/F/E/S 为 XML testcase 实际解析；不是把重复运行累加为独立样本。
全部 SHA、节点、模块、suite 秒、命令/UTC 时间在
`implementation-verification.json`、`*-command.json` 与 manifest。

| XML | T/P/F/E/S | suite 秒 |
| --- | --- | --- |
| red-relations | 11/2/9/0/0 | 5.880 |
| red-corroboration | 3/0/3/0/0 | 1.728 |
| green-probes-v1 | 56/56/0/0/0 | 21.146 |
| source-regressions-v1 | 67/57/10/0/0 | 28.010 |
| source-regressions-v2 | 67/67/0/0/0 | 25.099 |
| relations-api-final | 244/244/0/0/0 | 72.464 |
| full-final | **1793/1793/0/0/0** | 380.821 |
| ui-final | **54/54/0/0/0** | 39.721 |
| production-current（无效收集） | 0/0/0/0/0 | 0 |
| production-current-v2 | 2/2/0/0/0 | 1.159 |
| production-history | 2/2/0/0/0 | 1.380 |
| production-approval-malformed | 2/2/0/0/0 | 1.233 |
| production-genuine-malformed | 2/2/0/0/0 | 1.245 |
| production-genuine-valid | 2/2/0/0/0 | 1.438 |

有效 RED 在修改产品前独立执行，352 source 与起始 Gitblob 一致。
67 新项覆盖两段审计完整 identity、malformed 审批全类型/状态/其它 command、
Shadow/Canary count/cost、consumed source、strict unknown 和真实非零 Decimal。
核心健康对照仍 20/20；循环 Decimal 精度专门增加 21/21 对照而未降低最低样本阈值。

full UTC **2026-11-01T23:50:05.028631+00:00 → 23:56:57.675241+00:00**，
含进程/DB 收尾；pytest 380.84 秒，XML 380.821 秒。
full 含 test_ops_source_integrity=67、test_ops_health_binding=42、
test_promotion_ops_api=77、test_ops_api=19，F1 精确九项和 C1 同 artifact 两项
均有 actual node 列表。244 为这些 API/来源项、原 14 探测和 25 有界攻击的独立重跑，
不是替代 full。

build-final PASS，保留既有 chunk-size warning。UI54 使用 frozen mock fixtures，
不作为真实 PG production 的替代。前端使用独立实体 node_modules copy；
仅内部 .bin symlink 解析到 E，未指回产品或主工作树。31 tracked frontend 文件
除自有 cache/端口配置外逐字节一致。产品没有 frontend source 改动。

五个 production 场景分别启动/退出独立服务/DB；desktop 1440×900 与 mobile390×844。
真实 build dist 静态资源/真实 Ops API，无 route mocks/Vite dev，无业务 worker。
current B/hold 不借 A，history A 仍精确 receipt/window；两组 malformed 不借旧绿色
消费关系；genuine_valid 仍展示两条合法 consumed chain。各自输出目录有完整 trace。
实际查看 current/history、两组 malformed、合法链双视口及 UI Policies/Trace 截图，
移动表格横滚和页面 overflow ≤1 有实际断言。

生产资源实际加载字节与构建 dist 一致：
Ops JS `a4430d560a4461a12441b5433d72592db328646e28057a6426ecdef36a13e416`；
CSS `4f3070753582aa2f0a5e82bd28b182212feeb9724a92bf7aee5ae14a2a0c75e6`。
六项 dist SHA 全集保留后才清除 dist。

## 无效尝试

- source-regressions-v1 的 10 个 failed nodes 是新夹具错误：非法环境 DTO/503 两项、
  FK 两项、20 样本不足以形成循环小数精度对照两项、UUID/varchar 四项。
  它们不算产品 RED；修正夹具后 67 项 PASS，原 XML/log 全保留。
- 首次 production-current 缺 SPEC_SCENARIO，零收集；使用新 label v2 有效重跑。
- 错误只读路径定位、一次独立 playwright patch hunk mismatch、
  inventory 对 npm 内部 .bin 链接的过严断言均逐项记录，未覆盖有效证据。
- 没有中断产品评测；服务 TERM 为已完成场景的正常收尾，不是模型任务中断。

## 证明与清理

七次 pytest 的 14 份 before/after 快照每组完整相等；最终清理后第 15 份源快照仍
为完整 353（包括新增 untracked tests，而非遗漏新 test 的旧351）。
不同阶段的 352/353 摘要明确区分，不伪称产品修改前后源码一致。
主 eduagent HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422`，
266 source SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`
以及主 index/venv/源缓存前后未变。M3 index 仅明确 stage/NEWcommit 时更新。

`cleanup-verification.json` 核验本轮 **12 exact UUID DB / 248 exact UUID streams**
均不存在，34630/34631 关闭；每个 live 服务有 own PID、DB 与 cleanup 记录。
自有 frontend/node_modules、dist、pytest/tmp/npm/Vite/pycache 清理，不动主 venv/source/index。
所有有效、无效尝试、HTTP body、截图、trace、脚本、XML/log 保留。

执行账本：7 次 pytest invocation；真实 production 记录 **60 page HTTP + 42 explicit
request-context HTTP**，全部 GET。backend in-process API 与 UI mock HTTP 总数未装表，
明确不当作外部/模型请求。fixture model_calls 和 cost 是合成账本，不是实际计费。
**真实模型请求/费用 = 0/0**，无真实学生、formal holdout、生产发布、Docker/CI、
跨浏览器或 Task10 多 worker 证明。工程测试通过不等于独立规格/代码验收或教育安全证明。

## 交接

待 NEWcommit freeze/Gitblob 核验后，完整结果先落盘
`/tmp/m3-task9-source-integrity-fix-result.md` 再交给父侧。
只允许 fresh WHOLE SPEC → PASS 后 fresh WHOLE CODE；实现者未自行验收。
