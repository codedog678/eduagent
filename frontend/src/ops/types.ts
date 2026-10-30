export type OpsScalar = string | number | boolean

export interface OpsUsage {
  model_calls: number
  tool_calls: number
  input_tokens: number | null
  output_tokens: number | null
  estimated_cost_usd: string | null
  uncertain: boolean
}

export interface OpsRunSummary {
  run_id: string
  operation: string
  status: string
  trace_id: string
  attempt_count: number
  owner: string | null
  fencing_token: number
  lease_expires_at: string | null
  lease_fresh: boolean
  expert_job_count: number
  usage: OpsUsage
  latency_ms: number
  created_at: string
  updated_at: string
}

export interface OpsRunAttempt {
  number: number
  worker_id: string
  fencing_token: number
  status: string
  reason: string | null
  started_at: string
  deadline_at: string
  finished_at: string | null
  duration_ms: number
}

export interface OpsExpertJobSummary {
  job_id: string
  parent_run_id: string
  role: string
  status: string
  attempt_count: number
  max_attempts: number
  error_code: string | null
  deadline_at: string
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface OpsRunDetail extends OpsRunSummary {
  attempts: OpsRunAttempt[]
  expert_jobs: OpsExpertJobSummary[]
}

export interface OpsTraceSpan {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  name: string
  status: string
  attributes: Record<string, OpsScalar>
  started_at: string
  ended_at: string | null
  duration_ms: number
}

export interface OpsTrace {
  run_id: string
  trace_id: string
  spans: OpsTraceSpan[]
}

export interface OpsExpertBudget {
  max_model_calls: number
  max_tool_calls: number
  max_output_tokens: number
  max_context_tokens: number
  max_attempts: number
  deadline_at: string
}

export interface OpsExpertAttempt {
  worker_id: string
  fencing_token: number
  disposition: string
  rejection_code: string | null
  usage: OpsUsage
  source_refs: string[]
  created_at: string
}

export interface OpsExpertJobDetail {
  job_id: string
  parent_run_id: string
  logical_key: string
  role: string
  status: string
  input_hash: string
  policy_hash: string
  budget: OpsExpertBudget
  usage: OpsUsage
  source_refs: string[]
  attempts: OpsExpertAttempt[]
  error_code: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface OpsWorker {
  worker_id: string
  instance_id: string
  process_type: string
  status: string
  health: string
  fresh: boolean
  capabilities: string[]
  current_run_id: string | null
  current_job_id: string | null
  heartbeat_age_seconds: number
  started_at: string
  last_heartbeat_at: string
  stopped_at: string | null
}

export interface OpsRunPage {
  items: OpsRunSummary[]
  next_cursor: string | null
}

export interface OpsExpertJobPage {
  items: OpsExpertJobSummary[]
  next_cursor: string | null
}

export interface OpsWorkerPage {
  items: OpsWorker[]
  next_cursor: string | null
}

export interface CursorPageState {
  cursor: string | null
  history: Array<string | null>
}
