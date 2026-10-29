# EduAgent 分布式 Agent Harness 与可信策略晋级总体设计

日期：2026-10-29
状态：已确认，先实施 M1
目标岗位：Agent Harness / Agent 算法，双轨兼顾

## 1. 背景与事实基线

EduAgent 当前已经具备以下可验证能力：

- 单进程 `LearningHarness`：请求指纹、幂等重放、SQLite 原子提交、失败回滚、检查点和执行轨迹。
- 有界 Agent 运行时：模型/工具/上下文/时间预算，严格工具 schema、权限、来源和学习者范围校验。
- 跨会话记忆与复合任务：FTS5/向量混合检索、Coordinator、专家草稿、有限重规划和等待学生接续。
- 真实模型评测与 RSI：开发/留出隔离、配对比较、预算账本、不可变策略、回滚和失败留档。
- 当前断网全量回归：在 `python/` 目录运行得到 `511 passed, 1 warning`。

当前短板不是缺少普通 Agent 功能，而是：

1. SQLite、文件锁和进程内队列限制了多进程执行；进程崩溃只能整轮重试。
2. Trace 已有丰富业务事件，但没有统一 span、服务指标、跨 Worker 因果链和可视化回放。
3. RSI 候选已有开发集改善信号，但 Judge 仍存在布尔值与理由冲突、结构字段缺失，不能可信晋级。
4. README、简历材料和历史指标存在过期数字，招聘方难以快速验证当前能力。

本设计先建立真实、可复现的技术闭环。简历改写不属于本轮 M1 范围。

## 2. 目标

### 2.1 总体目标

将 EduAgent 从单进程教学 Agent 演进为：

- 具有持久任务、租约、接管、幂等提交和背压的分布式 Agent Harness；
- 具有明确写入所有权和隔离专家 Worker 的多 Agent 执行平台；
- 具有标准 Trace、服务指标、故障回放和内置 Ops Console 的可观测系统；
- 具有可信 Judge、开发/留出/Shadow/回滚链路的策略改进平台。

### 2.2 面试证明目标

Harness 方向应能用证据回答：

- 消息重复、Worker 崩溃、迟到结果和提交竞争时，为什么不会重复修改业务状态？
- Run、Step、模型、工具和专家调用如何追踪、恢复和回放？
- 单进程正确性如何演进到多进程，而不破坏原有事务边界？

Agent 算法方向应能用证据回答：

- 数据、策略、Judge、代码和模型版本如何绑定？
- unknown、Judge 无效、重复样本和留出泄露如何处理？
- 候选凭什么晋级、Shadow 如何验证、何时自动回滚？

## 3. 方案选择

### 3.1 备选方案

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| 仅 API/Run Worker 分离 | 可靠执行语义扎实，改动可控 | Agent 分发信号较弱 | 不足以完成双轨目标 |
| 所有 Agent 全面微服务化 | 形式直观 | 跨服务事务、状态所有权和运维复杂度过高 | 不采用 |
| 分布式执行底座 + 有界专家 Worker | 先解决可靠性，再分发无副作用计算 | 需要分阶段实施 | 采用 |

### 3.2 基础设施选择

- PostgreSQL 保存 Run、Step、Lease、Outbox、策略和部署状态，是唯一权威状态。
- Redis Streams 负责低延迟任务投递、消费者组和积压管理，不作为业务真相来源。
- 现有 SQLite 模式保留，继续服务零依赖演示、单元测试和本地开发。
- 不采用 Temporal。当前目标是展示并验证自研 Harness 语义，而不是将核心机制委托给外部工作流引擎。

## 4. 目标架构

```text
Client
  -> FastAPI Control Plane
       -> PostgreSQL
          run / step / lease / outbox / policy / deployment
       -> Redis Streams
          run jobs / expert jobs / result notifications

Run Worker pool
  -> Durable Coordinator
       -> deterministic local steps
       -> Expert Gateway
            -> Assessment Worker pool
            -> Curriculum Worker pool
            -> Tutor Worker pool
       -> Committer
            -> PostgreSQL single transaction

Observability
  -> Trace Store / Replay API
  -> OTLP exporter (optional)
  -> Prometheus metrics
  -> React Ops Console
```

### 4.1 状态所有权

