# EduAgent M3 可信策略晋级与受控灰度设计

日期：2026-10-30
状态：已确认，待实施
目标岗位：Agent Harness / Agent 算法

## 1. 背景与事实基线

EduAgent 已经完成：

- M1 Durable Run Plane：PostgreSQL 权威 Run、Redis Streams 投递、租约、fencing token、重试、接管、Outbox/Inbox 和跨进程 Trace。
- M2 Bounded Expert Plane：有界专家 Job、能力声明、输入快照、预算、来源校验、迟到结果拒绝和 Coordinator 单写入。
- 离线策略优化：开发/留出隔离、配对比较、校准、不可变候选策略和成本账本。

当前发布链路仍有四个关键缺口：

1. `PolicyRegistry` 依赖文件锁与 `active.json`，不能作为多进程发布权威。
2. 策略在执行开始时才解析，`distributed_runs` 没有固定 deployment；重试、租约接管和专家调用可能跨版本。
3. `PolicyHealthMonitor` 只观察少量结果并通过文件回滚，缺少并发保护、基线比较、延迟/成本门禁和可审计窗口。
4. Judge 对布尔值、理由和证据的一致性校验不完整；现有候选没有完成正式 holdout、Shadow 和 Canary 资格链。

因此，M3 不能把已有候选直接“上线”。它先建立可信控制面和受控流量演练，用真实 PostgreSQL、Redis 和多进程执行验证发布语义，但不声称真实学生质量收益。

## 2. 目标与非目标

### 2.1 目标

M3 必须交付以下可验证能力：

- PostgreSQL 成为策略包、部署、门禁、观测和审计的唯一发布权威。
- Run 在首次受理事务中固定 deployment 和 policy，所有重试、接管、步骤和专家 Job 继承该版本。
- 候选只能按 `registered -> shadow -> canary -> active` 前进，任何人都不能绕过必要门禁。
- 受控测试流量可以真实执行候选、写入隔离状态、产生指标，并触发事务化自动回滚。
- Judge v3 将无效、矛盾或无法修复的判断记为 `unknown`，不能误计为通过。
- 演练输出机器可读证据，绑定代码、配置、模型、协议、数据角色、请求和费用。

### 2.2 非目标

M3 不包含：

- 面向真实学生的生产灰度或自动全量发布。
- 以 Canary 运行指标证明教学质量提升。
- 在线训练、自动修改 prompt 或开放式自我迭代。
- 通用 Feature Flag 平台、跨区域控制面或外部制品仓库。
- 用事件溯源重建全部当前状态；审计事件只用于证据和追责。

## 3. 方案选择

### 3.1 发布权威

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| 扩展文件 `PolicyRegistry` | 改动小，本地易读 | 文件锁不能覆盖多主机；发布与 Run 固定不能同事务 | 不采用 |
| PostgreSQL 可信控制面 | 与 Durable Run 同一事务边界；支持行锁、唯一约束和 CAS | 需要迁移和命令面 | 采用 |
| 事件溯源 + 外部制品仓库 | 审计和扩展性最强 | 超出当前规模，演示与运维成本高 | 不采用 |

### 3.2 验证流量

| 方案 | 能验证的内容 | 风险与限制 | 结论 |
| --- | --- | --- | --- |
| 离线 Shadow | 候选可执行性、差异和部分成本 | 不验证分流、状态写入和回滚闭环 | 作为前置阶段 |
| 受控流量演练 | 真实分流、隔离写入、指标、告警和回滚 | 不能代表真实用户收益 | M3 采用 |
| 真实外部流量 | 外部效度最高 | 合规、环境和观察期均不受本项目控制 | M3 不采用 |

## 4. 总体架构

```text
Promotion CLI / Command API
  -> Policy Control Plane (PostgreSQL)
       policy_artifacts
       policy_gate_receipts
       policy_deployments
       policy_environment_heads
       rehearsal_token_nonces
       policy_observations
       policy_health_windows
       policy_audit_events

Controlled Rehearsal Driver
  -> signed rehearsal token
  -> Run Admission
       verify token + namespace
       load deployment snapshot
       deterministic HMAC assignment
       persist assignment on distributed_run
  -> Redis Streams
  -> Run Worker / Expert Workers
       inherit policy + deployment + namespace
       write isolated rehearsal state
       emit observations

Health Evaluator
  -> aggregate frozen window
  -> pass / hold / rollback
  -> transactional deployment switch

Read-only Ops API / Console
  -> deployment timeline, gates, cohorts, health, rollback evidence
```

控制面与运行面分离：

