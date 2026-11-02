# EduAgent 面试叙事与技术深度设计

日期：2026-11-02
状态：已批准，待实施计划
主投岗位：Agent Harness 工程，Agent 算法为辅助路径

## 1. 背景

EduAgent 已具备三层工程能力：

- M1 Durable Run Plane：PostgreSQL 权威运行状态、Redis Streams 投递、
  lease、fencing、outbox 和崩溃接管；
- M2 Bounded Expert Plane：冻结脱敏快照、只读专家执行、双重 fencing、
  父侧结果采用和 Ops Console；
- M3 Trusted Policy Promotion：Judge v3 资格绑定、Shadow、Canary、
  matched health window、自动回滚和不可变 Run binding。

Task 10 已完成真实 PostgreSQL/Redis 多进程 fixture 集成、SIGKILL 接管、
Compose 动态 smoke 和远程 CI。绑定 source revision 为 `f8b8e3c`，最终文档
revision 为 `e4ea5c3`。正式 eligible campaign rehearsal 未执行；Task 9 功能
已验证，但独立验收未完整封存。

当前主要问题不是缺少技术实现，而是对外表达分散：

1. README 首屏仍以英语学习应用为主，Harness 主线埋在长篇功能说明之后；
2. M0-M3 被写成能力列表，没有形成“失败问题、设计决策、验证证据”的演进故事；
3. `interview-readiness.md` 仍包含 Task 9/10 尚待实现的过期状态；
4. 技术资料很多，但没有按面试追问层级组织；
5. fixture、工程可靠性、模型效果和学习效果的结论边界需要保持一致。

## 2. 目标

本轮只整理现有成果，不新增系统能力，不修改核心实现。

### 2.1 GitHub 首页

让招聘方在 README 前两屏、一分钟内回答：

- 这个项目是什么；
- 它解决了哪类 Agent 工程难题；
- 最重要的架构决策是什么；
- 有哪些可复现证据；
- 哪些结论项目没有声称。

### 2.2 现场讲解

提供 30 秒、3 分钟和 10 分钟三档讲解。三档讲解共享同一事实主线，
能够自然进入白板、演示和源码追问。

### 2.3 技术深度

把现有实现整理为六组技术主题。每个主题均能从一句话判断下钻到机制、
源码、失败证据、替代方案和未解决边界。

## 3. 非目标

- 不新增 M4 或其他功能里程碑；
- 不修改 Python、TypeScript、Compose、CI 或测试代码；
- 不重新运行真实模型评测；
- 不执行缺少正式 eligible campaign 的 rehearsal；
- 不把 fixture 演练描述为真实策略发布；
- 不把工程测试描述为模型质量或学习效果证据；
- 不为简历另外维护一套互相独立的事实口径。

## 4. 叙事定位

### 4.1 主定位

> EduAgent 是面向有状态 Agent 的证据驱动执行与策略发布 Harness。
> 它以自适应教学为高一致性场景，处理重试、故障接管、专家委派和
> 策略变更下的状态可信问题。

教育场景用于说明为什么独立作答、受助表现、掌握度、公开回复和策略身份
不能被重复提交或错误污染。教育功能不是 GitHub 首屏的第一主角。

### 4.2 主故事

故事按四个阶段展开：

1. **M0 单机教学 Harness**：先保护业务事务、幂等和学习证据；
2. **M1 Durable Run Plane**：Worker 会崩溃，因此需要持久运行身份、
   lease、fencing、outbox 和可恢复 Trace；
3. **M2 Bounded Expert Plane**：专家需要独立扩展，但不能获得学生状态
   写权限，因此使用冻结快照、只读执行和父侧采用；
4. **M3 Trusted Policy Promotion**：算法候选不能由离线分数直接上线，
   因此引入资格绑定、Shadow、Canary、健康窗口和事务化回滚。

每个阶段必须使用同一表达结构：

> 失败问题 -> 设计决策 -> 核心不变量 -> 可复现证据 -> 适用边界

## 5. 信息架构

### 5.1 README

README 调整为以下顺序：

