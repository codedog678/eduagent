# 前端重设计方案

## 概述

对多 Agent 智能教育系统前端进行全面重设计，解决以下问题：
- 界面不美观，代码使用内联样式难以维护
- 两栏布局导致一屏放不下，需要滚动
- 所有文本为英文，需改为中文
- 部分数据未持久化到数据库

## 设计决策

| 决策项 | 选择 | 理由 |
|-------|------|------|
| 布局方案 | 主侧栏布局（左65%+右35%） | 学习流程自然，一屏展示完整 |
| 视觉风格 | 简洁专业风 | 白底+浅灰边框，清爽易读 |
| UI 框架 | Ant Design | 中文生态好，组件丰富 |
| 界面语言 | 中文 | 用户需求 |
| 题库持久化 | 不需要 | 保持 LLM 动态生成 |

## 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  Logo    首页    数据分析    [WebSocket状态]    学习者   │
├────────────────────────────────┬────────────────────────┤
│                                │                        │
│   知识点选择 [下拉框]          │   复习提醒卡片         │
│                                │   - 待复习项           │
│   测验区                       │   - 记忆保持率         │
│   - 题目 + 选项               │                        │
│   - 提交按钮                   ├────────────────────────┤
│                                │                        │
├────────────────────────────────┤   最近互动反馈         │
│                                │   - 评估结果           │
│   向导师提问 [输入框]          │   - 教学响应           │
│   [发送按钮]                   │   - 教学决策           │
│                                │                        │
└────────────────────────────────┴────────────────────────┘
```

### 区域说明

1. **顶部导航栏**：Logo、页面切换、WebSocket 连接状态、学习者信息
2. **左侧主区域（65%）**：
   - 知识点选择下拉框
   - 测验区（题目、选项、提交按钮）
   - 向导师提问区（输入框、发送按钮）
3. **右侧辅助区域（35%）**：
   - 复习提醒卡片（待复习项、记忆保持率、紧急程度）
   - 最近互动反馈（评估结果、教学响应、教学决策）

## 视觉规范

### 配色方案

| 用途 | 颜色值 | 说明 |
|-----|-------|------|
| 主色 | `#2563eb` | 按钮、链接、强调 |
| 成功色 | `#059669` | 正确答案、已掌握 |
| 警告色 | `#ea580c` | 需复习、注意力 |
| 错误色 | `#dc2626` | 错误答案、紧急 |
| 背景色 | `#ffffff` | 页面背景 |
| 卡片边框 | `#e2e8f0` | 浅灰边框 |
| 主文字 | `#0f172a` | 标题、正文 |
| 次文字 | `#64748b` | 说明文字 |

### 组件规范

- 卡片圆角：`8px`
- 按钮圆角：`6px`
- 间距单位：`8px` 倍数
- 字体：系统默认字体栈

## 数据持久化

### 已有数据库表

| 表名 | 用途 | 状态 |
|-----|------|------|
| `learners` | 学习者基本信息 | ✅ 已有 |
| `knowledge_states` | 知识点掌握度（BKT） | ✅ 已有 |
| `learning_records` | 答题记录 | ✅ 已有 |
| `review_items` | 复习计划（SM-2） | ✅ 已有 |
| `event_logs` | 事件日志 | ✅ 已有 |
| `agent_states` | Agent 状态 | ✅ 已有 |

### 需新增：学习统计视图

从 `learning_records` 表聚合计算，无需新建表：

```sql
-- 学习统计视图
CREATE VIEW learner_statistics AS
SELECT
    learner_id,
    COUNT(*) as total_questions,
    SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_answers,
    SUM(CASE WHEN NOT is_correct THEN 1 ELSE 0 END) as wrong_answers,
    ROUND(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END)::DECIMAL / COUNT(*), 2) as accuracy,
    SUM(time_spent_seconds) / 60.0 as total_time_minutes,
    AVG(time_spent_seconds) as avg_time_per_question,
    MAX(created_at) as last_activity
FROM learning_records
GROUP BY learner_id;
```

