# 第7章：Agent层拆解

> 4个Agent是系统的"大脑"，每个Agent自主订阅事件、独立处理、发布结果。
> 本章逐一拆解每个Agent的职责、逻辑和教育技术学原理。

---

## 7.1 教育技术学视角下的Agent设计

### 为什么是4个Agent？

传统智能教学系统（ITS）通常有4个经典模块（Clancey, 1999）：

| 经典模块 | 对应Agent | 职责 |
|---|---|---|
| **领域模型** | AssessmentAgent | 知识状态追踪 |
| **学生模型** | EngagementAgent | 情感/参与度追踪 |
| **教学模型** | TutorAgent | 教学策略与回复 |
| **课程模型** | CurriculumAgent | 学习路径规划 |

Agent              核心职责                    主要操作的"模型"
─────────────────────────────────────────────────────────────
AssessmentAgent    评估掌握程度                 学习者模型（LearnerModel/BKT）
                   "学生会不会？"

EngagementAgent    监测学习状态                 学习者行为数据（情绪/疲劳/专注度）
                   "学生状态好不好？"

TutorAgent         生成教学回复                 教学策略模型（提示/苏格拉底/讲解）
                   "老师怎么教？"

CurriculumAgent    规划学习路径                 领域模型（知识图谱）+ 课程模型（间隔复习）
                   "接下来学什么？"



本项目的设计与经典ITS的对应关系：

```
经典ITS 4模块                    本项目4个Agent
┌─────────────┐              ┌─────────────────────┐
│ 领域模型     │  ←对应→     │ AssessmentAgent     │ 知识掌握追踪
│ (Domain)    │              │ BKT算法             │
├─────────────┤              ├─────────────────────┤
│ 学生模型     │  ←对应→     │ EngagementAgent     │ 情感/参与度追踪
│ (Student)   │              │ 状态机检测          │
├─────────────┤              ├─────────────────────┤
│ 教学模型     │  ←对应→     │ TutorAgent          │ 教学回复/提示
│ (Tutor)     │              │ LLM + 本地策略      │
├─────────────┤              ├─────────────────────┤
│ 课程模型     │  ←对应→     │ CurriculumAgent     │ 路径规划/复习调度
│ (Curriculum)│              │ 知识图谱 + SM-2     │
└─────────────┘              └─────────────────────┘
```

### Agent Mesh 架构

与传统 Supervisor（中央调度）不同，本项目采用 **Agent Mesh**（网格架构）：

```
Supervisor模式（传统）：          Mesh模式（本项目）：
        ┌───────┐                    AssessmentAgent
        │调度器  │                   ↗ ↘        ↗ ↘
        └─┬─┬─┬─┘            EventBus ←→ TutorAgent
          │ │ │                    ↘ ↗        ↘ ↗
     ┌────┘ │ └────┐           CurriculumAgent ←→ EngagementAgent
     ▼      ▼      ▼
   Agent1 Agent2 Agent3        每个Agent自主订阅，无中心调度
```

**Mesh 的优势**：
- 新增Agent不需要修改现有代码
- 单个Agent故障不影响其他Agent
- Agent可以独立开发和测试

---

## 7.2 BaseAgent — 所有Agent的骨架

文件：`agents/base.py`（194行）

### 抽象接口

```python
class BaseAgent(ABC):
    """所有Agent必须实现两个抽象方法。"""

    @abstractmethod
    async def handle_event(self, event: Event) -> Optional[dict[str, Any]]:
        """处理事件，返回结果（可选）。"""
        ...

    @abstractmethod
    def get_subscribed_events(self) -> list[EventType]:
        """返回订阅的事件类型列表。"""
        ...
```

### 生命周期

```
__init__()          创建Agent，注入EventBus和learner_models
    │
    ▼
register()          遍历get_subscribed_events()，注册到EventBus
    │
    ▼
[等待事件...]        EventBus分发事件到_safe_handle()
    │
    ▼
_safe_handle()      加锁 → 更新状态 → 调用handle_event() → 发布结果事件 → 更新状态
    │
    ▼
unregister()        从EventBus取消注册（可选）
```

### 安全执行机制

