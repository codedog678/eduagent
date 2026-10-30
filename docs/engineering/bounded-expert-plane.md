# Bounded Expert Plane

## 目标与边界

M2 将 Assessment、Curriculum、Tutor 的草稿计算分发到独立进程，同时保持
`LearningHarness` 的单写边界。它证明的是可恢复、可审计的专家执行，不是把
SQLite learner state 伪装成可水平多写存储。

权威分工：

| 资产 | 权威组件 | Expert Worker 权限 |
| --- | --- | --- |
| Run、attempt、lease、expert job/result | PostgreSQL | 按 token 追加草稿结果 |
| 投递提示 | Redis Streams | 消费、ack；不决定是否可执行 |
| BKT、测验、记忆、计划、公开消息 | Run Worker + Harness SQLite | 无路径、无挂载、无写 API |
| Curriculum 动作与 Tutor 公开回复 | 当前 parent Run Worker | 只能提出未受信草稿 |

Compose 的 Expert Worker 只接收 PostgreSQL、Redis、template 模型配置和角色
能力，不挂载 `distributed_harnessdata`，不含 `HARNESS_STORE_PATH` 或
`OPS_API_TOKEN`。当前演示仍使用同一 PostgreSQL 管理账号；生产部署应拆分
DDL migration 身份与运行身份，并按表授权。

## 执行链路

```text
Run Worker
  -> freeze ExpertJobRequest
  -> PostgreSQL job + outbox
  -> Expert Dispatcher -> Redis hint
  -> Expert Worker claim + independent lease/token
  -> bounded ExpertEngine over snapshot tools
  -> append-only result
  -> parent polls PostgreSQL
  -> ExpertResultAdopter revalidates
  -> parent alone commits learner effect/public reply
```

Redis 消息可重复、延迟或丢失；PostgreSQL claim、parent authority、expert
lease 和 accepted-result 部分唯一索引共同决定有效结果。Inbox 只记录投递，
不能作为跳过执行的业务依据。

## 冻结协议

`ExpertJobRequest` 使用 Pydantic `extra="forbid"` 与不可变模型，字段包括：

- logical key、step、role、objective、plan ID/version 和祖先结果；
- learner/knowledge scope、当前输入、目标与约束；
- policy hash、practice policy、knowledge/profile/review/quiz 快照；
- 脱敏稳定记忆与历史原文、verified source refs；
- model/tool/output/context/attempt 上限与绝对 UTC deadline；
- distributed run ID、parent fencing token、attempt、worker、trace/span。

永不进入 payload：

- API key、数据库 URL、请求 header、provider credential；
- SQLite/repository/history/graph 对象、callback、`ContextVar`；
- parent 可变 steps/events/cache；
- private reasoning 或跨进程无意义的 monotonic deadline。

`ExpertSnapshotBuilder` 先复用公开数据规则，再递归拒绝 secret-shaped key。
Snapshot tools 只能读取 payload 内记录；未知工具、重复 call ID、非法参数、
越权 source ref 和角色不允许的动作都会被拒绝。

## 表与约束

| 表 | 关键约束 |
| --- | --- |
| `distributed_expert_jobs` | `(parent_run_id, parent_token, logical_key)` 唯一 |
| `distributed_expert_leases` | job 一对一；token 单调递增 |
| `distributed_expert_results` | append-only；每个 job 最多一条 accepted |
| `distributed_expert_outbox` | event key 唯一；发布后标记 |
| `distributed_expert_inbox` | `(consumer, message_key)` 唯一 |
| `distributed_worker_registry` | `(worker_id, instance_id)` 唯一 |

同一 parent epoch 只允许一个 active expert job。role 级 queued/running 数量、
单 payload 字节和总 queued payload 字节都在 PostgreSQL admission 中检查。

## 锁序与双重 Fencing

Expert claim 路径的行锁顺序为：

```text
parent run -> parent lease -> parent attempt
-> expert job -> expert lease -> expert results
```

