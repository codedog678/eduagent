# Distributed Run Plane

## 目标

M1 将 Run 的接收、投递、租约、恢复和观测迁移到 PostgreSQL 与 Redis
Streams，同时复用现有 `LearningHarness`。它用于证明多进程调度和故障恢复，
不把共享 SQLite 教学状态包装成可水平多写的存储。

## PostgreSQL 保证

PostgreSQL 是以下状态的唯一真相来源：

- Run 身份、请求指纹、状态、结果和错误；
- attempt 次数、Worker、完成原因和 fencing token；
- step intent、输入 hash、结果和接管后的 token；
- lease owner、到期时间和单调递增 token；
- transactional outbox、delivery inbox 和 durable spans。

所有 Run/Lease 复合变更使用统一的 `run -> lease` 行锁顺序。续租、step
提交和最终提交均校验当前 owner/token，并以 PostgreSQL 数据库时钟判断租约
是否有效。过期 Worker 即使继续运行，也不能提交 PostgreSQL 结果。

## Redis 不保证

Redis Streams 只加速投递，不保存业务真相：

- 消息可以重复、延迟或在消费者死亡后进入 pending；
- Dispatcher 可能在 `XADD` 成功、写回 outbox 前崩溃并再次发布；
- consumer group 和 pending reclaim 用于恢复投递；
- 是否允许执行由 PostgreSQL Run claim/state 决定。

Inbox 是投递观测与诊断记录。它不能因为“见过消息”就跳过仍可 claim 的
Run，否则 Worker 在写入 inbox 后崩溃会造成永久漏执行。

## M1 业务状态边界

教学状态仍保存在一个共享 SQLite 文件：

- Worker 只有持有有效 PostgreSQL lease 时才尝试执行；
- 每次业务执行临时打开 `LearningHarness`，完成后关闭并释放文件锁；
- 文件锁保证任何时刻只有一个 Worker 打开该 SQLite；
- 接管 Worker 使用相同 `learner_id + request_id` 重放，复用原有请求指纹与
  SQLite 事务幂等。

PostgreSQL fencing 不能回滚已发生的 SQLite 提交。若 Worker 在 SQLite
提交后、PostgreSQL 完成前死亡，接管 Worker 会重放同一个请求并读取已保存
结果。M1 的故障测试验证该路径只产生一个 SQLite 业务提交，但不宣称：

- PostgreSQL 与 SQLite 之间存在跨库原子事务；
- 模型调用或其他网络副作用恰好一次；
- SQLite 教学状态支持多个 Worker 水平并发写入。

取消是 best-effort。Control Plane 会终止 Run 租约并阻止后续 PostgreSQL
提交；已经完成的 SQLite 事务或外部调用无法被撤销。

## 故障矩阵

| 故障 | 恢复机制 | 可验证结果 |
| --- | --- | --- |
| API 写 Run 后崩溃 | Run 与 outbox 同一 PostgreSQL 事务 | Dispatcher 后续补发 |
| Dispatcher 发布后崩溃 | outbox 未标记时允许重复发布 | claim/state 拒绝重复执行 |
| Redis 暂时不可用 | outbox 保留未发布事件 | Redis 恢复后重试 |
| Worker 执行中死亡 | lease 到期，Reaper 写 retry outbox | 另一 Worker 使用新 token 接管 |
| 心跳丢失 | Worker 标记 lease lost 并停止提交 | 旧 token 被 fencing |
| 两 Worker 竞争提交 | owner/token/数据库时钟条件更新 | 仅当前租约可完成 |
| 运行中取消 | 清 owner/expiry，attempt 记 cancelled | 迟到提交被拒绝 |
| SQLite 已提交后死亡 | 相同 request ID 重放 | 返回已保存结果，不重复业务提交 |

## 本地命令

普通单进程模式：

```bash
docker compose up --build
```

分布式 Run Plane：

```bash
docker compose --profile distributed up --build -d
curl --fail http://localhost:8890/api/health
```

真实 PostgreSQL/Redis 集成测试：

```bash
cd python
DISTRIBUTED_ENABLED=true \
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
DISTRIBUTED_REDIS_URL=redis://localhost:6379/15 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
python -m pytest tests/distributed tests/integration/test_distributed_failover.py -q
```

故障恢复演示：

```bash
python tools/demo_distributed_recovery.py
```

运行状态、Trace 与指标：

```text
GET  http://localhost:8890/api/distributed/runs/{run_id}
GET  http://localhost:8890/api/distributed/runs/{run_id}/trace
POST http://localhost:8890/api/distributed/runs/{run_id}/cancel
GET  http://localhost:8890/metrics
```

`eduagent_distributed_runs_by_status` 每次抓取时从 PostgreSQL 聚合，因此在
API、Dispatcher、Reaper 和 Worker 分属不同进程时仍表示权威当前状态。
各进程内 counter 只用于该进程的事件诊断，不作为跨进程累计真相。

## 验收证据

验收必须同时保留：

- foundation、runtime、control plane 和演示代码的 Git commit；
- 完整后端回归及真实 PostgreSQL/Redis 集成测试输出；
- 强杀 Worker 后的 Run ID、两次 attempt、两个 fencing token；
- 跨进程 durable trace 与 Prometheus 指标快照；
- SQLite 中同一请求的业务效果计数。

仅有 mock 单元测试或架构说明不能证明 M1 完成。
