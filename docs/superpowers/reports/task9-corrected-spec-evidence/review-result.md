# Task9 排序修复后的 Fresh 全任务独立 SPEC 复审

结论：**PASS，未发现阻塞规格问题。** 原独立 FAIL 的 F1/P2 已由本轮真实 PostgreSQL、发布 authority 对照及 production 桌面/移动页面独立复现确认修复。本结论覆盖完整 Task9 六步与相关 design 不变量，不是仅一行 diff 或 F1 的复查。

本轮仅 SPEC。没有进行 CODE gate、Task10、源码修改、commit、push 或真实模型请求。Task9 尚不能据此宣称最终验收；父侧归档后决定启动 fresh CODE。

## 1. 身份与权威来源

- 唯一 source：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- HEAD：`e29bdb4d0c1b0e07b0e60a62ee61df3ae2e9915e`。
- Parent：`38f48d763b4a9599aa215f98a2cba1b32003b1e7`。
- Primary：`/Users/bytedance/Documents/trae_projects/eduagent`，只读；HEAD 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`。
- 351 个 tracked Python/frontend source combined SHA：`8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582`。
- 权威 plan：`docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md:1158-1252`，Task9 全六步。
- 权威 design：`docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md`，包括控制面只读、持久化不可变 assignment、Run 关联、隐私与证据角色相关不变量。
- 已完整读取新 brief、`/tmp/m3-task9-gate-order-fix-result.md`、修复报告、原独立 FAIL，以及原 brief 的权威规格/逐项要求/复现条件。实现方报告只作待验证声明。
- 本轮所有脚本、日志、原始 XML、截图及 SHA：`/tmp/m3-task9-corrected-spec-20261102/evidence/`，下文简称 E。

## 2. 发现与 F1 关闭证明

**当前阻塞发现：无。** 没有新增需要实现方修复的 severity/file/line 问题。

原 F1/P2 位置：`python/core/distributed/ops_queries.py:339-345`。当前第 343-345 行排序为 `(issued_at DESC, created_at DESC, receipt_id DESC)`；与 `python/core/distributed/promotion_repository.py:878-952` 中发布 `_bound_gate_receipts` 的三键顺序一致。不是通过只取 passed 掩盖失败。

本轮真实 PG 最小复现：

1. 创建独占数据库并运行真实 schema/migrations，创建同一 candidate artifact 精确 policy/protocol/runtime/source 绑定。
2. 插入旧 A：UUID `ffffffff-ffff-ffff-ffff-ffffffffffff`，`passed`，issued_at 为 `2026-11-01T00:00:00Z`，created_at 同时间。
3. 插入新 B：UUID `00000000-0000-0000-0000-000000000001`，先 `failed`、另一个独占库为 `unknown`；issued_at 与 A 完全相同，created_at 晚 60 秒。UUID 与追加时间反序，不能误用 UUID 把 A 排在 B 前。
4. 调用真实发布 `_bound_gate_receipts`：实际 `missing=['formal_holdout']`、accepted 空，与预期一致。
5. 调用真实 Ops HTTP detail：实际选 B，status 分别为 failed/unknown，与预期一致。
6. 使用本轮 Node20 构建的真实 production dist、真实 Ops HTTP、真实 PG，在 1440x900 与 390x844 两个 viewport 打开实际 Policies detail。唯一 formal_holdout 行分别显示红色 failed / 中性 unknown，旧绿色 passed 行不存在。

自有原始证据：`live-fixture-failed.json`、`live-fixture-unknown.json`、`live-server-*.log`、`live-failed.xml/log`、`live-unknown.xml/log`、`gate-detail-{failed,unknown}-{desktop,mobile}.png` 和 `live-{failed,unknown}-{desktop,mobile}.png`。截图已实际视觉检查，细节截图用于避免长全页图缩放影响辨认。

补充真实 PG 独立新攻击：`test_fresh_attacks.py:50-92` 覆盖 failed/unknown 的不同 created_at+反序 UUID、issued_at/created_at 同时相同的第三键、后来精确 pass 恢复、四个绑定维度各自错误的较新 pass、future-issued pass。F1 拒绝和 later-pass 恢复均与 authority 对照；future-issued 是 Ops 当前事实过滤检查，不把私有 helper 当成完整时间/资格 verifier。

原 F1 的归档 FAIL 保留不变，未改写旧结论为 PASS。当前 PASS 是新的独立执行结论。

## 3. Task9 六步逐规格结论

| Plan 步骤 | 本轮事实与证据 | 结论 |
|---|---|---|
| Step1 failing bounded/read-only API tests | 全读冻结 Task9 API tests；独立重跑当前 Task9 77 项、既有 Ops 19 项，另复用原独立 8 项有效探测，再新写并运行 23 项攻击。四 GET、auth、405、严格参数/模型、分页、脱敏、SQL read-only 和 gate tie 都有当前执行证据。 | PASS |
| Step2 API RED | 独立解析原 Task9 19 个 XML 与修复/归档 18 个 XML；原有效 fixture RED 75 tests / 56 failures / 0 errors，不能把另一个坏 fixture 的 56 errors 当预期 404。修复 valid RED 9 / 4 failures / 0 errors，GREEN 9 / 0。独立核验 13 组归档 before/after 相等，valid RED 到 GREEN 仅 OpsQueries source 改变，测试与当前冻结 bytes 相同。没有重跑历史 RED。 | PASS，历史证据核验 |
| Step3 redacted projections + Run/Trace | 完整核对 contracts/routes/queries；本轮独立执行四维精确 gate、三键排序、未来过滤、typed numbers/closed labels、100 上限、READ ONLY/REPEATABLE READ、旧 Run 真实 rollback、legacy NULL。F1 当前通过。 | PASS |
| Step4 Policies view | 实际桌面/移动 UI 与真实 production 页面核对导航、状态 icon/tooltip、environment/state filters、current/traffic/hash/cohort、gate、candidate/stable health、rollback/freeze timeline、无 mutation 控件和无 nested cards。 | PASS |
| Step5 backend/frontend verification | 新 API 127 次测试执行、mocked desktop/mobile UI 40 次、真实 PG production browser 12 次，全部 0 failure/error/skip；Node20.19.5 实际 tsc+Vite production build PASS。XML/count/SHA 自行计算。 | PASS |
| Step6 commit evidence surface | 独立核验当前 HEAD/parent、351 source、working-file 对 HEAD Git blob、169 changed paths，以及原/修复/独立 FAIL retained evidence。提交已有交付事实成立；reviewer 没有创建新提交或推送。 | PASS，提交/留档核验 |

## 4. 八项要求与 Design 不变量

| 要求 | 源码位置与自有行为证据 | 结论 |
|---|---|---|
| 1. 精确四 GET、auth、read-only | `ops_routes.py:35-73,280-332`，新列表/detail/health/audit；复用 router `require_ops_access`，四路径 POST/PUT/PATCH/DELETE 返回 405，bearer/loopback 401/403 检查通过。`ops_queries.py:280-285` 实际 `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`；冻结测试及独立 concurrent-append 探测查询 SHOW、尝试 INSERT 被 PG read-only 拒绝，且 query 不调用 CommandService。 | PASS |
| 2. keyset、上限、filters、拒绝不回显 | `ops_queries.py:217-229,252-263,287-428` typed cursor；`ops_routes.py:280-300` 闭合参数。3 endpoints 同时间 109 行实际两页 `[100,9]`，无重无漏、UUID/hash 降序；detail audit 实际 100，latest window 为最大同时间 hash。冻结与新探测覆盖空/重复/未知参数、类型混淆、时区溢出、非法 UUID/cursor、limit 1..100、无匹配空页及无 detail 404，拒绝不回显输入/SQL/private payload。 | PASS |
| 3. 公开字段、bounded、精确 gate | `ops_contracts.py:170-287` 与 `ops_queries.py:328-379,432-479`。`items[].stable_policy_hash/candidate_policy_hash` 是 12 位 list hash；detail 两 hash 全 64 位；current deployment/version、state、traffic_basis_points、cohort_counts、thresholds/hash、required_receipts、latest_health_window、audit_events 均 typed。gates 最多 8、window 最多 1、audit 最多 100。四维 exact binding 不显示错配 pass；F1 三键顺序和实际页面独立通过。 | PASS |
| 4. strict、隐私、数值/labels 攻击 | `OpsContract` extra forbid/frozen；actor/reason/issuer 为 Literal redacted；自由 details/components 不出响应。`ops_queries.py:232-249,468-519` 验证单个数字、闭合 threshold/event/transition 与 typed rollback 关联。独立 arbitrary 无敏感关键词 payload、HTML/Unicode、bool/object/list、NaN/Infinity、伪数值、超范围率、自由 labels 攻击均不回显，非法指标为 null，合法科学计数保留。Decimal 以受验证数字字符串序列化，不宣称全部 JSON number。没有 raw token/nonce/learner/request/private namespace/prompt/output/自由 details 新增公开路径。 | PASS |
| 5. immutable Run/Trace、legacy NULL | `ops_queries.py:204-215` 从 Run 保存的 deployment/full effective hash/cohort/state_namespace 投影，namespace 仅分类 production/rehearsal/NULL，不用当前 head 补历史身份。冻结 API 真正 head advance+health rollback 测试通过；自有 live harness 创建旧 candidate 与回滚后新 stable，真实 Runs table、drawer、Trace、Policies links 在两 viewport 断言并视觉检查。旧 hash/deployment 不漂移，新 stable 为另一 hash/deployment；legacy NULL 在当前 API/UI 仍不可用。 | PASS |
| 6. 实际导航、内容、窄屏、只读 | `OpsApp.tsx:98,133`、`PoliciesView.tsx:26-61,99-158,177-242`，沿用 Ant Design Table/Tag/Tooltip/Timeline/Descriptions 与既有 lucide ShieldCheck/status icon。actual UI 可达、状态 tooltip、流量/current relation、gate、candidate/stable metrics、rollback/failed deployment/window/transition 显示。actor/reason 原文全 redacted 有说明，公开事件/阈值/版本时间仍可审计。mobile 表格横向滚动、hash wrap，body 无额外横向溢出。实际 production 捕获所有 Ops 请求都是 GET；没有状态写按钮/嵌套 card。 | PASS |
| 7. 状态、分页、stale、build/browser | `PoliciesView.tsx:75-95,138-155,165-181` cleanup abort+disposed guard；`api.ts:540-572` GET+AbortController 与严格 guard。独立 40 browser executions 覆盖 loading/empty/error/auth/retry、filter/reset/pages、慢列表不能恢复旧结果、慢旧 detail 不覆盖新版本、legacy NULL、typed extra/freeform guards。production 实际 build；live 真实页面另外验证 `[50,7]` 部署分页、filters、health、audit、链接和无 mutation。 | PASS |
| 8. 冻结 provenance、raw、角色 | 本轮 `provenance.py`、`archive-check.py`、`finalize.py` 独立计算 Git/source/retained/XML/计数与 SHA，原 failures/坏 attempt 保留而不重命名成功。实现方 1684/96/40/8 只作 raw 归档核验，不算本轮重跑；本轮 6 个新 XML 明确见下表。fixture 均 synthetic/test evidence，live fixture 明示 release_eligible=false，不授予正式模型或学生效果资格。 | PASS |

范围说明：这里的错误不回显要求针对新增 policy endpoints；没有把既有 `/ops/runs` 等端点的所有历史 error 文案宣称为本轮重构或全面隐私审计。Run/Trace 相关检查针对 Task9 新增身份及既有 safe projection 的关联，不把此次 SPEC 当成全系统安全审计。

## 5. 本轮新执行、命令与原始 SHA

环境：Python 使用 primary `.venv/bin/python` 只读；`PYTHONPATH=m3/python`、TZ=UTC，pytest cache/pycache 自有 tmp。PG16 55432 独占 DB、EXIT dropdb；Redis56379/0 的 targeted fixtures 未实际使用 broker，未删共享键。Node20.19.5，Vite7.3.7；Playwright Chromium 桌面与窄屏 viewport，不是真实移动设备。browser skill 在首次 browser 自动化前已完整读取。

| 自有 XML | Tests | Failure/Error/Skip | SHA256 |
|---|---:|---|---|
| all-api.xml | 104 | 0/0/0 | `7a84e06e589a757189ff44b1e0aa70039990dd1d3da916f15c3b065229ea7c34` |
| fresh-attacks.xml | 23 | 0/0/0 | `986b6f7faacd5fd57c0e71edde12e14d41ad53251c486dfa04acc67f1a99d21e` |
| ui-40.xml | 40 | 0/0/0 | `54933b2920c6dc88c2a83de605a9b1a0db62eddb72b040c5168f21c93c31af9a` |
| live-failed.xml | 8 | 0/0/0 | `2f6610c110845f8f67940f31d0af3ab44db1fdc75dc7e0215e070a68df262bb5` |
| live-unknown.xml | 2 | 0/0/0 | `f5d302f1ac3f9d3a4c57fb8b3730a3c18b5c8604e5159254f443c7f5e2f09373` |
| live-run-detail-unknown.xml | 2 | 0/0/0 | `8c09241b9faf2b7adee3d783eb4bd2f0cb8c57ec8d842d60ba7d6ef314c4e8bc` |

合计 **179 次测试执行**，不是 179 个独立不同测试：API 127 = 冻结 Task9 77 + 既有 Ops 19 + 复用原独立有效探测 8 + 本轮新写攻击 23。browser 52 = route-mocked UI 40 + 真实 production/PG 12。额外 2 次 unknown Run detail 是补拍可读抽屉图的重复执行，不伪装成新功能覆盖。

本轮新写攻击 23：F1+later-pass recovery 4、exact binding 4、future-issued 1、数值/closed labels 11、3 endpoints cursor/filter 攻击 3。每个参数化 case 内可有多次请求，不把测试数当 HTTP 请求数。

`build.log` 实际 Node v20.19.5、`tsc && vite build` PASS。有单个通用 chunk >500KB warning，不是构建失败或本轮发现的阻塞规格项。日志 SHA：`d84897b2d0cba984aadd522cadce07dbe7673104eb9e83aa9a3cb34f37545fc7`。

完整复现调用及 runner 内部环境写于 E/commands.md；它是根据实际 runner/XML/log 还原的等价命令，不声称额外执行。核心调用：

```bash
E=/tmp/m3-task9-corrected-spec-20261102/evidence
bash "$E/pytest-runner.sh" all-api -c pyproject.toml -q -s \
  tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py \
  "$E/independent/test_independent.py" "$E/independent/test_gate_tie.py"
