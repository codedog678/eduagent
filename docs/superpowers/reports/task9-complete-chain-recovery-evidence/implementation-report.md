# Task9 Complete-Chain Recovery Implementation Handoff

状态：新修复实现者的工程执行与 NEW 产品冻结已完成，**不是 Task9 acceptance**。
父侧须针对整个 Task9 执行 fresh WHOLE SPEC；仅其 PASS 后执行 fresh WHOLE CODE。
本轮未自行启动、认领或替代任何独立审查，未启动 Task10、Agent50、真实模型或 push。

## 1. 范围与实际冻结

- 唯一可写产品树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 分支：`feature/m3-trusted-policy-promotion`。
- 新产品 freeze / 本报告写入时 HEAD：
  `9ef34434cc72f270085d234d89eae5f22d3d6ecd`。
- freeze parent：`85c2759d54fd55691cf69d98df91c81ad9caf65b`。
- Task8 acceptance / 后续 WHOLE review base：
  `8869166878a193a1c453376471cbe52c8fa84b3f`。
- 起点保存的 18 行 Ops diff 与 247 行新增 PG 测试均完整继承；核对后无需追加产品改动。
- 新 commit 仅两个产品/测试路径，实际 `261 insertions, 4 deletions`：
  `python/core/distributed/ops_queries.py`、
  `python/tests/distributed/test_ops_complete_chain.py`。
- 最终 **354** 个 Python/frontend 源路径全部包含新增测试，SHA：
  `6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96`。
  全部 working bytes 与 NEW freeze Gitblob 逐文件相等。
- 主 eduagent HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422`，
  266 源 SHA：
  `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。
  主 source/index/.venv 只读；本轮首尾快照和每次有效运行边界均未变。
- 仅普通 NEW commits；未 amend、push、修改 git config、跳过 hooks 或签名。

报告先写此 `/tmp` 文件，再同字节复制到新目录
`docs/superpowers/reports/task9-complete-chain-recovery-evidence/implementation-report.md`。
该目录随后以第二个普通 NEW docs commit 留档。docs commit 不改变上述产品 freeze。
为避免 commit/report 自引用，第二次 commit 的实际 HEAD/parent/staged 清单另写
`/tmp/m3-task9-complete-chain-evidence-commit.json`，最终回复给出实际两个提交。

## 2. 中断与历史边界

完整读取 `/tmp/m3-task9-recovery-implementation-brief.md`、权威 design、Task9 六步、
完整 chain SPEC FAIL，以及既有 F1/C1/S1-S3 实施和失败档案，沿用已批准方案。

前代理 `arun_6ae7dc7051536906a0739671` 已由用户明确 killed。
起点实际观察：原 `/tmp/m3-task9-chain-fix-d3d669c4-4da2-41c0-8da8-91e9c4c92192`
和旧 `/tmp/eduagent-m3-patched-runtime` 不存在。旧 PG/Redis 与旧依赖审计原始 `/tmp`
材料亦不能认领为保留。本轮没有补造旧运行次数、时间、费用或原始日志。
`interruption.json` 留有观察时间、丢失路径和继承文件初始 SHA；
`inherited/` 保存原补丁、完整测试字节及本次完整交接。

原 chain FAIL 的 398 payload 逐字节、逐 Gitblob 核验保留：

- 原 retained-manifest SHA：
  `6c5abd6d891154cb090b2d17db5ea4f693df56374e2c9c650589cf3159e8d1f3`。
- 原 398 payload SHA：
  `8cb8c5a30a5e3c4c15067378585a4419f0853dbc033e0b03f02e04e0116ce962`。
- 本轮另核验起点全部 **2411** 个 tracked docs 文件与原 bytes/Gitblob 一致。
  不覆盖旧报告、失败 XML、固定 runner 或 golden archive。

## 3. 修复事实

唯一 S1-R/P2 根因：Active approval 精确引用无效 Canary 时，Canary leaf 已 rejected，
但 Shadow 仍可被认证为 `passed/consumed_chain`。多种 poison 是同一完整依赖链问题，
不计作独立缺陷或独立安全证明。

