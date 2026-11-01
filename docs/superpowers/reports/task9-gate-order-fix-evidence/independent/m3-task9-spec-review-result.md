# Task9 冻结后独立 SPEC 审查结果

结论：**FAIL**。发现 1 个 P2 阻塞规格问题。Task9 不接受，不进入 CODE，不启动 Task10。

审查日期：2026-11-02。审查角色：冻结后全新独立 SPEC reviewer，不是实现者或父侧 provenance 核验者。

## 1. 审查身份与边界

- 唯一源码工作树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 冻结 HEAD：`38f48d763b4a9599aa215f98a2cba1b32003b1e7`。
- 父提交：`8869166878a193a1c453376471cbe52c8fa84b3f`。
- primary：`/Users/bytedance/Documents/trae_projects/eduagent`，HEAD 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`，`main...origin/main [ahead 2]`，clean。
- M3 最终 tracked worktree/index clean，冻结 source/evidence Git blob 与 working-file 内容一致。
- 已阅读 `/tmp/m3-task9-spec-review-brief.md`、`/tmp/m3-task9-implementer-result.md`。
- 权威规格：`docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md:1158-1252`，完整 Task9 六步；`docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md` 的 PostgreSQL 权威、最新回执、Ops 只读、隐私、不可变 Run assignment 与证据可观测性不变量。
- 未编辑源码、锁文件、已冻结测试或 evidence；未写 git index、commit、push；未运行真实模型。
- 所有审查脚本、原始日志/XML、截图、fixture 与独立 manifest 保留在 `/tmp/m3-task9-spec-independent/`。不得把这些 fixture 作为正式模型资格或真实学生证据。
- 执行隔离例外与补验见第 7 节，不能把“tracked clean”扩大解释成所有 ignored 元数据均未被触碰。

## 2. 阻塞发现

### F1 / P2：同一签发时间下 Ops 隐藏后追加 failed，误显示旧 passed

**根因文件/行：**

- `python/core/distributed/ops_queries.py:339-345`，特别是 `343-344`：按 `(issued_at DESC, receipt_id DESC)` 为 gate 排名，遗漏 `created_at DESC`。
- 权威发布门禁的对照：`python/core/distributed/promotion_repository.py:935-947`，采用 `(issued_at DESC, created_at DESC, receipt_id DESC)`，并拒绝最新 failed/unknown。
- 用户可见影响：`frontend/src/ops/PoliciesView.tsx:204-215` 将该投影称作“最新绑定收据”，直接渲染状态；`PolicyStatus` 将 `passed` 渲染为绿色通过图标。

**违反规格：**

- Task9 Step3 应公开真实 gate status，而不是独立于发布权威的另一套“最新”语义。
- design §5.2（第 130 行）规定最新有效绑定回执；Task3 已批准的不变量规定同一绑定的新 failed/unknown 使旧 pass 失效。此处不是以 Tasks1–8 PASS 替代 Task9，而是独立检验当前 Ops 对权威事实的投影是否一致。
- 只读投影无需调用 CommandService 或重做完整门禁资格审核，但不能选择一个被后续有效回执取代的旧 passed。

**最小复现：**

1. 在独占真实 PG 数据库中给同一 candidate policy 的 `formal_holdout` 插入两个合法、不同 evidence hash 的 append-only 回执。两者 `policy_hash/protocol_hash/runtime_hash/source_revision` 全部相同，`issued_at` 全部为 `2026-10-30T00:00:00Z`。
2. A：`receipt_id=ffffffff-ffff-ffff-ffff-ffffffffffff`，`status=passed`，`created_at=2026-10-30T00:00:00Z`，`evidence_hash=7` 重复 64 位。
3. B：`receipt_id=00000000-0000-0000-0000-000000000001`，`status=failed`，`created_at=2026-10-30T00:01:00Z`，`evidence_hash=8` 重复 64 位。
4. 调用 `_bound_gate_receipts(... required={"formal_holdout"}, health_bindings={})`：得到 `missing=["formal_holdout"]`、accepted `{}`。
5. 请求 `GET /ops/policies/deployments/{candidate_deployment_id}`：HTTP 200，`formal_holdout` 仍返回 A、`status="passed"`；B 未显示。
6. 使用生产 build 页面连接同一真实 PG-backed Ops API：桌面和移动页面均显示绿色 `formal_holdout passed`，无该 gate 的 failed 行。

预期：Ops 与发布权威采用一致的最新回执次序，显示 B 的 failed。实际：API/前端均显示 A 的 passed。

影响范围：运维 evidence surface 的 false-positive gate status。没有复现写权限绕过或实际错误晋级，发布门禁在该复现中仍正确拒绝。P2 足以阻塞 SPEC，因为这是 Task9 交付的可信证据表面本身的语义错误。

**独立复现材料与命令：**

```bash
bash /tmp/m3-task9-spec-independent/pytest.sh gate-tie-final \
  -c pyproject.toml \
  /tmp/m3-task9-spec-independent/test_gate_tie.py -q -s
