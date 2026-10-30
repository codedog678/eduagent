import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Select,
  Skeleton,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import type { TableColumnsType } from 'antd'
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  RotateCcw,
} from 'lucide-react'
import { getExpertJob, getRun, getRuns } from './api'
import type {
  OpsExpertJobDetail,
  OpsExpertJobSummary,
  OpsRunDetail,
  OpsRunSummary,
} from './types'

interface RunsViewProps {
  onRequestError: (error: unknown) => boolean
}

const RUN_STATUSES = [
  'accepted', 'queued', 'leased', 'running', 'waiting_expert', 'committing',
  'retryable_failed', 'completed', 'terminal_failed', 'exhausted', 'cancelled',
]
const MIN_INITIAL_LOADING_MS = 300

function statusColor(status: string): string {
  if (status === 'completed' || status === 'accepted') return 'success'
  if (status === 'running' || status === 'leased' || status === 'committing') return 'processing'
  if (status === 'queued' || status === 'waiting_expert') return 'warning'
  if (status.includes('failed') || status === 'exhausted') return 'error'
  return 'default'
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds} ms`
  if (milliseconds < 60_000) return `${(milliseconds / 1000).toFixed(2)} s`
  return `${(milliseconds / 60_000).toFixed(1)} min`
}

function formatUsage(run: OpsRunSummary): string {
  const tokens = run.usage.input_tokens === null || run.usage.output_tokens === null
    ? 'token 未知'
    : `${run.usage.input_tokens + run.usage.output_tokens} tokens`
  return `${run.usage.model_calls} 模型 / ${run.usage.tool_calls} 工具 / ${tokens}`
}

function requestMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求未完成，请重试'
}

export default function RunsView({ onRequestError }: RunsViewProps) {
  const [items, setItems] = useState<OpsRunSummary[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [cursor, setCursor] = useState<string | null>(null)
  const [history, setHistory] = useState<Array<string | null>>([])
  const [status, setStatus] = useState<string>()
  const [operation, setOperation] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [selectedRun, setSelectedRun] = useState<string | null>(null)

  useEffect(() => {
    let disposed = false
    const startedAt = performance.now()
    const pending = getRuns(cursor, { status, operation })
    setLoading(true)
    setError('')
    pending.promise.then(async (page) => {
      const remaining = MIN_INITIAL_LOADING_MS - (performance.now() - startedAt)
      if (remaining > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, remaining))
      }
      if (disposed) return
      setItems(page.items)
      setNextCursor(page.next_cursor)
    }).catch((reason: unknown) => {
      if (disposed) return
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      if (!onRequestError(reason)) setError(requestMessage(reason))
    }).finally(() => {
      if (!disposed) setLoading(false)
    })
    return () => {
      disposed = true
      pending.abort()
    }
  }, [cursor, status, operation, reload, onRequestError])

  function resetPaging() {
    setCursor(null)
    setHistory([])
  }

  function nextPage() {
    if (!nextCursor) return
    setHistory((values) => [...values, cursor])
    setCursor(nextCursor)
  }

  function previousPage() {
    if (!history.length) return
    setCursor(history[history.length - 1])
    setHistory((values) => values.slice(0, -1))
  }

  const columns: TableColumnsType<OpsRunSummary> = [
    {
      title: 'Run ID',
      dataIndex: 'run_id',
      width: 240,
      render: (value: string) => <code className="ops-id">{value}</code>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 138,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
    { title: '操作', dataIndex: 'operation', width: 135 },
    {
      title: '租约',
      width: 160,
      render: (_, run) => (
        <div className="ops-cell-stack">
          <Tag color={run.lease_fresh ? 'success' : 'default'}>
            {run.lease_fresh ? 'fresh' : 'not fresh'}
          </Tag>
          <span>{run.owner || '无 owner'} · fence {run.fencing_token}</span>
        </div>
      ),
    },
    {
      title: '尝试 / 专家',
      width: 120,
      render: (_, run) => `${run.attempt_count} / ${run.expert_job_count}`,
    },
    {
      title: '用量',
      width: 220,
      render: (_, run) => (
        <Tooltip title={run.usage.uncertain ? '用量包含不确定估计' : undefined}>
          <span>{formatUsage(run)}{run.usage.uncertain ? ' *' : ''}</span>
        </Tooltip>
      ),
    },
    {
      title: '延迟',
      dataIndex: 'latency_ms',
      width: 100,
      align: 'right',
      render: (value: number) => formatDuration(value),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      render: (value: string) => formatDate(value),
    },
    {
      title: '',
      key: 'detail',
      width: 76,
      fixed: 'right',
      render: (_, run) => (
        <Button
          type="text"
          icon={<ExternalLink size={15} />}
          onClick={() => setSelectedRun(run.run_id)}
          aria-label={`查看运行 ${run.run_id} 详情`}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <section className="ops-panel" aria-label="运行列表">
      <div className="ops-toolbar">
        <Space wrap>
          <Select
            className="ops-filter"
            allowClear
            placeholder="全部状态"
            value={status}
            options={RUN_STATUSES.map((value) => ({ value, label: value }))}
            onChange={(value) => {
              setStatus(value)
              resetPaging()
            }}
          />
          <Select
            className="ops-filter"
            allowClear
            placeholder="全部操作"
            value={operation}
            options={[{ value: 'learning_task', label: 'learning_task' }]}
            onChange={(value) => {
              setOperation(value)
              resetPaging()
            }}
          />
          <Button
            icon={<RotateCcw size={15} />}
            onClick={() => {
              setStatus(undefined)
              setOperation(undefined)
              resetPaging()
            }}
          >
            重置
          </Button>
        </Space>
        <Button icon={<RefreshCw size={15} />} onClick={() => setReload((value) => value + 1)}>
          刷新
        </Button>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          title="Runs 加载失败"
          description={error}
          action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>}
        />
      ) : loading && !items.length ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : !items.length ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有符合条件的运行" />
      ) : (
        <Table
          rowKey="run_id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={false}
          scroll={{ x: 1370 }}
        />
      )}

      <div className="ops-pagination" aria-label="Runs 游标分页">
        <Button icon={<ChevronLeft size={15} />} disabled={!history.length || loading} onClick={previousPage}>
          上一页
        </Button>
        <span>第 {history.length + 1} 页</span>
        <Button disabled={!nextCursor || loading} onClick={nextPage}>
          下一页 <ChevronRight size={15} />
        </Button>
      </div>

      <RunDrawer
        runId={selectedRun}
        onClose={() => setSelectedRun(null)}
        onRequestError={onRequestError}
      />
    </section>
  )
}

interface RunDrawerProps extends RunsViewProps {
  runId: string | null
  onClose: () => void
}

function RunDrawer({ runId, onClose, onRequestError }: RunDrawerProps) {
  const [detail, setDetail] = useState<OpsRunDetail | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [jobId, setJobId] = useState<string | null>(null)

  useEffect(() => {
    setDetail(null)
    setError('')
    setJobId(null)
    if (!runId) return
    const pending = getRun(runId)
    pending.promise.then(setDetail).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      if (!onRequestError(reason)) setError(requestMessage(reason))
    })
    return pending.abort
  }, [runId, reload, onRequestError])

  const jobColumns: TableColumnsType<OpsExpertJobSummary> = [
    {
      title: 'Job ID',
      dataIndex: 'job_id',
      width: 220,
      render: (value: string) => <code className="ops-id">{value}</code>,
    },
    { title: '角色', dataIndex: 'role', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 145,
      render: (value: string) => <Tag color={statusColor(value)}>{value}</Tag>,
    },
    {
      title: '尝试',
      width: 85,
      render: (_, job) => `${job.attempt_count}/${job.max_attempts}`,
    },
    {
      title: '',
      width: 70,
      render: (_, job) => <Button type="link" onClick={() => setJobId(job.job_id)}>检查</Button>,
    },
  ]

  return (
    <Drawer
      title="运行详情"
      open={Boolean(runId)}
      onClose={onClose}
      size="min(760px, 100vw)"
      destroyOnHidden
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          title="详情加载失败"
          description={error}
          action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>}
        />
      ) : !detail ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <div className="ops-detail">
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="Run ID"><code className="ops-id">{detail.run_id}</code></Descriptions.Item>
            <Descriptions.Item label="Trace">
              <a href={`#/trace/${encodeURIComponent(detail.run_id)}`}><code className="ops-id">{detail.trace_id}</code></a>
            </Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColor(detail.status)}>{detail.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="Owner">{detail.owner || '—'}</Descriptions.Item>
            <Descriptions.Item label="Lease">{detail.lease_fresh ? 'fresh' : 'not fresh'} · fence {detail.fencing_token}</Descriptions.Item>
            <Descriptions.Item label="延迟">{formatDuration(detail.latency_ms)}</Descriptions.Item>
            <Descriptions.Item label="用量">{formatUsage(detail)}</Descriptions.Item>
            <Descriptions.Item label="创建">{formatDate(detail.created_at)}</Descriptions.Item>
            <Descriptions.Item label="更新">{formatDate(detail.updated_at)}</Descriptions.Item>
          </Descriptions>

          <h3>运行尝试</h3>
          {detail.attempts.length ? (
            <ol className="ops-attempt-list">
              {detail.attempts.map((attempt) => (
                <li key={attempt.number}>
                  <div><strong>#{attempt.number}</strong> <Tag color={statusColor(attempt.status)}>{attempt.status}</Tag></div>
                  <code className="ops-id">{attempt.worker_id}</code>
                  <span>fence {attempt.fencing_token} · {formatDuration(attempt.duration_ms)}</span>
                  {attempt.reason && <span className="ops-error-text">{attempt.reason}</span>}
                </li>
              ))}
            </ol>
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无运行尝试" />}

          <h3>专家任务</h3>
          {detail.expert_jobs.length ? (
            <Table
              rowKey="job_id"
              size="small"
              columns={jobColumns}
              dataSource={detail.expert_jobs}
              pagination={false}
              scroll={{ x: 620 }}
            />
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无专家任务" />}

          {jobId && (
            <ExpertJobSection
              jobId={jobId}
              onClose={() => setJobId(null)}
              onRequestError={onRequestError}
            />
          )}
        </div>
      )}
    </Drawer>
  )
}

interface ExpertJobSectionProps extends RunsViewProps {
  jobId: string
  onClose: () => void
}

function ExpertJobSection({ jobId, onClose, onRequestError }: ExpertJobSectionProps) {
  const [detail, setDetail] = useState<OpsExpertJobDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const pending = getExpertJob(jobId)
    pending.promise.then(setDetail).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      if (!onRequestError(reason)) setError(requestMessage(reason))
    })
    return pending.abort
  }, [jobId, onRequestError])

  return (
    <section className="ops-job-detail" aria-label="专家任务详情">
      <div className="ops-section-heading">
        <h3>专家任务详情</h3>
        <Button type="text" onClick={onClose}>关闭</Button>
      </div>
      {error ? <Alert type="error" title={error} /> : !detail ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : (
        <>
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="Job ID"><code className="ops-id">{detail.job_id}</code></Descriptions.Item>
            <Descriptions.Item label="Logical key"><code className="ops-id">{detail.logical_key}</code></Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={statusColor(detail.status)}>{detail.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="Input hash"><code className="ops-id">{detail.input_hash}</code></Descriptions.Item>
            <Descriptions.Item label="Policy hash"><code className="ops-id">{detail.policy_hash}</code></Descriptions.Item>
            <Descriptions.Item label="预算">
              model {detail.budget.max_model_calls} · tool {detail.budget.max_tool_calls} · output {detail.budget.max_output_tokens} · context {detail.budget.max_context_tokens}
            </Descriptions.Item>
            <Descriptions.Item label="来源">
              {detail.source_refs.length ? detail.source_refs.map((ref) => <code className="ops-id ops-block-id" key={ref}>{ref}</code>) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="错误">{detail.error_code || '—'}</Descriptions.Item>
          </Descriptions>
          <h4>结果尝试</h4>
          {detail.attempts.length ? (
            <ol className="ops-attempt-list">
              {detail.attempts.map((attempt, index) => (
                <li key={`${attempt.worker_id}-${attempt.fencing_token}-${index}`}>
                  <div><strong>{attempt.disposition}</strong>{attempt.rejection_code && <Tag color="error">{attempt.rejection_code}</Tag>}</div>
                  <code className="ops-id">{attempt.worker_id}</code>
                  <span>fence {attempt.fencing_token} · {formatDate(attempt.created_at)}</span>
                </li>
              ))}
            </ol>
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无结果尝试" />}
        </>
      )}
    </section>
  )
}
