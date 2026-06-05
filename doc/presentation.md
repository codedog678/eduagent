# EduAgent 系统设计文档

> 多Agent智能教育与个性化学习系统 — 架构、算法与协作机制

---

## 一、系统总览

EduAgent 是一个基于**事件驱动 Mesh 架构**的 AI 英语学习系统。4 个专业 Agent 通过 EventBus 异步协作，三大核心算法（BKT、SM-2、艾宾浩斯遗忘曲线）为每个学生的个性化学习提供数据支撑。

```
用户提交答案
    │
    ▼
 EventBus ──┬→ AssessmentAgent  ──→ 更新掌握度（BKT）
             ├→ TutorAgent       ──→ 生成教学回复（LLM）
             ├→ CurriculumAgent  ──→ 规划学习路径（SM-2 + 知识图谱 + 遗忘曲线）
             └→ EngagementAgent  ──→ 检测情绪状态（规则/LLM）
```

---

## 二、三大核心算法

### 2.1 BKT — 贝叶斯知识追踪

**解决的问题：** 学生现在对这个知识点掌握了多少？

**核心公式：**

```
答对时：P(L|correct) = P(L)×(1-P(S)) / [P(L)×(1-P(S)) + (1-P(L))×P(G)]
答错时：P(L|wrong)   = P(L)×P(S) / [P(L)×P(S) + (1-P(L))×(1-P(G))]
学习转移（仅答对后）：P(L_new) = P(L|obs) + (1-P(L|obs))×P(T)
```

**四个参数：**

| 参数 | 含义 | 默认值 | 直觉解释 |
|------|------|--------|---------|
| P(L₀) | 初始掌握概率 | 0.1 | 没学之前，10%的可能已经会了 |
| P(T) | 学习转移概率 | 0.15 | 每次练习有15%概率从不会变会 |
| P(G) | 猜对概率 | 0.2 | 不会时有20%概率蒙对 |
| P(S) | 失误概率 | 0.1 | 会时有10%概率做错 |

**输出：** mastery 概率（0~1），表示"学生已学会的概率"。

**关键特性：** 答错的惩罚远大于答对的奖励（因为猜对概率 P(G)=0.2 远大于失误概率 P(S)=0.1）。

**代码位置：** `python/core/learner_model.py` → `LearnerModel.update_mastery()`

---

### 2.2 SM-2 — 间隔重复算法

**解决的问题：** 什么时候安排复习？

**核心公式：**

```
EF' = EF + (0.1 - (5-q) × (0.08 + (5-q) × 0.02))    // 更新难度因子
q < 3  → 重置间隔为 1 天                                // 答得差就从头来
q ≥ 3:
  第1次成功 → 1 天后复习
  第2次成功 → 6 天后复习
  之后     → interval = 上次interval × EF               // 间隔指数增长
```

**参数说明：**

| 参数 | 含义 | 范围 |
|------|------|------|
| EF (easiness_factor) | 难度因子，决定间隔增长速度 | [1.3, 2.5] |
| interval_days | 当前复习间隔（天） | 动态计算 |
| repetition | 连续成功复习次数 | ≥ 0 |
| quality (q) | 回答质量评分 | 0-5 |

**quality 来源：** BKT 的 mastery 映射而来：

| mastery | quality | 含义 |
|---------|---------|------|
| ≥ 0.9 | 5 | 完美掌握 |
| ≥ 0.75 | 4 | 掌握良好 |
| ≥ 0.6 | 3 | 基本掌握 |
| ≥ 0.4 | 2 | 还不稳固 |
| ≥ 0.2 | 1 | 比较薄弱 |
| < 0.2 | 0 | 完全不会 |

**输出：** 下次复习时间 `next_review`，复习间隔 `interval_days`。

**代码位置：** `python/core/spaced_repetition.py` → `SpacedRepetition.review()`

---

### 2.3 艾宾浩斯遗忘曲线

**解决的问题：** 还能记住多久？

**核心公式：**

```
R = e^(-t/S)
```

