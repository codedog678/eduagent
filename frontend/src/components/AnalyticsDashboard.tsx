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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
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
            </div>
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
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <Tag color="orange">正确率 {Math.round(item.accuracy * 100)}%</Tag>
                          <Text type="secondary">
                            掌握度 {Math.round(item.mastery * 100)}% | 答题 {item.attempts} 次 | 正确 {item.correct_count} 次
                          </Text>
                        </div>
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
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span>{point.knowledge_id || '通用'} · {point.type}</span>
                      {point.is_correct !== undefined && (
                        <Tag color={point.is_correct ? 'success' : 'error'}>
                          {point.is_correct ? '正确' : '错误'}
                        </Tag>
                      )}
                    </div>
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
