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
    await fetch(`/api/learner/init?learner_id=${learnerId}`, { method: 'POST' })
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
    const response = await fetch('/api/learner/question', {
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
