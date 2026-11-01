# WHOLE Task9 Independent SPEC Review

**状态：FAIL。3 项 P2 规格阻断问题。Task9 未验收，不得启动 CODE 或 Task10。**

本报告是本轮 fresh、独立、全 Task9 SPEC 审查，不是实现者报告、父侧 provenance 核验或 CODE 审查。范围从 Task8 acceptance 到最终 freeze，覆盖初实现、F1 和 C1 的全部前后端影响。常规测试通过不能抵消下面的独立规格失败。

## 身份与范围

- 工作树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 分支：`feature/m3-trusted-policy-promotion`。
- Task8 acceptance：`8869166878a193a1c453376471cbe52c8fa84b3f`。
- freeze HEAD：`2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d`。
- freeze parent：`517c04f137ed93ebb042ec4ff027d120d3625847`。
- **全部 352 源文件 SHA-256：`78fb2d84827b0e9c32df1bebbee9d4840f5eff301100da0a9f5489a0146b4357`**。
- 唯一自有 raw 目录：`/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93`，以下 `E/` 指此目录。
- 自有最终留存 202 个文件的 payload SHA-256：`03c093f997344b8000e077d54bf76ca90df7af4841fed8085ab1cec7f02d5d4a`；逐文件哈希在 `E/retained-manifest.json`。
- 数量与源码身份采用 tracked `python/` + `frontend/` 全集，而非仅本次 diff；摘要算法是紧凑 ASCII JSON 的排序 `(相对路径, 文件 SHA-256)` 对。

完整读取交接、批准 plan 的 Task9 六步及相关 design、初实现 result、F1 修复和独立 SPEC 材料、原 C1 CODEFAIL、最新实现 result 与 implementation-report。独立阅读上述基线到 freeze 的 14 个 source/test 路径及其依赖；不是只看最新 commit。

14 个路径：`python/api/ops_routes.py`、`python/core/distributed/{ops_contracts,ops_queries}.py`、`python/tests/distributed/{test_ops_api,test_ops_health_binding,test_promotion_ops_api}.py`、`frontend/src/ops/{OpsApp,PoliciesView,RunsView,TraceView}.tsx`、`frontend/src/ops/{api,types}.ts`、`frontend/src/ops/ops.css`、`frontend/e2e/ops.spec.ts`。

## 问题

### S1 / P2：来源链仅比较声明相等，未完整验证实际 audit/approval 绑定

**位置：** `python/core/distributed/ops_queries.py:559-589`，尤其 `577-578`；通过后由 `395-434` 投影为前序已消费证据。

**最小有效复现：**

1. 使用真实 migrations、immutable triggers、资格准备和 evaluator，形成每 cohort 20 个观测的有效 Shadow → Canary 前序。
2. 在自有 UUID DB 中 append 一个 Active snapshot、对应 audit 和 `_create_promotion_approval` 产生的 approval。正向对照完整合法关系确实可以展示。
3. 仅将 audit 与 approval 的 `command_hash` 同时设为相同的错误值；不修改旧 deployment、不关闭 triggers、不换 artifact。
4. GET `/ops/policies/deployments/{active_id}`。

`E/test_spec_relations.py` 的 `matching_wrong_command_hash` 实际命令规范哈希为 `2d490df40aced48ef99a84ec7259126a432c0e46ec3481351ec17a296a07263b`，存储声明却是 64 个 `a`。Active 为 `25be33d5-15ba-411f-ad5c-5103e0eec45d`。

**Actual：** HTTP 200，`canary_health` 和 `shadow_health` 均 `status=passed`、`health_source.relation=consumed_chain`。

**Expected：** 错误命令身份不能证明消费关系；无有效来源时不投影绿色已消费健康证据，且不能从同 artifact/相邻 version 推断。

同一有效探测组还确认：audit 的 `required_receipts=[]`、audit actor 与部署 actor 不一致、较新 approval 的 issuer/model_identity/data_role 错误，均仍借到绿色 consumed chain。分别有独立 JSON，未据此声称发布 API 已被绕过。

