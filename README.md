# EduAgent

**融合学习者建模、教学支架与间隔复习的多 Agent 英语学习应用。**

EduAgent 将答题评估、个性化辅导、课程推荐与学习状态支持组织为四个协作角色。系统使用事件驱动方式连接各角色，将学习者表现、知识点依赖和对话上下文用于教学反馈，并通过 React 界面呈现练习、答疑、复习及学习分析。

项目结合教育技术中的个性化学习与教学支架设计，以及 Python 异步服务、LLM 集成和事件追踪等工程实践。

## 跨会话教学 Harness

学生可以开始新会话，并继续同一知识点的教学线程。系统将公开对话、错题评估和受助记录保存在 Harness SQLite 中，为 Tutor 构建带来源和预算的上下文。

配置远程模型后，Tutor 使用原生工具协议查询历史、阅读证据、查询知识关系或提出澄清问题。模型请求、工具次数和执行时间均受限，工具参数采用严格 schema，学习者范围由服务端执行上下文注入。未配置模型时保留明确标记的文本回退。

导师提出问题后，本轮可以执行完成并进入“等待学生回答”状态；下一条同线程消息接续。回复、学习状态和证据提交成功后才返回成功，相同请求可重放，失败重试分别保留执行记录。前端提供教学历史和本轮互动记录。

普通提问获取当前题目帮助也计为受助，随后答对不作为独立掌握度证据。`advance` 测验需先完成作答再进行本题答疑。

配置见 `.env.example` 的 `TUTOR_*`、`MEMORY_*` 和 `COORDINATOR_*`。长期记忆使用 FTS5 关键词与可选向量检索，已提交的等待计划支持跨轮接续。当前演示 API 仍使用学习者 ID，多用户部署需接入登录主体认证。

## 长期记忆与复合任务（v0.3）

记忆继续以 SQLite 中的公开原文为依据。明确偏好和目标保留来源、版本与有效期；新陈述可替代或撤销旧版本，未明确解决的同类冲突保留为候选。学生说“请记住……”时可直接暂存原话，随回复原子提交。稳定画像跨知识点可读；教学片段不改变 BKT。

原文按约 1200 字、100 字重叠分块，中文使用二元词、英文使用词项进入 FTS5；索引未就绪的合法原文仍可关键词检索。语义召回使用硅基流动 **`BAAI/bge-m3`**，向量按 provider、model、维度和内容 hash 隔离。两路通过 RRF 合并，默认最多返回 5 条，重排序默认关闭。无相关命中时返回空集；不会把最近记录伪装成相关证据。

在 `.env` 中填入 `SILICONFLOW_API_KEY`，重启后后台自动补建 embedding；也可用 `MEMORY_EMBEDDING_API_KEY` 单独配置。`GET /api/health` 返回实际检索模式、降级原因、向量数和待处理作业数。未配置密钥时为 lexical；接口失败时回退关键词。默认模型不带 Pro 前缀，账户可用性与免费额度以供应商为准。`MEMORY_RETRIEVAL_MODE=lexical` 可停止新增 embedding 请求。

后台使用独立连接、短事务及持久化重试队列；网络请求不持有写事务。每累计 6 条主题消息或显式记忆提案时生成教学摘录：远程模型只选择原文，服务端逐条核验引用；无聊天模型时保留原文摘录。摘录和向量分别记录 usage 与延迟，失败不回滚已成功的教学互动。`MEMORY_EXTRACTION_ENABLED=false` 可关闭自动摘录；处理中的后台请求取消后作业仍可重试。

综合请求如“结合上次错误安排十分钟复习”进入 Coordinator；也可显式调用 `POST /api/learning/task`（请求字段同 `/api/question`）。规划器按需选择 Assessment、Curriculum 和最后的 Tutor，执行经 schema 校验的拓扑计划。Assessment / Curriculum 使用独立的原生工具循环，自主选择历史搜索、分页原文、画像或知识关系等只读工具；可引用已完成上游专家的合法来源。Curriculum 只提出练习建议，由 Coordinator 校验并准备，不能直接改掌握度或嵌套调用 Harness。无远程聊天模型时使用明确标记的规则计划与专家建议。

复合任务默认最多 3 次委派、每轮最多 1 次剩余计划修订，全轮上限为 8 次模型请求、16 次工具调用，并共用 Harness 截止时间。单专家默认最多 3 次模型请求、4 次工具调用，执行期间为 Tutor 保留 2 次模型和 3 次工具预算；局部上限不能突破全轮限制，旧事件链上的 `generate_*` 也计入总预算。`COORDINATOR_MAX_DELEGATIONS` 可配置到 6，需配合模型和工具预算使用。

