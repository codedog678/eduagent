# Task9 WHOLE CODE 独立审查：FAIL

**P1 / BUSINESS_SEMANTICS / 置信度 10/10，一项同根因缺陷。**

实际 clean CODE HEAD：`a3e2c0b0f510235cec8a98784afdb26b3bb6db79`；父 `9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f`。唯一 R 为 `/Users/bytedance/Documents/trae_projects/eduagent-m3`。范围从 Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f` 到当前 HEAD 的全部 Task9，21 source files，实际 Git `+3857/-51`，不是只审最新补丁。

本人完整读取当前 brief、bits-code-guard 与适用引用、批准 design/Task9 六步 plan、全部实施/SPEC/历史失败证据，并按分组 fallback 完成本人 WHOLE 源码及共享调用影响审查。新独立 SPEC PASS 仅是启动本轮的先决条件，未用其绿结果替代本人执行。

## 有效缺陷

[ops_queries.py:594-604](file:///Users/bytedance/Documents/trae_projects/eduagent-m3/python/core/distributed/ops_queries.py#L594-L604) 的 `_frozen_summary_matches` 在 canonical identity、数量和精确费用相等后即返回通过，没有验证完整冻结指标、实际观测 schema 和真实阈值结果。receipt/window 两个声明相同不代表对实际行真实。

真实 migration/FK/append-only 下，新增合法关联的观测/窗口/收据，保留原行与收据。发布权威先对同一精确叶子判拒绝，但完整 GET 200 仍显示 local passed；Active 引用该无效 Canary 时仍保留 Canary 与 Shadow 的 consumed_chain passed。预期应拒绝该来源，并使 Active 整条健康消费链失效，不能借其他叶子回退。

直接对照权威 [promotion_repository.py:721-749](file:///Users/bytedance/Documents/trae_projects/eduagent-m3/python/core/distributed/promotion_repository.py#L721-L749)。最小原证据为 E 下 `code-complement/active-candidate-permission_violation.json`：authority false，实际 decision fail / confirmed_permission_violation，冻结零失败，GET 两来源通过。

这是核心证据展示语义错误，不声称发布写绕过。未禁 trigger、未 update immutable、未把无效 setup 当产品 FAIL；Active 观测 fixture 的 is_current=false/head 留 Canary 原样保留。

建议后续修复：对有界精确冻结 keys 使用纯只读的 schema/完整摘要/阈值真实性认证，统一 local/consumed_chain 条件；保留 frozen minima、Decimal cost、合法非通过 local、独立 Shadow/history、合法 Active 两来源及精确 Canary 基线。Ops 不可调用 command 或无界/带副作用 evaluator。本 reviewer 不实现。

## 本人复跑

| 矩阵 | 结果 P/F/E/S |
|---|---|
| 完整 backend | 1911/0/0/0 |
| API | 362/0/0/0 |
| 原 integrity + 独立元数据矩阵 | 131/0/0/0 |
| 原有效 leaf/Active + minimum 全矩阵 | 90/0/0/0 |
| 本人完整指标互补攻击 | 6/36/0/0 |
| SQL/closed DTO 503 + FK/append-only 补充 | 9/0/0/0 |
| 全部 UI | 54/0/0/0 |
| 新增 fixture UI/Trace | 4/0/0/0 |
| PG production build 双 viewport | 28/6/0/0 |

Node 20.19.5 build exit 0。47 新 leaf cases 全部包含；90 = fresh local 9 + 独立 Active 6 + minimum 4 + checked-in minimum 24 + leaf 47。原七 local/五 same-input Active 有效反例本轮已通过，历史失败原件完整保留，不能抵消新 FAIL。

互补攻击六种 poison x 两 cohort x 两 local gate = 24F；同输入 Active = 12F；合法对照 6P。原 12 PG 场景双视口 24P，三个坏指标叶双视口 6F，合法指标 Active 2P，额外真实 PG pinned Trace 2P，共 34 checks，不重复增加样本数。

所有 production detail GET 200、error 0；16 场景 mobile 真横滚，current 0 -> 220，合法 before39/193 保留。136 实际资产响应正文与本轮 dist 字节一致。真实 Run Trace 来自本人 UUID PG/持久固定身份，fixture Trace 截图只算 UI。本人 view_image 核验七张关键图，路径及 SHA 见 E 的两份 visual inspection records。

## 完整证据与资源

E：`/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814`。

25 原 XML 逐 testcase 核验；26 complete before/after byte-equal pairs；92 ZIP/3251 members CRC/正文 SHA；32 health production records + 2 actual PG Trace；136 asset bodies。192 health page GET、340 production trace-network GET、136 explicit GET 有重叠，不相加；all HTTP unknown。各实际测试/构建/production invocation UTC、argv、cwd、exit 与 exact DB 生命周期均留 raw；完整探索读取 UTC 账本不可得，明确 unknown。

历史独立字节复核：6076 files、18 manifests、245 XML、734 ZIP/25943 members、7296 当前 actual Git blobs、5492 prior blobs。历史 v1 原失败/改名脚本、352 source 实际历史 Git blobs、一个原无效 JSON、SPEC 辅助 8P1F/误解析、尾空格、旧 CODE/实施失败和未滚图均原样保留；不复制旧 helper 错行号，实际 helper51行。本人两次封存辅助失败及旧脚本/traceback/UTC/exit 保留，第三次生成成功；实际行数已更正为 +3857/-51。

清理成功：23 exact UUID DB drop exit0、remaining0。共享 PG16.15 loopback57432/PID16852/原 data-dir 保留。本人 Redis56684/PID45475/runid/config 核验后 SHUTDOWN NOSAVE；56684/56685/56686 全关闭；无 FLUSH/PrefixDEL。子进程 key ledger 不完整，残留自有 keys 有列表，靠停止本人的非持久 Redis 丢弃，不声称逐 key 删除。

只删除 E 内 node_modules/cache/npm-cache/tmp/vite-cache；raw/dist/ZIP 保留。完整首末两树 source bytes/mtime/index/.venv/源 Vite cache/运行时一致，7296 M3 与1110 primary实际 blobs 已核验。357 source SHA `14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813`；primary266 source SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。两仓库、patched Python3.11.17/58dist/39declarations+5floors 只读。

本人实际秘密扫描已完成：E `code-secret-final.json` 记录9320 files、826 ZIP/29194 members、1 TAR/358 members、2 actual values，实际密钥值与高置信模式均0命中，不回显值。两仓库 tracked、全部保留 E/report 与 ZIP/TAR bodies 纳入。仅旧 parent-retain.py 的精确88/89行、实际Gitblob SHA9a7b272...分类两 assertion literals，不扩大白名单。最终报告/脚本更新另复扫至 `code-secret-final-report.json`，原扫描保留；normal hook2秒timeout不算完整 scan PASS。

无循环 manifest 覆盖 E 全部保留 raw/报告/脚本/dist（不含自己），外置 `E-seal.json` 绑定 manifest/payload/result/report SHA；外置 final-verification 记录首末保护、完整成员和后验读取。父侧须核验这些 NEW CODE FAIL 后才决定授权归档或 fresh 修复回环。

## 报告和限制

[完整证据说明](file:///tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814/code-review-detail.md) · [结构化 JSON](file:///tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814/final_comments.json) · [Markdown](file:///tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814/report.md) · [HTML](file:///tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814/report.html)。

0 新模型请求、0 actual USD、Agent50 paused；fixtures test_fixture/releasefalse。未跑 Docker/CI、缺正式 v3 独立链与学生效果，不能升格独立 release qualification。未实现、commit、push、外发评论、仓库归档、自授 Task9 验收或启动 Task10。
