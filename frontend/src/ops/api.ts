import type {
  OpsExpertAttempt,
  OpsExpertBudget,
  OpsExpertJobDetail,
  OpsExpertJobSummary,
  OpsRunAttempt,
  OpsRunDetail,
  OpsRunPage,
  OpsRunSummary,
  OpsScalar,
  OpsTrace,
  OpsTraceSpan,
  OpsUsage,
  OpsWorker,
  OpsWorkerPage,
} from './types'

const API_ROOT = '/ops-api/ops'
export const OPS_TOKEN_KEY = 'eduagent.ops.token'

type Guard<T> = (value: unknown, path: string) => T

export class OpsApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'OpsApiError'
  }
}

export interface AbortableRequest<T> {
  promise: Promise<T>
  abort: () => void
}

export interface RunFilters {
  status?: string
  operation?: string
}

export interface WorkerFilters {
  worker_id?: string
  process_type?: string
  status?: string
}

function fail(path: string, expected: string): never {
  throw new Error(`响应格式错误：${path} 应为 ${expected}`)
}

function object(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return fail(path, '对象')
  }
  return value as Record<string, unknown>
}

function exact(
  value: unknown,
  path: string,
  keys: readonly string[],
): Record<string, unknown> {
  const result = object(value, path)
  const actual = Object.keys(result)
  const missing = keys.find((key) => !(key in result))
  const unknown = actual.find((key) => !keys.includes(key))
  if (missing) fail(`${path}.${missing}`, '必填字段')
  if (unknown) fail(`${path}.${unknown}`, '受支持字段')
  return result
}

function string(value: unknown, path: string): string {
  if (typeof value !== 'string') return fail(path, '字符串')
  return value
}

function nullableString(value: unknown, path: string): string | null {
  return value === null ? null : string(value, path)
}

function number(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fail(path, '有限数字')
  return value
}

function integer(value: unknown, path: string): number {
  const result = number(value, path)
  if (!Number.isInteger(result)) return fail(path, '整数')
  return result
}

function nonNegativeInteger(value: unknown, path: string): number {
  const result = integer(value, path)
  if (result < 0) return fail(path, '非负整数')
  return result
}

function positiveInteger(value: unknown, path: string): number {
  const result = integer(value, path)
  if (result < 1) return fail(path, '正整数')
  return result
}

function nonNegativeNumber(value: unknown, path: string): number {
  const result = number(value, path)
  if (result < 0) return fail(path, '非负数字')
  return result
}

function boolean(value: unknown, path: string): boolean {
  if (typeof value !== 'boolean') return fail(path, '布尔值')
  return value
}

function array<T>(value: unknown, path: string, guard: Guard<T>): T[] {
  if (!Array.isArray(value)) return fail(path, '数组')
  return value.map((item, index) => guard(item, `${path}[${index}]`))
}

function stringArray(value: unknown, path: string): string[] {
  return array(value, path, string)
}

const usageKeys = [
  'model_calls', 'tool_calls', 'input_tokens', 'output_tokens',
  'estimated_cost_usd', 'uncertain',
] as const

function usage(value: unknown, path = 'usage'): OpsUsage {
  const item = exact(value, path, usageKeys)
  const estimated = item.estimated_cost_usd
  if (
    estimated !== null
    && (
      typeof estimated !== 'string'
      || !/^\+?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(estimated)
      || !Number.isFinite(Number(estimated))
      || Number(estimated) < 0
    )
  ) {
    fail(`${path}.estimated_cost_usd`, '十进制字符串或 null')
  }
  return {
    model_calls: nonNegativeInteger(item.model_calls, `${path}.model_calls`),
    tool_calls: nonNegativeInteger(item.tool_calls, `${path}.tool_calls`),
    input_tokens: item.input_tokens === null ? null : nonNegativeInteger(item.input_tokens, `${path}.input_tokens`),
    output_tokens: item.output_tokens === null ? null : nonNegativeInteger(item.output_tokens, `${path}.output_tokens`),
    estimated_cost_usd: estimated === null ? null : estimated,
    uncertain: boolean(item.uncertain, `${path}.uncertain`),
  }
}

