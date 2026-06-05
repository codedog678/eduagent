# EduAgent — 多Agent智能教育与个性化学习系统

<p align="center">
  <strong>基于事件驱动Mesh架构的AI英语学习系统</strong><br>
  4个专业AI Agent协作，提供个性化学习体验
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white" alt="React 18">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
</p>

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend                         │
│              (TypeScript + Vite, Port 3000)                 │
└──────────────┬─────────────────────────┬────────────────────┘
               │ REST API                │ WebSocket
               ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│                   (Python 3.13+, Port 8888)                 │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   REST API   │  │  Orchestrator │  │    WebSocket     │   │
│  │  /api/...    │  │   协调器       │  │  /ws/{learner}  │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                │                    │              │
│         ▼                ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              EventBus (异步发布/订阅)                   │    │
│  └────┬──────────┬──────────┬──────────┬───────────────┘    │
│       │          │          │          │                     │
│       ▼          ▼          ▼          ▼                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐    │
│  │Assessment│ │  Tutor  │ │Curriculum│ │  Engagement   │    │
│  │ Agent    │ │  Agent  │ │  Agent   │ │    Agent      │    │
│  │ BKT评估  │ │ 苏格拉底 │ │ 学习路径  │ │  情感识别      │    │
│  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬────────┘    │
│       │           │           │              │              │
│       ▼           ▼           ▼              ▼              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 LLM Service                         │    │
│  │   Anthropic / OpenAI / MiniMax / DeepSeek / 模板回退  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               PostgreSQL 16 (Async)                  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 事件驱动 Mesh 架构

系统采用 **事件驱动的Mesh架构**，Agent之间通过 `EventBus` 进行异步通信，无中心协调器：

1. 用户提交答案 → REST API 接收请求
2. `EventBus` 发布 `AnswerSubmitted` 事件
3. 4个Agent各自订阅感兴趣的事件，并行处理
4. 各Agent发布结果事件（如 `MasteryUpdated`、`HintGenerated`）
5. 前端通过 WebSocket 实时接收所有事件流

每个交互都带有 `correlation_id`，可追踪完整事件链路。

---

## 四大AI Agent

### 1. AssessmentAgent — 知识掌握评估

基于 **BKT（贝叶斯知识追踪）** 算法，实时更新学习者的知识掌握概率：

- 每次答题后更新掌握度（P(L)），使用 Beta 分布拟合
- 分析错误模式：概念性错误 / 程序性错误 / 粗心错误
- 识别薄弱知识点，输出学习建议
- 支持连击追踪（streak tracking）

### 2. TutorAgent — 个性化辅导

苏格拉底式教学，提供渐进式提示：

- **第一级**：元认知提示 — 引导自主思考
- **第二级**：脚手架提示 — 提供解题框架
- **第三级**：定向提示 — 直接给出关键信息
- 管理话题级对话上下文，支持追问和答疑

### 3. CurriculumAgent — 学习路径规划

基于 **知识图谱（DAG）** 和 **SM-2间隔重复** 算法：

- 拓扑排序确定学习顺序（Kahn算法）
- SM-2 算法安排复习计划（含难度因子）
- 艾宾浩斯遗忘曲线预测记忆保持率
- 根据掌握度动态调整推荐内容

### 4. EngagementAgent — 参与度感知

检测学习者情绪状态并触发干预：

| 状态 | 干预策略 |
|------|---------|
| 专注 (focused) | 保持当前节奏，提供适当挑战 |
| 困惑 (struggling) | 降低难度，提供脚手架提示 |
| 沮丧 (frustrated) | 鼓励安慰，调整学习策略 |
| 无聊 (bored) | 增加挑战性，切换学习内容 |
| 疲劳 (fatigued) | 建议休息，安排轻松内容 |
| 空闲 (idle) | 主动引导，推送学习提醒 |

---

## 核心算法

### BKT（贝叶斯知识追踪）

```
参数: P(L0)=初始掌握率, P(T)=学习率, P(G)=猜测率, P(S)=失误率
更新: P(L|correct) = P(L)(1-P(S)) / P(L)(1-P(S)) + (1-P(L))P(G)
      P(L|wrong)   = P(L)P(S) / P(L)P(S) + (1-P/L)(1-P(G))
```

