import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Empty,
  Input,
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
  RefreshCw,
  RotateCcw,
} from 'lucide-react'
import { getWorkers } from './api'
import type { AbortableRequest, WorkerFilters } from './api'
import type { OpsWorker, OpsWorkerPage } from './types'

interface WorkersViewProps {
  onRequestError: (error: unknown) => boolean
}

const POLL_INTERVAL_MS = 5_000
const PROCESS_TYPES = [
  'api', 'dispatcher', 'reaper', 'run-worker', 'expert-dispatcher',
  'expert-reaper', 'expert-worker',
]

function requestMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求未完成，请重试'
}

function healthColor(worker: OpsWorker): string {
  if (!worker.fresh || worker.health !== 'healthy') return 'error'
  if (worker.status !== 'running') return 'default'
  return 'success'
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

export default function WorkersView({ onRequestError }: WorkersViewProps) {
  const [items, setItems] = useState<OpsWorker[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [cursor, setCursor] = useState<string | null>(null)
  const [history, setHistory] = useState<Array<string | null>>([])
  const [workerIdInput, setWorkerIdInput] = useState('')
  const [filters, setFilters] = useState<WorkerFilters>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    let active: AbortableRequest<OpsWorkerPage> | null = null
    let disposed = false

    const load = () => {
      active?.abort()
      active = getWorkers(cursor, filters)
      setLoading(true)
      active.promise.then((page) => {
        if (disposed) return
        setItems(page.items)
        setNextCursor(page.next_cursor)
        setLastUpdated(new Date())
        setError('')
      }).catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        if (!onRequestError(reason)) setError(requestMessage(reason))
      }).finally(() => {
        if (!disposed) setLoading(false)
      })
    }

    load()
    const timer = window.setInterval(load, POLL_INTERVAL_MS)
    return () => {
      disposed = true
      window.clearInterval(timer)
      active?.abort()
    }
  }, [cursor, filters, reload, onRequestError])

  function resetPaging() {
    setCursor(null)
    setHistory([])
  }

  function updateFilters(next: WorkerFilters) {
    setFilters(next)
    resetPaging()
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

  const columns: TableColumnsType<OpsWorker> = [
    {
      title: 'Worker',
      width: 245,
      render: (_, worker) => (
        <div className="ops-cell-stack">
          <code className="ops-id">{worker.worker_id}</code>
          <span>instance <code className="ops-id">{worker.instance_id}</code></span>
        </div>
      ),
    },
    { title: '进程', dataIndex: 'process_type', width: 150 },
    {
      title: '健康',
      width: 145,
      render: (_, worker) => (
        <div className="ops-cell-stack">
          <Tag color={healthColor(worker)}>{worker.health}</Tag>
          <span>{worker.fresh ? 'fresh' : 'stale'} · {worker.status}</span>
        </div>
      ),
    },
    {
      title: '心跳年龄',
      dataIndex: 'heartbeat_age_seconds',
      width: 110,
      align: 'right',
      render: (value: number, worker) => (
        <Tooltip title={`上次心跳：${formatDate(worker.last_heartbeat_at)}`}>
          <span className={!worker.fresh ? 'ops-error-text' : ''}>{formatAge(value)}</span>
        </Tooltip>
      ),
    },
    {
      title: '能力',
      dataIndex: 'capabilities',
      width: 240,
      render: (values: string[]) => values.length
        ? <div className="ops-tag-list">{values.map((value) => <Tag key={value}>{value}</Tag>)}</div>
        : '—',
    },
    {
      title: '当前分配',
      width: 250,
      render: (_, worker) => (
        <div className="ops-cell-stack">
          <span>Run: {worker.current_run_id ? <code className="ops-id">{worker.current_run_id}</code> : '—'}</span>
          <span>Job: {worker.current_job_id ? <code className="ops-id">{worker.current_job_id}</code> : '—'}</span>
        </div>
      ),
    },
    {
      title: '启动时间',
      dataIndex: 'started_at',
      width: 180,
      render: (value: string) => formatDate(value),
    },
  ]

  return (
    <section className="ops-panel" aria-label="Worker 列表">
      <div className="ops-toolbar">
        <Space wrap>
          <Input.Search
            className="ops-worker-search"
            allowClear
            placeholder="精确 Worker ID"
            value={workerIdInput}
            onChange={(event) => setWorkerIdInput(event.target.value)}
            onSearch={(value) => updateFilters({ ...filters, worker_id: value || undefined })}
          />
          <Select
            className="ops-filter"
            allowClear
            placeholder="全部进程"
            value={filters.process_type}
            options={PROCESS_TYPES.map((value) => ({ value, label: value }))}
            onChange={(value) => updateFilters({ ...filters, process_type: value })}
          />
          <Select
            className="ops-filter"
            allowClear
            placeholder="全部状态"
            value={filters.status}
            options={['running', 'stopped'].map((value) => ({ value, label: value }))}
            onChange={(value) => updateFilters({ ...filters, status: value })}
          />
          <Button
            icon={<RotateCcw size={15} />}
            onClick={() => {
              setWorkerIdInput('')
              updateFilters({})
            }}
          >
            重置
          </Button>
        </Space>
        <div className="ops-poll-state">
          <span>{lastUpdated ? `${formatDate(lastUpdated.toISOString())} 更新` : '等待首次更新'}</span>
          <Button icon={<RefreshCw size={15} />} onClick={() => setReload((value) => value + 1)}>
            刷新
          </Button>
        </div>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          title="Workers 加载失败"
          description={error}
          action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>}
        />
      ) : loading && !items.length ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : !items.length ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有符合条件的 Worker" />
      ) : (
        <Table
          rowKey={(worker) => `${worker.worker_id}:${worker.instance_id}`}
          size="small"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={false}
          scroll={{ x: 1320 }}
          rowClassName={(worker) => worker.fresh ? '' : 'ops-stale-row'}
        />
      )}

      <div className="ops-pagination" aria-label="Workers 游标分页">
        <Button icon={<ChevronLeft size={15} />} disabled={!history.length || loading} onClick={previousPage}>
          上一页
        </Button>
        <span>第 {history.length + 1} 页 · 每 5 秒刷新</span>
        <Button disabled={!nextCursor || loading} onClick={nextPage}>
          下一页 <ChevronRight size={15} />
        </Button>
      </div>
    </section>
  )
}
