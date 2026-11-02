# WHOLE Task9 独立规格复审

**结论：WHOLESPECPASS。本轮未确认阻断规格缺陷。**
该结论仅交父侧核验、归档，不授予 Task9 最终验收，不启动 WHOLE CODE、
Task10、Agent50 或模型评测。父侧 PASS 归档之后才可另启 fresh WHOLE CODE。
工程开发回归证据标为 `validation_required`，不授予正式发布资格或教育安全证明。

## 1. 身份与完整范围

- 独立角色：fresh WHOLE SPEC reviewer，非实现者、父侧 provenance reviewer 或 CODE reviewer。
- 唯一目标树 R：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- branch：`feature/m3-trusted-policy-promotion`；actual clean HEAD：
  `a6500f5a4fb8ce1494742735655841230b6124fe`。
- parent / product：`d77299c710a4d330539010d9067c5b4938f4adf1`；
  product parent：`6147cec5bff26d60a3422b0f43f133b2db782e8f`。
- WHOLE 范围：Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f`
  至 actual freeze 的全部 Task9，包括初实现、F1、C1、S1–S3、S1-R、恢复轮和 SPEC-1。
- 自有 E：`/tmp/m3-task9-wholespec-90d3cbd2-0290-48f8-aba7-530548519b0e`。
- 全部 355 Python/frontend source/tests SHA256：
  `7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc`。
  算法为全部 tracked Python/frontend 路径及新增源路径的 SHA256，
  排序 `(relative_path, sha256)` 对的 compact ASCII JSON 再 SHA256。
- primary HEAD 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`；
  266 source SHA 保持
  `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。

完整读取新 brief、旧 complete-chain scope、修复 brief/result、批准 design 475 行、
plan 1448 行及完整 Task9 六步；完整读取实际实现报告、F1/C1/S1–S3/S1-R/
minimum 失败报告和原证据。不是只审七行下限补丁，不套旧 ed42/354 身份。

WHOLE 改动的 17 个源/测试路径全部核验：

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
python/tests/distributed/test_ops_complete_chain.py
python/tests/distributed/test_ops_health_binding.py
python/tests/distributed/test_ops_minimum_evidence.py
python/tests/distributed/test_ops_source_integrity.py
python/tests/distributed/test_promotion_ops_api.py
```

原 runner 只用于参考；复制到 E 后重新绑定 ROOT/HEAD、三独占 free ports、
UUID DB、记录位置和缓存。`runner-rebinding.json` 留全部差异。
未直接运行旧 fixed OWN 或会覆盖 golden 的脚本，没有 baseline tar/replay。
`prepare.py` 的旧 354/main 假设未调用；仅使用已核对的只读函数。

## 2. 本轮重点的 Actual / Expected

下列均为本人新 UUID PG、真实 migration/immutable triggers、完整 GET 的实际运行，
不是复述实现方绿色结果。`E/minimum/` 和 `E/api-final/` 保存逐项响应和 authority 对照。

| 条件 | Expected | 本人 Actual | 判定 |
| --- | --- | --- | --- |
| Canary 0/0、19/20、20/19 passed leaf | 不认证本地 Canary；Active 整条 consumed 链不可用 | authority 拒绝；完整 GET 无 Canary source；Active 无任何健康消费来源 | PASS |
| 同上 Canary 的独立合法 Shadow 前序 | 不因后续坏 Canary 删除独立合法 Shadow | Canary GET 仍保留独立 Shadow passed/consumed_chain | PASS |
| Shadow 0/0、19/20、20/19 passed leaf | 两个冻结下限都必须满足 | authority 拒绝；本地 Shadow 不认证 passed source | PASS |
| 默认 20/20 | 两来源合法时不得全删求绿 | authority 接受；合法 Active 保留 Canary/Shadow 两条精确来源 | PASS |
| 冻结下限 22/23，实际 20/23、22/20 | 不能使用全局 20 替代冻结下限 | local Canary 不认证，Active 整链为空；独立 Shadow 保留 | PASS |
| 冻结下限 22/23，实际 22/23 | 边界接受 | authority 接受；local 与 Active 完整 GET 来源正确 | PASS |
| local 1/1 failed/unknown，window hold/fail | 低样本非通过证据仍可展示，不当 pass | 精确 receipt、local、sample_count=1、原非通过状态/窗口保留 | PASS |
| 21/21 Decimal 对照 | 收据费用等于冻结 observation 精确总和，不用 rounded mean×count | 两状态精确求和通过，实际总和与 rounded 对照不同 | PASS |
| Active local 后续基线 | 仅使用已消费 Canary 冻结 stable keys，不漂移到新 Canary leaf | local Active 精确窗口/部署保持；Shadow receipt 不变；冻结 keys 一致 | PASS |
| 精确被引用 Canary 的 count/cost/status/身份/window/time/key poison | 无效 leaf 使其依赖的 Active 整链断开，不能留下更早 Shadow 绿证据 | 原 47+17 和 repo 完整 GET 47 全部通过；合法独立 Canary/Shadow 历史对照仍保留 | PASS |