| 符号 | 含义 |
|------|------|
| R | 记忆保持率（0~1） |
| t | 距离上次复习的天数 |
| S | 记忆强度（由 BKT 输出决定） |

**记忆强度 S 的计算：**

```python
S = mastery × (1 + streak × 0.1)
```

- mastery 越高 → S 越大 → 衰减越慢 → 记得越久
- streak 越高 → S 越大 → 连续答对的知识点更不容易忘

**遗忘曲线与 BKT 的关系：**

| | BKT | 遗忘曲线 |
|---|---|---|
| 回答的问题 | "现在会不会？" | "还能记多久？" |
| 触发时机 | 每次答题 | 按需查询 |
| 输入 | 答对/答错 | 距上次复习天数 |
| 输出 | mastery 概率 | 记忆保持率 R |
| 关系 | BKT 的输出是遗忘曲线的输入 | 依赖 BKT 的 mastery 和 streak |

**输出：** 记忆保持率 R（0~1），当 R < 0.5 时触发复习提醒。

**代码位置：** `python/core/learner_model.py` → `LearnerModel.get_forgetting_curve()`

---

### 2.4 三者协作关系

```
学生答题
  │
  ▼
BKT 算法 ──→ 输出 mastery（掌握概率）
  │               │
  │               ├──→ 映射为 SM-2 的 quality 分数
  │               │         │
  │               │         ▼
  │               │    SM-2 算法 ──→ 安排下次复习时间
  │               │
  │               └──→ 计算记忆强度 S
  │                         │
  │                         ▼
  │                   遗忘曲线 ──→ 预测还能记多久
  │                                    │
  │                                    ▼
  │                              是否需要复习？(R < 0.5)
  │
  ▼
CurriculumAgent 综合三者结果 → 决定下一步学什么
```

**一句话总结：** BKT 测量"当下会不会"，遗忘曲线预测"未来忘不忘"，SM-2 决定"什么时候复习"。BKT 的输出驱动另外两者。

---

## 三、四大 Agent 详解

### 3.1 AssessmentAgent — 评估专家

**职责：** 用 BKT 算法更新掌握度，分析错误模式，给出评估策略。

| 项目 | 内容 |
|------|------|
| 订阅事件 | `STUDENT_SUBMISSION` |
| 发布事件 | `MASTERY_UPDATED`、`WEAKNESS_DETECTED`（仅薄弱时）、`ASSESSMENT_COMPLETE` |
| 使用算法 | BKT（贝叶斯知识追踪） |
| 使用 LLM | 评估策略生成（受 `enable_agent_llm_decisions` 开关控制） |

**处理流程：**

```
STUDENT_SUBMISSION 到达
  │
  ├─① LearnerModel.update_mastery()     → BKT 贝叶斯更新
  ├─② _analyze_error_patterns()         → Jaccard 相似度分类错误类型
  ├─③ 判断薄弱点（mastery<0.4 且 attempts≥3）和强项
  ├─④ _build_assessment_strategy()      → 本地策略 / LLM 策略
  └─⑤ 发布事件
```

**错误模式分类（硬编码）：**

| 相似度 | 错误类型 | 含义 |
|--------|---------|------|
| < 0.3 | `conceptual` | 概念理解有误，答案差异大 |
| 0.3~0.7 | `procedural` | 解题步骤有误，部分正确 |
| > 0.7 | `careless` | 粗心错误，差一点就对 |

---

### 3.2 TutorAgent — 个性化导师

**职责：** 苏格拉底式教学，生成自然语言教学回复，提供分级提示。

| 项目 | 内容 |
|------|------|
| 订阅事件 | `STUDENT_SUBMISSION` |
| 发布事件 | `TEACHING_RESPONSE`、`HINT_PROVIDED` |
| 使用算法 | 无（纯 LLM 生成） |
| 使用 LLM | **始终调用**（不受 `enable_agent_llm_decisions` 开关控制） |

**提示分级（硬编码）：**

