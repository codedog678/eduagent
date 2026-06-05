# 第4章：EventBus — 系统的神经系统

## 4.1 为什么需要EventBus

**核心问题**：4个Agent之间如何协作？

**方案对比**：

| 方案 | 描述 | 问题 |
|---|---|---|
| **直接调用** | Agent A 调用 Agent B 的方法 | 强耦合，A必须知道B的存在 |
| **Supervisor模式** | 中央调度器协调所有Agent | 单点瓶颈，调度器复杂度O(n²) |
| **EventBus模式** | Agent发布事件，订阅者自主响应 | ✅ 松耦合，可扩展，容错 |

**EventBus的核心思想**：

```
传统调用：  A ──直接调用──▶ B ──直接调用──▶ C
             （A必须知道B和C）

EventBus：  A ──发布事件──▶ EventBus ──分发──▶ B, C
             （A不知道谁在监听，B和C自主决定是否响应）
```

---

## 4.2 EventBus 核心实现

文件：`core/event_bus.py`（共296行）

### 数据模型

```python
class EventType(str, Enum):
    """系统中所有事件类型的枚举定义。"""

    # 学生交互事件（根事件，由Orchestrator发布）
    STUDENT_SUBMISSION = "student.submission"    # 学生提交答案
    STUDENT_QUESTION = "student.question"        # 学生提问
    STUDENT_MESSAGE = "student.message"          # 学生发消息

    # Assessment Agent 事件
    ASSESSMENT_COMPLETE = "assessment.complete"
    MASTERY_UPDATED = "assessment.mastery_updated"
    WEAKNESS_DETECTED = "assessment.weakness_detected"

    # Tutor Agent 事件
    TEACHING_RESPONSE = "tutor.teaching_response"
    HINT_PROVIDED = "tutor.hint_provided"
    SOCRATIC_QUESTION = "tutor.socratic_question"

    # Curriculum Agent 事件
    REVIEW_SCHEDULED = "curriculum.review_scheduled"
    NEXT_TOPIC = "curriculum.next_topic"
    REVIEW_REMINDER = "curriculum.review_reminder"
    LEARNING_PATH_UPDATE = "curriculum.learning_path_update"

    # Engagement Agent 事件
    ENGAGEMENT_ALERT = "engagement.alert"
    ENCOURAGEMENT = "engagement.encouragement"
    PACE_ADJUSTMENT = "engagement.pace_adjustment"
    EMOTION_DETECTED = "engagement.emotion_detected"

    # Feedback / Session 事件
    FEEDBACK_GENERATED = "feedback.generated"
    SESSION_START = "session.start"
    SESSION_END = "session.end"


class Event(BaseModel):
    """事件数据模型。"""
    id: str                    # UUID唯一标识
    type: EventType            # 事件类型
    source: str                # 发布者（Agent名称）
    timestamp: datetime        # 发布时间
    learner_id: str            # 关联的学习者
    data: dict[str, Any]       # 事件负载数据
    correlation_id: str | None # 关联链ID（追踪事件因果）
    priority: EventPriority    # 优先级：LOW/NORMAL/HIGH/CRITICAL
```

### EventBus 类核心方法

```python
class EventBus:
    MAX_HISTORY = 1000  # 内存中最多保留1000条事件

    def __init__(self, enable_db_logging: bool = False):
        self._subscribers: dict[EventType, list[EventHandler]] = {}  # 订阅表
        self._event_history: list[Event] = []                        # 内存历史
        self._lock = asyncio.Lock()                                  # 并发锁
        self._enable_db_logging = enable_db_logging                  # 是否写DB
        self._correlation_chains: dict[str, list[Event]] = {}        # 事件链追踪
```

---

## 4.3 三个核心机制

### 机制1：发布-订阅（Pub-Sub）

```python
def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
    """订阅某类事件。"""
    if event_type not in self._subscribers:
        self._subscribers[event_type] = []
    if handler not in self._subscribers[event_type]:
        self._subscribers[event_type].append(handler)

async def publish(self, event: Event) -> None:
    """发布事件，通知所有订阅者。"""
    # 1. 记录到内存历史
    async with self._lock:
        self._event_history.append(event)

    # 2. 可选：写入数据库（事件溯源）
    if self._enable_db_logging:
        await self._log_event_to_db(event)

    # 3. 并发通知所有订阅者
    handlers = self._subscribers.get(event.type, [])
    tasks = [self._safe_handle(handler, event) for handler in handlers]
    await asyncio.gather(*tasks)  # 并发执行，不阻塞
```

**关键设计**：
- `asyncio.gather` 实现**并发分发**，多个Agent同时处理
- `_safe_handle` 包裹异常，**一个Agent出错不影响其他Agent**

```python
async def _safe_handle(self, handler: EventHandler, event: Event) -> None:
    """安全执行handler，捕获异常避免影响其他订阅者。"""
    try:
        await handler(event)
    except Exception:
        logger.exception("Error in handler for event %s", event.type.value)
        # 不重新抛出，保证其他handler继续执行
```

