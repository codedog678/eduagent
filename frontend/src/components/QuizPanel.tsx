// frontend/src/components/QuizPanel.tsx
import { Alert, Card, Radio, Button, Typography, Space, Spin } from 'antd'
import { SendOutlined, ReloadOutlined } from '@ant-design/icons'
import type { Quiz } from '../types'

const { Text, Paragraph } = Typography

interface QuizPanelProps {
  quiz: Quiz | null
  loading: boolean
  selectedOption: number | null
  onSelectOption: (index: number) => void
  onGenerateQuiz: () => void
  onSubmitQuiz: () => void
  busy: boolean
  finished: boolean
  support: string
  confidence: number | null
  onConfidence: (value: number | null) => void
  onHint: () => void
  onReveal: () => void
}

export default function QuizPanel({
  quiz,
  loading,
  selectedOption,
  onSelectOption,
  onGenerateQuiz,
  onSubmitQuiz,
  busy, finished, support, confidence, onConfidence, onHint, onReveal,
}: QuizPanelProps) {
  return (
    <Card
      title={
        <Space>
          <span style={{ fontSize: 16, fontWeight: 600 }}>测验练习</span>
          <Text type="secondary" style={{ fontSize: 13 }}>
            先独立判断，再按需获取提示
          </Text>
        </Space>
      }
      extra={
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={onGenerateQuiz}
          loading={loading}
          disabled={busy}
        >
          {quiz ? '新测验' : '生成测验'}
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin tip="正在生成题目..." />
        </div>
      )}

      {!loading && !quiz && (
        <div style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>
          点击"生成测验"开始练习
        </div>
      )}

      {!loading && quiz && (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Card
            style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
            bodyStyle={{ padding: 16 }}
          >
            <Paragraph style={{ fontSize: 15, marginBottom: 0, lineHeight: 1.7 }}>
              {quiz.question}
            </Paragraph>
          </Card>

          <Radio.Group
            disabled={busy || finished}
            value={selectedOption}
            onChange={(e) => onSelectOption(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              {quiz.options.map((option, index) => (
                <Radio
                  key={index}
                  value={index}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    padding: '12px 16px',
                    borderRadius: 8,
                    border: `1px solid ${selectedOption === index ? '#2563eb' : '#e2e8f0'}`,
                    background: selectedOption === index ? '#eff6ff' : '#fff',
                    width: '100%',
                  }}
                >
                  <span style={{ marginTop: 2 }}>{option}</span>
                </Radio>
              ))}
            </Space>
          </Radio.Group>
          <Space wrap>
            <Text type="secondary">把握程度（可选）</Text>
            <Radio.Group value={confidence} disabled={busy || finished}
              onChange={(event) => onConfidence(event.target.value)}
              options={[{ label: '不确定', value: 0.25 }, { label: '较确定', value: 0.75 },
                { label: '很确定', value: 1 }]} />
          </Space>
          {support && <Alert type="info" message={support} />}
          <Space>
            <Button disabled={busy || finished} onClick={onHint}>给我一个提示</Button>
            <Button disabled={busy} onClick={onReveal}>查看答案与解析</Button>
          </Space>

          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSubmitQuiz}
            disabled={selectedOption === null || finished || busy}
            loading={busy}
            block
            size="large"
          >
            {finished ? '本题已完成，开始新题检验' : '提交 / 重试答案'}
          </Button>
        </Space>
      )}
    </Card>
  )
}
