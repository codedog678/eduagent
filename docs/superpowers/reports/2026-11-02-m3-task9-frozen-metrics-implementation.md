# Task9 完整冻结指标真实性：实现交接

状态：工程实现与最终验证 GREEN，**不是独立 SPEC/CODE PASS，不是 Task9 验收**。等待父侧完整核验，再 fresh WHOLE SPEC；新 SPEC PASS 父核归档后才 fresh WHOLE CODE。本实现者未启动这两轮审查、Task10 或重复 agent。

## 版本与范围

唯一写入仓库 `/Users/bytedance/Documents/trae_projects/eduagent-m3`，分支 `feature/m3-trusted-policy-promotion`。设计和 Task9 六步计划已批准，不重新要求设计确认。

| 对象 | 实际身份 |
|---|---|
| 起始 clean HEAD | `ffc607d4908dc50d3d7977d8056a7d33385b78e5` |
| 起始父提交 | `a3e2c0b0f510235cec8a98784afdb26b3bb6db79` |
| 旧产品 / 旧源码 | `1b8e4b745126c92cfd56f9f021388dd615d98791` / 357 files，`14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813` |
| NEW 产品提交 | `780087401022dcfb3be904dee9ee442675625dc6`，父为起始 HEAD |
| NEW 主证据冻结 | `be56f27b67ee3bc54db71388f68de86f70358313`，父为 NEW 产品提交 |
| 最终完整源码 | 358 files，`788bbb025f2b26684e676fbafd6b8aded30054d0541aa8a72d786356e5fe43f0` |
| 主 payload | 6,645 files，`72b8ebce324a513ef8898d5857e3e0c14f80f5926cb8a211d7590e4876f11522` |
| 主冻结后验 | clean；14,872 M3 actual Git blobs、1,110 primary actual Git blobs 已实际读取核验 |

随后 NEW docs-only 交接提交的父为主证据冻结；其最终 HEAD、父、原始提交日志和后验验证见本轮 E 的 `handoff-postcommit.json`、`handoff-commit.log`。不可把提交自己的 hash 或提交后日志嵌入自己的不可变 blob；这些交父侧下一波归档，不能伪造循环 manifest。

## 实现

四个产品文件，实际 `+553/-24`；没有其他产品改动：

- `python/core/distributed/ops_queries.py`：针对窗口精确、有界的 candidate/stable keys，先认证实际观测 schema，再逐项认证完整指标、decision、触发阈值、精确 Decimal 费用。receipt/window 两个一致声明不再充当真实性证据；canonical 比较也区分 `False` 与 `0`。
- `python/core/distributed/policy_health.py`：抽取小型纯 `evaluate_matched_window`，复用已有纯 `evaluate_window`；原 worker 未匹配窗口分支保持相同公式和理由。GET 仅在已取有界集合上调用纯 schema/公式，不调用有状态 evaluator、command、rollback 或写入。
- `python/tests/distributed/test_ops_minimum_evidence.py`：把低样本/nonpass fixture 改为实际行支持的完整摘要；fail 对照追加真实硬失败观测，保留原行。
- `python/tests/distributed/test_ops_frozen_metrics.py`：169 个 PG/API 集成用例，覆盖全指标 missing/type/value/extra、实际观测 schema、延迟/费用/计数/阈值、精确 decision/reasons、合法指标、真实 worker hold/unknown 及 receipt 类型攻击。

local 与 consumed_chain 使用同一认证路径。精确 Canary 叶无效时 Active 整条健康消费链失效，不回退到另一叶；合法 Canary 的独立 Shadow/历史、合法 Active 两个 consumed 来源仍保留。20/20 minima、50/50 有界集合、21 项 Decimal、配对与分布、精确 stable 基线、时间/cutoff/元数据/audit/approval 关联保持既有回归。未知费用不补零，非通过诊断不被统一删掉。

## 有效 RED 与最终 GREEN