1. **首屏定位**
   - 项目名称与一句话价值；
   - M1、M2、M3 三项核心能力；
   - 绑定验收记录的证据数字；
   - 一句结论边界。
2. **为什么需要 Agent Harness**
   - 有状态 Agent 与一次性聊天的区别；
   - 重试、崩溃、委派和策略变化带来的风险。
3. **M0-M3 演进**
   - 每阶段按失败问题、决策和证据表达。
4. **权威边界总图**
   - PostgreSQL：运行身份、租约、策略和审计；
   - Redis Streams：可重复投递；
   - SQLite：当前教学业务事务的单写权威。
5. **三个技术案例**
   - 锁等待后重新验证 authority；
   - Expert accepted、adopted 和 public delivery 的分离；
   - 回滚只影响新 Run，旧 Run 保持不可变 binding。
6. **五分钟复现**
   - distributed profile；
   - SIGKILL 接管与 fixture promotion；
   - Ops 的 Run、Trace、Expert 和 Policy 证据。
7. **验证结果与证据入口**
   - 非分布式、分布式、前端 E2E 和远程 CI；
   - 数字均链接至权威验收记录。
8. **诚实边界**
   - SQLite 单写；
   - 外部模型副作用不承诺 exactly-once；
   - Task 9 独立验收未完整封存；
   - 正式 Judge v3 rehearsal 未执行；
   - 没有真实学生学习效果结论。
9. **应用场景与教学设计**
   - 保留现有学习者建模、教学支架、长期记忆、四 Agent 和 API 内容；
   - 下移层级，不删除有效说明。
10. **安装、运行和文档索引**

README 使用中文为主，保留通用英文技术名词。所有关键数字必须带权威来源，
不使用无法持续维护的营销式 badge。

### 5.2 现场讲解手册

新增 `docs/engineering/interview-playbook.md`，包含：

- 30 秒电梯陈述；
- 3 分钟主故事；
- 10 分钟架构深讲；
- 白板绘制顺序；
- 五分钟演示顺序；
- Harness 主线与 Agent 算法支线；
- 开场、转场、边界说明和收尾；
- 常见追问到技术深度文档的链接。

三档讲解不得维护三套不同事实，只允许改变信息密度。

### 5.3 技术深度手册

新增 `docs/engineering/interview-technical-deep-dive.md`。每个主题使用统一模板：

1. 主张；
2. 不变量；
3. 实现机制和数据流；
4. 可复现失败；
5. 修复与验收证据；
6. 设计取舍；
7. 替代方案；
8. 未解决边界；
9. 关键源码和文档入口。

技术主题包括：

1. 状态权威与跨存储一致性；
2. Lease、fencing 与阻塞锁后的权限复核；
3. 有界 Expert Plane 与唯一写权限；
4. 策略身份、版本固定和事务化回滚；
5. 自动契约、Judge、工程交付与学习效果的证据等级；
6. Trace、故障注入和可复现性。

每组主题提供四层答案：

- L1：一句话判断；
- L2：机制与白板数据流；
- L3：源码、失败测试和验收证据；
- L4：替代方案、演进路径和技术债务。

技术债务需明确记录，包括千行级 repository/query 模块、SQLite 单写边界、
正式 campaign 缺失和多租户隔离未完成。技术债务不得包装成已解决能力。

### 5.4 事实索引

更新 `docs/engineering/interview-readiness.md`：

- 定位为事实和证据索引，不再承担完整现场话术；
- 同步 Task 10、远程 CI 和 artifact；
- Task 9 保持“功能验证通过，独立验收未完整封存”；
- 删除 Task 9/10 尚待实现、Compose 未动态验证等过期陈述；
- 保留历史失败、修复和独立审查证据；
- 链接现场讲解与技术深度手册。

## 6. 事实流与所有权

文档事实采用单向流：

```text
M1-M3 权威工程文档 / 验收记录 / CI
                    |
                    v
       interview-readiness.md
          /                  \
         v                    v
      README       interview-playbook.md
                              |
                              v
             interview-technical-deep-dive.md
```

所有运行数字、状态和限制先在事实索引中确认。README 和面试材料只能概括，
不能创造新的完成状态。技术深度手册可以解释机制，但不能扩大证据范围。