### 机制2：关联链（Correlation Chain）

**问题**：学生提交一个答案，可能触发一连串事件，如何追踪因果关系？

**解决**：所有相关事件共享同一个 `correlation_id`。

```python
async def publish(self, event: Event) -> None:
    # 追踪事件链
    if event.correlation_id:
        if event.correlation_id not in self._correlation_chains:
            self._correlation_chains[event.correlation_id] = []
        self._correlation_chains[event.correlation_id].append(event)

def get_correlation_chain(self, correlation_id: str) -> list[Event]:
    """获取指定 correlation_id 的完整事件链。"""
    return self._correlation_chains.get(correlation_id, [])
```

**实际事件链示例**：

```
correlation_id = "abc-123"

Event 1: STUDENT_SUBMISSION (source: orchestrator)
    │
    ├──▶ Event 2: MASTERY_UPDATED (source: assessment_agent)
    ├──▶ Event 3: ASSESSMENT_COMPLETE (source: assessment_agent)
    │       │
    │       ├──▶ Event 4: TEACHING_RESPONSE (source: tutor_agent)
    │       └──▶ Event 5: NEXT_TOPIC (source: curriculum_agent)
    │
    └──▶ Event 6: ENGAGEMENT_ALERT (source: engagement_agent)

共6个事件，全部可通过 correlation_id="abc-123" 一次查出
```

### 机制3：事件溯源（Event Sourcing）

**问题**：内存中的事件历史会丢失，如何持久化？

**解决**：可选地将每个事件写入 PostgreSQL `event_logs` 表。

```python
async def _log_event_to_db(self, event: Event) -> None:
    """将事件写入EventLog表（事件溯源）。"""
    from models.session import async_session
    from models.database import EventLog

    async with async_session() as session:
        event_log = EventLog(
            event_id=event.id,
            event_type=event.type.value,
            source=event.source,
            learner_id=event.learner_id,
            data=event.data,
            correlation_id=event.correlation_id,
            created_at=event.timestamp,
        )
        session.add(event_log)
        await session.commit()
```

**事件溯源的好处**：
- 可以回放任意时间点的系统状态
- 支持审计和调试
- Agent崩溃后可从DB恢复事件历史

**数据库查询**：

```python
async def get_event_history_from_db(
    self,
    learner_id: str | None = None,
    event_type: EventType | None = None,
    correlation_id: str | None = None,
    limit: int = 50,
) -> list[Event]:
    """从PostgreSQL查询事件历史，支持降级到内存。"""
    try:
        # 查DB...
    except Exception as e:
        # 降级到内存历史
        return self.get_history(learner_id, event_type, correlation_id, limit)
```

---

## 4.4 Agent如何使用EventBus

### 注册阶段（Agent初始化时）

```python
# agents/assessment_agent.py 中的注册逻辑
class AssessmentAgent(BaseAgent):
    def __init__(self, ...):
        super().__init__(...)
        # 注册感兴趣的事件类型
        self.event_bus.subscribe(EventType.STUDENT_SUBMISSION, self.handle_event)
```

4个Agent的订阅关系：

| Agent | 订阅的事件 |
|---|---|
| AssessmentAgent | `STUDENT_SUBMISSION` |
| TutorAgent | `ASSESSMENT_COMPLETE`, `STUDENT_QUESTION`, `STUDENT_MESSAGE`, `ENGAGEMENT_ALERT` |
| CurriculumAgent | `MASTERY_UPDATED`, `WEAKNESS_DETECTED`, `PACE_ADJUSTMENT` |
| EngagementAgent | `STUDENT_SUBMISSION`, `ASSESSMENT_COMPLETE`, `STUDENT_MESSAGE` |

### 运行阶段（事件分发）

```
Orchestrator 发布 STUDENT_SUBMISSION
    │
    ├──▶ AssessmentAgent.handle_event()  ← 订阅了这个事件
    │       → 运行BKT算法
    │       → 发布 MASTERY_UPDATED
    │       → 发布 ASSESSMENT_COMPLETE
    │
    ├──▶ EngagementAgent.handle_event()  ← 也订阅了这个事件
    │       → 分析情绪状态
    │       → 发布 ENGAGEMENT_ALERT（如需要）
    │
    └──▶ TutorAgent  ❌ 不响应（没订阅 STUDENT_SUBMISSION）

MASTERY_UPDATED 被发布后
    │
    └──▶ CurriculumAgent.handle_event()  ← 订阅了这个事件
            → 更新复习计划
            → 发布 NEXT_TOPIC / REVIEW_SCHEDULED
```

---

## 4.5 EventBus 的容错设计

### 1. 异常隔离

```python
async def _safe_handle(self, handler, event):
    try:
        await handler(event)
    except Exception:
        logger.exception("Error in handler")  # 只记日志，不抛出
        # 其他handler不受影响
```

### 2. 内存限制

```python
MAX_HISTORY = 1000
if len(self._event_history) > self.MAX_HISTORY:
    self._event_history = self._event_history[-self.MAX_HISTORY:]
```