下限产品定位：`R/python/core/distributed/ops_queries.py:525-597`；
新 24 项完整 GET：`test_ops_minimum_evidence.py:121-279`。
原 minimum 4 项的 local 断言按 `canary_health` gate-specific 修正后执行；
原把独立 Shadow 一并计入的过宽断言不是验收依据，未删除历史原件。
Active 攻击为 append-only fixture，不是实际 PromotionCommand 晋级成功，
不据此声明已证明或修复发布权限绕过。

## 3. WHOLE 规格矩阵

批准 design 的 receipt identity / immutable deployment / 缺失不通过 /
query-command 分离不变量及 plan `:1158-1252` 六步为依据。
下表 file:line 均针对 actual freeze；完整节点、模块计数和符号范围在
`E/independent-execution-audit.json`。

| # | 完整规格 | 本人判定与主要证据 |
| --- | --- | --- |
| 1 | 精确四 GET、复用 Ops bearer/loopback、无 mutation、非回显 422/404/503 | PASS；`ops_routes.py` 全文；`test_promotion_ops_api.py:145-208,329-363`、`test_ops_api.py:645-704`；API315 实际运行，外部无 token 403、错 token 401、有效 token可读及四方法405。 |
| 2 | 三列表 typed keyset、limit 1..100、同时间无漏重、query allowlist/duplicate/empty/date overflow、有界 detail/audit | PASS；`ops_queries.py:219-263,301-380,733-782`；原 keyset 和自有 `test_extra_code.py` 三列表113行100+13、末页无 cursor、audit100、window tiebreak 实际断言通过。 |
| 3 | closed DTO/TS、UUID/hash/Decimal/numeric allowlist、unknown 不补零、privacy | PASS；`ops_contracts.py`、`api.ts` 全文；`test_promotion_ops_api.py:210-256,486-520`、自有 numeric 攻击及 UI strict guards；raw details/components、actor/reason/issuer原文、salt/token/nonce、learner/request/prompt/output/raw namespace不投影。 |
| 4 | F1 资格 gate 四维、issued/created/id 三键、failed/unknown 遮蔽、later pass 恢复 | PASS；`ops_queries.py:330-380`；`test_promotion_ops_api.py:258-326` 九项在本人 full/API 都实际通过；私有 helper 的 future-issued 边界未扩大成完整发布资格证明。 |
| 5 | REPEATABLE READ READ ONLY、GET 无写、无 command/evaluator/qualification replay、有界 SQL | PASS；`ops_queries.py:283-287,525-597`；`test_promotion_ops_api.py:364-398` 与自有 concurrent append/真实 DELETE 拒绝，SHOW read_only=on、repeatable read；冻结 observation 仅精确 IN keys + LIMIT，最多2×window_max_runs。 |
| 6 | C1 同 artifact 当前B/hold不借A、历史A不被B替换、local窗口/部署精确绑定 | PASS；`test_ops_health_binding.py:51-75,94-151`；本人 API/完整backend和 production current/history 各双视口通过；原 receipt/window/deployment identity 精确保留。 |
| 7 | S1 全 canonical 8 fields、两段 audit/approval/required/issuer/model/role/time、S2 latest遮蔽/other-command/cutoff | PASS；`ops_queries.py:599-731`；原47+17、`test_ops_source_integrity.py:99-176` 和 API315完整矩阵；两个 malformed production 均无 consumed source；错误相同声明不能代替实际命令hash，合法链仍两条来源。 |
| 8 | S3 精确leaf四维/版本/阈值/window/stats/cohort/key identity/time/count/cost、S1-R断链传播、SPEC-1冻结下限 | PASS；`ops_queries.py:425-597,717-731`；完整链111、minimum28；latest invalid不借旧pass，精确被引用Canary经相同有界校验后才允许依赖链，独立合法历史和local非pass不删。 |
| 9 | Run summary/detail/Trace immutable stored deployment/hash/cohort/namespace class，legacy NULL | PASS；`ops_queries.py:206-217,929-1003,1297-1338`；`test_promotion_ops_api.py:401-467` 真实head advance及health rollback；`RunsView.tsx`/`TraceView.tsx` 全文；UI绑定/旧NULL对照及两视口Trace实际检查。 |
| 10 | auth/loading/empty/error/retry/abort/dispose/reset/stale response、Policies阈值/状态/tooltip/metrics/timeline、mobile真横滚/无写控件 | PASS；`PoliciesView.tsx`/`OpsApp.tsx` 全文；`ops.spec.ts:503-754`，本人UI54及visual4；七production双视口正确性14，console/pageerror0、document overflow<=1、移动表格真实wheel横滚。 |
| 11 | 完整独立矩阵、源码/原raw身份、成本角色、只读资源隔离、未执行范围 | PASS（本轮工程流程）；本人1864/315/111/28/UI54/build/PG14；355source及4419 M3 tracked blobs首尾actual一致，primary/index/.venv/sourcecache未改；零模型、unknown HTTP总数，不自行验收。 |

