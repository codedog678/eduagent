# M3 Task7 Shadow 实施与验证记录

状态：原 Task7 spec review 已由父线程报告 PASS；code review 发现两个 P1，
之后父真实 PG probe 确认主/专家执行面存在同类时间授权缺陷。
Shadow 与跨执行面 corrective 均已提交；当前 source/test 冻结 HEAD 为
`f4726c841412f10dc8c93b7b0e1cd33c3662a43d`，
九文件矩阵 289 passed、全后端 1290 passed；父新 stage1 独立 spec review
PASS（65 tests、0 skipped），新 stage2 独立 code review PASS（89 checks）。
Task7 已验收；M3 的 Task8–10 和全项目面试就绪验收仍未完成。
批准依据：`docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md` Task7。
分支：`feature/m3-trusted-policy-promotion`。
原实施基线：`e486e28`；本轮 corrective 基线：
`8051d254a7a6ff04da33801506852987dfd65a42`。
仅写入隔离 worktree `/Users/bytedance/Documents/trae_projects/eduagent-m3`；
主 workspace 只用于读取已有 Python 解释器。本轮没有重做 Task7，
没有启动 Task8。仅 NEW commit，不 amend、不 push、不安装依赖。

## 第一轮 Shadow P1 Corrective（08e8a74）

已先阅读既有 Task7 计划、spec §8 和实际 repository/worker/executor/Harness 链路。
用户已批准 brainstorming/writing-plans 与每 task fresh implementer、两阶段 review，
第一轮只修 code review 的两个真实 Shadow P1；父随后授权同类跨执行面纠错，
见本报告末尾追加记录。独立 review 由父线程安排。

源代码和测试冻结范围：
`8051d254a7a6ff04da33801506852987dfd65a42..08e8a74830bb02de90e3d938e2e47a91ed61014f`。
NEW fix commit：
`08e8a74830bb02de90e3d938e2e47a91ed61014f`
(`fix(policy): fence shadow mutations after locks and drain execution cancellation`)。
仅三个文件，277 insertions、37 deletions：

- `python/core/distributed/shadow_repository.py`
- `python/core/distributed/shadow_worker.py`
- `python/tests/distributed/test_shadow_worker.py`

本报告随后另作 NEW docs commit，不修改上述冻结 source/test。

### P1a：等行锁后的时间授权

基线 `renew/complete/fail` 在 UPDATE 的 WHERE 中使用 `clock_timestamp()`。
另一事务只 `SELECT FOR UPDATE` 持锁、不更新行时，WHERE 可在等待前求值；
等待跨过有效期后仍续租或写入不可变 terminal。

修复：三种 mutation 共用 `_locked_live_shadow`，先按 ID `FOR UPDATE`，
获得行锁后另一次 SELECT 取 PostgreSQL `clock_timestamp()`；
同时验证 owner、token、running state、非空且未过期的 lease/deadline。
所有更新使用此次时间，renew 仍截断到 attempt deadline。拒绝事务不改变任何
terminal、lease、owner、token 或更新时间。

审计本 Task7 全部 Shadow claim/lease/terminal/reap mutation：
claim 和 reap 均使用 `SKIP LOCKED`，不会在被锁行上等待；锁前时间只筛选候选，
锁后再取 DB 时间生成 lease/deadline 或回收时间，不能用旧时间延长授权。
enqueue 不修改已有 job 的 lease/terminal。本轮没有 DDL，
schema VERSION 3 与 contract hash、普通只读 startup、显式 migration 均不变。

新增等锁回归为 renew/complete/fail 三种操作，分别覆盖 lease、deadline、
同时过期，共 9 个用例；短有效期为 0.8 秒。测试在 blocker 不更新行的事务中，
通过 `pg_stat_activity.wait_event_type='Lock'` 和 `pg_blocking_pids` 确认确实
等待该 blocker，且发现 Lock wait 时 DB 时间仍有效；随后轮询 DB 时间过期
才释放锁，未靠盲 sleep 推断竞态。另保留 3 个 active mutation 对照。

第一轮也记录了 M1/M2 `repository.py`、`expert_repository.py` 锁前取时间的
模式，当时尚未做跨执行面复现或修复。随后父实际 probe 得到有效的 4 failed，
已从审计疑点升级为确认缺陷，并由本 corrective owner 完成修复。
第一轮范围决定及其 199/20 绿灯只作为历史证据，不代表跨执行面当前 PASS。