专家失败、来源不合法或建题被拒绝时，原有依赖任务不会继续执行。协调者可调用规划器替换剩余步骤，保留已完成成果和失败事实，并重新检查角色、任务 ID、依赖及剩余预算；无有效修订时返回明确的部分结果。计划 `status=completed` 表示本轮执行结束，`outcome` 区分 `completed`、`partial` 与 `awaiting_student`；包含失败步骤的保守降级仍标记 `partial`。Trace 包含真实修订、结果复用、检查结论、预算及来源；引用合法性不等同于语义支持。

共享异步工具层提供历史搜索/分页原文、学习画像、到期复习、知识关系、记忆提案、单题准备和专家委派。读工具瞬时失败最多重试一次，写操作仅暂存、不自动重试；参数错误、权限拒绝与空结果分别返回。`prepare_practice` 校验前置知识，一轮最多一题，答案仅存服务端；经过 Tutor 辅导的题标记为受助。正确提交关联题后关闭待答计划，单纯发出练习不代表学生已经完成。

`GET /api/learning/plan/{learner_id}?thread_id=...` 读取最新计划。计划 JSON 保存专家结果、动作收据和学生补充信息；跨会话接续保留原目标与约束，复用已完成且来源仍有效的结果，只重跑待答或失效步骤及其下游。旧版缺少结果的计划会重新执行相应专家。关联练习跨知识点接续时仍使用提示约束，不重复建题。计划、原文、测验、记忆及作业在同一父事务提交；失败不留下半成品。新字段兼容现有 SQLite schema v3，无需额外迁移。

当前限制：向量在授权范围内加载并用 Python 计算余弦，默认最多扫描最近 2000 个块，适用于小规模演示；专家按依赖串行，恢复范围是已提交待答计划，不支持进程中断后的步骤级恢复。重规划有次数、上下文和全轮预算限制；不足时返回部分完成。最新[规划与来源修复复测](docs/evals/harness-long-runs/20261027-source-recovery-deepseek-flash/analysis.md)：后端370项、确定性8/8，自动5/6、30请求，原工程门槛通过，恢复2/2、计划完成5/5（原分母排除L01）。L02不再经过多余诊断，恢复原写作计划成功；L01课程草稿两次findings条数超限，未备题且partial保留。新计划简化与未读来源修复分支实跑均未触发，不能据单次回归推定其真实因果效果。教学内容准确性、材料缺口和内部术语仍待审核；工程门槛通过不能证明真实学习效果。语义阈值未用实网语料校准；教学材料未入库时工具明确返回 `not_provided`。

## 学习体验

1. **选择知识点**：围绕词汇、语法、阅读、写作等英语知识点开始练习。
2. **完成练习**：获取服务端保存的选择题，提交选项，可选记录把握程度。
3. **获得反馈**：先获得判断反馈并重试，主动请求提示或查看答案与解析。
4. **继续追问**：导师结合当前知识点的持久化历史与公开题目回答问题，支持跨会话接续。
5. **接受渐进提示**：主动求助时，依次获得思路检查、学科判断框架和选项验证提示。
6. **安排后续学习**：查看下一知识点推荐、复习快照、到期项目和学习分析。

## 教育设计

### 学习者建模

系统按“学习者 × 知识点”维护掌握概率、尝试次数、正确次数和连续正确次数，利用 BKT（贝叶斯知识追踪）的观测更新估计掌握状态。

实现包含初始掌握、猜测、失误和学习转移参数；为保持答错反馈的直观性，学习转移仅在答对后应用。掌握状态被用于薄弱点识别、导师上下文及课程推荐。

每道测验只有首次、未求助的作答更新掌握度与复习计划。重试、提示后作答和查看解析分别记录为辅助学习行为，便于区分独立表现与支架支持下的表现。把握程度可选，不额外增加问卷任务。

### 教学支架

测验错答后保留思考机会，Tutor 先提供形成性反馈；答案与解析由学习者主动查看。测验提示使用本地教学策略，分为三个层级：

| 层级 | 教学目的 |
|---|---|
| 元认知提示 | 引导学习者检查理解、回忆线索与思考方法 |
| 支架提示 | 提供词汇、语法、阅读或写作的判断框架 |
| 验证提示 | 引导代回选项、说明依据与排除干扰项 |

提示级别随同一测验的求助进程升级。自由答疑通过预算约束的上下文和原生工具查询历史；评估后的传统反馈路径保留近期回复相似度检查。