### SM-2 间隔重复

```
难度因子 EF' = EF + (0.1 - (1-q)(0.08 + (1-q)*0.02))
间隔天数 I(n) = I(n-1) * EF
其中 q = 答题质量 (0-5)
```

### 艾宾浩斯遗忘曲线

```
R = e^(-t/S)
R: 记忆保持率, t: 经过时间, S: 记忆强度
```

---

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.13+ | 主语言 |
| FastAPI | 异步 REST API + WebSocket |
| SQLAlchemy 2.0 | 异步 ORM（asyncpg 驱动） |
| PostgreSQL 16 | 主数据库 |
| Pydantic / pydantic-settings | 数据校验与配置管理 |
| Anthropic SDK / OpenAI SDK | LLM 集成 |
| Uvicorn | ASGI 服务器 |
| pytest + pytest-asyncio | 测试框架 |

### 前端

| 技术 | 用途 |
|------|------|
| React 18 | UI 框架 |
| TypeScript 5.5 | 类型安全 |
| Vite 5 | 构建工具与开发服务器 |
| WebSocket | 实时事件推送 |

### 基础设施

| 技术 | 用途 |
|------|------|
| Docker Compose | 多服务编排 |
| Nginx | 静态文件服务 + 反向代理 |

---

## 快速开始

### 前置要求

- Docker & Docker Compose
- Git

### 1. 克隆项目

```bash
git clone <repo-url>
cd eduagent
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少配置一项 LLM Provider 的 API Key：

```env
# 任选其一（优先级从高到低）
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
MINIMAX_API_KEY=xxxxx
DEEPSEEK_API_KEY=xxxxx

# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/eduagent
```

> 💡 不配置任何 API Key 也可以运行，系统会回退到本地模板模式。

### 3. 启动服务

```bash
docker compose up --build -d
```

启动后访问：

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| 后端 API | http://localhost:8888 |
| API 文档 | http://localhost:8888/docs |
| 健康检查 | http://localhost:8888/api/health |

### 4. 初始化演示数据

```bash
curl -X POST http://localhost:8888/api/demo/init
```

---

## 开发环境搭建

### 后端

```bash
cd python

# 创建虚拟环境
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 安装依赖
pip install -e ".[dev]"

# 启动数据库（需要本地 PostgreSQL 或使用 Docker）
docker compose up -d postgres

# 初始化数据库
python -m scripts.init_db

# 启动开发服务器
uvicorn api.main:app --reload --port 8888
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（自动代理到后端 8888 端口）
npm run dev
```

访问 http://localhost:5173

---

## API 参考

### REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查（含 LLM 状态） |
| `POST` | `/api/demo/init` | 初始化演示学习者数据 |
| `POST` | `/api/submit` | 提交答题结果 |
| `POST` | `/api/question` | 向导师提问 |
| `POST` | `/api/message` | 发送通用消息 |
| `GET` | `/api/progress/{learner_id}` | 获取学习者进度 |
| `GET` | `/api/knowledge-graph` | 获取完整知识图谱 |
| `GET` | `/api/analytics/overview` | 系统概览分析 |
| `GET` | `/api/analytics/{learner_id}` | 学习者个人分析 |
| `GET` | `/api/review-schedule/{learner_id}` | 复习计划与遗忘状态 |
| `POST` | `/api/review/complete` | 完成一次复习 |
| `POST` | `/api/quiz/generate` | 生成测验题目 |
| `POST` | `/api/quiz/answer` | 提交测验答案并获取评估 |

### WebSocket

连接：`ws://localhost:8888/ws/{learner_id}`

**发送消息（JSON）：**

```json
{
  "action": "submit",
  "data": {
    "question_id": "q1",
    "answer": "B",
    "is_correct": true
  }
}
```

支持的 action：`submit` | `question` | `message`

**接收事件流：** 每个事件为独立的 JSON 消息，包含 `type`、`data`、`timestamp` 字段。

---

## 数据库结构

系统使用 6 张核心表：