创建 job 时尚无 expert 行可锁，因此在 parent run/lease 后按
`parent -> queued-bytes -> role` 获取 advisory admission lock，再锁 parent
attempt。claim 在 parent attempt 与 expert job/lease 后获取 role advisory
lock。Run cancel 先锁 parent run/lease，再锁全部 active expert job/lease，
最后结束当前 parent attempt。Result submit 锁 parent run/lease、expert
job/lease 和已有 results，但不锁 parent attempt。所有跨平面路径先持有同一
parent run/lease，后续顺序按操作固定，不宣称每种操作共享一条不存在的全局
序列。

结果接受同时要求：

1. parent run 仍为 `running|waiting_expert`；
2. parent owner、deadline、fencing token 与 job epoch 一致；
3. expert job 为 running；
4. expert owner、deadline、fencing token 与提交者一致；
5. schema、role、step、input hash 和 policy hash 一致；
6. 该 job 尚无 accepted result。

因此 parent token 与 expert token 是两个独立权限域。只校验其中一个不足以阻止
旧 parent 采用新结果或旧 expert 向当前 parent 提交。

## 状态机

```text
create -> queued -> running -> completed
                    |       -> queued (retryable failure or expired lease)
                    |       -> terminal_failed
                    |       -> exhausted

any active state -> cancelled | parent_stale
any active state -> terminal_failed (deadline)
```

`accepted` 是 outbox event 类型，不是当前创建路径持久化的 job 状态；
`retryable_failed` 仍作为兼容 claim 状态保留，但当前 retry 路径直接回到
`queued`。

结果 disposition 与 job 状态分离：

```text
attempt result -> accepted
               -> rejected(parent_stale | expert_token_stale |
                           deadline_expired | schema_invalid |
                           result_conflict | ...)
```

Rejected result 仍保留 usage、诊断、worker 和 token。数据库 accepted 不代表
一定被 parent 采用；parent 还会校验当前 source 是否存在、policy 是否仍匹配、
Curriculum action 是否允许，以及 Tutor citation 是否在声明范围内。

## Retry、Deadline 与 Usage

- 只有 provider timeout/unavailable 属于可重试错误；
- schema、权限、预算、source 与 action 错误为 terminal；
- lease 到期会写 uncertain rejected attempt，再按指数退避重新入队；
- deadline、parent stale、cancel 或 attempts exhausted 会关闭 job；
- usage 跨 attempt 累计，parent 在继续前一次性计费；
- token/cost 不可确定时保留 `null/unknown`，不伪造为零；
- worker 被 kill 后远程 provider 仍可能计费，系统不宣称 exactly-once billing。

## Ops 与数据最小化

`/ops/*` 是严格只读 API，提供 Runs、Trace、Expert jobs 和 Workers：

- keyset cursor、limit 和 detail bounds 防止无界查询；
- source refs 只返回数据库记录与冻结 verified refs 的交集；
- 不返回 prompt、current input、history content、draft 正文或 diagnostics；
- usage 按 billable attempt/token 去重；
- 配置 token 时要求 Bearer；无 token 仅允许 loopback。

React Console 位于 `/ops/`，token 只保存在当前标签页 `sessionStorage`。界面有
loading、empty、error、auth、pagination 和 responsive drawer，不包含 retry、
cancel、lease steal 或 payload inspection 控件。

## 运行与复现

```bash
docker compose --profile distributed up --build -d
open http://localhost:3000/ops/

python tools/demo_expert_failover.py
python tools/benchmark_expert_plane.py --requests 30 --concurrency 4
```

真实基础设施测试：

```bash
cd python
DISTRIBUTED_ENABLED=true \
DISTRIBUTED_EXPERTS_ENABLED=true \
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
DISTRIBUTED_REDIS_URL=redis://localhost:6379/15 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
python -m pytest tests/distributed \
  tests/integration/test_distributed_failover.py \
  tests/integration/test_expert_failover.py -q
```

本轮本地验收机未安装 Docker，因此本地没有执行 Compose 容器烟测。
`docker-compose.yml` 已通过支持 alias 的 YAML 解析；同一组 PostgreSQL、
Redis 和真实子进程门禁在本地通过。CI 的 `compose-smoke` job 在 Docker
环境构建完整 profile，提交两次真实 Run，读取 Ops Run/Trace/Expert/Workers，
并在停止 `expert-worker-a` 后要求第二次 Run 仍完成。运行 JSON、解析后的
Compose 配置、容器状态和完整日志作为 Actions artifact 留存。Compose 中
所有分布式 dispatcher、reaper 和 worker 等待 `distributed-api` 完成 schema
初始化并通过 healthcheck 后启动。