```python
async def _safe_handle(self, event: Event) -> None:
    async with self._lock:  # 串行处理，防止并发冲突
        self.status.state = AgentState.PROCESSING
        try:
            result = await self.handle_event(event)
            self.status.total_processed += 1
            # 自动发布结果事件
            if result and "events" in result:
                for event_data in result["events"]:
                    await self._publish_result_event(...)
        except Exception as e:
            self.status.total_errors += 1
            raise
        finally:
            self.status.state = AgentState.IDLE
```

**关键设计**：
- `self._lock`（asyncio.Lock）确保同一Agent**串行处理事件**，避免并发导致状态不一致
- `_safe_handle` 自动捕获异常，**一个Agent出错不影响其他Agent**
- 状态自动追踪（IDLE → PROCESSING → IDLE）

### 状态持久化接口

```python
def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
    """子类重写：返回需要持久化的状态。"""
    return None

def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
    """子类重写：恢复持久化的状态。"""
    pass
```

---

## 7.3 AssessmentAgent — 知识掌握追踪

文件：`agents/assessment_agent.py`（291行）

### 教育技术学背景

AssessmentAgent 的核心是**诊断性评价**（Diagnostic Assessment）：

> 不是简单地判断"对/错"，而是分析**为什么错**、**错在哪里**、**接下来怎么办**。

对应的教育理论：
- **BKT（贝叶斯知识追踪）**：量化知识状态变化
- **错误分析理论**：将错误分为概念性/程序性/粗心三类（Brown & Burton, 1978）
- **形成性评价**：持续追踪学习过程，而非仅看最终结果

### 订阅与发布

```python
def get_subscribed_events(self) -> list[EventType]:
    return [EventType.STUDENT_SUBMISSION]  # 只订阅一个事件

# 发布3个事件：
# - MASTERY_UPDATED: 掌握度变化
# - WEAKNESS_DETECTED: 薄弱点（可选）
# - ASSESSMENT_COMPLETE: 评估完成（触发Tutor和Curriculum）
```

### 核心处理逻辑

```python
async def _handle_submission(self, event: Event) -> dict[str, Any]:
    # 1. 更新掌握度（BKT算法）
    model = self.get_learner_model(learner_id)
    state = model.update_mastery(knowledge_id, is_correct)

    # 2. 分析错误模式
    error_patterns = self._analyze_error_patterns(learner_id, knowledge_id, data)

    # 3. 判断薄弱点/强项
    is_weakness = state.mastery < 0.4 and state.attempts >= 3
    is_strong_point = state.mastery > 0.8 and state.streak >= 3

    # 4. 生成评估策略（本地规则 或 LLM）
    strategy = await self._build_assessment_strategy(...)

    # 5. 发布3个事件
    await self.emit(MASTERY_UPDATED, ...)
    if is_weakness:
        await self.emit(WEAKNESS_DETECTED, ...)
    await self.emit(ASSESSMENT_COMPLETE, ...)
```

### 错误模式分析

```python
def _analyze_error_patterns(self, learner_id, knowledge_id, data):
    similarity = self._calculate_similarity(student_answer, correct_answer)

    if similarity < 0.3:
        error_type = "conceptual"    # 概念理解有误
    elif similarity < 0.7:
        error_type = "procedural"    # 解题步骤有误
    else:
        error_type = "careless"      # 粗心错误
```

**相似度计算**（字符集Jaccard）：

```python
def _calculate_similarity(self, text1, text2):
    set1 = set(text1.lower())
    set2 = set(text2.lower())
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union)
```

### 评估策略生成

```python
async def _build_assessment_strategy(self, ...):
    # 本地策略（默认）
    if is_correct and mastery >= 0.75:
        action = "advance"     # 可以推进
    elif is_correct:
        action = "practice"    # 继续练习
    elif mastery < 0.3 or attempts >= 3:
        action = "remediate"   # 需要补救
    else:
        action = "practice"    # 继续练习

    # 可选：LLM策略（需 enable_agent_llm_decisions=True）
    if settings.enable_agent_llm_decisions:
        response = await llm_service.generate_assessment_strategy(...)
        ...
```

### 功能总结

