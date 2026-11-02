// frontend/src/components/QuestionInput.tsx
import { Card, Input, Button, Typography } from 'antd'
import { SendOutlined } from '@ant-design/icons'

const { Text } = Typography
const { TextArea } = Input

interface QuestionInputProps {
  message: string
  onMessageChange: (value: string) => void
  onSubmit: () => void
}

export default function QuestionInput({
  message,
  onMessageChange,
  onSubmit,
}: QuestionInputProps) {
  return (
    <Card
      title={
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>向导师提问</div>
          <Text type="secondary" style={{ fontSize: 13 }}>
            问题独立于测验评分，保留当前页面上下文
          </Text>
        </div>
      }
      style={{ background: '#fff7ed', border: '1px solid #fed7aa' }}
    >
      <TextArea
        value={message}
        onChange={(e) => onMessageChange(e.target.value)}
        placeholder="询问当前主题、你犯的错误、或接下来该复习什么..."
        autoSize={{ minRows: 3, maxRows: 6 }}
        style={{ marginBottom: 12 }}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={onSubmit}
        disabled={!message.trim()}
        block
        style={{ background: '#ea580c', borderColor: '#ea580c' }}
      >
        发送提问
      </Button>
    </Card>
  )
}
