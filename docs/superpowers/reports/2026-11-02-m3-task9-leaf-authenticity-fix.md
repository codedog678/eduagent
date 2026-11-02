# Task9 Frozen Leaf Authenticity: Fresh Implementation Result

## 状态与冻结身份

本轮是 fresh 实现者的工程修复和验证，不是独立 SPEC/CODE 审查，不自行授予 Task9 验收或发布资格。已有批准设计和 Task9 六步复用，没有重问执行授权。下一步由父侧核验 NEWfreeze，fresh WHOLE SPEC；只有新的 SPEC PASS 归档后，才进入 fresh WHOLE CODE。Task10 未启动。

- 唯一产品树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`，分支 `feature/m3-trusted-policy-promotion`。
- 起点：`855d5c6660343c24df0bef5ad4cf77160e83c566`，起点 parent `c52aaababba238ec26282f8c560c8f565a60a09e`。
- NEW 产品 commit：`1b8e4b745126c92cfd56f9f021388dd615d98791`，parent 为上述起点；正常 HEREDOC commit，没有 amend、push、config 或 hook bypass。
- 最终 `357` 个 `python/`、`frontend/` 源文件含新增测试，全集 SHA-256：`14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813`。`product-freeze.json` 列出每个路径与 SHA，已逐项核验产品 commit 实际 Git blob。全集摘要采用排序 path/hash 对的 canonical JSON，排除 docs/evidence，避免循环。
- primary `eduagent` 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`；266 source SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`，源码、测试、索引、`.venv` 和源树 Vite 缓存只读。
- 此文件先完整写入 `/tmp/m3-task9-leaf-authenticity-fix-result.md`，然后同字节复制到 `docs/superpowers/reports/2026-11-02-m3-task9-leaf-authenticity-fix.md`。
- 最终 docs/review HEAD 在正常 NEW docs commit 后解析，记录在 `/tmp/m3-task9-leaf-authenticity-fix-freeze.json`，并交给父侧。该外部 sidecar 同时包含实际 HEAD/parent、product、source、报告与 manifest SHA；不把包含自身的 commit SHA 写入其内容形成自引用。

## 修复范围

产品仅五条路径：

| 路径 | 修改 |
| --- | --- |
| `python/core/distributed/health_evidence_identity.py` | 新增小型有界纯验证组件，canonical observation key、排序、窗口两端、passed 空 triggered、Shadow parent pairing、Canary rehearsal/operation 同分布及非 production namespace |
| `python/core/distributed/policy_health.py` | observation key 和 same_distribution 移入共享组件，保留原 import/re-export 使用方式 |
| `python/core/distributed/promotion_repository.py` | 权威冻结叶子使用共享关系验证，保留完整评估、阈值、成本及时间身份验证 |
| `python/core/distributed/ops_queries.py` | 在现有 bounded 精确冻结摘要中共享纯关系验证，不调用 command/evaluator 或无界 replay |
| `python/tests/distributed/test_ops_leaf_authenticity.py` | 47 项完整真实 PG HTTP GET 集成回归，两个 cohort、两门禁、独立 Active、合法替换对照 |

坏 local passed source 不认证；Canary 的独立合法 Shadow 仍保留。Active 引用的精确 Canary leaf 无效时，整条 consumed_chain 断开，不借旧 Shadow 或别的合法叶子。合法双来源、独立 Shadow、Active local 真基线、低样本 failed/unknown 与 hold/fail 历史没有删除，minima 没有降低。共享组件只处理既有 bounded 集合的身份关系；Ops 原摘要验证仍与权威重评估职责分离，未来聚合规则变更仍需完整矩阵验证。

新增文件全是 API 集成测试，没有修改单元测试文件；已读取相应技能，单测生成流程不适用于这些 API/GUI 测试。

## RED 与最终 GREEN

有效 RED 均先在真实 migration/FK/append-only PG 中追加新 UUID 记录，权威先校验同一精确 leaf，再完整 HTTP GET 200；旧收据和 observation 保留。旧 runner 已复制并重绑定本轮 OWN，不覆盖历史 golden。

| 本人执行 | 通过 / 总数 | 失败性质 |
| --- | --- | --- |
| `red-valid-leaf` | 2 / 9 | 7 项有效 local 真实性失败 |
| `red-valid-active` | 1 / 6 | 5 项同类 Canary 输入的独立 Active 尾断言失败，不称 12 类独立反例 |
| `red-new-get` | 14 / 47 | 33 项有效新增 GET 失败，无 setup error |
| `green-new-get` | 47 / 47 | 修复后全通过 |
| `green-leaf-active` | 15 / 15 | 合法对照及独立断链通过 |
| `green-minimum` | 28 / 28 | minima、非 pass、真实基线通过 |
| `final-backend` | 1911 / 1911 | 完整 backend，359.79 秒 |
| `final-api` | 362 / 362 | 原 API315 + 新 GET47，105.21 秒 |
| `final-integrity` | 131 / 131 | source integrity、独立 metadata/链探测的扩大集合 |
| `final-leaf-minimum` | 90 / 90 | 新47 + minimum28 + 独立15，重叠最终复跑 |
| Node20 `final-build` | exit 0 | tsc + Vite；保留大 chunk 警告 |
| `final-ui` | 54 / 54 | 原全部 UI，双 viewport |
| 额外可视化选择 | 2 + 2 | Trace2、Policies2；`final-visual4` 标签实际 XML 是2，不误报4 |
| 七原 PG production 场景 | 14 / 14 | current/history/approval malformed/genuine malformed/genuine valid/referenced poison/minimum zero |
| 五新增 PG production 场景 | 10 / 10 | local bad、Active bad、local valid、Active valid、Shadow valid |

这些套件有重叠，不能相加为独立样本。原 F1/C1/S1/S2/S3/S1-R、Decimal 21/21、Active local 基线、完整断链、只读事务/隐私、auth/keyset/固定 Trace 身份均被完整 backend/API/UI 和独立矩阵覆盖。

原字节保留的无效尝试：初次两个 pytest 未传 `-c pyproject.toml`，`red-fresh-leaf` 9失败与 `red-fresh-active` 6失败不是有效业务 RED；随后正确配置另起新 DB。production 的 `approval_malformed` 拼写没有选中故障注入，两个合法对照被坏链断言误判；正确场景名另跑通过。新增 local bad 初次启动证明的 Decimal 不能序列化，未执行 browser，用新标签修正重跑，半写入 JSON 原样保留。运行时脚本把39项目约束加5下限误认为总39，以及 Trace parser 初次只支持 `_sha1` 不支持实际 `_file`，均属于证据脚本错误，原 tool 日志和成功的原 pip 输出保留，修正后完整核验通过。未将这些失败删除或混入最终工程通过率。

## 生产页面、Trace 与环境

本人实际 `view_image` 检查六张关键截图，包括坏 Active、合法 Active、坏 local、历史 local、移动 Trace 和 Policies；`view-image-review.json` 记录文件与观察。坏 Active 健康门禁为 unknown 且无认证来源；合法链两条 consumed 来源带“非本部署新观测”提示。移动表格可横滚，部分 region 截图因滚动会截到 sticky header 或裁切表格列，不把它们宣称为像素完美 UI 审查。

- 本轮 `28` XML、`30` 起末快照对完整解析；对应快照完全一致。
- `84` Trace ZIP、`2982` 成员逐字节 SHA/结构解析，生产 Trace 中 `104` 份真实 JS/CSS 响应正文与本轮 `frontend/dist` 完全一致，不只相信截图或 asset 名称。
- production JSON 记录浏览器 `156` GET 和显式 request-context `104` GET（含保留的无效配置尝试）；这是已记录范围，history 的额外验证等不能据此推断所有 HTTP 总量。全 HTTP 总数为 `unknown`。
- 正确场景全部 GET-only、console/page errors 0、页面横向溢出 <=1px；移动横滚有 before/after 与实际 scrollLeft 断言。
- Node `20.19.5`：`/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`；依赖实体复制到自有 tmp，不 symlink 回源模块。
- Python 实际入口 `/tmp/eduagent-m3-patched-runtime/bin/python`，`3.11.17`；58 installed distributions，39实际 project/dev/build/requirements 约束 +5额外 repair floors 全满足，`pip check` 无断裂依赖。runtime 前后 metadata 一致，没有修改 runtime 或主 `.venv`。
- 本轮实际模型/新 Agent 请求数 `0`，实际费用 USD `0`，Agent50 仍 paused；PG 中 USD 是合成 fixture 账本，不是计费。没有 live provider、正式 v3/holdout、学生任务、Docker 安装或真实 CI 成功声明。

## 清理与完整证据

自有 E：`/tmp/m3-task9-leaf-fix-8551ecba-8589-42a0-b9d7-b3873a329816`。每次 invocation 新 UUID PG DB，finally exact drop；`cleanup-final.json` 记录26个实际 DB，均已不存在。共享 PG16.15 loopback57432、PID16852、指定原 data-dir 留存。自有 Redis62584 PID7250/run_id `83b415577ad1f46d20804806ccbf325dc5d4d14a` 的 PID 文件、dir/save/appendonly 全核验后 `SHUTDOWN NOSAVE`；没有 FLUSH/prefix DEL。248个日志内 exact reset streams 均已不存在；停止前12个残余 key 的创建包含未计量子进程，不声称完整 key 归属账本。62585/62586 已不监听。自有 modules/cache/tmp/pycache 清理；保留本次 dist、全部 raw、脚本和 trace。

起点 M3 `5492` 和 primary `1110` actual tracked Git blobs 已核验，历史 Task9 raw/manifest/失败原字节未改。每个测试 invocation 的命令、UTC 起止、exit、DB/drop、环境、source/index/mtime/venv/cache 前后记录在 raw；normal product commit 精确起止未计量，明确 unknown，实际 Git 时间和工具日志保留。产品暂存五文件实际秘密扫描通过。全 retained995文件/84ZIP/2982成员扫描，1个本地配置、2个不同实际 secret values，无值回显，无实际值或模式命中。另两条安全的生成扫描/封存记录加入最终997 payload；docs实际暂存集合再完整扫描，并把结果留在单独 staging evidence。

核心持久目录：`docs/superpowers/reports/task9-leaf-authenticity-fix-evidence/`。

- `manifest.json`：997 payload files，manifest 本身另外留存。
- manifest SHA-256：`37449214c2bb58d5c4e4119d2b0bda5915b39368e136d35b5fe6c2d6c0b3dfbf`。
- payload SHA-256：`c44505192c92ed41c69a6027c4f564af421262ecd6a485f534201d2487e7bb5f`。
- `product-freeze.json`：产品、parent、全部357路径与实际 blob 身份。
- `final-verification.json`：完整 XML/快照/Trace member/production asset bytes 清单。
- `historical-and-recovery-raw-audit.json`：既有失败与 raw 原字节/结构/Gitblob 核验。
- `cost-and-role-ledger.json`、`runtime-final.json`、`cleanup-final.json`：角色/成本/unknown、58+39+5、资源与保护边界。
- 单独 `task9-leaf-authenticity-fix-staging-evidence/`：docs暂存全字节扫描与 staged manifest，核心 manifest不循环包含后生成记录。

报告 SHA、最终 docs/review HEAD/parent、两个目录实际 Git blobs 及清洁保护状态在提交后的外部 freeze sidecar 核验。正常 hook 的硬编码2秒扫描若超时，不将其当作完整扫描通过；本人独立 full actual-byte/ZIP 扫描证据单列。没有 amend/push/gitconfig/hook bypass；最终结论仅为本轮工程修复验证完成、等待父侧 NEWfreeze 和顺序独立复审。