### 知识依赖与间隔复习

英语知识点通过 DAG 表达前置依赖。课程角色检查已掌握知识，筛选可学习的候选节点，再结合学习者画像生成推荐。

复习使用 SM-2 调整间隔与难度因子，同时根据掌握度、连续正确次数和距上次复习时间计算启发式记忆保持率，提供到期提醒和七天复习计划。

### 学习状态支持

系统结合近期正确率、连续答错、答题速度变化及会话时长估计学习状态，并提供鼓励、节奏调整或休息建议。状态估计用于选择支持策略。

## 四个协作角色

| Agent | 输入与职责 | 主要输出 |
|---|---|---|
| Assessment | 处理答题结果，更新掌握度，分析错误模式与薄弱点 | 掌握度更新、薄弱点事件、评估策略 |
| Tutor | 处理评估结果、问题与消息，组织上下文和分级提示 | 教学回复、提示级别与生成方式 |
| Curriculum | 响应掌握度和节奏变化，检查前置知识与复习状态 | 下一知识点、课程策略、复习安排 |
| Engagement | 记录交互行为，估计学习状态并选择干预 | 状态建议、鼓励与节奏调整事件 |

各角色运行在同一后端进程中，共享事件总线和学习者模型。Agent 自行订阅相关事件，编排器负责接收交互、发布初始事件、汇总结果并生成教学决策。

## 系统架构

```mermaid
flowchart TD
    UI["React 学习界面"] --> API["FastAPI：REST / WebSocket"]
    API --> HARNESS["LearningHarness：去重、超时与检查点"]
    HARNESS --> ORCH["AgentOrchestrator"]
    ORCH --> BUS["EventBus：进程内优先级队列"]
    BUS --> A["Assessment"]
    BUS --> T["Tutor"]
    BUS --> C["Curriculum"]
    BUS --> E["Engagement"]
    A --> BUS
    T --> BUS
    C --> BUS
    E --> BUS
    A --> MODEL["共享学习者模型"]
    T --> MODEL
    C --> MODEL
    T --> RUNTIME["TutorRuntime：ContextBuilder、工具循环与 hooks"]
    RUNTIME --> LLM["LLMService：文本 / 原生工具协议"]
    RUNTIME --> HISTORY["LearningHistory：教学消息与评估证据"]
    A --> LLM
    C --> LLM
    E --> LLM
    ORCH --> LLM
    BUS --> DB["PostgreSQL：事件日志"]
    HARNESS --> STATE["SQLite：执行记录、教学证据、测验与学习检查点"]
    HISTORY --> STATE
    ORCH --> RESULT["教学反馈、策略、推荐与复习快照"]
    RESULT --> API
```

一次答题的主要事件关系：

```text
student.submission
├── Assessment：更新学习者模型
│   ├── assessment.mastery_updated → Curriculum：更新复习与课程建议
│   ├── assessment.weakness_detected → Curriculum：分析补救路径
│   └── assessment.complete
│       ├── Tutor：生成教学反馈
│       └── Engagement：估计学习状态与支持需求
└── Engagement：记录答题行为

编排器汇总本次事件 → 教学决策 + 导师回复 + 推荐 + 复习快照
```

### 事件与上下文

- 子事件进入当前交互队列，当前处理器释放锁后再分发，按优先级及入队顺序执行。
- 每次交互使用 `correlation_id` 关联事件链；经过 Harness 时与 `run_id` 一致，`attempt_id` 区分重试，`parent_event_id` 记录事件因果关系。
- 事件历史保存在内存中，并可写入 PostgreSQL。
- Tutor 保留近期对话缓存；REST 答疑从持久化主题线程读取公开消息与历史评估证据，按上下文预算选择来源。
- 学习者模型、复习项目、导师对话和参与度状态从 Harness 检查点恢复。

### Harness 执行边界

REST 与 WebSocket 交互统一经过 `LearningHarness`，按请求 ID 和内容指纹去重。已完成请求返回已保存结果；同一 ID 换内容返回 `409`。客户端在网络失败时复用同一 ID 重试。

事件链有处理器超时、总执行超时和步数预算；处理器失败会中止执行并回滚本地学习状态。SQLite 事务一起提交学习检查点、测验状态、公开教学消息、学习证据和执行结果，避免请求重放重复判分。中断的执行在下次启动标记失败，可重新执行。`/api/runs/{learner_id}/{request_id}` 提供执行状态和结果，`/trace` 子路径提供各次执行尝试及步骤。