- Control Plane 接收请求、校验幂等键、创建 Run，不直接执行 Agent 链。
- Run Worker 持有 Run 租约，负责 Coordinator 状态机和最终提交。
- Expert Worker 只产生结构化草稿、来源、usage 和诊断，不直接写学习状态。
- 只有持有当前 fencing token 的 Run Worker 可以提交测验、学习状态、公开回复和最终结果。
- Redis 消息表示“需要处理”，不能证明业务已经完成。

### 4.2 交付语义

系统采用“至少一次投递、效果恰好一次”：

- Redis、网络和 Worker 都可能造成重复投递。
- `run_id + step_id + input_hash` 标识同一逻辑步骤。
- PostgreSQL 条件更新、唯一约束和 fencing token 拒绝重复或过期提交。
- 外部模型调用不承诺恰好一次；取消、超时或响应丢失仍可能产生费用，账本必须保留。

## 5. 数据模型

M1 最小表：

| 表 | 作用 | 关键约束 |
| --- | --- | --- |
| `distributed_runs` | 逻辑 Run 与状态机 | `(learner_id, request_id)` 唯一；保存 input hash |
| `distributed_run_attempts` | 每次租约执行尝试 | attempt 单调增加 |
| `distributed_steps` | 可恢复步骤与结果 | `(run_id, step_id, input_hash)` 唯一 |
| `distributed_leases` | owner、到期时间、fencing token | token 单调增加 |
| `distributed_outbox` | 事务后待发布事件 | 幂等 event key |
| `distributed_inbox` | 已接收消息去重 | consumer + message key 唯一 |
| `distributed_trace_spans` | 跨进程公开 span | trace/span/parent 关系 |

M2 增加专家 Job/Result；M3 增加 Campaign、Policy Version、Deployment 和 Health Window。

所有表名使用独立前缀，避免在 M1 未验证前替换现有 SQLite 权威链路。

## 6. Run 状态机

```text
accepted -> queued -> leased -> running
                    -> waiting_expert -> running
                    -> committing -> completed
                               \-> retryable_failed -> queued
                               \-> terminal_failed
                               \-> exhausted
                               \-> cancelled
```

状态转换必须满足：

- 每次转换由 PostgreSQL 条件更新保护。
- `leased/running/waiting_expert/committing` 必须绑定 owner、lease deadline 和 fencing token。
- 完成、终止失败、耗尽和取消为终态；重试创建新 attempt，不覆盖旧证据。
- 状态和对话状态继续分离，`completed + awaiting_student` 仍是合法组合。

## 7. 可靠执行协议

### 7.1 接单与投递

1. API 在一个 PostgreSQL 事务内写入 Run 和 outbox。
2. Dispatcher 锁定未发布 outbox 行，发布到 Redis Stream。
3. 发布成功后标记时间；若进程在发布与标记之间崩溃，允许重复发布。
4. 对账扫描器定期重新发布超时未确认的 outbox。

### 7.2 领取与续租

1. Run Worker 收到消息后尝试数据库租约。
2. 租约成功时递增 fencing token，并创建 attempt。
3. Worker 周期续租；续租失败后必须停止产生新步骤和提交。
4. Reaper 扫描过期租约，将 Run 转为可恢复状态并重新入队。
5. 旧 Worker 恢复后即使继续运行，也无法用旧 token 写入。

### 7.3 步骤执行

- 每个步骤先持久化 intent，再执行外部动作。
- 已完成且 input hash 一致的步骤直接复用结果。
- 同 step ID 但 input hash 不同属于协议错误，不允许静默复用。
- 可重试错误使用有界退避；参数、权限、schema 和预算错误不自动重试。
- 取消阻止新步骤和最终提交，但不删除已经发生的调用与费用证据。

### 7.4 最终提交

最终业务状态、Run 完成、公开 Trace 摘要和 result outbox 在一个 PostgreSQL 事务内提交。提交前再次校验：

- 当前 fencing token；
- Run 未取消且租约有效；
- 所有必要步骤完成；
- 预算和来源契约满足；
- 结果 schema 与策略版本匹配。

## 8. 有界专家平面

M2 将 Assessment、Curriculum 和 Tutor 的只读分析或草稿生成分发到专家 Worker：

- Expert Job 包含冻结输入引用、角色、策略 hash、预算、deadline 和幂等键。
- Worker 只通过受限工具读取授权数据。
- Expert Result 包含 draft、source refs、usage、状态和可重试性。
- Coordinator 校验结果后决定采用、降级、重试或重规划。
- 迟到、过期 token、策略版本不符和来源非法的结果不得进入最终提交。

