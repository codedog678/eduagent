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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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
                  <Badge status={meta.progress === 'exception' ? 'error' : meta.progress === 'active' ? 'warning' : 'success'} text={item.urgency} />
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
        </div>
      )}
    </Card>
  )
}