REST `/question` 与 `/message` 通过 `converse` 接入长期证据和 TutorRuntime。执行状态为 `completed` 时，对话仍可处于 `awaiting_student`；下一条同线程消息接续待回答问题。原生工具循环默认最多请求模型 3 次、调用工具 4 次，拒绝调用同样消耗工具预算；重复工具调用 ID、输出截断及预算耗尽会中止本轮。未配置远程模型或关闭工具模式时使用文本路径，执行记录明确区分生成方式。

当前采用单个后端进程串行执行交互，并以文件锁阻止多个 worker 共用存储。SQLite 为主链路学习状态与执行结果的权威存储；PostgreSQL 事件日志作为可选诊断记录，失败事件也可能出现在日志中。Docker 使用独立持久卷保存检查点。模型调用等外部副作用不承诺恰好一次。

### 队列与存储

事件队列使用 Python 标准库 `heapq`，保存在当前交互的内存中，不依赖数据库或外部消息服务。Agent 发布后续事件时只入队，当前处理器退出并释放锁后再执行后续事件。默认每次事件链最多入队 64 个事件，普通处理器超时为 15 秒，REST 答疑的 Tutor 处理器超时为 40 秒，整次业务执行超时为 45 秒。Tutor 模型调用共用本轮剩余 deadline；上下文预算采用 UTF-8 字节估计，模型实际 usage 单独记录。等待前一个请求释放执行锁的时间不计入业务执行超时。

SQLite 无需安装数据库服务或手动建表。`LearningHarness` 启动时在 `HARNESS_STORE_PATH` 指定的文件中自动创建以下表：

| 表 | 用途 | 关键字段 |
|---|---|---|
| `runs` | 请求去重、状态查询和结果重放 | `learner`、`request`、`fingerprint`、`status`、`result`、`error`、`updated` |
| `checkpoints` | 保存并恢复学习状态与 Agent 上下文 | `learner`、`state`（JSON） |
| `quizzes` | 服务端保存题目、答案、提示与作答进度 | `id`、`learner`、`body`（JSON） |
| `learning_sessions` | 学习会话及归属 | `id`、`learner`、`created` |
| `learning_threads` | 跨会话主题线程 | `id`、`learner`、`knowledge` |
| `conversation_messages` | 公开教学消息 | `id`、`learner`、`session`、`thread`、`run`、`role`、`content` |
| `learning_evidence` | 评估与受助证据 | `id`、`learner`、`thread`、`run`、`quiz`、`kind`、`body` |
| `run_attempts` | 各次执行与重试结果 | `id`、`learner`、`request`、`run`、`status`、`reason` |
| `run_steps` | 执行步骤及来源关联 | `attempt`、`seq`、`body` |
| `pending_questions` | 导师追问及后续接续 | `id`、`learner`、`thread`、`run`、`question`、`answered_by` |

不设置路径时，默认文件位于仓库根目录的 `data/harness.sqlite3`；显式配置的相对路径从后端进程启动目录解析。Docker 使用 `/app/data/harness.sqlite3` 并挂载 `harnessdata` 持久卷。原有 PostgreSQL 表结构保持不变。

进程重启后从最后一次已提交检查点恢复学习状态，未完成的内存事件队列不会续跑。上次中断的请求标记为失败，客户端以相同请求 ID 和内容重试时，重新执行整次交互；已经完成的请求直接返回保存结果。

长期教学证据从升级后的交互开始积累，旧检查点中的有限历史不会自动回填新消息表。细粒度步骤在成功或正常异常时提交；进程硬退出前未提交的步骤可能丢失。来源列表表示提供给上下文或工具读取的证据，不代表已验证模型逐句引用。

这是本地教学演示应用，学习者 ID 由客户端指定；独立作答、信心与耗时属于行为证据，不能直接视为真实能力或经过验证的情绪测量。

### 教学决策

默认使用本地策略汇总评估、课程、参与度与导师输出，选择答疑、补救、复习、推进、鼓励或继续练习等建议。

设置 `ENABLE_AGENT_LLM_DECISIONS=true` 后，评估策略、课程策略、参与度判断和最终教学决策可使用 LLM 生成结构化建议；无有效输出时采用本地策略。下一知识点推荐还会检查模型返回的知识点是否属于候选集合。

## 模型集成

主运行链路使用 `python/core/llm_service.py`，支持 Anthropic、OpenAI、MiniMax 和 DeepSeek。