### P1b：取消 drain 与 Store Lock

基线用外层 `wait_for` task 隐式持有 `_execute`。Python 3.11.17 下，
deadline 先取消内部执行，SDK 延迟清理时 heartbeat 又失租，
finally 再取消外层 wait_for，可能返回而内部仍活跃；重复外部取消同样不安全。

修复：显式持有真实 `_execute` task，以独立 deadline timer 与 heartbeat
竞争结束事件。finally 只向尚未取消的 task 发一次 cancel；
`shield(gather(...))` 循环等待真实执行、heartbeat、timer 全部退出。
等待期间记录外层重复取消，drain 完成后才释放 filesystem lock 并传播取消。
不在失租或 deadline 后写 terminal；正常 terminal cleanup 只在真实执行退出、
summary 事务成功后进行。

新增 8 个真实链路回归：`LearningTaskExecutor`、`AgentOrchestrator`、
`LearningHarness`、`LLMService` 均保留，只有 SDK `create` 被 stub；
SDK 取消清理由事件控制。覆盖 deadline/heartbeat overlap、lease loss、
external cancel、repeated cancel，分别验证重试接管和 exhausted terminal reaper。
测试直接保留 SDK 所在真实执行 task 引用：清理未放行时旧 run_once/执行 task
不能退出，新 worker 只能取得 DB claim、不能取得 filesystem lock 或调用模型，
terminal reaper 不能删活跃 store；放行后旧执行完全退出，新真实 executor
正常完成接管，或 terminal reaper 正常删除。后续 SDK 调用还断言旧执行 task
已 done，主 Run 结果不变。既有真实 SDK 正常成功/失败对照仍在矩阵中。

取消边界：协作 SDK/执行若永远不退出，worker 就永远等待并持锁；
不会伪称强行终止、释放锁让新执行重叠，或让 reaper 删除活跃 store。
重复 cancel 不能变成中断 Harness/SDK 清理的第二次内部 cancel。
进程硬终止、独立 volume/不支持锁的文件系统不在此协作取消保证内。

### 本轮红绿证据

每个运行独立 createdb，EXIT dropdb；使用
`DISTRIBUTED_TEST_DATABASE_URL`，未使用 `DATABASE_URL`。
PostgreSQL 16 `127.0.0.1:55432` postgres 无密码，
Redis `127.0.0.1:56379/0`，main 的既有 Python 3.11.17 解释器，
`PYTHONPATH=<worktree>/python`、`TZ=UTC`。

| 运行 | 结果 | 秒 | Source/Test 时点 |
| --- | --- | ---: | --- |
| 两 P1 基线红灯 | 13 failed、7 passed、0 skipped、36 deselected | 18.92 | 8051d25 source + 新 20 用例 |
| 首次 corrective 绿灯 | 20 passed、0 skipped、36 deselected | 13.76 | corrective source，未提交 |
| 最终测试断言绿灯 | 20 passed、0 skipped、36 deselected | 13.83 | 最终 source/test，未提交 |
| 冻结 HEAD 八文件矩阵 | 199 passed、0 skipped、无 deselect | 46.42 | 08e8a748 source/test |
| 冻结 HEAD fresh DB 重复 | 20 passed、0 skipped、36 deselected | 13.34 | 08e8a748 source/test |

红灯 9 个 PG case 均为过期却未抛 `ShadowFencingViolation`；
4 个 SDK case 为 deadline overlap/repeated cancel 的 retry/exhausted 路径。
其中 deadline exhausted 已可重获锁；其它 case 外层已 done 而内部未安全退出。
repeat retry 的失败 teardown 还出现等待超时，未误报为正常退出；
之后仅强化后续 SDK 调用必须等待旧 task done 的断言和失败 teardown，
不改变测试触发条件。其余 7 个对照通过。最终两个 frozen HEAD 运行没有
failure/error/skipped 或 warning；结果不相加。第一轮当时未复跑全后端；
跨执行面扩展修复之后已在新冻结 HEAD 运行完整后端，见追加记录。