**证据：** `E/relations-valid.xml` 中 6 个对应 assertion failure；`E/relation-{matching_wrong_command_hash,audit_missing_required,audit_wrong_actor,approval_wrong_issuer,approval_wrong_model,approval_wrong_role}.json`。有效正向 synthetic exact-chain 和真实命令完整链两个对照都 PASS。

**最小修复目标：** 验证实际命令身份及 audit/approval 的完整闭合关系，而非只验证两个自由声明相等；保留真实合法链与全部原边界测试。此处不给实现补丁。

### S2 / P2：较新 malformed approval 在选取前被过滤，旧 passed 被复活

**位置：** `python/core/distributed/ops_queries.py:541-549`，尤其先按 `details["command_id"]` 过滤的 `544`。

**最小有效复现：**

1. 由真实晋级命令形成完整 Shadow → Canary → Active 链，而非手工合成 Active。
2. 保持旧 approval/audit/deployment 不变，append 同 artifact、同 `issued_at`、较新 `created_at` 的 `promotion_approval`，仅 `details=[]` 并使用该 details 的真实 canonical evidence hash。
3. GET Active 详情并打开实际 production build 的 Policies 页面。

生产夹具 Active：`cc864aad-7574-4ba4-8f9d-8b57a0c9afad`；旧 approval：`67611768-09f0-4c21-bad9-26ef9453afe8`；新 malformed approval：`66091393-c592-4be8-a958-07fb1d70ec6b`。

**Actual：** 新行在 SQL 选取阶段消失，旧 approval 被采用；API 返回两项 passed consumed-chain，桌面和移动页面均显示绿色“已消费前序证据（非本部署新观测）”，且 promotion_approval 仍为 passed。

**Expected：** 无法确定绑定的 latest malformed evidence 必须 fail closed，不跳过它恢复旧绿色消费证明。合法旧记录可作为历史原始材料保留，但不能被标为已验证当前消费关系。

**证据：** `E/corroboration-final.xml` 的 genuine-command case assertion FAIL；`E/corroboration-final-genuine.json`；`E/live-fixture-genuine_malformed_latest_valid.json`；`E/production-genuine-malformed.xml` **2 assertion failures / 0 errors**；两个视口的 API/body/assets/network JSON、trace、截图。另一次 append-only 合成合法链生产验证 `production-approval-malformed.xml` 也为 **2 assertion failures**，不是“观察到缺陷即 PASS”。

实际查看了 `detail-genuine_malformed_latest_valid-{desktop,mobile}-left.png` 和 `detail-approval_malformed_latest-{desktop,mobile}-left.png`：绿色标签与错误前序来源确实呈现。正确性断言在保留画面及 HTTP 证据后失败，未将失败误记为成功。

**最小修复目标：** 先确定 latest evidence 的排序和保守遮蔽语义，再验证可识别绑定；不能在验证前丢弃 malformed latest。不得因此弱化 local failed/unknown 或 malformed latest 的原 fail-closed 行为。

### S3 / P2：收据计数、费用与冻结窗口不一致仍被认证为健康来源

**位置：** `python/core/distributed/ops_queries.py:486-529`；该校验未核对 `receipt.sample_count` 和 `receipt.cost`。最终 DTO 输出于 `381-389`。

**最小有效复现：**

1. 在自有 DB 用 evaluator 产生真实 pass window，candidate/stable 各 20 个观测，原 health receipt `sample_count=20`、`cost=0.40000000`。
2. append 较新同来源 receipt，保持 window/identity/stats 正确且 evidence hash 可复算，仅将 `sample_count=0` 或 `cost=0`。
3. 读取 Ops 详情；同时用现有发布权威 `_validated_health_window` 做前后对照。

**Actual：** Ops 返回同一冻结窗口的 `local`、`window_decision=pass`、`status=passed`，分别输出 `sample_count=0` 或 `cost=0E-8`。发布权威对原行返回有效 window，对新行返回 unavailable。

