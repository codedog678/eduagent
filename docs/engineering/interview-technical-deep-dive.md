# EduAgent 面试技术深挖手册

每个主题按同一顺序回答：主张、不变量、机制、失败、证据、取舍、替代方案、
未解决边界。L1 用于快速判断，L2 用于白板，L3 用于源码追问，L4 用于架构演进。

本手册不创造完成状态。运行结果以
[技术面试证据索引](interview-readiness.md)为准。

## 1. 状态权威与跨存储一致性

### L1：一句话

PostgreSQL 决定分布式执行身份，Redis 只负责可重复投递，SQLite 提交当前教学
业务事务；系统依赖 fencing 与 request ID 幂等恢复跨存储故障，不宣称跨库
exactly-once。

### L2：机制与不变量

| 存储 | 权威内容 | 明确不负责 |
| --- | --- | --- |
| PostgreSQL | Run、Attempt、Step、Lease、Outbox、Trace、Policy、Audit | 当前 BKT、测验、记忆和公开回复事务 |
| Redis Streams | 投递提示、consumer group、pending reclaim | 判断 Run 是否允许执行或提交 |
| Harness SQLite | 学习检查点、测验、消息、记忆、计划和执行结果 | 多 Worker 水平写入 |

核心不变量是：**消息存在不代表可以执行，执行过不代表仍可提交，控制面完成不代表
业务效果可以被重新执行。**

Dispatcher 可以在 `XADD` 成功、回写 outbox 前崩溃，因此消息允许重复。Worker
每次都回 PostgreSQL claim，只有当前 owner/token 才获得执行资格。真正的教学
效果由 `learner_id + request_id + content fingerprint` 保护；接管者用同一请求
重放，SQLite 若已提交就返回已保存结果。

### L3：失败窗口与源码

最重要的窗口是：SQLite 已提交，Worker 在 PostgreSQL `complete` 前死亡。
PostgreSQL fencing 不能撤销 SQLite 事务；reaper 会让新 Worker 接管，新 Worker
用相同 request ID 重放并读到已保存结果，因此只产生一次业务提交。

相反，如果外部模型请求已经发出但业务事务没有提交，远端可能已经计费或产生
不可撤销副作用。当前系统只能把调用、usage 和失败留下证据，不能保证它只发生
一次。

实现入口：

- [Run repository](../../python/core/distributed/repository.py)：Run/Lease/Attempt
  权威状态、outbox、step 与最终提交；
- [Distributed executor](../../python/core/distributed/executor.py)：按 execution
  authority 打开正确的 Harness store；
