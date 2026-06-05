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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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
      </div>
    </Card>
  )
}