| 提示级别 | 触发条件 | 内容 |
|----------|---------|------|
| METACOGNITIVE（元认知） | hint_count ≤ 2 | 引导自主思考，不给答案 |
| SCAFFOLDING（脚手架） | hint_count ≤ 4 | 提供解题框架和排除方向 |
| TARGETED（定向） | hint_count > 4 | 直接给出关键规则和答案方向 |

METACOGNITIVE = 1   # 元认知：引导学生自我反思
    SCAFFOLDING = 2     # 脚手架：提供排除顺序
    TARGETED = 3        # 针对性：直接给出关键规则和答案方向

**特殊设计：**

- 答对确认回复：**始终本地模板**（不调用 LLM）
- 历史去重：SequenceMatcher 相似度 ≥ 0.86 时判定重复，避免回答雷同
- 对话上下文：维护 per-topic 历史（最多 10 条），支持连续追问

---

### 3.3 CurriculumAgent — 课程规划师

**职责：** 规划学习路径，安排复习计划，检测遗忘风险。

| 项目 | 内容 |
|------|------|
| 订阅事件 | `MASTERY_UPDATED`、`WEAKNESS_DETECTED`、`PACE_ADJUSTMENT` |
| 发布事件 | `LEARNING_PATH_UPDATE`、`NEXT_TOPIC`、`REVIEW_SCHEDULED`、`REVIEW_REMINDER` |
| 使用算法 | SM-2（间隔重复）+ 艾宾浩斯遗忘曲线 + 知识图谱（DAG 拓扑排序） |
| 使用 LLM | 课程策略 + 下一知识点推荐（部分受开关控制） |

**处理流程：**

```
MASTERY_UPDATED 到达
  │
  ├─① mastery → quality → SM-2.review()     → 更新复习间隔
  ├─② _build_curriculum_strategy()           → 本地策略 / LLM 策略
  │   └─ 发布 LEARNING_PATH_UPDATE
  ├─③ mastery ≥ 0.6?
  │   └─ KnowledgeGraph.get_ready_nodes()    → 找可推进的知识点
  │   └─ LLM 推荐（始终调用）
  │   └─ 发布 NEXT_TOPIC
  └─④ 检测遗忘
      ├─ SpacedRepetition.get_due_items()    → 到期复习项
      ├─ LearnerModel.get_forgetting_curve() → 遗忘检测（R<0.5）
      └─ 发布 REVIEW_SCHEDULED + REVIEW_REMINDER
```

**课程策略优先级（硬编码）：**

| 优先级 | 条件 | 动作 |
|--------|------|------|
| 1 | 有到期复习项 | `review`（先复习） |
| 2 | 当前 mastery < 0.4 | `remediate`（先补救） |
| 3 | 有 ready 的下一知识点 | `advance`（往前走） |
| 4 | 其他 | `practice`（继续练） |

**节奏调整（硬编码，响应 EngagementAgent）：**

| 动作 | 效果 |
|------|------|
| `slow_down` | 所有复习间隔 × 1.5（放慢节奏） |
| `speed_up` | 所有复习间隔 × 0.7（加快节奏） |

---

### 3.4 EngagementAgent — 参与度感知

**职责：** 检测学生情绪状态，触发教学干预。

| 项目 | 内容 |
|------|------|
| 订阅事件 | `STUDENT_SUBMISSION` |
| 发布事件 | `EMOTION_DETECTED`、`ENCOURAGEMENT`、`PACE_ADJUSTMENT` |
| 使用算法 | 无（规则引擎 / LLM） |
| 使用 LLM | 情绪评估（受 `enable_agent_llm_decisions` 开关控制） |

**情绪状态检测（硬编码规则）：**

| 状态 | 条件 | 干预动作 |
|------|------|---------|
| `IDLE` | 空闲 > 300秒 | 推送学习提醒 |
| `FRUSTRATED` | 连续答错 ≥ 3 次 | 鼓励 + `slow_down`（放慢节奏） |
| `FATIGUED` | 会话 > 45分钟 且 正确率 < 50% | 建议休息 |
| `BORED` | 正确率 > 90% 且 连续答对 ≥ 5 | `speed_up`（加快节奏）+ 增加难度 |
| `STRUGGLING` | 连续答错 ≥ 1 次 | 提供提示 |
| `FOCUSED` | 其他 | 保持当前节奏 |