| 优先级 | Provider | API Key | 模型配置 |
|---|---|---|---|
| 1 | Anthropic | `ANTHROPIC_API_KEY` | `MODEL_ID` |
| 2 | OpenAI | `OPENAI_API_KEY` | `OPENAI_MODEL` |
| 3 | MiniMax | `MINIMAX_API_KEY` | `MINIMAX_MODEL` |
| 4 | DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` |

`LLM_PROVIDER=auto`（默认）按上述优先级选择已配置的 Key。也可显式指定 `deepseek` 等 Provider；缺少对应 Key 会报配置错误，不会改用其他 Key。`LLM_PROVIDER=template` 强制使用本地模式。LLM 用于答疑、错题解释、候选知识点推荐，以及可选的教学策略生成；当前测验的分级提示采用本地策略。

DeepSeek 本地和 Docker 接入均可在根目录 `.env` 中填写：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=high
```

当前推荐模型名为 `deepseek-flash`，使用 OpenAI 兼容 SDK。项目显式设置 `DEEPSEEK_THINKING=disabled` 建立非思考评测基线；改为 `enabled` 开启思考，此时 `DEEPSEEK_REASONING_EFFORT` 可选 `high`、`max`，不传不生效的 temperature。

思考模式的工具循环会完整回传当前请求中的 `reasoning_content`，只保留在内存消息中，不写入学生回复、历史或公开 Trace。下一次学生请求从公开教学证据重新构建模型上下文，不重放旧工具协议。思考内容计入上下文预算；输出截断仍按执行耗尽处理。DeepSeek 的 SDK 自动重试已关闭，便于控制单轮请求次数。配置指纹记录思考开关与生效的 effort，便于比较实验。官方说明：[模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode)。

通过 `python python/test_llm_config.py` 检查本地配置，不发送请求；显式添加 `--live` 才会发送标准 API 连通性请求（可能计费）。该检查使用主链路原生协议，完整正文或合法工具调用均视为连通成功；截断、无正文且无有效工具调用的响应以及 API 错误均返回失败。工具调用只验证响应协议，不执行完整教学循环。

`ENABLE_TUTOR_TOOLS=true` 时，REST 答疑使用原生工具协议，注册历史检索、来源读取、知识关系查询及 `ask_student`；绑定有效练习题时提供公开题目查询工具。模型工具参数不包含学习者 ID，服务端校验角色允许的工具、资源归属与严格参数结构。`advance` 模式禁止本题答疑和提示，主动查看答案会结束测验。

出题优先使用对应知识点的本地题库；未命中题库时尝试 LLM 生成。服务端校验题目结构、选项唯一性与答案索引，再保存并只向客户端返回题干、选项和测验 ID。暂无有效题目时给出可重试提示。判分依据保存的答案，客户端不能传入标准答案。

## 技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Uvicorn、asyncio |
| 模型调用 | Anthropic SDK、OpenAI SDK |
| 数据与配置 | SQLite、SQLAlchemy 异步 ORM、asyncpg、PostgreSQL、Pydantic |
| 前端 | React 18、TypeScript、Ant Design、Vite |
| 通信与部署 | REST、WebSocket、Docker Compose、Nginx |
| 测试 | pytest、pytest-asyncio |

## 快速开始：Docker

需要 Git、Docker 与 Docker Compose。

```bash
git clone https://github.com/codedog678/eduagent.git
cd eduagent
cp .env.example .env
docker compose up --build -d
```

Compose 已转发 `LLM_PROVIDER` 以及 Anthropic、DeepSeek 的配置。使用 Anthropic 时，可在根目录 `.env` 中填写：

```dotenv
ANTHROPIC_API_KEY=your-api-key
LLM_PROVIDER=anthropic
ANTHROPIC_BASE_URL=https://api.anthropic.com
MODEL_ID=your-model-id
```

默认 `LLM_PROVIDER=auto` 且不填写 Key 时使用本地模式。使用 OpenAI 或 MiniMax 的容器部署时，将对应变量加入 `python-api.environment`。

容器使用代码中的默认 Tutor 配置。若需通过根目录 `.env` 调整 `ENABLE_TUTOR_TOOLS` 或 `TUTOR_*` 参数，也需将对应变量加入 `python-api.environment`。

| 服务 | 地址 |
|---|---|
| 学习界面 | http://localhost:3000 |
| API 文档 | http://localhost:8888/docs |
| 健康检查 | http://localhost:8888/api/health |

可通过界面的初始化按钮，或以下请求创建演示数据：

```bash
curl -X POST 'http://localhost:8888/api/demo/init?learner_id=student_001'
```

