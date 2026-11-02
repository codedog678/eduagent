# EduAgent

**多 Agent 自适应教学系统，包含持久化执行、故障恢复和策略发布能力。**

[是什么](#是什么) · [做了什么](#做了什么) · [怎么做的](#怎么做的) ·
[技术栈](#技术栈) · [重难点](#重难点) · [测试](#测试)

[整体架构图](#整体架构) · [学习数据流转图](#学习数据流转) · [教育学原理](#教育学原理)

## 是什么

EduAgent 是一个面向英语学习的多 Agent 教学系统。学生可以围绕知识点完成
练习、获取渐进提示、向导师追问，并在后续会话中继续之前的学习任务。
系统根据答题表现维护知识掌握状态，推荐后续知识点和复习安排。

项目还实现了 **Agent Harness**：负责管理一次 Agent 任务的上下文、工具权限、
执行预算、状态提交和恢复。教学是它的具体应用场景——一次互动会同时改变
测验、学习记录和后续计划，因此还需要处理重复请求、进程崩溃和策略切换。

## 做了什么

| 能力 | 已实现的功能 |
| --- | --- |
| 练习与反馈 | 服务端出题和判分，错答后可重试、逐级求助或查看解析；区分独立作答与受助作答 |
| 个性化学习 | BKT 掌握度估计、知识点前置依赖、薄弱点推荐、SM-2 间隔复习 |
| 跨会话答疑 | 持久化对话和学习证据，接续导师追问；用工具查询历史、阅读来源和查询知识关系 |
| 长期记忆 | 保存有来源和版本的偏好、目标与教学片段；支持关键词与向量混合检索 |
| 复合任务 | Coordinator 按需组织评估、课程规划和导师答疑；支持有界重规划和部分结果 |
| 可靠执行 | 请求去重、事务提交、超时与并发控制；分布式任务支持租约、故障接管和持久化 Trace |
| 专家委派 | 独立 Expert Worker 根据只读快照计算草稿，父任务校验后采用并提交 |
| 评测与策略发布 | 离线回归、真实模型运行记录、Judge v3 资格校验，以及 Shadow、Canary 和自动回滚 |
| 运维界面 | 查看 Run、Attempt、Expert、Trace、策略版本、健康窗口与回滚审计 |

当前已完成教学主链路及 M1–M3 工程实现：M1 是持久化任务执行，M2 是有界专家
委派，M3 是受控策略发布。策略发布已通过测试候选的工程演练，正式 Judge v3
发布资格演练尚未执行；真实学生学习效果也尚未开展实验验证。

## 怎么做的

### 整体架构

教学应用由交互层、Harness、Agent 执行层和学习状态层组成。下面展示普通模式的
组件关系；分布式任务调度在后面的执行架构图中展开。

```mermaid
flowchart TB
    UI["React 学习界面<br/>练习 / 答疑 / 历史 / 复习"] --> API["FastAPI<br/>REST / WebSocket"]
    API --> H["LearningHarness<br/>去重 / 超时 / 检查点 / 事务提交"]

    subgraph EXEC["Agent 执行层"]
        ORCH["AgentOrchestrator + EventBus"]
        ROLES["Assessment / Tutor<br/>Curriculum / Engagement"]
        COORD["Coordinator<br/>复合计划 / 专家委派 / 有界重规划"]
        TUTOR["TutorRuntime<br/>上下文构建 / 原生工具循环"]
        TOOLS["受限工具层<br/>历史检索 / 来源读取 / 知识查询"]
        ORCH --> ROLES
        COORD --> TUTOR
        ROLES --> TUTOR
        TUTOR --> TOOLS
        COORD --> TOOLS
    end

    H --> ORCH
    H --> COORD
    ROLES --> MODEL["学习者模型 / 知识 DAG / SM-2"]
    TUTOR --> LLM["LLMService<br/>模型调用 / 额度 / 本地回退"]
    COORD --> LLM
    TOOLS --> HISTORY["LearningHistory<br/>对话 / 学习证据 / 长期记忆检索"]
    HISTORY --> DB["SQLite<br/>测验 / 证据 / 计划 / 检查点"]
    H -->|"提交本轮业务状态与结果"| DB
    MODEL -.->|"状态由 Harness 纳入检查点"| DB
```

普通答题经 EventBus 驱动四个角色；REST 自由答疑由 Tutor 使用 TutorRuntime，
复合任务则由 Coordinator 按需组织专家和最终导师回复。图中的角色仍在同一个
进程内运行；独立 Expert Worker 属于后面的分布式模式。学习者模型和 Agent
上下文在进程内使用，持久化由 Harness 统一提交，重启时从检查点恢复。

### 教学流程：状态、证据与 Agent 协作

一次练习的主要流程：

1. 服务端生成并保存题目、答案和测验 ID，客户端只接收题干与选项。
2. Assessment 根据保存的答案判分；只有首次、未求助的作答更新掌握度和复习计划。
3. Tutor 提供反馈，Curriculum 更新课程与复习建议，Engagement 根据互动记录提供节奏支持。
4. Harness 在同一 SQLite 事务中提交测验、学习状态、公开消息、证据和本轮结果。
5. 学生继续追问时，Tutor 读取同一主题线程的历史；导师提出待答问题后，下一轮可以接续。

普通教学流程通过进程内事件总线协作。综合请求（如“结合上次错误安排十分钟
复习”）由 Coordinator 生成有依赖关系的计划，再调用评估、课程和导师专家。
专家提出的练习建议仍需父任务校验，不能直接修改掌握度或公开回复。

Tutor 使用原生工具调用协议。工具参数由严格 schema 校验，学习者范围由服务端
注入；模型不能通过自行填写学习者 ID 扩大访问范围。历史检索结合 SQLite FTS5
和可选的 `bge-m3` 向量召回，用 RRF 合并结果，来源原文可以分页读取。
没有模型密钥时使用明确标记的本地规则或模板；向量不可用时回退到关键词检索。

### 学习数据流转

以一次测验作答及其后续答疑为例。掌握度和学习记录走不同的更新路径：
所有合法作答都会保存行为证据，只有首次独立作答进入 BKT 和复习计划更新。

```mermaid
sequenceDiagram
    actor S as 学生 / 前端
    participant H as Harness
    participant A as 教学 Agent
    participant D as SQLite
    Note over S,D: ① 出题：答案保留在服务端
    S->>H: 请求练习
    H->>D: 保存题目、答案和测验状态
    H-->>S: 返回题干、选项和 quiz_id
    Note over S,D: ② 作答：判分与学习证据分离
    S->>H: 提交选项、request_id 和 quiz_id
    H->>D: 读取题目，校验归属和请求指纹
    alt 首次作答且未求助
        H->>A: 判分后更新 BKT 和 SM-2
    else 重试、提示后或对话求助后作答
        H->>A: 保留掌握度和复习计划，记录受助表现
    end
    A-->>H: 反馈、学习状态和后续建议
    H->>D: 同事务提交测验、证据、检查点和结果
    D-->>H: 提交成功
    H-->>S: 返回反馈，相同请求可重放
    Note over S,D: ③ 后续答疑：从已提交证据接续
    S->>H: 追问或补充回答
    H->>D: 读取主题历史、评估证据和待答计划
    H->>A: 按预算构建上下文，Tutor 回答
    A-->>H: 公开回复或待答问题
    H->>D: 同事务保存回复、待答状态和本题受助标记
    D-->>H: 提交成功
    H-->>S: 返回回复，需要补充时等待下一轮
```

该图表示逻辑数据流，Agent 内部调用由 EventBus 或 Coordinator 编排。
例如，学生第一次答错，随后请求提示并答对：第一次独立错答会更新掌握度，
后续正确答案记为受助表现，保留练习过程，但不会把提示后的正确直接计为独立掌握。
失败时恢复本轮之前的学习状态，并保留失败执行记录。

### 教育学原理

系统将学习证据用于下一步教学决策：先判断学生当前能独立完成什么，再决定
提供多少帮助、是否回到前置知识，以及何时再次复习。

| 原理与依据 | 在系统中的落实 | 适用边界 |
| --- | --- | --- |
| **形成性评价**：用学习过程中的证据调整后续教学（Black & Wiliam, 1998） | 错答后保留重试机会，给出线索检查建议；评估结果用于补救、课程推荐和复习 | 自动判分与提示是形成性反馈机制，反馈的教学质量仍需审阅 |
| **支架式教学**：为当前任务提供逐步支持（Wood、Bruner & Ross, 1976） | 主动求助时按“思路检查 → 学科判断框架 → 选项验证”升级提示；答案与解析由学生主动查看 | 当前是固定三级提示；尚未实现经验证的个性化支架撤除策略 |
| **元认知与自我调节学习**：支持学生检查理解、监控策略并调整学习（Zimmerman, 2002） | 提示要求圈出线索、说明选择依据和排除理由；允许选择求助时机，并可选记录答题把握程度 | 只提供部分调节支架，未实现完整 SRL 测量，也不将把握程度直接当作能力 |
| **知识追踪**：通过连续作答推断知识状态（Corbett & Anderson, 1995） | 按“学习者 × 知识点”用 BKT 维护掌握概率，考虑猜测、失误、初始掌握与学习转移 | 当前仅独立作答更新；学习转移只在答对后应用，属于项目改动，参数未经真实学生数据拟合 |
| **前置知识与循序学习**：学习任务应考虑已有基础 | 用 DAG 表达知识依赖，课程推荐和推进测验检查前置知识；基础不足时建议先补练 | 图谱和门槛是人工配置的教学规则，不代表已验证的最优学习路径 |
| **间隔练习**：将练习分散到不同时间（Cepeda 等, 2006） | 用 SM-2 调整复习间隔和难度因子，展示到期项目与七天计划 | SM-2 是调度实现；保持率为启发式估计，尚未证明该配置下的长期保持收益 |

独立与受助证据分离是贯穿这些机制的设计原则：支架可以帮助完成当前任务，
受助成功需要与后续独立练习分别记录。Engagement 的节奏建议来自近期正确率、
耗时和会话长度等行为规则，用于提供支持，不视为经过验证的情绪诊断。

<details>
<summary>教育学参考文献</summary>

- Black, P., & Wiliam, D. (1998). *Assessment and Classroom Learning*. [DOI](https://doi.org/10.1080/0969595980050102)
- Wood, D., Bruner, J. S., & Ross, G. (1976). *The Role of Tutoring in Problem Solving*. [DOI](https://doi.org/10.1111/j.1469-7610.1976.tb00381.x)
- Zimmerman, B. J. (2002). *Becoming a Self-Regulated Learner: An Overview*. [DOI](https://doi.org/10.1207/s15430421tip4102_2)
- Corbett, A. T., & Anderson, J. R. (1995). *Knowledge tracing: Modeling the acquisition of procedural knowledge*. [DOI](https://doi.org/10.1007/BF01099821)
- Cepeda, N. J., et al. (2006). *Distributed practice in verbal recall tasks: A review and quantitative synthesis*. [DOI](https://doi.org/10.1037/0033-2909.132.3.354)

这些文献用于说明设计依据，不构成 EduAgent 学习效果的实证结论。

</details>

### 执行架构：分开任务调度与业务提交

普通模式由一个后端进程执行教学任务，SQLite 保存业务状态；同一学习者的
请求串行，不同学习者的请求可并发处理。启用分布式模式后，增加 PostgreSQL
和 Redis 来管理任务投递、租约和故障恢复：

```mermaid
flowchart TB
    API["分布式 API"] --> PG["PostgreSQL<br/>任务状态 / 租约 / 策略绑定"]
    PG --> OUT["事务 Outbox"]
    OUT --> REDIS["Redis Streams<br/>任务投递"]
    REDIS --> RUN["Run Worker<br/>父任务执行"]
    RUN --> EXPERT["Expert Worker<br/>只读快照 → 草稿"]
    EXPERT --> CHECK["父任务校验<br/>权限 / 来源 / 版本"]
    CHECK --> STATE["Harness + SQLite<br/>教学事务提交"]
    PG --> OPS["Ops Console / Trace"]
```

PostgreSQL 决定谁有执行和提交权限；Redis 负责投递，可以出现重复消息。
Worker 用租约维持执行权，每次接管获得更高的 fencing token（执行代次标识），
旧 Worker 即使继续运行，也不能用过期 token 提交 PostgreSQL 结果。

Expert Worker 有自己的租约，只读取冻结、脱敏且带预算的快照，不挂载教学
SQLite。父 Run Worker 校验专家结果的来源、策略版本和当前权限后，统一提交
教学业务状态。SQLite 仍由文件锁保证单写，任务恢复复用原请求 ID。

### 评测与发布：先验证候选，再限制影响范围

评测分别记录确定性契约检查、模型语义判断、运行 Trace 和用量。Judge v3
校验判定、理由与证据的一致性；证据不足或无法核验时记为 `unknown`，不授予发布资格。

候选策略先进入 **Shadow**（隔离试跑，不提交主业务状态），再进入 **Canary**
（按固定规则分配少量受控流量）。系统在匹配窗口中比较延迟、错误和费用等
指标，达到失败阈值时事务化回滚。每个 Run 在受理时固定策略身份；回滚影响
后续新请求，已经受理的 Run 保留原版本，便于恢复与审计。

### 代码入口

| 路径 | 职责 |
| --- | --- |
| [python/api/](python/api/) | 普通与分布式 API、请求编排、Ops 查询 |
| [python/agents/](python/agents/) | Assessment、Tutor、Curriculum、Engagement |
| [harness.py](python/core/harness.py) | 请求去重、执行预算、测验与事务提交 |
| [tutor_runtime.py](python/core/tutor_runtime.py) | 上下文构建、原生工具循环与导师接续 |
| [learning_history.py](python/core/learning_history.py) | 公开对话、学习证据、历史检索与来源读取 |
| [python/core/distributed/](python/core/distributed/) | 任务租约、专家执行、策略绑定与晋升 |
| [python/evals/](python/evals/) | 数据集、评测执行器、Judge 与报告工具 |
| [frontend/src/](frontend/src/) · [frontend/ops/](frontend/ops/) | 学习界面与 Ops Console |

## 技术栈

| 层次 | 技术与用途 |
| --- | --- |
| 后端 | Python 3.11+、FastAPI、Uvicorn、asyncio；REST 与 WebSocket |
| Agent 与模型 | 自建 Harness、事件总线、工具循环；Anthropic / OpenAI SDK，支持 DeepSeek、MiniMax |
| 学习算法 | BKT、知识依赖 DAG、SM-2；分级提示与学习行为记录 |
| 存储与检索 | SQLite / FTS5 保存教学证据；可选 `bge-m3` 向量召回、RRF 融合 |
| 分布式执行 | PostgreSQL 16、SQLAlchemy / asyncpg、Redis Streams；租约、fencing、Outbox |
| 前端 | React 18、TypeScript、Ant Design 6、Vite 7 |
| 可观测性 | 持久化 Trace、OpenTelemetry、Prometheus、Ops Console |
| 部署与测试 | Docker Compose、Nginx、GitHub Actions、pytest / pytest-asyncio、Playwright |

### 快速开始

需要 Git、Docker 和 Docker Compose。首次在新目录中配置：

```bash
git clone https://github.com/codedog678/eduagent.git
cd eduagent
cp .env.example .env

# 首次生成并写入本地配置，后续启动复用这份 .env
postgres_password="$(openssl rand -hex 24)"
{
  echo "POSTGRES_PASSWORD=$postgres_password"
  echo "DATABASE_URL=postgresql+asyncpg://postgres:${postgres_password}@postgres:5432/edu_agent"
  echo "DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres:${postgres_password}@postgres:5432/edu_agent"
  echo "OPS_API_TOKEN=$(openssl rand -hex 24)"
  echo "PROMOTION_COMMAND_PRINCIPAL=local-rehearsal"
  echo "PROMOTION_REHEARSAL_SECRET=$(openssl rand -hex 32)"
  echo "PROMOTION_ASSIGNMENT_SECRET=$(openssl rand -hex 32)"
} >> .env
unset postgres_password

docker compose up --build -d
```

`.env` 被 Git 忽略。已有数据库卷时应复用首次设置的密码。
默认不填写模型密钥也能体验本地模式；接入真实模型可按
[.env.example](.env.example) 配置 `LLM_PROVIDER` 和对应密钥。
Compose 当前转发 Anthropic 和 DeepSeek 配置，其他 provider 或自定义 Tutor
参数需在对应服务的 `environment` 中补充。

| 服务 | 地址 |
| --- | --- |
| 学习界面 | http://localhost:3000 |
| 普通 API 文档 / 健康检查 | http://localhost:8888/docs · http://localhost:8888/api/health |
| 分布式 API（需启用 profile） | http://localhost:8890/docs · http://localhost:8890/api/health |
| Ops Console（需启用 profile） | http://localhost:3000/ops/ |

初始化演示学习者：

```bash
curl -X POST 'http://localhost:8888/api/demo/init?learner_id=student_001'
```

需要查看任务调度和专家执行时，启用分布式模式：

```bash
docker compose --profile distributed up --build -d
```

该 profile 使用 template 模型运行工程演示。Ops Console 使用本地 `.env` 中的
`OPS_API_TOKEN` 访问只读证据。真实故障演示的环境要求和命令见
[专家执行协议](docs/engineering/bounded-expert-plane.md)。

### 本地开发

后端使用 Python 3.11+，前端使用 Node.js 20.19+（20.x）或 22.12+。
先完成上面的 `.env` 配置，再在仓库根目录启动后端：

```bash
docker compose up -d postgres
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./python[dev]"

# 本机进程连接 localhost；容器配置继续保留 postgres 主机名
set -a
source .env
set +a
export DATABASE_URL="postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@localhost:5432/edu_agent"
uvicorn api.main:app --reload --host 127.0.0.1 --port 8888
```

本地开发时先停止占用 8888 / 3000 端口的应用容器。在另一个终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

Vite 将 `/api`、`/ws` 代理到普通后端，将分布式与 Ops 请求代理到 8890。
Harness 使用 Unix 文件锁，后端运行在 macOS / Linux；Windows 可使用 WSL 或 Docker。

## 重难点

| 问题 | 处理方式 | 验证入口 |
| --- | --- | --- |
| 网络重试可能重复判分，或只提交部分学习状态 | 请求 ID + 内容指纹去重；回复、测验、证据与检查点同事务提交；完成请求重放结果 | [Harness 回归](python/tests/test_learning_harness.py) |
| 学生获得提示后答对，容易被误记为独立掌握 | 记录首次作答、重试、提示和对话受助；仅首次独立作答更新掌握度与复习 | [教学证据回归](python/tests/test_tutor_harness.py) |
| 多轮工具与专家调用可能耗尽预算，超时后继续占用资源 | deadline、模型 / 工具上限、学习者排队超时；服务进程内聊天、向量、重排和摘录共用模型额度 | [并发边界](docs/engineering/harness-concurrency-20261029.md) |
| Worker 等锁期间租约可能到期，锁前检查已失效 | 获取阻塞锁后用数据库当前时间重新校验 owner、token 和 deadline，再修改状态 | [真实等锁测试](python/tests/distributed/test_lease_lock_time.py) |
| 专家结果格式正确，但来自过期任务或越权来源 | 同时校验父任务与专家租约；结果先接收，再由父侧复核采用，专家没有教学写权限 | [专家协议](docs/engineering/bounded-expert-plane.md) |
| 候选策略出错，回滚与运行中任务、迟到观察发生交错 | 受理时固定版本；匹配健康窗口、锁定观察集合，事务内回滚并保留审计与 Outbox | [策略发布集成测试](python/tests/integration/test_policy_promotion.py) |

当前教学 SQLite 仍是单写存储；PostgreSQL 与 SQLite 没有跨库原子事务，
恢复依靠同请求重放。外部模型调用不保证恰好执行一次。当前 API 的学习者 ID
由客户端指定，多用户部署还需要登录主体认证；向量检索在授权范围内加载并
计算余弦，适用于小规模数据。更完整的设计取舍见
[技术深挖手册](docs/engineering/interview-technical-deep-dive.md)。

## 测试

### 已有验证

下面是 **2026-11-02、源码版本 `f8b8e3c`** 的归档结果；详细命令和证据见
[M3 验收记录](docs/engineering/m3-policy-promotion-acceptance.md)。

| 范围 | 结果 | 验证内容 |
| --- | --- | --- |
| 后端非分布式测试 | 850 passed，56 skipped | 教学主链路、工具协议、状态与评测边界；跳过项不计为通过 |
| PostgreSQL / Redis 分布式测试 | 1537 passed | 租约、等锁、旧 token 拒绝、真实多进程接管、专家与策略发布 |
| Ops Playwright | 54 passed | 桌面与移动视口下的页面行为、查询和证据展示 |
| GitHub Actions | 5 个 job 成功 | 后端、前端构建、打包、Compose smoke、分布式集成；[归档 CI](https://github.com/codedog678/eduagent/actions/runs/41457794154) |

故障测试使用真实 PostgreSQL、Redis 和子进程，包含 SIGKILL 强杀、接管、重复
投递、自动回滚与迟到观察。策略发布候选及回执使用测试 fixture，
`release_eligible=false`，这些结果证明对应工程路径，不能授予真实策略发布资格。
Ops Policies 功能已验证，但其独立审查未完整封存。

### 运行测试

在已安装 `python[dev]` 的环境中运行：

```bash
cd python

# 后端回归：不需要真实模型请求
LLM_PROVIDER=template python -m pytest tests -q -m "not distributed_integration"

# 内置离线评测
eduagent-eval validate
eduagent-eval run --suite builtin
```

分布式测试会重建目标库的测试表，需使用**独占测试数据库**，不要指向应用库。
先设置 `TEST_DATABASE_URL`（含账号和密码的 `postgresql+asyncpg://...`）及
`TEST_REDIS_URL`（测试 Redis URL），再在 `python/` 中运行：

```bash
export DISTRIBUTED_ENABLED=true
export DISTRIBUTED_EXPERTS_ENABLED=true
export DISTRIBUTED_TEST_DATABASE_URL="${TEST_DATABASE_URL:?请先设置独占测试数据库 URL}"
export DISTRIBUTED_DATABASE_URL="$TEST_DATABASE_URL"
export DISTRIBUTED_TEST_REDIS_URL="${TEST_REDIS_URL:?请先设置测试 Redis URL}"
export DISTRIBUTED_REDIS_URL="$TEST_REDIS_URL"
export LLM_PROVIDER=template
export MEMORY_RETRIEVAL_MODE=lexical
export MEMORY_WORKER_ENABLED=false

python -m pytest tests/distributed \
  tests/integration/test_distributed_failover.py \
  tests/integration/test_expert_failover.py \
  tests/integration/test_policy_promotion.py -q
```

前端构建与 Ops 页面测试，在 `frontend/` 中运行：

```bash
npm ci
npm run build
npx playwright install chromium
npm run test:e2e -- e2e/ops.spec.ts
```

Playwright 使用 mock API 检查页面行为，并自行启动 Vite；运行前释放 3000 端口。
真实服务接线由 CI 的 Compose smoke 另行验证。

### 真实模型评测

已有固定学生脚本的真实模型评测，保留逐条输入、公开回复、工具调用、Trace、
失败、代码版本和用量。Agent50 共完成 82 次模型请求，自动契约检查为 40/50；
最终任务语义与工具语义审阅尚未完成，因此不作为最终任务成功率。
真实模型运行会消耗额度，命令、预算与历史结果见
[评测文档与数据索引](docs/evals/README.md)。

自动检查、模型语义质量与真实学习效果分别评价。当前没有正式 eligible Judge v3
发布资格演练，也没有真实学生的学习效果因果实验。

进一步阅读：[执行协议](docs/engineering/distributed-run-plane.md) ·
[专家协议](docs/engineering/bounded-expert-plane.md) ·
[策略发布协议](docs/engineering/trusted-policy-promotion.md) ·
[工程过程](docs/engineering/problem-solution-log.md) ·
[证据索引](docs/engineering/interview-readiness.md)

**License：** [MIT](LICENSE)