八文件仍为原矩阵：
`test_shadow_worker.py` 56（原 36 + 新 20）、
`test_shadow_usage.py` 13、`test_runtime_schema_startup.py` 18、
`test_schema_migration.py` 8、`test_worker.py` 8、`test_repository.py` 35、
`test_expert_repository.py` 33、`test_policy_pinning.py` 28。

五份 JUnit 已用 XML parser 核对 tests/failures/errors/skipped。
红灯：`/tmp/eduagent-m3-t7-fix-red.xml`；
其余：worktree 的 `docs/superpowers/reports/task7-fix-{green,green-final,matrix,repeat}.xml`
（ignored 运行产物，不加入提交）。数据库查询确认本轮 `eduagent_m3_t7_fix_%`
临时 DB 均已清理。`git diff --check` 通过。
Docker 不可用，本轮未执行 Docker、不改 Compose，不把静态 YAML 或工程
fixture 称为 Docker 部署、正式 release 模型证据、Task7 验收或 Task8 证据。

第一轮当时状态：Shadow corrective 自身检查完成，等待独立复审。
当前跨执行面 source/test 冻结及待复审状态以追加记录为准。未启动 Task8。

## 原实施边界（8051d25 历史记录）

- PostgreSQL 是 Shadow 队列的权威。主 Run 完成事务依据其持久化的部署快照
  入队，唯一键 `(parent_run_id, deployment_id)` 抑制重复。后续 head 变更
  不改变已冻结的候选、输入哈希、输入引用、部署版本和 binding。
- claim 使用 `FOR UPDATE SKIP LOCKED`，递增 fencing token/attempt；
  renew/complete/fail 同时验证 owner、token、状态、数据库 lease 和 deadline。
  重试由数据库时间决定，最多三次；调用者时钟不能提前回收或延长 deadline。
- 候选通过真实 `LearningTaskExecutor`、`AgentOrchestrator`、`LearningHarness`
  执行，使用明确的 `shadow` authority 和 inline experts。生产/rehearsal
  executor、普通 durable expert gateway/repository 不接受 Shadow capability。
- Shadow executor 不接收主 harness 路径、不接收 durable expert gateway，
  且拒绝 `enable_db_logging=True`，避免候选 raw 内容写入普通业务数据库日志。
  默认 orchestrator 不调用 `init_database`，Harness 使用同步 learner 路径。
- store 只能是服务端派生的
  `root/shadow/<deployment>/<parent-run>/harness.sqlite3`。
  UUID/namespace、symlink/root escape 和持有锁要求均 fail closed。
  锁 inode 在 disposable store 外，旧执行取消完成前不释放；
  新 worker 和 reaper 不能同时写入或清理旧 worker 的活跃 store。
- terminal summary 事务成功后才删除 store；事务失败保留现场。
  reaper 分页覆盖超过 100 个 terminal jobs，跳过仍持有 filesystem lock 的目录。
  冻结字段受 SQL trigger 保护，terminal summary append-only。
- durable summary 只保留固定状态枚举和有限非负数字/null：
  token、model/tool calls、cost、latency。错误码来自 allowlist。
  `structured_result="unavailable"`，不把业务完成自动等同于 schema-valid。
  原始学生输入、模型回复、provider/model 标识、密钥和异常正文不写入 summary。
  Task7 不写 `PolicyObservationRecord`，不实现 Task8 health/rollback。
- 新增 Shadow CLI/Compose worker 和 reaper，只挂载
  `shadow_harnessdata:/app/shadow`，依赖显式 migrate 完成。
  普通 startup 仍只读检查 schema marker，不恢复 auto-DDL。
  迁移新增 `max_attempts` 等列并更新 contract hash；上线仍需 drain 后显式 migrate。

## 真实用量链路

`LLMService.tool_turn` 消耗 model 预算，但不记录 `model_turn`。
Tutor 使用 `after_model(..., usage=...)`；generate 使用 `model_usage`；
inline expert 使用 `expert_usage_charged` 聚合。Shadow 汇总只消费这三种来源，
不把 `budget_used` 或不存在的 `model_turn` 再计为用量。

真实 SDK stub 保留 executor/orchestrator/harness/runtime/accounting 链路，
只有 SDK `create` 被替换，不调用外部模型、不使用真实模型凭据：

