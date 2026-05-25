# EduAgent - 多Agent智能教育系统

## 项目概述

这是一个基于多Agent架构的智能教育系统，采用Mesh + 事件驱动模式，通过4个专业Agent协作实现个性化学习体验。

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLAlchemy (async)
- **前端**: React 18 / TypeScript / Vite
- **数据库**: PostgreSQL 16 (asyncpg)
- **AI服务**: Anthropic Claude API (可选)
- **部署**: Docker / Docker Compose

## 架构设计

### 核心架构: Mesh + 事件驱动

所有Agent通过EventBus进行双向异步通信，没有中心调度者，每个Agent自主决定响应哪些事件。

```
                        ┌──────────────┐
                        │  React 前端   │
                        │  (WebSocket)  │
                        └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │ API Gateway  │
                        │  / EventBus  │
                        └──────┬───────┘
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
 ┌────▼──────┐          ┌─────▼──────┐          ┌──────▼──────┐
 │ Assessment│◄────────►│   Tutor    │◄────────►│    Hint     │
 │   Agent   │          │   Agent    │          │    Agent    │
 └────┬──────┘          └────────────┘          └─────────────┘
      │                       ▲
      │                       │
 ┌────▼──────┐          ┌─────┴──────┐
 │ Curriculum│◄────────►│ Engagement │
 │   Agent   │          │   Agent    │
 └───────────┘          └────────────┘
```

## Agent功能分布

### 1. Assessment Agent (评估Agent)
**文件**: `python/agents/assessment_agent.py`

**核心职责**:
- 接收学生答题结果，用BKT算法更新mastery
- 检测薄弱知识点，通知Curriculum Agent调整路径
- 定期生成学习报告

**订阅事件**:
- `STUDENT_SUBMISSION` - 学生提交答案
- `STUDENT_QUESTION` - 学生提问

**发布事件**:
- `MASTERY_UPDATED` - 掌握度更新
- `WEAKNESS_DETECTED` - 检测到薄弱点
- `ASSESSMENT_COMPLETE` - 评估完成

### 2. Tutor Agent (教学Agent)
**文件**: `python/agents/tutor_agent.py`

**核心职责**:
- 根据学生水平采用苏格拉底式提问教学
- 根据Assessment结果动态调整教学难度
- 当学生卡住时，内部分级提示（三级提示策略）

**订阅事件**:
- `ASSESSMENT_COMPLETE` - 评估完成
- `STUDENT_MESSAGE` - 学生消息
- `ENGAGEMENT_ALERT` - 参与度警报

**发布事件**:
- `TEACHING_RESPONSE` - 教学回复（含提示）

### 3. Curriculum Agent (课程Agent)
**文件**: `python/agents/curriculum_agent.py`

**核心职责**:
- 基于知识图谱拓扑排序规划学习路径
- 使用SM-2算法安排复习时间
- 检查前置知识是否达标再推进新内容
- 管理复习提醒和紧急度分类
- 响应节奏调整请求

**订阅事件**:
- `MASTERY_UPDATED` - 掌握度更新
- `WEAKNESS_DETECTED` - 检测到薄弱点
- `PACE_ADJUSTMENT` - 节奏调整

**发布事件**:
- `REVIEW_SCHEDULED` - 复习计划
- `NEXT_TOPIC` - 推荐新主题
- `REVIEW_REMINDER` - 复习提醒
- `ENCOURAGEMENT` - 鼓励（响应节奏调整）

### 4. Engagement Agent (互动Agent)
**文件**: `python/agents/engagement_agent.py`

**核心职责**:
- 监测学生学习行为指标（响应时间、错误率趋势、会话时长）
- 基于行为分析判断学习状态（专注/挫败/厌倦/疲劳）
- 适时发出干预事件：鼓励、建议休息、调整节奏

**订阅事件**:
- `STUDENT_SUBMISSION` - 学生提交答案
- `ASSESSMENT_COMPLETE` - 评估完成
- `STUDENT_MESSAGE` - 学生消息

**发布事件**:
- `ENGAGEMENT_ALERT` - 参与度警报
- `ENCOURAGEMENT` - 鼓励
- `PACE_ADJUSTMENT` - 节奏调整

## 事件流设计

### 核心事件流：学生答题

