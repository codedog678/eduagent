import { useEffect, useRef, useState } from 'react'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import ReviewReminder from './components/ReviewReminder'
import { AgentEvent, useWebSocket } from './hooks/useWebSocket'

const KNOWLEDGE_OPTIONS = [
  { value: 'vocab_basic', label: 'Basic Vocabulary' },
  { value: 'vocab_intermediate', label: 'Intermediate Vocabulary' },
  { value: 'vocab_advanced', label: 'Advanced Vocabulary' },
  { value: 'vocab_academic', label: 'Academic Vocabulary' },
  { value: 'grammar_tenses', label: 'Tenses' },
  { value: 'grammar_passive', label: 'Passive Voice' },
  { value: 'grammar_conditionals', label: 'Conditionals' },
  { value: 'grammar_relative', label: 'Relative Clauses' },
  { value: 'reading_skimming', label: 'Skimming' },
  { value: 'reading_scanning', label: 'Scanning' },
  { value: 'reading_inference', label: 'Inference' },
  { value: 'reading_main_idea', label: 'Main Idea' },
  { value: 'writing_paragraph', label: 'Paragraph Writing' },
  { value: 'writing_email', label: 'Email Writing' },
  { value: 'writing_essay', label: 'Essay Writing' },
  { value: 'writing_summary', label: 'Summary Writing' },
]

const AGENT_META: Record<string, { name: string; color: string }> = {
  AssessmentAgent: { name: 'Assessment', color: '#2563eb' },
  TutorAgent: { name: 'Tutor', color: '#059669' },
  CurriculumAgent: { name: 'Curriculum', color: '#d97706' },
  EngagementAgent: { name: 'Engagement', color: '#dc2626' },
  api: { name: 'System', color: '#64748b' },
}

const EVENT_LABELS: Record<string, string> = {
  'student.submission': 'Submission',
  'student.question': 'Question',
  'student.message': 'Message',
  'assessment.mastery_updated': 'Mastery Updated',
  'assessment.complete': 'Assessment Complete',
  'assessment.weakness_detected': 'Weakness Detected',
  'tutor.teaching_response': 'Teaching Response',
  'curriculum.next_topic': 'Next Topic',
  'curriculum.review_scheduled': 'Review Scheduled',
  'curriculum.review_reminder': 'Review Reminder',
  'engagement.alert': 'Engagement Alert',
  'engagement.encouragement': 'Encouragement',
  'engagement.pace_adjustment': 'Pace Adjustment',
}

interface Quiz {
  question: string
  options: string[]
  correct_index: number
  explanation: string
  source?: string
  difficulty?: number
}

interface TeachingResponse {
  response: string
  teaching_style: string
  context_type: string
  knowledge_id: string
  hint_level?: number | null
  hint_count?: number | null
}