`_project_health_sources` 改为 classmethod，`_consumed_canary` 在返回精确引用前，
复用同一 leaf projector 校验指定 Canary receipt。artifact 不存在时直接不可用。
Canary 自身 gate/status、四维身份、issuer/model/data_role、strict version、
deployment/window/threshold/evidence/time、sample_count、Decimal cost、冻结 observation
任一不闭合，整条 Active consumed dependency chain 均不成立。

不借另一合法 latest leaf 替换坏引用；不因 Active 坏引用删除 Canary 的独立历史 Shadow。
合法 Active 两条 consumed 来源、local/历史/latest malformed 遮蔽、transition cutoff、
20/20 正向对照与既有 21/21 循环 Decimal 保留。
完整 canonical command 八字段、audit/approval/required/actor/reason 检查沿用原实现。

仅复用有界纯查询，不回溯 Active，不调用 evaluator/command/授权写入口，
不无界重放，不改前端/DTO，也不靠前端过滤隐藏错误。
Ops 既有 REPEATABLE READ READ ONLY 与 public privacy/binding 协议未扩展。

新增 47 个真实 PG 完整 GET 集成用例：30 poison、缺/不存在/旧有效引用、
同错误 evidence 声明、合法双来源、后续 receipt/window、Active local pass/failed/unknown、
latest malformed/failed/unknown approval、local current 与历史独立性。
这些不是单元测试或独立资格评估。

## 4. 真实 RED 与最终 GREEN

因为起点已有补丁，RED 在本轮自有 Git 冻结副本执行：
`git archive 85c2759 -- python frontend tools`，353 原源逐文件等于冻结 Gitblob，
source SHA `1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65`。
新增回归复制进基线的额外路径明确记录，不声称原 Git 已包含此测试。
基线 tar、额外测试初始字节、source manifest 均留档。

下表 T/P/F/E/S 为本轮 raw XML testcase 实际解析；所有 E/S 为 0。
重复 suite、重复 fixture 和视口不相加为独立样本。

| 实际 XML | T/P/F/E/S | Suite 秒 |
| --- | --- | --- |
| red-integrity47-v2 | 47/42/5/0/0 | 16.185 |
| red-metadata17-v2 | 17/11/6/0/0 | 6.807 |
| red-complete-chain-v2 | 47/16/31/0/0 | 20.183 |
| red-production-poison | 2/0/2/0/0 | 1.465 |
| green-complete-chain | 47/47/0/0/0 | 20.234 |
| green-integrity47 | 47/47/0/0/0 | 21.540 |
| green-metadata17 | 17/17/0/0/0 | 7.182 |
| relations-api-final | 291/291/0/0/0 | 80.150 |
| full-final | **1840/1840/0/0/0** | 352.524 |
| ui54 | **54/54/0/0/0** | 35.327 |
| ui-visual4 | 4/4/0/0/0 | 6.699 |
| ui-screenshots4 | 4/4/0/0/0 | 6.476 |
| production-current | 2/2/0/0/0 | 1.124 |
| production-history | 2/2/0/0/0 | 1.328 |
| production-approval-malformed | 2/2/0/0/0 | 1.198 |
| production-genuine-malformed | 2/2/0/0/0 | 1.206 |
| production-genuine-valid | 2/2/0/0/0 | 1.455 |
| production-referenced-poison | 2/2/0/0/0 | 1.192 |

Full UTC：`2026-11-02T02:10:50.609503+00:00`
至 `2026-11-02T02:16:46.381370+00:00`，包括建库/收尾。
pytest 实际 wall summary 352.54 秒；XML 累积 suite 秒与 wall 概念分开。
保留 asyncio fixture scope 警告、现有 zip-parametrize deprecation 和 TestAgent collection
warning，不借去掉警告改产品或测试行为。

API291 = 原 API/关系/攻击244 + 本轮新增47 的独立重跑，不替代完整后端1840。
完整后端含新增47、既有 source-integrity67、health-binding42、promotion API77、
Ops API19；逐 node 清单在机器验证中，可复算 F1、strict identity 与 Decimal 对照。

