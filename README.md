# EduAgent

**融合学习者建模、教学支架与间隔复习的多 Agent 英语学习应用。**

EduAgent 将答题评估、个性化辅导、课程推荐与学习状态支持组织为四个协作角色。系统使用事件驱动方式连接各角色，将学习者表现、知识点依赖和对话上下文用于教学反馈，并通过 React 界面呈现练习、答疑、复习及学习分析。

项目结合教育技术中的个性化学习与教学支架设计，以及 Python 异步服务、LLM 集成和事件追踪等工程实践。

## 学习体验

1. **选择知识点**：围绕词汇、语法、阅读、写作等英语知识点开始练习。
2. **完成练习**：获取服务端保存的选择题，提交选项，可选记录把握程度。
3. **获得反馈**：先获得判断反馈并重试，主动请求提示或查看答案与解析。
4. **继续追问**：导师结合当前知识点的对话历史及最近题目回答问题。
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

提示级别随同一测验的求助进程升级。自由答疑结合知识点历史生成回复，并检查近期回复的相似度。

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
    API --> ORCH["AgentOrchestrator"]
    ORCH --> BUS["EventBus：异步发布与订阅"]
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
    T --> LLM["LLMService"]
    A --> LLM
    C --> LLM
    E --> LLM
    ORCH --> LLM
    BUS --> DB["PostgreSQL：事件日志"]
    ORCH --> STATE["学习状态、答题记录与复习项目"]
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
- 每次交互使用 `correlation_id` 关联事件链，支持按学习者、类型和交互查询。
- 事件历史保存在内存中，并可写入 PostgreSQL。
- Tutor 分别管理会话历史、知识点历史和最近题目上下文。
- 学习者模型、复习项目、导师对话和参与度状态从 Harness 检查点恢复。

### Harness 执行边界

REST 与 WebSocket 交互统一经过 `LearningHarness`，按请求 ID 和内容指纹去重。已完成请求返回已保存结果；同一 ID 换内容返回 `409`。客户端在网络失败时复用同一 ID 重试。

事件链有处理器超时、总执行超时和步数预算；处理器失败会中止执行并回滚本地学习状态。SQLite 事务一起提交学习检查点、测验状态和结果，避免请求重放重复判分。中断的执行在下次启动标记失败，可重新执行。`/api/runs/{learner_id}/{request_id}` 提供执行状态和结果，失败记录包含诊断事件。

当前采用单个后端进程串行执行交互，并以文件锁阻止多个 worker 共用存储。SQLite 为主链路学习状态与执行结果的权威存储；PostgreSQL 事件日志作为可选诊断记录，失败事件也可能出现在日志中。Docker 使用独立持久卷保存检查点。模型调用等外部副作用不承诺恰好一次。

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

Provider 按已配置的 Key 选择。LLM 用于答疑、错题解释、分级提示、候选知识点推荐，以及可选的教学策略生成。

出题优先使用对应知识点的本地题库；未命中题库时尝试 LLM 生成。服务端校验题目结构、选项唯一性与答案索引，再保存并只向客户端返回题干、选项和测验 ID。暂无有效题目时给出可重试提示。判分依据保存的答案，客户端不能传入标准答案。

## 技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Uvicorn、asyncio |
| 模型调用 | Anthropic SDK、OpenAI SDK |
| 数据与配置 | SQLAlchemy 异步 ORM、asyncpg、PostgreSQL、Pydantic |
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

默认 Compose 配置通过 `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL` 和 `MODEL_ID` 向后端传入模型配置。可在根目录 `.env` 中填写：

```dotenv
ANTHROPIC_API_KEY=your-api-key
ANTHROPIC_BASE_URL=https://api.anthropic.com
MODEL_ID=your-model-id
```

不填写 Key 时使用本地模式。使用其他 Provider 的容器部署时，将对应变量加入 `python-api.environment`。

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

后端可使用 Python 3.13+，与 `pyproject.toml` 的版本声明一致；依赖安装使用 `requirements.txt`。

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
```

在后端终端执行：

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --host 0.0.0.0 --port 8888
```

Windows 使用 `.venv\Scripts\activate` 激活虚拟环境。应用启动时初始化数据库表。

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
| POST | `/api/question` | 围绕知识点提问 |
| POST | `/api/message` | 发送学习消息 |
| POST | `/api/quiz/generate` | 以学习者 ID、请求 ID 获取测验；推进模式校验前置知识 |
| POST | `/api/quiz/answer` | 以测验 ID、选项索引判分并触发教学流程 |
| POST | `/api/quiz/hint` | 主动获取提示 |
| POST | `/api/quiz/reveal` | 查看答案与解析并结束本题 |
| GET | `/api/runs/{learner_id}/{request_id}` | 查询执行状态与保存结果 |
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
    "question": "一般过去时和现在完成时有什么区别？"
  }'
```

交互响应包含 `correlation_id`、`teaching_response`、`teaching_decision`、`agent_insights`、`next_topic_recommendation`、`review_snapshot` 和 `interaction_events` 等字段；具体内容随交互类型变化。

测验作答还包含 `learning_evidence`（独立性、尝试次数、提示使用、把握程度）和 `execution`（请求 ID、执行状态）。旧 `/api/review/complete` 返回 `410`，复习通过测验统一更新。分析中的题数与正确率对应独立作答，耗时与辅助行为展示最近 200 次作答。

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
| `python/core/learner_model.py` | 掌握度更新与学习状态 |
| `python/core/knowledge_graph.py` | 知识依赖与路径算法 |
| `python/core/spaced_repetition.py` | SM-2 复习算法 |
| `python/core/llm_service.py` | 主链路模型调用、提示与降级 |
| `python/core/memory_manager.py` | 学习者模型缓存与持久化 |
| `python/models/` | 数据表与异步数据库会话 |
| `python/config/settings.py` | 环境变量和模型配置 |
| `python/tests/` | 算法、Agent 协作及 API 测试 |
| `frontend/src/App.tsx` | 学习交互主界面 |
| `frontend/src/components/` | 练习、反馈、复习与分析组件 |

## 测试

在已安装依赖的后端环境中运行：

```bash
cd python

# 算法、事件总线与 Agent 协作
python -m pytest \
  tests/test_agents.py \
  tests/test_agent_integration.py \
  tests/v2/test_event_bus.py \
  tests/v2/test_knowledge_graph.py \
  tests/test_learning_harness.py -q

# API 测试
python -m pytest tests/test_api.py -v
```

主链路 `LLMService.generate` 在 pytest 环境下跳过远程调用，使用业务降级逻辑验证流程。

## License

[MIT](LICENSE)