全部六步：Step1 有界只读测试 PASS；Step2 历史有效 RED 留档/provenance PASS
（没有重写历史源再跑 RED）；Step3 完整可信投影 PASS；
Step4 Policies 页面 PASS；Step5 本人全矩阵和真实生产正确性 PASS；
Step6 已冻结 evidence surface 的 provenance PASS（本 reviewer 未 commit/push）。

## 4. 本人实际运行矩阵

T/P/F/E/S 来自原 XML testcase 子节点，不按 exit0推断。
完整 backend 与 API、完整链、minimum 有重叠，**不得相加为独立样本数**。
suite 秒不等于 wall clock；并行运行的调度、migration和清理时间另在UTC记录。

| 原 XML stem | T/P/F/E/S | suite秒 | SHA256 |
| --- | --- | --- | --- |
| full-final | 1864/1864/0/0/0 | 402.568 | 8d7237463085de6afe131810d567d27fe4ed4da8a30e2b91d5828bb662be2a43 |
| api-final | 315/315/0/0/0 | 93.740 | 47a89df76d499cdb59bf714280dc9565962732ef31284c2b75d69d50eb47a140 |
| integrity-complete | 111/111/0/0/0 | 73.935 | 4fd255d8b37be7caf9e38eea6b7d09d69b499ba69f850249485aa5291fe68baa |
| minimum | 28/28/0/0/0 | 37.578 | e3c390e70b6eea59c7ecc7cc07b03a00443e8708a3ce24c89b366f405654d319 |
| ui54 | 54/54/0/0/0 | 36.153 | e85d755fa84f19fa0174898d58e69623caa065791210300d8deb8773e06db7d0 |
| ui-visual4 | 4/4/0/0/0 | 6.391 | f2dfd6c7e0d08407cd86cd8f0923486ab9ff55e1680d6c5efdb6270260255609 |
| prod-final-current | 2/2/0/0/0 | 1.135 | d537c6f0f656d27e9431451634a40357499794ddc7d443f792bb0fa712418447 |
| prod-final-history | 2/2/0/0/0 | 1.446 | cdf5fd2d7be06d06d6e2e2ee3433323573b644159b5a38e6d3b7bfd1511816ed |
| prod-final-approval-malformed | 2/2/0/0/0 | 1.194 | 29d2b8be0ab3304821133d9cd4975b2f75f31456707e1ceeb941f4e027243084 |
| prod-final-genuine-malformed | 2/2/0/0/0 | 1.221 | 2ed632dcb72ddef3235a27a0a74a6d59f4b11ad88a2c4d137c102f80f212666b |
| prod-final-genuine-valid | 2/2/0/0/0 | 1.424 | 96ce17408c4d6b5cabf7112bb0c3a9608c306189f19dcff0063056114f95814e |
| prod-final-referenced-poison | 2/2/0/0/0 | 1.271 | 5907a7230501546c11126089d9035989404188e6083c712ba1f59a1e72105af5 |
| prod-final-minimum-zero | 2/2/0/0/0 | 1.295 | b4f36e68755e34fd3b3f3845a09a14fe965efe74761e590bad5d33737966a7e6 |

111 = 自有原 independent47 + metadata17 + repo完整GET47；
28 = gate-specific原minimum4 + 新完整GET24。
API315包含全部相关Ops六测试模块和原relations/corroboration/code/extra探测；
完整模块计数和每个node在 `independent-execution-audit.json.xml`，不省略成API291。
全部1864后端node均有真实XML，包括现有integration/failover；运行单测不等于
启动live Agent50或完成Task10多worker演练。