**鼓励节流（硬编码）：** 每连续答对 3 题才触发一次鼓励，避免过度打扰。

---

## 四、Agent 事件协作全景

### 4.1 事件流转图

```
                         ┌──────────────────────────────┐
                         │       STUDENT_SUBMISSION      │
                         └──────┬───────┬───────┬────────┘
                                │       │       │
                    ┌───────────┘       │       └───────────┐
                    ▼                   ▼                   ▼
           ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
           │  Assessment  │   │    Tutor     │   │  Engagement  │
           │    Agent     │   │    Agent     │   │    Agent     │
           └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                  │                  │                   │
                  ▼                  ▼                   ▼
         MASTERY_UPDATED    TEACHING_RESPONSE    EMOTION_DETECTED
         ASSESSMENT_COMPLETE                      PACE_ADJUSTMENT
         WEAKNESS_DETECTED                        ENCOURAGEMENT
                  │                                      │
                  ▼                                      │
         ┌──────────────┐                               │
         │  Curriculum  │◄──────────────────────────────┘
         │    Agent     │
         └──────┬───────┘
                │
                ▼
       LEARNING_PATH_UPDATE
       NEXT_TOPIC
       REVIEW_SCHEDULED
       REVIEW_REMINDER
```

### 4.2 Agent 事件订阅/发布总表

| Agent | 订阅（输入） | 发布（输出） | 使用算法 |
|-------|-------------|-------------|---------|
| **AssessmentAgent** | `STUDENT_SUBMISSION` | `MASTERY_UPDATED`、`WEAKNESS_DETECTED`、`ASSESSMENT_COMPLETE` | BKT |
| **TutorAgent** | `STUDENT_SUBMISSION` | `TEACHING_RESPONSE`、`HINT_PROVIDED` | — |
| **CurriculumAgent** | `MASTERY_UPDATED`、`WEAKNESS_DETECTED`、`PACE_ADJUSTMENT` | `LEARNING_PATH_UPDATE`、`NEXT_TOPIC`、`REVIEW_SCHEDULED`、`REVIEW_REMINDER` | SM-2 + 遗忘曲线 + 知识图谱 |
| **EngagementAgent** | `STUDENT_SUBMISSION` | `EMOTION_DETECTED`、`ENCOURAGEMENT`、`PACE_ADJUSTMENT` | — |

### 4.3 Agent 之间的依赖关系

```
AssessmentAgent ───掌握度更新───→ CurriculumAgent
                  （核心数据流）

AssessmentAgent ───薄弱点检测───→ CurriculumAgent
                                  （触发补救路径）

EngagementAgent ───节奏调整───→ CurriculumAgent
                                （调整复习间隔）

EngagementAgent ───情绪状态───→ Orchestrator
                                （影响教学决策）

TutorAgent ───────教学回复───→ Orchestrator
                              （汇总给前端）
```

**关键依赖链：** AssessmentAgent 是数据源头 — 没有它的 BKT 输出，CurriculumAgent 无法安排复习，EngagementAgent 无法判断学习趋势。

---

## 五、硬编码 vs LLM 判断详解

### 5.1 全局开关

```python
# python/config/settings.py
enable_agent_llm_decisions: bool = False  # 默认关闭
```

当 `enable_agent_llm_decisions = False`（默认）时，所有 LLM 决策路径关闭，系统完全基于规则运行。

### 5.2 各模块决策方式总表