## 7. 现场讲解内容合同

### 7.1 30 秒

必须覆盖：

- 有状态 Agent Harness 定位；
- 教育状态不能被重复或错误提交的核心冲突；
- M1-M3 的递进；
- 一项真实故障证据；
- 一句诚实边界。

### 7.2 3 分钟

必须覆盖：

- 场景和失败模型；
- exactly-once 不可得时的工程选择；
- Expert 计算与业务写权限分离；
- 算法候选的可信发布门禁；
- 测试、CI 和正式 rehearsal 的证据等级。

### 7.3 10 分钟

必须覆盖：

- 权威边界图；
- Worker lease/fencing 接管；
- Expert 冻结快照和父侧采用；
- policy binding、Shadow、Canary 和 rollback；
- Ops/Trace 如何验证设计主张；
- 当前限制和下一步演进。

## 8. 技术案例选择

优先使用以下案例，因为它们同时具备机制、失败和修复证据：

1. **锁等待后的权限失效**
   - 说明条件更新不等于最终 authority 正确；
   - 关联 live authority、attempt deadline 和锁后复核。
2. **双重 fencing 的 Expert 采用**
   - 区分 parent epoch 与 expert attempt；
   - 说明只读计算结果为何仍需父侧校验。
3. **不可变 policy binding 与回滚**
   - 说明旧 Run、新 Run、迟到 observation 的不同处理；
   - 关联真实多进程 promotion fixture。
4. **证据不足时的 fail closed**
   - 说明 Judge `unknown`、缺失费用和不合格 campaign；
   - 对比开发重放与正式发布资格。

README 只展示前三项的简版。现场和技术深度手册可展开第四项。

## 9. 错误与边界处理

文档实施时按以下规则处理冲突：

- README 与验收文档冲突时，以验收文档为准；
- 历史报告与当前代码状态冲突时，保留历史语境，不把旧结果改写成当前结果；
- 测试数量缺少绑定 revision 时，不进入首屏；
- 相对链接无法定位时，修复链接或删除不可靠引用；
- 正式 rehearsal 缺失时，只描述外部前置条件和 fail-closed 探测；
- Task 9 不得改写为完整独立验收通过；
- 任何“效果提升”必须说明是工程指标、模型指标还是学习效果。

## 10. 验证

本轮不改代码，因此不重新运行完整后端测试矩阵。验证包括：

1. 对照以下权威来源人工核验：
   - `docs/engineering/distributed-run-plane.md`；
   - `docs/engineering/bounded-expert-plane.md`；
   - `docs/engineering/trusted-policy-promotion.md`；
   - `docs/engineering/m3-policy-promotion-acceptance.md`。
2. 检查 README 和三份面试文档中的本地相对链接；
3. 检查关键源码路径和命令存在；
4. 检索并消除 Task 9/10 的过期状态；
5. 检索 unsupported claims：
   - 正式发布完成；
   - 真实模型效果提升；
   - 学习效果提升；
   - exactly-once；
   - 多 Worker 业务状态水平写入；
6. 执行 `git diff --check`；
7. 检查最终 diff 仅包含批准的文档范围。

## 11. 验收标准

- README 前两屏能在一分钟内说明定位、难题、架构和证据；
- README 展示 M0-M3 的因果演进，而不是功能堆叠；
- 30 秒、3 分钟和 10 分钟讲解可直接使用；
- 六组技术主题均包含机制、失败、证据、取舍和边界；
- Harness 主线清晰，Agent 算法支线可以独立进入；
- Task 9、Task 10 和 formal rehearsal 状态在四份文档中一致；
- fixture、工程可靠性、模型质量和学习效果没有混淆；
- 所有关键路径、链接和命令可定位；
- `git diff --check` 通过；
- 未修改核心实现、配置、测试或运行时行为。

## 12. 实施顺序

1. 更新事实索引；
2. 重构 README；
3. 编写现场讲解手册；
4. 编写技术深度手册；
5. 执行交叉一致性和链接核验；
6. 复审结论边界；
7. 提交文档变更。