| 功能 | 实现 |
|---|---|
| 掌握度追踪 | BKT算法：`model.update_mastery()` |
| 错误分类 | 字符集相似度 → conceptual/procedural/careless |
| 薄弱点检测 | mastery < 0.4 且 attempts >= 3 |
| 强项识别 | mastery > 0.8 且 streak >= 3 |
| 评估策略 | 本地规则 + 可选LLM |

---

## 7.4 TutorAgent — 教学回复与提示

文件：`agents/tutor_agent.py`（558行，最大的Agent）

### 教育技术学背景

TutorAgent 的核心是**脚手架教学**（Scaffolding）和**苏格拉底式提问**：

| 理论 | 来源 | 在TutorAgent中的体现 |
|---|---|---|
| **脚手架理论** | Vygotsky的最近发展区 | 3级提示：元认知→脚手架→针对性 |
| **苏格拉底式提问** | 古希腊哲学 | 连续答错2次后触发追问式提示 |
| **生成效应** | 认知心理学 | 让学生自己思考，而非直接给答案 |
| **间隔检索练习** | Roediger & Karpicke | 提示不重复，鼓励主动回忆 |

### 3级提示系统

```python
class HintLevel:
    METACOGNITIVE = 1   # 元认知：引导学生自我反思
    SCAFFOLDING = 2     # 脚手架：提供排除顺序
    TARGETED = 3        # 针对性：直接给出关键规则
```

**提示升级策略**：

```
第1-2次提示 → Level 1 元认知
  "先别翻答案，先只看题干。和这道题最相关的第一条线索是什么？"

第3-4次提示 → Level 2 脚手架
  "给你一个排除顺序：先用线索排掉最不可能的两个，再在剩下两个里细比。"

第5次+提示 → Level 3 针对性
  "更具体一点，这题真正决定对错的就是这一条规则：..."
```

### 处理流程

```python
async def handle_event(self, event: Event):
    if event.type == ASSESSMENT_COMPLETE:
        return await self._handle_assessment(event)   # 答题反馈
    elif event.type == STUDENT_QUESTION:
        return await self._handle_student_question(event)  # 学生提问
    elif event.type == STUDENT_MESSAGE:
        return await self._handle_student_message(event)   # 自由消息
    elif event.type == ENGAGEMENT_ALERT:
        await self._handle_engagement_alert(event)         # 参与度警报
```

### 答题反馈逻辑

```python
async def _handle_assessment(self, event):
    if is_correct:
        # 答对：确认+强化
        reply = self._build_correct_answer_reply(...)
        await self._emit_teaching_response(teaching_style="confirmation")
        return

    attempts = self._student_attempts.get(attempt_key, 0) + 1

    if attempts >= 2:
        # 答错2次+：给提示
        reply, hint_level, hint_count = await self._provide_hint(...)
        await self._emit_teaching_response(teaching_style="hint")
        return

    # 答错1次：解释式回复
    reply = await self._generate_distinct_reply(...)
    await self._emit_teaching_response(teaching_style="guided_explanation")
```

### 回复去重机制

```python
async def _generate_distinct_reply(self, learner_id, knowledge_id, builder):
    recent = self._recent_teacher_responses(learner_id, knowledge_id, limit=2)
    reply = await builder(recent, 0)  # 第一次尝试
    if self._is_too_similar(reply.response, recent):
        reply = await builder(recent, 1)  # 换个变体再试
    return reply

def _is_too_similar(self, candidate, previous_responses):
    # 首句相同 → 太相似
    # 字符级相似度 >= 0.86 → 太相似
```

**为什么需要去重？** 避免学生看到重复的"先看题干线索"式回复，提升体验。

### 对话历史管理

```python
MAX_HISTORY = 16          # 全局对话历史上限
MAX_TOPIC_HISTORY = 10    # 单个知识点对话历史上限

# 双层历史：
# _conversation_history[learner_id] → 全局最近16条
# _topic_history[learner_id][knowledge_id] → 单知识点最近10条
```

### LLM 集成

```python
# TutorAgent 有4种LLM调用场景：
1. generate_answer_wrong_response()    → 答错后的解释
2. generate_student_question_response() → 回答学生提问
3. generate_hint_response()             → 生成提示
4. generate_message_response()          → 自由对话

# 每种场景都有本地降级模板
# LLM失败时自动回退到模板回复
```

