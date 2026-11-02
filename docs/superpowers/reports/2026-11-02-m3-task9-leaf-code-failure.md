# Task9 独立 WHOLE CODE 审查

**结论：WHOLECODEFAIL。发现 1 个 P1 阻断本次 Task9 代码审查的问题，置信度 10/10。**
这是独立 CODE reviewer 的结果，不是实施或 SPEC 结论，不授予 Task9 最终验收。
常规绿色回归和已归档 SPEC PASS 不能抵消本人有效反例。只读两产品树，
未写产品代码、commit、push、外发评论或启动后续任务。

## 1. 缺陷

### [P1] 冻结叶子的真实性校验不完整，错误认证 local 及 Active 消费链

- 主要位置：`python/core/distributed/ops_queries.py:583-596`。
- 完整逻辑位置：`:525-597`；来源投影 `:483-521`；Active 依赖传播 `:724-731`。
- 类型：业务语义问题。条件性确定缺陷，置信度 10/10。
- 不是已证明的 PromotionCommand 晋级绕过，不扩大为公网越权或模型安全证明。

`_frozen_summary_matches` 校验 key 格式、存在性、计数、排序、部分身份和 Decimal
费用，但没有验证 observation key 的 canonical 身份、Canary rehearsal/operation
同分布与非 production namespace、Shadow 同 parent pairing、window start/end key
及 passed window 的空 triggered_thresholds。两份声明和哈希相等不证明底层样本合法。
`_consumed_canary` 复用这段不足的叶校验，因此会连带认证整个 Active 消费链。

权威只读 helper `promotion_repository.py:651-759` 会拒绝同一批证据：
canonical key 在 `:734-735`，Shadow pairing 在 `:741-743`，同分布/namespace 在
`:744-747`，start/end 在 `:707-708`，passed triggered 阈值在 `:679-680`。
这是已有明确契约，不依赖外部服务假设。

**本人有效复现：**新 UUID PostgreSQL，真实 migration、FK 和 append-only triggers。
保留全部原合法 observation/window/receipt；新增一条具有真实 FK Run 的 observation，
保持样本数、cost、排序和指标，按替换后的 keys 重算 window_id 和 receipt evidence_hash，
追加更晚的 receipt。完整 HTTP GET 必须返回 200。每个攻击先断言权威 helper 拒绝，
然后对实际 DTO 做拒绝断言；没有依靠失败的 setup、关 trigger、immutable UPDATE、
重复 observation key 或不合法 FK 求 FAIL。

| 新 leaf 变体 | 权威 Actual | 完整 local GET Actual | Expected / 判定 |
| --- | --- | --- | --- |
| Canary canonical key 不符 | 拒绝 | canary_health passed/local | 不认证该叶子；FAIL |
| Shadow canonical key 不符 | 拒绝 | shadow_health passed/local | 不认证该叶子；FAIL |
| Canary namespace=production | 拒绝 | canary_health passed/local | 不认证该叶子；FAIL |
| Canary rehearsal_id 不同分布 | 拒绝 | canary_health passed/local | 不认证该叶子；FAIL |
| Shadow candidate/stable 不同 parent | 拒绝 | shadow_health passed/local | 不认证该叶子；FAIL |
| Canary window start_key 不符 | 拒绝 | canary_health passed/local | 不认证该叶子；FAIL |
| Canary pass 却有 triggered_thresholds | 拒绝 | canary_health passed/local | 不认证该叶子；FAIL |
| 合法替换 Canary / Shadow | 接受 | 各自合法 passed/local | 保留来源；2 项 PASS |

第一轮 local 断言失败后的 Active 尾断言未执行，不能冒称它已覆盖 Active。
因此另跑独立 `test_fresh_active_leaf.py`：上述 5 个 Canary 变体分别断言 Active
整链必须为空，实际全部返回 `canary_health` 和 `shadow_health` 两条 passed/
consumed_chain，5 个有效 FAIL；合法精确 leaf 对照保留双来源，1 PASS。
这五项是同类输入的新调用，不与第一轮相加为十二种独立反例。
Canary 本地仍可保留独立合法 Shadow 历史；Expected 没有要求删除它。