## 本地开发

后端使用 Python 3.11+，与 Docker 和 `pyproject.toml` 保持一致。

先在仓库根目录启动数据库：

```bash
docker compose up -d postgres
cp .env.example .env
```

根目录 `.env` 中的本地数据库连接配置：

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent
ENABLE_DB_LOGGING=true
ENABLE_AGENT_LLM_DECISIONS=false
LLM_TIMEOUT_SECONDS=12
HARNESS_STORE_PATH=data/harness.sqlite3
HARNESS_TIMEOUT_SECONDS=45
HARNESS_MAX_STEPS=64
QUIZ_TTL_SECONDS=86400
ENABLE_TUTOR_TOOLS=true
TUTOR_MAX_MODEL_CALLS=3
TUTOR_MAX_TOOL_CALLS=4
TUTOR_CONTEXT_BUDGET_TOKENS=6000
TUTOR_MAX_OUTPUT_TOKENS=800
TUTOR_HANDLER_TIMEOUT_SECONDS=40
```

在后端终端执行：

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8888
```

当前 Harness 使用 Unix 文件锁，后端在 macOS 或 Linux 环境运行；Windows 可通过 WSL 或 Docker 启动。应用启动时按版本迁移 SQLite 执行表，并尝试初始化 PostgreSQL 数据表。

在另一个终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

Vite 在 `3000` 端口提供页面，并将 `/api` 与 `/ws` 代理到后端 `8888` 端口。

## API

以下路径由当前应用入口挂载，完整参数见 `/docs`。

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/api/health` | 服务与模型配置状态 |
| POST | `/api/demo/init` | 初始化指定学习者的演示数据 |
| POST | `/api/submit` | 记录自我报告，不更新测验掌握度 |
| POST | `/api/question` | 围绕知识点提问，支持会话、主题线程与测验绑定 |
| POST | `/api/message` | 发送学习消息或接续导师追问 |
| POST | `/api/quiz/generate` | 以学习者 ID、请求 ID 获取测验；推进模式校验前置知识 |
| POST | `/api/quiz/answer` | 以测验 ID、选项索引判分并触发教学流程 |
| POST | `/api/quiz/hint` | 主动获取提示 |
| POST | `/api/quiz/reveal` | 查看答案与解析并结束本题 |
| GET | `/api/runs/{learner_id}/{request_id}` | 查询执行状态与保存结果 |
| GET | `/api/runs/{learner_id}/{request_id}/trace` | 查询各次执行尝试、终止原因与步骤 |
| GET | `/api/history/{learner_id}` | 分页读取公开教学对话，支持知识点和线程过滤 |
| GET | `/api/history/{learner_id}/source` | 按 `source_ref` 读取公开消息或评估证据 |
| GET | `/api/progress/{learner_id}` | 学习进度与薄弱点 |
| GET | `/api/knowledge-graph` | 知识节点与学习顺序 |
| GET | `/api/review-schedule/{learner_id}` | 复习计划与保持率估计 |
| GET | `/api/analytics/overview` | 整体答题统计 |
| GET | `/api/analytics/{learner_id}` | 学习者分析 |
| GET | `/api/statistics/{learner_id}` | 答题次数、正确率与耗时 |

提问示例：

```bash
curl -X POST http://localhost:8888/api/question \
  -H 'Content-Type: application/json' \
  -d '{
    "learner_id": "student_001",
    "knowledge_id": "grammar_tenses",
    "request_id": "question-001",
    "session_id": "session-001",
    "question": "一般过去时和现在完成时有什么区别？"
  }'
```

交互响应包含 `correlation_id`、`teaching_response`、`teaching_decision`、`agent_insights`、`next_topic_recommendation`、`review_snapshot` 和 `interaction_events` 等字段；具体内容随交互类型变化。

REST 答疑可传入 `thread_id` 延续指定线程；不传时默认接续该学习者在当前知识点的线程。前端开始新会话会更换 `session_id`，保留主题线程。请求绑定当前练习题时传入 `quiz_id`；旧客户端遗漏此字段时，服务端关联最近有效的同知识点测验并记录受助。

响应中的 `execution` 包含请求 ID、run/attempt ID、会话及线程 ID、执行状态、对话状态、待回答问题及来源列表。测验作答还包含 `learning_evidence`（独立性、尝试次数、提示与对话受助、把握程度）。旧 `/api/review/complete` 返回 `410`，复习通过测验统一更新。分析中的题数与正确率对应独立作答，耗时与辅助行为展示最近 200 次作答。

### WebSocket

连接 `ws://localhost:8888/ws/{learner_id}`，发送顶层 JSON 字段：

