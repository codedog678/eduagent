# EduAgent 面试讲解手册

适用主线：Agent Harness 工程。Agent 算法作为第二入口。

本手册只改变信息密度，不改变事实。运行数字与完成状态以
[技术面试证据索引](interview-readiness.md)为准。

## 三十秒

我做的不是普通聊天 Agent，而是一个有状态 Agent Harness。教育场景里一次答题
会同时影响测验、掌握度、回复和后续计划，所以重试、Worker 崩溃或策略切换不能
重复提交或污染状态。我把系统从单机事务 Harness 扩展为可恢复 Run Plane、
只读 Expert Plane 和可信策略晋升链路，并用真实 PostgreSQL/Redis 多进程
SIGKILL、自动回滚和 CI 验证。这里的发布演练仍是 `release_eligible=false`
的 fixture，不能包装成真实模型效果。

## 三分钟主故事

### 0:00-0:30 场景与冲突

这个项目从自适应教学开始，但我最后解决的是一个通用的有状态 Agent 问题。
一次交互不仅生成文本，还会改变测验状态、掌握度、记忆和学习计划。网络重试、
进程崩溃或新旧策略混跑都可能造成不可逆的证据污染，所以“模型能回答”不是
交付完成，执行身份、业务提交和公开回复必须能被追踪并保持一致。

### 0:30-1:15 M1：谁有提交权

M1 把分布式执行状态放进 PostgreSQL，Redis Streams 只负责可重复投递。
Worker 用 lease 获得临时执行权，但最终提交还必须携带单调增长的 fencing token；
旧 Worker 即使没有立即停止，也不能越过新 epoch 提交。业务学习状态当前仍由
SQLite 单写，崩溃后使用同一 request ID 重放，因此我明确不宣称跨库事务或外部
模型副作用实现了 exactly-once。

### 1:15-2:00 M2：专家如何扩展但不越权

Assessment、Curriculum 和 Tutor 草稿可以交给独立 Expert Worker，但 Expert
只能读取冻结、脱敏、带预算的快照，不能挂载业务 SQLite。结果先经过 Expert
token 和 parent Run token 的双重 fencing，再由父 Worker 校验 policy、来源范围
和当前来源可用性。`accepted result` 只是一个可审计草稿，只有父侧 adopted 后
才能进入唯一业务写事务，更不能直接等同于 public delivery。

### 2:00-2:40 M3：算法候选如何受控上线

离线分数不直接授予线上发布权。M3 把 policy hash、runtime hash、Judge 协议、
campaign、deployment 和 namespace 绑定在一起，Run 在 admission 时固定身份。
候选先进入无业务提交权的 Shadow，再进入确定性 cohort 的 Canary；health
evaluator 只消费匹配窗口，失败时在事务内更新 head、写审计并发 Outbox。回滚
只影响新 Run，已受理 Run 继续使用原 binding，迟到 observation 只留证据。

### 2:40-3:00 证据与边界

最终绑定 `f8b8e3c` 的矩阵是非分布式 `850 passed, 56 skipped`、真实
PostgreSQL/Redis 分布式 `1537 passed`、Ops Playwright `54 passed`，远程 CI
五个 job 全部成功。但 Task 9 的独立审查未完整封存，正式 eligible Judge v3
campaign rehearsal 也没有外部前置条件，所以我只主张控制面工程闭环，不主张
策略已正式发布或学习效果提升。

## 十分钟白板

### 1. 先画三个权威存储

**怎么画：** 左到右画 PostgreSQL、Redis Streams、Harness SQLite。PostgreSQL
下面写 `Run / Attempt / Lease / Policy / Audit`，Redis 写 `delivery only`，
SQLite 写 `learning transaction / single writer`。

**必须说的不变量：** 投递消息不是提交许可；任何 Worker 都必须回到权威存储
证明自己仍拥有当前 epoch。

**常见追问：** 为什么不把全部状态都放 PostgreSQL？

