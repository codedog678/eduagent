# Task9 Leaf Authenticity: Fresh WHOLE SPEC Result

## 结论与权限

**WHOLE SPEC: PASS。** 本人独立阅读批准规格及完整 Task9 影响范围，独立执行下述矩阵，未发现仍阻断该规格的有效反例。此前 P1 叶子真实性缺陷的 7 个 local 变体及 5 个同输入 Canary Active 断链断言本轮均完成并通过；不能将其说成 12 种独立攻击输入。

这不是 WHOLE CODE PASS、Task9 最终验收或正式 release qualification。只有父侧核验本报告及完整新 raw、完成 NEW docs 归档后，才可启动 fresh WHOLE CODE。本人未实现产品、未 commit/push、未启动 Task10/模型/Agent50。

本人证据根 E：`/tmp/m3-task9-leaf-spec-9efac2fb-3201-4499-9be6-a10cde0023e7`。下文 E 相对路径均指此目录。本报告先完整落盘，再同字节保留为 `E/review-result.md`，随后封存 `E/manifest.json`。外部封存证明 `/tmp/m3-task9-leaf-authenticity-spec-seal.json` 记录最终 report/payload/manifest SHA；不把该 manifest SHA 写回报告，避免循环。逐项 testcase 原始矩阵以 `execution-final-audit.json`、所有 XML 和相应 raw proof 为准，不以实施 GREEN 或旧 c52 SPEC 代替本人执行。

## 冻结事实