```json
{
  "action": "question",
  "knowledge_id": "grammar_tenses",
  "question": "现在完成时什么时候使用？"
}
```

支持 `submit`、`question` 和 `message`。服务端完成本次处理后，逐条发送事件，消息包含 `event_type`、`source`、`data`、`timestamp` 和 `correlation_id`。

WebSocket 保留基础交互及 Harness 去重、回滚能力；跨会话证据、当前测验受助绑定与原生工具循环使用上述 REST 接口。

## 代码导航

| 路径 | 职责 |
|---|---|
| `python/api/main.py` | 应用入口与生命周期 |
| `python/api/routes.py` | 当前 REST 接口 |
| `python/api/orchestrator.py` | 组装角色、交互处理与决策汇总 |
| `python/api/websocket.py` | WebSocket 连接与交互 |
| `python/agents/` | 四个角色及事件处理基类 |
| `python/core/event_bus.py` | 事件分发、历史与日志 |
| `python/core/harness.py` | 执行预算、请求去重、原子检查点与服务端测验 |
| `python/core/harness_migrations.py` | Harness SQLite 顺序迁移与版本校验 |
| `python/core/versions.py` | 应用、trace、eval schema 版本与配置指纹 |
| `python/core/run_context.py` | 请求级上下文、执行标识、截止时间与步骤 |
| `python/core/learning_history.py` | 会话、教学证据、检索、来源读取与执行轨迹 |
| `python/core/tutor_runtime.py` | ContextBuilder 和有界原生工具循环 |
| `python/core/tutor_hooks.py` | 模型预算、工具门禁与结果记录 |
| `python/core/learner_model.py` | 掌握度更新与学习状态 |
| `python/core/knowledge_graph.py` | 知识依赖与路径算法 |
| `python/core/spaced_repetition.py` | SM-2 复习算法 |
| `python/core/llm_service.py` | 主链路模型调用、提示与降级 |
| `python/core/memory_manager.py` | 学习者模型缓存与持久化 |
| `python/models/` | 数据表与异步数据库会话 |
| `python/config/settings.py` | 环境变量和模型配置 |
| `python/evals/` | 内置回归集、确定性评分、MRBench 适配与报告 CLI |
| `python/tests/` | 算法、Agent 协作及 API 测试 |
| `frontend/src/App.tsx` | 学习交互主界面 |
| `frontend/src/components/` | 练习、反馈、复习与分析组件 |
| `frontend/src/components/TeachingHistory.tsx` | 跨会话对话、待回答提醒与本轮互动记录 |

## 测试

在已安装依赖的后端环境中运行：

```bash
cd python

# 完整后端测试集
python -m pytest tests -q

# 算法、事件总线与 Agent 协作
python -m pytest \
  tests/test_agents.py \
  tests/test_agent_integration.py \
  tests/v2/test_event_bus.py \
  tests/v2/test_knowledge_graph.py \
  tests/test_learning_harness.py -q

# API 测试
python -m pytest tests/test_api.py -v

# 跨会话、工具协议、受助与事务边界
python -m pytest tests/test_tutor_harness.py -q
```

后端测试覆盖主链路、原生工具协议和评测执行器。主链路 `LLMService.generate` 在 pytest 环境下跳过远程调用；协议测试在确定注入 MockTransport 后显式允许 SDK 序列化。原生工具测试使用 scripted 模型和 mock SDK，验证 OpenAI 兼容与 Anthropic 消息协议、DeepSeek 思考开关及私有思考回传、权限、预算、追问接续和提交失败回滚，不调用真实模型。

配置了远程模型的 `.env` 时，离线运行测试可显式选择模板模式：

```bash
LLM_PROVIDER=template python -m pytest -q
```

前端验证：

```bash
cd frontend
npm run build
```

自动测试验证执行与状态边界；真实模型表现通过下述独立评测入口记录，学生学习效果需要另外开展实验。

## 离线评测

内置 20 条项目自有回归样例，覆盖教学回复规则、跨会话、权限、幂等、回滚和 trace。运行过程强制使用本地路径，不消耗模型额度：

```bash
cd python
eduagent-eval validate
eduagent-eval run --suite builtin
```

MRBench V1 使用固定 commit 和归档摘要按需下载到用户缓存，不进入仓库：

```bash
eduagent-eval fetch mrbench
```

转换结果保留 CC BY-SA 4.0、来源 ID、split 和 revision。确定性规则只用于回归与标签校准，不等同于真实教学效果评价。

