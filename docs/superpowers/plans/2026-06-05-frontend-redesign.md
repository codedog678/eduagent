# 前端重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将前端从内联样式+英文界面重构为 Ant Design + 中文界面的主侧栏布局，一屏展示完整学习工作台

**Architecture:** 使用 Ant Design 组件库构建响应式布局，左侧 65% 为测验区，右侧 35% 为反馈/复习区。所有文本改为中文，新增 TypeScript 类型定义文件统一管理类型。

**Tech Stack:** React 18, Vite, Ant Design 5, TypeScript

---

## 文件结构

```
frontend/src/
├── App.tsx                    # 修改：主布局重构
├── main.tsx                   # 无需修改
├── types/
│   └── index.ts               # 新建：TypeScript 类型定义
├── components/
│   ├── Header.tsx             # 新建：顶部导航栏
│   ├── KnowledgeSelect.tsx    # 新建：知识点选择
│   ├── QuizPanel.tsx          # 新建：测验区
│   ├── QuestionInput.tsx      # 新建：提问区
│   ├── FeedbackPanel.tsx      # 新建：互动反馈
│   ├── ReviewReminder.tsx     # 重写：复习提醒（Ant Design）
│   └── AnalyticsDashboard.tsx # 重写：数据分析（中文化）
└── hooks/
    └── useWebSocket.ts        # 无需修改
```

---

### Task 1: 安装 Ant Design

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装 antd 依赖**

```bash
cd e:/5.study/5.project/eduagent/frontend && npm install antd
```

- [ ] **Step 2: 验证安装成功**

```bash
cd e:/5.study/5.project/eduagent/frontend && npm ls antd
```

Expected: `antd@5.x.x`

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add antd dependency"
```

---

### Task 2: 创建 TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
// frontend/src/types/index.ts

export interface Quiz {
  question: string
  options: string[]
  correct_index: number
  explanation: string
  source?: string
  difficulty?: number
}

export interface TeachingResponse {
  response: string
  teaching_style: string
  context_type: string
  knowledge_id: string
  hint_level?: number | null
  hint_count?: number | null
}

export interface ReviewSnapshot {
  knowledge_id: string
  next_review: string | null
  retention: number | null
  urgency: string
  is_due: boolean
  days_since_review: number | null
  top_due_items: Array<{
    knowledge_id: string
    next_review: string
    overdue_days: number
  }>
}

export interface NextTopicRecommendation {
  knowledge_id: string
  name: string
  difficulty: number
  reason: string
  alternatives: string[]
}

export interface TeachingDecision {
  strategy: string
  priority: string
  summary: string
  next_action: string
  rationale: string
  generation_mode: string
  agent_votes?: Record<string, unknown>
}

export interface InteractionResult {
  learner_id: string
  knowledge_id: string
  correlation_id: string
  evaluation?: {
    is_correct: boolean
    feedback: string
    student_answer?: string
    correct_answer?: string
  } | null
  teaching_response?: TeachingResponse | null
  next_topic_recommendation?: NextTopicRecommendation | null
  teaching_decision?: TeachingDecision | null
  agent_insights?: Record<string, unknown>
  review_snapshot?: ReviewSnapshot | null
  interaction_events?: AgentEvent[]
  events_triggered?: number
}

export interface AgentEvent {
  event_type: string
  source: string
  timestamp: string
  correlation_id: string
  data: Record<string, unknown>
}

export interface ReminderItem {
  knowledge_id: string
  retention: number
  days_since_review: number
  urgency: 'urgent' | 'high' | 'medium' | 'low'
  created_at?: string
}

export interface DueItem {
  knowledge_id: string
  next_review: string
  overdue_days: number
}

export interface ForgettingStatusItem {
  knowledge_id: string
  retention: number
  days_since_review: number
  is_due: boolean
  next_review: string
}

export interface ReviewSchedule {
  reminders: ReminderItem[]
  due_items: DueItem[]
  forgetting_status: ForgettingStatusItem[]
  total_items: number
}

export interface KnowledgeOption {
  value: string
  label: string
}

export interface LearnerStatistics {
  total_questions: number
  correct_answers: number
  wrong_answers: number
  accuracy: number
  total_time_minutes: number
  avg_time_per_question: number
  last_activity: string | null
}

export const KNOWLEDGE_OPTIONS: KnowledgeOption[] = [
  { value: 'vocab_basic', label: '基础词汇' },
  { value: 'vocab_intermediate', label: '中级词汇' },
  { value: 'vocab_advanced', label: '高级词汇' },
  { value: 'vocab_academic', label: '学术词汇' },
  { value: 'grammar_tenses', label: '时态' },
  { value: 'grammar_passive', label: '被动语态' },
  { value: 'grammar_conditionals', label: '条件句' },
  { value: 'grammar_relative', label: '定语从句' },
  { value: 'reading_skimming', label: '略读' },
  { value: 'reading_scanning', label: '扫读' },
  { value: 'reading_inference', label: '推断' },
  { value: 'reading_main_idea', label: '主旨大意' },
  { value: 'writing_paragraph', label: '段落写作' },
  { value: 'writing_email', label: '邮件写作' },
  { value: 'writing_essay', label: '论文写作' },
  { value: 'writing_summary', label: '摘要写作' },
]

export const AGENT_META: Record<string, { name: string; color: string }> = {
  AssessmentAgent: { name: '评估助手', color: '#2563eb' },
  TutorAgent: { name: '导师', color: '#059669' },
  CurriculumAgent: { name: '课程助手', color: '#d97706' },
  EngagementAgent: { name: '激励助手', color: '#dc2626' },
  api: { name: '系统', color: '#64748b' },
}

export const EVENT_LABELS: Record<string, string> = {
  'student.submission': '提交答案',
  'student.question': '提问',
  'student.message': '消息',
  'assessment.mastery_updated': '掌握度更新',
  'assessment.complete': '评估完成',
  'assessment.weakness_detected': '发现薄弱点',
  'tutor.teaching_response': '导师响应',
  'curriculum.next_topic': '下一主题',
  'curriculum.review_scheduled': '安排复习',
  'curriculum.review_reminder': '复习提醒',
  'curriculum.learning_path_update': '学习路径策略',
  'engagement.alert': '激励提醒',
  'engagement.encouragement': '鼓励',
  'engagement.pace_adjustment': '节奏调整',
  'engagement.emotion_detected': '参与度策略',
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add TypeScript types and Chinese constants"
```

