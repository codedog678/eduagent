import { useEffect, useState } from 'react'

interface ReminderItem {
  knowledge_id: string
  retention: number
  days_since_review: number
  urgency: 'urgent' | 'high' | 'medium' | 'low'
  created_at?: string
}

interface DueItem {
  knowledge_id: string
  next_review: string
  overdue_days: number
}

interface ForgettingStatusItem {
  knowledge_id: string
  retention: number
  days_since_review: number
  is_due: boolean
  next_review: string
}

interface ReviewSchedule {
  reminders: ReminderItem[]
  due_items: DueItem[]
  forgetting_status: ForgettingStatusItem[]
  total_items: number
}

const KNOWLEDGE_LABELS: Record<string, string> = {
  vocab_basic: 'Basic Vocabulary',
  vocab_intermediate: 'Intermediate Vocabulary',
  vocab_advanced: 'Advanced Vocabulary',
  vocab_academic: 'Academic Vocabulary',
  grammar_tenses: 'Tenses',
  grammar_passive: 'Passive Voice',
  grammar_conditionals: 'Conditionals',
  grammar_relative: 'Relative Clauses',
  reading_skimming: 'Skimming',
  reading_scanning: 'Scanning',
  reading_inference: 'Inference',
  reading_main_idea: 'Main Idea',
  writing_paragraph: 'Paragraph Writing',
  writing_email: 'Email Writing',
  writing_essay: 'Essay Writing',
  writing_summary: 'Summary Writing',
}

const URGENCY_META: Record<ReminderItem['urgency'], { label: string; color: string; background: string }> = {
  urgent: { label: 'Urgent', color: '#b91c1c', background: '#fef2f2' },
  high: { label: 'High', color: '#c2410c', background: '#fff7ed' },
  medium: { label: 'Medium', color: '#a16207', background: '#fefce8' },
  low: { label: 'Low', color: '#166534', background: '#f0fdf4' },
}

function knowledgeLabel(knowledgeId: string): string {
  return KNOWLEDGE_LABELS[knowledgeId] || knowledgeId
}

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function RetentionMeter({ retention }: { retention: number }) {
  const percent = Math.max(0, Math.min(100, Math.round(retention * 100)))
  const color = percent < 30 ? '#dc2626' : percent < 50 ? '#ea580c' : percent < 70 ? '#ca8a04' : '#16a34a'

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <div
        style={{
          width: '100%',
          height: 8,
          borderRadius: 999,
          background: '#e2e8f0',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: '100%',
            background: color,
            transition: 'width 0.25s ease',
          }}
        />
      </div>
      <div style={{ color, fontSize: 12, fontWeight: 700 }}>{percent}% retained</div>
    </div>
  )
}

export default function ReviewReminder({ learnerId }: { learnerId: string }) {
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

  if (loading) {
    return (
      <div
        style={{
          minWidth: 280,
          padding: 16,
          borderRadius: 18,
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          color: '#64748b',
          fontSize: 14,
        }}
      >
        Loading review signals...
      </div>
    )
  }

  const reminders = schedule?.reminders || []
  const dueItems = schedule?.due_items || []
  const topStatus = schedule?.forgetting_status?.slice(0, 3) || []
  const urgentCount = reminders.filter((item) => item.urgency === 'urgent' || item.urgency === 'high').length

  return (
    <div
      style={{
        minWidth: 300,
        maxWidth: 360,
        padding: 16,
        borderRadius: 18,
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        boxShadow: '0 14px 30px rgba(15, 23, 42, 0.06)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 12 }}>
        <div>
          <div style={{ color: '#0f172a', fontSize: 16, fontWeight: 700 }}>Review Queue</div>
          <div style={{ color: '#64748b', fontSize: 12 }}>
            {schedule?.total_items || 0} tracked item{schedule?.total_items === 1 ? '' : 's'}
          </div>
        </div>
        <div
          style={{
            alignSelf: 'flex-start',
            padding: '6px 10px',
            borderRadius: 999,
            background: urgentCount > 0 ? '#fee2e2' : '#dcfce7',
            color: urgentCount > 0 ? '#991b1b' : '#166534',
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {urgentCount > 0 ? `${urgentCount} urgent` : 'On track'}
        </div>
      </div>

      {reminders.length === 0 && dueItems.length === 0 ? (
        <div
          style={{
            padding: 14,
            borderRadius: 14,
            background: '#f8fafc',
            color: '#64748b',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          Review timing will appear here after quiz attempts start updating spaced repetition data.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {reminders.slice(0, 3).map((item) => {
            const meta = URGENCY_META[item.urgency]
            return (
              <div
                key={`${item.knowledge_id}-${item.created_at || item.days_since_review}`}
                style={{
                  padding: 12,
                  borderRadius: 14,
                  background: meta.background,
                  border: `1px solid ${meta.color}22`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
                  <div style={{ color: '#0f172a', fontSize: 14, fontWeight: 700 }}>
                    {knowledgeLabel(item.knowledge_id)}
                  </div>
                  <div
                    style={{
                      padding: '2px 8px',
                      borderRadius: 999,
                      background: meta.color,
                      color: '#ffffff',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {meta.label}
                  </div>
                </div>
                <RetentionMeter retention={item.retention} />
                <div style={{ marginTop: 8, color: '#475569', fontSize: 12 }}>
                  Last reviewed {item.days_since_review.toFixed(1)} day(s) ago
                </div>
              </div>
            )
          })}

          {dueItems.length > 0 && (
            <div
              style={{
                padding: 12,
                borderRadius: 14,
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
              }}
            >
              <div style={{ color: '#0f172a', fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                Next due items
              </div>
              <div style={{ display: 'grid', gap: 6 }}>
                {dueItems.slice(0, 3).map((item) => (
                  <div
                    key={`${item.knowledge_id}-${item.next_review}`}
                    style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 12 }}
                  >
                    <span style={{ color: '#334155' }}>{knowledgeLabel(item.knowledge_id)}</span>
                    <span style={{ color: '#64748b' }}>
                      {item.overdue_days > 0 ? `${item.overdue_days} day(s) overdue` : formatDateTime(item.next_review)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {topStatus.length > 0 && (
            <div
              style={{
                padding: 12,
                borderRadius: 14,
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
              }}
            >
              <div style={{ color: '#0f172a', fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                Memory risk snapshot
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {topStatus.map((item) => (
                  <div key={`${item.knowledge_id}-${item.next_review}`}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 4 }}>
                      <span style={{ color: '#1e3a8a', fontSize: 12 }}>{knowledgeLabel(item.knowledge_id)}</span>
                      <span style={{ color: '#475569', fontSize: 12 }}>
                        {item.is_due ? 'Due now' : formatDateTime(item.next_review)}
                      </span>
                    </div>
                    <RetentionMeter retention={item.retention} />
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