| 场景 | Model | Tool | Input Token | Output Token | Cost | Terminal |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 完整 provider usage | 3 | 2 | 41 | 21 | null | completed |
| 最后一轮 token 未知 | 3 | 2 | null | null | null | completed |
| 真实执行后异常 | 3 | 2 | 41 | 21 | null | failed |
| 最后一轮 provider 异常 | 3 | 2 | null | null | null | failed |

两次 tool 计数为 coordinator delegation 和 quiz-context lookup。
失败仍保留已知 calls；未知 token 不伪造完整总量，未知 cost 不伪造 0。
零 model calls 时 token/calls 为已知 0，但没有 provider cost 证据仍为 null。
清理断言使用执行前保存的路径，避免 `path_for` 重新创建目录。

## 原实施代理实际验证（历史）

所有基础设施运行都单独 `createdb`，使用 EXIT `dropdb`，不共享数据库。
PostgreSQL 16：`127.0.0.1:55432`，用户 `postgres`，无密码；
Redis：`127.0.0.1:56379/0`。解释器来自主 workspace 的既有 `.venv`，
`PYTHONPATH` 仅指向隔离 worktree，`TZ=UTC`。

| 运行 | 实际结果 | 秒 | 范围 |
| --- | --- | ---: | --- |
| 恢复后原始 SDK stub | 3 passed，0 skipped，25 deselected | 1.26 | 已继承 after_model/unavailable 修正 |
| 新 guard 红灯 | 2 failed，23 passed，0 skipped，24 deselected | 3.04 | 未知 cost 被写 0；Shadow DB logging 构造未拒绝 |
| 最终全后端 | 1180 passed，0 skipped | 125.90 | `python/tests`，真实 PG/Redis |
| 最终 Task7 相关专项 | 179 passed，0 skipped | 31.60 | 以下八个文件，未 deselect |

计数重叠，不可相加；表中不是父代理的运行结果。
全后端只有历史 `TestAgent` 带 `__init__` 的 collection warning。
两个最终 JUnit 均实际解析，failure/error/skipped 数量均为 0：
`/tmp/eduagent-m3-task7-backend.xml`、`/tmp/eduagent-m3-task7-target.xml`。
以上两个运行均在本代理最后的 source/test 修改后启动；之后仅新增本报告。
它们是待提交补丁的检查，不是提交后冻结 HEAD 的独立检查。

父代理另报告独立 fresh DB 全后端 `1180 passed`、0 skipped、
一个已知 collection warning，128.67 秒，EXIT trap 已清理；
该运行不是最终冻结 HEAD 检查，且收集时点不保证包含所有后来追加测试。
不以它替代本代理完整收集最新 Task7 测试的专项结果。

专项构成：Shadow worker 36、Shadow usage 13、runtime startup 18、
schema migration 8、worker 8、repository 35、expert repository 33、policy pinning 28。
包含真实 Redis duplicate delivery、真实 PostgreSQL row lock/takeover、
真实 executor 成功/失败、SQL identity/terminal guards 和 Shadow CLI subprocess
在 expert poll 持锁期间无 startup DDL 的检查。

可复现 runner，在隔离 worktree 根目录运行：

```bash
run_task7_tests() (
  set -e
  DB="eduagent_m3_t7_$(date +%s)_${RANDOM}"
  createdb -h 127.0.0.1 -p 55432 -U postgres "$DB"
  trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
  export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
  export DISTRIBUTED_TEST_REDIS_URL="redis://127.0.0.1:56379/0"
  export PYTHONPATH="$PWD/python"
  export TZ=UTC
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
    -m pytest "$@" -q --tb=short
)

run_task7_tests python/tests \
  --junitxml=/tmp/eduagent-m3-task7-backend.xml

run_task7_tests \
  python/tests/distributed/test_shadow_worker.py \
  python/tests/distributed/test_shadow_usage.py \
  python/tests/distributed/test_runtime_schema_startup.py \
  python/tests/distributed/test_schema_migration.py \
  python/tests/distributed/test_worker.py \
  python/tests/distributed/test_repository.py \
  python/tests/distributed/test_expert_repository.py \
  python/tests/distributed/test_policy_pinning.py \
  --junitxml=/tmp/eduagent-m3-task7-target.xml
```

