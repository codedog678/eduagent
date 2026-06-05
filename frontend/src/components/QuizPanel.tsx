// frontend/src/components/QuizPanel.tsx
import { Card, Radio, Button, Typography, Space, Spin } from 'antd'
import { SendOutlined, ReloadOutlined } from '@ant-design/icons'
import type { Quiz } from '../types'

const { Title, Text, Paragraph } = Typography

interface QuizPanelProps {
  quiz: Quiz | null
  loading: boolean
  selectedOption: number | null
  onSelectOption: (index: number) => void
  onGenerateQuiz: () => void
  onSubmitQuiz: () => void
}

export default function QuizPanel({
  quiz,
  loading,
  selectedOption,
  onSelectOption,
  onGenerateQuiz,
  onSubmitQuiz,
}: QuizPanelProps) {
  return (
    <Card
      title={
        <Space>
          <span style={{ fontSize: 16, fontWeight: 600 }}>测验练习</span>
          <Text type="secondary" style={{ fontSize: 13 }}>
            题库动态生成，提交后获取导师指导
          </Text>
        </Space>
      }
      extra={
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={onGenerateQuiz}
          loading={loading}
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

          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSubmitQuiz}
            disabled={selectedOption === null}
            block
            size="large"
          >
            提交答案
          </Button>
        </Space>
      )}
    </Card>
  )
}