---

## 7.5 CurriculumAgent — 课程规划与复习调度

文件：`agents/curriculum_agent.py`（627行）

### 教育技术学背景

| 理论 | 来源 | 在CurriculumAgent中的体现 |
|---|---|---|
| **间隔效应** | Ebbinghaus (1885) | SM-2间隔重复 |
| **遗忘曲线** | Ebbinghaus | 记忆保持率预测 |
| **掌握学习** | Bloom (1968) | mastery >= 0.6 才推进下一知识点 |
| **先决条件学习** | Gagné | 知识图谱前置依赖检查 |
| **最近发展区** | Vygotsky | 就绪节点 = 跳一跳够得着的内容 |

### 核心职责

```
CurriculumAgent
    │
    ├── 学习路径规划
    │   ├── 知识图谱拓扑排序
    │   ├── 就绪节点检测
    │   └── LLM推荐下一主题
    │
    ├── 复习调度
    │   ├── SM-2间隔重复
    │   ├── 遗忘曲线预测
    │   └── 生成复习提醒
    │
    └── 节奏调整
        ├── 识别弱项 → 补救路径
        └── 响应参与度Agent的PACE_ADJUSTMENT
```

### 订阅与发布

```python
def get_subscribed_events(self) -> list[EventType]:
    return [
        EventType.MASTERY_UPDATED,      # AssessmentAgent发布
        EventType.WEAKNESS_DETECTED,    # AssessmentAgent发布
        EventType.PACE_ADJUSTMENT,      # EngagementAgent发布
    ]

# 发布4个事件：
# - NEXT_TOPIC: 推荐下一个学习主题
# - REVIEW_SCHEDULED: 复习计划
# - REVIEW_REMINDER: 复习提醒
# - LEARNING_PATH_UPDATE: 学习路径更新
```

### Mastery → Quality 转换

```python
def _mastery_to_quality(self, mastery: float) -> int:
    """将BKT的mastery转换为SM-2的quality评分。"""
    if mastery >= 0.9:   return 5  # 完美
    if mastery >= 0.75:  return 4  # 正确
    if mastery >= 0.6:   return 3  # 困难
    if mastery >= 0.4:   return 2  # 错误
    if mastery >= 0.2:   return 1  # 不会
    return 0                       # 完全不会
```

**这是BKT和SM-2的桥梁**：AssessmentAgent更新mastery → CurriculumAgent将其转为quality → SM-2更新复习计划。

### 下一主题推荐

```python
async def _check_and_recommend_next(self, learner_id, correlation_id):
    # 1. 获取已掌握的知识点
    mastered_ids = {s.knowledge_id for s in model.knowledge_states.values()
                    if s.mastery >= 0.6}

    # 2. 知识图谱找就绪节点
    ready = self.knowledge_graph.get_ready_nodes(mastered_ids)

    # 3. 可选：LLM推荐（从就绪节点中选最优）
    candidates = ready[:6]
    response = await llm_service.generate_next_topic_recommendation(candidates, profile)
    # 如果LLM推荐了有效节点，用LLM的；否则用第一个就绪节点

    # 4. 发布NEXT_TOPIC事件
    await self.emit(NEXT_TOPIC, ...)
```

### 复习提醒生成

```python
async def _send_review_schedule(self, learner_id, correlation_id):
    items = list(self._review_items.get(learner_id, {}).values())

    # 1. SM-2获取到期复习项
    due_items = self.sr.get_due_items(items)

    # 2. 遗忘曲线预测即将遗忘的项
    for item in items:
        retention = model.get_forgetting_curve(item.knowledge_id, days_since_review)
        if retention < 0.5:
            forgetting_items.append(...)

    # 3. 生成复习提醒
    reminders = []
    for item in due_items:
        reminders.append(ReviewReminder(
            knowledge_id=item.knowledge_id,
            retention=0.0,           # 已到期
            days_since_review=...,
        ))
    for item in forgetting_items:
        reminders.append(ReviewReminder(
            knowledge_id=item["knowledge_id"],
            retention=item["retention"],  # 预测保持率
            days_since_review=...,
        ))

    # 4. 发布REVIEW_SCHEDULED和REVIEW_REMINDER
```

