import { useEffect, useState } from 'react'
import { Alert, Button, Descriptions, Empty, Select, Skeleton, Space, Table, Tabs, Tag, Timeline, Tooltip } from 'antd'
import type { TableColumnsType } from 'antd'
import { CheckCircle2, ChevronLeft, ChevronRight, CircleHelp, PauseCircle, RefreshCw, RotateCcw, ShieldCheck, XCircle } from 'lucide-react'
import { getPolicyAudit, getPolicyDeployment, getPolicyDeployments, getPolicyHealthWindows } from './api'
import type { AbortableRequest } from './api'
import type {
  OpsAuditEvent, OpsHealthStats, OpsHealthWindow, OpsPolicyDeployment, OpsPolicyDeploymentDetail,
  OpsPolicyPage, PolicyEnvironment, PolicyState,
} from './types'

interface Props {
  deploymentId?: string
  onRequestError: (error: unknown) => boolean
}
type Evidence = OpsPolicyDeployment | OpsHealthWindow | OpsAuditEvent
type EvidenceTab = 'deployments' | 'windows' | 'audit'
const STATES: PolicyState[] = ['registered', 'shadow', 'canary', 'active', 'frozen', 'rolled_back']

function date(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : '请求未完成，请重试'
}
function PolicyStatus({ value }: { value: string }) {
  const good = ['active', 'passed', 'pass'].includes(value)
  const bad = ['rolled_back', 'failed', 'fail', 'health_rollback'].includes(value)
  const held = ['frozen', 'hold'].includes(value)
  const Icon = good ? CheckCircle2 : bad ? XCircle : held ? PauseCircle : CircleHelp
  return (
    <Tooltip title={`只读状态：${value}`}>
      <Tag color={good ? 'success' : bad ? 'error' : held ? 'warning' : 'default'} className="ops-policy-status">
        <Icon size={13} aria-hidden="true" /> {value}
      </Tag>
    </Tooltip>
  )
}
function PolicyLink({ id }: { id: string }) {
  return <a href={`#/policies/${id}`} aria-label={`查看策略 ${id}`}><code className="ops-id">{id}</code></a>
}
function AuditTimeline({ items }: { items: OpsAuditEvent[] }) {
  return items.length ? (
    <Timeline
      items={items.map((item) => ({
        icon: <ShieldCheck size={14} aria-hidden="true" />,
        content: (
          <div className="ops-policy-audit">
            <strong>{item.event_type}</strong>
            {item.from_state && item.to_state && <span>{item.from_state} → {item.to_state}</span>}
            <span>{date(item.created_at)} · {item.environment}</span>
            {item.deployment_id && <PolicyLink id={item.deployment_id} />}
            {item.failed_deployment_id && <span>失败部署 <PolicyLink id={item.failed_deployment_id} /></span>}
            {item.health_window_id && <code className="ops-id">Window {item.health_window_id}</code>}
            <small>actor: {item.actor} · reason: {item.reason}</small>
          </div>
        ),
      }))}
    />
  ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无审计事件" />
}

export default function PoliciesView({ deploymentId, onRequestError }: Props) {
  const [tab, setTab] = useState<EvidenceTab>('deployments')
  const [environment, setEnvironment] = useState<PolicyEnvironment>()
  const [state, setState] = useState<PolicyState>()
  const [items, setItems] = useState<Evidence[]>([])
  const [loadedTab, setLoadedTab] = useState<EvidenceTab>('deployments')
  const [cursor, setCursor] = useState<string | null>(null)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [history, setHistory] = useState<Array<string | null>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let disposed = false
    const pending: AbortableRequest<OpsPolicyPage<Evidence>> = tab === 'deployments'
      ? getPolicyDeployments(cursor, { environment, state })
      : tab === 'windows' ? getPolicyHealthWindows(cursor, environment) : getPolicyAudit(cursor, environment)
    setLoading(true)
    setItems([])
    setNextCursor(null)
    setError('')
    pending.promise.then((page) => {
      if (disposed) return
      setLoadedTab(tab)
      setItems(page.items)
      setNextCursor(page.next_cursor)
    }).catch((reason: unknown) => {
      if (disposed || (reason instanceof DOMException && reason.name === 'AbortError')) return
      if (!onRequestError(reason)) setError(message(reason))
    }).finally(() => { if (!disposed) setLoading(false) })
    return () => { disposed = true; pending.abort() }
  }, [tab, environment, state, cursor, reload, onRequestError])

  function resetPaging() { setCursor(null); setHistory([]) }
  function resetSelection() { window.location.hash = '#/policies' }
  const deploymentColumns: TableColumnsType<OpsPolicyDeployment> = [
    { title: 'Deployment', width: 260, render: (_, item) => <PolicyLink id={item.deployment_id} /> },
    { title: '环境 / 版本', width: 140, render: (_, item) => <div className="ops-cell-stack"><span>{item.environment}</span><strong>版本 {item.version}</strong></div> },
    { title: '状态', width: 150, render: (_, item) => <PolicyStatus value={item.state} /> },
    { title: '当前部署', width: 160, render: (_, item) => <div className="ops-cell-stack"><Tag color={item.is_current ? 'success' : 'default'}>{item.is_current ? 'current' : 'historical'}</Tag><span>当前版本 {item.current_version ?? '未知'}</span></div> },
    { title: 'Stable / Candidate', width: 170, render: (_, item) => <div className="ops-cell-stack"><code className="ops-id">S {item.stable_policy_hash}</code><code className="ops-id">C {item.candidate_policy_hash ?? '不可用'}</code></div> },
    { title: 'Candidate 流量', width: 120, render: (_, item) => `${item.traffic_basis_points / 100}%` },
    { title: 'Cohort 运行数', width: 175, render: (_, item) => `S ${item.cohort_counts.stable} · C ${item.cohort_counts.candidate} · Shadow ${item.cohort_counts.shadow}` },
    { title: '创建时间', width: 170, render: (_, item) => date(item.created_at) },
  ]
  const windowColumns: TableColumnsType<OpsHealthWindow> = [
    { title: '部署', width: 260, render: (_, item) => <PolicyLink id={item.deployment_id} /> },
    { title: '环境 / 版本', width: 140, render: (_, item) => `${item.environment} · ${item.deployment_version ?? '未知'}` },
    { title: '健康决策', width: 120, render: (_, item) => <PolicyStatus value={item.decision} /> },
    { title: 'Candidate / Stable 运行数', width: 180, render: (_, item) => `${item.candidate_stats.run_count ?? '未知'} / ${item.stable_stats.run_count ?? '未知'}` },
    { title: '触发阈值', width: 240, render: (_, item) => item.triggered_thresholds.join(', ') || '无' },
    { title: '评估时间', width: 180, render: (_, item) => date(item.evaluated_at) },
  ]
  return (
    <section className="ops-panel" aria-label="Policies 只读证据">
      <div className="ops-toolbar">
        <Space wrap>
          <Select className="ops-filter" aria-label="策略环境" allowClear placeholder="全部环境" value={environment}
            options={['production', 'rehearsal'].map((value) => ({ value, label: value }))}
            onChange={(value) => { setEnvironment(value); resetPaging(); resetSelection() }} />
          {tab === 'deployments' && (
            <Select className="ops-filter" aria-label="策略状态" allowClear placeholder="全部状态" value={state}
              options={STATES.map((value) => ({ value, label: value }))}
              onChange={(value) => { setState(value); resetPaging(); resetSelection() }} />
          )}
          <Button icon={<RotateCcw size={15} />} onClick={() => {
            setEnvironment(undefined); setState(undefined); resetPaging(); resetSelection()
          }}>重置</Button>
        </Space>
        <Button icon={<RefreshCw size={15} />} onClick={() => setReload((value) => value + 1)}>刷新</Button>
      </div>
      <Tabs activeKey={tab} onChange={(value) => { setTab(value as EvidenceTab); resetPaging() }}
        items={[{ key: 'deployments', label: '部署' }, { key: 'windows', label: '健康窗口' }, { key: 'audit', label: '审计时间线' }]} />
      <section aria-label="策略证据列表">
        {error ? (
          <Alert type="error" showIcon title="策略证据加载失败" description={error}
            action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>} />
        ) : loading || loadedTab !== tab ? <Skeleton active paragraph={{ rows: 6 }} />
          : !items.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有符合条件的策略证据" />
            : tab === 'audit' ? <AuditTimeline items={items as OpsAuditEvent[]} />
              : tab === 'windows'
                ? <Table rowKey="window_id" size="small" dataSource={items as OpsHealthWindow[]} columns={windowColumns} pagination={false} scroll={{ x: 1120 }} />
                : <Table rowKey="deployment_id" size="small" dataSource={items as OpsPolicyDeployment[]} columns={deploymentColumns} pagination={false} scroll={{ x: 1345 }} />}
      </section>
      <div className="ops-pagination" aria-label="Policies 游标分页">
        <Button icon={<ChevronLeft size={15} />} disabled={!history.length || loading} onClick={() => {
          setCursor(history[history.length - 1]); setHistory((values) => values.slice(0, -1))
        }}>上一页</Button>
        <span>第 {history.length + 1} 页</span>
        <Button disabled={!nextCursor || loading} onClick={() => {
          setHistory((values) => [...values, cursor]); setCursor(nextCursor)
        }}>下一页 <ChevronRight size={15} /></Button>
      </div>
      {deploymentId && <PolicyDetail deploymentId={deploymentId} reload={reload} onRequestError={onRequestError} />}
    </section>
  )
}