先在起始 357-source 上完整运行原 42 项：**6P/36F/0E/0S**。保留真实 authority-versus-GET JSON、XML、日志、原 receipt/观测行。之后相同输入首次 GREEN 42P，再于最终 358-source 运行 `green4-original42` 42P。

| 最终源码矩阵 | P/F/E/S | 原始入口 |
|---|---|---|
| 完整 backend | 2080/0/0/0 | `green-backend.xml` |
| API | 492/0/0/0 | `green-api.xml` |
| integrity / metadata 全矩阵 | 131/0/0/0 | `green-integrity.xml` |
| 独立 boundaries / minimum / leaf 补充 | 67/0/0/0 | `green-boundaries.xml` |
| 原完整指标互补矩阵 | 42/0/0/0 | `green4-original42.xml` |
| 全部 UI | 54/0/0/0 | `green-ui.xml` |
| Node 20.19.5 production build | exit 0 | `green-build-command.json`、`.log` |
| 实际 PG production，17 场景双 viewport | 34/0/0/0 | `green-production-*.xml` |

backend/API 包含新的 169 项 PG/API 指标用例；这些矩阵、重复运行和旧检查点存在重叠，**不相加为独立样本**。backend 覆盖既有 health/promotion/runtime/rollback 等共享行为，API/integrity/boundaries 覆盖 Task9 完整只读接口及既有安全/分页/授权/DTO/关联护栏，实际 argv 逐项留档。

生产构建 17 场景为原 12 场景、三个坏指标叶、合法指标 Active、真实 PG pinned Trace。每个场景使用新 UUID 数据库。三个坏指标叶不再展示虚假健康来源；合法 Active 两来源仍真实返回。Active 指标对照是 append-only 展示 fixture，`is_current=false`、head 仍为 Canary，不能写成实际晋级成功或发布写绕过。

最终 34 次 production viewport 的 **136 个实际 GET 资产正文**与当次 dist 字节一致；无非 GET 页面请求，GET 200、浏览器 error 0、overflow ≤1。16 个 health 场景手机均核验实际 scrollBefore/scrollAfter 增加，未用图宽代替真实横滚。真实 Run Trace 的响应正文、固定策略身份与 ZIP 证据来自实际 migrated PG。

## 原始证据

本轮 E：`/tmp/m3-task9-metrics-fix-41068737-e9a6-42a2-89f8-10d7dda22e11`。

主归档：`docs/superpowers/reports/task9-frozen-metrics-implementation-evidence/`。

提交/交接补充：`docs/superpowers/reports/task9-frozen-metrics-implementation-staging-evidence/`。

`source-manifest.json` 仅包含完整源码，排除 raw；主 `manifest.json` 不包含自己。补充 manifest 绑定主 freeze、报告与提交后材料，也不包含自己。本 `/tmp` 结果与仓库报告保持同字节。

- `execution-final-audit.json`：49 原 XML 全部逐 testcase 解析；51 complete before/after 原字节相等对，按五个源码检查点分组，最终源码 24 对；176 Trace ZIP / 5,816 members CRC、SHA、事件、响应正文核验。
- 两次完整 production 波次共 272 个资产响应正文，其中最终波次 136；68 个 viewport 原件包含 4 个真实 PG Trace 原件。早期重复波次保留但不加入最终独立分母。
- `historical-final-audit.json`：7,005 历史 files、19 manifests、270 XML、826 ZIP / 29,194 members；起始 8,225 actual Git blobs 与 primary 1,110 blobs；旧 352-source 清单对原 Git revision 实际读取，不与当前变更源码混比。历史 v1 改名原件及原无效 JSON 保留，旧归档没有修改。
- 新波次已包含上一轮尚未归档的 `m3-task9-metrics-code-fail-postcommit.json` 与 `m3-task9-metrics-code-fail-commit.log`。
- 执行命令有 UTC、argv、cwd、exit；完整探索读取 UTC 账本不可得，明确 unknown。模型请求 0、actual USD `0`、全局 HTTP 总数 unknown。

## 失败与限制

