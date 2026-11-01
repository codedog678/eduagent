# Task9 Fresh Independent CODE Review

结论：**CODE FAIL。发现 1 个 P2 阻断验收问题 C1：健康 gate 回执跨 deployment 串用，当前与历史详情的绿色 passed 证据关联不准确。** 旧排序 F1 已修复，本轮 C1 是独立的新问题，不是旧 F1 重开。完整 Task9 已审，不仅最新 docs commit 或排序 diff。Task10 未启动，Task9 不应据此验收。

本报告先完整落盘，再通知父侧。没有修改 source/tests/index，没有 commit/push/真实模型请求；primary 只读。所有本轮新探测、日志、XML、截图、构建和缓存都在自有 `/tmp`。

## 1. 身份、范围与证据

- 唯一产品工作树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 冻结 HEAD：`365a11542843ebcc7ecfce13e91a76e44c43d816`。
- 被审产品 revision：`e29bdb4d0c1b0e07b0e60a62ee61df3ae2e9915e`。
- 全范围 base：`8869166878a193a1c453376471cbe52c8fa84b3f`，包含初实现 `38f48d7` 与排序修复 `e29bdb4`。
- 351 tracked Python/frontend 文件与 HEAD Git blob 一致；权威 sorted path/hash combined SHA：`8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582`。
- Primary HEAD 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`；两侧 clean。
- 本轮证据根目录 E：`/tmp/m3-task9-code-20261102-5TNycP`。
- 完整读取 `/tmp/m3-task9-code-review-brief.md`、Task9 plan 六步、相关 design、SPEC 全文；完整审查 base→HEAD 的 13 个 Python/frontend changed paths，包括 routes/contracts/queries、全部新 UI/types/validators、Run/Trace、CSS、冻结 API/e2e tests，沿调用关系核查发布 authority、health evaluator、数据库模型和运行身份。
- SPEC PASS 只作为归档事实，未作为 CODE PASS 前提。没有运行会覆盖旧 golden 或绑定旧固定 parent 的 collector。

## 2. C1 / P2：健康回执未绑定被展示的 Deployment

**主要位置：`python/core/distributed/ops_queries.py:339-360`。**

相关位置：`ops_queries.py:372-376`；`ops_contracts.py:206-215`；`frontend/src/ops/PoliciesView.tsx:204-216`。

原因：查询先按 artifact 的 policy/protocol/runtime/source 四维过滤，再仅按 gate_type 分组选择 `(issued_at, created_at, receipt_id)` 三键最新值。对于 deployment-scoped 的 `shadow_health` / `canary_health`，没有区分回执 details 中的 deployment/version/thresholds/window 关联。公开 DTO 又没有这些 typed source relations，UI 在所选部署详情里直接展示绿色 passed，不能辨别它属于另一部署。

发布 authority `promotion_repository.py:897-946` 明确按健康 deployment、version、thresholds、有效最新窗口核查，生产 health evaluator `policy_health.py:449-464` 签发的健康回执也包含这些关联。本轮真实 `_bound_gate_receipts` 对当前部署返回 missing，而 Ops 展示另一部署的 passed。

这不是要求 Ops 成为新的授权器，也不是把 `hold` 强制改为 `failed`。问题是 **deployment-local 证据被显示在错误 deployment 下，且没有历史/外来来源标识**。四维相等只证明 artifact 相同，不证明健康回执适用于该 deployment。

### 最小有效复现

1. 独占 PG 库运行真实 migrations，保留 append-only/immutable triggers。
2. 创建 synthetic canary 部署 A/v2，对真实 health evaluator 提供 20 candidate + 20 stable 工程观察；得到 pass 窗口和健康回执 RA，RA.details.deployment_id=A。
3. **追加** B/v3，复用完全相同的 immutable artifact 和 thresholds，推进 rehearsal head 到 B。没有更新已有 deployment，没有禁用 trigger，也没有重新 mint 不同 artifact。
4. B 没有健康样本，真实 evaluator 得到 hold 窗口；B 没有自己的 canary_health 回执。
5. Authority 对 B 返回 `missing=['canary_health'], accepted={}`。
6. `GET /ops/policies/deployments/B` 实际返回 `is_current=true`、B 的 hold 窗口，却在 gate_receipts 返回 A 的 RA/passed。
7. 真实 production dist + 真实 HTTP + 真实 PG，在 1440x900 和 390x844 页面均显示上述绿色 passed 与 B/hold，没有外来回执关联说明。

第二个有效场景：A、B 各自产生真实 pass 回执后，查看历史 A，实际返回较新的 RB，而非 A 的 RA。相同 artifact 下历史详情的健康证据被后续部署替换。

预期：健康 gate 依据其有效 deployment/chain 关联选择；无匹配回执保持不可用/unknown。若保留 artifact 全局历史回执，必须公开闭合 typed source relation 并明确标记历史/不适用，不能在当前部署详情中冒充其最新绑定健康证据。资格类 artifact gates 保持原四维过滤与三键排序。

有效探测：`E/test_code_attacks.py:21-85`。原始 `attacks-v3.xml` 为 **21 tests / 2 failures / 0 errors / 0 skip**，两项 failure 都是上述产品行为断言。`health-cross-current.json`、`health-cross-history.json` 保存实际关联。

真实页面：`live-fixture.json`、`production-{desktop,mobile}.json`；`live-v2.xml` 为 **4 tests / 2 failures / 0 errors / 0 skip**。其中两项通过的是资产字节/实际缺陷观察/GET-only/布局检查，另两项明确按正确行为断言无外来 passed，实际均失败，不能把 observation PASS 算作产品正确性 PASS。

截图已实际视觉读取：`screenshots/live2-cross-binding-mobile.png`、`screenshots/live-correctness-desktop.png`；另读 `screenshots/policies-desktop.png` 核查正常 mocked UI 的状态、metrics、rollback/freeze timeline。完整 production 桌面/移动图与 detail 图均保留。

## 3. 逐项 CODE 判定

| 边界 | 判定 | 独立事实与定位 |
|---|---|---|
| Ops auth、严格输入、错误不回显、只读 methods | PASS，限 Task9 新路径 | 复用 router auth；闭合 query、重复/空/未知/溢出 limit、异常日期/UUID/cursor 拒绝；新路径错误为固定文案。冻结测试在本轮 full 运行，新增三个端点参数攻击通过。`ops_routes.py:35-73,280-332`。 |
| SQL read-only、无业务写、快照一致性 | PASS | `ops_queries.py:280-285`；冻结 SQL observer/command 禁用测试通过；本轮独立 concurrent append 证明 REPEATABLE READ 隐藏追加、fresh session 可见，DELETE 被 PG read-only 拒绝。 |
| Typed keyset、100 上限、过滤器与 reset | PASS | 本轮独立三个列表各 113 同时间 rows，页数 `[100,13]`、typed UUID/hash 逆序、无重复遗漏；detail audit=100/latest window 确定；非法跨 UUID/hash cursor 拒绝。Frontend environment/state/tab reset 与 abort/disposed 行为 40 UI 覆盖通过。 |
| DTO/privacy/numbers/closed audit fields | PASS，已测边界 | 固定 fields、extra forbid/frozen、actor/reason/issuer redacted；自由 JSON 不直接投影，非法 bool/object/list/NaN/Infinity/负值/SQL/HTML/Unicode 数值为 null，合法小数与缺值保持区分；audit 状态与 rollback 关联 typed。`ops_contracts.py:170-287`、`ops_queries.py:232-249,468-519`。不声称任意损坏 DB shape 均完整 fuzz 过。 |
| Artifact gate 四维与三键顺序 | PASS | `ops_queries.py:339-356` 与 authority 三键相同。完整本轮冻结测试包括新 failed/unknown、created_at/UUID 反序、later pass 恢复、四维错配与未来 issued 过滤；旧 F1 不再复现。未来过滤与 authority helper 的完整资格语义未混用。 |
| 健康 gate deployment/window 关联与历史展示 | **FAIL / C1 P2** | 四维过滤没有健康 scoped binding；有效真实 PG 两场景与真实 production 双 viewport 确认。 |
| immutable Run summary/detail/Trace、legacy NULL | PASS | `ops_queries.py:204-215,644,961` 从 Run 保存字段投影，不借当前 head 补身份。冻结真实 head advance/rollback、NULL、cohort count、policy pinning/worker/expert 全矩阵通过；40 UI 检查 Run/Trace links、旧绑定、legacy unavailable。未以当前 namespace raw 值替代 typed relation。 |
| async stale/auth/loading/error/UI compatibility | PASS，C1 展示语义除外 | `PoliciesView.tsx:75-95,165-181` abort + disposed；detail ID guard、稳定 auth callback、lock unmount；Run/Trace 新 strict keys 与后端响应一致；40 mocked desktop/mobile 回归通过。没有以一次截图代替 stale/error/auth 测试。 |
| 页面导航、状态、指标、timeline、移动只读 | PASS，C1 除外 | 实际 40 UI 导航、shield/status tooltip、candidate/stable、current/history、rollback/freeze、无 mutation 控件。真实 production 双 viewport 实际请求全 GET、资产 bytes 相同、body overflow=0，mobile table 横滚有效。健康回执绿色关联语义 FAIL。 |
| 全 backend 影响矩阵与 frozen provenance | PASS | 自己重跑完整 1684、78 模块；两侧 source/index/primary venv 及原 evidence 字节保持。43 个历史 XML 自行解析但不认领重跑。 |

Task9 六步：Step1 测试范围/契约核查 PASS；Step2 历史有效 RED/GREEN raw 核验 PASS（本轮未重跑历史 RED）；Step3 redacted projections **FAIL/C1**；Step4 Policies evidence semantics **FAIL/C1**；Step5 常规工程矩阵/build/UI PASS，但新增正确性探测 **FAIL/C1**，不能作为验收 PASS；Step6 冻结提交与留档事实核验 PASS，reviewer 未创建提交。

## 4. 独立矩阵、计数与 Hash

有效最终执行合计 **1753 次测试执行，1749 passed / 4 failures / 0 errors / 0 skip**；不是 1753 独立 case，也不是 API HTTP 请求数。4 failures 为 C1 的两 backend 与两 browser 正确性断言。常规完整 backend 的 1684 包括 Task9 77 + 原 Ops 19，不重复加到总数。

| 本轮 XML | Tests | Fail/Error/Skip | SHA256 |
|---|---:|---|---|
| full-v2.xml | 1684 | 0/0/0 | `6e86bdbebc80b97a7eeaa295bbc077681f59fb637968e62f2dbd692600a0a16d` |
| attacks-v3.xml | 21 | 2/0/0 | `b8e2180eea5eb5b44adae33b49e559339f4ce7a37c3e0440793ddd12df54619c` |
| extra.xml | 4 | 0/0/0 | `244a44017b11d465271a672f6e11e710f86321bb84fd716d4225a9dc93d23cb0` |
| ui-v2.xml | 40 | 0/0/0 | `bc4574ac987779b3f7d52fc166c9db0effc423e39a441690027d046f3bf43f9d` |
| live-v2.xml | 4 | 2/0/0 | `bdcde41cf0e3311606a643c2844ca8dbdc2e47910072075cc1f2ce34a8265c90` |

完整 backend 影响矩阵：

| 分组 | 执行 | 结果 |
|---|---:|---|
| distributed：API/strict models、admission、assignment/pinning、repository/replay、worker/expert、promotion/health/shadow、runtime/migrations/telemetry | 1126 | 全 PASS |
| evals/optimization/qualification/证据工具 | 192 | 全 PASS |
| integration 跨进程 failover | 5 | 全 PASS |
| 其余原 backend/harness/model concurrency/agent/API/v2 | 361 | 全 PASS |
| 合计 78 test modules | 1684 | 0fail/error/skip |

`E/backend-impact-matrix.json` 按 XML 每个 classname 保存全部 78 模块计数，`E/verification.json` 保存 suite/case 实数对照、各 XML SHA、archive raw 核验和 frontend isolation。唯一 warning 是已有 pytest TestAgent collection warning，不是 skip。

Node **v20.19.5** 实际 `tsc && vite build` PASS，Vite v7.3.7；通用 >500KB chunk warning 保留。`build.log` SHA：`7e2443e2a90a6d94a8d04f56365b33a5973f821b12af201715e5001bc256af6a`。

Lock SHA：`90dbc9aae2e41ba3fe968254330755f3e183959a735a64132ad7f3c9b2b55bb5`。两 production HTTP assets 检查均与本轮 dist byte-exact，逐资源 SHA 在 `production-*.json` 和 `verification.json`；不是只核对文件名。

## 5. 实际调用与未成功尝试

每个 pytest 调用 cwd 均为 `/Users/bytedance/Documents/trae_projects/eduagent-m3/python`。runner 内容完整保留，使用 primary `.venv/bin/python`、`PYTHONPATH=m3/python:E`、TZ=UTC、own TMPDIR/cache/pycache/basetemp，自动创建 invocation-unique PG DB 并 EXIT dropdb。没有使用生产 DATABASE_URL。

实际命令（下列是记录，不表示现在又执行一次）：

```bash
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh full -c pyproject.toml -q
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh full-v2 -c pyproject.toml -q
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh attacks -c pyproject.toml -q /tmp/m3-task9-code-20261102-5TNycP/test_code_attacks.py
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh attacks-v2 -c pyproject.toml -q /tmp/m3-task9-code-20261102-5TNycP/test_code_attacks.py
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh attacks-v3 -c pyproject.toml -q /tmp/m3-task9-code-20261102-5TNycP/test_code_attacks.py
bash /tmp/m3-task9-code-20261102-5TNycP/pytest.sh extra -c pyproject.toml -q /tmp/m3-task9-code-20261102-5TNycP/test_extra_code.py
bash /tmp/m3-task9-code-20261102-5TNycP/prepare-frontend.sh
bash /tmp/m3-task9-code-20261102-5TNycP/node.sh build build
bash /tmp/m3-task9-code-20261102-5TNycP/node.sh ui test e2e/ops.spec.ts --reporter=line,junit --output=/tmp/m3-task9-code-20261102-5TNycP/ui-output
bash /tmp/m3-task9-code-20261102-5TNycP/node.sh ui-v2 test e2e/ops.spec.ts --reporter=line,junit --output=/tmp/m3-task9-code-20261102-5TNycP/ui-v2-output
bash /tmp/m3-task9-code-20261102-5TNycP/live.sh
bash /tmp/m3-task9-code-20261102-5TNycP/node.sh live test --config=playwright.live.config.ts --reporter=line,junit --output=/tmp/m3-task9-code-20261102-5TNycP/live-output
bash /tmp/m3-task9-code-20261102-5TNycP/node.sh live-v2 test --config=playwright.live.config.ts --reporter=line,junit --output=/tmp/m3-task9-code-20261102-5TNycP/live-v2-output
```

Node commands 的 cwd 是 `E/frontend`；live runner cwd 是 E。node.sh 读取现成 Node20 interpreter，npm/Vite/temp cache 在 own tmp。执行 configs 只改 own dev port=33490/cache/strictPort、Playwright baseURL，live=33491；原 source/e2e/lock 均实体复制且不改 bytes。browser skill 在任何自动化前完整读取。

有效 C1 最小重跑调用只需 `pytest.sh` 指定 `test_code_attacks.py::test_current_health_gate_must_not_borrow_previous_deployment_pass` 或 `::test_historical_health_gate_must_not_be_replaced_by_new_deployment`；下一 reviewer 应复制到自己的 tmp 并调整路径，不覆盖本轮证据。

原始不成功 attempts 全保留：

| 原始 attempt | 计数 | 原因，不能算产品 failure |
|---|---|---|
| full.xml | 1684 / 18fail / 4error / 0skip | 我写的 Redis guard v1 只允许最短 UUID stream 名，误拒绝 fixtures 的 process/schema/rehearsal/control 名；1662 项通过。v2 拓宽到已核查的 test UUID 派生名后完整 1684 PASS。 |
| attacks.xml | 21 / 2fail | fixture 尝试 UPDATE immutable deployment required_receipts，被真实 append-only trigger 拒绝。 |
| attacks-v2.xml | 21 / 1fail | fixture 调用了会按 created_at mint 新 artifact 的 helper，未形成同 artifact 对照，历史探测缺新回执。其 current 探测 PASS 不认领为缺陷关闭。 |
| ui.xml | 40 / 2fail | 冷 Vite dependency 启动首个 Runs 工作流 heading 等待超时，之后 38 项通过；暖启动同冻结 40 项全通过。未改 frozen test。 |
| live.xml | 4 / 2fail | 我用 `^passed$` selector 漏掉 Tag 文本前空格；2 个 observation 失败，2 个空集合正确性断言假通过，全部无效。保留 v1 script，修为 whitespace-aware selector 后 live-v2 明确正确性 FAIL。 |

`safety-v1.py`、`test_code_attacks-v1.py`、`test_code_attacks-v2.py`、`health-binding-v1.spec.ts` 与相应 XML/log/trace 保留，不把坏 fixture/selector 当产品证明。C1 只依据 valid attacks-v3 与 live-v2。

当前有效 probe SHA：`test_code_attacks.py` = `c0a25ca7ca514af672c5cdae2e621a88033baa74ba19c1bbf6a70f9f46986949`；extra = `264d971ec65939445f3cc218a63d17aaa38835a4c4ec3b86f67d9156803e435d`。

## 6. 归档核验与角色区分

- 自行读取 SPEC 完整 report，逐文件核验其 94 retained 映射、manifest 原 bytes、原始 XML，不以报告结论代替 CODE。
- SPEC94 combined：`8bcc90f85f0f45394ce88d0db813529083b43cd7af87df849077fd366dc757a0`；SPEC manifest SHA：`4e223f8308fb77c8578b662edb07bf7919554541a84bafc4fa21b373de54b838`。
- Repo SPEC report SHA：`d8d7ddd93edd2041a5e88aa89d875d295c7a6ab85d0233c6c62cd895128e01b1`。
- 原初实现/排序修复/其独立归档/SPEC 的 **43 XML** 均自行解析 suite 与 testcase counts、failure/error/skip、逐文件 SHA。历史 RED、旧 FAIL、坏 attempts 均原样保留。
- 父侧另报 patched-runtime 1684 PASS 为其独立旁证；我未将其执行或 manifest 验证认领为本轮执行。这里 full-v2 是自己使用指定只读主 `.venv` 的实际重跑。
- 真实 PG fixtures 为 synthetic 工程证据，`release_eligible=false`；不授予正式 holdout/模型质量/学生效果资格。live harness 运行真实 migrations/health evaluator/Ops API/production assets，不等同生产平台部署或真正模型 worker execution。

## 7. 终态、清理与限制

`E/cleanup.json` 与 7 组 before/after、`full-before.json`→`review-final.json` 首尾一致确认：

- 全部 own invocation DB 由 EXIT dropdb；只读查询 `pg_database WHERE datname LIKE 'm3_t9_code_%'` 返回 0 行。
- 33490/33491 listener=0。live Python 已 TERM 并确认外层 runner EXIT=143、shutdown/dispose/dropdb 完成；143 是主动停止服务，不是漏清理。
- Redis 只枚举本轮日志中的 exact UUID streams，以及 v1 被打断 fixture 的同 UUID、源码明确的 siblings；共 495 own names，实际残存 22 个已删，remaining=0。没有 FLUSH，没有删除父侧或共享未知 key，也没有用全库扫描结果作清空声明。
- 已删 own physical node_modules、dist、Vite/npm/pytest/pycache/TMPDIR/PID；原始 XML/log/scripts/configs/screenshots/失败 traces 和 verification/manifest 保留待父侧归档。
- M3 与 primary tracked files、source hashes、HEAD、Git blob、两 index hash/mtime 完全一致；主 `.venv` 10023 个目录/文件 metadata digest 保持 `bd8ab3a3cd903dd8885089b03024186593305238ef3d50b54d17729eb39f1239`；M3 `.vite`/`.vite-temp` metadata 未变。主 `.venv` 没有安装/写缓存。
- 没有 source/tests/index 编辑、commit/push、模型请求、Task10；没有 dump env/credentials/SQL/private real payload。
- 未执行：历史 RED 重跑、真实模型费用/质量评测、正式资格/学生效果、真实移动设备、生产反向代理/部署平台、Task10。全部 browser 是 Chromium desktop/mobile viewport；本轮未独立再建真实 Run drawer/Trace production fixture，相关边界由自己完整 backend 与 40 mocked UI 验证，不把归档截图当新执行。

E manifest 有 **148 retained files + manifest**（最终报告另在本文件，不包含在 E manifest，避免循环 hash）。Combined SHA（sorted relative-path→SHA 的 compact ASCII sorted pairs JSON）：`14cc0b77076f7608968762b7ea28769516f0103dae455c3293ea16fbacc6d016`。

Manifest SHA：`8713e23393c6c5e0650c31204cc2053757da2c97484374a3d42f85d94fe4541f`。

**Fresh full Task9 CODE FAIL / C1 P2。** 父侧应核验此报告与 raw、交回新的实现者修复健康 evidence scoped binding，再按授权顺序 freeze→fresh SPEC→PASS 后 fresh CODE。只有新的 CODE PASS 后才能验收 Task9 并启动 Task10；本 reviewer 不自行认领验收或启动后续任务。