**Expected：** 不一致的最新收据不能获得已验证来源归属；不可把窗口 20 个样本和实际 0.4 的费用关联到另一份声称为 0 的绿色收据。发布权威对照只是证据验证，不把 Ops 当授权面。

权威已有明确规则：`promotion_repository.py:712` 校验 sample_count；`754-755` 校验观测费用总和。

**证据：** `E/corroboration-final-{sample_count,cost}.json`，`E/corroboration-final.xml` 两个实际 assertion failures；前一组 `E/summary-{sample_count,cost}.json` 与 `relations-valid.xml` 也独立失败。最新收据分别为 `44b3a2a3-f636-4ac5-a8db-e657c9e16fd6`、`af027de0-c68a-4d40-aced-0f1342174aa2`。

**最小修复目标：** 健康证据归属校验应覆盖冻结计数与费用的一致性，最新不一致行仍需遮蔽旧 pass，不能用 fallback 规避。

三项均为 P2：阻断已批准的来源可信/一致性规格，但本轮没有证明生产写入、发布权限绕过或真实学习者影响，因此不升级为 P0/P1。

## Task9 六步

| 批准步骤 | 独立结论与证据 |
| --- | --- |
| 1. 有界只读 API RED 测试 | PASS：四 GET 路由、严格参数、认证与只读 tripwire 均有测试；最终 full 内 `test_promotion_ops_api` 77 项和既有 Ops 19 项实际运行。 |
| 2. 验证 RED | PASS（历史证据）：初始 red-api 的 fixture errors 不当有效 RED；有效 red-api-valid-fixture 75 项中 56 assertion failures，以及 6 项有效 cursor RED 均解析留存。不能以测试解析代替本轮行为验证。 |
| 3. 脱敏投影与 immutable binding | FAIL：只读、有界、脱敏与 Run binding 常规行为通过，但新增健康来源闭合和 metadata 验证存在 S1-S3。 |
| 4. Policies 页面 | FAIL：布局、过滤、分页、状态、指标、历史/当前关系和错误恢复通过；页面信任错误来源 DTO，S2 的实际 production 双视口正确性失败。 |
| 5. 后端、前端与 build 验证 | FAIL（整体）：完整后端 1726 PASS、UI 54 PASS、build PASS，但新增独立规格探测和 production 正确性断言 FAIL。 |
| 6. 冻结 Ops evidence surface | PASS（provenance）：初实现/F1/C1 commits 与现有证据完整冻结，352 source + 232 最新 evidence Git blobs 均 byte-exact。不是 Task9 acceptance；本 reviewer 未提交。 |

## 交接规格逐项矩阵