- 命令面负责注册、开始 Shadow、开始 Canary、晋级、冻结和人工回滚。
- 运行面只读取已提交的 deployment snapshot，不允许自行晋级。
- Ops API 只读，不复用命令权限。
- PostgreSQL 当前状态用于并发决策；append-only 审计事件用于证据，不反向驱动状态。

## 5. 数据模型与不变量

### 5.1 `policy_artifacts`

保存不可变策略制品：

- `policy_hash`：主键，规范 JSON 的 SHA-256。
- `parent_policy_hash`、`components`、`fixed_components_hash`。
- `runtime_hash`、`source_revision`、`protocol_hash`、`proposer_hash`。
- `data_role`、`evidence_bindings`、`created_at`。

同一 `policy_hash` 不允许出现不同正文。加载时必须重新计算哈希并校验 runtime/source compatibility。

### 5.2 `policy_gate_receipts`

每张回执表示一个不可变门禁结论：

- `receipt_id`、`policy_hash`、`gate_type`、`status`。
- `evidence_hash`、`protocol_hash`、`runtime_hash`、`source_revision`。
- `model_identity`、`data_role`、`sample_count`、`cost`。
- `details`、`issued_at`、`issuer`。

`status` 只能是 `passed / failed / unknown`。新证据产生新回执，不覆盖旧回执。晋级查询只接受与目标策略及当前发布协议完全绑定的最新有效 `passed` 回执。

### 5.3 `policy_deployments`

每次状态变化创建新版本，不原地改写历史：

- `deployment_id`、`environment`、`version`、`state`。
- `candidate_policy_hash`、`stable_policy_hash`、`previous_stable_deployment_id`。
- `traffic_basis_points`、`assignment_salt_id`。
- `thresholds`、`thresholds_hash`、`required_receipts`。
- `command_id`、`reason`、`actor`、`created_at`。

约束：

- `(environment, version)` 唯一且单调增加。
- deployment snapshot 只允许 INSERT，不能 UPDATE/DELETE。
- 命令通过 `expected_version` 做 CAS；过期命令返回冲突，不能覆盖新状态。
- `command_id` 全局唯一，重复命令返回原结果。
- M3 只允许 `environment=rehearsal` 的候选进入 Canary/Active。普通请求始终使用生产稳定策略。

`policy_environment_heads` 每个 environment 只有一行，保存 `current_deployment_id`
和 `current_version`。它是唯一允许原地 CAS 更新的发布指针；deployment 历史和审计记录仍
保持不可变。Run 受理锁定 head 后读取对应 snapshot。

各状态的服务语义固定为：

- `registered / shadow / frozen / rolled_back`：新主 Run 全部使用 `stable_policy_hash`。
- `canary`：按 `traffic_basis_points` 在 candidate/stable 之间分流。
- `active`：rehearsal 新 Run 全部使用 `candidate_policy_hash`。

### 5.4 Run 固定字段

`distributed_runs` 增加：

- `deployment_id`
- `effective_policy_hash`
- `policy_cohort`：`stable / candidate / shadow`
- `assignment_key_hash`
- `assignment_reason`
- `state_namespace`
- `rehearsal_id`

这些字段在首次受理时写入，之后不可修改。Run attempt、step、expert job、expert result 和 trace 均携带或可关联这些值。任何版本或 namespace 不一致的结果都不能提交。

### 5.5 观测、窗口与审计

`policy_observations` 以幂等键记录单 Run 观测：

- `observation_key = run_id + metric_contract_version`
- deployment、policy、cohort、namespace、结果分类
- latency、token、cost、commit outcome、permission outcome
- observation time、source trace

`policy_health_windows` 保存冻结窗口、候选/基线统计、判定、触发阈值和输入 observation 范围。相同窗口重复计算必须得到同一结果。

`policy_audit_events` 仅追加，记录命令、门禁拒绝、状态转换、自动回滚和操作者。数据库权限禁止 UPDATE/DELETE。

`rehearsal_token_nonces` 保存 token nonce 的摘要、rehearsal、过期时间和首次消费时间。
nonce 摘要唯一，并在 Run 受理事务中消费；Redis 不承担防重放权威。

## 6. Run 受理与确定性分流

### 6.1 受理事务

Run 首次受理在同一 PostgreSQL 事务内：

1. 校验 `(learner_id, request_id)` 和 input hash。
2. 校验服务端签发的 rehearsal token；从 token 解析 `rehearsal_id`，不信任客户端自报 environment/namespace。
3. 锁定并读取当前 deployment snapshot。
4. 计算 cohort，解析并校验策略制品。
5. 写入 Run 固定字段及 Outbox。