## 真实故障证据

两个 demo/benchmark JSON 对应的实现 revision：
`913bfd0aae22e2dfac447604aa3904c2c6ff690a`。生成它们时 worktree clean，diff
SHA-256 为
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
该 revision 是 Task 9 的实现边界；Task 10 的 CI、README 与本文属于随后
发布提交，并由该提交的 GitHub Actions 重新验收，不把旧 JSON 冒充为发布
提交证据。Task 10 发布内容 revision 为
`1c6501c06aa2916daefb108345d75ccec17df4a0`；其后的 metadata-only 提交仅记录
该 revision。

本地环境：Python 3.11.17、PostgreSQL 16.15、Redis 8.10.3、macOS arm64。

| 场景 | 权威结果 |
| --- | --- |
| Expert Worker kill | expert token `[1,2]`；1 accepted、1 `lease_expired` rejected |
| Parent RunWorker kill | late result `parent_stale`；accepted=0；parent result null |
| 重复 Redis 消息 | 同一 job 仅 1 accepted result、1 engine execution |
| cancel waiting parent | run/job cancelled；迟到草稿 rejected；parent result null |

完整集成命令结果：`158 passed in 33.11s`。所有子进程在 `finally` 终止，意外
退出时测试读取并展示 stderr。

本次运行的逐测试 JUnit 证据：
[m2-distributed-integration-913bfd0.xml](evidence/m2-distributed-integration-913bfd0.xml)。
其中包含四个 `test_expert_failover.py` 多进程场景；CI 每次运行也上传新的
`distributed-test-evidence` artifact。归档前仅将本机 hostname 替换为平台
描述，不修改测试数量、名称、结果或耗时。该次运行发生在 Task 10 文档/CI
worktree 上，归属和命令单独记录于
[m2-distributed-integration-913bfd0.json](evidence/m2-distributed-integration-913bfd0.json)，
不套用上述两个 JSON 的 clean-worktree 声明。

Demo 原始输出：
[m2-expert-demo-913bfd0.json](evidence/m2-expert-demo-913bfd0.json)。
它记录 run/job ID、两个 worker PID、parent/expert token、result count、
provider request count 与成本未知状态。独立 SQLite 的 `runs`、`checkpoints`、
`conversation_messages`、`learning_evidence` 前后均为 0，摘要一致。

## 基准

原始输出：
[m2-expert-benchmark-913bfd0.json](evidence/m2-expert-benchmark-913bfd0.json)。

配置：template、30 正式请求、3 warmup、4 workers、role running limit=4。

| 指标 | 结果 |
| --- | ---: |
| enqueue-to-start p50 / p95 | 265.178 / 277.464 ms |
| end-to-end p50 / p95 | 298.874 / 359.932 ms |
| throughput | 63.078 req/s |
| queue peak | 30 |
| errors | 0 |
| parent owner-lock wait proxy | 0.021306 s |
| provider requests / cost | 0 / unknown |

该 benchmark 为 PostgreSQL/Redis + template 的控制面测量。owner-lock 指标使用
真实 `LearningHarness` owner lock 包围一次 `DurableExpertGateway` 等待，但
不是完整业务执行。结果不代表远程模型容量、不包含网络 provider latency，
也不证明多个 Run Worker 可水平写 learner state。

## 已知限制

- learner state 仍为单 SQLite store；远程 Expert wait 会延长 parent 持锁时间；
- PostgreSQL 与 SQLite 无跨库原子事务；
- model call、timeout、kill 与 billing 不具备 exactly-once；
- Compose 演示使用 PostgreSQL 管理账号，生产应使用 migration/runtime 分权；
- Expert steps 仍按 plan dependency 串行，不执行 DAG 并行调度；
- Ops API 是调试面，不是生产级多租户 RBAC/audit 系统；
- 当前证据为 template 控制面，不证明教学质量或真实模型效果；
- M3 trusted policy promotion、shadow/canary 与自动 rollback 不在本里程碑。