const runSummaryKeys = [
  'run_id', 'operation', 'status', 'trace_id', 'attempt_count', 'owner',
  'fencing_token', 'lease_expires_at', 'lease_fresh', 'expert_job_count',
  'usage', 'latency_ms', 'created_at', 'updated_at',
] as const

function runSummary(value: unknown, path = 'run'): OpsRunSummary {
  const item = exact(value, path, runSummaryKeys)
  return {
    run_id: string(item.run_id, `${path}.run_id`),
    operation: string(item.operation, `${path}.operation`),
    status: string(item.status, `${path}.status`),
    trace_id: string(item.trace_id, `${path}.trace_id`),
    attempt_count: nonNegativeInteger(item.attempt_count, `${path}.attempt_count`),
    owner: nullableString(item.owner, `${path}.owner`),
    fencing_token: nonNegativeInteger(item.fencing_token, `${path}.fencing_token`),
    lease_expires_at: nullableString(item.lease_expires_at, `${path}.lease_expires_at`),
    lease_fresh: boolean(item.lease_fresh, `${path}.lease_fresh`),
    expert_job_count: nonNegativeInteger(item.expert_job_count, `${path}.expert_job_count`),
    usage: usage(item.usage, `${path}.usage`),
    latency_ms: nonNegativeInteger(item.latency_ms, `${path}.latency_ms`),
    created_at: string(item.created_at, `${path}.created_at`),
    updated_at: string(item.updated_at, `${path}.updated_at`),
  }
}

const runAttemptKeys = [
  'number', 'worker_id', 'fencing_token', 'status', 'reason', 'started_at',
  'deadline_at', 'finished_at', 'duration_ms',
] as const

function runAttempt(value: unknown, path = 'attempt'): OpsRunAttempt {
  const item = exact(value, path, runAttemptKeys)
  return {
    number: positiveInteger(item.number, `${path}.number`),
    worker_id: string(item.worker_id, `${path}.worker_id`),
    fencing_token: positiveInteger(item.fencing_token, `${path}.fencing_token`),
    status: string(item.status, `${path}.status`),
    reason: nullableString(item.reason, `${path}.reason`),
    started_at: string(item.started_at, `${path}.started_at`),
    deadline_at: string(item.deadline_at, `${path}.deadline_at`),
    finished_at: nullableString(item.finished_at, `${path}.finished_at`),
    duration_ms: nonNegativeInteger(item.duration_ms, `${path}.duration_ms`),
  }
}

const jobSummaryKeys = [
  'job_id', 'parent_run_id', 'role', 'status', 'attempt_count', 'max_attempts',
  'error_code', 'deadline_at', 'created_at', 'updated_at', 'completed_at',
] as const

function jobSummary(value: unknown, path = 'job'): OpsExpertJobSummary {
  const item = exact(value, path, jobSummaryKeys)
  return {
    job_id: string(item.job_id, `${path}.job_id`),
    parent_run_id: string(item.parent_run_id, `${path}.parent_run_id`),
    role: string(item.role, `${path}.role`),
    status: string(item.status, `${path}.status`),
    attempt_count: nonNegativeInteger(item.attempt_count, `${path}.attempt_count`),
    max_attempts: positiveInteger(item.max_attempts, `${path}.max_attempts`),
    error_code: nullableString(item.error_code, `${path}.error_code`),
    deadline_at: string(item.deadline_at, `${path}.deadline_at`),
    created_at: string(item.created_at, `${path}.created_at`),
    updated_at: string(item.updated_at, `${path}.updated_at`),
    completed_at: nullableString(item.completed_at, `${path}.completed_at`),
  }
}

function runPage(value: unknown, path = 'response'): OpsRunPage {
  const item = exact(value, path, ['items', 'next_cursor'])
  return {
    items: array(item.items, `${path}.items`, runSummary),
    next_cursor: nullableString(item.next_cursor, `${path}.next_cursor`),
  }
}

function runDetail(value: unknown, path = 'response'): OpsRunDetail {
  const item = exact(value, path, [...runSummaryKeys, 'attempts', 'expert_jobs'])
  const summaryValue = Object.fromEntries(
    runSummaryKeys.map((key) => [key, item[key]]),
  )
  return {
    ...runSummary(summaryValue, path),
    attempts: array(item.attempts, `${path}.attempts`, runAttempt),
    expert_jobs: array(item.expert_jobs, `${path}.expert_jobs`, jobSummary),
  }
}