幂等重放返回原 assignment。相同 request ID 但 input hash 不同仍返回冲突。

### 6.2 分流算法

Canary 使用：

```text
bucket = uint64(HMAC-SHA256(
  assignment_secret,
  environment || deployment_id || learner_id || request_id
)) mod 10000

candidate if bucket < traffic_basis_points else stable
```

- salt 只保存引用，密钥来自服务端 secret provider，不进入日志、Trace 或数据库。
- `traffic_basis_points` 在一个 deployment 版本内不可变。
- assignment 的哈希结果持久化，后续不重新计算。
- Shadow 阶段主 Run 固定 stable；候选执行创建关联的 shadow execution，共用冻结输入但无提交权。

### 6.3 版本继承

- attempt 和 lease takeover 只按 Run 固定字段执行。
- Expert Job 从 Run 复制 policy、deployment、namespace 和 snapshot hash。
- Expert Result 必须逐字段匹配；不匹配记协议拒绝。
- 自动回滚只影响回滚事务提交后受理的新 Run，旧 Run 继续使用原固定版本。

## 7. Judge v3 与晋级门禁

### 7.1 Judge v3 契约

Judge 原始输出必须包含：

- `verdict`：`pass / fail / unknown`
- `reason_codes`：受控枚举
- `evidence_refs`：必须引用输入中存在的证据
- `criterion_results`：逐项 `pass / fail / unknown`
- `rationale`：有长度上限的简短说明

验证顺序：

1. 严格 schema 与枚举校验。
2. 校验总 verdict 与 criterion results 的逻辑一致性。
3. 校验 reason code 与 verdict 一致。
4. 校验 evidence ref 存在且属于当前样本。
5. 最多进行一次有界 schema repair；repair 只能整理已有内容，不能补造证据。
6. 仍无效、矛盾或缺证据时输出 `unknown`。

`unknown` 保留原始响应、校验错误、repair 请求和 repair 响应，计入成本和无效率，但绝不计入通过。

### 7.2 门禁顺序

| 阶段 | 必要回执 | 通过条件 |
| --- | --- | --- |
| Registered | artifact integrity、campaign eligibility | 制品可重算；原始配对证据、协议和代码绑定有效 |
| Shadow | Judge v3 calibration、formal holdout、harness qualification、shadow health | 无留出复用；Judge 有效；候选可执行且无安全异常 |
| Canary | canary health | 达到最小样本；全部 operational guardrail 通过 |
| Active | promotion approval | 前述回执仍有效；人工命令显式晋级 |

正式 holdout 每个 campaign binding 只允许消费一次。失败、unknown、中断和费用超限都保留记录，不允许通过重跑只挑成功结果。

### 7.3 状态机

```text
registered -> shadow -> canary -> active
      |          |          |         |
      +-------> frozen <-----+---------+
                            \-> rolled_back
```

- 前向迁移必须验证当前 state、expected version 和必要回执。
- `frozen` 禁止新流量，可由门禁失败、证据不一致或人工命令触发。
- `rolled_back` 表示曾接管流量后回退；该候选不能直接恢复，修复后必须注册新 policy hash。
- Active 在 M3 中仅表示 rehearsal environment 的稳定候选，不表示已向真实学生发布。

## 8. Shadow、Canary 与隔离写入

### 8.1 Shadow

Shadow candidate：

- 使用与 stable 相同的冻结、脱敏输入。
- 可以调用模型和只读工具，产生完整 Trace、usage、latency 和差异记录。
- 没有业务提交 capability；结果不能修改测验、学习状态、记忆或公开回复。
- baseline 与 candidate 的调用费用分别记账。

Shadow 门禁至少验证：执行成功率、schema 有效率、权限拒绝、预算、p95 latency 和单 Run 成本。Shadow 只用于 operational qualification，不把输出差异解释为真实学习收益。

### 8.2 Canary

Canary 只接收 Rehearsal Driver 产生的签名流量：

- token 绑定 rehearsal、过期时间、允许操作和 nonce。
- nonce 只能使用一次；过期、签名错误或权限不符直接拒绝。
- server 将其映射到独立 `state_namespace`。
- PostgreSQL 角色、repository 条件和提交校验共同禁止 rehearsal 写入生产 namespace。
- 使用隔离 learner ID 和测试数据，不能引用真实学生数据。

候选会真实运行、真实提交到 rehearsal namespace 并产生真实指标，因此可以验证分流、状态隔离和回滚，而不污染正式学习状态。

## 9. 健康窗口与自动回滚

### 9.1 初始演练阈值

阈值在 deployment 创建时冻结并哈希。M3 默认值：