可核对实例 `fresh-active/active-noncanonical_key.json`：
receipt `8b14cc81-a8f7-4746-b9e7-3bf8310a4139`，
window `9b4005130b03b716b08dc5a38e33f4f117bf57aae17946dcdd62b822fa5500c8`，
stored key `d0cf04b4e344be99c2753e2dbd986152a27b1e827f047fedfdc5442fd7ae1d9e`，
expected canonical key
`d2955bae128296691126d0ec7d57c56bd123c1c1302c9abe5a34a87fc1bed0fa`。
同一份 raw 保留权威拒绝、本地和 Active 的精确 GET 响应。

问题代码：

```python
if (
    row.deployment_id != source.deployment_id or row.cohort != cohort
    or row.policy_hash != policy or row.metric_contract_version != 1
    or not source.created_at <= row.observed_at <= window.evaluated_at
    or row.created_at > window.evaluated_at
    or not isinstance(row.cost, Decimal) or not row.cost.is_finite() or row.cost < 0
):
    return False
```

建议：补齐有界、纯读的冻结证据身份和集合关系谓词，最好与权威校验共用可读验证组件；
精确 Canary 叶失败后整条 Active 依赖链不可认证。不调用 command、不重放无界 evaluator，
不以删前端行、借另一个合法 leaf 或删除独立合法历史代替修复。
新增上述完整 GET 反例与合法对照回归。本人没有实施该建议。

## 2. 冻结身份与完整范围

- R：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- actual clean CODEHEAD：`c52aaababba238ec26282f8c560c8f565a60a09e`。
- parent：`a6500f5a4fb8ce1494742735655841230b6124fe`；产品：
  `d77299c710a4d330539010d9067c5b4938f4adf1`。
- WHOLE：Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f` 至 actual CODEHEAD，
  包括全部初实现、F1/C1/S1-S3/S1-R/恢复/冻结下限修复，不是最后 docs 或 minimum patch。
- 自有 E：`/tmp/m3-task9-wholecode-40baa8dc-0414-46d1-b816-90149468b042`。
- 355 源/测试全集 SHA256：
  `7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc`。
- primary clean HEAD：`2ff803c968d64741d149e5a1ce88a823d4d32422`；
  266 source SHA：
  `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。

完整读取三指定 brief 及 complete-chain SPEC scope、批准 design 475 行和 plan 1448 行，
包括 Task9 六步，实际实现、新 SPEC 和历史失败报告；完整阅读 WHOLE 改动的 17 源/测试路径
及依赖契约，不借实施/SPEC/父侧运行作为本人验收。源码 WHOLE +3602/-20，
完整 Git diff 留 `whole-task9-source.diff`。文档/raw 大范围另分组审查。
bits-code-guard 在当前无 subagent 能力的环境按四组本地执行，做跨组 DTO/调用链核对；
JSON/Markdown/HTML 结果保留自有 E，不发送外部评论。

源路径：前端 `e2e/ops.spec.ts`、OpsApp/PoliciesView/RunsView/TraceView、
api/types/ops.css；后端 ops_routes/ops_contracts/ops_queries；
test_ops_api、test_promotion_ops_api、test_ops_health_binding、
test_ops_source_integrity、test_ops_complete_chain、test_ops_minimum_evidence。
具体路径和逐文件 blob/SHA 在初末快照与独立执行审计中。

## 3. 本人 WHOLE 矩阵

下列 PASS 仅表示列出的工程回归实际通过，不是正式 release、学生效果或无其他缺陷证明。