| # | 核验范围 | 结论与独立证据 |
| --- | --- | --- |
| 1 | Ops auth、重复/空/未知 query、limit/UUID/cursor/date/overflow、固定公开错误、GET-only、只读事务 | PASS：full 中 API 参数、认证与 mutation 拒绝测试；`test_promotion_ops_api.py:145-182,329-397`；独立 attacks 对全部三个列表再次测 duplicate/empty/overflow/typed cursor；实际 `SHOW transaction_read_only=on`、`SHOW transaction_isolation=repeatable read`，并发 append 不进入旧 snapshot，DELETE 被 PG 拒绝。 |
| 2 | 三列表同时间 keyset、100 上限、无漏重、typed cursor、过滤/reset、有界详情/audit | PASS：独立 113 同时间记录按 100+13 完整分页，排序、唯一性、末页 cursor 均断言；audit detail 100 上限及 window 同时间 tiebreak 均验证，见 `E/test_extra_code.py` 与 `attacks.xml`。 |
| 3 | 固定 DTO、hash/UUID/Decimal/numeric poison、missing/unknown 不补零、闭合来源、无 raw details/actor/reason 泄漏 | FAIL（来源部分）：类型/脱敏通过 `test_promotion_ops_api.py:210,486,503`、独立 numeric poison 和 UI strict guard；来源闭合/一致性存在 S1-S3。 |
| 4 | 资格 gate 四维与三键排序、F1 failed/unknown 遮蔽、later pass 恢复、future issued/错绑定 | PASS：完整 full 明确解析到 F1 九项（4 个 tie/nonpass+恢复场景、5 个四维/future 场景），并非靠原 F1 报告；`test_promotion_ops_api.py:258-326`。没有重新打开已修复 F1。 |
| 5 | C1 同 artifact 两部署：B/hold 不借 RA；历史 A 不被 RB 替换；真实窗口/immutable triggers/20 cohort | PASS：full 的 2 项核心测试、独立原 valid attack 的 2 项重跑及真实 production current/history 双视口。`health-cross-current.json` 记录权威 missing；历史显示原 receipt/window。没有 UPDATE 旧 deployment 或新 mint artifact。 |
| 6 | local 健康来源部署/version/threshold/window/cohort、malformed/failed/unknown 不 fallback、旧 pass 对 latest hold 的语义 | FAIL（metadata）；现有 42 项回归内身份/malformed/local nonpass/旧窗口语义通过，`test_ops_health_binding.py:94-151,223-264`。另发现 S3，不能因此宣称整个健康证据安全规格通过。 |
| 7 | 真 audit/approval 消费链、typed source、local/前序明确、断链不借 pass、current/history/rollback/freeze | FAIL：合法真链、无 audit/错 receipt/邻接边界及 local nonpass 通过；`test_ops_health_binding.py:154-208,266-294`。新增 S1/S2 证明链校验仍不完整。rollback/freeze 无健康来源借用，并有真实 rollback Run 不变性测试。 |
| 8 | Run/Attempt/Expert/Trace immutable binding、legacy NULL、head advance/rollback、前后端新字段一致 | PASS：full 的 `test_promotion_ops_api.py:401-466` 与相关 expert/binding suites；UI stored/legacy 两类链路和 strict guards 实际运行，Trace 双视口截图实际查看。 |
| 9 | auth/loading/error/empty/stale abort/disposed/filter reset、shield/status/tooltip/metrics/timeline、mobile overflow、无写控件 | PASS（基础交互）；54 UI tests 实际运行，两视口 Policies/Trace 截图实际查看；production 网络全部 GET、无 console/page errors、文档横向 overflow ≤1，mobile 表格实际横滚。错误来源语义归 S2 阻断，不用此行 PASS 掩盖。 |
| 10 | 原始 RED/GREEN、XML/SHA/source/运行身份、独立完整 backend/API/攻击/UI/build/production、行为断言 | PASS（执行与留档完整）；产品整体结果为 FAIL。73 archived XML 和 13 own XML 均独立解析；352 before/after 已补齐实现者 fullv2 的 351 snapshot 缺口；生产攻击为 assertion FAIL，未当 PASS。 |
| 11 | 原 C1 148 raw/10 XML、无效 attempts 与 SPEC 材料保留；不盲跑旧固定 runner | PASS：原 148 payload+manifest 与 HEAD Git blobs 精确一致，10 XML 均解析；保留坏 fixture、guard/selector attempts。使用自有新 runner/UUID DB，不运行任何会写 golden 的旧 runner。 |

## 本轮实际运行

环境：Python 3.11.17（`/tmp/eduagent-m3-patched-runtime/bin/python`），PG16 `127.0.0.1:55432`，Redis `127.0.0.1:56379/0`，Node **20.19.5**，锁定 Vite 7.3.7 / plugin 5.2 / React18。数据库环境只设 `DISTRIBUTED_TEST_DATABASE_URL`，显式移除 `DATABASE_URL`。pytest 网络 guard 禁止非 loopback 连接；没有模型调用、Agent50 实跑、Task10 或 CODE 工作流。

