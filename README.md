# EduAgent

**融合学习者建模、教学支架与间隔复习的多 Agent 英语学习应用。**

EduAgent 将答题评估、个性化辅导、课程推荐与学习状态支持组织为四个协作角色。系统使用事件驱动方式连接各角色，将学习者表现、知识点依赖和对话上下文用于教学反馈，并通过 React 界面呈现练习、答疑、复习及学习分析。

项目结合教育技术中的个性化学习与教学支架设计，以及 Python 异步服务、LLM 集成和事件追踪等工程实践。

## 学习体验

1. **选择知识点**：围绕词汇、语法、阅读、写作等英语知识点开始练习。
2. **完成练习**：获取选择题并提交答案，记录作答表现与耗时。
3. **获得反馈**：查看评估结果、导师解释和当前教学建议。
4. **继续追问**：导师结合当前知识点的对话历史及最近题目回答问题。
5. **接受渐进提示**：重复答错时，逐步获得元认知、支架和针对性提示。
6. **安排后续学习**：查看下一知识点推荐、复习快照、到期项目和学习分析。

## 教育设计

### 学习者建模

系统按“学习者 × 知识点”维护掌握概率、尝试次数、正确次数和连续正确次数，利用 BKT（贝叶斯知识追踪）的观测更新估计掌握状态。

实现包含初始掌握、猜测、失误和学习转移参数；为保持答错反馈的直观性，学习转移仅在答对后应用。掌握状态被用于薄弱点识别、导师上下文及课程推荐。

### 教学支架

Tutor 根据当前题目、学生答案、掌握水平和近期对话生成反馈。提示分为三个层级：

| 层级 | 教学目的 |
|---|---|
| 元认知提示 | 引导学习者检查理解、回忆线索与思考方法 |
| 支架提示 | 提供关键规则、组织框架或分析方向 |
| 针对性提示 | 对当前困难提供更具体的指导 |

提示级别随同一题目的求助进程升级。系统还检查近期回复的相似度，并在回复过于重复时再次生成。

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

- `asyncio.gather` 并发分发给事件订阅者，各处理器分别捕获异常。
- 每次交互使用 `correlation_id` 关联事件链，支持按学习者、类型和交互查询。
- 事件历史保存在内存中，并可写入 PostgreSQL。
- Tutor 分别管理会话历史、知识点历史和最近题目上下文。
- 学习者模型采用缓存优先、数据库懒加载，并在答题后保存状态。

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

出题优先使用对应知识点的本地题库；未命中题库时尝试 LLM 生成。选择题依据标准答案判定；无标准答案的作答支持 LLM 评估。未配置模型或模型调用失败时，各业务方法采用相应的本地反馈与兜底内容。

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
| POST | `/api/submit` | 提交已判定的答题结果 |
| POST | `/api/question` | 围绕知识点提问 |
| POST | `/api/message` | 发送学习消息 |
| POST | `/api/quiz/generate` | 获取测验题 |
| POST | `/api/quiz/answer` | 判定作答并触发教学流程 |
| GET | `/api/progress/{learner_id}` | 学习进度与薄弱点 |
| GET | `/api/knowledge-graph` | 知识节点与学习顺序 |
| GET | `/api/review-schedule/{learner_id}` | 复习计划与保持率估计 |
| POST | `/api/review/complete` | 更新复习结果 |
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
  tests/v2/test_knowledge_graph.py -q

# API 测试
python -m pytest tests/test_api.py -v
```

主链路 `LLMService.generate` 在 pytest 环境下跳过远程调用，使用业务降级逻辑验证流程。

## License

[MIT](LICENSE)