或在 Python 层通过 API 实时计算（更灵活，无需维护视图）。

## 前端组件结构

```
src/
├── App.tsx                    # 主应用，路由和状态管理
├── components/
│   ├── Header.tsx             # 顶部导航栏
│   ├── KnowledgeSelect.tsx    # 知识点选择下拉框
│   ├── QuizPanel.tsx          # 测验区（题目+选项+提交）
│   ├── QuestionInput.tsx      # 向导师提问区
│   ├── FeedbackPanel.tsx      # 最近互动反馈
│   ├── ReviewReminder.tsx     # 复习提醒卡片
│   └── AnalyticsDashboard.tsx # 数据分析页（已有，需中文化）
├── hooks/
│   └── useWebSocket.ts        # WebSocket 连接（已有）
└── types/
    └── index.ts               # TypeScript 类型定义
```

### 核心组件说明

1. **Header.tsx**：使用 Ant Design 的 `Layout.Header`，包含导航菜单和状态指示器
2. **QuizPanel.tsx**：使用 Ant Design 的 `Card`、`Radio.Group`、`Button`
3. **FeedbackPanel.tsx**：使用 Ant Design 的 `Card`、`Tag`、`Descriptions`
4. **ReviewReminder.tsx**：使用 Ant Design 的 `Card`、`Progress`、`Badge`

## 中文化清单

需要翻译的文本：

### 通用
- "Learning Workspace" → "学习工作台"
- "Quiz Practice" → "测验练习"
- "Ask the Tutor" → "向导师提问"
- "Interaction Feed" → "互动记录"
- "Review Queue" → "复习队列"
- "Analytics" → "数据分析"

### 按钮
- "Generate Quiz" → "生成测验"
- "New Quiz" → "新测验"
- "Submit Answer" → "提交答案"
- "Send Question" → "发送提问"
- "Seed Demo Data" → "初始化演示数据"
- "Review Now" → "立即复习"

### 反馈
- "Correct" → "正确"
- "Needs Review" → "需复习"
- "Conversation" → "对话"
- "Evaluation" → "评估结果"
- "Tutor Response" → "导师响应"
- "Teaching Decision" → "教学决策"

### 数据
- "Mastery" → "掌握度"
- "Retention" → "记忆保持率"
- "Urgency" → "紧急程度"
- "Due now" → "待复习"
- "Accuracy" → "正确率"
- "Study Time" → "学习时长"
- "Hints Used" → "使用提示数"
- "Total Questions" → "总题数"

## API 端点

### 已有端点（无需改动）
- `POST /api/quiz/generate` — 生成测验
- `POST /api/quiz/answer` — 提交答案
- `POST /api/question` — 向导师提问
- `GET /api/analytics/{learner_id}` — 获取分析数据
- `GET /api/review-schedule/{learner_id}` — 获取复习计划
- `POST /api/review/complete` — 完成复习
- `POST /api/demo/init` — 初始化演示数据

### 需新增端点
- `GET /api/statistics/{learner_id}` — 获取学习统计数据

## 实施步骤

1. **安装 Ant Design**：`npm install antd`
2. **创建组件结构**：按上述目录结构创建文件
3. **翻译所有文本**：按中文化清单逐项翻译
4. **重构布局**：实现主侧栏布局
5. **替换内联样式**：使用 Ant Design 组件和 CSS Modules
6. **新增统计 API**：后端新增 `/api/statistics/{learner_id}` 端点
7. **测试和调优**：确保一屏展示、响应式适配

## 不在范围内

- 题库持久化（保持 LLM 动态生成）
- 新增数据库表（使用已有表 + 聚合查询）
- 移动端适配（本次聚焦桌面端一屏展示）
- 用户认证系统（保持当前简单模式）