Node20 `npm run build` 实际 PASS，Vite chunk-size warning 保留。
Vite7.3.7/plugin5.2/React18.3.1/Playwright1.64.1/TypeScript5.9.3 锁不变。
前端实体依赖副本在自有目录，所有内部 symlink 解析在该副本内，不链接回产品树。
生产服务是真实 PG fixture + FastAPI Ops + 静态 build dist，无 route mocks、
Vite dev、业务 worker 或真实模型。UI54 明确使用 mock fixtures，不能替代生产验证。

六场景分别独占 UUID DB/server lifecycle，desktop1440x900 与 mobile390x844。
current hold 不借旧 pass；history 保留原 receipt/window；
synthetic/genuine malformed latest 不恢复旧绿色消费；
genuine_valid 保留两条合法来源；referenced poison 阻断完整链。
生产所有 page HTTP 均 GET，无 page/console error，overflow <= 1px；
移动宽表的实际横滚有断言。

全部加载的 HTTP JS/CSS 与 build dist bytes 精确匹配。Ops JS SHA
`a4430d560a4461a12441b5433d72592db328646e28057a6426ecdef36a13e416`；
CSS SHA `4f3070753582aa2f0a5e82bd28b182212feeb9724a92bf7aee5ae14a2a0c75e6`。
六项 dist 文件 SHA 在机器验证中，清理前保存；不声称保留已删除的 dist 目录。

实际打开 RED 双视口、六 production 双视口、mock Policies desktop 与 Trace mobile
共16张关键截图。RED 的 Canary unknown/Shadow consumed passed 与 GREEN 断链有直接对照。
移动表部分列需要横滚；desktop region screenshot 可能包含现有 sticky header 叠层，
不把截图标为无任何展示限制。完整 screenshot/trace 与 DOM/API 断言共同留档。

## 5. 恢复 runtime 与父侧材料

本轮新建 Python3.11.17 runtime `/tmp/eduagent-m3-patched-runtime`，
使用底层解释器，不向主 `.venv` 安装、不对源码 editable install。
一次真实 pip install 包含 project15、dev4、build2、requirements18、repair floors5，
共 **44** 条约束；包括入口特有 `psycopg2-binary` 和 build `wheel`。
按 packaging Requirement/specifier 逐条核验全部通过，真实 `pip check` 无 broken requirements。
安装记录、UTC、完整 freeze、pip inspect 原始 JSON 和58个已安装 distribution 在新档案。

主要实际版本：FastAPI0.162.0、Starlette1.10.0、AnyIO4.16.0、
certifi2026.10.23、Pydantic2.14.2、pydantic-settings2.16.2、
SQLAlchemy2.0.55、setuptools84.2.1、wheel0.48.0、psycopg2-binary2.9.13、
pytest9.2.0、pytest-asyncio1.4.1.post1、gepa0.1.4。
新解析也包含 anthropic2.3.0、openai3.42.1；不能称为旧54包pin复原。
完整1840与API/UI/build真实执行证明本冻结源的工程兼容性，不证明真实 SDK 模型调用。
retained old runtime-context 原文件未改，其 SHA 和内容单独关联。

父侧只读重建与新扫描材料只复制指定六文件到 `parent-role/`：
audit.json、scan-manifest.json、scan.stdout.log、scan.stderr.log、
dependency-input requirements.txt、manifest.json。
不归档未经审核的 tool-install.log、父侧工具 env 或 caches。
父侧 input54 SHA：
`df7c12e0bcea5a5844a742114d0fd00045a7487752908579265d672aa6b60dae`；
pyproject SHA：
`304fa864ff328fdc8b925e1a08b4b47863759dd88a5195aa522aa9bc73c0b793`。
旧 env 实际 missing roots 为 psycopg2-binary 与 wheel，旧 preflight 仅提 wheel 不完整。
新 parent scan UTC `2026-11-02T02:10:34.271181Z` 至 `02:10:48.573361Z`，
exit1、54dependencies、5affected、12raw、8alias-groups，**FAIL**。
audit SHA `bf8f340197921bca02408aa9cbe1ef78d352aff65d1053d8f81b0acb59cc7d08`。
这是未来 Task10 预检，不是旧 `/tmp` raw，不判断本次 runtime PASS/FAIL，
不替代 Task9/Task10 验收。本轮未扫描新 runtime 的漏洞，未认领依赖安全资格。