bash "$E/pytest-runner.sh" fresh-attacks -c pyproject.toml -q -s "$E/test_fresh_attacks.py"
bash "$E/node-runner.sh" build build
bash "$E/node-runner.sh" ui-40 test e2e/ops.spec.ts --reporter=line,junit \
  --output=/tmp/m3-task9-corrected-spec-20261102/playwright-ui
```

failed/unknown live runner 与 browser 分终端执行，startup 后 browser、TERM 并等 EXIT 后换库，具体命令保留 E/commands.md。未来复现需复制并调整全部 OWN/E/port/cache 路径，不能运行这些固定路径脚本覆盖本轮或 repo frozen evidence。

## 6. 构建与执行隔离

- 前端 tracked 文件复制到自有 tmp；29 个非执行 config 文件 byte-exact，2 个执行 config 仅改 own cacheDir/dev port。锁文件未降级。
- node_modules 是实体 copy，非 symlink；递归检查没有指向 OWN 外的 dependency symlink。实际 Node 输出记录 tmp realpath。
- 自有 dev 33290、live 33291；Vite cache/configbundle/.vite-temp/dist、Playwright outputs、npm cache 全部 own tmp，不写 M3 `.vite-temp`。
- `frontend-isolation.json` 记录 6 个 dist 文件 SHA，combined `dee1c3dbd3260679fa5c5caaf53e0f4f9cd3fde47fccbed80ee976fefa58060f`；package-lock SHA `90dbc9aae2e41ba3fe968254330755f3e183959a735a64132ad7f3c9b2b55bb5`。
- `production-http*.json` 在真实 HTTP 比较 Ops HTML 和全部 assets 与上述 dist bytes 完全相等，并记录 SHA/GET methods，不仅检查文件名。Live 不使用 route mocks；mock 40 UI 与 production 12 明确分列。
- live fixture 跑真实迁移、admission、健康窗口、transactional rollback 后查询真实 OpsQueries；为隔离审查通过 tmp Starlette mount 服务实际 dist/API，不宣称验证生产部署平台、反向代理或实际 worker/model execution。
- 新 live script v1 全页图过长但测试通过；仅修改 tmp 探测的截图/产物命名，补拍旧/新 drawer，原 v1 bytes 保存为 `fresh-live-v1.spec.ts`。未修改产品源/冻结测试/黄金证据。
- 本轮没有先 symlink 后纠正之类的新隔离例外；原 FAIL 中的历史例外原样保留，不认领为本轮行为。

## 7. 归档材料独立核验

`frozen-verification.json` 独立核验：

- 修复 E 的 165 文件 combined（不含该 E manifest）`f3dfc50551894f9c5f504cd98b04c1988a40eff2aab379c4b8ba1a88b9afb5fb`。
- 修复 E manifest SHA `9b843383cec0844e90f9ebec9931d056693e35564656b40d35ddb47725c338f0`。
- 169 changed paths，仅 2 个 Python source/test 路径，其余报告/evidence；修复 source diff 仅新增 created_at 排序键，新增回归测试保留。
- 37 个原始 XML（修复/其独立归档 18 + 原 Task9 19）的 suite/case 实数及 failure/error/skip SHA 已独立解析，不只读报告 summary。
- 实现方 full-backend 1684、API 96、browser 40、realPG failed6+unknown2 全部零失败，是**归档 raw 工程证据**。本轮没有重新执行 1684 全后端或这些历史命令。

`archive-provenance-check.json` 独立确认 13 组历史 before/after 状态相同；valid RED 到 GREEN source 仅 OpsQueries，测试 hash 与冻结相同：`398177df539bfe99febf42597d9bd9ce722349dc775c91eebbd59abbcef6243a`。

原独立 FAIL 报告 SHA：`b675d19d303dfedbe557f6ed20e37c9ab684e78afd1440c9ad9789be67fce55d`。旧 bad fixture、失败运行与原 SPEC FAIL 未覆盖。归档核验不等于本轮重跑，也不直接替代规格行为证明。

## 8. 终态与清理

`execution-summary.json` 保存本轮六 XML 计数/SHA、实际 HTTP/dist 校验以及结构化 cleanup commands/output。

- 所有自有 PG 库通过 EXIT dropdb 清理；只读 `pg_database` 查询 `m3_t9_cspec_%` 结果 0 行。
- 自有 33290/33291 listeners 为 0；failed/unknown server 已 TERM 并观察 EXIT 143。143 为有意停止服务，两个 finally/EXIT trap 完成 shutdown/dropdb/after snapshot，不是测试失败或遗漏进程。
- Redis 只读扫描本轮 own prefix 为 0；targeted 未使用 broker，无 FLUSH/DEL，不清不明共享键，也不以 prefix 扫描宣称整个共享 Redis 为空。
- 已删除 own frontend 实体依赖、dist、npm/pycache/pytest/Vite caches、Playwright 临时 outputs、PID；必要最后运行状态复制留 E，原始 XML/log/config/scripts/SHA/screenshots 保留待父侧归档。
- M3/primary git status 均 clean。351 source、retained evidence 对 HEAD Git blob 相同；primary HEAD/source/status、两 Git index 与主 `.venv`/site-packages、M3 `.vite-temp` 等受保护 mtime 在 **10 组本轮 before/after（含全审查首尾）** 完全相同。
- 未启动 CODE/Task10，未模型请求、未打印环境凭据、未修改主 `.venv`、未 commit/push。

本轮 E manifest：94 retained files + manifest；combined（不含 manifest）`8bcc90f85f0f45394ce88d0db813529083b43cd7af87df849077fd366dc757a0`。

本轮 E manifest SHA：`4e223f8308fb77c8578b662edb07bf7919554541a84bafc4fa21b373de54b838`。计算约定为 sorted relative-path→SHA256 mapping 的 compact ASCII JSON SHA256；XML、scripts、logs、截图与快照的逐文件 SHA 全列于 manifest。

## 9. 限制与父侧交接

本轮没有历史 RED/完整 1684 后端重跑、真实模型费用/质量评测、正式 holdout 资格审核、真实学生效果、真实移动设备、生产平台部署、跨 worker 压测或 Task10 演练。本轮证据是独立规格行为与冻结 provenance，不将 developmental fixtures 包装为正式模型资格。发布 gate 的全部健康/资格语义没有重写，Ops 仍只展示事实，不变成新的授权器。

**Fresh 全 Task9 SPEC PASS；F1/P2 已关闭；无当前阻塞规格发现。** 完整结果先写此文件，原始证据保留 E。由父侧验证/归档并决定启动 fresh CODE，不能跳到 Task10 或称最终验收完成。