| 项目 | 本人检查与 Actual | 判定 |
| --- | --- | --- |
| 四 GET/auth/query/错误 | 只读路由、复用 bearer/loopback、query allowlist/duplicate/empty/date/UUID、422/404/503；API315 实际运行 | 已执行范围 PASS |
| keyset/bounded SQL | limit1..100，三列表113条100+13，同时间 tie 无漏重，audit100，窗口 tie；完整代码/自有 extra 探测 | 已执行范围 PASS |
| DTO/numeric/privacy | closed Python/TS，Decimal/unknown/null、递归 redaction、禁止 raw details/components/token/student payload；API315/UI54 | 已执行范围 PASS |
| RR READ ONLY | 真实事务 SHOW、并发 append 快照和写拒绝；冻结 exact IN keys+LIMIT，无 query 调 command | 已执行范围 PASS |
| F1 四维排序遮蔽 | policy/protocol/runtime/source 与 issued/created/id；failed/unknown 遮蔽和 later pass 恢复，九条回归 | 已执行范围 PASS |
| C1 当前/历史绑定 | 同 artifact 两部署，不借 A 认证 B/hold，历史 A 不漂移；真实 PG current/history 双视口 | 已执行范围 PASS |
| canonical8fields/approval/latest | 精确 command/audit/required/actor/reason/time；最新坏审批、other-command/cutoff，原47+17+47 | 已执行范围 PASS |
| 冻结 minimum/精确 receipt/Decimal | 0/0、19/20、20/19、20/20，22/23 自定义边界、21/21 精确成本、Active 基线与不替换 exact leaf；minimum28 | 已执行范围 PASS |
| 叶子真实性/Active 依赖传播 | 新 7 种有效 local 反例；另 5 项 Canary Active 反例，authority拒绝但Ops认证 | **FAIL / P1** |
| Run/Trace immutable | stored binding、head advance、rollback、legacyNULL；API/UI/实际 Trace 双视口 | 已执行范围 PASS |
| 前端 auth/abort/stale/mobile | loading/empty/error/retry/reset/dispose/延迟响应，真实横滚、无写控件；最终UI54和visual4 | 已执行范围 PASS，首轮失败保留 |
| 原档、身份与隔离 | 历史3673文件/blob/180XML/442ZIP；两树全集首尾保护、自有资源精确清理 | 复算完成，不抵消P1 |

Task9 六步：完整只读投影测试和历史 RED/raw 已检查；新增有效反例并未改产品；
前端和全矩阵实际验证完成；冻结 evidence surface 已核验；本 reviewer 不执行实施计划中的
产品 commit 步骤，也不自行给 Task9 验收。

## 4. 本人实际 XML

T/P/F/E/S 逐 testcase/failure/error/skipped 计算，不根据 exit0 猜测。
full/API/integrity/minimum 与重跑 UI、visual4 有重叠，**不相加为独立样本数**。
suite_seconds 不等于 wall clock，尤其 parallel、migration、清理或 runner 等待。

| XML | T/P/F/E/S | suite秒 | SHA256 |
| --- | --- | --- | --- |
| full-final | 1864/1864/0/0/0 | 395.535 | 63d99f7b91042514a65e949adfae380f579646ad8af35598124378ff2097ddcb |
| api-final | 315/315/0/0/0 | 86.556 | e8b672a73a3384de879a6f1e5dcba11cbd97b0ca72e7bdc8c67dd274d1c5c0d7 |
| integrity-complete | 111/111/0/0/0 | 44.334 | 5a02f2c4b4d3f02694f1e0e634a10ae6fe3cdfba8691454bcd4320ea6e706a52 |
| minimum | 28/28/0/0/0 | 17.394 | 2ade3c19da19bf7c765734936f9d4c99010aaf641b5ebdd05f8e2da25a5709ef |
| fresh-leaf | 9/2/7/0/0 | 3.633 | 39daa483135c1fe9ff9718b3757eae1819b7082ba8a32065d4e3935dde334d60 |
| fresh-active | 6/1/5/0/0 | 4.083 | 4150f0aeae6e1320cb4a2da09fbe3fe92ebac66890fe07cf5acb5d762d7102d9 |
| ui54 原失败 | 54/51/1/2/0 | 168.403 | 6969d460cadee1aa6f0db1c727cfac4923ae02e48e67102b6334ff13a4352b0c |
| ui54-recheck | 54/54/0/0/0 | 31.193 | d4ac9185f987459e659b051cc2b7bc444f2cb71411d98671373c37503d0f05e0 |
| ui-visual4 | 4/4/0/0/0 | 6.537 | b83005077e8223e85f4c13d8801e390f7027fa62b6b7f5e6d1d063ccf9db6912 |
| prod-current | 2/2/0/0/0 | 1.132 | 1f34756a99faec2a25f58f3871a969ab9ee18661dc6e8b3f20eae473c9912b40 |
| prod-history | 2/2/0/0/0 | 1.742 | a7e4547ef6cc43d1946c8f4d60875f5013e3582123fc80a1a1362f40805d36cc |
| prod-approval-malformed | 2/2/0/0/0 | 3.461 | 39312ddcbc58f6ab6fda97a4ca23e4682775abc6c01cc298ea7f4c8c51384376 |
| prod-genuine-malformed | 2/2/0/0/0 | 1.210 | c2bbebd71ee5eead0b27a31e337280e3b0f1f32ffee1e7250be03d220ea5f589 |
| prod-genuine-valid | 2/2/0/0/0 | 1.397 | c8a1893c3f8fd322f20c07773fd5592a167574aaea08683b832238eb82e632d4 |
| prod-referenced-poison | 2/2/0/0/0 | 1.189 | b09f4d05c69e13e9656e45e8f6b8723f7ae21ce0d24936428547459e9d4cbdc2 |
| prod-minimum-zero | 2/2/0/0/0 | 1.215 | 38af7106d7423e55d8b2d6a2a27e7a45ff730bc14a3554569ead44f38cbb682b |

