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
