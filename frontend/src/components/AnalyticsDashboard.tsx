import { useEffect, useState } from 'react'

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

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatDateTime(value: string | null): string {
  if (!value) return 'No activity yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent: string
}) {
  return (
    <div
      style={{
        padding: 18,
        borderRadius: 18,
        background: '#ffffff',
        border: `1px solid ${accent}33`,
        boxShadow: '0 16px 32px rgba(15, 23, 42, 0.06)',
      }}
    >
      <div style={{ color: '#64748b', fontSize: 12, marginBottom: 8 }}>{label}</div>
      <div style={{ color: '#0f172a', fontSize: 28, fontWeight: 800 }}>{value}</div>
    </div>
  )
}

function DistributionRow({
  label,
  count,
  total,
  color,
}: {
  label: string
  count: number
  total: number
  color: string
}) {
  const width = total > 0 ? (count / total) * 100 : 0

  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
        <span style={{ color: '#334155' }}>{label}</span>
        <span style={{ color: '#0f172a', fontWeight: 700 }}>{count}</span>
      </div>
      <div
        style={{
          width: '100%',
          height: 10,
          borderRadius: 999,
          background: '#e2e8f0',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${width}%`,
            height: '100%',
            background: color,
            transition: 'width 0.25s ease',
          }}
        />
      </div>
    </div>
  )
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
    return (
      <div style={{ padding: 24, color: '#64748b' }}>
        Loading analytics...
      </div>
    )
  }

  if (error) {
    return (
      <div
        style={{
          padding: 24,
          borderRadius: 18,
          background: '#fef2f2',
          border: '1px solid #fecaca',
          color: '#991b1b',
        }}
      >
        {error}
      </div>
    )
  }

  if (!data) {
    return (
      <div style={{ padding: 24, color: '#64748b' }}>
        No analytics available yet.
      </div>
    )
  }

  const distribution = data.knowledge_distribution || {}
  const totalTracked = Object.values(distribution).reduce((sum, count) => sum + count, 0)
  const stats = data.analytics

  return (
    <div style={{ display: 'grid', gap: 20 }}>
      <div
        style={{
          padding: 24,
          borderRadius: 22,
          background: 'linear-gradient(135deg, #ffffff 0%, #f8fbff 100%)',
          border: '1px solid #dbeafe',
          boxShadow: '0 18px 40px rgba(15, 23, 42, 0.08)',
        }}
      >
        <div style={{ marginBottom: 18 }}>
          <div style={{ color: '#1d4ed8', fontSize: 13, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            Progress Signals
          </div>
          <div style={{ color: '#0f172a', fontSize: 28, fontWeight: 800, marginTop: 6 }}>
            Real Usage Analytics
          </div>
          <div style={{ color: '#64748b', fontSize: 14, marginTop: 6 }}>
            The dashboard now uses backend-tracked progress and hides placeholder distributions.
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
          <StatCard label="Total Questions" value={stats.total_questions} accent="#2563eb" />
          <StatCard label="Accuracy" value={formatPercent(stats.accuracy)} accent="#059669" />
          <StatCard label="Study Time" value={`${stats.total_time_spent_minutes} min`} accent="#d97706" />
          <StatCard label="Hints Used" value={stats.hints_used} accent="#7c3aed" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <div
          style={{
            padding: 20,
            borderRadius: 20,
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            boxShadow: '0 16px 32px rgba(15, 23, 42, 0.06)',
          }}
        >
          <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700, marginBottom: 14 }}>
            Knowledge Distribution
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            <DistributionRow label="Mastered" count={distribution.mastered || 0} total={totalTracked} color="#16a34a" />
            <DistributionRow label="Proficient" count={distribution.proficient || 0} total={totalTracked} color="#65a30d" />
            <DistributionRow label="Developing" count={distribution.developing || 0} total={totalTracked} color="#f59e0b" />
            <DistributionRow label="Beginner" count={distribution.beginner || 0} total={totalTracked} color="#ef4444" />
            <DistributionRow label="Not Started" count={distribution.not_started || 0} total={totalTracked} color="#94a3b8" />
          </div>

          <div style={{ marginTop: 16, color: '#64748b', fontSize: 13, lineHeight: 1.6 }}>
            Covered knowledge points: {stats.knowledge_points_covered.length}
            <br />
            Average time per question: {stats.avg_time_per_question} second(s)
            <br />
            Last activity: {formatDateTime(stats.last_activity)}
          </div>
        </div>

        <div
          style={{
            padding: 20,
            borderRadius: 20,
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            boxShadow: '0 16px 32px rgba(15, 23, 42, 0.06)',
          }}
        >
          <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700, marginBottom: 14 }}>
            Weak Points
          </div>

          {data.weak_points.length === 0 ? (
            <div
              style={{
                padding: 16,
                borderRadius: 14,
                background: '#f8fafc',
                color: '#64748b',
              }}
            >
              No weak points identified yet.
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 10 }}>
              {data.weak_points.map((item) => (
                <div
                  key={item.knowledge_id}
                  style={{
                    padding: 14,
                    borderRadius: 14,
                    background: '#fff7ed',
                    border: '1px solid #fdba74',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                    <strong style={{ color: '#0f172a' }}>{item.knowledge_id}</strong>
                    <span style={{ color: '#9a3412', fontSize: 12 }}>
                      accuracy {formatPercent(item.accuracy)}
                    </span>
                  </div>
                  <div style={{ color: '#475569', fontSize: 13, lineHeight: 1.6 }}>
                    Mastery {formatPercent(item.mastery)} | Attempts {item.attempts} | Correct {item.correct_count}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div
        style={{
          padding: 20,
          borderRadius: 20,
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          boxShadow: '0 16px 32px rgba(15, 23, 42, 0.06)',
        }}
      >
        <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700, marginBottom: 14 }}>
          Recent Learning Curve
        </div>

        {data.learning_curve.length === 0 ? (
          <div
            style={{
              padding: 16,
              borderRadius: 14,
              background: '#f8fafc',
              color: '#64748b',
            }}
          >
            No recorded activity yet.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            {data.learning_curve.slice(-10).map((point) => (
              <div
                key={`${point.timestamp}-${point.knowledge_id || point.type}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  padding: 12,
                  borderRadius: 14,
                  background: point.is_correct === false ? '#fff7ed' : '#f8fafc',
                  border: '1px solid #e2e8f0',
                }}
              >
                <div>
                  <div style={{ color: '#0f172a', fontWeight: 700, fontSize: 14 }}>
                    {point.knowledge_id || 'General'} · {point.type}
                  </div>
                  <div style={{ color: '#64748b', fontSize: 12 }}>
                    {formatDateTime(point.timestamp)}
                  </div>
                </div>
                {point.is_correct !== undefined ? (
                  <div
                    style={{
                      alignSelf: 'center',
                      padding: '4px 10px',
                      borderRadius: 999,
                      background: point.is_correct ? '#dcfce7' : '#fee2e2',
                      color: point.is_correct ? '#166534' : '#991b1b',
                      fontSize: 12,
                      fontWeight: 700,
                    }}
                  >
                    {point.is_correct ? 'Correct' : 'Wrong'}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