```
学生答题
  → STUDENT_SUBMISSION 事件
  → Assessment Agent 处理
      → MASTERY_UPDATED 事件
          → Curriculum Agent（更新SM-2复习计划 + 复习提醒）
      → ASSESSMENT_COMPLETE 事件
          → Tutor Agent（生成苏格拉底式回复）
          → Engagement Agent（分析学习状态）
  → Engagement Agent 并行处理
      → 如果检测到挫败 → ENGAGEMENT_ALERT 事件
          → Tutor Agent（调整教学策略）
          → Curriculum Agent（放慢节奏，延长复习间隔）
```

### 提示流：学生卡住

```
学生连续答错
  → Tutor Agent 检测到 attempts >= 2
  → 内部分级提示（三级提示策略）
  → TEACHING_RESPONSE 事件（teaching_style: "hint"）
```

## 核心模块

### EventBus (事件总线)
**文件**: `python/core/event_bus.py`

- 发布-订阅模式，支持异步事件分发
- 支持事件历史记录（Event Sourcing基础）
- 支持PostgreSQL事件日志持久化
- 使用asyncio.gather并发通知所有订阅者

### LearnerModel (学习者模型)
**文件**: `python/core/learner_model.py`

- BKT算法更新mastery
- Beta分布表示掌握度不确定性
- 知识状态跟踪
- 遗忘曲线支持

### KnowledgeGraph (知识图谱)
**文件**: `python/core/knowledge_graph.py`

- 知识点依赖关系
- 拓扑排序规划学习路径
- 前置知识检查

### SpacedRepetition (间隔重复)
**文件**: `python/core/spaced_repetition.py`

- SM-2算法实现
- 复习计划生成
- 遗忘曲线预测

## 项目结构

```
eduagent/
├── frontend/                    # React前端
│   ├── src/
│   │   ├── App.tsx             # 主应用组件
│   │   ├── components/         # UI组件
│   │   └── hooks/              # 自定义Hook
│   └── package.json
├── python/                      # Python后端
│   ├── agents/                 # Agent实现
│   │   ├── base_agent.py       # Agent基类
│   │   ├── assessment_agent.py
│   │   ├── tutor_agent.py      # 含分级提示逻辑
│   │   ├── curriculum_agent.py # 含复习提醒逻辑
│   │   └── engagement_agent.py
│   ├── core/                   # 核心模块
│   │   ├── event_bus.py        # 事件总线
│   │   ├── learner_model.py    # 学习者模型
│   │   ├── knowledge_graph.py  # 知识图谱
│   │   └── spaced_repetition.py # 间隔重复
│   ├── api/                    # API层
│   │   ├── main.py             # FastAPI应用
│   │   ├── orchestrator.py     # Agent编排器
│   │   ├── routes.py           # API路由
│   │   └── websocket.py        # WebSocket支持
│   ├── models/                 # 数据模型
│   │   ├── database.py         # SQLAlchemy模型
│   │   └── session.py          # 数据库会话
│   └── requirements.txt
├── docker-compose.yml          # Docker编排
└── .env.example                # 环境变量模板
```

## 开发指南

### 本地开发

1. 克隆项目
2. 复制 `.env.example` 为 `.env` 并配置
3. 启动Docker服务: `docker-compose up -d postgres`
4. 安装Python依赖: `cd python && pip install -r requirements.txt`
5. 启动后端: `python -m uvicorn api.main:app --reload --port 8888`
6. 安装前端依赖: `cd frontend && npm install`
7. 启动前端: `npm run dev`

### 添加新Agent

1. 在 `python/agents/` 创建新Agent类
2. 继承 `BaseAgent` 实现 `subscribed_events` 和 `handle_event`
3. 在 `python/api/orchestrator.py` 初始化新Agent
4. 在 `EventType` 枚举中添加新事件类型（如需要）

### 测试

```bash
cd python
python -m pytest tests/
```

## 面试要点

### 架构设计
- 为什么选择Mesh架构而不是Supervisor或Pipeline？
- 事件驱动架构的优势：松耦合、可扩展、容错
- 开闭原则验证：新增Agent无需修改现有代码

### 算法选择
- BKT vs 简单正确率：BKT追踪动态学习过程，考虑猜测和失误
- SM-2 vs Leitner系统：SM-2更精细，连续调整间隔
- Beta分布表示mastery：共轭先验，更新方便，表达不确定性

### 教育学理论
- 苏格拉底式教学：不给答案，通过反问让学生自己发现
- Vygotsky最近发展区(ZPD)：分级提示的教育学依据
- 费曼学习法：让学生教别人，深化理解

### 系统设计
- 状态一致性保证：单写者策略、事件溯源、版本号
- 异步通信：asyncio.gather并发通知
- 数据库持久化：异步PostgreSQL，支持事件日志
