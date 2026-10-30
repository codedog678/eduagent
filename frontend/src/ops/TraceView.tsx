import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Empty, Skeleton, Tag } from 'antd'
import {
  ChevronDown,
  ChevronRight,
  CircleDot,
  RefreshCw,
} from 'lucide-react'
import { getTrace } from './api'
import type { OpsTrace, OpsTraceSpan } from './types'

interface TraceViewProps {
  runId: string
  onRequestError: (error: unknown) => boolean
}

interface SpanNode {
  span: OpsTraceSpan
  children: SpanNode[]
}

function statusColor(status: string): string {
  if (status === 'ok' || status === 'completed' || status === 'accepted') return 'success'
  if (status === 'running' || status === 'unset') return 'processing'
  if (status.includes('error') || status.includes('failed')) return 'error'
  return 'default'
}

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${milliseconds} ms`
  if (milliseconds < 60_000) return `${(milliseconds / 1000).toFixed(2)} s`
  return `${(milliseconds / 60_000).toFixed(1)} min`
}

function buildTree(spans: OpsTraceSpan[]): SpanNode[] {
  const byId = new Map(spans.map((span) => [span.span_id, span]))
  const children = new Map<string, OpsTraceSpan[]>()
  spans.forEach((span) => {
    if (span.parent_span_id && byId.has(span.parent_span_id)) {
      const siblings = children.get(span.parent_span_id) || []
      siblings.push(span)
      children.set(span.parent_span_id, siblings)
    }
  })

  const visited = new Set<string>()
  const makeNode = (span: OpsTraceSpan, ancestors: Set<string>): SpanNode => {
    visited.add(span.span_id)
    if (ancestors.has(span.span_id)) return { span, children: [] }
    const nextAncestors = new Set(ancestors).add(span.span_id)
    return {
      span,
      children: (children.get(span.span_id) || []).map((child) => makeNode(child, nextAncestors)),
    }
  }

  const roots = spans
    .filter((span) => !span.parent_span_id || !byId.has(span.parent_span_id))
    .map((span) => makeNode(span, new Set()))
  spans.forEach((span) => {
    if (!visited.has(span.span_id)) roots.push(makeNode(span, new Set()))
  })
  return roots
}

function requestMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求未完成，请重试'
}

export default function TraceView({ runId, onRequestError }: TraceViewProps) {
  const [trace, setTrace] = useState<OpsTrace | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    const pending = getTrace(runId)
    setLoading(true)
    setError('')
    pending.promise.then((value) => {
      setTrace(value)
      setExpanded(new Set(value.spans.map((span) => span.span_id)))
    }).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      if (!onRequestError(reason)) setError(requestMessage(reason))
    }).finally(() => setLoading(false))
    return pending.abort
  }, [runId, reload, onRequestError])

  const tree = useMemo(() => buildTree(trace?.spans || []), [trace])

  function toggle(spanId: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  return (
    <section className="ops-panel" aria-label="运行 Trace">
      <div className="ops-toolbar">
        <div className="ops-trace-identity">
          <span>Run</span>
          <code className="ops-id">{runId}</code>
          {trace && (
            <>
              <span>Trace</span>
              <code className="ops-id">{trace.trace_id}</code>
            </>
          )}
        </div>
        <Button icon={<RefreshCw size={15} />} onClick={() => setReload((value) => value + 1)}>
          刷新
        </Button>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          title="Trace 加载失败"
          description={error}
          action={<Button onClick={() => setReload((value) => value + 1)}>重试</Button>}
        />
      ) : loading && !trace ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : !trace?.spans.length ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="此运行没有 Trace span" />
      ) : (
        <div className={loading ? 'ops-refreshing' : ''}>
          <div className="ops-trace-header" aria-hidden="true">
            <span>Span</span>
            <span>状态</span>
            <span>耗时</span>
          </div>
          <ol className="ops-trace-tree" role="tree" aria-label="Trace 因果树">
            {tree.map((node) => (
              <TraceNode key={node.span.span_id} node={node} expanded={expanded} onToggle={toggle} />
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}

interface TraceNodeProps {
  node: SpanNode
  expanded: Set<string>
  onToggle: (spanId: string) => void
}

function TraceNode({ node, expanded, onToggle }: TraceNodeProps) {
  const { span, children } = node
  const open = expanded.has(span.span_id)
  const attributes = Object.entries(span.attributes)

  return (
    <li role="treeitem" aria-expanded={children.length ? open : undefined}>
      <div className="ops-trace-row">
        <div className="ops-trace-name">
          {children.length ? (
            <button
              className="ops-tree-toggle"
              type="button"
              onClick={() => onToggle(span.span_id)}
              aria-label={`${open ? '收起' : '展开'} ${span.name}`}
            >
              {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
            </button>
          ) : <span className="ops-tree-leaf"><CircleDot size={11} /></span>}
          <div>
            <strong>{span.name}</strong>
            <code className="ops-id">{span.span_id}</code>
          </div>
        </div>
        <div><Tag color={statusColor(span.status)}>{span.status}</Tag></div>
        <span className="ops-trace-duration">{formatDuration(span.duration_ms)}</span>
      </div>
      {attributes.length > 0 && (
        <dl className="ops-trace-attributes">
          {attributes.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {children.length > 0 && open && (
        <ol role="group">
          {children.map((child) => (
            <TraceNode key={child.span.span_id} node={child} expanded={expanded} onToggle={onToggle} />
          ))}
        </ol>
      )}
    </li>
  )
}