有效原 RED、早期 GREEN、最终 GREEN、中间失败和辅助 attempt 均保留，不覆盖旧材料：

- `metrics-attempt1` 213P/4F：Infinity 在 PG numeric 边界被拒绝，属于 setup，后改为明确 DB rejection control，不计 GET 业务失败。
- `final-backend` 2070P/6F、`final-api` 482P/6F：辅助 JSON 文件名冲突；改为 `metrics-` 前缀并重跑最终矩阵。
- 重用 `green-original42` 名称的一次尝试在 DB 创建前 AssertionError；原该名称证据保留，最终改用 `green4-original42`。该次独立 traceback/UTC 未落盘，不声称有完整原始记录。
- provenance parser 的旧 source manifest 比对对象错误、production batch 汇总误作单视口，两次失败命令记录及原脚本保留，修正后完整重跑；首次 docs 暂存因 `.gitignore:55` 拒绝，raw 日志保留，后只强制暂存精确新文档目录，未改配置。
- 实际 view_image 核验坏指标 Active desktop、合法 leaf Active mobile、合法 metrics Active mobile 和真实 Trace mobile。`metrics_active_valid` 左侧手机截图的来源文字部分裁切，不声称整段可见；另一合法 leaf Active 图两个来源标签确实可见。
- runner 的 `trace-pinned-{viewport}.png` 共享名称使较早 standalone PNG 被后续波次覆盖；当前 PNG 为最终绿色真实 PG Trace。较早各自 Trace ZIP 完整保留，但不伪称早期 standalone PNG 单独留存。
- 原 XML/log/error-context/HTML 尾空格未重写；raw diff-check exit 2 是已披露原始空格，不是代码 check PASS。产品与新 nonraw 报告检查 exit 0。

## 资源与秘密

47 个独立 UUID DB：13 pytest invocation + 34 production invocation，finally drop exit 0、实际查询 remaining 0；见 `resources-supplement.json`。共享 PostgreSQL 16.15、loopback57432、PID16852、原 data-dir 实际核验并保留。

本轮 Redis62049 的 PID/run_id/config 与起始身份一致，save 空、appendonly no，核验后 `SHUTDOWN NOSAVE`；62049/62050/62051 全关闭，无 FLUSH/PrefixDEL。子进程 key 账本不完整，保留剩余自有 key 清单，不声称逐 key 删除。

primary `eduagent` 的 source/tests/index/.venv、两树 source cache 与共享 Python runtime 只读；完整源码 bytes/mtime 与最终测试检查点一致。M3 index/HEAD 仅因获准 NEW 提交改变，不把它们说成首末不变。

fresh Python3.11.17 / 58 distributions、39 declarations + 5 repair floors 全核验，pip check/freeze exit 0；Node20.19.5 身份实际验证；自有 modules 为实体 copy，symlink 仅指向该实体内部。仅删除 E 内 `frontend/node_modules`、`cache`、`npm-cache`、`pycache`、`__pycache__`、`vite-cache` 等实际存在的指定缓存；raw/dist/basetemp 证据保留，包含 tmp 内原测试数据和转换文件，未笼统声称 tmp 已清空。

完整实际秘密扫描：15,966 files、1,002 ZIP / 35,010 members、1 TAR / 358 members，两个 actual secret values 与高置信模式有效命中 0，值不回显。只对旧 `parent-retain.py` 原 Git blob SHA `9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a` 的精确 88/89 行分类两个 scanner assertion literals，没有扩大白名单。随后新增归档、报告和提交材料另按实际值及模式扫描；正常 hooks 没有 bypass，前一轮 hook 2 秒 timeout 不作为完整 scan PASS。

未 amend、push、改 config 或 bypass hook。0 新模型，Agent50 semantic paused；未运行 Docker/live CI、未访问生产 URL/provider，未取得独立 release qualification、正式 v3 独立链或学生效果证据。**工程 GREEN 不能替代父核及后续 fresh WHOLE SPEC/CODE。**