`git diff --check` 通过。系统 `python3` 的已有 PyYAML 静态解析通过：
Shadow commands、root、专用 volume、migrate gates 和其它服务无 Shadow mount。
未安装依赖。Docker 不可用，未运行 `docker compose config` 或 Docker 服务；
静态 YAML 不是 Docker execution，也不是部署验收。

## 原实施 Review 与未覆盖边界（历史）

原实施代理自身检查当时未发现这两个 P1，不能替代独立 review。
父线程后来报告第一阶段 spec review PASS，第二阶段 code review 发现 P1a/P1b；
本轮修复与待复审状态以上文为准。

用量 summary 是当前 terminal execution/replay 的诊断，不是跨中断/lease-loss
尝试的完整账单。进程硬终止时未持久化的 token/cost 无法恢复；
数据库 fencing 禁止旧 worker 在失去权限后补写 summary。
未知值不构成 policy qualification 或健康 gate 证据。
filesystem lock 依赖所有 Shadow worker/reaper 可见同一个支持锁的 volume。
这些工程 fixture 不证明外部模型质量、学生学习效果、正式候选发布资格，
也不证明 Docker 部署或 Task8 health observation 已实现。

原实施提交范围为 Task7 的 21 个 source/test/Compose 文件和本报告。
`reports` 已被忽略，仅对本报告执行明确的 `git add -f`，不加入其它历史报告。
完成提交后停留等待两阶段 review，不继续其它 task。

## 跨执行面 P1 Corrective 追加（f4726c8）

### 确认缺陷与范围

父修正 fixture 参数后，真实 PostgreSQL probe 的最终有效运行是
4 failed，5.58 秒：primary renew/fail 未拒绝，expert renew 未拒绝，
expert submit_result 返回 accepted=True。此前 probe 的 fixture 参数错误
不是产品缺陷，不作为红灯证据；本实现不导入 `/tmp` probe。

父授权同一 corrective owner 修主/专家 lease/deadline 相关入口，不另起 Task、
不扩展到非 lease 业务。新增真实 fixture 回归覆盖上述四种拒绝场景，并进一步
覆盖最后的 attempt/step/job/result/advisory 锁；所有可能阻塞的授权相关锁均
必须先返回，再取独立 PostgreSQL `clock_timestamp()`，不能只移到首锁之后。

NEW source/test commit：
`f4726c841412f10dc8c93b7b0e1cd33c3662a43d`
(`fix(distributed): validate live authority after all blocking locks`)。
只有以下三个文件，448 insertions、87 deletions：

- `python/core/distributed/repository.py`
- `python/core/distributed/expert_repository.py`
- `python/tests/distributed/test_lease_lock_time.py`

整体 corrective source/test 范围为
`8051d254a7a6ff04da33801506852987dfd65a42..f4726c841412f10dc8c93b7b0e1cd33c3662a43d`，
包含前述 `08e8a74` Shadow 修复；后续只提交本报告，source/test 不再改变。
无 DDL，schema VERSION 3、contract hash、startup/migration 路径均未修改。
父已独立修改两篇 M1/M2 工程文档，本 owner 不暂存、不提交这些修改。

### 最后一个锁之后校验

| 入口 | 取 DB 时间前已取得的锁 | 授权或时间用途 |
| --- | --- | --- |
| primary claim | run、lease | 新 attempt/lease 起点使用锁后时间 |
| primary renew/committing/complete/fail | run、lease、attempt | 完整 active state、owner、token、lease、attempt owner/status/finished/deadline guard |
| primary start_step/complete_step | run、lease、step（存在时）、attempt | step 锁不能落在 guard 之后 |
| primary requeue_expired | run、lease、owned attempt | 重新判断过期并写回收时间；`_finish_attempt` 重入已持有的 attempt 锁 |
| expert create_or_replay | parent run/lease、parent/queue/role advisory、parent attempt、旧 epoch jobs/leases、existing job | 全部预锁之后验证授权，再关闭旧 epoch 或 admission/replay |
| expert claim | parent run/lease/attempt、job、expert lease、role advisory | 新 parent/job deadline guard 和 lease 起点 |
| expert renew | parent run/lease/attempt、job、expert lease | 完整双层 authority guard |
| expert submit_result/fail_attempt | parent run/lease/attempt、job、expert lease、results | 完整 parent attempt/deadline 与 expert guard；过期只追加 rejected usage，不改 job terminal |
| expert terminal/reap_expired | parent run/lease/attempt、job、expert lease、results | terminal 必须在最后 result 锁之后验证；reaper 使用同一 parent attempt/deadline guard |