---

### Task 3: 创建 Header 组件

**Files:**
- Create: `frontend/src/components/Header.tsx`

- [ ] **Step 1: 创建 Header 组件**

```tsx
// frontend/src/components/Header.tsx
import { Layout, Menu, Badge, Tag, Button, Space } from 'antd'
import {
  BookOutlined,
  BarChartOutlined,
  ReloadOutlined,
} from '@ant-design/icons'

const { Header } = Layout

interface HeaderProps {
  activeTab: 'learning' | 'analytics'
  onTabChange: (tab: 'learning' | 'analytics') => void
  connected: boolean
  learnerId: string
  score: { correct: number; total: number }
  onInitDemo: () => void
}

export default function AppHeader({
  activeTab,
  onTabChange,
  connected,
  learnerId,
  score,
  onInitDemo,
}: HeaderProps) {
  const menuItems = [
    {
      key: 'learning',
      icon: <BookOutlined />,
      label: '学习工作台',
    },
    {
      key: 'analytics',
      icon: <BarChartOutlined />,
      label: '数据分析',
    },
  ]

  return (
    <Header
      style={{
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#2563eb' }}>
          智能学习平台
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[activeTab]}
          items={menuItems}
          onClick={({ key }) => onTabChange(key as 'learning' | 'analytics')}
          style={{ border: 'none', background: 'transparent' }}
        />
      </div>

      <Space size="middle">
        <Badge
          status={connected ? 'success' : 'error'}
          text={connected ? '已连接' : '重连中'}
        />
        <Tag color="blue">学习者: {learnerId}</Tag>
        <Tag color="green">
          得分: {score.correct}/{score.total || 0}
        </Tag>
        <Button
          icon={<ReloadOutlined />}
          onClick={onInitDemo}
          size="small"
        >
          初始化数据
        </Button>
      </Space>
    </Header>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Header.tsx
git commit -m "feat: add Header component with Ant Design"
```

---

### Task 4: 创建 KnowledgeSelect 组件

**Files:**
- Create: `frontend/src/components/KnowledgeSelect.tsx`

- [ ] **Step 1: 创建 KnowledgeSelect 组件**

```tsx
// frontend/src/components/KnowledgeSelect.tsx
import { Select, Typography } from 'antd'
import { KNOWLEDGE_OPTIONS } from '../types'

const { Label } = Typography

interface KnowledgeSelectProps {
  value: string
  onChange: (value: string) => void
}

export default function KnowledgeSelect({
  value,
  onChange,
}: KnowledgeSelectProps) {
  return (
    <div>
      <Label strong style={{ marginBottom: 8, display: 'block' }}>
        选择知识点
      </Label>
      <Select
        value={value}
        onChange={onChange}
        style={{ width: '100%' }}
        options={KNOWLEDGE_OPTIONS}
        placeholder="请选择要学习的知识点"
      />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/KnowledgeSelect.tsx
git commit -m "feat: add KnowledgeSelect component"
```