下面 T/P/F/E/S 来自 XML testcase 实际解析，不把重复测试或不同时间的同一场景累加为独立样本：

| 本轮 XML | T/P/F/E/S | suite 秒 | SHA-256 |
| --- | --- | --- | --- |
| full.xml | 1726/1726/0/0/0 | 379.018 | `37e44e95893b8d2d667e163876e4958eaaf039df9771a44bf24ab25baced53a4` |
| attacks.xml | 25/25/0/0/0 | 2.182 | `8d0299b1719dc7871ccc1d02a04e915996e21ccd818e088ea240a42ffaed5954` |
| relations-valid.xml | 11/2/9/0/0 | 6.311 | `78466e8afd3dc9ef3b2974be494690b6c8d2638b78e8a21dec82211858d23d2a` |
| corroboration-final.xml | 3/0/3/0/0 | 1.322 | `f26ed9db46377bae911527ec8710a7e06a150ec75dfdffdba676d540e4c56684` |
| ui.xml | 54/54/0/0/0 | 37.214 | `b280ff84fdd05812d2d14157ee731285b1c70f31ba88537a3bcf37be72e923ec` |
| production-current.xml | 2/2/0/0/0 | 1.057 | `d4f4bfe0e7fb75f1243b3af5967632995fdc4176aa7dd96318ace13b52d03ba6` |
| production-history.xml | 2/2/0/0/0 | 1.106 | `327529b15104298e291e23c7fc1c2753ea296bbf431275720b2dbbb6743d2deb` |
| production-history-visible.xml | 2/2/0/0/0 | 1.144 | `efbf7e4f1b7c2cf2560c3159602a2fc4fa8efcb6b6b12d8abf2e789507da62d9` |
| production-approval-malformed.xml | 2/0/2/0/0 | 1.242 | `0b7cb57e2efa2789f36c939ddf0b3fc489300b652b0c7ee8d07ebf865b82bc19` |
| production-genuine-malformed.xml | 2/0/2/0/0 | 1.606 | `d2e6398c46a710614c6215ebbc9c5a5080756feb6dae164790d9845858c2cd86` |

Full UTC：**2026-11-01 23:15:26.889985 → 23:22:04.586926**，包括进程/数据库收尾约 397.697 秒；pytest 输出 379.04 秒，XML suite 为 379.018 秒。完整后端中 `test_ops_health_binding=42`、`test_promotion_ops_api=77`、`test_ops_api=19`，相关 138 项为 full 的子集。初实现 1675、原 C1 CODE 1684、实现者 fullv2 1726 都不是本 reviewer 的新样本。

Relations UTC 23:22:36.581602 → 23:22:45.736914；attacks 23:24:17.456480 → 23:24:22.188114；最终 corroboration 23:30:22.328549 → 23:30:26.004501。同名中间运行不替换最终运行，命令/DB/时间完整在对应 `*-command.json`。UI wall time 见 `ui.log`，37.214 秒是两个视口 suite time 汇总，不当墙钟时间。

实际执行命令（`E` 为上述固定唯一目录；这些已执行 label 不可直接重用覆盖 raw，应在新 UUID 目录复现）：

```bash
/tmp/eduagent-m3-patched-runtime/bin/python "$E/review.py" pytest full -c pyproject.toml -q
/tmp/eduagent-m3-patched-runtime/bin/python "$E/review.py" pytest relations-valid -c pyproject.toml -q "$E/test_spec_relations.py"
/tmp/eduagent-m3-patched-runtime/bin/python "$E/review.py" pytest attacks -c pyproject.toml -q "$E/test_code_attacks.py" "$E/test_extra_code.py"
/tmp/eduagent-m3-patched-runtime/bin/python "$E/review.py" pytest corroboration-final -c pyproject.toml -q "$E/test_spec_corroboration.py"
bash "$E/node.sh" build build
bash "$E/node.sh" ui test e2e/ops.spec.ts --reporter=line,junit --output="$E/ui-output"
bash "$E/live.sh" genuine_malformed_latest_valid
env SPEC_SCENARIO=genuine_malformed_latest_valid bash "$E/node.sh" production-genuine-malformed test --config=playwright.production.config.ts --reporter=line,junit --output="$E/production-genuine-malformed-output"
```