```

该 runner 自动进入 M3 `python`，每次创建唯一数据库并 EXIT dropdb，输出仅在自有 `/tmp`。实测 1 个有效用例，1 failure，0 error/skip；错误即 `passed != failed`，不是 fixture 或启动错误。

- API：`gate-tie-final.log`、`gate-tie-final.xml`、`test_gate_tie.py`。
- 生产页面：`ui-live-isolated.log/xml` 中 desktop/mobile 的两个 `gate-tie.spec.ts` 用例均失败；其余四个 live 用例通过。
- 页面对照脚本：`frontend/live-e2e/gate-tie.spec.ts`、`live_server.py`、`live.sh`、`frontend/playwright.live.config.ts`。
- 截图：`screenshots/gate-tie-desktop.png`、`screenshots/gate-tie-mobile.png`；放大详情证据 `screenshots/gate-detail-desktop.png`、`screenshots/gate-detail-mobile.png` 已视觉查看。
- live server 使用真实迁移后的 append-only 表、实际健康 evaluator/rollback、真实 HTTP Ops 查询，无 API route mock。构造回执始终标为 `test_fixture/release_eligible=false`。

修复方向（未实施）：统一 Ops 与权威发布门禁的回执排序；添加同 issued_at、不同 created_at 且 UUID 反序的 failed/unknown 回归测试。修复、重新冻结后需要 fresh 全 Task9 SPEC，不能直接跳到 CODE。

## 3. Task9 六步逐项审查

| 获批步骤 | 独立核对与证据 | 判定 |
| --- | --- | --- |
| Step1 bounded/read-only API tests | 阅读全部 `test_promotion_ops_api.py`，实跑 Task9 68 + 既有 Ops 19；补写 7 个独立探测。精确四个 GET、405、bearer/loopback、422/404、strict response、keyset、脱敏与数据库只读均有行为证据。新增 F1 证明现有测试缺少回执时间 tie。 | 已交付，但 coverage 缺口被独立攻击揭示 |
| Step2 API RED | 独立解析冻结 RED 原始 XML/log：有效 fixture RED 75 tests / 56 failures / 19 pass；源码冻结前四个 endpoint 404 的断言失败可核对。初始 56 errors 的坏 fixture 和 zero-test wrong-path 不被视为有效 RED。未反向修改/检出旧源码重新跑 RED。 | provenance 核对通过，历史 RED 不冒充本轮重跑 |
| Step3 redacted projections + Run/Trace identity | 阅读 routes/contracts/queries；实测四维 gate binding、后续非 tie failed 覆盖 passed、数值 allowlist、闭合 labels、100 上限、READ ONLY 与 snapshot、旧 Run/真实 rollback、legacy NULL。F1 显示 gate “最新”语义不一致。 | **FAIL** |
| Step4 Policies view | 从源码、40 个独立重跑的 desktop/mobile 用例、真实 PG 生产页面和截图核对导航、filters、流量、hash、gates、health、audit、无 mutation 控件、table overflow。F1 的 API false-positive 被前端绿色渲染，实际可见。 | 结构/交互通过；gate 事实展示受 F1 阻塞 |
| Step5 backend/frontend verification | 本轮独立 PG/API 94 pass；Node20 实际 production `npm run build` pass；40 UI pass；真实 PG 页面 4 pass；攻击 API 1 fail，攻击 desktop/mobile 2 fail。全量 backend 1675 只独立核验冻结原始证据，没有声称重跑。 | 常规验证通过，但有效独立反例阻塞 |
| Step6 commit evidence surface | 独立复算冻结 HEAD、父提交、13 source SHA、47 evidence SHA、19 XML statistics，以及62 changed paths与allowlist完全一致。未自行 commit。commit message 内容对应 Ops evidence scope。 | 冻结/provenance 通过，不等于规格通过 |

## 4. 交接要求与 Design 不变量逐项证明

1. **精确四个 GET、复用 Ops auth、无写命令：通过。** `python/api/ops_routes.py:323-357` 四个 GET；router dependency `require_ops_access` 复用。独立重跑四条 route 的 POST/PUT/PATCH/DELETE 405、外网403、配置token后401/有效访问；command-service tripwire。`ops_queries.py:280-284` 显式 `REPEATABLE READ READ ONLY`。真实 `SHOW transaction_read_only=on`、DML `DELETE/INSERT ... WHERE false` 仍被PG拒绝。新增 concurrent append 探测证明同一查询事务看不到写事务的后续 append。

2. **排序、分页、参数、拒绝信息：通过。** `ops_queries.py:217-229,252-263,299-428` 三类 typed keyset；`ops_routes.py:297-320` 闭合参数、重复/空/未知拒绝，limit 1..100。三 endpoint 新增 109 条同时间记录，独立验证两页 `[100,9]`、无漏无重、UUID/hash反向排序；不存在过滤返回空page。既有独立重跑覆盖非法cursor/UUID、时区year0001/9999溢出422、缺detail404与拒绝不回显输入。此处 keyset tie 通过不证明 gate receipt tie，后者单列 F1。

3. **公开字段、bounded detail、gate事实：部分失败。** 合同 `ops_contracts.py` 与 `_deployment/_health_window` 包括 current deployment/version、state/traffic、12位list hash/64位detail hash、cohortcounts、冻结thresholds/hash、typedhealth及timeline。detail gates最多8，window最多1，audit最多100。109-event探测实际返回100；latestwindow为同时间最大hash。四维 policy/protocol/runtime/source mismatch 的较新pass均不会替代精确绑定回执；不同issued_at的较新failed正确展示。唯独同issued_at的latest排序在 F1 失败。

4. **严格与任意值脱敏：通过已执行范围。** 新 projections 没有 components、自由details、assignment salt、token/nonce、learner/requestID、prompt/modeloutput/raw namespace。`_health_stats` 逐字段数值校验，不做keyword黑名单。新增无敏感关键词的任意输入 `violet meadow 7391 <img onerror=alert(1)> 汉字 🧪` 注入 actor/reason/issuer/audit event label/threshold label/known metric field/extra JSON字段，四个响应均不泄露。未知event/threshold闭合为`redacted`，非法/NaN/Infinity/bool/dict数值变null，合法负relative rate与Decimal数值保留。Decimal wire values为既有协议的有限十进制字符串，count为JSON整数，不将自由文本当指标。

5. **immutable Run summary/detail/Trace：通过。** `_policy_identity`（`ops_queries.py:204-214`）直接读存储Run字段，不解析head；Run summary与Trace调用该函数。独立重跑生产head advance、历史NULL与真实rehearsal healthrollback测试；生产真实PG页面还验证old candidate Run仍显示旧fullhash/deployment与`candidate · rehearsal`，新Run显示rollback deployment、stable fullhash与`stable · rehearsal`。原始namespace不公开。RunsView table/drawer、TraceView实际可见且Policies链接可达。

6. **Policies布局/内容：通过结构要求，事实语义受F1阻塞。** 使用现有AntDesign table/tag/tooltip/timeline/Descriptions与既有lucide ShieldCheck/status icon习惯；并未要求替换既有icon library。environment/state filters、current/head relation、traffic、stable/candidate比较、gate receipt、health candidate/stable、rollback/freeze timeline均实际可见。actor/reason全redacted有说明，typed event/from/to/faileddeployment/window与thresholdfacts仍可关联。无 mutation 按钮，无 nested card。390px viewport表格 wheel水平滚动，body无额外横向溢出；哈希wrap可读。

7. **状态/分页/reset/stale/build/browser：通过已执行范围。** 完全隔离依赖副本后的40 UI用例覆盖loading/empty/error/retry/auth/token清理、list/detail staleabort、分页filterreset、strict frontend guard、NULL unavailable、detail empty证据；真实PG生产页面进一步覆盖50+7分页、filterreset第1页、production+canary空状态、status tooltip、真实health/audit、old/newRunlinks。实际Node v20.19.5、Vite7.3.7 build PASS。锁SHA `90dbc9aae2e41ba3fe968254330755f3e183959a735a64132ad7f3c9b2b55bb5` 与源码完全相同，无降级。新截图与放大gate详情均视觉检查。

8. **冻结证据真实性与非资格边界：通过。** 不以实现者报告或父侧声明替代证据。自行解析全部19 XML testcase与suite F/E/S，重新hash workingbytes及Gitblob。所有独立fixture仅用于工程回归；真实PG/HTTP/Chromium不代表真实模型、正式holdout、学生效果或Task10多进程演练。

## 5. 独立执行结果与可复现环境

- Python：primary `.venv/bin/python`，3.11.17；`PYTHONPATH=M3/python`、`TZ=UTC`、缓存前缀自有tmp。
- PG：16，`127.0.0.1:55432`。每个pytest invocation、每个live server lifecycle均唯一 `m3_t9_spec_*` 数据库，EXIT dropdb。
- Redis：测试配置为`127.0.0.1:56379/0`；Task9主要是PG只读查询。本轮没有把设置Redis URL说成独立多进程/Redis演练。
- Node：精确使用 `npm exec --yes --package=node@20.19.5 -- node ...`，自有npmcache；最终改为tmp实体依赖副本。源包/锁不变。
- 前端验证副本：`/tmp/m3-task9-spec-independent/frontend/`，源码/e2e原样复制；唯一验证配置差异为 Vite `cacheDir` 指向自有tmp。最终build的Ops JS/CSS content-hash文件名与初次build一致。
- live harness：`Starlette StaticFiles`提供实际production dist；mounted FastAPI Ops路由使用真实PG `OpsQueries`；不启动真实业务runtime/worker/model。健康窗口来自受控synthetic observations，通过真实 evaluator/rollback事务产生。

| 本轮原始 XML / log | Tests | Failures | Errors | Skip | 角色 |
| --- | ---: | ---: | ---: | ---: | --- |
| targeted-final.xml | 94 | 0 | 0 | 0 | Task9 68 +既有Ops19 +新增探测7 |
| gate-tie-final.xml | 1 | 1 | 0 | 0 | F1有效PG/API反例 |
| ui-isolated.xml | 40 | 0 | 0 | 0 | 完全tmp依赖后的desktop/mobile回归 |
| ui-live-isolated.xml | 6 | 2 | 0 | 0 | 真实PG生产页面4 pass + F1 desktop/mobile2 fail |
| build-isolated.log | 不适用 | 不适用 | 不适用 | 不适用 | 实际Node20 `tsc && vite build` PASS |

最终独立 SHA-256：

- `targeted-final.xml`: `25037b17fef7b0ca1f296459012b3db06f8df2adb045b0148a974e7815077926`
- `gate-tie-final.xml`: `bcf1e12164c0f407645ece8ef0224c11485c7a1ec68e4e45fa8dbd50538c3c25`
- `ui-isolated.xml`: `a24f35622097e06144d14c3b7359f5e04fc8f40f9e8facd9844f6938b6286e0f`
- `ui-live-isolated.xml`: `d428abe3043453361f6f01d8da5f3030da27be6772050b0e90a098b26632c066`
- `build-isolated.log`: `1d99950e7435e0bef9ece0ba5b7b0f317f270ed280bed224a048380e3b6358cb`

完整individual hashes：`/tmp/m3-task9-spec-independent/independent-manifest.json`。
解析程序：`provenance.py`（冻结47+13+19XML+62paths）、`summarize.py`（本轮XML/SHA）。

本轮最终命令（Python runner自行进入M3/python；前端命令cwd为tmp/frontend）：

```bash
bash /tmp/m3-task9-spec-independent/pytest.sh targeted-final \
  tests/distributed/test_promotion_ops_api.py tests/distributed/test_ops_api.py \
  /tmp/m3-task9-spec-independent/test_independent.py -q

