# WHOLE Task9 SPEC FAIL

**结论：WHOLESPECFAIL。** 最终 freeze 存在一个 P2 规格缺陷：Active 的 approval 引用无效 Canary health receipt 时，查询仍认证更早的 Shadow 为 `passed / consumed_chain`。独立 API 攻击、重新执行与真实 PostgreSQL production build 双视口均得到正确性断言 FAIL。完整 backend/API/UI 常规 PASS 不覆盖此 FAIL。

本报告仅交父侧归档。没有实施修复、修改产品 source/tests/index/主 venv、commit/push、模型请求、Task9 acceptance、启动 CODE/Task10/Agent50。不得据此直接进入后续阶段。

## 1. 身份与范围

- 唯一目标：`/Users/bytedance/Documents/trae_projects/eduagent-m3`，下文 R。
- branch：`feature/m3-trusted-policy-promotion`。
- freeze：`c45bf55e1aa5753eb1d83ad8a3eb60487b741474`。
- parent：`3444cf1967f9b5c9d64fde824dd4b53333a29143`。
- WHOLE 范围：Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f` 至 freeze，包括初实现、F1、C1、S1-S3，不只审最新修复。
- 自有原始唯一目录：`/tmp/m3-task9-wholespec-3f2b2095-92a9-45b5-bcf8-55b2e2eabd2c`，下文 E。
- 全部 **353 source** SHA256：`1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65`。算法为 `python/` 与 `frontend/` 源全集逐文件 SHA256，排序 `(relative path, hash)` 的 compact ASCII JSON 再 SHA256，不包含 evidence 自身。

完整读取本轮 brief、批准 design 全文、plan 全文与 Task9 六步、新完整实施 result/report、前轮 fresh SPEC FAIL 全文及初实现/F1/C1报告。逐文件读取 WHOLE 改动的 15 个 source/test 路径和相关依赖：

```text
frontend/e2e/ops.spec.ts
frontend/src/ops/OpsApp.tsx
frontend/src/ops/PoliciesView.tsx
frontend/src/ops/RunsView.tsx
frontend/src/ops/TraceView.tsx
frontend/src/ops/api.ts
frontend/src/ops/ops.css
frontend/src/ops/types.ts
python/api/ops_routes.py
python/core/distributed/ops_contracts.py
python/core/distributed/ops_queries.py
python/tests/distributed/test_ops_api.py
python/tests/distributed/test_ops_health_binding.py
python/tests/distributed/test_ops_source_integrity.py
python/tests/distributed/test_promotion_ops_api.py
```

独立读取并结构核验新 241 raw payload、旧 SPEC 202 raw payload：JSON 全解析、JSONL 全行解析、XML 全 testcase/message 解析、ZIP 全 member/CRC 与 trace/network JSON 事件解析、文本全文读取、PNG 完整字节 hash。结构读取不等于人工查看每张归档截图；实际视觉检查的 17 张自有截图明确列在 `E/screenshot-inspection.md`。父侧 802 Gitblob/14 XML/7 paired/cleanup 声明没有代替本人的判断或执行。

## 2. 有效发现

### S1-R / P2：无效被引用 Canary 回执仍可认证 Active 的部分消费链

**规格依据：**

- `R/docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md:121-145,276,355-365,393`：receipt 全身份、immutable deployment、必要回执、缺失/unknown 不当通过、命令与查询边界。
- `R/docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md:1200-1227`：可信只读投影、健康来源和页面证据。
- `/tmp/m3-task9-source-integrity-spec-brief.md:51-62` 的本轮 S1/S3要求：验证两段完整消费关系，缺失/poison/同错误声明不能得到 green consumed，计数费用不一致不能 fallback。

**根因与产品位置：**

1. [`_consumed_canary`](file:///Users/bytedance/Documents/trae_projects/eduagent-m3/python/core/distributed/ops_queries.py#L646-L716) 检验 approval/audit、canonical command 及 approval 与所引用 receipt 的表面相等，但没有验证该 receipt 本身的 `gate_type/status`、四维、issuer/model/role、冻结窗口及精确 count/cost 是否有效。
2. [`_health_receipts`](file:///Users/bytedance/Documents/trae_projects/eduagent-m3/python/core/distributed/ops_queries.py#L392-L422) 据此把 Canary 当作已消费前序，继续为 Active 追加 Shadow 来源。
3. [`_project_health_sources`](file:///Users/bytedance/Documents/trae_projects/eduagent-m3/python/core/distributed/ops_queries.py#L449-L522) 会正确拒绝 poisoned Canary，但逐 gate `continue`，未使完整链失效，保留 Shadow `passed / consumed_chain`。
4. `R/frontend/src/ops/api.ts:495-556` 的闭合 DTO validator 能接受这个形状合法但链不完整的响应；`R/frontend/src/ops/PoliciesView.tsx:202-225` 如实显示服务端错误认证。不是前端自行推断，也不是未验证 DTO 的问题。

**有效最小复现：**

1. 每 invocation 创建自有 UUID PG DB，执行真实 migrations/immutable triggers。由 `real_active_fixture(stop_at="canary")` 形成真实 Shadow→Canary 命令/evaluator/20+20 冻结证据。
2. append 一个新的 Canary receipt，保持已有 receipt/details/window/evidence 身份，仅令 `sample_count=0`，不 UPDATE 旧数据、不关闭 trigger、不降低 cohort 或阈值。
3. append 新 Active snapshot 与对应完整规范 `PromotionCommand`、audit、`required_receipts=["canary_health","shadow_health","promotion_approval"]`；由 `_create_promotion_approval` 引用精确 poisoned receipt。所有 command 字段、actor/reason、hash、time 均规范一致，不是旧任意错误 hash 夹具。
4. 请求 `GET /ops/policies/deployments/{new_active_id}`。正确性要求所有已认证消费来源为空。

自有实现位于 `E/test_independent_integrity.py:37-95,140-157`；仅为外置 append-only 测试夹具，不是产品实现或授权发布。

**Actual：** HTTP 200，Canary 来源被拒绝，但 Shadow 仍 `status=passed`、`health_source.relation=consumed_chain`、20 样本、费用 `0.40000000`。approval 自身 `sample_count=0` 并与 poisoned receipt 相等，仍足以让 `_consumed_canary` 返回。

**Expected：** 精确被引用 Canary health receipt 无效，不能证明 Active 的完整消费链；不得对其转而认证任何经该断链连接的 Shadow 消费来源。可展示 raw 历史资格 receipt，但不得投影 green consumed。Shadow→Canary 的独立合法历史记录不因此应被删除；本 FAIL 针对 Active 的完整来源认证。

**固定证据：** `E/independent-integrity/referenced-active-sample_count.json`：

```text
actual_hash = stored_hash =
9424929acba59bca1d082203674be471e7f835758a41e04538488a5e5f9d438b
referenced_health = a4fef888-d58c-451c-bd3b-5ce00af42898
original_health   = 6b599a8c-c67e-4ea9-9249-c66757714163
poison            = sample_count: 0
remaining gate    = shadow_health / passed / consumed_chain
remaining receipt = 3def1502-a4e9-47d8-95aa-43f8dbe4175e
source deployment = e8f8a42e-e1c4-4bce-8d9d-dfa3579dea15 / version 4
source window     = 044b8c4f2300788e10c611676568e9352975e10edd9ee25f13e68d9d5768410c
```

**独立确认：**

- `independent-integrity.xml`：47 项，42 PASS、5 有效 assertion FAIL。Active 精确引用的 receipt 依次仅改变 `sample_count=0 / cost=0 / status=unknown / protocol_hash / gate_type`，均留下 Shadow consumed；两段规范命令全部 8 字段+合法对照、8 approval 绑定攻击、有界 key/Decimal 攻击均通过各自正确性要求。
- `independent-reproduction.xml`：新 UUID DB 重跑 12 项，7 PASS、同 5 有效 FAIL；没有用上一 DB 结果冒充复现。
- `chain-metadata-v2.xml`：17 项，11 PASS、6 有效 FAIL。Active 被引用 Canary receipt 的 `issuer / model_identity / data_role / policy_hash / runtime_hash / source_revision` 各单独错误仍留下 Shadow。v2 的 foreign policy 使用已存在 stable artifact，满足 FK；参数化名称仍带原 `f...` 字面标签，实际 poison 值在 JSON，不误称 v2 为 FK失败。
- `production-referenced-poison.xml`：真实 PG + built dist + Ops API，desktop1440×900/mobile390×844，**0 PASS / 2 assertion FAIL**。网络 GET-only、asset bytes、无 console/page error、body overflow 和 mobile 真横滚先通过，随后 `health == []` 正确性断言失败。没有把“观察到错误”计作 PASS。
- 真实生产 fixture：`E/live-fixture-referenced_canary_poison.json`；双方响应：`E/production-referenced_canary_poison-{desktop,mobile}.json`；实际看过 `E/screenshots/detail-referenced_canary_poison-{desktop,mobile}-left.png` 和 mobile 右滚截图。画面为 Canary unknown、Shadow passed/已消费前序证据。

上述是 **一个根因** 的多种 poison 与重复证据，不算 11 个独立缺陷或独立发布样本。没有证明发布权限绕过、生产业务写入或真实学生影响，所以定 P2，不升级为 P0/P1。最小修复目标是让完整消费关系依赖精确被引用 receipt 的有效性并传播断链；本 reviewer 不提供或实施补丁。

## 3. 全规格矩阵

六步按批准 plan `:1172-1250` 核验：

| 步骤 | 本轮结论与证据 |
| --- | --- |
| 1. bounded/read-only API tests | PASS：独立 full 与 relations-api-v2 实际执行 auth/query/method/DTO/keyset 项；`test_promotion_ops_api.py:119-210,329-398`。 |
| 2. 原始 RED | PASS（历史 provenance）：初实现/F1/C1 与 S1-S3 原 RED 原样保留；原无效 fixture/setup/0收集不能算产品 RED，详见第6节。没有重新编造原测试。 |
| 3. redacted projections | FAIL（完整消费链）：只读/有界/脱敏/immutable binding 均通过；S1-R 阻断来源可信规格。 |
| 4. Policies view | FAIL（来源正确性）：基础交互、布局、历史/current、两组 malformed、合法 chain 正确；新增生产 poison 双视口实际显示错误认证。 |
| 5. backend/frontend verification | FAIL（整体）：完整1793/API244/source67/UI54/build通过，但独立有效 attack 与 production 正确性 FAIL，不能以常规 green 验收。 |
| 6. commit evidence surface | PASS（provenance）：freeze 全353source及新旧归档逐Gitblob一致，未认领实现者提交为本人工作；未commit/push，不授予Task9验收。 |

WHOLE 11 项维持全部核验，不只查 S1-S3：

| # | 规格 | 结论与 file:line / 自有证据 |
| --- | --- | --- |
| 1 | 四 GET 路径、复用 Ops auth/loopback、严格 query、422/404/503、不接受任何 mutation | PASS：`R/python/api/ops_routes.py` 全文；`test_promotion_ops_api.py:145-208,329-363`、`test_ops_api.py:645-704`；full/API244/自有25攻击。 |
| 2 | 三列表同时间 keyset/100上限/typed cursor/allowlist/filter reset/有界详情audit | PASS：`test_promotion_ops_api.py:119-208,347-362`；`E/test_extra_code.py:15-46` 的113条100+13无漏重、末页cursor；详情audit100与window tiebreak；API244。 |
| 3 | closed DTO+TS validator、hash/UUID/Decimal/numeric poison、unknown不补零、脱敏 | PASS（类型/隐私），FAIL（来源真实性）：`ops_contracts.py:177-307`、`api.ts:404-556`、`test_promotion_ops_api.py:210-256,486-520`、`E/test_code_attacks.py:122-136`；S1-R形状合法但链错误。 |
| 4 | F1九条资格gate四维/issued-created-id排序、failed/unknown遮蔽与later pass恢复 | PASS：`test_promotion_ops_api.py:258-326`；full.xml实际九个node均PASS，完整名单在`independent-verification.json.f1_nine`，恢复断言在同node内。不是拿历史F1报告当本轮执行。 |
| 5 | read-only repeatable snapshot、GET无写入、不调用command/evaluator/qualification replay | PASS：`ops_queries.py:283-287`、`test_promotion_ops_api.py:364-398`、`E/test_extra_code.py:48-80` 并发append不可见；API244实际执行；bounded frozen SQL捕获只读IN+LIMIT。 |
| 6 | local health部署/version/threshold/window/cohort/latest/unknown、不借旧pass；精确count/cost | PASS（leaf校验）：`test_ops_health_binding.py:94-151,223-264`、`test_ops_source_integrity.py:179-209,241-255`；source67/health42与独立11 frozenkeys probes；完整消费失效传播仍归S1-R FAIL，不泛称健康安全全通过。 |
| 7 | audit/approval/required/actor/issuer/model/role两段完整真消费链、local/consumed、cutoff、current/history/rollback/freeze | FAIL（S1-R）：`ops_queries.py:392-716`；规范命令8字段两段18项与approval8字段均PASS、原42关系边界PASS；11种精确引用receipt poison仍认证Shadow。C1同artifact当前与历史两项实际PASS；production current/history各2PASS。 |
| 8 | Run/Trace始终使用stored immutable deployment/cohort/effective hash/namespace class，legacy NULL | PASS：`test_promotion_ops_api.py:401-467` 的real head advance+health rollback与NULL；`frontend/e2e/ops.spec.ts:604-656`、RunsView/TraceView全文；API/UI/补Trace截图。 |
| 9 | auth/loading/error/empty/stale abort/disposed/reset、status/tooltip/metrics/timeline/shield/无写控件/mobile真横滚 | PASS（基础交互），FAIL（错误认证语义）：`PoliciesView.tsx:32-98,152-176,202-225`、`ops.spec.ts:503-738`；UI54实际双视口、补visual4；正常prod10PASS、poison2FAIL，17截图实际查看，body无横向溢出。 |
| 10 | 完整独立backend/API/attack/Node20build/UI/PGproduction、XML/hash/source/time/raw证据 | PASS（执行与留档），整体产品FAIL：16自有XML、100归档XML、70自有trace ZIP；34前后完整快照+最终第35份；见第4-6节。 |
| 11 | scope/cost/role/provenance/资源隔离/只读/无模型/不自行验收 | PASS（本轮流程）：8pytest+6独立PG生产周期，14UUIDDB/248stream精确核验，主树/venv/cache未变；工程验证非正式release，未知费用不当零。 |

S2 的 latest 优先、数组/null/缺失/非法 ID、failed/unknown遮蔽及明确other-command/cutoff，在 `test_ops_source_integrity.py:123-176`、`test_ops_health_binding.py:223-264`、自有8approval关系+5approval metadata与真实malformed生产均正确；没有跳过旧pass寻找绿色。

S3 的精确 sample_count、finite/nonnegative Decimal、冻结candidate+stable keys、唯一性/顺序/限额/identity/time及IN+LIMIT正确；`ops_queries.py:525-597`、自有`test_independent_integrity.py:160-219`。20/20正常非零费用链继续可见；21/21循环Decimal对照`test_ops_source_integrity.py:195-209`两项在full/source67均PASS，未用roundedmean×count、补零或降低阈值。但 S3 错误 receipt 在完整链中仍因 S1-R 留下更早 Shadow，不能据此写“S1-S3全部关闭”。

原有效 relations11（2positive/9negative）+corroboration3、code/extra25全部在本人 API244 重跑通过。新增67中`test_inconsistent_consumed_summary_is_unavailable:212-238`只直接验证单来源 `_project_health_sources`，不覆盖Active完整GET链的失效传播；因此其green不反驳S1-R。

## 4. 自有真实运行矩阵

T/P/F/E/S 按实际 XML testcase 元素解析，不按 exit code 推断。不同运行与full/API/source67有重叠，不相加为独立样本；suite秒是testsuite汇总，不必等于墙钟。

| XML stem | T/P/F/E/S | suite秒 | SHA256 |
| --- | --- | --- | --- |
| full | 1793/1793/0/0/0 | 380.552 | e16ba40a506f05c79762d18f14b2674289add49d388d28d09ab6d7fd74ca2411 |
| relations-api（无效路径/0收集） | 0/0/0/0/0 | 0.005 | 937b6804898b750edc01fbec3e545690e5379624020c62c8bc13774edfc4acec |
| relations-api-v2 | 244/244/0/0/0 | 64.825 | 5776c90384d741f9d3a3136ab5803bf757b6e1161d07461b81663683cca3313a |
| independent-integrity | 47/42/5/0/0 | 25.254 | ffdcf2333064fc1731f660f69dff5ac210a71789c759d14ddf46460e3b92ec67 |
| independent-reproduction | 12/7/5/0/0 | 7.515 | 382265988c308057bdb0d89627e43f881e7ee1af8ba9602b79d08edebf4dc38a |
| chain-metadata（含2无效FK夹具failure） | 17/10/7/0/0 | 9.014 | f7cfe4f81e1e3839239cecbcc61160c40d7aaf85953f180c3535322d86669f6e |
| chain-metadata-v2 | 17/11/6/0/0 | 7.243 | e675b33a1491330f5c40e8d97cdb0ab320d01376b7389b2f50c40890c85088a4 |
| source67 | 67/67/0/0/0 | 25.350 | 42624f997ba47e1d029d7d8d780786b786d8a98ad0bb06336de7c41cd1624d1e |
| ui54 | 54/54/0/0/0 | 39.282 | 3d4a13beddfe06662782da8300502ee638965b79e01b1520e0ed918f1e9e263e |
| ui-visual | 4/4/0/0/0 | 6.675 | 7226cf27199ae2d274cced5f4be97261f858f3b96f8bbf95086c77bddceb91bb |
| production-current | 2/2/0/0/0 | 1.177 | 6da44e3616d95ce5986a2b545e6c045baf77ab18318f464f28c049e607be9bd8 |
| production-history | 2/2/0/0/0 | 1.420 | ff0415ff42f313a25c26daa3cd2c1ce35e63dbd46e8bde5474a6daca2a7493d7 |
| production-approval-malformed | 2/2/0/0/0 | 1.210 | fd18ca83baf27c6c2d03ecc32177308c4a7e25e47bf2678f15abf5af9ac696e9 |
| production-genuine-malformed | 2/2/0/0/0 | 1.253 | 25f56c9de485456cfcf1e1da88659b4d797c52faf59a0f9835b92600534b8c36 |
| production-genuine-valid | 2/2/0/0/0 | 1.439 | 1df1fb2e8b5933aa57d30b550fcb3dd2f31467dbcd24892a90c1f102c1ea666e |
| production-referenced-poison | 2/0/2/0/0 | 1.427 | c792e71e0cb1fc18f37b7c0cd2d11299b2a86730ab0427aa0b4c576e05e646f1 |

**build：PASS**，`E/node20-build.log` 实际执行 `npm run build`（tsc + vite），Node20.19.5/Vite7.3.7/plugin5.2.0/React18.3.1/Playwright1.64.1/TS5.9.3。既有>500kB chunk warning保留，不当错误。build UTC `00:21:59.849788 → 00:22:06.313213`。

完整后端UTC `2026-11-02T00:11:10.731968+00:00 → 00:18:02.283416+00:00`，包含DB/进程收尾；pytest实际380.57秒。API244 UTC `00:20:04.407837 → 00:21:15.866368`；复现12 UTC `00:22:32.757873 → 00:22:44.596503`；metadata-v2 UTC `00:26:35.524058 → 00:26:45.350001`；source67 UTC `00:28:32.388843 → 00:29:00.508745`。UI54墙钟`00:22:32.521078 → 00:22:54.477698`，Playwright输出21.6秒，不把39.282双suite汇总当墙钟。

所有 exact command arrays、cwd、UTC、exit/drop_exit、XML模块与完整节点/message 在 `E/independent-verification.json`、`E/*-command.json`；生产PID/exit/drop在六个`E/*-lifecycle.json`，每个drop_exit=0。

以下为runner入口与参数摘要；精确已执行child command arrays以`*-command.json`为准。不能盲跑这些固定OWN/labels覆盖证据；复现须另建UUID目录、labels、DB、端口和trace路径：

```text
PY = /tmp/eduagent-m3-patched-runtime/bin/python
E  = /tmp/m3-task9-wholespec-3f2b2095-92a9-45b5-bcf8-55b2e2eabd2c

PY E/review.py pytest full -c pyproject.toml -q
PY E/review.py pytest relations-api-v2 -c pyproject.toml
  tests/distributed/test_ops_source_integrity.py
  tests/distributed/test_ops_health_binding.py tests/distributed/test_ops_api.py
  tests/distributed/test_promotion_ops_api.py E/test_spec_relations.py
  E/test_spec_corroboration.py E/test_code_attacks.py E/test_extra_code.py -q
PY E/review.py pytest independent-integrity -c pyproject.toml E/test_independent_integrity.py -q
PY E/review.py pytest chain-metadata-v2 -c pyproject.toml E/test_chain_metadata.py -q
PY E/review.py pytest source67 -c pyproject.toml tests/distributed/test_ops_source_integrity.py -q
PY E/frontend_run.py build node20-build
PY E/frontend_run.py ui ui54 e2e/ops.spec.ts
PY E/frontend_run.py production production-current current
PY E/frontend_run.py production production-history history
PY E/frontend_run.py production production-approval-malformed approval_malformed_latest
PY E/frontend_run.py production production-genuine-malformed genuine_malformed_latest_valid
PY E/frontend_run.py production production-genuine-valid genuine_valid
PY E/frontend_run.py production production-referenced-poison referenced_canary_poison
```

runner最终实际pytest命令附加`-p safety`、E专属cache/basetemp/JUnit；PYTHONPATH包含R/python与E。Python3.11.17，仅设置`DISTRIBUTED_TEST_DATABASE_URL`，移除生产`DATABASE_URL`。PG16.15 `127.0.0.1:55432` postgres无密码，Redis56379/0；每invocation新UUIDDB/finallydrop，非loopback连接guard禁止外部模型网络。Node实体copy modules，不symlink回产品。浏览器测试前完整读取TRAE-browseruse skill。

## 5. 生产、截图与源身份

五个正常场景均为本人新运行，共10PASS：current B/hold无借A；history A精确原receipt/window；synthetic approval malformed及真命令malformed最新均无consumedsource；genuine_valid仍两项合法passed consumed。production无route mocks，无Vite dev，从真实dist提供静态资源；只挂Ops查询API，未启动业务worker/dispatcher。

本人实际view_image查看17张：UI Policies/Trace四张、五正常生产双视口左侧十张、poison双视口左侧及mobile真右滚三张。视觉和网络/数据断言共同核验；没有将截图生成当行为PASS。正常表格横滚与document overflow<=1；desktop截图捕获时sticky header遮住局部行不另报产品缺陷。

31 tracked frontend copy仅`vite.config.ts / playwright.config.ts`为自有端口/cache修改；所有产品/e2e字节与freeze一致。modules为实体目录，24,463个实体文件hash形成tree SHA `29585540623285fb824d3dd3fe9bdffc080a2eaa18aac77c2fb73e0336262a61`，内部.bin symlinks全部解析在`E/frontend/node_modules`内。

所有生产HTTP资源与本轮dist逐字节相等并核验SHA，Ops JS `a4430d560a4461a12441b5433d72592db328646e28057a6426ecdef36a13e416`，CSS `4f3070753582aa2f0a5e82bd28b182212feeb9724a92bf7aee5ae14a2a0c75e6`；六个dist文件全部hash保存在机器索引，随后仅清自有dist。

17次执行的34份 before/after完整snapshot与首次full-before**完全相等**，包括两棵树全部tracked字节、全部353/266source、HEAD/status/index hash+mtime、主venv和源Vite cache元数据。每次snapshot均独立逐353源对freeze Gitblob，非父侧证明复用。清理后`E/final-source-after.json`为第35份，仍全等。

- M3 index SHA `e4a38b37a1f4c3a51b647bf6e12b3888d3fc6b1ae735983e1f84f53de2c9f2b8`，mtime `1793577843731667860`。
- 主eduagent HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422`，266source SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。
- 主index SHA `3c86bfc88b4c08aa70ae40624b1a3ba21bf77c129192b9cd9a1eddb72ee66c95`，mtime `1793564703011337702`。
- 两棵工作树始终clean；主venv10024 entries与源cache元数据未变。修复测试env未安装/改动/删除。

## 6. 原始证据与失败分类

独立逐manifest payload+Gitblob核验四组历史归档：

| 归档 | payload数 | manifest SHA256 |
| --- | --- | --- |
| task9-source-integrity-fix-evidence | 241 | 516bde76893d4a2deceeb95b2ff55fbed330f78a51d7d6c47213cff119e114ec |
| task9-health-binding-spec-failure-evidence | 202 | ca86a8c220fbcf30a4f8cdec10d9c5fcf674cd69a453fbef8779ca51be3a99d2 |
| task9-health-binding-fix-evidence | 231 | ea803109837115ba2236efbefbad34e46f7e2a7ac1fd41307249ea4fd52cce46 |
| task9-code-failure-evidence | 148 | 8713e23393c6c5e0650c31204cc2053757da2c97484374a3d42f85d94fe4541f |

新payload SHA `57afd1b91c0d12e9515c9ac2bf7b65c6dc91b46ed0b7669cf0606e3f9741bee1`；旧SPEC payload SHA `03c093f997344b8000e077d54bf76ca90df7af4841fed8085ab1cec7f02d5d4a`。二者payload算法本人重算。全部100历史XML独立解析，`E/archive-parsed.json`记录真实T/F/E/S及失败message；新旧443payload深度结构审计在`E/archive-structure-audit.json`，70自有trace CRC/事件在`E/own-trace-audit.json`。

旧SPEC13 XML真实T/F/E/S：

```text
attacks25/0/0/0; full1726/0/0/0; ui54/0/0/0
relations11/0/11/0（无效setup）; relations-valid11/9/0/0（有效）
corroboration3/3/0/0（无效async配置）
corroboration-valid3/3/0/0（1有效assertion+2无效serializing）
corroboration-final3/3/0/0（3有效assertion）
production-current2/0/0/0; production-history2/0/0/0
production-history-visible2/0/0/0
production-approval-malformed2/2/0/0
production-genuine-malformed2/2/0/0
```

旧15snapshot全彼此相等、352source内容对其HEAD `2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d`逐Gitblob正确；不把旧source当当前353。新实施7paired共14snapshot每组相等，最终source353内容匹配c45，即使记录HEAD仍是precommit3444cf1；red旧352内容对3444cf1，green-v1/67-v1中间source保留为实施中间状态，不冒充最终freeze证明。新final-source-after及full-final/API-final/source-v2的353均对c45，分类见结构索引。

新实施14 XML原样保留：red-relations11有2PASS/9有效assertionFAIL，red-corroboration3有效FAIL；source-regressions-v1 67有57PASS/10夹具FAIL；v2 67PASS；green56/full1793/API244/UI54与5生产10PASS仍只属实施证据。**原production-current0收集是无效attempt，不能算PASS或FAIL；v2才2有效PASS。**

原67/10夹具FAIL分类不改：非法environment DTO/503两项、FK两项、循环Decimal对照设置两项、UUID/varchar四项。原C1/F1有效失败/修复/不正确fixture/guard/selector/cache/async/serialization中间记录全部保留；C1原有效两部署FAIL现独立关闭，本S1-R不是偷换复开C1或F1。

本人无效/部分无效attempt也保留：

- `relations-api.xml` 0收集/exit4：误指不存在`test_ops_queries.py / test_ops_policy_deployments.py`，首个报错为前者；修正path后独立API244全PASS。0收集不是产品失败或green。
- `chain-metadata.xml` 17/10PASS/7FAIL中仅5为有效断言；2为foreign不存在artifact FK错误，不能算规格FAIL。v2用已存在stableartifact，两target有效，再得到6有效Active断言FAIL；未覆写原XML/log。
- 自有source/配置/辅助test路径定位时不存在的文件只是只读定位错误；实际文件定位后读取，不算产品缺陷。没有跳过有效失败或篡改产品测试求green。

## 7. 账本、清理与限制

自有实际执行8pytest invocations（含0收集）、6独立生产服务/DB周期、1build、UI54及visual4。生产页面监听HTTP **72 GET**，显式request-context **50 GET**（detail+assets+history额外detail）；ready探测至少每场景1 GET，重试总数未装表，不合并伪称122为所有请求。backend in-process API与mock UI请求总数未装表，记unknown。所有页面请求GET，console/pageerror0，document overflow<=1。

**实际模型请求0、实际模型费用0**；fixture cost/model_calls为合成工程账本，不是模型计费。论文/学生效果、正式release qualification、formal holdout、live Agent50、多worker Task10、真实生产发布、Docker/CI、跨浏览器均未执行。不以mock、单元或开发校准替代独立发布资格。

清理UTC `2026-11-02T00:34:31.608622+00:00`，`E/cleanup-verification.json`：14 exact UUID DB全部已finallydrop且实际查询不存在；248 exact UUID Redis stream全部不存在（清理前已0，未删共享key）；35730/35731 connect_ex均61关闭。只清E的实体node_modules/dist/cache/tmp/npm-cache/vite-cache/__pycache__。未flush/prefix删除、停共享服务、改两棵树/主venv/源Vitecache或动他人证据。所有本轮有效/无效XML/log/commands/JSON/screenshots/70trace ZIP/外置scripts完整保留。

## 8. 交接

**WHOLESPECFAIL；S1-R/P2阻断完整来源可信规格。** 本文件先完整写入指定`/tmp/m3-task9-source-integrity-spec-result.md`，随后保留同字节`E/review-result.md`及非循环`E/retained-manifest.json`。机器索引以`E/independent-verification.json`、`E/archive-structure-audit.json`、`E/cleanup-verification.json`为入口，所有hash可复核。

父侧可归档本结论并组织后续修复与重新freeze/fresh WHOLE SPEC；本reviewer不自行实现、不授予验收、不启动CODE/Task10/Agent50。只有后续fresh WHOLE SPEC真正PASS后，才具备父侧启动fresh WHOLE CODE的前置条件。