111 = 原独立47 + metadata17 + repo完整GET47；28 = gate-specific原4 + repo新24。
API315 保留六个源Ops测试模块及独立relations/corroboration/code/extra探测；
full1864 是本人最终冻结源码全后端，非复述 SPEC 数据。

实际命令数组、cwd、环境、start/end UTC、exit、UUID DB/finally drop 和
production server PID/lifecycle 均在 `*-command.json`、`*-lifecycle.json`。
主要实际 UTC：

```text
fresh-leaf:  2026-11-02T05:15:03.869097+00:00 -> 05:15:14.124123+00:00
full-final:  2026-11-02T05:16:29.285388+00:00 -> 05:29:13.657433+00:00
api-final:   2026-11-02T05:16:29.285460+00:00 -> 05:18:02.432735+00:00
fresh-active:2026-11-02T05:21:56.962998+00:00 -> 05:26:48.242308+00:00
ui54:        2026-11-02T05:21:56.569894+00:00 -> 05:24:31.615058+00:00
ui-recheck:  2026-11-02T05:32:03.813461+00:00 -> 05:32:21.940388+00:00
production child commands: 05:32:07.155478+00:00 -> 05:47:20.214750+00:00
```

复现必须另建 UUID E 和 freeports，将 ROOT/HEAD/DB prefix/records/config 全重新绑定；
使用自有 `review.py pytest ... test_fresh_leaf_identity.py` 或
`test_fresh_active_leaf.py`，不要直接运行历史 fixed OWN/main/golden runner。
本报告中的实际 UUID 只用于核对，不作未来复现目标。

## 5. 浏览器、资产与运行时

本人 Node20.19.5，实际 npm build/tsc/Vite7.3.7 exit0，chunk>500kB warning 原样保留。
node_modules 实体复制到 E，内部链接均在自有树内，没有 symlink 回产品源。
browser skill 在 build/Playwright 前读取。

七场景真实 PostgreSQL、迁移/fixture、FastAPI OpsQueries 和本轮 dist，经本地 production
Starlette 提供；不是 Vite mock 生产、外部模型或真实部署。desktop1440x900、
mobile390x844，14/14 正确性通过。没有把 production14 PASS 当成新叶子攻击通过。

本人实际查看14张production关键图及 Policies/immutable Trace双视口4图，共18张。
合法 Active 显示双精确来源，历史/local 正确；坏审批/poison/minimumzero 无健康消费来源。
mobile 宽表是真实容器横滚；部分截图在 scrollIntoView/横滚之后，不能证明初始scrollLeft=0，
不声称全部列同屏可见。desktop sticky header 局部取景遮行不据此编造产品缺陷。

生产 page listener84 GET、完整production trace142 GET、42个实际CSS/JS响应正文
与 retained dist逐字节一致，console/pageerror0、document overflow<=1。
统计重叠，不作为 HTTP 总数；导航响应缺正文者不算byte检查，同trace request-context GET
有正文。全部126 trace ZIP CRC通过、4457 members逐字节读取/hash，trace/network逐行JSON解析。
六个dist文件原bytes已保留，清理后不依赖丢失 build 路径。

Python3.11.17 patched runtime只读使用，58 distributions、39声明约束实际匹配；
pip check exit0，该检查前后runtime元数据相等。未安装/升级，未跑漏洞审计，
不把此结果当成Task10依赖最终验收。两产品主`.venv`在完整初末快照保持不变。

## 6. 旧证据、失败与 provenance