| 表名 | 说明 |
|------|------|
| `learners` | 学习者档案（ID、姓名、邮箱、元数据） |
| `knowledge_states` | 知识点掌握状态（掌握度、Alpha/Beta参数、尝试次数、连击） |
| `learning_records` | 答题历史（对错、用时、掌握度前后变化） |
| `review_items` | SM-2 复习计划（难度因子、间隔天数、下次复习时间） |
| `event_logs` | 事件溯源日志（事件类型、来源、数据、correlation_id） |
| `agent_states` | Agent 运行时状态持久化（JSON 格式） |

---

## 项目结构

```
eduagent/
├── docker-compose.yml          # Docker 多服务编排
├── .env.example                # 环境变量模板
├── LICENSE                     # MIT License
├── python/                     # 后端
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── api/                    # API 层
│   │   ├── main.py             # FastAPI 入口
│   │   ├── routes.py           # REST 路由
│   │   ├── orchestrator.py     # Agent 协调器
│   │   └── websocket.py        # WebSocket 通道
│   ├── agents/                 # AI Agent 层
│   │   ├── base.py             # Agent 抽象基类
│   │   ├── assessment_agent.py # BKT 评估 Agent
│   │   ├── tutor_agent.py      # 导师 Agent
│   │   ├── curriculum_agent.py # 课程规划 Agent
│   │   └── engagement_agent.py # 参与度 Agent
│   ├── core/                   # 核心算法
│   │   ├── event_bus.py        # 异步事件总线
│   │   ├── learner_model.py    # BKT 算法实现
│   │   ├── knowledge_graph.py  # 知识图谱（DAG）
│   │   ├── spaced_repetition.py # SM-2 间隔重复
│   │   ├── llm_service.py      # LLM 多Provider封装
│   │   └── memory_manager.py   # 学习者状态缓存
│   ├── llm/                    # LLM Provider 适配器
│   │   ├── anthropic_adapter.py
│   │   ├── openai_adapter.py
│   │   ├── minimax_adapter.py
│   │   ├── deepseek_adapter.py
│   │   └── template_adapter.py # 本地模板回退
│   ├── models/                 # 数据模型
│   │   ├── database.py         # SQLAlchemy ORM
│   │   └── session.py          # 异步会话管理
│   ├── schemas/                # Pydantic 模型
│   ├── services/               # 业务服务层
│   ├── interaction/            # 对话管理
│   ├── repositories/           # 数据访问层
│   ├── config/
│   │   └── settings.py         # 配置管理
│   └── tests/                  # 测试套件
│       ├── test_bkt.py         # BKT 算法测试
│       ├── test_api.py         # API 端点测试
│       └── test_agents.py      # Agent 集成测试
└── frontend/                   # 前端
    ├── Dockerfile
    ├── package.json
    ├── nginx.conf              # Nginx 反向代理配置
    └── src/
        ├── main.tsx
        ├── App.tsx             # 主应用
        ├── components/
        │   ├── AnalyticsDashboard.tsx
        │   └── ReviewReminder.tsx
        └── hooks/
            └── useWebSocket.ts # WebSocket 连接管理
```

---

## 运行测试

```bash
cd python

# 运行全部测试
python -m pytest tests/ -v

# 仅运行 BKT 算法测试
python -m pytest tests/test_bkt.py -v

# 仅运行 API 测试
python -m pytest tests/test_api.py -v
```

---

## LLM Provider 配置

系统支持 4 种 LLM Provider，按优先级自动选择：

| 优先级 | Provider | 环境变量 |
|--------|----------|---------|
| 1 | Anthropic | `ANTHROPIC_API_KEY` |
| 2 | OpenAI | `OPENAI_API_KEY` |
| 3 | MiniMax | `MINIMAX_API_KEY` |
| 4 | DeepSeek | `DEEPSEEK_API_KEY` |

**自动回退机制：** 未配置任何 API Key 时，系统使用 `TemplateAdapter` 提供本地模板化响应，无需网络连接即可完整运行。

在 `.env` 中可指定默认 Provider：

```env
LLM_PROVIDER=anthropic   # 或 openai / minimax / deepseek
LLM_MODEL=claude-sonnet-4-20250514
```

---

## License

[MIT License](LICENSE) © 2026