BKT 更新、题目判分、测验状态、记忆提交和公开回复仍由 Run Worker 统一写入。

## 9. 可观测性与回放

### 9.1 Trace

内部 span 采用 OpenTelemetry 语义：

```text
request
  -> enqueue
  -> run_attempt
       -> coordinator_step
       -> expert_job
            -> model_call
            -> tool_call
       -> commit
```

每个 span 至少记录 trace/span/parent ID、run/attempt/step、开始结束时间、状态、Worker、策略版本和脱敏属性。公开 Trace 不保存密钥、请求 header、私有思考或未经授权的完整载荷。

提供可选 OTLP exporter；没有 collector 时，内部 Trace 仍正常工作。

### 9.2 指标

Prometheus 指标至少包括：

- 队列深度、排队时间、运行时延；
- 活跃 Worker、租约续期失败、接管次数、恢复时间；
- 重复投递、幂等命中、迟到结果拒绝、提交竞争；
- 模型/工具调用、预算耗尽、费用估算；
- Judge invalid/unknown、策略晋级和自动回滚。

### 9.3 回放

- `replay --dry-run`：从冻结输入和策略重建决策，不写业务状态。
- `retry`：沿用逻辑 `run_id`，创建新 attempt。
- Trace API 和 Ops Console 必须保留各次 attempt，不只展示最终成功。

## 10. Ops Console

复用现有 React 应用增加运维视图：

- Runs：状态、Worker、租约、fencing token、重试、策略、成本和时延。
- Trace：跨 API、Run、Expert、Model、Tool 和 Commit 的树状时间线。
- Workers：心跳、当前任务、积压和近期故障。
- Campaigns：校准、候选、开发/留出/Shadow、unknown、成本和回滚。

Console 是诊断界面，不提供任意修改业务状态的入口。破坏性演示通过受控脚本执行。

## 11. 可信策略晋级

### 11.1 Judge v3

- 每个目标输出逐项决策、稳定失败码、理由和原文证据。
- 校验器检查 `passed` 与理由/证据逻辑一致性。
- 理由明确陈述违规但布尔为通过时，整条标记 `invalid_judgment`。
- 缺字段允许一次只修结构的请求，绑定原始输出 hash，不允许改变语义结论。
- 修复失败记 unknown，不补零、不选择性重试。
- 生成前冻结历史响应 hash；重复文本不能作为新的独立校准样本。
- 标签记录来源，助手审阅不冒充独立人工金标准。

### 11.2 Campaign

- task、judge、reflection/proposal 都通过持久 Job 运行，共享请求和费用预算。
- trajectory 绑定代码、数据、模型、策略、Judge 和运行配置 hash。
- 开发集配对比较采用交错顺序和重复执行。
- 候选先过开发净胜、退化上限和有效 Judge 比例，再获得一次全局留出资格。
- unknown 单独报告并进入结果上下界，不伪装成失败或成功。

### 11.3 发布

```text
candidate -> development_passed -> holdout_passed
          -> registered -> shadow -> active
                                  \-> rejected
active -> rolled_back
```

- 策略注册表不可变，active pointer 原子切换。
- Shadow 使用相同冻结输入离线重放，不影响学生状态。
- 健康窗口检查错误率、成本、延迟和安全门禁；退化时自动回滚。
- 没有候选通过时，以“可信拒绝”完成 Campaign，不强行发布。

### 11.4 消融

至少比较：

1. 移除确定性泄露规则；
2. 移除全文读取策略；
3. 将 strict unknown 改为补零。

报告展示总体、能力分组、配对胜负、unknown 区间、成本、延迟和退化案例。

## 12. 故障处理

固定验证以下故障：

| 故障 | 预期行为 |
| --- | --- |
| API 提交后 Dispatcher 崩溃 | Outbox 对账后重新发布 |
| Run Worker 执行中强杀 | 租约到期，另一 Worker 接管 |
| Redis 短暂不可用 | PostgreSQL 状态不丢失，恢复后补发 |
| 同一 Run 重复投递 | 幂等命中，不重复副作用 |
| 专家重复或迟到结果 | 合并或拒绝，记录原因 |
| 两 Worker 同时提交 | 仅当前 fencing token 成功 |
| 模型调用超时但可能计费 | 不提交结果，账本保留未知/预留费用 |
| Judge 结构或逻辑无效 | 一次结构修复后记 unknown |