const traceSpanKeys = [
  'span_id', 'trace_id', 'parent_span_id', 'name', 'status', 'attributes',
  'started_at', 'ended_at', 'duration_ms',
] as const

function traceSpan(value: unknown, path = 'span'): OpsTraceSpan {
  const item = exact(value, path, traceSpanKeys)
  const rawAttributes = object(item.attributes, `${path}.attributes`)
  const attributes: Record<string, OpsScalar> = {}
  Object.entries(rawAttributes).forEach(([key, attribute]) => {
    if (
      typeof attribute !== 'string'
      && typeof attribute !== 'number'
      && typeof attribute !== 'boolean'
    ) fail(`${path}.attributes.${key}`, '字符串、数字或布尔值')
    attributes[key] = attribute
  })
  return {
    span_id: string(item.span_id, `${path}.span_id`),
    trace_id: string(item.trace_id, `${path}.trace_id`),
    parent_span_id: nullableString(item.parent_span_id, `${path}.parent_span_id`),
    name: string(item.name, `${path}.name`),
    status: string(item.status, `${path}.status`),
    attributes,
    started_at: string(item.started_at, `${path}.started_at`),
    ended_at: nullableString(item.ended_at, `${path}.ended_at`),
    duration_ms: nonNegativeInteger(item.duration_ms, `${path}.duration_ms`),
  }
}

function trace(value: unknown, path = 'response'): OpsTrace {
  const item = exact(value, path, ['run_id', 'trace_id', 'spans'])
  return {
    run_id: string(item.run_id, `${path}.run_id`),
    trace_id: string(item.trace_id, `${path}.trace_id`),
    spans: array(item.spans, `${path}.spans`, traceSpan),
  }
}

const expertBudgetKeys = [
  'max_model_calls', 'max_tool_calls', 'max_output_tokens', 'max_context_tokens',
  'max_attempts', 'deadline_at',
] as const

function expertBudget(value: unknown, path = 'budget'): OpsExpertBudget {
  const item = exact(value, path, expertBudgetKeys)
  return {
    max_model_calls: nonNegativeInteger(item.max_model_calls, `${path}.max_model_calls`),
    max_tool_calls: nonNegativeInteger(item.max_tool_calls, `${path}.max_tool_calls`),
    max_output_tokens: nonNegativeInteger(item.max_output_tokens, `${path}.max_output_tokens`),
    max_context_tokens: nonNegativeInteger(item.max_context_tokens, `${path}.max_context_tokens`),
    max_attempts: positiveInteger(item.max_attempts, `${path}.max_attempts`),
    deadline_at: string(item.deadline_at, `${path}.deadline_at`),
  }
}

const expertAttemptKeys = [
  'worker_id', 'fencing_token', 'disposition', 'rejection_code', 'usage',
  'source_refs', 'created_at',
] as const

function expertAttempt(value: unknown, path = 'attempt'): OpsExpertAttempt {
  const item = exact(value, path, expertAttemptKeys)
  return {
    worker_id: string(item.worker_id, `${path}.worker_id`),
    fencing_token: nonNegativeInteger(item.fencing_token, `${path}.fencing_token`),
    disposition: string(item.disposition, `${path}.disposition`),
    rejection_code: nullableString(item.rejection_code, `${path}.rejection_code`),
    usage: usage(item.usage, `${path}.usage`),
    source_refs: stringArray(item.source_refs, `${path}.source_refs`),
    created_at: string(item.created_at, `${path}.created_at`),
  }
}

function expertJobDetail(value: unknown, path = 'response'): OpsExpertJobDetail {
  const keys = [
    'job_id', 'parent_run_id', 'logical_key', 'role', 'status', 'input_hash',
    'policy_hash', 'budget', 'usage', 'source_refs', 'attempts', 'error_code',
    'created_at', 'updated_at', 'completed_at',
  ] as const
  const item = exact(value, path, keys)
  return {
    job_id: string(item.job_id, `${path}.job_id`),
    parent_run_id: string(item.parent_run_id, `${path}.parent_run_id`),
    logical_key: string(item.logical_key, `${path}.logical_key`),
    role: string(item.role, `${path}.role`),
    status: string(item.status, `${path}.status`),
    input_hash: string(item.input_hash, `${path}.input_hash`),
    policy_hash: string(item.policy_hash, `${path}.policy_hash`),
    budget: expertBudget(item.budget, `${path}.budget`),
    usage: usage(item.usage, `${path}.usage`),
    source_refs: stringArray(item.source_refs, `${path}.source_refs`),
    attempts: array(item.attempts, `${path}.attempts`, expertAttempt),
    error_code: nullableString(item.error_code, `${path}.error_code`),
    created_at: string(item.created_at, `${path}.created_at`),
    updated_at: string(item.updated_at, `${path}.updated_at`),
    completed_at: nullableString(item.completed_at, `${path}.completed_at`),
  }
}