### ReviewReminder 紧急度

```python
class ReviewReminder:
    @property
    def urgency(self) -> str:
        if self.retention < 0.3:  return "urgent"   # 红色：快忘了
        if self.retention < 0.5:  return "high"     # 橙色：要忘了
        if self.retention < 0.7:  return "medium"   # 黄色：在遗忘
        return "low"                                 # 绿色：还好
```

---

## 7.6 EngagementAgent — 情感与参与度追踪

文件：`agents/engagement_agent.py`（432行）

### 教育技术学背景

| 理论 | 来源 | 在EngagementAgent中的体现 |
|---|---|---|
| **自我决定理论** | Deci & Ryan (1985) | 检测挫败/无聊，维护内在动机 |
| **流理论** | Csikszentmihalyi (1990) | 追踪挑战-技能平衡 |
| **情感检测** | Baker & Yacef (2009) | 基于行为的情感推断 |
| **干预理论** | 临床心理学 | 适时鼓励/降难度/建议休息 |

### 6种学习状态

```python
class LearningState(str, Enum):
    FOCUSED = "focused"       # 专注：正常学习
    STRUGGLING = "struggling" # 困难：刚出错，需要帮助
    FRUSTRATED = "frustrated" # 挫败：连续出错
    BORED = "bored"          # 无聊：太简单
    FATIGUED = "fatigued"    # 疲劳：学太久
    IDLE = "idle"            # 空闲：长时间无操作
```

### 状态检测逻辑

```python
def _detect_state(self, engagement: LearnerEngagement) -> LearningState:
    if engagement.idle_seconds > 300:                          # 5分钟无操作
        return LearningState.IDLE
    if engagement.consecutive_errors >= 3:                     # 连续3次错
        return LearningState.FRUSTRATED
    if engagement.session_duration_minutes > 45 and recent_accuracy < 0.5:  # 学45分钟+正确率<50%
        return LearningState.FATIGUED
    if engagement.recent_accuracy > 0.9 and consecutive_correct >= 5:        # 正确率>90%连续5题
        return LearningState.BORED
    if engagement.consecutive_errors >= 1:                     # 刚出错
        return LearningState.STRUGGLING
    return LearningState.FOCUSED
```

**状态优先级**：IDLE > FRUSTRATED > FATIGUED > BORED > STRUGGLING > FOCUSED

### 干预策略

| 状态 | 干预类型 | 具体行为 |
|---|---|---|
| **FRUSTRATED** | 降难度 + 鼓励 | 发ENGAGEMENT_ALERT + PACE_ADJUSTMENT(slow_down) |
| **BORED** | 提难度 | 发ENGAGEMENT_ALERT + PACE_ADJUSTMENT(speed_up) |
| **FATIGUED** | 建议休息 | 发ENCOURAGEMENT(break_suggestion) |
| **STRUGGLING** | 提示引导 | 由TutorAgent响应ENGAGEMENT_ALERT |
| **FOCUSED** | 正向鼓励 | 连续答对3题+时发ENCOURAGEMENT(每3题一次) |

### 参与度快照

```python
def _build_engagement_snapshot(self, engagement, event):
    return {
        "session_minutes": engagement.session_duration_minutes,  # 学习时长
        "recent_accuracy": engagement.recent_accuracy,            # 近10题正确率
        "consecutive_errors": engagement.consecutive_errors,      # 连续错误
        "consecutive_correct": engagement.consecutive_correct,    # 连续正确
        "speed_trend": speed_trend,                               # 速度趋势
        "recent_topics": recent_topics,                           # 近期练习的知识点
    }
```

---

## 7.7 四个Agent的协作全景

### 事件订阅-发布关系图