| 指标 | 默认门槛 |
| --- | --- |
| 最小候选样本 | 20 Runs |
| 最大窗口 | 最近 50 个候选 Runs |
| confirmed permission violation | 0，单次立即触发 |
| commit failure rate | 不高于 5% |
| terminal run failure rate | 不高于 10% |
| p95 latency 相对 stable | 增幅不高于 50% |
| mean cost per Run 相对 stable | 增幅不高于 30% |
| unknown / invalid structured result rate | 不高于 10% |

普通指标达到最小样本后才判定；硬安全事件无需等待样本。候选和 stable 基线必须来自同一 rehearsal、相同操作分布和同一 metric contract，二者都至少有 20 个 Runs。基线不足时状态为 `hold`，不能晋级，也不因信息不足自动回滚。

指标计算固定为：

- failure rate 的分母是窗口内对应 cohort 的 terminal Runs。
- unknown rate 的分母是窗口内所有受结构契约约束的判定；observation 同时保存分子和分母。
- p95 使用 nearest-rank，不在不同算法之间切换。
- 相对增幅为 `(candidate - stable) / max(stable, epsilon)`；epsilon 在 deployment thresholds 中冻结。

对表中的最大值门槛，等于或超过阈值即触发失败；只有严格低于阈值才通过。这些是可靠性 guardrail，不是统计显著的教学效果检验。阈值可通过新 deployment version 修改，不能改写正在观察的版本。

### 9.2 事务化回滚

Health Evaluator 检测到触发条件后，在一个事务中：

1. 以 advisory lock 锁定 environment，并 `FOR UPDATE` 锁定 environment head 后读取当前 deployment。
2. 确认故障 deployment 仍是当前 Canary/Active 且版本与窗口一致。
3. 写入不可变 health window 和 rollback audit event。
4. 创建 `rolled_back` deployment snapshot：保留故障 candidate，服务策略恢复为 `stable_policy_hash`，candidate 流量设为 0。
5. 以 expected version 更新 environment head，使其指向 rollback snapshot。
6. 提交后发送 deployment-change Outbox。

迟到 observation 可以保存，但若其 deployment 已不是当前版本，只能形成历史窗口，不能再次切换指针。重复 evaluator 使用相同 command/window key，结果幂等。

### 9.3 失败策略

- PostgreSQL 不可用：Run 无法持久化 assignment，因此不接受新 Run，返回可重试 503；不能只靠进程缓存假装成功受理。
- PostgreSQL 可用但候选制品缺失、哈希不符或 runtime 不兼容：候选 Run 受理失败并冻结 deployment，不静默改派 stable。
- Stable 制品已在本地校验缓存：缓存可减少读取开销，但数据库中的 assignment 仍是权威。
- Redis 不可用：Run 与 assignment 留在 PostgreSQL/Outbox，恢复后重投。
- Health evaluator 不可用：停止晋级；当前 Canary 不自动扩大流量，告警并等待恢复。
- 指标或基线不完整：判为 `hold`，不当作通过。

## 10. 安全、权限与审计

- 发布命令要求独立 command principal；运行 Worker 没有发布权限。
- 命令必须提供 actor、reason、command ID 和 expected version。
- Ops API/Console 只读，不接受状态变更。
- assignment secret、模型密钥、token 原文和私有载荷不进入审计或 Trace。
- 策略组件继续受 allowlist、长度、哈希和 runtime compatibility 约束。
- rehearsal token 使用短 TTL、单次 nonce 和受控 operation allowlist。
- 数据库通过角色和约束保护 immutable artifact、receipt 和 audit event。
- 所有拒绝也写审计：缺门禁、版本冲突、非法状态、证据不匹配和权限不足均可复盘。

## 11. 接口边界

实施必须拆分为以下模块：

- `PolicyArtifactRepository`：注册、校验和读取不可变策略。
- `PromotionRepository`：deployment 状态机、CAS 和审计事务。
- `PolicyAssigner`：验证 rehearsal 上下文并计算确定性 cohort。
- `GateVerifier`：按发布协议验证必要回执，不运行评测。
- `JudgeV3`：结构化判定、一次 repair 和 unknown 处理。
- `PolicyObservationRecorder`：幂等写单 Run 指标。
- `PolicyHealthEvaluator`：冻结窗口、比较基线和发起回滚命令。
- `RehearsalTokenVerifier`：签名、TTL、nonce 和 operation 校验。
- `PromotionCommandService`：唯一写命令入口。
- `PromotionQueryService`：Ops 与报告使用的只读视图。

这些模块不能导入 FastAPI 全局对象；服务入口负责身份和 transport，domain service 负责不变量，repository 负责事务。