本人重新全文读取/hash/actualGitblob核验历史3673 Task9文件、180 XML逐项解析、
442 ZIP CRC/15567 members完整读取。JSON全文、JSONL全行和文本字节保留；
旧图片字节核验不冒称重看每一张。索引 `historical-and-recovery-raw-audit.json`。

新SPEC462 manifestSHA：
`8c03414cbb03a275947f017ff274e7692b76cb7cb7867447c81802972b87a1bb`；
payloadSHA `ae71838146eb68041589efe58c5889c7425c0c83140bd05c02b15f61c085bd2e`；
reportSHA `80ccd67d9b2a80673475595c7b479a05fb00fc4e8a5cc58f8c342126338887cd`。
实现570 manifestSHA：
`daeaf5ae1953363ec9027082b3e0bd70bb2d712d16f14499049f4b7ad4103d19`；
payloadSHA `a0f174383667b0ccdc56c174e28d5e0f8acf0c4b07006abcc872c46449ae6d9b`。
原minimumFAIL466、F1/C1/S1-S3/S1-R、恢复中断/丢失tmp/无效fixture/原invalid scanner
全部原字节未覆盖；未知历史请求、时间、费用不补造。
新SPEC PASS 和父侧postcommit只作provenance，不能替代本人代码判断或覆盖本次P1。

本人原UI51/1F/2E完整保留，同配置最终54PASS和visual4PASS；
未提高timeout或改源求绿。首轮导航/timeout问题未独立复现为产品缺陷。
辅助无效read路径、XML分类假设、scan/cleanup pid库存竞态完整留
`auxiliary-invalid-attempts.md`、原脚本/快照/log/UTC记录，均不当产品反例或首次scan成功。

最终 secret 扫描以本地实际值和高置信模式覆盖自有 retained/history/17源路径及 ZIP成员，
不回显 secret。仅将原Gitblob精确相等的旧scanner `parent-retain.py:88-89` 两条 PEM
assert literal分类，不扩大白名单，raw literal hits仍应记2而非改成0。
扫描结果以独立最终raw记录为准。正常hook的2秒扫描超时不称完整scan，本reviewer不commit/hook。
本人清理后串行扫描实际完成：4280文件、568ZIP、20024成员，2项distinct实际本地secret值
匹配0，高置信模式有效匹配0，原scanner精确literal命中2。实际UTC
`2026-11-02T05:58:33.421547+00:00`，原扫描记录 `independent-secret-final.json`；
报告补充后的再次扫描另留 `independent-secret-postreport.json`，不覆盖这次记录。

## 7. 资源、成本与终态

实际 cleanup UTC：`2026-11-02T05:53:53.260581+00:00 -> 05:54:05.951501+00:00`。
13个本人 UUID DB均 finally drop0、精确 datname 查询无余留，无他人DB删除。
自有Redis56737/PID86947，shutdown前核对PID/run_id/dir/save/appendonly与起点一致；
nonpersistent、SHUTDOWN NOSAVE，无FLUSH或prefix DEL。
ledger1017条、428 exact DEL/UNLINK；subprocess12个余key未计量，不称账本完整，
只随本人已确认实例关闭。56737/56738/56739均connect_ex61关闭。
本人modules/dist/cache/tmp/npm/Vite缓存已清，raw/trace/screenshots/retaineddist/scripts保留。

两树全部tracked/source/HEAD/status/index hash+mtime/`.venv`/源Vitecache
每测试/build/UI/production invocation前后核验。最终4891 M3与1110 primary
tracked Gitblobs全部实际相等，355/266源全集首尾相等。主树始终只读。
共享PG16.15 loopback57432/PID16852/指定data-dir与patched runtime保留。

实际模型请求0、实际模型费用USD0；fixture model_calls/cost不是实际计费。
HTTP总体unknown，不补零。所有失败和辅助attempt成本模型0，时间未知者明确unknown。
Docker absent、不安装；真实CI、Task10/Agent50/live模型、正式holdout/v3release、
多租户生产部署、真实手机/跨浏览器、学生效果均未执行或授予证明。
工程开发回归证据仍为 `validation_required`，不是独立release qualification。

本完整结果先落 `/tmp/m3-task9-minimum-code-result.md`，E保留同字节
`review-result.md`、bits-code-guard JSON/Markdown/HTML及全部本人raw非循环manifest。
最终封存后通知父侧核对归档；**WHOLECODEFAIL，不继续Task10，不自授Task9验收。**