## 6. 原始记录、账本与无效尝试

自有执行目录：
`/tmp/m3-task9-chain-recovery-d7c17eb6-6c53-4bca-9c54-26b53147cd36`
（macOS realpath 为 `/private/tmp/...`，两者同目录）。
raw-only manifest `retained-raw-manifest.json`：

- **592** raw payload，JSON303、JSONL1、XML18、ZIP76。
- raw-only manifest SHA：
  `13fdf031a591dbe0d671f4ed1d1a01541185a0236a3effc83ecc57282de89daa`。
- raw payload SHA：
  `320a2d3d945abd6dfd089d8afe74d7559d14de80677501479f8f63d4bfcd6926`。
- 每个文件路径/SHA、原始命令/UTC、XML节点、source、snapshot、fixtures、HTTP、
  runtime和service logs均在 manifest；ZIP CRC 实际核验。
- raw manifest 排除自身与此后生成的完整报告以避免循环。总归档另加入 raw manifest、
  本完整报告，payload594，外层 archive manifest 再加1文件。
  外层 manifest SHA/报告 SHA 在最终 post-archive 核验和最终交接中给出，不伪造循环值。
  以上594是初次归档范围；下述提交前原始空白检查新增三项材料后，
  最终payload597，加外层manifest共598文件，592项原始scope字节不变。

19组有效 before/after **完整快照相等**；另保留最初四份无效启动 before。
最终清理后主 source/index/.venv、M3 source/index、源 Vite cache/temp 与起点均相等。
M3 index 只在明确 stage/NEW commit 更新；freeze后354源仍等于测试全过程字节。
source 摘要只含源与测试，不循环包含 docs/evidence。

保留而不当成产品失败：

1. PG 第一次启动 Unix-domain socket 路径超过103字节，exit1，raw日志保留；
   后续以 TCP127.0.0.1 / 禁用 Unix socket 成功。
2. Redis daemon PID 文件读取竞态使首次身份记录失败，服务实际已启动；
   后续 PONG/pg-ready 与身份记录成功。没有编造原失败 tool stdout。
3. red-integrity47/red-metadata17/red-complete-chain/node20-build 的首次 display
   comprehension `KeyError: 'head'`，发生在 pytest/build/建库之前。
   四份 before 保存；原 tool stdout 未落盘，事实边界明确记录，v2有效运行另label。
4. ui-visual4 四项PASS但未设 OPS_SCREENSHOT_DIR，不作为独立png证据；
   新label ui-screenshots4设目录后四项PASS，原trace仍保留。
5. cleanup首次断言看到未装表子进程Redis键而失败，未执行删除；
   launcher raw保留，后续只停止本次自建无持久化服务，未扩大DEL范围。

真实模型请求/计费USD = **0/0**。fixture sample/cost是合成账本，不是实际计费。
artifact literal data_role 是 `holdout_validated`，但 evidence bindings 明确
`test_fixture/release_eligible=false`，不能当作真实独立 holdout。
fixture protocol=`b`重复64，runtime=`f`重复64，source=`test-source`，
server receipt model label不是在线模型调用。各fixture policy/threshold/receipt/window
身份和费用在 `execution-ledger.json`，受攻击变体在probes/raw source中。
生产含RED共84 page HTTP、58显式 request-context GET 可复算；
backend in-process/mock UI及全部HTTP总量未装表，记 **unknown**，不冒充模型请求。

## 7. 清理与复审服务交接

本轮15个 exact UUID invocation DB全drop_exit0；PG只剩postgres/template0/template1。
248个reset日志中 exact UUID streams全部不存在。
另发现11个UUID子进程附加stream及1个非UUID rehearsal stream，
创建操作未装表；source定位到现有expert/failover worker初始化链。
不把248谎报为所有曾创建键，也不对非UUID或未记录创建身份的键做DEL/FLUSH。
停止本次唯一自建Redis：先核对PID与`save="" / appendonly=no / dir`，
再 `SHUTDOWN NOSAVE`，保存停服前每键xinfo/raw，确认57379关闭。
该临时服务无持久化，不保留这些键；没有改共享/生产Redis或前缀删除。