env npm_config_cache=/tmp/m3-task9-spec-independent/npm-cache \
  npm exec --yes --package=node@20.19.5 -- node -e \
  'console.log("Node",process.version); const {spawnSync}=require("node:child_process"); const {dirname}=require("node:path"); const r=spawnSync("npm",["run","build"],{stdio:"inherit",env:{...process.env,PATH:dirname(process.execPath)+":"+process.env.PATH}});process.exit(r.status??1)' \
  > /tmp/m3-task9-spec-independent/build-isolated.log 2>&1

env npm_config_cache=/tmp/m3-task9-spec-independent/npm-cache \
  OPS_SCREENSHOT_DIR=/tmp/m3-task9-spec-independent/screenshots-isolated \
  PLAYWRIGHT_JUNIT_OUTPUT_FILE=/tmp/m3-task9-spec-independent/ui-isolated.xml \
  npm exec --yes --package=node@20.19.5 -- node node_modules/@playwright/test/cli.js \
  test e2e/ops.spec.ts --reporter=line,junit \
  --output=/tmp/m3-task9-spec-independent/playwright-isolated \
  > /tmp/m3-task9-spec-independent/ui-isolated.log 2>&1

# 独立terminal先运行服务；startup complete后再运行下面的Playwright命令。
env SPEC_GATE_TIE=1 bash /tmp/m3-task9-spec-independent/live.sh isolated