---

### Task 5: 创建 QuizPanel 组件

**Files:**
- Create: `frontend/src/components/QuizPanel.tsx`

- [ ] **Step 1: 创建 QuizPanel 组件**

```tsx
// frontend/src/components/QuizPanel.tsx
import { Card, Radio, Button, Typography, Space, Spin } from 'antd'
import { SendOutlined, ReloadOutlined } from '@ant-design/icons'
import type { Quiz } from '../types'

const { Title, Text, Paragraph } = Typography

interface QuizPanelProps {
  quiz: Quiz | null
  loading: boolean
  selectedOption: number | null
  onSelectOption: (index: number) => void
  onGenerateQuiz: () => void
  onSubmitQuiz: () => void
}

export default function QuizPanel({
  quiz,
  loading,
  selectedOption,
  onSelectOption,
  onGenerateQuiz,
  onSubmitQuiz,
}: QuizPanelProps) {
  return (
    <Card
      title={
        <Space>
          <span style={{ fontSize: 16, fontWeight: 600 }}>测验练习</span>
          <Text type="secondary" style={{ fontSize: 13 }}>
            题库动态生成，提交后获取导师指导
          </Text>
        </Space>
      }
      extra={
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={onGenerateQuiz}
          loading={loading}
        >
          {quiz ? '新测验' : '生成测验'}
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin tip="正在生成题目..." />
        </div>
      )}

      {!loading && !quiz && (
        <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
          点击"生成测验"开始练习
        </div>
      )}

      {!loading && quiz && (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Card
            style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
            bodyStyle={{ padding: 16 }}
          >
            <Paragraph style={{ fontSize: 15, marginBottom: 0, lineHeight: 1.7 }}>
              {quiz.question}
            </Paragraph>
          </Card>

          <Radio.Group
            value={selectedOption}
            onChange={(e) => onSelectOption(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              {quiz.options.map((option, index) => (
                <Radio
                  key={index}
                  value={index}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    padding: '12px 16px',
                    borderRadius: 8,
                    border: `1px solid ${selectedOption === index ? '#2563eb' : '#e2e8f0'}`,
                    background: selectedOption === index ? '#eff6ff' : '#fff',
                    width: '100%',
                  }}
                >
                  <span style={{ marginTop: 2 }}>{option}</span>
                </Radio>
              ))}
            </Space>
          </Radio.Group>

          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSubmitQuiz}
            disabled={selectedOption === null}
            block
            size="large"
          >
            提交答案
          </Button>
        </Space>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/QuizPanel.tsx
git commit -m "feat: add QuizPanel component"
```

---

### Task 6: 创建 QuestionInput 组件

**Files:**
- Create: `frontend/src/components/QuestionInput.tsx`

- [ ] **Step 1: 创建 QuestionInput 组件**

```tsx
// frontend/src/components/QuestionInput.tsx
import { Card, Input, Button, Typography } from 'antd'
import { SendOutlined } from '@ant-design/icons'

const { Text } = Typography
const { TextArea } = Input

interface QuestionInputProps {
  message: string
  onMessageChange: (value: string) => void
  onSubmit: () => void
}

export default function QuestionInput({
  message,
  onMessageChange,
  onSubmit,
}: QuestionInputProps) {
  return (
    <Card
      title={
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>向导师提问</div>
          <Text type="secondary" style={{ fontSize: 13 }}>
            问题独立于测验评分，保留当前页面上下文
          </Text>
        </div>
      }
      style={{ background: '#fff7ed', border: '1px solid #fed7aa' }}
    >
      <TextArea
        value={message}
        onChange={(e) => onMessageChange(e.target.value)}
        placeholder="询问当前主题、你犯的错误、或接下来该复习什么..."
        autoSize={{ minRows: 3, maxRows: 6 }}
        style={{ marginBottom: 12 }}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={onSubmit}
        disabled={!message.trim()}
        block
        style={{ background: '#ea580c', borderColor: '#ea580c' }}
      >
        发送提问
      </Button>
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/QuestionInput.tsx
git commit -m "feat: add QuestionInput component"
```

---

### Task 7: 创建 FeedbackPanel 组件

**Files:**
- Create: `frontend/src/components/FeedbackPanel.tsx`

