import { useEffect, useState } from 'react'
import { Alert, Button, Card, Collapse, Space, Tag, Typography } from 'antd'
import type { InteractionResult } from '../types'

interface HistoryMessage {
  source_ref: string
  session_id: string
  role: string
  content: string
}

interface Props {
  learnerId: string
  knowledgeId: string
  threadId?: string
  sessionId: string
  interaction: InteractionResult | null
  busy: boolean
  onNewSession: () => void
}

const STEP_LABELS: Record<string, string> = {
  run_started: '开始处理',
  commit_started: '准备保存互动',
  context_built: '整理学习历史',
  event_dispatched: '传递学习信息',
  handler_started: '开始协作',
  handler_completed: '完成协作',
  handler_failed: '协作未完成',
  before_model: '准备教学回复',
  after_model: '生成教学回复',
  model_fallback: '生成教学回复',
  before_tool: '准备查询',
  after_tool: '查询完成',
  run_completed: '保存互动结果',
  run_failed: '本次处理未完成',
}

const TOOL_LABELS: Record<string, string> = {
  search_learning_history: '查找相关历史',
  read_learning_history: '阅读历史证据',
  get_knowledge_context: '查询知识关系',
  get_quiz_context: '读取练习题',
  ask_student: '等待你的回答',
}

const STATUS_LABELS: Record<string, string> = {
  completed: '已完成', failed: '未完成', exhausted: '达到本轮限制',
  cancelled: '已取消', running: '处理中', ok: '已完成', denied: '未允许执行',
}

export default function TeachingHistory({
  learnerId, knowledgeId, threadId, sessionId, interaction, busy, onNewSession,
}: Props) {
  const [messages, setMessages] = useState<HistoryMessage[]>([])
  const [error, setError] = useState('')
  const [before, setBefore] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  const [trace, setTrace] = useState<Array<{ label: string; steps: Array<Record<string, unknown>> }>>([])

  useEffect(() => {
    const controller = new AbortController()
    const query = new URLSearchParams({ knowledge_id: knowledgeId })
    if (threadId) query.set('thread_id', threadId)
    setError('')
    setTrace([])
    void fetch(`/api/history/${encodeURIComponent(learnerId)}?${query}`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('教学历史读取失败')
        return response.json()
      }).then(data => {
        setMessages(data.items)
        setBefore(data.next_cursor)
        setPending(!!data.pending_question)
      }).catch(exc => {
        if (!controller.signal.aborted) setError(exc.message)
      })
    return () => controller.abort()
  }, [learnerId, knowledgeId, threadId, sessionId, interaction?.execution?.run_id])

  async function loadEarlier() {
    if (!before) return
    const query = new URLSearchParams({ knowledge_id: knowledgeId, before: String(before) })
    if (threadId) query.set('thread_id', threadId)
    try {
      const response = await fetch(`/api/history/${encodeURIComponent(learnerId)}?${query}`)
      if (!response.ok) throw new Error('更早历史读取失败')
      const data = await response.json()
      setMessages(previous => [...data.items, ...previous])
      setBefore(data.next_cursor)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : '历史读取失败')
    }
  }

  async function loadTrace() {
    const requestId = interaction?.execution?.request_id
    if (!requestId) return
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(learnerId)}/${encodeURIComponent(requestId)}/trace`)
      if (!response.ok) throw new Error('互动记录读取失败')
      const data = await response.json()
      setTrace(data.attempts.map((attempt: { status: string; steps: Array<Record<string, unknown>> }, i: number) => ({
        label: `第 ${i + 1} 次处理 · ${STATUS_LABELS[attempt.status] || '处理中'}`, steps: attempt.steps,
      })))
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : '互动记录读取失败')
    }
  }

  return (
    <Card title="教学对话" style={{ marginTop: 16 }}
      extra={<Button disabled={busy} onClick={onNewSession}>开始新会话</Button>}>
      {error && <Alert type="warning" title={error} style={{ marginBottom: 12 }} />}
      {(pending || interaction?.execution?.dialogue_state === 'awaiting_student') && (
        <Alert type="info" title="导师正在等待你的回答，可以在提问框继续回应。" style={{ marginBottom: 12 }} />
      )}
      <Space orientation="vertical" style={{ width: '100%' }}>
        {before && <Button onClick={() => void loadEarlier()}>查看更早对话</Button>}
        {!messages.length && <Typography.Text type="secondary">本知识点尚无教学对话。</Typography.Text>}
        {messages.map(message => (
          <div key={message.source_ref}>
            <Tag>{message.role === 'user' ? '你' : '导师'}</Tag>
            {message.session_id !== sessionId && <Tag>之前的会话</Tag>}
            <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
              {message.content}
            </Typography.Paragraph>
          </div>
        ))}
        {interaction?.assistance?.recorded && (
          <Typography.Text type="secondary">本题已使用教学帮助，后续作答会记录为受助练习。</Typography.Text>
        )}
        {interaction?.execution && <Button onClick={() => void loadTrace()}>查看本次互动记录</Button>}
        {!!trace.length && <Collapse items={trace.map((attempt, i) => ({
          key: String(i), label: attempt.label,
          children: <Space orientation="vertical">{attempt.steps.map((step, j) => (
            <Typography.Text key={j}>
              {STEP_LABELS[String(step.kind)] || '处理学习信息'}
              {step.tool ? ` · ${TOOL_LABELS[String(step.tool)] || '查询'}` : ''}
              {step.status ? ` · ${STATUS_LABELS[String(step.status)] || '处理中'}` : ''}
            </Typography.Text>
          ))}</Space>,
        }))} />}
      </Space>
    </Card>
  )
}