```
                         Orchestrator
                              │
                    publish_root_event()
                              │
                              ▼
                    ┌─── STUDENT_SUBMISSION ───┐
                    │                           │
                    ▼                           ▼
            AssessmentAgent              EngagementAgent
            (BKT更新掌握度)              (追踪参与度)
                    │                           │
                    ├→ MASTERY_UPDATED          ├→ EMOTION_DETECTED
                    ├→ WEAKNESS_DETECTED        ├→ PACE_ADJUSTMENT
                    └→ ASSESSMENT_COMPLETE      └→ ENCOURAGEMENT
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            TutorAgent              CurriculumAgent
            (教学回复)              (复习调度)
                    │                   │
                    ├→ TEACHING_RESPONSE ├→ NEXT_TOPIC
                    ├→ HINT_PROVIDED     ├→ REVIEW_SCHEDULED
                    └→ SOCRATIC_QUESTION └→ REVIEW_REMINDER
```

### 一次完整交互的事件链

```
correlation_id = "xyz-789"

1. STUDENT_SUBMISSION (orchestrator)
   │
   ├──▶ 2. MASTERY_UPDATED (assessment_agent)
   │       → CurriculumAgent 处理
   │       → 3. LEARNING_PATH_UPDATE (curriculum_agent)
   │       → 4. REVIEW_SCHEDULED (curriculum_agent)
   │       → 5. REVIEW_REMINDER (curriculum_agent)
   │
   ├──▶ 6. ASSESSMENT_COMPLETE (assessment_agent)
   │       → TutorAgent 处理
   │       → 7. TEACHING_RESPONSE (tutor_agent)
   │       → EngagementAgent 处理
   │       → 8. EMOTION_DETECTED (engagement_agent)
   │
   └──▶ 如果 mastery >= 0.6:
           → 9. NEXT_TOPIC (curriculum_agent)

共 7-9 个事件，全部可通过 correlation_id 一次查出
```

---

## 7.8 Agent 状态持久化

### 哪些状态需要持久化？

| Agent | 持久化内容 | 方法 |
|---|---|---|
| **AssessmentAgent** | 错误模式统计 | `get_state_for_save()` → `_error_patterns` |
| **TutorAgent** | 答题尝试次数 + 提示历史 | `get_state_for_save()` → `_student_attempts`, `_hint_history` |
| **CurriculumAgent** | 复习提醒列表 | `get_state_for_save()` → `_reminders` |
| **EngagementAgent** | 情绪状态 + 连续统计 + 最近结果 | `get_state_for_save()` → 完整的 `LearnerEngagement` |

### 持久化流程

```
保存：
  orchestrator → agent.get_state_for_save(learner_id)
              → 写入 agent_states.state_data (JSON)

恢复：
  orchestrator → agent.load_state(learner_id, state_data)
              → 从 agent_states.state_data 读取
```

---

## 7.9 汇报要点

**讲这部分时可以这样说**：

> "系统的4个Agent对应经典ITS的4个模块：
>
> **AssessmentAgent** 是'诊断医生'——用BKT算法追踪掌握度，分析错误是概念性的、步骤性的还是粗心的。
>
> **TutorAgent** 是'辅导老师'——提供3级渐进式提示：先引导自我反思，再给排除顺序，最后给关键规则。还会去重，避免学生看到重复回复。
>
> **CurriculumAgent** 是'课程规划师'——用知识图谱推荐下一主题，用SM-2安排复习，用遗忘曲线预测什么时候会忘。
>
> **EngagementAgent** 是'情感观察员'——追踪6种情绪状态（专注/困难/挫败/无聊/疲劳/空闲），适时降难度、提难度或建议休息。
>
> 4个Agent通过EventBus松耦合协作，新增Agent不需要修改现有代码。"

---

## 7.10 涉及文件清单

| 文件 | 行数 | 职责 |
|---|---|---|
| `agents/base.py` | 194 | Agent抽象基类 |
| `agents/assessment_agent.py` | 291 | BKT掌握度追踪 + 错误分析 |
| `agents/tutor_agent.py` | 558 | 教学回复 + 3级提示 + 对话历史 |
| `agents/curriculum_agent.py` | 627 | 知识图谱 + SM-2复习 + 遗忘曲线 |
| `agents/engagement_agent.py` | 432 | 情绪检测 + 干预策略 |
| `tests/test_agent_integration.py` | — | 多Agent集成测试 |



### 1. 学习者模型（LearnerModel）→ AssessmentAgent 主导