primary `_assert_active_lease` 自己锁 attempt、取新 DB 时间并返回此次时间；
新增原来缺失的 attempt deadline 校验。`_finish_attempt` 对 worker/reaper
重入本事务已取得的同一行锁，不在授权检查后等待新的 attempt 锁。
operator cancel、telemetry、inbox/outbox 等非 live lease 授权流程不人为扩范围。

expert submit_result 原来没有父 attempt 锁或完整 parent deadline 校验，
现与 fail_attempt 共用 `_authority_rejection` 的完整 parent guard；
拒绝仍保留 append-only usage，不写 accepted draft、不改变 terminal。
create 的旧 epoch helper 只预锁返回 pairs，不在等待后续锁前修改 ORM 行。

末锁审计还真实复现了同一 live state guard 的 ORM 缓存漏洞：
expert identity 在等锁前读入，之后 `FOR UPDATE` 默认不覆盖缓存；
持锁事务将 job 改为 cancelled 后，claim/renew/result/fail 仍可能按旧状态授权。
4 个真实等锁测试均红灯；job 加锁查询加入 `populate_existing=True`，
授权同时使用最新 DB 时间和锁返回的最新 DB 状态。

### 真实 PG 回归与红绿

新增文件共 90 个用例：primary 31、expert 59。包含 70 个过期/末锁覆盖、
12 个 active mutation 对照、4 个 claim/reaper 锁后时间起点检查、
4 个锁后 job 状态刷新检查。短期限 0.8 秒：
观察事务先 `pg_stat_clear_snapshot()`，再确认 `wait_event_type='Lock'`
且 `pg_blocking_pids` 包含本 blocker PID，并确认发现等锁时期限仍有效；
确认阻塞之后才由数据库等待跨期、释放锁，不靠盲 sleep 推断竞态。
terminal/attempt/step/accepted result 与 active 对照断言均保留。

每次运行独立 createdb + EXIT dropdb，PG16/Redis/只读 main 解释器配置同上，
另外设置 `PYTHONDONTWRITEBYTECODE=1`。JUnit 实际用 XML parser 核对，
所有运行 errors/skipped 均为 0：

| 本实现运行 | 实际结果 | 秒 | Source/Test 时点 |
| --- | --- | ---: | --- |
| 首轮跨执行面红灯（含 7 个 create fixture 哈希冲突） | 70 failed、12 passed | 74.11 | 08e8a74 source + 新测试；7 个构造错误不计产品缺陷 |
| 修正 fixture 的有效红灯 | 70 failed、12 passed | 73.86 | 08e8a74 source + 82 用例 |
| 首次跨执行面绿灯 | 82 passed | 75.70 | now/attempt 修复，未提交 |
| 状态缓存专项红灯 | 4 failed、86 deselected | 4.72 | now 修复后、populate_existing 前 |
| 最终跨执行面绿灯 | 90 passed | 83.92 | 最终 source/test，未提交 |
| 冻结 HEAD 九文件矩阵 | 289 passed、无 deselect | 130.54 | f4726c841412f10dc8c93b7b0e1cd33c3662a43d |
| 冻结 HEAD 全后端 | 1290 passed、无 deselect | 226.70 | 同一冻结 source/test |

82 是中间测试收集与绿灯，不是最终冻结收集；之后增加 4 个锁后取时检查和
4 个状态刷新检查，`f4726c8` 最终新文件收集 90 项。
冻结矩阵 289 = 原八文件当前 199 + 新文件 90；全后端 1290 也包含完整 90 项。
矩阵和全后端均在 NEW source/test commit 后运行，不用中间 82 替代冻结验证。

