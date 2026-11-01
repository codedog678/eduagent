// frontend/src/components/KnowledgeSelect.tsx
import { Select, Typography } from 'antd'
import { KNOWLEDGE_OPTIONS } from '../types'

const { Text } = Typography

interface KnowledgeSelectProps {
  value: string
  onChange: (value: string) => void
}

export default function KnowledgeSelect({
  value,
  onChange,
}: KnowledgeSelectProps) {
  return (
    <div>
      <Text strong style={{ marginBottom: 8, display: 'block' }}>
        选择知识点
      </Text>
      <Select
        value={value}
        onChange={onChange}
        style={{ width: '100%' }}
        options={KNOWLEDGE_OPTIONS}
        placeholder="请选择要学习的知识点"
      />
    </div>
  )
}