实际 Node20.19.5 `npm run build`（tsc + Vite7.3.7）exit0；
`node20-build.log` 原 >500kB chunk warning保留，不包装为错误或安全资格。
UI54 Playwright墙钟20.0秒；visual4墙钟4.1秒；36.153/6.391为双suite汇总。
Python3.11.17、共享PG16.15，runtime未安装或升级；
独立读取58 installed distributions、39声明约束全部匹配，`pip check` exit0。
`dependencies-independent.json` 保留具体版本、约束及该检查前后runtime元数据相等。

主要实际 UTC：

```text
full-final: 2026-11-02T04:38:47.816061+00:00 → 04:49:58.436823+00:00
api-final:  2026-11-02T04:48:29.453720+00:00 → 04:50:09.060121+00:00
integrity:  2026-11-02T04:38:47.816082+00:00 → 04:44:18.270743+00:00
minimum:    2026-11-02T04:38:47.816083+00:00 → 04:43:42.137465+00:00
build:      2026-11-02T04:36:43.413305+00:00 → 04:38:54.865834+00:00
production child commands: 2026-11-02T04:51:20.100127+00:00 至 04:53:08.096071+00:00
```

14执行的 exact command arrays、cwd、UTC/start/end、exit，
四pytest UUIDDB/drop和七production lifecycle/PID/drop均在原 `*-command.json`/
`*-lifecycle.json`。这些是已执行记录，不可直接复用固定labels覆盖原件。
复现入口为 E 的 `review.py` / `frontend_run.py`，须另建UUID目录并重新绑定。

## 5. Production、HTTP与截图

七场景逐个新建UUID DB、运行真实PG migration/fixture/health事务，
从本人 Node20构建dist经Starlette提供静态资源和真实FastAPI OpsQueries。
没有route mocks、Vite dev、业务worker或外部模型调用。
desktop 1440×900、mobile390×844，正确性全部14PASS。

本人实际 `view_image` 读取14张production详情关键图和Policies/Trace双视口4张，
共18张，逐图路径/SHA在 `independent-execution-audit.json.actual_visual_inspections`。
合法链可见两个精确来源版本/window；两个malformed、poison和minimumzero均
没有绿色健康消费来源。原始approval/资格passed可显示为历史原始证据，
不能因此解释为健康消费通过或发布资格。

本人production页面监听84 GET；完整production trace network142 GET；
42个实际CSS/JS响应正文与本轮retained dist逐字节相等。三组统计有重叠，
不是HTTP总量。导航JS部分响应不留body，但同trace request-context GET
留齐每个资产真实bytes；未把没有正文的响应当成功byte检查。
`production-*.json` 另留bytes/hash、实际请求、viewport、scroll状态；
每个trace与资产正文再次由独立审计复核，GET-only、console/pageerror0。
readiness重试、全部backend in-process/API和mock HTTP总量未统一计量，记unknown。

宽表为容器内真实横滚，document overflow<=1。`scrollBefore` 是显式wheel前，
但在 source.scrollIntoView 之后，不声称页面最初scrollLeft=0。
mobile left截图可能已有局部横滚，不单凭截图证明全部列同时可见。
desktop详情截图的sticky header局部遮行是取景状态，不据此编造新产品缺陷。

先保留本人实际六个dist文件原bytes于 `E/retained-http-dist/` 后才清理dist。
Ops JS SHA：`a4430d560a4461a12441b5433d72592db328646e28057a6426ecdef36a13e416`；
CSS SHA：`4f3070753582aa2f0a5e82bd28b182212feeb9724a92bf7aee5ae14a2a0c75e6`。
本人72 trace ZIP全部CRC通过、2615 members完整读取/hash；
`.trace/.network` 每行JSON事件完整解析，不以截图生成代替视觉检查。

## 6. 旧证据、失败与来源身份

本人独立读取/hash/实际Gitblob核验全部3201 Task9历史文件；
167 XML逐testcase/failure/error/skip解析，370 ZIP全CRC/member/hash和事件解析。
原JSON全文、JSONL全行、文本全文读取。历史视觉图片字节核验不冒称本人重看每张图。
完整索引：`historical-and-recovery-raw-audit.json`。

| 归档 | 本人复算数量 | manifest SHA | payload SHA |
| --- | --- | --- | --- |
| 最新 minimum-fix | 570 raw | daeaf5ae1953363ec9027082b3e0bd70bb2d712d16f14499049f4b7ad4103d19 | a0f174383667b0ccdc56c174e28d5e0f8acf0c4b07006abcc872c46449ae6d9b |
| 原 minimum SPEC FAIL | 466 raw | 04952f15c0258d545dca305c6b14ca4a68fcaefd32257a3ace8389e95f7e2344 | 69900312b69b41ebd5694890112f0eef180cf634d3d81c6eca5a7dd0036e41a6 |