env npm_config_cache=/tmp/m3-task9-spec-independent/npm-cache \
  PLAYWRIGHT_JUNIT_OUTPUT_FILE=/tmp/m3-task9-spec-independent/ui-live-isolated.xml \
  npm exec --yes --package=node@20.19.5 -- node node_modules/@playwright/test/cli.js \
  test --config=playwright.live.config.ts --reporter=line,junit \
  --output=/tmp/m3-task9-spec-independent/playwright-live-isolated \
  > /tmp/m3-task9-spec-independent/ui-live-isolated.log 2>&1
```

再次复现时先恢复自有tmp依赖：`rsync -a --exclude=.vite-temp --exclude=.vite M3/frontend/node_modules/ /tmp/m3-task9-spec-independent/frontend/node_modules/`。这里`M3`仅为工作树绝对路径的缩写，不要创建原依赖的符号链接；运行live.sh后用其日志里的自有Python PID执行TERM，EXIT trap会drop该数据库。原runner的frozen evidence路径没有被使用。

保留而不包装成产品失败的历史attempt：

- `targeted.xml`：94 tests，4 failures。独立探测fixture复用了 `uq_policy_gate_evidence` 的evidencehash，修正自有fixture后94全通过，不归咎产品。
- `gate-tie.xml`：1 launch failure。单独外部test路径未自动加载M3 pyproject的asyncio设置；显式 `-c pyproject.toml` 后获得F1有效assertion failure。该坏启动不算规格反例。
- `ui.xml`40pass、`ui-live.xml`4pass、`ui-gate-tie.xml`2fail为初轮；完全tmp依赖后的最终重跑结论相同，报告以isolated产物为主要前端证据。

## 6. 冻结材料独立核验

复算而非转述：

- source files 13，combined SHA `67581927eea462b0c8ce36ef495b84d3211d7f11d62980d16d71315f90616810`。
- retained evidence files 47，combined SHA `432b7da2ddf1a45af5003e70e716066ac98db52d694ea972bb9558aa96e8b62b`。
- sorted compact ASCII JSON算法与manifest一致；每个working SHA与HEAD Gitblob SHA一致。
- 加manifest与实现报告，62 changed paths与实际commit path set完全一致。
- 19份原始XML全部suitecounts、testcasecounts、failure/error/skip子节点与manifest一致。
- frozen final backend1675/F0/E0/S0，API87/F0/E0/S0，desktop/mobile40/F0/E0/S0。
- frozen final XML SHA分别：
  `a5a99c8991698c92f1fb0a20987b003eafcd65350038460831bfaf4192828db8`、
  `da238bf77a61cad579a7926efb02e96f1aa7365f994c9764c479d62fba894433`、
  `3f8a12fce1cacf69b27ba8670e79295761d93c6da20daec02739402b336a1f03`。
- 原始RED/failedattempts保持原bytes；没有格式化冻结日志/XML。
- provenance成功只能证明材料身份/计数，不推导SPEC PASS。

## 7. 未执行范围、隔离例外与清理

未执行：

- 未独立重跑全1675backend，已独立逐XML/SHA核对，并重跑所有Task9/Ops API与独立攻击；不把实现者full命令认领成本轮命令。
- 未复跑历史RED的旧源码，不checkout、不更改冻结工作树。
- 未进行Task10真实PG+Redis多进程driver/worker rehearsal、Docker/CI、正式campaign/model qualification、Agent50语义审核、真实学生效果检验。
- 对新响应进行了明确任意载荷/数值攻击，不宣称覆盖所有数据库损坏、所有遗留Ops自由字段或所有网络故障。
- 保留既有shared frontend chunk-size warning；没有升级依赖或认领依赖安全资格。

隔离例外（明确披露）：

- 初次frontend副本把`node_modules`链接到M3已有依赖。虽手动设置Vite cacheDir在tmp，Vite默认config bundle仍经该链接写入/删除了M3已有ignored `frontend/node_modules/.vite-temp` 的临时文件，目录mtime更新到11月2日05:15，最终目录为空。
- 这是“所有cache应在自有tmp”约束的执行例外，不能隐瞒。没有保留源码、锁文件、frozen evidence内容变化，tracked Git/index状态一直clean；primary没有此操作。
- 发现后只unlink自有tmp链接，将依赖复制为自有tmp实体目录；重跑actualbuild、40UI、真实PG6UI，全部缓存输出留tmp，F1仍复现。没有为了恢复mtime再写原目录，也没有删除原依赖/缓存。

清理结果：

- 三个live server进程均已停止，其退出143来自审查者主动TERM，不是功能测试失败。
- 每次pytest/live数据库EXIT dropdb。PG最终独立查询 `SELECT count(*) ... datname LIKE 'm3_t9_spec_%'` 为 **0**。
- 最终3000/3001无listener。未停止共享PG/Redis服务，未做Redis flush或全局清理。
- 自有npmcache、pycache、pytestcache、vitecache、实体依赖副本、build dist已移除；保留必要原始XML/log/screenshot/failed trace、复现代码与fixtureJSON供父侧归档。所有保留文件位于自有tmp。
- M3 `git diff --exit-code HEAD -- python frontend docs/superpowers/reports/task9-ops-evidence`为0；primary/M3最终tracked状态clean，HEAD均未变。

## 8. 给父侧的终态交接

**SPEC FAIL，唯一阻塞发现 F1/P2。** 本报告和独立原始证据已经写盘，不依赖最后消息是否送达。

父侧可以据此安排窄范围实现修复与重新冻结；随后fresh全Task9 SPEC。只有该轮SPEC PASS后才freshCODE。本审查没有写修复、没有开启CODE、没有启动Task10，也不把Task9/M3标为已接受。
