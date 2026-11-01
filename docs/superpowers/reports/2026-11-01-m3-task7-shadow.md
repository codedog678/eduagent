# M3 Task7 Shadow 实施与验证记录

状态：实施代理自身检查通过，等待两阶段独立 review；未宣告 Task7 验收或 M3 完成。
批准依据：`docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md` Task7。
分支：`feature/m3-trusted-policy-promotion`，基线：`e486e28`。
仅写入隔离 worktree `/Users/bytedance/Documents/trae_projects/eduagent-m3`；
主 workspace 只用于读取已有 Python 解释器。恢复被停止代理的未提交补丁，
没有重做 Task7，也没有启动 Task8。仅 NEW commit，不 amend、不 push。

## 实施边界

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

## 本代理实际验证

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

## Review 与未覆盖边界

本代理未发现尚未修复的 Task7 自身检查阻塞，但独立 spec/code review 均未完成，
不能替代父代理验收。第一阶段 spec review 已由父代理启动；
第二阶段需针对冻结 NEW commit。

用量 summary 是当前 terminal execution/replay 的诊断，不是跨中断/lease-loss
尝试的完整账单。进程硬终止时未持久化的 token/cost 无法恢复；
数据库 fencing 禁止旧 worker 在失去权限后补写 summary。
未知值不构成 policy qualification 或健康 gate 证据。
filesystem lock 依赖所有 Shadow worker/reaper 可见同一个支持锁的 volume。
这些工程 fixture 不证明外部模型质量、学生学习效果、正式候选发布资格，
也不证明 Docker 部署或 Task8 health observation 已实现。

提交范围为当前 Task7 的 21 个 source/test/Compose 文件和本新报告。
`reports` 已被忽略，仅对本报告执行明确的 `git add -f`，不加入其它历史报告。
完成提交后停留等待两阶段 review，不继续其它 task。