Backend runner 的 cwd 为 M3 `python/`，完整 testpaths 由 `pyproject.toml` 选择。每 invocation 新 UUID DB + finally drop；所有 cache/basetemp/JUnit 指向 E。前端命令 cwd 为 `E/frontend/`。其他 production 命令使用同一方式分别以 `current`、`history`、`history_visible`、`approval_malformed_latest` 为独立场景启动和退出，自有日志/fixture/DB 清理记录分别保留。

Build PASS，`build.log` 保留既有 chunk-size warning。实体 copy 的 node_modules 无指回源树的 symlink；31 个 tracked frontend 文件的字节核验中仅自有 `vite.config.ts` / `playwright.config.ts` 为隔离 cache/端口而修改，全部产品 frontend/source/e2e 字节与 freeze 一致。production 从真实构建 dist 提供静态资源，实际加载的 assets 与 dist **逐字节相等**并核验 SHA，不使用 Vite dev 或 route mocks。

production Ops JS SHA：`a4430d560a4461a12441b5433d72592db328646e28057a6426ecdef36a13e416`；CSS：`4f3070753582aa2f0a5e82bd28b182212feeb9724a92bf7aee5ae14a2a0c75e6`。全部 6 个 dist 文件哈希在 `independent-verification.json`，构建已在留痕后按要求清缓存移除。

## 来源证明与中间失败

本轮逐文件验证全部 **352 source** 与 HEAD Git blobs 一致。7 次 pytest 的 before/after 共 **14 份完整快照**彼此完全相等；清理后的第 15 份 `final-source-after.json` 也相等。快照包括两棵工作树全部 tracked 文件、352/266 source、HEAD/status/index hash+mtime、venv 和源 Vite cache 元数据。不是沿用遗漏新 test 的实现者 351 snapshot。

M3 index SHA：`81df8d0c20bd673297648f28baf2ced704764c47d91a3604dd44efec10e37ddf`；primary HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422`、266 source SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`，两个 worktree 均 clean、全部前后相等。没有修改 source、index、主 venv 或源 Vite cache。

最新 231 payload + manifest 共 **232 evidence Git blob**，原 C1 148 payload + manifest 共 **149 Git blob**，本轮全部 independently byte-exact。最新 manifest SHA `ea803109837115ba2236efbefbad34e46f7e2a7ac1fd41307249ea4fd52cce46`；旧 C1 manifest SHA `8713e23393c6c5e0650c31204cc2053757da2c97484374a3d42f85d94fe4541f`。明细为 `archive-gitblob.json`、`archive-parsed.json`，只证明 provenance，不替代 SPEC。

独立解析全部 73 archived XML。最新修复的 19 XML 精确 T/F/E/S：

| XML stem | T/F/E/S |
| --- | --- |
| c1red / c1redvalid / c1green / greenfinal | 2/0/2/0；2/2/0/0；2/0/0/0；2/0/0/0 |
| relations / relationsv2 / relationsv3 / relationsv4 | 126/5/0/0；126/0/0/0；137/54/0/0；137/4/0/0 |
| relationsfinal / relationsfinalv2 / relationsfreeze | 137/4/0/0；138/0/0/0；138/0/0/0 |
| full / fullv2 | 1726/1/0/0；1726/0/0/0 |
| uifull / uifinal / uifinalv2 | 54/6/0/0；54/0/2/0；54/0/0/0 |
| production / productioncurrentfinal / productionhistoryfinal | 4/0/0/0；2/0/0/0；2/0/0/0 |