### 3. DB写入失败不影响分发

```python
async def _log_event_to_db(self, event):
    try:
        # 写DB...
    except Exception as e:
        logger.error("Failed to log event: %s", e)
        # 继续执行，不影响事件分发
```

### 4. DB查询失败降级到内存

```python
async def get_event_history_from_db(self, ...):
    try:
        # 查DB...
    except Exception:
        return self.get_history(...)  # 降级到内存历史
```

---

## 4.6 完整事件流示例

**场景**：学生提交一道英语题的答案

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 学生点击"提交"                                            │
│    前端 POST /api/submit                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Orchestrator 接收请求                                     │
│    生成 correlation_id = "xyz-789"                           │
│    发布根事件:                                               │
│    Event(type=STUDENT_SUBMISSION, source="orchestrator",    │
│          learner_id="student_1", data={...},                │
│          correlation_id="xyz-789")                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. EventBus 分发给所有订阅者                                  │
│    → AssessmentAgent (订阅了 STUDENT_SUBMISSION)             │
│    → EngagementAgent (订阅了 STUDENT_SUBMISSION)             │
└───────────┬────────────────────────────┬────────────────────┘
            │                            │
            ▼                            ▼
┌───────────────────────┐  ┌─────────────────────────────────┐
│ 4a. AssessmentAgent   │  │ 4b. EngagementAgent             │
│     运行BKT算法        │  │     分析情绪状态                 │
│     更新掌握度          │  │     追踪连续答题                 │
│                       │  │                                 │
│     发布:             │  │     发布(如需要):                │
│     - MASTERY_UPDATED │  │     - ENGAGEMENT_ALERT          │
│     - ASSESSMENT_     │  │     - ENCOURAGEMENT             │
│       COMPLETE        │  │     - PACE_ADJUSTMENT           │
└───────────┬───────────┘  └─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. EventBus 再次分发（MASTERY_UPDATED）                       │
│    → CurriculumAgent (订阅了 MASTERY_UPDATED)                │
│                                                             │
│    CurriculumAgent:                                         │
│    - 更新SM-2复习计划                                        │
│    - 检查知识图谱就绪节点                                     │
│    - 发布: NEXT_TOPIC, REVIEW_SCHEDULED                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. EventBus 再次分发（ASSESSMENT_COMPLETE）                   │
│    → TutorAgent (订阅了 ASSESSMENT_COMPLETE)                 │
│    → EngagementAgent (订阅了 ASSESSMENT_COMPLETE)            │
│                                                             │
│    TutorAgent:                                              │
│    - 生成教学回复（3级提示）                                  │
│    - 发布: TEACHING_RESPONSE                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Orchestrator 收集所有事件                                  │
│    从DB查询 correlation_id="xyz-789" 的所有事件              │
│    构建 InteractionResult 返回给前端                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 4.7 关键数据结构总结

| 结构 | 位置 | 作用 |
|---|---|---|
| `EventType` 枚举 | `core/event_bus.py:35` | 定义所有21种事件类型 |
| `Event` 模型 | `core/event_bus.py:73` | 事件数据载体（id/type/source/data/correlation_id） |
| `EventBus` 类 | `core/event_bus.py:89` | 发布-订阅核心实现 |
| `_subscribers` 字典 | `core/event_bus.py:105` | 事件类型 → handler列表的映射 |
| `_correlation_chains` | `core/event_bus.py:109` | correlation_id → 事件链的映射 |
| `EventLog` ORM | `models/database.py:135` | 事件持久化到PostgreSQL |

---

## 4.8 汇报要点

**讲这部分时可以这样说**：

> "系统的通信层采用**事件驱动Mesh架构**，核心是 `EventBus` 事件总线。
>
> 与传统的 Supervisor 中央调度模式不同，本系统的4个Agent**自主订阅**感兴趣的事件类型，**自主决定**如何响应。EventBus只负责分发，不关心谁在监听。
>
> 三个关键设计：
> 1. **发布-订阅解耦**：Agent之间零耦合，新增Agent不需要修改现有代码
> 2. **关联链追踪**：通过 `correlation_id` 追踪一次学生操作触发的完整事件链，支持调试和审计
> 3. **事件溯源**：所有事件持久化到PostgreSQL，支持回放和状态恢复
>
> 这种架构的核心优势是**可扩展性**：未来要新增一个Agent，只需要让它订阅现有事件类型即可，不需要修改任何现有Agent的代码。"

---

## 4.9 涉及文件清单

| 文件 | 职责 |
|---|---|
| `core/event_bus.py` | EventBus核心实现（296行） |
| `models/database.py` → `EventLog` | 事件持久化ORM |
| `models/session.py` → `async_session` | 数据库连接（写入/查询事件日志） |
| `agents/base.py` → `register()` | Agent注册到EventBus |
| `agents/*.py` → `handle_event()` | 各Agent的事件处理逻辑 |
| `api/orchestrator.py` → `publish_root_event()` | 发布根事件 |
| `tests/v2/test_event_bus.py` | EventBus单元测试 |