## 12. 测试策略

### 12.1 单元测试

- artifact 规范化、哈希碰撞拒绝和 runtime compatibility。
- Judge schema、verdict/reason/evidence 一致性、一次 repair、unknown。
- HMAC bucket 边界和固定向量。
- 状态机全部合法/非法迁移。
- receipt 绑定、过期协议和 unknown 拒绝。
- health threshold、最小样本、基线不足和硬安全事件。
- token TTL、nonce、operation 和 namespace 校验。

### 12.2 PostgreSQL 集成测试

- Run 受理与 assignment/Outbox 同事务。
- 并发相同 request 的幂等 assignment。
- attempt、lease takeover 和 expert job 继承固定版本。
- stale expected version 不能覆盖并发晋级。
- 两个 evaluator 只能提交一次回滚。
- 迟到 observation 不影响新 deployment。
- append-only 表不能 UPDATE/DELETE。
- rehearsal 数据库角色不能写生产 namespace。

### 12.3 多进程故障测试

使用真实 PostgreSQL、Redis 和至少两个 Worker 验证：

- assignment 后 API 崩溃，重放仍返回同版本。
- Worker 在模型调用后崩溃，接管继续使用原策略。
- Candidate 运行中发生回滚，旧 Run 固定候选，新 Run 固定 stable。
- Redis 重复投递不会重复 observation 或提交。
- evaluator 在回滚事务前后崩溃均可幂等恢复。

### 12.4 端到端受控演练

一次正式演练包含两个场景：

1. **健康 Canary**：候选通过门禁，在固定比例流量下完成至少 20 个 candidate Runs 和 20 个匹配的 stable Runs，生成 `pass` health window，但不会自动向真实用户发布。
2. **故障 Canary**：注入可复现的延迟或提交失败，超过冻结阈值，系统自动回退 stable；验证新旧 Run 的版本边界、隔离状态和审计时间线。

## 13. 验收标准

M3 只有在以下证据全部存在时才完成：

1. 迁移、模型和约束证明 PostgreSQL 是发布权威。
2. 自动化测试证明首次受理固定版本，重试、接管和专家链不漂移。
3. Judge v3 fixture 证明矛盾/无效输出不会被当成通过。
4. 门禁测试证明人工命令无法绕过 formal holdout、Shadow 或 Canary。
5. 真实 PostgreSQL + Redis + 多进程演练证明确定性分流和隔离写入。
6. 故障演练证明事务回滚、迟到样本隔离和旧 Run 固定。
7. Prometheus 指标、Trace 和机器可读报告可以互相定位同一 deployment/run。
8. 报告记录代码版本、配置、模型、数据角色、请求数、失败、中断和费用。
9. 文档明确标注受控演练，不声称真实学生效果或生产流量验证。
10. 全量回归、静态检查、依赖/密钥扫描和 CI 通过。

## 14. 演练产物与面试叙事

正式演练保留：

- `manifest.json`：代码、协议、runtime、模型、阈值和基础设施版本。
- `requests.jsonl`：逐 Run assignment、cohort、版本、结果、延迟和费用。
- `gate_receipts.jsonl`：所有 passed/failed/unknown 门禁回执。
- `health_windows.jsonl`：冻结窗口、基线、触发指标和判定。
- `audit_timeline.jsonl`：注册、晋级、拒绝和回滚命令。
- `summary.md`：事实、限制、失败和成本摘要。
- Prometheus snapshot 与关键 Trace ID。

Harness 岗面试重点：

- 为什么分配必须和 Run 受理同事务；
- at-least-once 下如何靠不可变 assignment、fencing 和幂等 observation 保证效果一致；
- 回滚如何避免迟到样本和并发命令覆盖。

Agent 算法岗面试重点：

- Judge invalid/unknown 为什么必须独立于 fail；
- campaign、holdout、策略、Judge、代码和成本如何形成证据绑定；
- Shadow、Canary operational guardrail 与真实教学效果检验的边界。

## 15. 实施顺序

1. Judge v3 与不可变 gate receipt。
2. PostgreSQL policy artifact/deployment/audit 模型和状态机。
3. Run admission assignment、版本继承和兼容读取。
4. Shadow execution 与 observation。
5. Rehearsal token、namespace 和 Canary 写隔离。
6. Health evaluator 与事务化 rollback。
7. Ops 只读查询、指标和报告。
8. 多进程故障演练、CI、文档和面试材料。

每一步先以测试证明不变量，再接入下一层。旧文件 Registry 在迁移期仅服务单进程本地模式；M3 验收后，分布式模式禁止使用文件指针作为发布权威。