有效 70 红灯中，68 个为等锁后仍授权/未回收；submit_result/reaper 的
attempt 场景则因原实现根本未锁 attempt 而提前返回，是缺失授权锁的真实失败。
4 个状态红灯为 cancelled 后仍 claim/renew、accepted result 或 job mutation。
最终矩阵零 warning；全后端仅已有的 `TestAgent.__init__` collection warning。
各计数重叠，不相加，不把历史 179/199/20 绿灯冒充当前版本证明。

七份 JUnit 位于 worktree ignored 的
`docs/superpowers/reports/task7-crossplane-{red,red-final,green,state-red,green-final,matrix,backend}.xml`，
均未加入提交。查询确认本实现的 `eduagent_m3_lock_%`、
`eduagent_m3_state_%`、`eduagent_m3_t7_cross_%` 临时数据库全部清理。

可复现：复用上文 runner，加 `PYTHONDONTWRITEBYTECODE=1`，
专项传 `python/tests/distributed/test_lease_lock_time.py`；
矩阵为上文八文件加该新文件；全后端仍传 `python/tests`。
这些工程 fixtures 无外部模型请求，不构成正式 release 模型证据。

### 父独立证据与待 Review

以下为父报告的独立运行，不计入本实现 pytest 计数：

- Shadow corrective：20 passed、36 deselected、13.33 秒；
  当时 source 为 `08e8a74` 且未改变，fresh DB 已清理；
  JUnit `/tmp/eduagent-m3-shadow-fix-independent.xml`。
- 跨执行面原四条 probe：最终从 4 failed 变为 4 passed、5.25 秒；
  当时是 staged 跨执行面补丁，不声称冻结 HEAD；
  fresh DB 已清理，JUnit `/tmp/eduagent-m3-crossplane-green.xml`。

父在精确 source HEAD `f4726c841412f10dc8c93b7b0e1cd33c3662a43d`
的新 fresh stage1 spec review 已报告 PASS，65 tests、0 skipped；
新的 fresh stage2 code review 已启动，结论尚未返回。
本 owner 的绿灯、父 probe 与原 spec review PASS 均不能替代新两阶段最终判定。
当前为 corrective 实施与自身验证完成、独立复审待定，不宣告 Task7 验收 PASS。
P1b 的取消边界保持第一轮描述：协作取消不退出就持续持锁，不伪称强制终止。
只停止于 Task7，不启动 Task8，不 push，不 amend。

## 父线程最终验收闭环

两阶段独立审查均针对 `f4726c841412f10dc8c93b7b0e1cd33c3662a43d`
的冻结 source/test，范围为 `8051d25..f4726c8`，包含两轮纠错。
审查前后 Python source/test 哈希一致；后续 `cf7a8e9` 只提交报告，
父同步 M1/M2 工程文档中的末锁时钟、parent attempt 和状态刷新说明。

| 独立审查 | 范围 | 实际结果 | 秒 |
| --- | --- | ---: | ---: |
| Stage1 spec | Shadow 新回归 | 20 passed，36 deselected | 13.42 |
| Stage1 spec | 跨执行面关键权限 | 24 passed | 22.27 |
| Stage1 spec | 隔离、固定策略、只读启动 | 21 passed | 4.24 |
| Stage2 code | Shadow 新回归 | 20 passed | 13.79 |
| Stage2 code | 跨执行面代表矩阵 | 51 passed | 43.22 |
| Stage2 code | 额外 attempt 撤销探针 | 12 passed | 2.128 |
| Stage2 code | 心跳异常、内部超时、重复取消探针 | 2 passed | 0.769 |
| Stage2 code | Run/Expert 并发锁序探针 | 4 passed | 0.950 |

各组无 failure/skip；两阶段分别 PASS，未发现尚未修复的 blocking P1/P2。
Stage2 共 89 个独立检查，包含测试与额外探针，不能与实现矩阵或全后端相加。
父另实际解析冻结全后端 JUnit：1290 tests、0 failure/error/skipped，
226.686 秒；不是第二阶段重跑的全后端。所有临时数据库均已清理。

据此验收 Task7 的工程实现及同类跨执行面纠错，允许推进已批准 Task8。
真实 SDK 链路中的供应商请求由受控 stub 替代；没有新增外部模型请求，
不证明正式候选资格、真实学生效果或 Docker 动态部署。协作取消若不退出
仍持续持锁，硬终止未持久化的用量仍未知；这些边界不因审查 PASS 改变。