- [LearningHarness](../../python/core/harness.py)：request ID、内容指纹和业务事务；
- [M1 业务状态边界](distributed-run-plane.md#m1-业务状态边界)：已提交后死亡的
  恢复语义；
- [真实故障集成](../../python/tests/integration/test_distributed_failover.py)：
  接管与唯一业务效果。

### L4：取舍与演进

**为什么 M1 不直接把全部业务状态迁到 PostgreSQL？** M1 的目标是先证明 Run
身份、租约、恢复和观测，复用已有事务化教学 Harness，避免同时重写控制面与
业务模型。代价是保留文件锁和跨库故障窗口。

迁移业务状态到 PostgreSQL 后，可以把 Run terminal 与教学写入收敛到更明确的
事务/Outbox 协议，但仍不能让外部模型调用天然 exactly-once。迁移前必须保持：

- 同一 learner 串行；
- request/content 去重；
- 独立表现与受助表现不混写；
- 公开回复和学习证据同事务可见；
- 旧 fencing token 不能提交。

## 2. Lease、Fencing 与锁后权限复核

### L1：一句话

Lease 解决“当前是否有人应该工作”，fencing 解决“旧执行者即使还活着也不能
提交”；数据库行锁只序列化访问，不能替代获得锁后的时效与身份复核。

### L2：机制与不变量

每次 claim 都将 fencing token 单调加一。Worker A 的 token 1 过期后，Worker B
可获得 token 2；A 的进程、网络请求或缓存不会被魔法终止，但所有受保护提交都
必须携带 token，PostgreSQL 只接受当前 owner/token。

锁序固定为 `run → lease → attempt`，step 路径再锁 step；Expert 跨平面路径还会
锁 expert job/lease/result。拿到所有可能阻塞的锁后，代码重新读取数据库
`clock_timestamp()` 并检查：

- Run/Attempt 状态；
- owner 与 fencing token；
- lease expiry；
- attempt deadline；
- parent epoch；
- Expert 自身 lease/deadline。

不变量是：**任何在等锁前成立的权限条件，都不能直接授权锁后的写入。**

### L3：真实并发失败

曾复现的危险交错是：

1. A 查询到 lease 尚未过期；
2. A 等待被另一事务持有的行锁；
3. 等待期间 lease 或 attempt deadline 过期；
4. 如果 A 沿用锁前时间，它会在获得锁后错误提交。

[真实等锁回归](../../python/tests/distributed/test_lease_lock_time.py)让操作确定进入
PostgreSQL Lock wait，跨过 lease/deadline 后再放锁，同时验证 renew、step、
complete、fail、reaper 和 Expert 路径。repository 使用锁后数据库时间和
`populate_existing` 重载，避免 ORM session 继续使用锁前缓存。

另一个细节是 attempt deadline 与 lease 不同：lease 可以续租，但单次 attempt
仍不能无限执行。只检查 lease 会让已超出 attempt deadline 的 Worker 继续提交。

### L4：替代方案

- **只有心跳：** 能发现 Worker 失联，不能阻止暂停后恢复的旧 Worker。
- **只有行锁：** 能序列化事务，不能表达跨事务 ownership epoch。
- **进程取消：** 只能 best-effort，无法撤销远端调用或阻塞的第三方库。
- **分布式锁服务：** 仍需要 fencing token 进入最终权威写路径，否则锁服务失效
  后的旧持有者问题没有消失。

面试时不要说“fencing 保证 Worker 被杀死”，准确说法是“fencing 让旧执行者的
迟到提交失去效力”。

## 3. 有界 Expert Plane 与唯一业务写权限

### L1：一句话

Expert Plane 扩展的是可恢复的只读计算，不是业务写权限；Expert 结果需要
parent token 与 expert token 双重有效，并由当前父 Run 重新采用后才可能公开。

### L2：执行链路

```text
Run Worker
  -> freeze/redact ExpertJobRequest
  -> PostgreSQL job + outbox
  -> Redis hint
  -> Expert Worker claim + independent token
  -> bounded engine over snapshot-only tools
  -> append-only result
  -> parent polls and revalidates
  -> parent alone commits learner effect/public reply
```

冻结快照包含 learner/knowledge scope、目标、约束、policy hash、已验证来源和预算；
不包含 API key、数据库 URL、SQLite handle、repository、callback、可变
`ContextVar` 或 private reasoning。Compose 的 Expert Worker 不挂载 Harness
SQLite，也没有业务写 API。

### L3：四个不同状态

| 状态 | 说明 | 是否可公开 |
| --- | --- | --- |
| submitted | Worker 提交了一次 attempt 结果 | 否 |
| accepted | PostgreSQL 验证双重 token、schema、role、input/policy hash，且该 job 尚无 accepted result | 否 |
| adopted | 当前父 Run 再验证 source、policy、action/citation 与当前 authority | 仍需业务提交 |
| public delivery | 父侧 Harness 事务成功并形成公开结果 | 是 |

只校验 Expert token 不够：旧 parent epoch 的 job 可能向新 parent 提交。只校验
parent token 也不够：旧 Expert attempt 可能覆盖当前 attempt。因此
[Expert repository](../../python/core/distributed/expert_repository.py)在提交结果时
同时锁定并验证 parent run/lease/attempt 与 expert job/lease/result；
[Expert adopter](../../python/core/distributed/expert_adopter.py)继续做业务语义采用。

`accepted` 也不证明引用语义正确。它只证明结构、身份和声明范围满足协议；Tutor
citation 是否支持最终结论仍是上层评测问题。

### L4：为什么不让 Expert 直接写业务 PostgreSQL

直接写业务状态可以减少父侧串行瓶颈，但会同时扩大：

- learner 并发冲突；
- 受助/独立证据污染面；
- policy/source 授权面；
- 重试和迟到结果的补偿范围；
- 每个 Expert 角色所需数据库权限。

M2 选择“并行草稿、串行采用”，先隔离最昂贵且可重算的计算。若以后下放写权限，
必须先定义每类业务效果的幂等键、冲突模型、补偿语义和租户权限，不能仅把 SQLite
表迁到 PostgreSQL 就宣称完成。

## 4. 策略身份、版本固定与事务化回滚

### L1：一句话

策略发布不是替换一段 prompt，而是把 artifact、运行时、Judge 协议、campaign、
deployment、namespace 和每个 Run 的不可变 binding 连成可重放身份链。

### L2：身份与状态机

| 身份 | 作用 |
| --- | --- |
| policy hash / parent hash | 标识候选内容与继承关系 |
| runtime hash / source revision | 标识执行代码与构建来源 |
| protocol / calibration identity | 标识 Judge 口径 |
| campaign / qualification receipts | 标识候选为何有资格进入 rehearsal |
| deployment / version | 标识环境中的一次策略状态机实例 |
| state namespace | 隔离 stable、candidate、shadow 的业务状态 |
| Run binding | 固定 admission 时的 deployment、policy、cohort、namespace |

状态单向经过 `registered → shadow → canary → active`，任何阶段可冻结；Canary/
Active 可 rolled back。Run 在 admission 事务中固定 binding，Worker 接管和
Expert job 继承它，active head 后续变化不能改写旧 Run。

### L3：并发回滚与迟到观察

Policy-health 在一个 PostgreSQL 事务内：

1. 锁 deployment 与当前 head；
2. 冻结并验证 observation/window/threshold identity；
3. 写失败 window；
4. 将 deployment 标记 rolled back；
5. CAS 更新 stable head；
6. 写唯一 rollback audit 与 Outbox。

两个 evaluator 并发时，共享 head 锁和版本条件使第二个不能再次移动 head 或生成
第二条有效回滚。旧 deployment 的迟到 observation 可以保留用于审计，但不能把
已经变化的 head 回退。真实交错见
[policy health publication 回归](../../python/tests/distributed/test_policy_health_publication.py)。

Task 10 的
[多进程 promotion 集成](../../python/tests/integration/test_policy_promotion.py)
还验证：Run Worker SIGKILL 后 token `1 → 2` 且 binding 字节不变；回滚前旧 Run
保持 candidate；回滚后新 Run 使用 stable；迟到 observation 不改变 head。

### L4：为什么不用“读取当前 active prompt”

执行时动态读取 active prompt 会产生不可重放的混合版本：

- 同一 Run 的不同 attempt 可能使用不同 policy；
- Expert result 无法证明对应哪个父策略；
- 回滚会改变正在执行任务的语义；
- Trace 无法将质量、成本和故障归因到唯一候选。

不可变 binding 增加了 schema、迁移和证据链复杂度，但换来重放、归因和安全回滚。
正式生产还需要 RBAC、租户隔离、密钥托管和真实 eligible campaign，这些不在
当前 fixture 验收范围。

## 5. 自动契约、Judge、工程交付与学习效果

### L1：一句话

“格式正确”“Judge 通过”“故障演练通过”和“学生学得更好”是四种不同结论，
任何一层通过都不能自动升级为下一层。

### L2：证据等级

| Evidence | Proves | Does not prove |
| --- | --- | --- |
| deterministic/automatic contract | 回复、Trace 结构和工程不变量 | 语义质量 |
| Judge v3 | 冻结 rubric 下的模型判断和 unknown 处理 | 人类真值或学习效果 |
| engineering integration | 冻结 fixture 上的故障路径行为 | 候选模型质量 |
| learner study | 特定研究设计下的因果学习结果 | 通用基础设施正确性 |

Judge v3 的 `unknown` 表示证据不足，不是“回复中出现失败词”。Judge 可以做一次
受约束 repair；继续重试会把预算和偏差隐藏在评分器里，因此 repair 后仍不完整
就保留 unknown，并进入健康窗口的 unknown rate。

### L3：为什么开发重放不能授予资格

开发集被用于发现问题、修改 prompt/规则和选择候选，重复评估会产生选择偏差。
正式资格需要：

1. 当前 Judge v3 协议和独立 calibration identity；
2. 未被开发选择污染的 formal holdout；
3. 匹配 runtime/source revision；
4. 完整请求、失败、中断与成本账本；
5. `simulation=false`、`mode=qualification`、`state=eligible` campaign。

缺少 cost、结构化判断、receipt 或身份绑定时，health 保持 HOLD/fail closed，
不能把缺失值当作零或把“未看到失败”当作通过。

### L4：教育证据为什么更严格

系统区分首次独立作答与提示后答对，后者不更新独立掌握证据。这保证日志可以支持
后续研究，但并不自动证明支架有效。学习效果还需要对照条件、前后测或迁移任务、
样本量、缺失处理和统计分析；当前项目没有执行这类真实学生因果研究。

因此面试中可以说“保护了可用于研究的证据边界”，不能说“已经证明提升学习效果”。

## 6. Trace、故障注入与可复现性

### L1：一句话

Trace 的价值不是展示调用链，而是把请求、所有权 epoch、步骤、策略身份和最终
业务效果连成可审计因果链。

### L2：身份链

```text
request_id -> run_id -> attempt_id -> step_id
                         |             |
                         v             v
                   fencing token   policy binding
```

每次接管创建新 attempt/token，但 request 与 Run 身份保持。Step 记录 intent、
input hash、结果和 token；Expert job 再继承 parent run/token/policy；最终
observation、health window 和 audit 绑定 deployment 与 source revision。

### L3：什么才算强证据

| 风险 | 弱证据 | 当前较强证据 |
| --- | --- | --- |
| Worker 崩溃 | mock exception | 真实子进程 SIGKILL，token `1 → 2` |
| 重复消息 | 单元函数调用 | Redis/outbox 重发与 PostgreSQL claim 拒绝 |
| 旧 Expert | 只看 job status | parent + expert 双 token 与 append-only rejection |
| 迟到观察 | 手工构造最终状态 | 回滚后发布旧 deployment observation，head 不变 |
| 回滚竞态 | 串行两次调用 | 两事务竞争 deployment/head 锁和 CAS |
| 发布证据 | 只报 passed 数量 | revision、配置、JUnit、结构化 artifact、敏感值扫描 |

测试数量只有同时说明范围、revision、环境、跳过项和 artifact 才有意义。当前最终
数字绑定 `f8b8e3c`：非分布式 `850 passed, 56 skipped`、分布式
`1537 passed`、Ops `54 passed`；正式 rehearsal 仍未执行。

### L4：可观测性边界

Ops 是脱敏只读投影，不是新的权威写平面。Redis/进程内 counter 也不能替代
PostgreSQL 聚合的当前状态。生产化下一步应增加：

- 租户身份与行级授权；
- Trace 保留、采样和敏感字段策略；
- SLO 与告警，而不只是演示指标；
- artifact 生命周期与可验证供应链；
- 正式 rehearsal 的模型/provider 账本。

## 技术债务与下一步演进

| 方向 | 当前边界 | 为什么推迟 | 必须保持的不变量 | 完成证据 |
| --- | --- | --- | --- | --- |
| 教学状态迁移 PostgreSQL | SQLite 单写、文件锁 | M1 先隔离 Run Plane 风险 | learner 串行、请求幂等、公开回复与证据原子可见 | 真实多 Worker 业务写入与崩溃矩阵 |
| 拆分千行 repository/query | 多个模块超过千行 | M1-M3 先稳定协议和审查修复 | 锁序、事务边界、错误码不变 | 契约测试、等锁回归和 API diff |
| 多租户身份与授权 | learner ID 由演示 API 传入 | 当前重点是控制面正确性 | tenant/learner scope 不可由模型扩展 | 跨租户拒绝、审计和权限测试 |
| 正式 eligible-campaign rehearsal | 只有 fixture 控制面闭环 | 缺少 campaign 与匹配模型凭据 | 写入前 fail closed、身份完全匹配 | 七类正式 artifact 与真实请求/成本账本 |
| 独立模型校准与留出资格 | 历史开发重放有污染 | 需要冻结新数据和预算 | calibration、holdout、runtime/source 独立绑定 | Judge v3 qualification receipts |
| 真实学生学习效果研究 | 只有工程与虚构评测数据 | 需要伦理、样本和教学流程 | 独立/受助表现分离、低负担测量 | 预注册设计、完整数据与因果分析 |

## 快速源码导航

| 问题 | 入口 |
| --- | --- |
| Run claim/renew/commit | [repository.py](../../python/core/distributed/repository.py) |
| 多进程执行与 Harness store | [executor.py](../../python/core/distributed/executor.py) |
| Expert job/result | [expert_repository.py](../../python/core/distributed/expert_repository.py) |
| Expert 父侧采用 | [expert_adopter.py](../../python/core/distributed/expert_adopter.py) |
| Policy 分配 | [policy_assignment.py](../../python/core/distributed/policy_assignment.py) |
| Health 与回滚 | [policy_health.py](../../python/core/distributed/policy_health.py) |
| Promotion 写平面 | [promotion_repository.py](../../python/core/distributed/promotion_repository.py) |
| 多进程闭环 | [test_policy_promotion.py](../../python/tests/integration/test_policy_promotion.py) |