| 模块 | 决策内容 | 硬编码 / LLM / 可切换 | 说明 |
|------|---------|----------------------|------|
| **BKT 算法** | mastery 更新 | **始终硬编码** | 核心算法，不依赖 LLM |
| **错误模式分析** | 概念/步骤/粗心分类 | **始终硬编码** | Jaccard 相似度 |
| **薄弱点判断** | mastery<0.4 且 attempts≥3 | **始终硬编码** | 阈值判定 |
| **强项判断** | mastery>0.8 且 streak≥3 | **始终硬编码** | 阈值判定 |
| **评估策略** | 诊断 + 建议动作 | **可切换** | 开关控制，默认本地策略 |
| **答错回复** | 自然语言教学回复 | **始终调用 LLM** | TutorAgent 不受开关控制 |
| **学生提问回复** | 自然语言回答 | **始终调用 LLM** | TutorAgent 不受开关控制 |
| **提示生成** | 分级提示文本 | **始终调用 LLM** | TutorAgent 不受开关控制 |
| **答对确认** | 确认回复 | **始终硬编码** | 本地模板，不调用 LLM |
| **提示级别升级** | 元认知/脚手架/定向 | **始终硬编码** | 按 hint_count 阈值 |
| **SM-2 算法** | 复习间隔计算 | **始终硬编码** | 核心算法，不依赖 LLM |
| **mastery→quality 映射** | 0-5 分转换 | **始终硬编码** | 阈值映射表 |
| **遗忘曲线** | 记忆保持率计算 | **始终硬编码** | 核心算法，不依赖 LLM |
| **复习提醒** | 紧急程度分类 | **始终硬编码** | retention 阈值 |
| **知识图谱路径** | 拓扑排序 / 前置检查 | **始终硬编码** | DAG 算法 |
| **课程策略** | 补救/复习/推进/练习 | **可切换** | 开关控制，默认本地策略 |
| **下一知识点推荐** | 推荐哪个知识点 | **始终调用 LLM** | 无开关控制，LLM 失败回退到 ready[0] |
| **情绪状态检测** | 6 种状态分类 | **可切换** | 开关控制，默认规则引擎 |
| **干预路由** | 鼓励/减速/加速/休息 | **始终硬编码** | 按状态分发 |
| **鼓励节流** | 每 3 题一次 | **始终硬编码** | 计数器 |
| **教学决策（Orchestrator）** | 综合策略 | **可切换** | 开关控制，默认本地策略 |

### 5.3 设计原则

```
核心算法（BKT / SM-2 / 遗忘曲线 / 知识图谱）
  → 始终硬编码，保证确定性和可解释性

阈值判断（薄弱点 / 情绪状态 / 复习紧急度）
  → 始终硬编码，保证行为可预测

自然语言生成（教学回复 / 提示 / 策略描述）
  → 优先 LLM，本地模板兜底

策略决策（评估策略 / 课程策略 / 教学决策）
  → 可切换，默认本地规则，LLM 增强可选
```

**为什么这样设计？**

1. **确定性优先**：核心算法必须可复现、可调试，不能因为 LLM 的随机性导致 mastery 计算不一致
2. **无 LLM 也能跑**：不配置 API Key 时，系统完全基于规则运行，保证 demo 可用
3. **渐进增强**：先用规则保证基本功能，再用 LLM 提升自然语言质量和策略精细度
4. **容错兜底**：每个 LLM 调用都有本地 fallback，LLM 失败不影响核心流程

---

## 六、一次答题的完整链路

以学生答错一题 `vocab_basic` 为例：