interface ReviewSnapshot {
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

interface InteractionResult {
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
  review_snapshot?: ReviewSnapshot | null
  interaction_events?: AgentEvent[]
  events_triggered?: number
}

function getKnowledgeLabel(knowledgeId: string): string {
  return KNOWLEDGE_OPTIONS.find((item) => item.value === knowledgeId)?.label || knowledgeId
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'Not scheduled yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'N/A'
  return `${Math.round(value * 100)}%`
}

function urgencyLabel(value: string): string {
  const labels: Record<string, string> = {
    urgent: 'Urgent',
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  }
  return labels[value] || value
}

function eventSummary(event: AgentEvent): string {
  const data = event.data as Record<string, unknown>
  if (typeof data.response === 'string' && data.response) return data.response
  if (typeof data.feedback === 'string' && data.feedback) return data.feedback
  if (typeof data.message === 'string' && data.message) return data.message
  if (typeof data.reason === 'string' && data.reason) return data.reason
  if (data.mastery !== undefined) return `Mastery ${formatPercent(Number(data.mastery))}`
  if (typeof data.question === 'string' && data.question) return data.question
  return EVENT_LABELS[event.event_type] || event.event_type
}

function EventCard({ event }: { event: AgentEvent }) {
  const meta = AGENT_META[event.source] || { name: event.source, color: '#64748b' }

  return (
    <div
      style={{
        border: `1px solid ${meta.color}33`,
        background: '#ffffff',
        borderRadius: 14,
        padding: 14,
        boxShadow: '0 10px 24px rgba(15, 23, 42, 0.06)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: meta.color,
              flexShrink: 0,
            }}
          />
          <strong style={{ color: '#0f172a', fontSize: 13 }}>{meta.name}</strong>
        </div>
        <span style={{ color: '#64748b', fontSize: 12 }}>
          {EVENT_LABELS[event.event_type] || event.event_type}
        </span>
      </div>
      <div style={{ color: '#334155', fontSize: 14, lineHeight: 1.6 }}>{eventSummary(event)}</div>
    </div>
  )
}

function FeedbackPanel({
  interaction,
  quiz,
}: {
  interaction: InteractionResult | null
  quiz: Quiz | null
}) {
  if (!interaction) {
    return (
      <div
        style={{
          borderRadius: 18,
          border: '1px dashed #cbd5e1',
          padding: 24,
          background: '#f8fafc',
          color: '#64748b',
        }}
      >
        Start a quiz or ask a question to see one complete interaction here.
      </div>
    )
  }

  const evaluation = interaction.evaluation
  const teaching = interaction.teaching_response
  const review = interaction.review_snapshot
  const positive = evaluation?.is_correct ?? false

  return (
    <div
      style={{
        display: 'grid',
        gap: 14,
        borderRadius: 18,
        padding: 20,
        background: '#ffffff',
        border: '1px solid #dbeafe',
        boxShadow: '0 16px 36px rgba(37, 99, 235, 0.08)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
        <div>
          <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700 }}>Latest Interaction</div>
          <div style={{ color: '#64748b', fontSize: 13 }}>
            {getKnowledgeLabel(interaction.knowledge_id)}
          </div>
        </div>
        <div
          style={{
            padding: '6px 12px',
            borderRadius: 999,
            background: evaluation ? (positive ? '#dcfce7' : '#fee2e2') : '#e0f2fe',
            color: evaluation ? (positive ? '#166534' : '#991b1b') : '#0369a1',
            fontSize: 13,
            fontWeight: 700,
          }}
        >
          {evaluation ? (positive ? 'Correct' : 'Needs Review') : 'Conversation'}
        </div>
      </div>

      {evaluation && (
        <div
          style={{
            borderRadius: 14,
            padding: 16,
            background: positive ? '#f0fdf4' : '#fff7ed',
            border: `1px solid ${positive ? '#86efac' : '#fdba74'}`,
          }}
        >
          <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>Evaluation</div>
          <div style={{ color: '#334155', lineHeight: 1.6 }}>{evaluation.feedback}</div>
          {!positive && evaluation.correct_answer && (
            <div style={{ marginTop: 8, color: '#7c2d12', fontSize: 14 }}>
              Correct answer: {evaluation.correct_answer}
            </div>
          )}
          {!positive && quiz?.explanation && (
            <div style={{ marginTop: 8, color: '#475569', fontSize: 14 }}>
              Key idea: {quiz.explanation}
            </div>
          )}
        </div>
      )}

      {teaching && (
        <div
          style={{
            borderRadius: 14,
            padding: 16,
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
            <div style={{ fontWeight: 700, color: '#0f172a' }}>Tutor Response</div>
            <div style={{ color: '#1d4ed8', fontSize: 12, textTransform: 'capitalize' }}>
              {teaching.context_type.replace('_', ' ')}
            </div>
          </div>
          <div style={{ color: '#1e3a8a', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {teaching.response}
          </div>
          {teaching.hint_count ? (
            <div style={{ marginTop: 8, color: '#475569', fontSize: 13 }}>
              Hint level {teaching.hint_level || 1}, hint count {teaching.hint_count}
            </div>
          ) : null}
        </div>
      )}

      {review && (
        <div
          style={{
            borderRadius: 14,
            padding: 16,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 10 }}>Review Snapshot</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
            <div>
              <div style={{ color: '#64748b', fontSize: 12 }}>Next review</div>
              <div style={{ color: '#0f172a', fontSize: 14 }}>{formatDateTime(review.next_review)}</div>
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: 12 }}>Retention</div>
              <div style={{ color: '#0f172a', fontSize: 14 }}>{formatPercent(review.retention)}</div>
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: 12 }}>Urgency</div>
              <div style={{ color: '#0f172a', fontSize: 14 }}>{urgencyLabel(review.urgency)}</div>
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: 12 }}>Due now</div>
              <div style={{ color: '#0f172a', fontSize: 14 }}>{review.is_due ? 'Yes' : 'No'}</div>
            </div>
          </div>
          {review.top_due_items.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ color: '#64748b', fontSize: 12, marginBottom: 6 }}>Top due items</div>
              <div style={{ display: 'grid', gap: 6 }}>
                {review.top_due_items.slice(0, 3).map((item) => (
                  <div
                    key={`${item.knowledge_id}-${item.next_review}`}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '8px 10px',
                      borderRadius: 10,
                      background: '#ffffff',
                    }}
                  >
                    <span style={{ color: '#0f172a', fontSize: 13 }}>
                      {getKnowledgeLabel(item.knowledge_id)}
                    </span>
                    <span style={{ color: '#64748b', fontSize: 12 }}>
                      {item.overdue_days > 0 ? `${item.overdue_days}d overdue` : formatDateTime(item.next_review)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LearningInterface({
  learnerId,
  knowledgeId,
  setKnowledgeId,
  message,
  setMessage,
  quiz,
  quizLoading,
  selectedOption,
  setSelectedOption,
  latestInteraction,
  handleGenerateQuiz,
  handleSubmitQuiz,
  handleQuestion,
  eventGroups,
}: {
  learnerId: string
  knowledgeId: string
  setKnowledgeId: (value: string) => void
  message: string
  setMessage: (value: string) => void
  quiz: Quiz | null
  quizLoading: boolean
  selectedOption: number | null
  setSelectedOption: (value: number | null) => void
  latestInteraction: InteractionResult | null
  handleGenerateQuiz: () => Promise<void>
  handleSubmitQuiz: () => Promise<void>
  handleQuestion: () => Promise<void>
  eventGroups: AgentEvent[][]
}) {
  const feedRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [eventGroups])

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 24,
        alignItems: 'start',
      }}
    >
      <div style={{ display: 'grid', gap: 18 }}>
        <div
          style={{
            display: 'grid',
            gap: 16,
            padding: 20,
            borderRadius: 20,
            background: 'linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)',
            border: '1px solid #dbeafe',
            boxShadow: '0 18px 40px rgba(15, 23, 42, 0.08)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
            <div>
              <div style={{ color: '#0f172a', fontSize: 20, fontWeight: 700 }}>Learning Workspace</div>
              <div style={{ color: '#64748b', fontSize: 13 }}>Learner: {learnerId}</div>
            </div>
            <ReviewReminder learnerId={learnerId} />
          </div>

          <div>
            <label htmlFor="knowledge-select" style={{ display: 'block', color: '#334155', fontSize: 13, marginBottom: 6 }}>
              Knowledge point
            </label>
            <select
              id="knowledge-select"
              value={knowledgeId}
              onChange={(event) => setKnowledgeId(event.target.value)}
              style={{
                width: '100%',
                padding: '12px 14px',
                borderRadius: 12,
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#0f172a',
                fontSize: 14,
              }}
            >
              {KNOWLEDGE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div
            style={{
              display: 'grid',
              gap: 12,
              padding: 16,
              borderRadius: 16,
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
              <div>
                <div style={{ color: '#0f172a', fontSize: 17, fontWeight: 700 }}>Quiz Practice</div>
                <div style={{ color: '#64748b', fontSize: 13 }}>
                  Stable question bank first, tutor guidance after submission.
                </div>
              </div>
              <button
                onClick={() => {
                  void handleGenerateQuiz()
                }}
                disabled={quizLoading}
                style={{
                  padding: '10px 14px',
                  borderRadius: 12,
                  border: 'none',
                  background: quizLoading ? '#94a3b8' : '#2563eb',
                  color: '#ffffff',
                  cursor: quizLoading ? 'not-allowed' : 'pointer',
                  fontWeight: 700,
                }}
              >
                {quiz ? 'New Quiz' : 'Generate Quiz'}
              </button>
            </div>

            {quizLoading ? (
              <div style={{ color: '#475569', fontSize: 14 }}>Preparing a question...</div>
            ) : null}

            {quiz ? (
              <div style={{ display: 'grid', gap: 10 }}>
                <div
                  style={{
                    padding: 14,
                    borderRadius: 14,
                    background: '#ffffff',
                    color: '#0f172a',
                    lineHeight: 1.7,
                  }}
                >
                  {quiz.question}
                </div>

                {quiz.options.map((option, index) => (
                  <label
                    key={`${option}-${index}`}
                    style={{
                      display: 'flex',
                      gap: 10,
                      alignItems: 'flex-start',
                      padding: 12,
                      borderRadius: 14,
                      background: selectedOption === index ? '#dbeafe' : '#ffffff',
                      border: `1px solid ${selectedOption === index ? '#60a5fa' : '#dbeafe'}`,
                      cursor: 'pointer',
                    }}
                  >
                    <input
                      type="radio"
                      checked={selectedOption === index}
                      onChange={() => setSelectedOption(index)}
                      name="quiz-answer"
                      style={{ marginTop: 2 }}
                    />
                    <span style={{ color: '#0f172a', lineHeight: 1.5 }}>{option}</span>
                  </label>
                ))}

                <button
                  onClick={() => {
                    void handleSubmitQuiz()
                  }}
                  disabled={selectedOption === null}
                  style={{
                    padding: '12px 16px',
                    borderRadius: 12,
                    border: 'none',
                    background: selectedOption === null ? '#94a3b8' : '#059669',
                    color: '#ffffff',
                    cursor: selectedOption === null ? 'not-allowed' : 'pointer',
                    fontWeight: 700,
                  }}
                >
                  Submit Answer
                </button>
              </div>
            ) : null}
          </div>

          <div
            style={{
              display: 'grid',
              gap: 10,
              padding: 16,
              borderRadius: 16,
              background: '#fff7ed',
              border: '1px solid #fed7aa',
            }}
          >
            <div>
              <div style={{ color: '#0f172a', fontSize: 17, fontWeight: 700 }}>Ask the Tutor</div>
              <div style={{ color: '#64748b', fontSize: 13 }}>
                Questions stay separate from quiz grading and keep the current page context.
              </div>
            </div>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Ask about the current topic, a mistake you made, or what to review next."
              style={{
                width: '100%',
                minHeight: 96,
                padding: 12,
                borderRadius: 14,
                border: '1px solid #fdba74',
                resize: 'vertical',
                font: 'inherit',
                color: '#0f172a',
                background: '#ffffff',
              }}
            />
            <button
              onClick={() => {
                void handleQuestion()
              }}
              disabled={!message.trim()}
              style={{
                padding: '12px 16px',
                borderRadius: 12,
                border: 'none',
                background: message.trim() ? '#ea580c' : '#cbd5e1',
                color: '#ffffff',
                cursor: message.trim() ? 'pointer' : 'not-allowed',
                fontWeight: 700,
              }}
            >
              Send Question
            </button>
          </div>

          <FeedbackPanel interaction={latestInteraction} quiz={quiz} />
        </div>
      </div>

      <div style={{ display: 'grid', gap: 18 }}>
        <div
          style={{
            padding: 18,
            borderRadius: 20,
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            boxShadow: '0 18px 40px rgba(15, 23, 42, 0.06)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 14 }}>
            <div>
              <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700 }}>Interaction Feed</div>
              <div style={{ color: '#64748b', fontSize: 13 }}>
                One grouped batch per student action.
              </div>
            </div>
            <div
              style={{
                padding: '6px 10px',
                borderRadius: 999,
                background: '#ecfeff',
                color: '#0f766e',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {eventGroups.length} batches
            </div>
          </div>

          <div
            ref={feedRef}
            style={{
              display: 'grid',
              gap: 16,
              maxHeight: 860,
              overflowY: 'auto',
              paddingRight: 4,
            }}
          >
            {eventGroups.length === 0 ? (
              <div
                style={{
                  padding: 24,
                  borderRadius: 16,
                  background: '#f8fafc',
                  color: '#64748b',
                  textAlign: 'center',
                }}
              >
                The event feed will appear here after the first quiz or question.
              </div>
            ) : (
              eventGroups.map((group, index) => (
                <div
                  key={`${group[0]?.correlation_id || group[0]?.timestamp || index}`}
                  style={{
                    display: 'grid',
                    gap: 10,
                    padding: 14,
                    borderRadius: 18,
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ color: '#0f172a', fontSize: 14, fontWeight: 700 }}>
                      Batch {eventGroups.length - index}
                    </div>
                    <div style={{ color: '#64748b', fontSize: 12 }}>
                      {formatDateTime(group[0]?.timestamp)}
                    </div>
                  </div>
                  {group.map((event) => (
                    <EventCard
                      key={`${event.timestamp}-${event.source}-${event.event_type}`}
                      event={event}
                    />
                  ))}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

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

  async function handleGenerateQuiz() {
    setQuizLoading(true)
    setSelectedOption(null)
    setLatestInteraction(null)
    try {
      const response = await fetch('/api/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_id: knowledgeId, difficulty: 0.5 }),
      })
      const data = (await response.json()) as { quiz?: Quiz }
      setQuiz(data.quiz || null)
      setQuizStartedAt(Date.now())
    } finally {
      setQuizLoading(false)
    }
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
    <div
      style={{
        minHeight: '100vh',
        background:
          'radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 28%), linear-gradient(180deg, #f8fbff 0%, #eef4ff 48%, #f8fafc 100%)',
      }}
    >
      <div
        style={{
          maxWidth: 1320,
          margin: '0 auto',
          padding: '28px 20px 40px',
          fontFamily: '"Segoe UI", "Helvetica Neue", sans-serif',
          color: '#0f172a',
        }}
      >
        <header
          style={{
            display: 'grid',
            gap: 16,
            padding: 24,
            borderRadius: 24,
            background: 'linear-gradient(135deg, #0f172a 0%, #1d4ed8 62%, #38bdf8 100%)',
            color: '#ffffff',
            boxShadow: '0 22px 56px rgba(30, 64, 175, 0.22)',
            marginBottom: 24,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 14, letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.75 }}>
                Multi-Agent Learning Flow
              </div>
              <h1 style={{ margin: '8px 0 10px', fontSize: 34, lineHeight: 1.1 }}>
                Learn Like a Guided Session, Not a Raw Event Log
              </h1>
              <div style={{ color: 'rgba(255,255,255,0.84)', maxWidth: 760, lineHeight: 1.7 }}>
                Quiz feedback, tutor guidance, and review timing now arrive as one coherent interaction.
              </div>
            </div>

            <div style={{ display: 'grid', gap: 8, minWidth: 240 }}>
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 999,
                  background: connected ? 'rgba(16, 185, 129, 0.18)' : 'rgba(248, 113, 113, 0.2)',
                  color: '#ffffff',
                  fontSize: 13,
                  fontWeight: 700,
                  textAlign: 'center',
                }}
              >
                {connected ? 'WebSocket Connected' : 'WebSocket Reconnecting'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
                <span>Learner: {learnerId}</span>
                <span>
                  Score: {score.correct}/{score.total || 0}
                </span>
              </div>
              <button
                onClick={() => {
                  void handleInitDemo()
                }}
                style={{
                  padding: '10px 14px',
                  borderRadius: 12,
                  border: '1px solid rgba(255,255,255,0.24)',
                  background: 'rgba(255,255,255,0.12)',
                  color: '#ffffff',
                  cursor: 'pointer',
                  fontWeight: 700,
                }}
              >
                Seed Demo Data
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={() => setActiveTab('learning')}
              style={{
                padding: '10px 16px',
                borderRadius: 999,
                border: 'none',
                background: activeTab === 'learning' ? '#ffffff' : 'rgba(255,255,255,0.16)',
                color: activeTab === 'learning' ? '#1d4ed8' : '#ffffff',
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              Learning Flow
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              style={{
                padding: '10px 16px',
                borderRadius: 999,
                border: 'none',
                background: activeTab === 'analytics' ? '#ffffff' : 'rgba(255,255,255,0.16)',
                color: activeTab === 'analytics' ? '#1d4ed8' : '#ffffff',
                cursor: 'pointer',
                fontWeight: 700,
              }}
            >
              Analytics
            </button>
          </div>
        </header>

        {activeTab === 'learning' ? (
          <LearningInterface
            learnerId={learnerId}
            knowledgeId={knowledgeId}
            setKnowledgeId={setKnowledgeId}
            message={message}
            setMessage={setMessage}
            quiz={quiz}
            quizLoading={quizLoading}
            selectedOption={selectedOption}
            setSelectedOption={setSelectedOption}
            latestInteraction={latestInteraction}
            handleGenerateQuiz={handleGenerateQuiz}
            handleSubmitQuiz={handleSubmitQuiz}
            handleQuestion={handleQuestion}
            eventGroups={eventGroups}
          />
        ) : (
          <AnalyticsDashboard learnerId={learnerId} />
        )}
      </div>
    </div>
  )
}