## 13. 测试与验收

### 13.1 测试层次

- 单元和属性测试：状态机、幂等键、租约、fencing、Judge 一致性。
- 集成测试：真实 PostgreSQL、Redis 和两个独立 Worker 进程。
- 故障注入：强杀、断连、重复投递、迟到结果和提交竞争。
- 全量回归：现有测试和离线评测必须继续通过。
- 基准：并发 1/4/16/32 下的吞吐、P50/P95、队列等待、恢复时间和重复副作用数。

### 13.2 总体验收

- distributed profile 可一条命令启动。
- 至少两个 Worker 可竞争任务并完成自动接管。
- 所有固定故障都有自动断言和可读 Trace。
- 重复业务副作用计数为 0。
- Ops Console 可展示完整跨进程因果链。
- 一次真实 Campaign 得到可审计的晋级或可信拒绝结论。
- 策略注册、Shadow、切换和回滚可离线复现。
- 测试数量和结果由脚本生成，README 不再维护过期硬编码数字。

## 14. 里程碑

### M1：Durable Run Plane

- PostgreSQL Run/Step/Lease/Outbox schema；
- Redis Streams Dispatcher、Run Worker、Reaper；
- fencing、幂等提交、异步状态查询；
- 内部 span、OTLP 可选导出和 Prometheus 指标；
- 两 Worker 强杀接管演示。

完成标志：现有业务在 distributed profile 下可运行，重复副作用为 0，Worker 崩溃后自动恢复。

### M2：Bounded Expert Plane

- 专家 Job/Result 协议和 Worker 池；
- Coordinator 写入所有权、迟到结果拒绝、局部重试；
- Ops Console 的 Runs/Trace/Workers；
- 并发与故障基准。

完成标志：Assessment、Curriculum、Tutor 草稿可远程执行，专家故障不破坏最终事务边界。

### M3：Trusted Improvement Plane

- Judge v3 校准；
- 分布式 Campaign；
- 开发/留出/Shadow/active/rollback；
- Campaign Console 与三项消融。

完成标志：真实 Campaign 产生可审计的发布决策，策略注册和回滚均有可复现证据。

## 15. 非目标

- Kubernetes 控制面、多区域容灾和生产级自动扩缩容；
- 将全部业务模块拆成微服务；
- 通用工作流 DSL 或通用 Agent 平台；
- 外部模型调用的网络级恰好一次；
- 为获得晋级结果修改留出标签或忽略 unknown；
- 在 M1 同时重写简历材料。

## 16. 演示故事

最终演示使用同一条证据链：

1. 提交一个复合教学任务；
2. API 事务创建 Run 和 Outbox；
3. 两个 Worker 中一个持租约执行；
4. 强杀该 Worker，另一个在租约到期后接管；
5. 注入重复专家结果，Harness 拒绝重复副作用；
6. Trace 展示完整接管、预算、工具、策略和提交因果链；
7. 同一执行底座运行策略 Campaign；
8. Judge、开发、留出和 Shadow 门禁决定晋级或可信拒绝；
9. 健康退化触发 active pointer 回滚。

一句话定位：

> EduAgent 是一个带可靠执行、隔离专家、可观测 Trace 和可信策略晋级的 Agent Harness；同一套证据链既解释系统如何避免重复执行，也解释策略为何可以或不可以发布。

## 17. 外部依据

本设计方向与当前公开 Agent 运行时的共同要求一致：

- [AWS AgentCore Harness 岗位说明](https://www.amazon.jobs/en/jobs/10478272/sr-software-development-engineer-agentcore-aws-agentic-ai)强调 managed agent loop、会话隔离、身份、工具编排、记忆、可观测性、故障处理、版本、渐进发布与回滚。
- [OpenAI Agents SDK Tracing](https://openai.github.io/openai-agents-js/guides/tracing/)以 workflow/trace/span 表达 Agent、turn、generation、tool、guardrail 和 handoff，并支持自定义 exporter。
- [Anthropic Agent 工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)建议用评测系统化衡量工具设计，并强调清晰边界、有效上下文和 token 效率。

这些资料用于确认能力维度，不作为本项目已经达到生产级规模的证据。