## 真实模型评测

首批 12 条项目自建场景采用固定学生脚本：8 条检验 Agent 接续、历史检索、权限与学习证据，4 条辅助检查教学回复。每条使用全新学习者、独立临时 SQLite 和真实 `LearningHarness.converse/answer`，不连接业务 PostgreSQL。

已执行的基线、提示 v2/v3 复测、逐条公开 Trace 和常见 Agent 指标见[评测文档与数据索引](docs/evals/README.md)。这些记录保留失败与待审阅项；各版本成绩分别报告。

多 Agent 长任务第二轮工程优化采用精简模型草稿、有限历史发现、事实快照和必要/可选动作区分，未运行进化。[本轮分析与三轮同评分对照](docs/evals/harness-long-runs/20261027-optimized-deepseek-flash/analysis.md)记录实际效果；[历史修改回顾](docs/engineering/historical-change-log.md)补记此前原型、前端/API、形成性评价、模型、评测、记忆和协作修改，[工程过程记录](docs/engineering/problem-solution-log.md)持续按“问题→原因→解决→效果”保存修改、失败和下一轮待办。

已有任务的[成功评分与工具语义评分](docs/evals/20261025/tutor-final-scoring-20261025.md)已完成单次 AI 审阅，包含逐项原文证据、工具选择/参数及漏调标签、分组成功率和边界裁定。原始报告不改写，没有新增模型请求；AI 标签不代表独立人工确认。

Agent 主评测数据已[扩至 50 条](docs/evals/tutor-agent-50-review.md)：保留原 8 条、补充 42 条，覆盖接续、历史依据、完整检索、工具决策、权限和学习证据。新增数据在执行前定义语义与工具决策要求；[整套真实运行](docs/evals/20261025/agent50-live/run-state.json)已完成，82次请求，自动契约40/50；最终任务语义与工具语义审阅按用户要求暂停，不能将自动契约视为最终成功率。`eduagent-eval validate-live --dataset evals/datasets/tutor_agent50_review.jsonl` 不调用供应商，真实运行可用重复的 `--case-id` 按[清单](docs/evals/tutor-agent-50-manifest.json)分批，保留原预算上限。

根目录 `.env` 配置 `LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-flash`、`DEEPSEEK_THINKING=disabled` 后运行：

```bash
cd python
eduagent-eval run-live \
  --dataset evals/datasets/tutor_live12_review.jsonl \
  --output eval-results/tutor-live12.json \
  --max-requests 42 --max-cny 3
```

该命令调用真实模型并消耗额度。每次答疑最多 3 次模型请求、4 次工具调用、800 输出 Token；整批最多 42 次请求和 3 元保守预算，不自动重跑。费用按官方 Flash 高峰价格预留，收到 usage 后记录缓存命中/未命中与闲时至高峰费用区间；请求用量未知时保留预留金额，金额不是供应商账单。

报告逐条保存学生输入、公开回复、实际工具批次、来源、前后知识状态、测验及学习证据、Trace、代码与数据摘要、延迟和用量。结果在每条执行后写入 JSON 和 Markdown；临时数据库自动清理。第 08 条先验证目标旧笔记不在初始上下文或搜索摘要中，第 10 条先验证外部学习者正文不可见。

Tutor 原生工具路径的通用答疑约束集中在 `python/core/tutor_policy.py`。未结束的练习使用 `hint_only`，可以讲所需语法类别和公开候选，但不直接给具体答案词形、词义或正确选项；结束练习后的公开讲解采用 `explanation`。缺失具体材料时必须用 `ask_student` 建立待答状态；补充信息已足够时先完成原请求，可选背景不阻断回答。学生明确要求问题引导时仍可提问。提示版本写入上下文 Trace 与配置指纹，便于比较修改前后的行为。

这组任务评测观察 Tutor Agent 如何根据输入和历史选择工具、接续问题，并与 Harness 一起提交学习证据。其他领域 Agent 在该配置下使用本地策略协同；本批不是完整的多 Agent 自主协作或通用 Agent 基准评测。

自动评分只判定可核对的契约和指定原文。教学事实、针对性及是否直接代答进入 `semantic_review`，质量分按准确性、针对性、可操作性各 0–2 分单独审阅。语义未审阅时标记 `review_pending`，不会将自动检查成功写成整体通过；如添加 AI 审阅，应独立标明审阅者，不能冒充人工评分。固定学生脚本的正确选择不代表真实学习收益或迁移效果。

## License

[MIT](LICENSE)