自有pytest/cache/tmp、实体node_modules、dist、baseline展开副本、npm/pip/pycache清理；
baseline.tar、所有raw、截图、trace、脚本保留。37730/37731关闭，无本次live/browser/worker残留。
未删除主venv、用户目录或父侧env。未运行Docker/CI容器，不安装Docker。

可复用资源：

- runtime仍保留：`/tmp/eduagent-m3-patched-runtime/bin/python`。
- **PG保留运行**：16.15，loopback `127.0.0.1:57432`，PID16852，
  user postgres，仅测试 trust auth。data-dir：
  `/Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36/pgdata`。
- PostgreSQL bin：`/opt/homebrew/opt/postgresql@16/bin`。
- 自建Redis8.10.3已停止，原PID16860不是当前服务身份，57379无listener。
  后续reviewer须另建自己的UUID临时Redis与清理账本，或经协调在该测试父目录重启，
  不能把旧identity.json当作仍运行证据。
- PG正常重启配方（仅必要时由新资源持有人执行）：
  `pg_ctl -D <上述data-dir> -l <父目录>/postgres.log -o "-h 127.0.0.1 -p 57432 -k ''" -w start`。
- 每invocation新UUID DB，只传 DISTRIBUTED_TEST_DATABASE_URL，
  移除真实DATABASE_URL和模型密钥，finally drop；Redis exact keys，不prefix/flush。
- Node20 binary：
  `/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`。
- raw `service-identity.json`记录启动时身份；当前保留/停服状态以
  `cleanup-verification.json.kept`与`redis-before-owned-service-shutdown.json`为准。

## 8. 执行配方与下一步

本轮所有实际参数和UTC在 `*-command.json`、`*-launcher.json`。
主要配方为 `PY OWN/launch.py <label> review.py pytest <label> ... -q`；
外层runner使用隔离runtime；baseline使用TASK9_EXEC_ROOT指向本轮Git副本。
完整后端参数`tests -q`；API291包括四个产品API/来源测试、
四个复制关系/攻击probe以及新增complete-chain测试；
独立integrity和metadata分别从自有probe路径执行。
前端 `frontend_run.py build` / `ui ... e2e/ops.spec.ts` /
`production <label> <scenario>`，后者六场景串行独立启动、ready、执行、TERM、drop。
Node20、命令完整列表、PG URLs、env路径和UTC均可机器复算。

**不可直接执行冻结archive里的固定OWN脚本**：它们是本轮原始运行记录。
新reviewer必须复制到新的UUID目录，更新OWN/ROOT/HEAD/labels/ports/cache、
实体依赖副本和独立Redis，遵循只读source/full manifest和exact资源清理规则。
共享PG需协调而不删他人DB，禁止重写本轮raw。

本轮工程复验不授予真实模型release资格、学生学习效果、分布式规模安全、
多worker生产化、Task10双安装入口/最终安全审计或独立SPEC/CODE结论。
父侧下一步：以本产品freeze及其docs归档提交执行
**fresh WHOLE SPEC（Task8 acceptance至新freeze全Task9）→ PASS后fresh WHOLE CODE**。

## 9. 归档提交前补充

首次 docs 暂存后 `git diff --cached --check` exit2，触发实现者脚本断言，
尚未进入 `git commit` 或 hooks；产品freeze未变。
告警仅原始log/XML、保存的diff上下文和浏览器error-context里的行尾/EOF空白。
不修剪、重写这些raw以求检查绿灯。另以新UTC重跑相同只读check保存raw，
按实际告警路径限定为raw文件，产品与手写报告/脚本没有空白告警；
后续仍执行普通HEREDOC NEW commit，不改git配置、不跳hooks/签名。

`postarchive-staging/`保存新整理脚本、这次只读check输出和机器分类记录三项，
纳入最终597 payload的外层manifest。raw-only592 manifest仍明确是先前scope，
不伪称已包含后发生材料。完整报告更新先写此/tmp，再同字节回写本轮未提交新archive，
只更新本轮新manifest，不动任何既有历史档案。