```
1. 用户提交答案（is_correct=false）
   └→ API 发布 STUDENT_SUBMISSION 事件

2. AssessmentAgent 收到事件
   ├→ BKT 更新：mastery 0.1 → 0.078（答错下降）
   ├→ 错误分析：similarity=0.25 → "conceptual"（概念错误）
   ├→ 判断：mastery=0.078 < 0.4 且 attempts=1 → 暂不判定薄弱
   ├→ 评估策略：mastery < 0.3 → action="remediate"
   └→ 发布 MASTERY_UPDATED + ASSESSMENT_COMPLETE

3. TutorAgent 收到事件
   ├→ 调用 LLM 生成答错回复
   ├→ 分析错误原因，给出苏格拉底式引导
   └→ 发布 TEACHING_RESPONSE

4. CurriculumAgent 收到 MASTERY_UPDATED
   ├→ mastery=0.078 → quality=0 → SM-2 重置间隔为 1 天
   ├→ 课程策略：mastery < 0.4 → action="remediate"
   ├→ mastery < 0.6 → 不推荐下一知识点
   ├→ 检测遗忘：retention=1.0（刚学的，不会忘）
   └→ 发布 LEARNING_PATH_UPDATE

5. EngagementAgent 收到事件
   ├→ 连续答错 1 次 → state="struggling"
   ├→ 干预：提供提示
   └→ 发布 EMOTION_DETECTED

6. Orchestrator 汇总所有事件
   ├→ 提取各 Agent 输出
   ├→ 综合教学决策：action="remediate"（优先补救）
   └→ 返回给前端：评估结果 + 教学回复 + 课程建议 + 情绪状态
```

---

## 七、数据持久化

| 数据 | 存储位置 | 说明 |
|------|---------|------|
| LearnerModel（BKT 状态） | PostgreSQL `knowledge_states` 表 | mastery、alpha、beta、streak 等 |
| ReviewItem（SM-2 计划） | PostgreSQL `review_items` 表 | EF、interval、next_review |
| LearningRecord（答题记录） | PostgreSQL `learning_records` 表 | 对错、用时、mastery 前后变化 |
| EventLog（事件日志） | PostgreSQL `event_logs` 表 | 事件溯源，支持回放 |
| AgentState（Agent 状态） | PostgreSQL `agent_states` 表 | 提醒、错误模式等运行时状态 |
| 对话历史 | 内存（TutorAgent） | per-topic 上下文，不持久化 |
| 情绪状态 | 内存（EngagementAgent） | 连续计数器，不持久化 |

---

## 八、技术栈总结

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 |
| 数据库 | PostgreSQL 16 |
| LLM | Anthropic / OpenAI / MiniMax / DeepSeek + 模板回退 |
| 算法 | BKT + SM-2 + 艾宾浩斯遗忘曲线 + DAG 拓扑排序 |
| 架构 | 事件驱动 Mesh + Event Sourcing |
| 部署 | Docker Compose（3 服务） |



### 一、学生交互事件（API 层发布，系统的触发入口）

| 事件                 | 触发时机         | 载荷 data 包含                       | 谁会订阅                      |
| -------------------- | ---------------- | ------------------------------------ | ----------------------------- |
| `STUDENT_SUBMISSION` | 学生提交答案     | knowledge_id、is_correct、time_spent | Assessment、Tutor、Engagement |
| `STUDENT_QUESTION`   | 学生向导师提问   | knowledge_id、question               | Tutor                         |
| `STUDENT_MESSAGE`    | 学生发送普通消息 | message、knowledge_id                | Tutor                         |

这 3 个事件是**一切的起点**。没有它们，系统不会有任何动作。

------

### 二、AssessmentAgent 发布的事件（评估结果）

| 事件                  | 含义             | 载荷 data 包含                                           | 谁会订阅                     |
| --------------------- | ---------------- | -------------------------------------------------------- | ---------------------------- |
| `MASTERY_UPDATED`     | 掌握度已更新     | mastery、level、streak、is_weakness、assessment_strategy | **Curriculum**（核心数据流） |
| `WEAKNESS_DETECTED`   | 检测到薄弱知识点 | knowledge_id、mastery、error_patterns                    | Curriculum（触发补救路径）   |
| `ASSESSMENT_COMPLETE` | 本次评估完成     | 完整评估结果（含题目、答案、策略）                       | Orchestrator（汇总给前端）   |

**三者的关系：** `MASTERY_UPDATED` 每次都发，`ASSESSMENT_COMPLETE` 每次都发，`WEAKNESS_DETECTED` 只在判定为薄弱时才发。

------

### 三、TutorAgent 发布的事件（教学回复）