**下钻：** [状态权威与跨存储一致性](interview-technical-deep-dive.md#1-状态权威与跨存储一致性)。

### 2. 走一遍 Run 数据流

**怎么画：** API admission → PostgreSQL Run/Outbox → dispatcher → Redis →
Worker claim → Step → SQLite business commit → Run terminal。

**必须说的不变量：** request ID 与内容指纹共同去重；相同 ID 换内容拒绝，
相同请求重放必须复用业务幂等边界。

**常见追问：** PostgreSQL terminal 成功、SQLite 提交失败怎么办？

**下钻：** [跨存储失败窗口](interview-technical-deep-dive.md#l3失败窗口与源码)。

### 3. 注入 Worker 死亡

**怎么画：** Worker A 获得 token 1，在 lease 过期后被 SIGKILL 或停顿；reaper
重新排队，Worker B 获得 token 2；A 的迟到提交画红叉。

**必须说的不变量：** lease 解决活性，fencing 解决旧执行者仍活着时的安全性。

**常见追问：** 有数据库行锁为什么还需要 fencing？

**下钻：** [Lease、Fencing 与锁后权限复核](interview-technical-deep-dive.md#2-leasefencing-与锁后权限复核)。

### 4. 加上 Expert Plane

**怎么画：** 父 Run 从已固定输入生成 snapshot，Expert Worker 只读计算，
result 回到 parent validation，再进入业务提交。标出 parent token 和 expert token。

**必须说的不变量：** Expert 的计算可恢复，但 learner-state 写权限不随计算下放。

**常见追问：** accepted result 为什么还不能直接返回给用户？

**下钻：** [有界 Expert Plane](interview-technical-deep-dive.md#3-有界-expert-plane-与唯一业务写权限)。

### 5. 固定策略身份

**怎么画：** `campaign → policy hash → deployment → namespace → Run binding`，
并在 Attempt、Expert job 和最终结果旁重复同一 binding。

**必须说的不变量：** admission 后的执行身份不可随 active head 变化。

**常见追问：** 回滚时为什么不把正在执行的 Run 切回 stable？

**下钻：** [策略身份与事务化回滚](interview-technical-deep-dive.md#4-策略身份版本固定与事务化回滚)。

### 6. 加上 Shadow、Canary 和回滚

**怎么画：** Candidate 先进入无业务提交权的 Shadow；通过 receipt 后按 HMAC
cohort 进入 Canary；health window 失败后更新 head 并写 rollback audit。

**必须说的不变量：** qualification evidence、执行 binding、健康 observation
和 rollback audit 必须能回到同一冻结身份链。

**常见追问：** 两个 evaluator 同时决定回滚会怎样？

**下钻：** [并发 evaluator 与迟到观察](interview-technical-deep-dive.md#l3并发回滚与迟到观察)。

### 7. 用 Ops 与 Trace 收尾

**怎么画：** 从 Run、Attempt、Step、Lease、Expert、Policy identity 指向同一
Trace；旁边写 source revision、配置、JUnit 和 artifact。

**必须说的不变量：** Trace 不是装饰日志，而是证明“哪个身份在什么边界做了
什么”的因果证据。

**常见追问：** 为什么测试数量不能单独证明系统可靠？

**下钻：** [Trace、故障注入与可复现性](interview-technical-deep-dive.md#6-trace故障注入与可复现性)。

## 五分钟现场演示

### 前置条件

- Docker、Python 3.11 和 `python[dev]` 依赖可用；
- `.env` 已配置稳定复用的 PostgreSQL 密码、Ops token 和 promotion secret；
- 演示账号有创建临时数据库的权限；
- 不需要真实模型凭据，provider 使用 template，记忆检索使用 lexical。

### 0:00-1:00 启动并确认进程

```bash
docker compose --profile distributed up --build -d
curl --fail http://localhost:8890/api/health
open http://localhost:3000/ops/
```

在 Ops Workers 确认 Run Worker、Expert Worker、dispatcher、reaper、Shadow 和
policy-health 进程可见。说明 Redis 进程健康不等于它拥有状态权威。

### 1:00-2:30 强杀 Expert

```bash
export DISTRIBUTED_DATABASE_URL="$LOCAL_DISTRIBUTED_DATABASE_URL"
export DISTRIBUTED_REDIS_URL=redis://localhost:6379/15
export LLM_PROVIDER=template
export MEMORY_RETRIEVAL_MODE=lexical
export MEMORY_WORKER_ENABLED=false
python tools/demo_expert_failover.py
```

指出 token `1 → 2`、唯一 accepted result、被强杀 attempt、迟到结果拒绝，以及
未变化的学习状态摘要。原始结构化证据见
[专家接管报告](../superpowers/reports/demo-startup-final.json)。

### 2:30-4:00 跑 promotion fixture

```bash
(cd python && python -m pytest tests/integration/test_policy_promotion.py -q)
```

这条用例启动真实 PostgreSQL/Redis 和真实子进程，覆盖接管、binding 保持、
Shadow 隔离、Canary、自动回滚和迟到 observation。必须同时说明 candidate 与
receipt 是 fixture，证据保持 `release_eligible=false`，模型请求数为 0。

### 4:00-5:00 对照 Ops 与边界

依次打开 Runs、Trace、Experts、Policies，指向：

- Run/Attempt 的 fencing token；
- Expert result 的 adopted/rejected 状态；
- policy/deployment/namespace binding；
- health window 与唯一 rollback audit；
- 回滚前旧 Run 与回滚后新 Run 的不同 binding。

Docker、端口或数据库权限临时不可用时，不现场改环境。改为展示绑定 revision 的
[Task 10 验收记录](m3-policy-promotion-acceptance.md)、
[专家演示原始 JSON](../superpowers/reports/demo-startup-final.json)和远程 CI
artifact，并明确这是预先归档证据，不是假装现场运行。

## 面试官方向切换

### Harness 工程追问

| 面试官关注 | 一句话转场 |
| --- | --- |
| exactly-once | “我没有承诺 exactly-once，而是把可重复投递、业务幂等和外部副作用分别建模。” |
| Redis 与 PostgreSQL | “Redis 负责唤醒，PostgreSQL 决定身份和提交权，故障时不会由消息存在与否决定真相。” |
| lease 与 fencing | “lease 解决没人工作，fencing 解决旧的人还在工作。” |
| 锁顺序 | “真正危险的是条件在等锁前成立、获得锁后已经过期，所以提交前必须锁后复核。” |
| 取消与 deadline | “取消是 best-effort，attempt deadline 和 lease 分别约束执行时间与所有权。” |
| 可观测性 | “Trace 绑定 Run、Attempt、Step、token 和 policy identity，不只记录字符串日志。” |

以上问题统一下钻到
[面试技术深挖手册](interview-technical-deep-dive.md)。

### Agent 算法追问

| 面试官关注 | 一句话转场 |
| --- | --- |
| 工具选择与预算 | “工具循环有请求、工具和全轮预算，拒绝调用也消耗预算，避免无限纠错。” |
| 检索与来源 | “词法和向量通过 RRF 合并，但召回命中与读过原文、引用合法与语义支持仍是不同结论。” |
| Judge v3 | “`unknown` 表示证据不足，不是失败文本别名；一次 bounded repair 后仍不完整就 fail closed。” |
| 数据角色 | “开发重放定位问题，独立校准固定判断口径，留出 qualification 才可能授予发布资格。” |
| Shadow/Canary | “算法候选先证明隔离和证据完整，再证明匹配窗口健康，不会直接替换 active policy。” |
| 学习效果 | “工程链路保护学习证据，但是否促进学习需要独立的真实学生因果研究。” |

算法证据入口见
[Agent 算法面试证据卡](agent-algorithm-evidence.md)。

## 开场与收尾

### 面向招聘方或非专业面试官

“这个项目最初是多 Agent 教学应用，但真正有区分度的是：我把会改变长期状态的
Agent 做成了可恢复、可审计、可受控发布的 Harness，并保留了失败和未完成证据。”

### 面向分布式系统面试官

“我想先画清三个权威边界：PostgreSQL 决定执行身份，Redis 只投递，SQLite
提交当前教学事务。后面的 lease、fencing、Expert 和 policy rollback 都是在
维护这三个边界。”

### 收尾

“我最看重的不是组件数量，而是每个结论是否有明确的不变量、失败模型和证据
范围。这个项目已经证明控制面的可靠执行，但我仍把单写业务状态、正式 campaign
和学习效果留作明确边界，这也是我做 Agent Harness 时的工程判断。”

## 不要这样说

| 不准确表述 | 精确替代表述 |
| --- | --- |
| “实现了 exactly-once” | “实现可重复投递下的权威 fencing 与业务幂等；外部模型副作用不承诺 exactly-once。” |
| “策略已正式上线” | “fixture 控制面和故障闭环通过；正式 eligible campaign rehearsal 未执行。” |
| “模型效果显著提升” | “历史开发评测观察到候选差异，但不满足当前 Judge v3 正式资格。” |
| “支持业务状态水平扩展” | “Run/Expert 控制面可多进程恢复；Harness SQLite 业务状态仍单写。” |
| “测试通过就证明教学有效” | “测试证明工程不变量；教学效果需要独立真实学生研究。” |
| “accepted expert result 就是最终回答” | “accepted 只是可审计草稿，仍需父侧 adopted 和业务事务提交。” |

