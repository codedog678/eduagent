// frontend/src/components/Header.tsx
import { Layout, Menu, Badge, Tag, Button, Space } from 'antd'
import {
  BookOutlined,
  BarChartOutlined,
  ReloadOutlined,
} from '@ant-design/icons'

const { Header } = Layout

interface HeaderProps {
  activeTab: 'learning' | 'analytics'
  onTabChange: (tab: 'learning' | 'analytics') => void
  connected: boolean
  learnerId: string
  score: { correct: number; total: number }
  onInitDemo: () => void
}

export default function AppHeader({
  activeTab,
  onTabChange,
  connected,
  learnerId,
  score,
  onInitDemo,
}: HeaderProps) {
  const menuItems = [
    {
      key: 'learning',
      icon: <BookOutlined />,
      label: '学习工作台',
    },
    {
      key: 'analytics',
      icon: <BarChartOutlined />,
      label: '数据分析',
    },
  ]

  return (
    <Header
      style={{
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#2563eb' }}>
          智能学习平台
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[activeTab]}
          items={menuItems}
          onClick={({ key }) => onTabChange(key as 'learning' | 'analytics')}
          style={{ border: 'none', background: 'transparent' }}
        />
      </div>

      <Space size="middle">
        <Badge
          status={connected ? 'success' : 'error'}
          text={connected ? '已连接' : '重连中'}
        />
        <Tag color="blue">学习者: {learnerId}</Tag>
        <Tag color="green">
          得分: {score.correct}/{score.total || 0}
        </Tag>
        <Button
          icon={<ReloadOutlined />}
          onClick={onInitDemo}
          size="small"
        >
          初始化数据
        </Button>
      </Space>
    </Header>
  )
}