```python
# learner_model.py
class LearnerModel:
    knowledge_states: dict[str, KnowledgeState]  # 每个知识点的掌握度
    # mastery, attempts, correct_count, streak...
```

**作用：** 量化"学生会不会"。用 BKT 算法追踪掌握概率。

**谁在用：**

- AssessmentAgent：**主操作者**，每次答题后调用 `update_mastery()`
- TutorAgent：读取 mastery，决定教学难度
- CurriculumAgent：读取 mastery，安排学习路径
- EngagementAgent：读取 mastery，判断是否在挣扎

------

### 2. 行为/状态模型 → EngagementAgent 主导

```python
# engagement_agent.py
class LearnerEngagement:
    state: LearningState  # focused / struggling / frustrated / bored / fatigued
    recent_response_times: list[float]  # 最近的答题时间
    recent_results: list[bool]          # 最近的答题对错
    consecutive_errors: int             # 连续错误次数
    consecutive_correct: int            # 连续正确次数
    session_duration_minutes: float     # 学习时长
```

**作用：** 监测"学生状态好不好"。从答题行为中推断情绪状态。

**谁在用：**

- EngagementAgent：**主操作者**，分析行为数据推断情绪
- TutorAgent：收到 `ENGAGEMENT_ALERT` 后调整教学策略（比如学生沮丧时给鼓励）
- Orchestrator：在决策时参考情绪状态

------

### 3. 教学模型 → TutorAgent 主导

```python
# tutor_agent.py 中的教学策略
class HintLevel:
    METACOGNITIVE = 1    # 元认知提示（"想想看，这个词的前缀是什么意思？"）
    SCAFFOLDING = 2      # 脚手架提示（"abund- 表示充足，ant 是形容词后缀"）
    TARGETED = 3         # 针对性提示（"abundant = plentiful，丰富的"）
```

**作用：** 决定"怎么教"。根据学生状态选择教学策略。

**谁在用：**

- TutorAgent：**主操作者**，生成教学回复、分级提示、苏格拉底式提问
- LLM：根据 context 调用不同的 prompt 生成回复

------

### 4. 课程模型 → CurriculumAgent 主导

```python
# curriculum_agent.py 中涉及的模型
KnowledgeGraph    # 知识点拓扑关系（前置依赖）
SpacedRepetition  # SM-2 间隔重复算法
ReviewItem        # 复习项（下次复习时间、遗忘曲线）
```

**作用：** 决定"学什么、什么时候复习"。

**谁在用：**

- CurriculumAgent：**主操作者**，规划学习路径、安排复习
- Orchestrator：提取 `NEXT_TOPIC` 推荐给前端

------

## 它们之间的协作关系

**不是独立工作，而是"各司其职、数据共享"：**

```
学生答一道题（答错了）
        │
        ▼
AssessmentAgent：
  mastery: 0.75 → 0.62
  发布 ASSESSMENT_COMPLETE
        │
        ├──→ EngagementAgent：
        │      连续错误 +1，状态从 focused → struggling
        │      发布 ENGAGEMENT_ALERT
        │          │
        │          └──→ TutorAgent：
        │                 收到 ALERT，切换到"鼓励模式"
        │                 发布 TEACHING_RESPONSE："别灰心，这个词确实容易混淆..."
        │
        ├──→ CurriculumAgent：
        │      mastery 低于阈值，标记为需要复习
        │      发布 REVIEW_SCHEDULED
        │
        └──→ TutorAgent：
               收到 ASSESSMENT_COMPLETE
               根据 mastery=0.62 决定提示级别
               发布 TEACHING_RESPONSE
```

------

## 总结



```
┌─────────────────────────────────────────────────────────┐
│  四个 Agent 对应四个"模型维度"：                           │
│                                                         │
│  学习者模型  ←→  AssessmentAgent  （会不会？）           │
│  行为模型    ←→  EngagementAgent  （状态好不好？）        │
│  教学模型    ←→  TutorAgent       （怎么教？）            │
│  课程模型    ←→  CurriculumAgent  （学什么/什么时候复习？） │
│                                                         │
│  它们共享 LearnerModel 数据，通过 EventBus 协作。         │
│  不是"谁拥有模型"，而是"谁主导这个维度的决策"。            │
└────────────────────────
```