const workerKeys = [
  'worker_id', 'instance_id', 'process_type', 'status', 'health', 'fresh',
  'capabilities', 'current_run_id', 'current_job_id', 'heartbeat_age_seconds',
  'started_at', 'last_heartbeat_at', 'stopped_at',
] as const

function worker(value: unknown, path = 'worker'): OpsWorker {
  const item = exact(value, path, workerKeys)
  return {
    worker_id: string(item.worker_id, `${path}.worker_id`),
    instance_id: string(item.instance_id, `${path}.instance_id`),
    process_type: string(item.process_type, `${path}.process_type`),
    status: string(item.status, `${path}.status`),
    health: string(item.health, `${path}.health`),
    fresh: boolean(item.fresh, `${path}.fresh`),
    capabilities: stringArray(item.capabilities, `${path}.capabilities`),
    current_run_id: nullableString(item.current_run_id, `${path}.current_run_id`),
    current_job_id: nullableString(item.current_job_id, `${path}.current_job_id`),
    heartbeat_age_seconds: nonNegativeNumber(item.heartbeat_age_seconds, `${path}.heartbeat_age_seconds`),
    started_at: string(item.started_at, `${path}.started_at`),
    last_heartbeat_at: string(item.last_heartbeat_at, `${path}.last_heartbeat_at`),
    stopped_at: nullableString(item.stopped_at, `${path}.stopped_at`),
  }
}

function workerPage(value: unknown, path = 'response'): OpsWorkerPage {
  const item = exact(value, path, ['items', 'next_cursor'])
  return {
    items: array(item.items, `${path}.items`, worker),
    next_cursor: nullableString(item.next_cursor, `${path}.next_cursor`),
  }
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  })
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}

function request<T>(path: string, guard: Guard<T>): AbortableRequest<T> {
  const controller = new AbortController()
  let token = ''
  try {
    token = sessionStorage.getItem(OPS_TOKEN_KEY) || ''
  } catch {
    token = ''
  }
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const promise = fetch(`${API_ROOT}${path}`, {
    method: 'GET',
    headers,
    signal: controller.signal,
  }).then(async (response) => {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new OpsApiError(`请求失败（HTTP ${response.status}）`, response.status)
    }
    if (!response.ok) {
      const detail = typeof body === 'object' && body !== null && 'detail' in body
        ? (body as { detail?: unknown }).detail
        : null
      throw new OpsApiError(
        typeof detail === 'string' ? detail : `请求失败（HTTP ${response.status}）`,
        response.status,
      )
    }
    return guard(body, 'response')
  })
  return { promise, abort: () => controller.abort() }
}

export function getRuns(
  cursor: string | null,
  filters: RunFilters,
  limit = 50,
): AbortableRequest<OpsRunPage> {
  return request(`/runs${query({ limit, cursor, ...filters })}`, runPage)
}

export function getRun(runId: string): AbortableRequest<OpsRunDetail> {
  return request(`/runs/${encodeURIComponent(runId)}`, runDetail)
}

export function getTrace(runId: string): AbortableRequest<OpsTrace> {
  return request(`/runs/${encodeURIComponent(runId)}/trace`, trace)
}

export function getExpertJob(jobId: string): AbortableRequest<OpsExpertJobDetail> {
  return request(`/expert-jobs/${encodeURIComponent(jobId)}`, expertJobDetail)
}

export function getWorkers(
  cursor: string | null,
  filters: WorkerFilters,
  limit = 50,
): AbortableRequest<OpsWorkerPage> {
  return request(`/workers${query({ limit, cursor, ...filters })}`, workerPage)
}