function PolicyDetail({ deploymentId, reload, onRequestError }: Props & { deploymentId: string; reload: number }) {
  const [detail, setDetail] = useState<OpsPolicyDeploymentDetail | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let disposed = false
    setDetail(null); setError('')
    const pending = getPolicyDeployment(deploymentId)
    pending.promise.then((value) => { if (!disposed) setDetail(value) }).catch((reason: unknown) => {
      if (disposed || (reason instanceof DOMException && reason.name === 'AbortError')) return
      if (!onRequestError(reason)) setError(message(reason))
    })
    return () => { disposed = true; pending.abort() }
  }, [deploymentId, reload, retry, onRequestError])
  const window = detail?.latest_health_window
  return (
    <section className="ops-policy-detail ops-detail" aria-label="策略版本详情">
      <div className="ops-section-heading"><h3>策略版本详情</h3><a href="#/policies">关闭详情</a></div>
      {error ? <Alert type="error" showIcon title="策略详情加载失败" description={error}
        action={<Button onClick={() => setRetry((value) => value + 1)}>重试</Button>} />
        : !detail || detail.deployment_id !== deploymentId ? <Skeleton active paragraph={{ rows: 8 }} /> : (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="Deployment"><code className="ops-id">{detail.deployment_id}</code></Descriptions.Item>
              <Descriptions.Item label="环境 / 版本">{detail.environment} · 版本 {detail.version} <PolicyStatus value={detail.state} /></Descriptions.Item>
              <Descriptions.Item label="当前部署">
                {detail.current_deployment_id ? <PolicyLink id={detail.current_deployment_id} /> : '不可用'} · 当前版本 {detail.current_version ?? '未知'}
              </Descriptions.Item>
              <Descriptions.Item label="Stable hash"><code className="ops-id">{detail.stable_policy_hash}</code></Descriptions.Item>
              <Descriptions.Item label="Candidate hash"><code className="ops-id">{detail.candidate_policy_hash ?? '不可用'}</code></Descriptions.Item>
              <Descriptions.Item label="流量 / Cohort">{detail.traffic_basis_points / 100}% candidate · Stable {detail.cohort_counts.stable} / Candidate {detail.cohort_counts.candidate} / Shadow {detail.cohort_counts.shadow}</Descriptions.Item>
              <Descriptions.Item label="Actor / Reason">{detail.actor} / {detail.reason}</Descriptions.Item>
              <Descriptions.Item label="创建">{date(detail.created_at)}</Descriptions.Item>
            </Descriptions>
            <p className="ops-policy-note">Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。</p>
            <h3>冻结阈值</h3>
            <dl className="ops-policy-thresholds">
              {Object.entries(detail.thresholds).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}
            </dl>
            <h3>Gate Receipts</h3>
            {!detail.required_receipts.length && !detail.gate_receipts.length
              && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 Gate 收据" />}
            <div className="ops-tag-list">{detail.required_receipts.map((gate) => {
              const receipt = detail.gate_receipts.find((item) => item.gate_type === gate)
              return <Tooltip key={gate} title={receipt ? '最新绑定收据' : '未取得绑定收据'}><span>{gate} <PolicyStatus value={receipt?.status ?? 'unknown'} /></span></Tooltip>
            })}</div>
            {detail.gate_receipts.length > 0 && <Table rowKey="receipt_id" size="small" pagination={false} scroll={{ x: 760 }}
              dataSource={detail.gate_receipts} columns={[
                { title: 'Gate', dataIndex: 'gate_type', width: 180 },
                { title: '状态', dataIndex: 'status', width: 120, render: (value: string) => <PolicyStatus value={value} /> },
                { title: '样本', dataIndex: 'sample_count', width: 80 },
                { title: '成本 USD', dataIndex: 'cost', width: 90 },
                { title: 'Issuer', dataIndex: 'issuer', width: 100 },
                { title: '签发时间', dataIndex: 'issued_at', width: 180, render: date },
              ]} />}
            <h3>最新健康窗口</h3>
            {!window ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无健康窗口，指标不可用" /> : (
              <>
                <p><PolicyStatus value={window.decision} /> {date(window.evaluated_at)} · 指标协议 v{window.metric_contract_version}</p>
                <p className="ops-policy-note">触发阈值：{window.triggered_thresholds.join(', ') || '无'}。未知指标保持未知，不作为零值。</p>
                <HealthMetrics window={window} />
              </>
            )}
            <h3>回滚 / 冻结审计时间线</h3>
            <AuditTimeline items={detail.audit_events} />
            <p className="ops-policy-note">展示最近最多 100 条事件；完整分页证据见审计时间线页签。</p>
          </>
        )}
    </section>
  )
}

function HealthMetrics({ window }: { window: OpsHealthWindow }) {
  const metrics = Object.keys(window.candidate_stats) as Array<keyof OpsHealthStats>
  return <Table rowKey="metric" size="small" pagination={false} scroll={{ x: 560 }}
    dataSource={metrics.map((metric) => ({
      metric, candidate: window.candidate_stats[metric] ?? '未知', stable: window.stable_stats[metric] ?? '未知',
    }))}
    columns={[{ title: '指标', dataIndex: 'metric', width: 280 }, { title: 'Candidate', dataIndex: 'candidate', width: 140 }, { title: 'Stable', dataIndex: 'stable', width: 140 }]} />
}