原 C1 10 XML 精确 T/F/E/S：attacks 21/2/0/0、attacks-v2 21/1/0/0、attacks-v3 21/2/0/0、extra 4/0/0/0、full 1684/18/4/0、full-v2 1684/0/0/0、live 4/2/0/0、live-v2 4/2/0/0、ui 40/2/0/0、ui-v2 40/0/0/0。逐 XML SHA 与完整失败 message 已在 `archive-parsed.json` 独立留存。最新 `c1red` 的 2 errors 是无效 RED；`uifinal` 是 2 errors，不能改称 assertion failures。原有效 C1 两部署 failures 本轮关闭；新 S1-S3 并非原 F1/C1 偷换复开。

本 reviewer 无效/部分无效 attempts 也全部保留，不混入产品失败：

- `relations.xml`：11 setup errors，临时 conftest 缺 raw_repo fixture；补齐自有 fixture 后 `relations-valid.xml` 才是 11 个有效探测。
- `corroboration.xml`：3 failure 节点，但都是遗漏 `-c pyproject.toml` 导致 async runner 配置未加载，不算 3 产品失败。
- `corroboration-valid.xml`：1 genuine assertion failure + 2 自有证据序列化 AttributeError；不能整组算 3 产品失败。`corroboration-final.xml` 才是全部 3 个真实 assertion failure。
- 首次 `live-genuine_malformed_latest.log` 因把 UUID 对象直接传给严格查询接口而启动失败，未跑页面；新场景 `_valid` 使用合法 string 后完整生产验证。
- 一次定位 PoliciesView 的旧路径不存在、一次查询不存在的 pytest.ini/health_metrics.py，都是只读定位错误，不是产品缺陷。

原始失败 XML/log、有效重跑、脚本、JSON、screenshots 和 traces 均保留，没有覆盖 golden 或删除断链探测以求 green。

## 截图、限制与清理

浏览器运行前完整读 TRAE-browseruse skill。实际查看生产 current/history 双视口详情、追加的 history_visible 双视口左侧来源画面、两个 malformed 场景双视口左侧来源画面，以及 UI Policies/Trace 双视口截图。历史移动端第一次右滚截图不能单独证明来源可见，故额外运行 `history_visible`：先断言来源标签可见和 bounding box 在 viewport 内，留左侧画面，再实际横向滚动，最终 2 PASS；这不是拿文本存在推断先前可见。

本轮是 synthetic engineering validation：真实 PG/migrations/triggers/evaluator 和真实 production build/API，但没有真实学生数据、模型请求、formal holdout、生产发布、两 worker Task10 rehearsal、Docker/CI 或跨浏览器证明。UI 54 项使用 frozen mock fixtures，其覆盖不能替代真实 production；真实生产服务只挂载 Ops API 查询状态，未启动业务 dispatcher/worker。Agent50 持续暂停；其单元测试不等于 live Agent50。模型请求/模型费用均 **0 / 0**。

清理核验 UTC **2026-11-01 23:34:46**：全部 **13 exact UUID DB** 不存在、**248 exact UUID Redis stream** 不存在，`33630` / `33631` 关闭。exact 名称、查询前后结果、已移除目录在 `E/cleanup-verification.json`；只按本次记录的 exact 资源处理，没有全局 flush、prefix deletion 或他人端口清理。

自有 `frontend/node_modules`、`frontend/dist`、npm/pytest/tmp/Vite cache 在 hashes/证据留存后清除。产品和主工作树、主 venv、源 cache 前后未变；保留 raw 证据和可复现脚本。没有实施修复、提交、推送或启动后续任务。

## 交接

**WHOLE Task9 SPEC FAIL。** 父侧应交给新的实现者修复 S1-S3 后重新冻结，再发起 **fresh full SPEC**；仅其 PASS 后才可进行 **fresh full CODE**。本报告不授予 Task9 acceptance，不允许根据已有 1726/UI54/build green 直接进入 CODE/Task10。

本文件完整落盘后才发送最终交接；完整机器可读证据以 `E/independent-verification.json`、`E/cleanup-verification.json` 和 `E/retained-manifest.json` 为索引。