- [ ] **Step 1: 创建 FeedbackPanel 组件**

```tsx
// frontend/src/components/FeedbackPanel.tsx
import { Card, Tag, Typography, Descriptions, Alert } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import type { InteractionResult, Quiz } from '../types'
import { KNOWLEDGE_OPTIONS } from '../types'

const { Title, Text, Paragraph } = Typography

interface FeedbackPanelProps {
  interaction: InteractionResult | null
  quiz: Quiz | null
}

function getKnowledgeLabel(knowledgeId: string): string {
  return KNOWLEDGE_OPTIONS.find((item) => item.value === knowledgeId)?.label || knowledgeId
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A'
  return `${Math.round(value * 100)}%`
}

export default function FeedbackPanel({ interaction, quiz }: FeedbackPanelProps) {
  if (!interaction) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
          <MessageOutlined style={{ fontSize: 32, marginBottom: 8 }} />
          <div>完成一次测验或提问后，互动反馈将显示在这里</div>
        </div>
      </Card>
    )
  }

  const evaluation = interaction.evaluation
  const teaching = interaction.teaching_response
  const review = interaction.review_snapshot
  const positive = evaluation?.is_correct ?? false

  return (
    <Card title="最近互动反馈" style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* 互动标题 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text strong style={{ fontSize: 15 }}>
              {getKnowledgeLabel(interaction.knowledge_id)}
            </Text>
          </div>
          <Tag
            icon={positive ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            color={evaluation ? (positive ? 'success' : 'error') : 'processing'}
          >
            {evaluation ? (positive ? '正确' : '需复习') : '对话'}
          </Tag>
        </div>

        {/* 评估结果 */}
        {evaluation && (
          <Alert
            type={positive ? 'success' : 'warning'}
            message="评估结果"
            description={
              <>
                <Paragraph style={{ marginBottom: 0 }}>{evaluation.feedback}</Paragraph>
                {!positive && evaluation.correct_answer && (
                  <Text type="danger" style={{ display: 'block', marginTop: 8 }}>
                    正确答案: {evaluation.correct_answer}
                  </Text>
                )}
                {!positive && quiz?.explanation && (
                  <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                    核心要点: {quiz.explanation}
                  </Text>
                )}
              </>
            }
          />
        )}

        {/* 导师响应 */}
        {teaching && (
          <Card
            size="small"
            title="导师响应"
            extra={<Tag color="blue">{teaching.context_type.replace('_', ' ')}</Tag>}
            style={{ background: '#eff6ff', border: '1px solid #bfdbfe' }}
          >
            <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
              {teaching.response}
            </Paragraph>
            {teaching.hint_count ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                提示级别 {teaching.hint_level || 1}，提示次数 {teaching.hint_count}
              </Text>
            ) : null}
          </Card>
        )}

        {/* 教学决策 */}
        {interaction.teaching_decision && (
          <Card
            size="small"
            title="教学决策"
            extra={<Tag color="purple">{interaction.teaching_decision.generation_mode}</Tag>}
            style={{ background: '#f5f3ff', border: '1px solid #c4b5fd' }}
          >
            <Paragraph style={{ marginBottom: 8 }}>
              {interaction.teaching_decision.summary}
            </Paragraph>
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="策略">
                {interaction.teaching_decision.strategy}
              </Descriptions.Item>
              <Descriptions.Item label="优先级">
                {interaction.teaching_decision.priority}
              </Descriptions.Item>
              <Descriptions.Item label="下一步">
                {interaction.teaching_decision.next_action}
              </Descriptions.Item>
            </Descriptions>
            {interaction.teaching_decision.rationale && (
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
                {interaction.teaching_decision.rationale}
              </Text>
            )}
          </Card>
        )}

        {/* 复习快照 */}
        {review && (
          <Card size="small" title="复习快照" style={{ background: '#f8fafc' }}>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="下次复习">
                {review.next_review ? new Date(review.next_review).toLocaleString() : '未安排'}
              </Descriptions.Item>
              <Descriptions.Item label="记忆保持率">
                {formatPercent(review.retention)}
              </Descriptions.Item>
              <Descriptions.Item label="紧急程度">
                {review.urgency}
              </Descriptions.Item>
              <Descriptions.Item label="待复习">
                {review.is_due ? '是' : '否'}
              </Descriptions.Item>
            </Descriptions>
            {review.top_due_items.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  待复习项目:
                </Text>
                {review.top_due_items.slice(0, 3).map((item) => (
                  <div key={`${item.knowledge_id}-${item.next_review}`} style={{ fontSize: 12, marginTop: 4 }}>
                    <Text>{getKnowledgeLabel(item.knowledge_id)}</Text>
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      {item.overdue_days > 0 ? `逾期 ${item.overdue_days} 天` : new Date(item.next_review).toLocaleString()}
                    </Text>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </Space>
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/FeedbackPanel.tsx
git commit -m "feat: add FeedbackPanel component"
```

