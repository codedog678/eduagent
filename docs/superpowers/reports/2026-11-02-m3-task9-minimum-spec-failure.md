# Task9 Fresh Independent WHOLE SPEC Result

## Verdict

**WHOLESPECFAIL. Task9 不可验收，不进入 WHOLE CODE。**

存在 1 个已由真实 PostgreSQL 完整 GET、合法对照以及生产构建双视口证明的阻断项：Ops 将不足冻结最小样本的精确 Canary receipt 当作可信 passed 来源，并继续为 Active 展示 Canary、Shadow 两段 `consumed_chain`。现有完整后端、原攻击矩阵和原六个生产页面场景通过，不足以抵消此新反例。

本报告仅为独立规格复审，不是实现者报告、父侧核验、代码验收或 release qualification。未修改 repo/source/tests/index/.venv，未 commit/push，未调用模型，未启动 Task10 或实际 Agent50 评测。

## Identity And Scope

- 唯一目标：`/Users/bytedance/Documents/trae_projects/eduagent-m3`，分支 `feature/m3-trusted-policy-promotion`。
- WHOLE 起点：Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f`。
- review HEAD：`ed42d33a187115825a8a94fb45ae8b4652cf4c11`。
- 产品 freeze：`9ef34434cc72f270085d234d89eae5f22d3d6ecd`；product parent：`85c2759d54fd55691cf69d98df91c81ad9caf65b`。
- 本人 raw 目录：`/tmp/m3-task9-wholespec-7116c864-8783-4351-92c2-550bf3427d3e`，下文相对 raw 路径均基于此目录。
- 开始时间：`2026-11-02T02:41:55.148169+00:00`；清理完成：`2026-11-02T03:09:16.917325+00:00`；随后继续只读 provenance/报告生成。
- 354 项 python/frontend 源全集，包含新增 `test_ops_complete_chain.py`：
  `6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96`。
- WHOLE diff、初实现、F1、C1、S1-S3、S1-R、失败中断和恢复证据均纳入，未只看最后 diff。完整 diff 保存在 `whole-task9-source.diff`。

## Blocking Finding

### SPEC-1: 不足样本的冻结 pass 仍可认证整条消费链

权威要求：

- `docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md:307-324`：candidate 与匹配 stable 均至少 20 Runs，基线不足为 hold，不能晋级。
- 同文 `:422`：健康 Canary 的 pass 需要至少 20/20。
- `docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md:1158-1230`：Task9 暴露可信只读证据，而非仅格式正确的声明。
- 启动 brief “必须独立证明”第 1、2、4、5 项：精确引用 leaf 必须真实有效，不能用两份相等的错误声明证明消费链。

根因位置：

- `python/core/distributed/ops_queries.py:525-549`，`_frozen_summary_matches` 只要求 `0 <= len(keys[label]) <= window_max_runs`、run_count/sample_count 相等和 Decimal 精确费用，没有对 passed 来源应用冻结 `candidate_min_runs` / `stable_min_runs`。
- 同文件 `:464-520`，`_project_health_sources` 接受声明为 pass、hash 自洽且费用/key 一致的不足量窗口。
- 同文件 `:733-744`，`_consumed_canary` 复用该 leaf 检查，因此错误信任继续传播至 Active 的两段来源。
- 对照：`python/core/distributed/promotion_repository.py:651-752`，权威 `_validated_health_window` 明确执行最小样本限制，本轮对三种不足量证据均返回无效。

独立复现：

1. 自有 UUID DB 中执行真实 register → Shadow → Canary 命令与 evaluator，获得合法 20/20 原始窗口。
2. 仅追加新的 immutable window/receipt，选择原真实 observation 的有序子集，重算 window identity、evidence hash、run_count、sample_count 和真实 Decimal 总费用；无触发器禁用，无原记录篡改，无 FK 错误。
3. 用完整 canonical transition command、真实 audit、精确引用新 receipt 的 approval 构造可检验关系。该 Active fixture 是追加的攻击证据，不冒称真实晋级命令成功。
4. 使用完整 GET 读取 Canary 与 Active，先保存请求结果与期望，再执行正确性断言。

| Candidate / Stable | 权威消费校验 | 预期 Active 可信来源 | 实际 Active 来源 | 实际 Canary passed 来源 |
| --- | --- | --- | --- | --- |
| 0 / 0 | 拒绝 | 0 | Canary + Shadow，共 2 | local Canary + consumed Shadow，共 2 |
| 19 / 20 | 拒绝 | 0 | 共 2 | 共 2 |
| 20 / 19 | 拒绝 | 0 | 共 2 | 共 2 |
| 20 / 20 | 接受 | 2 | 共 2 | 共 2 |

原始证据：

- 探测源码 `test_minimum_evidence.py:24-112`。
- `minimum/minimum-0-0.json`、`minimum/minimum-19-20.json`、`minimum/minimum-20-19.json`、`minimum/minimum-20-20.json`。
- `minimum.xml`：4 项，1 passed、3 failure、0 error、0 skip；不是“发现缺陷所以测试 PASS”。
- `minimum-command.json`、`minimum.log`、对应 before/after。
- `live-fixture-prod-minimum-zero.json`、`production-prod-minimum-zero-{desktop,mobile}.json`。
- `prod-minimum-zero.xml`：0 passed、2 failure、0 error、0 skip；对应 trace ZIP 和截图保留。
- 生产 GET 的 receipt `d19b5d24-cf9b-4fef-a9e3-8b90ecbc8eaa`，sample_count=0、cost=`0E-8`，仍显示 `passed / consumed_chain`。页面同时显示冻结下限 candidate=20、stable=20。
- 已本人查看 `screenshots/detail-prod-minimum-zero-{desktop,mobile}-left.png`，非仅读取 DTO 或父侧截图结论。

影响与边界：这是 Ops 可信证据展示及断链传播缺陷。攻击需要测试夹具/损坏持久证据；不证明公共 GET 能写库，不证明认证绕过，也不证明实际 PromotionCommand 能晋级不足量候选。本轮权威消费 helper 拒绝的事实必须保留。

探测断言范围：三种负例均在 Active 整链断言处有效失败，未执行该函数最后的 local 断言。尾部 local 断言包含独立 Shadow，范围过宽，不作为本报告验收依据；Canary 的合法独立 Shadow 不应因 local Canary 无效而全局删除。表中 Canary 来源列是已保存完整 GET 的实际值，local Canary 本身样本不足的判断只针对该 gate，不否定独立 Shadow 历史。

修复验收方向：passed/consumed leaf 的有界只读验证必须应用其冻结样本下限，失败应传播为整条 Active 消费链不可用；保留合法 20/20、21/21 Decimal、独立 Shadow 历史及合法 local 非通过状态。不能靠前端删行、重放授权或全局删除 health 达成绿色。

## Independent Execution

环境：

- Python `3.11.17`，`/tmp/eduagent-m3-patched-runtime/bin/python`。
- PostgreSQL `16.15`，共享测试服务 `127.0.0.1:57432`，postgres trust，PID `16852`；只通过测试 URL 使用逐 invocation UUID DB。
- 自有 Redis `8.10.3`，`127.0.0.1:58479`，PID `33110`，run_id `046911ec75baff5dd011f5abfb68e56d1f291566`，save 空、appendonly=no。
- Node `20.19.5` binary：`/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`。Vite `7.3.7`；未降级锁。
- 实体 node_modules copy，仅内部 symlink，无指回 source 的链接；目录 hash 与逐文件/链接表见 `dependency-independent-check.json`。
- `PYTHONPATH=M3/python:OWN`，TZ=UTC，禁止非 loopback socket；清除模型密钥及生产 `DATABASE_URL`；pytest 使用 `-c pyproject.toml`，所有缓存/trace/dist 在 OWN。
- 浏览器 skill 在自动化前全文读取。浏览器 1440×900 与 390×844。

| 本人 invocation | XML 测试 | Passed / Failure / Error / Skip | UTC 起止 |
| --- | --- | --- | --- |
| `full-final` | 1840 | 1840 / 0 / 0 / 0 | 02:53:42.633564 → 03:00:00.317843 |
| `api-final` | 291 | 291 / 0 / 0 / 0 | 03:00:13.832056 → 03:01:38.641114 |
| `integrity-metadata` | 64，即 47+17 | 64 / 0 / 0 / 0 | 03:02:27.765883 → 03:02:52.565975 |
| `minimum` | 4 | 1 / 3 / 0 / 0 | 03:02:27.765860 → 03:02:32.171127 |
| `ui54` | 54 | 54 / 0 / 0 / 0 | 02:49:33.098760 → 02:49:52.922656 |
| `ui54-screenshots` | 54 | 54 / 0 / 0 / 0 | 03:04:11.521823 → 03:04:29.453395 |
| `prod-current` | 2 | 2 / 0 / 0 / 0 | 03:03:09.122531 → 03:03:11.542377 |
| `prod-history` | 2 | 2 / 0 / 0 / 0 | 03:03:42.069843 → 03:03:44.315159 |
| `prod-synthetic` | 2 | 2 / 0 / 0 / 0 | 03:04:14.277601 → 03:04:16.794574 |
| `prod-genuine-malformed` | 2 | 2 / 0 / 0 / 0 | 03:04:46.130269 → 03:04:48.251585 |
| `prod-genuine-valid` | 2 | 2 / 0 / 0 / 0 | 03:05:14.478594 → 03:05:16.802939 |
| `prod-referenced-poison` | 2 | 2 / 0 / 0 / 0 | 03:05:34.401526 → 03:05:36.556123 |
| `prod-minimum-zero` | 2 | 0 / 2 / 0 / 0 | 03:06:02.066550 → 03:06:04.212625 |

所有日期为 2026-11-02。API 的 252 项与 full 重叠，只有 39 个额外测试身份，不能把两套相加作为独立样本。54 UI 执行为 27 个逻辑测试 × 2 视口，带截图重跑不能增加独立用例数。新增完整 GET 47 已包含在 full/API，非额外第三批独立样本。

Node20 production build 独立成功，保留 `node20-build-command.json`、`.log`、before/after；现有 chunk-size warning 不冒充失败或优化完成。

精确命令、cwd、环境、UTC、小数费用边界、退出码、XML 逐项 counts 与 SHA 全存于 `*-command.json`、`verification-summary.json`、`raw-parsed-summary.json` 和 manifest。主要 XML SHA：

- full-final：`46ef69c94d1f89a59ea801b706007daa1c5d423796cc6f239139ac689e1137e0`。
- api-final：`d28f3e9b3130a5a849d482f1509b396505c6dba099eb122fbacfbe7eaf637e52`。
- integrity-metadata：`fd3c44a8f0ec71237f58e6781cefb1d41ed62d8e30fa9b54069b4eaaaf863935`。
- minimum：`cc8dd77cff9ba74f56980ac0fddcd64e5017ba79066c5ffe11d4322b5066123f`。
- prod-minimum-zero：`54e59936c02b80e761d203d4bcdaade10e8322f48a0929d2633bba8a6da83277`。

可复盘命令入口：`review.py pytest LABEL -c pyproject.toml ... -q`、`frontend_run.py build LABEL`、`frontend_run.py ui LABEL e2e/ops.spec.ts`、`frontend_run.py production LABEL SCENARIO`。重跑须新建独占非持久 Redis 身份与 UUID tmp/DB，不能将本轮已关闭 PID 当作现役服务。

## WHOLE Requirement Matrix

| 要求与权威位置 | 本人检查/证据 | 结论 |
| --- | --- | --- |
| 四 GET、auth、strict query、limit/keyset<=100、422/404/503；plan:1172-1209 | `test_promotion_ops_api.py:119-182,329-399`、`test_ops_api.py:314-385,499-504,645-681`，完整 API291/full1840 | 通过现有测试与攻击 |
| closed DTO、隐私、numeric poison、未知不补零；plan:1186-1213 | `test_promotion_ops_api.py:210-328,486-520`，own code/extra attacks、UI strict guards | 通过 |
| REPEATABLE READ READ ONLY、bounded SQL、GET 不写、不调 command；plan:1207-1209 | `ops_queries.py` read session；API:364-399 实际数据库 READ ONLY 验证，independent integrity 冻结 keys IN+LIMIT 捕获 | 通过 |
| F1 九类 gate order：latest failed/unknown、issued/created/UUID tie、四维、future、失绑定 | 初 F1 全报告/raw 已读，API:258-328 与 own query/auth poison 全执行 | 通过 |
| C1 同 artifact 两部署不借绿，current/history 独立 | API、`test_ops_health_binding.py:24-78`、own code attacks，生产 current/history 双视口 | 通过 |
| canonical 全命令字段、audit/actor/reason/required、latest approval 遮蔽 | source integrity、independent integrity 18 command 控制与 8 approval 字段、metadata17、new47 | 通过原矩阵 |
| 精确 Canary receipt 11 poison 断链；不借另一合法 leaf、不用等错声明 | `test_ops_complete_chain.py:149-185`，independent 47/17，生产 referenced poison | 通过原 poison；不足样本反例 FAIL |
| receipt gate/status/四维/issuer/model/data_role/version/deployment/window/threshold/evidence/time/sample/cost/keys 全有效 | 新旧完整 GET、integrity 47、metadata17；自己的 minimum 4 与生产双视口 | **FAIL：passed 下限缺失** |
| 合法 Active 双来源、Canary 的 Shadow 历史、local/current/history、cutoff/local masking | new47:177-246、health-binding、六生产场景；本人查看图片 | 通过合法对照 |
| 20/20 与 21/21，Decimal 不从 rounded mean 反推 | source-integrity:184-209，新旧合法 fixture；API/full 中执行，20/20 own control | 通过 |
| Run/Trace immutable 与 legacy NULL；plan:1211-1213 | API:401-466，真实 head advance/rollback 与 UI:604-646 | 通过 |
| UI loading/empty/error/retry、stale abort/disposed/filter reset、只读、移动端真横滚；plan:1215-1241 | UI54 两次双视口、生产页面滚动+document overflow+GET-only+无 console/pageerror | 通过原场景；不足量信任误展示 FAIL |
| HTTP 生产资产与 dist 字节/hash 相等，真实 PG 来源 | 14 份 production JSON，六正确场景12 passed、额外攻击2 failed；asset bytes 比对在正确性断言前执行 | 通过资产验证，不将攻击视为 PASS |
| SOURCE/新增 tests/HEAD/index/主venv/cache；brief:7-9 | 17 成对 invocation 快照、final/report-freeze、全部 Gitblob 验证 | 通过本轮只读边界 |
| 历史失败 byteexact、原坏 fixture 与中断边界 | 历史2157文件、134 XML、176 ZIP 全结构/CRC/bytehash/Gitblob，恢复 baseline tar358 独立验证 | 通过归档保留，未声称继承执行为本人运行 |

原始 suite 并非穷尽一切可能的损坏值。这里的“通过”只针对已读权威与所列可复盘断言，不覆盖 SPEC-1，也不建立教育效果。

## Archives And Provenance

全文读取权威 design、plan（Task9 六步），实现 brief/result，旧 `2026-11-02-m3-task9-chain-spec-failure.md`，初实现/F1/C1/S1-S3/S1-R 与新恢复报告、raw，并全文读父侧 verify 程序与结果作身份参照。

本人独立执行的原始核对：

- `historical-and-recovery-raw-audit.json`：2157 个 Task9 历史/恢复文件逐字节 SHA，JSON/JSONL/XML 全量解析，176 ZIP CRC/成员/trace事件解析，逐文件对当前 HEAD Gitblob。134 XML 的原 failure/error/skipped 明细保留。
- `final-independent-provenance.json`：M3 当前3374 tracked、primary当前1110 tracked 全部对各自 HEAD Gitblob；恢复 `baseline.tar` 全358文件对 `85c2759...` Gitblob，其中 python/frontend353。
- 恢复新归档598文件、manifest597 payload，父侧给出的身份作为参照；本人重新读取/核对并对 Gitblob，而非直接将父侧命令标成本人执行。
- 原有效 RED integrity47=42/5、metadata17=11/6、new47=16/31、生产引用 poison2=0/2 是归档恢复 replay；不是本轮运行，也不是已丢失中断前运行。本轮 current GREEN 及新 minimum FAIL 独立执行列在上表。
- 原 0 收集、2 FK 无效尝试保留为无效；不计产品失败或 PASS。缺失的早期 `/tmp` 证据和 runtime、中断请求数/费用/具体运行事实不可重建，保持 unknown。
- 旧失败归档字节未更改；不把断点前后环境变化说成全等。

本轮 source/index/cache：

- M3 index SHA `6fa20fddb6370d8e6b6271a7662735a6ddedf1f1237b025b1e72fb178dbdbc9e`，mtime_ns `1793586418980684130`。
- primary 源266 SHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。
- primary index SHA `3c86bfc88b4c08aa70ae40624b1a3ba21bf77c129192b9cd9a1eddb72ee66c95`，mtime_ns `1793564703011337702`。
- primary `.venv` 10024 entries 元数据 SHA `fc797cc8e4911370e8e86cc825338c3dc232c91865c7ceeeaf6bf0387f5d69b1`；M3 `.venv` 本轮不存在。
- 两树 Vite/Vite-temp entry 元数据、源码每字节、tracked每字节、index bytes+mtime 在17成对快照及 final/report-freeze 与 initial 全等。主venv结论是本轮完整元数据快照相等，不夸称缺失中断前的全内容 hash 相等。
- `git diff --check Task8Acceptance..reviewHEAD -- python frontend` 本人成功执行，stdout/stderr/exit 存入 final-independent-provenance。

## Dependencies And Resources

- 本人读取58 installed distributions、校验39个 project/dev/build/container 入口约束及可选 `gepa==0.1.4`，实际 `pip check` exit0；不声称完成 build-install/container audit。
- 父侧后来对当前57非pip项目/runtime依赖执行 pip-audit，`02:40:29.079467 → 02:40:43.652275Z`，exit0/0 advisory。本轮独立核对全部版本、输入/audit SHA，并原样保留 `parent-dependency-evidence/`；**不是本人漏洞扫描**。旧实施报告“当时未扫描”不因此被篡改。
- 模型请求0、实际模型费用USD0；所有 synthetic receipt cost 都是 fixture 字段，不是实际模型消费。pytest/API HTTP 总请求数未全局计量，unknown；browser page 请求数在各 production JSON，不能冒充全部 HTTP/APIRequestContext 请求数。
- 本轮14个独立UUID DB 均 finally drop，且本人实际查询全部 exact datname 无残留。共享PG PID/data-dir/version与开始相同，未停止、删除或改其数据目录。
- 自有Redis记录503个 exact keys；停服前实际25 keys，其中24未被本进程装表（含子进程UUID keys、policy-deployments、初始化的 `eduagent:rehearsal-runs`）。不能声称账本覆盖全部曾创建 keys。
- 实际归属由独占服务初始空库、run_id/PID/dir/config建立；最终仅对该身份 `SHUTDOWN NOSAVE`，没有 FLUSH、前缀DEL、共享key/服务删除。
- 58479/38730/38731均已关闭，自有 browser/Vite/live_server 进程无残留；共享PG与patched runtime保留，旧57379 Redis未复用。
- 仅删除OWN内实体node_modules、dist、pytest/tmp/npm/Vite缓存；原始trace、XML、失败log、脚本、截图全部保留。生产资产同字节保留至 `retained-http-dist/`。
- 已本人实际查看18张关键截图：六要求场景×双视口12，minimum×双视口2，Policies/Trace×双视口4。逐图SHA在 verification-summary。
- local 两个 distinct secret 值在本轮 raw 与ZIP成员扫描匹配0，最终 artifact manifest再次扫描全部保留payload；未输出秘密值。

## Invalid Attempts And Non-Claims

本轮自己的无效/失败尝试也保留：

- preparation `/private/tmp` 相对未 resolve 的 `/tmp` 模块边界错误：发生于服务/测试前，见 `preparation-attempt-boundary.json`，不是产品缺陷。
- 首次 `full` XML1840=1839 passed/1 failure，业务断言后清理自有 failover key 被过严的 OWN guard 拒绝；原 log/XML 保留。guard 改为仅允许本调用创建的 exact UUID key，`guard-failover` 1 passed，随后 `full-final`1840全通过。无源改动。
- `api291` 因本人输入不存在测试路径，进程exit4、XML0，DB已drop；不计 PASS。纠正为真实 test_promotion_ops_api/test_ops_api 后 `api-final`291 passed。
- 新 minimum 的3个失败与生产2个失败是有效产品反例，不与上述无效尝试混淆。

Docker不可用，未安装或实际执行CI/容器。未执行真实模型、正式 rehearsal、Agent50 或教学效果评测。完整 backend 中的 mock/fixture 单测不等于这些 live 工作流。父侧 Task10 预检与其并行准备不属于本人验收。

最终交付：本文件与 OWN 的 `review-result.md` 同字节；OWN `manifest.json` 包含完整保留payload的SHA、XML/命令/角色/费用/失败/cleanup，不把manifest自身放进其payload，不参与源全集hash。父侧可独立核验归档，但当前 verdict 为 FAIL，不能触发 fresh WHOLE CODE。