新report SHA：`3610b6c2f13d80144ea77774f25636dc3b4b93969de3c0a599e408d0b2012446`；
原FAIL report SHA：`1477affb6fb21ec9be96354c1d44178bca21cca5cb3f714fa8314040a97fd6f8`。
每个映射文件与actualfreeze Gitblob一致，实施tmp/result与repo报告同字节。
父侧4419blob/17XML/23pair/72ZIP/30DB/traceasset等只作为其provenance参考，
没有冒称本人的运行；本人的独立结果是本报告第4、5、7节。

历史分类不改：
初始坏fixture/0收集、F1 future-helper错误假设、C1 guard/immutable fixture/
selector/冷启动，S1–S3 setup/async/序列化、67项夹具中间失败，
恢复轮中断unknown、丢失tmp、无效tar/navigation-body假设均保留。
本轮实施 red-new-get24=12PASS/12FAIL含1无效UUIDfixture；
correctedRED24=13PASS/11有效FAIL；不把无效项计成产品RED。
原F1/C1/S1–S3/S1-R/SPEC-1有效失败的闭合依据是本人新运行，
不是将旧FAIL改写成PASS。未知旧请求/时间/费用未补造。

本人测试/production无失败或无效fixture尝试；辅助扩展secret扫描曾exit1，
全文错误及只读诊断保存在 `E/secret-scan-invalid-attempt.md`。
原因是旧历史扫描器源码 `parent-retain.py:88-89` 的两条PEM头bytes断言匹配模式，
并非private key body；实际两项distinct本地secret值匹配0。
修正后只对这个actualGitblob相等的文件、两条精确assert源码进行明确分类，
不放宽其他路径、真实secret值或ZIP成员扫描。raw pattern literal hits=2，
不是把原始模式命中改称0；真实secret/high-confidence key material匹配0。
该辅助失败不是产品规格反例，也不冒称首次scan成功。
正常hook的hardcoded扫描超时不能认完整hook通过；本reviewer不commit或运行hook。

## 7. 隔离、清理与限制

14个执行的28份before/after完整快照每组相同；另有evidence-audit与cleanup快照。
每次核对两树tracked/source/HEAD/status/index hash+mtime/.venv/sourceVitecache；
最终源全集与起点全相等，并重算4419 M3 tracked Gitblobs与primary全部tracked。
`final-source-gitblob.json` 留最终实际snapshot和逐源/原始文件摘要。
实体node_modules copy，所有内部symlink解析在E内，不链接回source。
仅自有执行config/cache/端口和production evidence spec作记录增强，源tests/e2e未改。

清理实际UTC `2026-11-02T04:57:43.377885+00:00 → 04:57:57.981041+00:00`：

- 本人11 exact UUID DB全部finally drop0、实际无余；另核对原30 exact UUID DB无余。
  不对他人DB执行drop，不停共享PG。
- 自有Redis50864/PID70611，shutdown前核对PID/run_id/dir/save/appendonly全同起点；
  nonpersistent，save空、appendonly=no，identitychecked `SHUTDOWN NOSAVE`。
- 自有ledger1017条、428次exact UUID DEL/UNLINK；无FLUSH、无prefix DEL。
  subprocess worker有12个未计量余key，未宽删；不声称key账本完整，
  仅随已确认本人的nonpersistent实例关闭结束。
- 50864/50865/50866全部connect_ex=61关闭。本人node_modules/dist/cache/tmp/
  npm/Vite/__pycache__已清；retained dist/raw/screenshots/traces/scripts保留。
- 共享PG16.15/127.0.0.1:57432/postgres/PID16852、指定data dir和patched runtime保留，
  两树source/tests/index/.venv及源Vitecache未写。

实际模型请求0、模型费用USD0；fixture model_calls/cost不是实际计费。
Docker二进制不可用、真实CI未跑，不安装或认绿。正式v3资格缺口、
多租户/真实生产部署、学生效果、正式holdout、live Agent50、Task10、
跨浏览器/真实手机、WHOLE CODE均未执行，不授予这些层面的证明。

## 8. 终态交接

**WHOLESPECPASS；无已确认P0/P1/P2阻断规格发现。**
本报告先完整落盘 `/tmp/m3-task9-minimum-spec-result.md`，
并在E保留同字节 `review-result.md`、全部本人新raw和非循环 `retained-manifest.json`。
最终secret扫描、报告同字节、payload/hash/manifest及冻结source首尾核验通过后通知父侧。
父侧核验并归档PASS后才可新启fresh WHOLE CODE，本reviewer不自行启动或授予最终验收。