---

### Task 8: 重写 ReviewReminder 组件

**Files:**
- Rewrite: `frontend/src/components/ReviewReminder.tsx`

- [ ] **Step 1: 重写 ReviewReminder 组件**

```tsx
// frontend/src/components/ReviewReminder.tsx
import { useEffect, useState } from 'react'
import { Card, Progress, Badge, Button, Typography, Space, List } from 'antd'
import { ClockCircleOutlined, AlertOutlined } from '@ant-design/icons'
import type { ReviewSchedule, ReminderItem } from '../types'
import { KNOWLEDGE_OPTIONS } from '../types'

const { Text, Title } = Typography

interface ReviewReminderProps {
  learnerId: string
  onStartReview?: (knowledgeId: string) => void
}

const URGENCY_META: Record<ReminderItem['urgency'], { color: string; progress: string }> = {
  urgent: { color: '#dc2626', progress: 'exception' },
  high: { color: '#ea580c', progress: 'exception' },
  medium: { color: '#ca8a04', progress: 'active' },
  low: { color: '#16a34a', progress: 'success' },
}

function getKnowledgeLabel(knowledgeId: string): string {
  return KNOWLEDGE_OPTIONS.find((item) => item.value === knowledgeId)?.label || knowledgeId
}

export default function ReviewReminder({ learnerId, onStartReview }: ReviewReminderProps) {
  const [schedule, setSchedule] = useState<ReviewSchedule | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    async function fetchSchedule() {
      try {
        const response = await fetch(`/api/review-schedule/${learnerId}`)
        const data = (await response.json()) as ReviewSchedule
        if (mounted) {
          setSchedule(data)
        }
      } catch (error) {
        console.error('Failed to load review schedule', error)
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    void fetchSchedule()
    const timer = window.setInterval(() => {
      void fetchSchedule()
    }, 30000)

    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [learnerId])

  const reminders = schedule?.reminders || []
  const dueItems = schedule?.due_items || []
  const urgentCount = reminders.filter((item) => item.urgency === 'urgent' || item.urgency === 'high').length

  return (
    <Card
      title={
        <Space>
          <span>复习队列</span>
          <Badge
            count={urgentCount > 0 ? `${urgentCount} 紧急` : '正常'}
            style={{
              backgroundColor: urgentCount > 0 ? '#dc2626' : '#16a34a',
            }}
          />
        </Space>
      }
      loading={loading}
      size="small"
      style={{ marginBottom: 16 }}
    >
      {reminders.length === 0 && dueItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 16, color: '#64748b' }}>
          <ClockCircleOutlined style={{ fontSize: 24, marginBottom: 8 }} />
          <div>暂无待复习内容</div>
        </div>
      ) : (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {reminders.slice(0, 3).map((item) => {
            const meta = URGENCY_META[item.urgency]
            const percent = Math.round(item.retention * 100)
            return (
              <Card
                key={`${item.knowledge_id}-${item.created_at || item.days_since_review}`}
                size="small"
                style={{
                  borderLeft: `3px solid ${meta.color}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text strong>{getKnowledgeLabel(item.knowledge_id)}</Text>
                  <Badge status={meta.progress as 'exception' | 'active' | 'success'} text={item.urgency} />
                </div>
                <Progress
                  percent={percent}
                  size="small"
                  status={percent < 30 ? 'exception' : percent < 70 ? 'active' : 'success'}
                  format={() => `${percent}% 记忆`}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  上次复习: {item.days_since_review.toFixed(1)} 天前
                </Text>
                {onStartReview && (
                  <Button
                    type="link"
                    size="small"
                    onClick={() => onStartReview(item.knowledge_id)}
                    style={{ padding: 0, marginTop: 4 }}
                  >
                    立即复习
                  </Button>
                )}
              </Card>
            )
          })}

          {dueItems.length > 0 && (
            <Card size="small" title="待复习项目" style={{ background: '#f8fafc' }}>
              <List
                size="small"
                dataSource={dueItems.slice(0, 3)}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button
                        key="review"
                        type="link"
                        size="small"
                        onClick={() => onStartReview?.(item.knowledge_id)}
                      >
                        复习
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      title={getKnowledgeLabel(item.knowledge_id)}
                      description={
                        item.overdue_days > 0
                          ? `逾期 ${item.overdue_days} 天`
                          : `下次: ${new Date(item.next_review).toLocaleDateString()}`
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Space>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ReviewReminder.tsx
git commit -m "feat: rewrite ReviewReminder with Ant Design"
```

---

### Task 9: 重写 AnalyticsDashboard 组件

**Files:**
- Rewrite: `frontend/src/components/AnalyticsDashboard.tsx`

- [ ] **Step 1: 重写 AnalyticsDashboard 组件**

```tsx
// frontend/src/components/AnalyticsDashboard.tsx
import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Typography, Progress, List, Tag, Spin, Alert } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  BulbOutlined,
  TrophyOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

interface AnalyticsPayload {
  analytics: {
    learner_id: string
    total_sessions: number
    total_time_spent_minutes: number
    total_questions: number
    correct_answers: number
    wrong_answers: number
    accuracy: number
    hints_used: number
    knowledge_points_covered: string[]
    avg_time_per_question: number
    last_activity: string | null
  }
  knowledge_distribution: Record<string, number>
  weak_points: Array<{
    knowledge_id: string
    mastery: number
    attempts: number
    correct_count: number
    accuracy: number
  }>
  learning_curve: Array<{
    timestamp: string
    type: string
    knowledge_id?: string
    is_correct?: boolean
  }>
}

function formatDateTime(value: string | null): string {
  if (!value) return '暂无活动'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export default function AnalyticsDashboard({ learnerId }: { learnerId: string }) {
  const [data, setData] = useState<AnalyticsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function fetchAnalytics() {
      try {
        setLoading(true)
        const response = await fetch(`/api/analytics/${learnerId}`)
        if (!response.ok) {
          throw new Error(`Analytics request failed with ${response.status}`)
        }
        const payload = (await response.json()) as AnalyticsPayload
        if (mounted) {
          setData(payload)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown analytics error')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    void fetchAnalytics()
    return () => {
      mounted = false
    }
  }, [learnerId])

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 100, textAlign: 'center' }} />
  }

  if (error) {
    return <Alert type="error" message={error} showIcon />
  }

  if (!data) {
    return <Alert type="info" message="暂无分析数据" />
  }

  const stats = data.analytics
  const distribution = data.knowledge_distribution || {}

  return (
    <div style={{ padding: '0 24px' }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        学习数据分析
      </Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="总题数"
              value={stats.total_questions}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#2563eb' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="正确率"
              value={Math.round(stats.accuracy * 100)}
              suffix="%"
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#059669' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="学习时长"
              value={stats.total_time_spent_minutes}
              suffix="分钟"
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#d97706' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="使用提示数"
              value={stats.hints_used}
              prefix={<BulbOutlined />}
              valueStyle={{ color: '#7c3aed' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* 知识点分布 */}
        <Col xs={24} lg={12}>
          <Card title="知识点掌握分布" style={{ height: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              {Object.entries(distribution).map(([level, count]) => {
                const labels: Record<string, { text: string; color: string }> = {
                  mastered: { text: '已掌握', color: '#16a34a' },
                  proficient: { text: '熟练', color: '#65a30d' },
                  developing: { text: '发展中', color: '#f59e0b' },
                  beginner: { text: '初学', color: '#ef4444' },
                  not_started: { text: '未开始', color: '#94a3b8' },
                }
                const info = labels[level] || { text: level, color: '#94a3b8' }
                return (
                  <div key={level}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text>{info.text}</Text>
                      <Text strong>{count}</Text>
                    </div>
                    <Progress
                      percent={stats.total_questions > 0 ? (count / stats.total_questions) * 100 : 0}
                      strokeColor={info.color}
                      size="small"
                      showInfo={false}
                    />
                  </div>
                )
              })}
            </Space>
            <div style={{ marginTop: 16 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                已覆盖知识点: {stats.knowledge_points_covered.length} |
                平均用时: {stats.avg_time_per_question} 秒/题 |
                最近活动: {formatDateTime(stats.last_activity)}
              </Text>
            </div>
          </Card>
        </Col>

        {/* 薄弱知识点 */}
        <Col xs={24} lg={12}>
          <Card title="薄弱知识点" style={{ height: '100%' }}>
            {data.weak_points.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
                暂未发现薄弱知识点
              </div>
            ) : (
              <List
                dataSource={data.weak_points}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={item.knowledge_id}
                      description={
                        <Space>
                          <Tag color="orange">正确率 {Math.round(item.accuracy * 100)}%</Tag>
                          <Text type="secondary">
                            掌握度 {Math.round(item.mastery * 100)}% | 答题 {item.attempts} 次 | 正确 {item.correct_count} 次
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 学习曲线 */}
      <Card title="最近学习曲线" style={{ marginTop: 16 }}>
        {data.learning_curve.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
            暂无学习记录
          </div>
        ) : (
          <List
            dataSource={data.learning_curve.slice(-10)}
            renderItem={(point) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <span>{point.knowledge_id || '通用'} · {point.type}</span>
                      {point.is_correct !== undefined && (
                        <Tag color={point.is_correct ? 'success' : 'error'}>
                          {point.is_correct ? '正确' : '错误'}
                        </Tag>
                      )}
                    </Space>
                  }
                  description={formatDateTime(point.timestamp)}
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AnalyticsDashboard.tsx
git commit -m "feat: rewrite AnalyticsDashboard with Ant Design and Chinese"
```

---

### Task 10: 重构 App.tsx 主布局

**Files:**
- Rewrite: `frontend/src/App.tsx`

- [ ] **Step 1: 重写 App.tsx 主布局**

```tsx
// frontend/src/App.tsx
import { useState } from 'react'
import { Layout, Row, Col } from 'antd'
import AppHeader from './components/Header'
import KnowledgeSelect from './components/KnowledgeSelect'
import QuizPanel from './components/QuizPanel'
import QuestionInput from './components/QuestionInput'
import FeedbackPanel from './components/FeedbackPanel'
import ReviewReminder from './components/ReviewReminder'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import { AgentEvent, useWebSocket } from './hooks/useWebSocket'
import type { Quiz, InteractionResult } from './types'

const { Content } = Layout

export default function App() {
  const [learnerId] = useState('student_001')
  const { connected, eventGroups, appendInteraction } = useWebSocket(learnerId)
  const [knowledgeId, setKnowledgeId] = useState('vocab_basic')
  const [message, setMessage] = useState('')
  const [activeTab, setActiveTab] = useState<'learning' | 'analytics'>('learning')
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [quizLoading, setQuizLoading] = useState(false)
  const [latestInteraction, setLatestInteraction] = useState<InteractionResult | null>(null)
  const [score, setScore] = useState({ correct: 0, total: 0 })
  const [quizStartedAt, setQuizStartedAt] = useState<number | null>(null)

  async function handleInitDemo() {
    await fetch(`/api/demo/init?learner_id=${learnerId}`, { method: 'POST' })
    window.location.reload()
  }

  async function handleGenerateQuiz(overrideKnowledgeId?: string) {
    const kid = overrideKnowledgeId || knowledgeId
    setQuizLoading(true)
    setSelectedOption(null)
    setLatestInteraction(null)
    try {
      const response = await fetch('/api/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_id: kid, difficulty: 0.5 }),
      })
      const data = (await response.json()) as { quiz?: Quiz }
      setQuiz(data.quiz || null)
      setQuizStartedAt(Date.now())
    } finally {
      setQuizLoading(false)
    }
  }

  function handleStartReview(knowledgeId: string) {
    setKnowledgeId(knowledgeId)
    void handleGenerateQuiz(knowledgeId)
  }

  async function handleSubmitQuiz() {
    if (!quiz || selectedOption === null) return

    const timeSpentSeconds = quizStartedAt ? Math.max(1, Math.round((Date.now() - quizStartedAt) / 1000)) : 1
    const response = await fetch('/api/quiz/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        learner_id: learnerId,
        knowledge_id: knowledgeId,
        question: quiz.question,
        student_answer: quiz.options[selectedOption],
        correct_answer: quiz.options[quiz.correct_index],
        explanation: quiz.explanation,
        time_spent_seconds: timeSpentSeconds,
      }),
    })
    const data = (await response.json()) as InteractionResult & { interaction_events?: AgentEvent[] }
    setLatestInteraction(data)
    appendInteraction(data.interaction_events || [])

    const quality = data.evaluation?.is_correct ? 4 : 1
    void fetch(
      `/api/review/complete?learner_id=${learnerId}&knowledge_id=${knowledgeId}&quality=${quality}`,
      { method: 'POST' },
    )

    setScore((previous) => ({
      correct: previous.correct + (data.evaluation?.is_correct ? 1 : 0),
      total: previous.total + 1,
    }))
  }

  async function handleQuestion() {
    if (!message.trim()) return
    const response = await fetch('/api/question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        learner_id: learnerId,
        knowledge_id: knowledgeId,
        question: message.trim(),
      }),
    })
    const data = (await response.json()) as InteractionResult & { interaction_events?: AgentEvent[] }
    setLatestInteraction(data)
    appendInteraction(data.interaction_events || [])
    setMessage('')
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <AppHeader
        activeTab={activeTab}
        onTabChange={setActiveTab}
        connected={connected}
        learnerId={learnerId}
        score={score}
        onInitDemo={handleInitDemo}
      />

      <Content style={{ padding: '24px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        {activeTab === 'learning' ? (
          <Row gutter={24}>
            {/* 左侧主区域 65% */}
            <Col xs={24} lg={16}>
              <KnowledgeSelect value={knowledgeId} onChange={setKnowledgeId} />
              <QuizPanel
                quiz={quiz}
                loading={quizLoading}
                selectedOption={selectedOption}
                onSelectOption={setSelectedOption}
                onGenerateQuiz={() => void handleGenerateQuiz()}
                onSubmitQuiz={() => void handleSubmitQuiz()}
              />
              <QuestionInput
                message={message}
                onMessageChange={setMessage}
                onSubmit={() => void handleQuestion()}
              />
            </Col>

            {/* 右侧辅助区域 35% */}
            <Col xs={24} lg={8}>
              <ReviewReminder learnerId={learnerId} onStartReview={handleStartReview} />
              <FeedbackPanel interaction={latestInteraction} quiz={quiz} />
            </Col>
          </Row>
        ) : (
          <AnalyticsDashboard learnerId={learnerId} />
        )}
      </Content>
    </Layout>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: refactor App.tsx with Ant Design main layout"
```

---

### Task 11: 添加统计数据 API 端点

**Files:**
- Modify: `python/api/routes.py`

- [ ] **Step 1: 添加 statistics 端点**

在 `python/api/routes.py` 文件末尾添加：

```python
@router.get("/statistics/{learner_id}")
async def get_statistics(learner_id: str, request: Request):
    """获取学习统计数据（聚合自 learning_records 表）。"""
    from models.database import LearningRecord
    from models.session import async_session
    from sqlalchemy import func, select

    async with async_session() as session:
        # 总题数
        total_questions = await session.scalar(
            select(func.count(LearningRecord.id))
            .where(LearningRecord.learner_id == learner_id)
        )

        # 正确题数
        correct_answers = await session.scalar(
            select(func.count(LearningRecord.id))
            .where(LearningRecord.learner_id == learner_id)
            .where(LearningRecord.is_correct == True)
        )

        # 总用时（秒）
        total_time = await session.scalar(
            select(func.sum(LearningRecord.time_spent_seconds))
            .where(LearningRecord.learner_id == learner_id)
        )

        # 平均用时
        avg_time = await session.scalar(
            select(func.avg(LearningRecord.time_spent_seconds))
            .where(LearningRecord.learner_id == learner_id)
        )

        # 最后活动时间
        last_record = await session.execute(
            select(LearningRecord.created_at)
            .where(LearningRecord.learner_id == learner_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(1)
        )
        last_activity = last_record.scalar_one_or_none()

    total_q = total_questions or 0
    correct_a = correct_answers or 0
    total_t = total_time or 0
    avg_t = avg_time or 0

    return {
        "total_questions": total_q,
        "correct_answers": correct_a,
        "wrong_answers": total_q - correct_a,
        "accuracy": round(correct_a / total_q, 3) if total_q > 0 else 0.0,
        "total_time_minutes": round(total_t / 60, 1),
        "avg_time_per_question": round(avg_t, 1),
        "last_activity": last_activity.isoformat() if last_activity else None,
    }
```

- [ ] **Step 2: Commit**

```bash
git add python/api/routes.py
git commit -m "feat: add statistics API endpoint"
```

---

### Task 12: 测试前端构建

**Files:**
- None (verification step)

- [ ] **Step 1: 运行 TypeScript 编译检查**

```bash
cd e:/5.study/5.project/eduagent/frontend && npx tsc --noEmit
```

Expected: 无错误输出

- [ ] **Step 2: 运行 Vite 构建**

```bash
cd e:/5.study/5.project/eduagent/frontend && npm run build
```

Expected: 构建成功，无错误

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: resolve TypeScript compilation issues"
```

---

## 不在范围内

- 题库持久化（保持 LLM 动态生成）
- 新增数据库表（使用已有表 + 聚合查询）
- 移动端适配（本次聚焦桌面端一屏展示）
- 用户认证系统（保持当前简单模式）
- 单元测试（后续可补充）