| 事件                | 含义             | 载荷 data 包含                                     | 谁会订阅                   |
| ------------------- | ---------------- | -------------------------------------------------- | -------------------------- |
| `TEACHING_RESPONSE` | 生成了教学回复   | response（自然语言）、teaching_style、context_type | Orchestrator（展示给前端） |
| `HINT_PROVIDED`     | 给出了提示       | hint_level、hint_text                              | Orchestrator               |
| `SOCRATIC_QUESTION` | 反问学生一个问题 | question（苏格拉底式追问）                         | Orchestrator               |

TutorAgent 的事件**主要是给人看的**——包含自然语言文本，前端直接展示给学生。

------

### 四、CurriculumAgent 发布的事件（学习路径）

| 事件                   | 含义               | 载荷 data 包含                                               | 谁会订阅                 |
| ---------------------- | ------------------ | ------------------------------------------------------------ | ------------------------ |
| `LEARNING_PATH_UPDATE` | 课程策略已更新     | curriculum_strategy（plan、action、target）                  | Orchestrator             |
| `NEXT_TOPIC`           | 推荐了下一个知识点 | knowledge_id、name、difficulty、reason、alternatives         | Orchestrator             |
| `REVIEW_SCHEDULED`     | 复习计划已安排     | due_now（到期项）、about_to_forget（即将遗忘）、weekly_schedule | Orchestrator             |
| `REVIEW_REMINDER`      | 发出复习提醒       | reminders（紧急程度列表）、urgent_count                      | 前端 ReviewReminder 组件 |

------

### 五、EngagementAgent 发布的事件（情绪与干预）

| 事件               | 含义               | 载荷 data 包含                                               | 谁会订阅                       |
| ------------------ | ------------------ | ------------------------------------------------------------ | ------------------------------ |
| `EMOTION_DETECTED` | 检测到学生情绪状态 | state（focused/struggling/frustrated/bored/fatigued/idle）、reason、suggestion | Orchestrator                   |
| `ENCOURAGEMENT`    | 触发了鼓励         | message（鼓励文本）                                          | 前端展示                       |
| `PACE_ADJUSTMENT`  | 要求调整学习节奏   | action（slow_down / speed_up）                               | **Curriculum**（调整复习间隔） |
| `ENGAGEMENT_ALERT` | 参与度异常警报     | alert_type、severity                                         | Orchestrator                   |

**`PACE_ADJUSTMENT` 是跨 Agent 通信的典型例子：** EngagementAgent 检测到学生疲劳 → 发布 `PACE_ADJUSTMENT(slow_down)` → CurriculumAgent 收到后把所有复习间隔 ×1.5。

------

### 六、系统级事件

| 事件                 | 含义           | 谁会订阅               |
| -------------------- | -------------- | ---------------------- |
| `SESSION_START`      | 学习会话开始   | 各 Agent（初始化状态） |
| `SESSION_END`        | 学习会话结束   | 各 Agent（保存状态）   |
| `FEEDBACK_GENERATED` | 生成了学习反馈 | 前端展示               |

------

### 事件之间的因果链



```
STUDENT_SUBMISSION（学生答题）
  │
  ├──→ AssessmentAgent
  │      └──→ MASTERY_UPDATED
  │             │
  │             ├──→ CurriculumAgent
  │             │      ├──→ LEARNING_PATH_UPDATE
  │             │      ├──→ NEXT_TOPIC（如果 mastery ≥ 0.6）
  │             │      └──→ REVIEW_SCHEDULED + REVIEW_REMINDER
  │             │
  │             └──→ （CurriculumAgent 内部更新 SM-2）
  │
  ├──→ TutorAgent
  │      └──→ TEACHING_RESPONSE
  │
  └──→ EngagementAgent
         ├──→ EMOTION_DETECTED
         ├──→ ENCOURAGEMENT（如果连续答对）
         └──→ PACE_ADJUSTMENT
                │
                └──→ CurriculumAgent（调整复习间隔）
```

**一句话：** 事件就是 Agent 之间的"消息"。一个事件可以被多个 Agent 同时订阅（广播），一个 Agent 也可以发布多个事件（链式触发）。整个系统的运转就是事件的流动。
