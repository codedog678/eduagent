// frontend/src/App.tsx
import { useRef, useState } from 'react'
import { Alert, Layout, Row, Col } from 'antd'
import AppHeader from './components/Header'
import KnowledgeSelect from './components/KnowledgeSelect'
import QuizPanel from './components/QuizPanel'
import QuestionInput from './components/QuestionInput'
import TeachingHistory from './components/TeachingHistory'
import FeedbackPanel from './components/FeedbackPanel'
import ReviewReminder from './components/ReviewReminder'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import { AgentEvent, useWebSocket } from './hooks/useWebSocket'
import type { Quiz, InteractionResult } from './types'

const { Content } = Layout

function readThreads(learnerId: string): Record<string, string> {
  try {
    const stored = JSON.parse(localStorage.getItem(`eduagent:threads:${learnerId}`) || '{}')
    return stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {}
  } catch { return {} }
}

export default function App() {
  const [learnerId] = useState('student_001')
  const [sessionId, setSessionId] = useState(() => {
    try {
      const id = sessionStorage.getItem(`eduagent:session:${learnerId}`) || crypto.randomUUID()
      sessionStorage.setItem(`eduagent:session:${learnerId}`, id)
      return id
    } catch { return crypto.randomUUID() }
  })
  const [threads, setThreads] = useState<Record<string, string>>(() => readThreads(learnerId))
  const { connected, appendInteraction } = useWebSocket(learnerId)
  const [knowledgeId, setKnowledgeId] = useState('vocab_basic')
  const [message, setMessage] = useState('')
  const [activeTab, setActiveTab] = useState<'learning' | 'analytics'>('learning')
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [quizLoading, setQuizLoading] = useState(false)
  const [latestInteraction, setLatestInteraction] = useState<InteractionResult | null>(null)
  const [score, setScore] = useState({ correct: 0, total: 0 })
  const [quizStartedAt, setQuizStartedAt] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [support, setSupport] = useState('')
  const [finished, setFinished] = useState(false)
  const [confidence, setConfidence] = useState<number | null>(null)
  const executing = useRef(false)

  function rememberThread(data: InteractionResult, kid: string) {
    if (!data.execution) return
    setThreads(previous => {
      const next = { ...previous, [kid]: data.execution!.thread_id }
      try { localStorage.setItem(`eduagent:threads:${learnerId}`, JSON.stringify(next)) } catch { /* 存储不可用时仍可对话 */ }
      return next
    })
  }

  function startNewSession() {
    if (busy || quizLoading) return
    const id = crypto.randomUUID()
    setSessionId(id)
    setLatestInteraction(null)
    setMessage('')
    try { sessionStorage.setItem(`eduagent:session:${learnerId}`, id) } catch { /* 内存会话仍有效 */ }
  }

  async function post(path: string, payload: Record<string, unknown>) {
    // 传输失败时复用同一 request_id 和内容，避免重复执行。
    const body = JSON.stringify({ ...payload, request_id: crypto.randomUUID() })
    let response: Response
    try {
      response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })
    } catch {
      response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })
    }
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请求未完成，请重试')
    return data
  }

  async function perform(action: () => Promise<void>) {
    if (executing.current) return
    executing.current = true
    setBusy(true)
    setError('')
    try { await action() } catch (exc) {
      setError(exc instanceof Error ? exc.message : '请求未完成，请重试')
    } finally {
      executing.current = false
      setBusy(false)
    }
  }

  async function handleInitDemo() {
    await perform(async () => {
      const response = await fetch(`/api/demo/init?learner_id=${learnerId}`, { method: 'POST' })
      if (!response.ok) throw new Error('初始化失败，请重试')
      window.location.reload()
    })
  }

  async function handleGenerateQuiz(overrideKnowledgeId?: string, mode = 'practice') {
    if (executing.current) return
    executing.current = true
    const kid = overrideKnowledgeId || knowledgeId
    setQuizLoading(true)
    setSelectedOption(null)
    setLatestInteraction(null)
    setQuiz(null)
    setSupport('')
    setFinished(false)
    setConfidence(null)
    setError('')
    try {
      const data = await post('/api/quiz/generate', {
        learner_id: learnerId, knowledge_id: kid, difficulty: 0.5, mode,
        session_id: sessionId, thread_id: threads[kid],
      })
      rememberThread(data, kid)
      setQuiz(data.quiz || null)
      setQuizStartedAt(Date.now())
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : '生成失败')
    } finally {
      executing.current = false
      setQuizLoading(false)
    }
  }

  function handleStartReview(knowledgeId: string) {
    if (busy || quizLoading) return
    setKnowledgeId(knowledgeId)
    void handleGenerateQuiz(knowledgeId)
  }

  function handleAdvanceToNextTopic(nextKnowledgeId: string) {
    if (!nextKnowledgeId || busy || quizLoading) return
    setKnowledgeId(nextKnowledgeId)
    setSelectedOption(null)
    setLatestInteraction(null)
    void handleGenerateQuiz(nextKnowledgeId, 'advance')
  }

  async function handleSubmitQuiz() {
    if (!quiz || selectedOption === null || finished) return

    const timeSpentSeconds = quizStartedAt ? Math.max(1, Math.round((Date.now() - quizStartedAt) / 1000)) : 1
    await perform(async () => {
      const data = await post('/api/quiz/answer', {
        learner_id: learnerId,
        quiz_id: quiz.quiz_id,
        selected_index: selectedOption,
        confidence,
        time_spent_seconds: timeSpentSeconds,
      }) as InteractionResult & { interaction_events?: AgentEvent[] }
      setLatestInteraction(data)
      appendInteraction(data.interaction_events || [])
      setFinished(!!data.evaluation?.is_correct)
      setSelectedOption(null)
      if (data.learning_evidence?.independent) setScore((previous) => ({
        correct: previous.correct + (data.evaluation?.is_correct ? 1 : 0),
        total: previous.total + 1,
      }))
    })
  }

  async function handleSupport(action: 'hint' | 'reveal') {
    if (!quiz || (finished && action !== 'reveal')) return
    await perform(async () => {
      const data = await post(`/api/quiz/${action}`, { learner_id: learnerId, quiz_id: quiz.quiz_id })
      setSupport(data.support.text)
      setFinished(data.support.finished)
    })
  }

  async function handleQuestion() {
    if (!message.trim()) return
    await perform(async () => {
      const data = await post('/api/question', {
        learner_id: learnerId,
        knowledge_id: quiz?.knowledge_id || knowledgeId,
        question: message.trim(),
        session_id: sessionId,
        thread_id: threads[quiz?.knowledge_id || knowledgeId],
        quiz_id: quiz && !finished ? quiz.quiz_id : undefined,
      }) as InteractionResult & { interaction_events?: AgentEvent[] }
      rememberThread(data, quiz?.knowledge_id || knowledgeId)
      setLatestInteraction(data)
      appendInteraction(data.interaction_events || [])
      setMessage('')
    })
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
        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}
        {activeTab === 'learning' ? (
          <Row gutter={24}>
            {/* 左侧主区域 65% */}
            <Col xs={24} lg={16}>
              <KnowledgeSelect value={knowledgeId} onChange={(value) => {
                if (busy || quizLoading) return
                setKnowledgeId(value)
                setQuiz(null)
                setLatestInteraction(null)
                setSupport('')
              }} />
              <QuizPanel
                quiz={quiz}
                loading={quizLoading}
                selectedOption={selectedOption}
                onSelectOption={setSelectedOption}
                onGenerateQuiz={() => void handleGenerateQuiz()}
                onSubmitQuiz={() => void handleSubmitQuiz()}
                busy={busy}
                finished={finished}
                support={support}
                confidence={confidence}
                onConfidence={setConfidence}
                onHint={() => void handleSupport('hint')}
                onReveal={() => void handleSupport('reveal')}
              />
              <QuestionInput
                message={message}
                onMessageChange={setMessage}
                onSubmit={() => void handleQuestion()}
              />
              <TeachingHistory
                learnerId={learnerId}
                knowledgeId={quiz?.knowledge_id || knowledgeId}
                threadId={threads[quiz?.knowledge_id || knowledgeId]}
                sessionId={sessionId}
                interaction={latestInteraction}
                busy={busy || quizLoading}
                onNewSession={startNewSession}
              />
            </Col>

            {/* 右侧辅助区域 35% */}
            <Col xs={24} lg={8}>
              <ReviewReminder learnerId={learnerId} onStartReview={handleStartReview} />
              <FeedbackPanel
                interaction={latestInteraction}
                quiz={quiz}
                onAdvanceToNextTopic={handleAdvanceToNextTopic}
              />
            </Col>
          </Row>
        ) : (
          <AnalyticsDashboard learnerId={learnerId} />
        )}
      </Content>
    </Layout>
  )
}