| 项目 | 本人核验的实际值 |
| --- | --- |
| 唯一目标 R | `/Users/bytedance/Documents/trae_projects/eduagent-m3` |
| Branch / clean review HEAD | `feature/m3-trusted-policy-promotion` / `9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f` |
| Parent / product | `1b8e4b745126c92cfd56f9f021388dd615d98791` |
| Product parent / 旧 FAIL docs | `855d5c6660343c24df0bef5ad4cf77160e83c566` |
| WHOLE 起点 | Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f` |
| 357 python/frontend source SHA | `14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813` |
| Primary HEAD | `2ff803c968d64741d149e5a1ce88a823d4d32422` |
| Primary 266 source SHA | `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5` |
| 本次实施 997 payload manifest SHA | `37449214c2bb58d5c4e4119d2b0bda5915b39368e136d35b5fe6c2d6c0b3dfbf` |
| 本次实施 payload / report SHA | `c44505192c92ed41c69a6027c4f564af421262ecd6a485f534201d2487e7bb5f` / `6d623c64406c84a7e20e75bdb9e7746fde1bdf16994a149c38c191d5b17fdbdf` |
| Staging 最终 9 payload manifest SHA | `46d47eb044fa9c6a2f741c17e55f8dbbbdaeaf9cb33e49199f9ed4739c20db28` |
| 原 CODE FAIL 595 raw manifest SHA | `1da8278d77d5b683e4b6c08211a0c49d610932a553971c33a24dad8d4c6ba92a` |
| 原 CODE FAIL payload / report SHA | `3b95879869f3ce1db7afbe089d4093683643f9082d6cc20d8eb8f808e9dfda37` / `c888b639b6e9a6bd9d60e1537fbf24a9cd8840e02738a5d42763751c8ce40b45` |

本人复算实际 Git blobs：当前 R 全 6503、旧起点 5492、primary 1110；source 每字节对 review/product Git blob，不仅对工作树 hash。WHOLE source 变化为 21 文件，不是最后 5-file patch：

- 前端：`frontend/e2e/ops.spec.ts`；`frontend/src/ops/{OpsApp,PoliciesView,RunsView,TraceView}.tsx`；`api.ts`、`ops.css`、`types.ts`。
- 后端：`python/api/ops_routes.py`；`python/core/distributed/{health_evidence_identity,ops_contracts,ops_queries,policy_health,promotion_repository}.py`。
- 测试：`python/tests/distributed/{test_ops_api,test_ops_complete_chain,test_ops_health_binding,test_ops_leaf_authenticity,test_ops_minimum_evidence,test_ops_source_integrity,test_promotion_ops_api}.py`。

完整阅读本轮 spec/fix brief、minimum spec/code brief、complete-chain spec/code brief、完整实现报告及原 FAIL 报告；历史执行只作为 provenance 和反例依据。原 CODE brief 内 c52 启动文字是历史事实，本轮不据此取得 CODE 权限。

## 规格依据

批准 design：`docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md` 全文。重点 L32、L104-L105、L156-L177、L261-L262、L331、L361-L362、L394、L435。批准 plan：`docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md` Task9 L1158-L1250 全六步及验收范围。

| Plan 六步 | 本轮规格核验结果 |
| --- | --- |
| Step1 L1172-L1188：四 GET、有界分页、鉴权、closed/redacted DTO、禁写 | PASS；完整 API 及独立恶意 query/113 tie/RR/503 补证。 |
| Step2 L1190-L1199：初始 failing API | 原始历史 RED 保留；本轮为独立 FINAL_SOURCE 验证，不伪造初实现前 RED。 |
| Step3 L1201-L1213：只读投影和不可变 Run/Trace 绑定 | PASS；有界纯读，不调用命令或 evaluator；完整来源关系及脱敏核验。 |
| Step4 L1215-L1228：Policies 和移动表格、无 mutation 控件 | PASS；UI54、实际 PG 两视口、本人 8 张图及真横滚。 |
| Step5 L1230-L1240：backend/build/UI | PASS；本人 full1911/API362、Node20 production build、完整 UI54。 |
| Step6 L1242-L1250：实现提交 | 产品/NEW docs freeze 已存在且实际 blobs 核验；本 reviewer 只读，不自行执行提交。 |

## 逐项规格矩阵

等级列为若退化的风险级别，不表示存在未修复缺陷。每一行实际结果均由本人本轮运行或源码核验支持。`spec-api/`、`spec-integrity/`、`spec-leaf-minimum/` 中逐请求 proof 保存 authority、完整 GET200 与实际 DTO；不能把 fixture 创建、无效异常、跳过尾部断言当有效覆盖。

| ID / 等级 | 权威或实际实现行号（R 相对） | Expected | 本人 Actual / 原始证据 | 结果 |
| --- | --- | --- | --- | --- |
| LEAF-1 P1 | `health_evidence_identity.py:9-14,26-46`；`ops_queries.py:526-604` | 两 cohort canonical key 绑定实际 run/deployment/cohort/version | 两 gate、两 cohort 非 canonical 被 authority 拒绝且 GET 无对应来源；合法替换精确 receipt 保留。repo new47 + fresh9。 | PASS |
| LEAF-2 P1 | helper L16-L24、L49-L56 | Canary rehearsal/operation 分布一致 | candidate/stable rehearsal 缺失或不匹配、operation 不匹配均拒绝；等比例 mixed-operation 合法保留。new47 raw。 | PASS |
| LEAF-3 P1 | helper L55-L56 | passed Canary 两 cohort 均非 production | candidate 与 stable production 变体均拒绝；合法 rehearsal namespace 对照保留。new47。 | PASS |
| LEAF-4 P1 | helper L53-L54 | Shadow 两 cohort 同 parent pairing | candidate/stable 不配对拒绝，合法同时替换 parent 保留。new47、fresh9。 | PASS |
| LEAF-5 P1 | helper L30-L36 | window start/end 精确 flat keys，空集合 canonical 空 hash | 两 gate 首尾错 key 拒绝；minimum0/0 原件保留，非 pass 空诊断契约不删。new47 + minimum24。 | PASS |
| LEAF-6 P1 | helper L37、L51 | passed 的 triggered_thresholds 必须空 | Canary/Shadow 带 trigger 被拒绝；合法空集合 pass 保留。new47/fresh9/freshActive6。 | PASS |
| LEAF-7 P1 | helper L28-L48；`ops_queries.py:531-575` | 有界、唯一、严格排序、精确 key 集合 | LIMIT `2*window_max_runs`、排序/重复/缺记录/版本错等原矩阵保持。integrity131、API362。 | PASS |
| LEAF-8 P1 | `promotion_repository.py:651-754` 与 `ops_queries.py:526-604` | 小型共享纯 validator，不将命令或无界重放带入 Ops | helper 无 SQL/写/调用 evaluator；Ops 仅读取有限冻结集合并精确 Decimal 求和。authority 的有界 evaluator 仍只在 authority，不被 Ops 调用。 | PASS |
| CHAIN-1 P1 | `ops_queries.py:393-524` | 坏 local 来源不能借旧 pass 或邻部署补绿 | 原 7 local 有效攻击全部 GET200 后不认证；Canary 独立合法 Shadow 历史仍认证。fresh9 XML 9/9。 | PASS |
| CHAIN-2 P1 | `ops_queries.py:607-739` | 坏精确 Canary 使 Active 整链不可用 | 原 5 Canary 同输入尾断言独立执行，不因 local 先失败而跳过；Active 两来源均空。freshActive6 XML 6/6。 | PASS |
| CHAIN-3 P1 | `ops_queries.py:426-449,660-739` | 精确 receipt ID/evidence，不以合法 latest 替代 | 原 complete47、独立 relations、metadata17、poison production 两视口通过；合法其他 leaf 不能恢复坏精确引用。 | PASS |
| CHAIN-4 P1 | `ops_queries.py:451-524,607-739` | canonical command 八字段、审批/audit/required/actor/reason 双段闭合 | 同错声明、坏审批、精确 ID、时间断链均 fail closed；真实合法双来源保留。API362/integrity131。 | PASS |
| CHAIN-5 P1 | `ops_queries.py:426-524` | 最新坏审批遮蔽，不借 cutoff 后材料 | 独立 genuine malformed latest 与合法 chain 对照、时间 cutoff 原矩阵通过。7 原 production 场景完整重跑。 | PASS |
| CHAIN-6 P1 | `ops_queries.py:577-589` | 合法 Active local stable baseline 绑定已消费 Canary key | 新合法 Canary leaf 不能替换已冻结 baseline；local Active 合法保留。minimum24 最后一项。 | PASS |
| CHAIN-7 P1 | `ops_queries.py:451-524`；`ops_contracts.py:206-238,289-315` | local 与 consumed_chain 不混淆；合法 Canary/Shadow/Active 不被全删 | leaf_local_valid 双 gate、leaf_shadow_valid 单 Shadow、leaf_active_valid 双 consumed 来源。真实 PG raw+trace 完整。 | PASS |
| MIN-1 P1 | `ops_queries.py:531-546` | 0/0、19/20、20/19 不足冻结下限不能认证 pass | authority 拒绝；local Canary/Shadow 不认证；Active 全链空，合法 Shadow 历史保留。原4 + repo24。 | PASS |
| MIN-2 P1 | 同上；`test_ops_minimum_evidence.py:187-228` | custom 22/23 使用所属 deployment 下限，不写死20 | 20/23、22/20 拒绝，22/23 合法，authority 和 GET 同向。 | PASS |
| MIN-3 P1 | `ops_queries.py:552-604`；minimum tests L230-L244 | 21/21 循环 Decimal 精确费用，不从 rounded mean 反推 | Canary、Shadow 均保留 pass；receipt.cost 等于实际有限 rows 精确总和。 | PASS |
| MIN-4 P2 | helper L51-L52；minimum tests L170-L185 | 低样本 failed/unknown、hold/fail 诊断仍显示 | 两 gate 三类非 pass 状态全部保留，不将其认证成 passed。 | PASS |
| IDENT-1 P1 | `ops_queries.py:451-524` | policy/protocol/runtime/source 四维、issuer/model/data_role/strict version/threshold/window/time 完整 | F1 四维三键九条、S1-S3/S1-R、original47+17+repo47 均实际重跑，无退化。 | PASS |
| IDENT-2 P1 | `ops_queries.py:331-382,426-449` | 同 artifact 两部署 current/history 不相互借证据 | C1 两部署、独立 current/historical 攻击、113 tie 分页保持。API362。 | PASS |
| API-1 P1 | `api/ops_routes.py:34-97,280-332` | auth 原复用，四只读 GET，POST/PUT/PATCH/DELETE 405 | 认证/无效 key/query、missing404、禁写实际断言通过。 | PASS |
| API-2 P2 | `ops_queries.py:90-120,220-267,290-329,741-790` | limit<=100、合法 allow-list、typed keyset，无 duplicate/empty/overflow 偷渡 | 113 同时间戳最大100/剩13；typed tie、极值/非 canonical cursor；所有 duplicate/空/越界 query 在 IO 前拒绝。 | PASS |
| API-3 P1 | `ops_contracts.py:16-18,184-327`；`ops_queries.py:235-252,841-873` | closed DTO，无 raw payload/learner/request/nonce/token/私有字段，numeric poison 为 null | 完整 API 隐私、未知数字与0区分、有限值正常；trace 不回显私有载荷。 | PASS |
| API-4 P1 | `ops_queries.py:284-288`；`ops_routes.py:294-301` | RR READ ONLY、有界SQL、GET不写；数据库/DTO异常脱敏503 | RR concurrent append 不进入同 snapshot；只读属性与无写核验；补充8个实际完整 GET503 无异常私有值泄露。 | PASS |
| TRACE-1 P1 | `ops_queries.py:207-218,937-1011,1305-1347,1388-1413` | Run/Trace persisted deployment/cohort/hash，legacy NULL 不绑定 current | 冻结版本与 namespace class 投影、跨 head 变化及 legacy NULL 原测试保持。full/API/UI。 | PASS |
| UI-1 P2 | `PoliciesView.tsx:63-154,166-242` | loading/empty/error/stale auth/abort/dispose/filterreset 正确 | 完整 UI54 两视口，无新增源 UI 漏跑；错误/退出后的过期请求不恢复。 | PASS |
| UI-2 P2 | `OpsApp.tsx:98,130-134`；`PoliciesView.tsx:203-225,251` | Policies 导航、gate 来源/最新窗口诊断、无 mutation 按钮 | 真实 PG 坏来源与合法对照可区分，最新 pass 诊断不冒充认证；GET only、errors0、document overflow0。 | PASS |
| UI-3 P2 | production mobile raw + trace | 真横滚，合法起始 offset 不强制0 | 12/12 actual wheel 增量；current 0→220，history/local合法39→760，Active合法193→760。见下表。 | PASS |
| UI-4 P2 | `execution-final-audit.json:traces/productions` | actual HTTP CSS/JS response bytes 等于本轮 dist，不只 hash 声明 | 82 ZIP/2937 成员 CRC+逐成员摘要；24 PG records，96 实际生产资产响应 body=dist，完整 GET detail body 也相等。 | PASS |
| EVID-1 P1 | initial/final snapshot + actual blobs + historical audit | 两树/source/tests/index mtime/venv/Vitecache/runtime 全保护 | 每执行完整22 paired快照字节相等，最终完整首末相等；6503+1110实际 blobs。 | PASS |
| EVID-2 P1 | historical audit + corroboration | 所有历史有效 FAIL/无效 setup/中断 unknown 原字节保留 | 5283历史files、224XML逐case、652ZIP/23006members、17manifest 已核，未覆盖原 valid RED。 | PASS |
| EVID-3 P1 | secret raw + 精确旧 Git blob | actual secret values/ZIP全字节0命中，不扩白名单 | 2distinct actual values 不回显；有效pattern0。只精确 frozen parent-retain.py L88-L89 两 assertion literal 分类。 | PASS |
| OPS-1 P1 | owned identity/lifecycle + cleanup | 只清自有UUID资源；shared PG/runtime保留，no FLUSH/prefixDEL | 19exactDB finally drop=0且真实remaining0；自有Redis身份核验后NOSAVE，三端口closed；共享PG不动。 | PASS |
| ROLE-1 P1 | commands/audits/report | 0新模型/0实际费用、全HTTP未知、不叠加样本、不授release | 本人model0/costUSD0；allHTTP unknown；synthetic test_fixture/releasefalse；Agent50 paused。 | PASS |

上表实现短名位于 `python/core/distributed/`，前端短名位于 `frontend/src/ops/`。完整单 testcase 名称、outcome/failure/error/skip、suite SHA 已存在 `execution-final-audit.json:suites`，封存另生成 `verification-matrix.json`，均保留两次辅助 schema 失败；没有用一句“全绿”删除这些失败。

## 本人运行矩阵

全部后端从 R/python 执行 `/tmp/eduagent-m3-patched-runtime/bin/python -m pytest -c pyproject.toml ... -q -p safety`，cache/basetemp/XML 全在 E，每 invocation 独立 UUID PG DB；完整命令/env/drop/UTC 在 `*-command.json`。前端为 Node `v20.19.5`、E 中物理 copy 模块、本轮 production dist，不降锁、不 symlink 写源。

| Suite | 实际结果 P/F/E/S | UTC 2026-11-02 开始→结束 | XML SHA256 |
| --- | --- | --- | --- |
| full backend `tests`（含新增47） | 1911/0/0/0 | 06:46:00.918175→06:52:20.975399 | `ec782aeca93e843223e18ccf16e3bf1e9a883d9c7a14d65b5737a5e7c7ba6237` |
| WHOLE API + relations/corroboration/attacks/extra | 362/0/0/0 | 06:46:00.918157→06:47:57.183334 | `39e2467bc50daf8622cc3109e390bd78d010689b65ab95a56fd2d2dafdfbc9ca` |
| integrity repo67 + independent47 + metadata17 | 131/0/0/0 | 06:51:11.837395→06:52:11.980111 | `7d9f2573b99094bda7fdf18e5c5ff9da4b9cd43a2e66353f7ff1a30891ede0fc` |
| leaf/minimum new47+repo24+original4+fresh9+freshActive6 | 90/0/0/0 | 06:51:11.837468→06:52:02.709022 | `050cae8b27d0accb1c8993185195e42f0eca8c69afd048a876e0e8dc494ab426` |
| production build `npm run build` | exit0 | 06:46:00.524095→06:46:05.573628 | `spec-build.log`，非XML |
| 全部 UI54（desktop/mobile） | 54/0/0/0 | 06:51:11.553761→06:51:33.056594 | `5b0f2415b923e739748216e77fdfc9211ec1b9a77a26c80278e0d2056e1ef9c1` |
| Run/Trace 与 Policies visual supplement | 4/0/0/0 | 06:58:34.014893→06:58:38.810512 | `101b56f977d50a4e3b2eeb92bf8b11880f63eb86c7a0cb6be3a0ee1b977f33d5` |
| sanitized503 + 真实 FK/append-only v3 | 9/0/0/0 | 07:03:54.725266→07:03:57.677969 | `7196e46dfddeb3f5310d18b356fdbaedb4623a65a63fabbfe5c5942cf0da0f1b` |
| 12 actual PG production 场景 × 两视口 | 每场景2/0/0/0 | current 06:51:15.470684→06:51:18.587486；其余batch 06:52:39.929740→06:55:11.070500 | 每场景 XML SHA、命令、case 在 final audit |

API362 的实际分解：repo API19 + promotion77 + integrity67 + health42 + complete47 + minimum24 + leaf47 + 独立39。所有套件存在重叠，不相加为独立样本。fresh files 名称中历史“WHOLE CODE”只说明反例的历史来源，本轮是本人 SPEC 测试，不认领 CODE 审查或别人的执行。

最终共21XML，逐case解析；其中19套有效最终矩阵无 F/E/S，另外2套辅助 schema parser 失败原样保留。22完整快照 pairs 字节相等；初版18XML审计 `execution-full-audit.json` 保留但不冒充最终全集。

### 真实 PG Production 与移动范围

| 场景（两视口各PASS） | 实际正确性 | mobile left 前→后 / width→fullWidth |
| --- | --- | --- |
| current | current v3/hold/不足基线与未知指标，无假来源 | 0→220 / 340→560 |
| history | 历史v2本地pass不替换成current v3 | 39→760 / 340→1100 |
| approval_malformed_latest | synthetic坏最新审批不可认证 | 0→760 / 340→1100 |
| genuine_malformed_latest_valid | 真实合法命令链后坏最新审批遮蔽，不能恢复绿 | 0→760 / 340→1100 |
| genuine_valid | 真实合法 Active 双前序来源保留 | 193→760 / 340→1100 |
| referenced_canary_poison | 精确坏Canary使Active整链空 | 0→760 / 340→1100 |
| minimum_zero | 0/0精确Canary使Active两gate unknown；历史保留 | 0→760 / 340→1100 |
| leaf_local_bad | 无local Canary认证，独立Shadow保留 | 0→760 / 340→1100 |
| leaf_active_bad | Active两健康gate无来源，资格审批审计保留 | 0→760 / 340→1100 |
| leaf_local_valid | local Canary+独立Shadow保留 | 39→760 / 340→1100 |
| leaf_active_valid | 两consumed来源均标非本部署新观测 | 193→760 / 340→1100 |
| leaf_shadow_valid | 合法local Shadow保留 | 39→760 / 340→1100 |

本人先读取 TRAE-browseruse，再运行 browser 验证；本人实际 `view_image` 8 图，路径和摘要在 `visual-inspection.md`、`spec-scope-corroboration.json`。其中 `visual/policy-trace-mobile.png`、`visual/policies-desktop.png` 为 frontendfixture，仅证明 UI，不升格 PG production Trace；另6图为真实 PG + 本轮 dist。历史桌面局部截图 sticky header 有部分遮挡，未宣称像素完美或所有列同屏。

24 production records 均 errors0、document overflow0、GET only、detail actual body 与 Trace 同字节结构；96实际 CSS/JS response bodies 匹配 retained dist。pageGET144、production networkGET242、explicit GET96 口径重叠，**不相加**；所有 HTTP 总量仍 unknown。父侧104资产正文、30pairs/28XML等只作为父 provenance，不算本人计数。

## 原始失败、历史与限制

`historical-full-raw-audit.json` 完整核验5283历史file bytes/text/JSON结构、224XML逐case、652ZIP/23006members以及17份manifest；原报告和 FAIL 均仍在冻结R。manifest/payload各SHA完整存于该审计，不复制或覆盖历史raw。主要历史身份：

- minimum修复570：manifest `daeaf5ae1953363ec9027082b3e0bd70bb2d712d16f14499049f4b7ad4103d19`；payload `a0f174383667b0ccdc56c174e28d5e0f8acf0c4b07006abcc872c46449ae6d9b`。
- minimum原FAIL466：manifest `04952f15c0258d545dca305c6b14ca4a68fcaefd32257a3ace8389e95f7e2344`；payload `69900312b69b41ebd5694890112f0eef180cf634d3d81c6eca5a7dd0036e41a6`。
- 旧c52 SPEC462：manifest `8c03414cbb03a275947f017ff274e7692b76cb7cb7867447c81802972b87a1bb`；payload `ae71838146eb68041589efe58c5889c7425c0c83140bd05c02b15f61c085bd2e`。不代替本轮。
- complete恢复597：manifest `35c56ec0e1a5c2cfd25d0b889b0078bcfad4167edc51cfd9f851fe4ab9c559ee`；payload `330fa3eef8833666cf8ae0c0adec5c27d1c2211a6f4c3d57c7f79edecb9cb173`。

保留原 leaf9=2PASS/7有效FAIL、active6=1PASS/5同输入有效FAIL、新GET33有效RED、原UI51PASS/1F/2E与重跑54PASS；authority拒绝但Ops认证是原问题，不宣称已证明写晋级绕过。初始无 `-c` pytest、坏 production 场景名、Decimal 启动 partial invalidJSON、旧0collection/FK无效fixture、父parser错误与中断/tmp丢失 unknown均保留；不计为有效产品反例、不事后补造请求/费用/UTC。

本人辅助失败原始资料在 `auxiliary-attempts.md`：

- historical audit v1，UTC06:58:30.684113→06:58:48.050947 exit1：错误将旧manifest-v1中的当前脚本当旧bytes。v2未覆盖v1，独立核验旧摘要精确等于保留的 `finalize-docs-v1.py`，最终staging9/9完整。旧 source-manifest 的仓库相对根另核352 actual Git blobs，误根“missing321”不是材料丢失。
- schema v1 UTC07:02:07.073913→07:02:09.568163 exit1、8PASS1FAIL：asyncpg内部char `b'f'` 被错比字符串；v2 UTC07:03:06.077277→07:03:08.491334 exit1、8PASS1FAIL：trigger文本 `DELETE OR UPDATE` 被错搜顺序。实际catalog原件、脚本v1/v2、XML均保留。
- v3使用真实tgtype bitmask，先创建合法完整链有实际行，再对六表既有行DELETE在savepoint内全部被append-only拒绝回滚；9PASS。不disable trigger、不UPDATEimmutable、不用DELETE空表求假通过。
- 只读路径/rg错误和部分阅读命令精确UTC未计量，明示unknown；测试与审计命令的UTC/exit未从阅读命令猜造。

runtime本人实际Python3.11.17、58distributions、39project/dev/build/requirements声明 + 5修复floors逐项满足，pip check exit0；runtime漏洞审计不是本轮任务。Docker不可用未装；真实CI、容器生产、多浏览器、真实手机硬件、正式v3/holdout/live模型、学生任务与教学收益未验证。synthetic fixture为 `test_fixture`/releasefalse，开发replay不得视为正式qualification，Agent50仍paused。

## 保护、秘密与资源清理

本人初末完整 snapshot 包含两树所有tracked、357/266 source（新增tests）、index hash+mtime、每source mtime、两venv、源Vite/.vite-temp、readonly runtime。22每执行全paired字节相等、最终初末全相等；M3 index SHA `d366a7617d965da78b74f4ee4bea788dcd3f1d10317433d2abd59c77e7aad210`；primary index SHA `3c86bfc88b4c08aa70ae40624b1a3ba21bf77c129192b9cd9a1eddb72ee66c95`。不把中断前丢失快照说成跨断点一致。

清理实际UTC07:05:24.801266→07:05:36.661920 exit0，见 `spec-cleanup-final.json`：

- 19个本人独立UUID DB，真实 migration/FK/append-only启用，finally exact drop均exit0，共享admin再查remaining0。只使用测试distributed URL。
- 自有Redis loopback51476 PID29907/run_id `72e036fd2b2f4c7951ab57ba38bf545b3afe297b`、独立E/redis-service、save空/appendonly=no；清理前核PID/run_id/dir/config，再 `SHUTDOWN NOSAVE` exit0。noFLUSH/noPrefixDEL；1017账本行不能冒充所有subprocess key全量，未计量key随自有非持久服务结束。
- 本人51476/51477/51478全部closed；未复用实施62584/62585/62586身份。Node模块/cache/tmp/npmcache/自有Vitecache已精确清理，raw/dist/scripts/ZIP/screenshots保留。
- 共享PG16.15 loopback57432 PID16852、指定data-dir保留，admin库实际仅postgres/template0/template1；只读runtime `/tmp/eduagent-m3-patched-runtime/bin/python` 保留，两树/source/index/venv/sourcecache未动。

本人完整actual-secret scan UTC07:05:44.135847→07:06:17.750174 exit0，`spec-secret-final.json`：7273files、734ZIP/25943实际非目录member、1tar/358member；1本地配置、2distinct实际secret values，匹配0，不回显值；高置信pattern有效0。两原始literal hits仅分类 frozen `docs/superpowers/reports/task9-chain-spec-failure-evidence/parent-retain.py:88-89`，实际Gitblob SHA `9a7b2724246b6230fd40961aba8cc12bdb8ee96f50b91bd318d5e5af5d9c489a`，均scanner assertion而非key正文；不扩路径/行白名单。normal hook hardcoded2秒扫描超时不是完整scanPASS。本报告新增后另做post-report实际值和ZIP全字节复扫，不覆盖原scan。

## 非循环封存与交接

E保留本人全部raw与脚本、21XML逐case、完整before/after、每command原UTC/exit/env、actualGitblob、schema/GET proof、所有ZIP成员CRC/hash、production资源正文、8图视觉记录及辅助失败。`verification-matrix.json`按完整XML case归档，`command-ledger-final.json`不补造setup/batch缺失的aggregate exit；测试/生产子命令实际exit0仍明确保留。`manifest.json`仅映射自有payload，排除自身；报告、脚本、审计JSON均纳入payload。外seal将包含准确payloadcount与source/report/payload/manifestSHA，最终逐文件/逐ZIP/逐case重新验证，报告不反向包含其摘要。

历史原raw仍在readonly R，对应actualGitblob与17manifest的完整独立映射留在E；不将父/实施/历史执行算成本人新样本。全HTTP unknown、本人新模型0/实际costUSD0及所有未验证范围不变。

**交回父侧：本轮 WHOLE SPEC PASS；等待父侧独立核验和 NEW docs 归档。不得用本报告自行授予 CODE、Task9 最终验收或启动 Task10。**
