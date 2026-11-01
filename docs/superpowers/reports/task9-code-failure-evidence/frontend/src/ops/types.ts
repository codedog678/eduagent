export type OpsScalar = string | number | boolean

export interface OpsUsage {
  model_calls: number
  tool_calls: number
  input_tokens: number | null
  output_tokens: number | null
  estimated_cost_usd: string | null
  uncertain: boolean
}

export type PolicyEnvironment = 'production' | 'rehearsal'
export type PolicyState = 'registered' | 'shadow' | 'canary' | 'active' | 'frozen' | 'rolled_back'
export type PolicyGate = 'artifact_integrity' | 'campaign_eligibility' | 'judge_calibration'
  | 'formal_holdout' | 'harness_qualification' | 'shadow_health' | 'canary_health' | 'promotion_approval'
export type PolicyAuditType = 'qualification_registered' | 'promotion_transitioned'
  | 'promotion_rejected' | 'health_rollback' | 'admission_artifact_rejected' | 'redacted'
export type PolicyThresholdCode = 'confirmed_permission_violation' | 'baseline_shortage'
  | 'cost_unavailable' | 'structured_decisions_unavailable' | 'commit_failure_rate'
  | 'terminal_failure_rate' | 'unknown_rate' | 'latency_increase_rate'
  | 'mean_cost_increase_rate' | 'matched_window_incomplete' | 'redacted'

export interface OpsPolicyBinding {
  deployment_id: string | null
  effective_policy_hash: string | null
  policy_cohort: 'stable' | 'candidate' | 'shadow' | null
  namespace_class: PolicyEnvironment | null
}

export interface OpsRunSummary extends OpsPolicyBinding {
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

export interface OpsTrace extends OpsPolicyBinding {
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

export interface OpsPolicyThresholds {
  candidate_min_runs: number
  stable_min_runs: number
  window_max_runs: number
  commit_failure_rate: string
  terminal_failure_rate: string
  latency_increase_rate: string
  mean_cost_increase_rate: string
  unknown_rate: string
  relative_epsilon: string
}

export interface OpsHealthStats {
  run_count: number | null
  commit_failure_rate: string | null
  terminal_failure_rate: string | null
  p95_latency: string | null
  mean_cost: string | null
  structured_decision_count: number | null
  unknown_decision_count: number | null
  unknown_rate: string | null
  fault_injected_count: number | null
  injected_commit_failure_count: number | null
  natural_failure_count: number | null
  latency_increase_rate: string | null
  mean_cost_increase_rate: string | null
}

export interface OpsGateReceipt {
  receipt_id: string
  policy_hash: string
  gate_type: PolicyGate
  status: 'passed' | 'failed' | 'unknown'
  evidence_hash: string
  sample_count: number
  cost: string
  issuer: 'redacted'
  issued_at: string
}

export interface OpsHealthWindow {
  window_id: string
  deployment_id: string
  deployment_version: number | null
  environment: PolicyEnvironment
  metric_contract_version: number
  thresholds_hash: string | null
  candidate_stats: OpsHealthStats
  stable_stats: OpsHealthStats
  decision: 'pass' | 'hold' | 'fail'
  triggered_thresholds: PolicyThresholdCode[]
  evaluated_at: string
  created_at: string
}

export interface OpsAuditEvent {
  event_id: string
  environment: PolicyEnvironment
  deployment_id: string | null
  failed_deployment_id: string | null
  health_window_id: string | null
  from_state: PolicyState | null
  to_state: PolicyState | null
  event_type: PolicyAuditType
  actor: 'redacted'
  reason: 'redacted'
  created_at: string
}

export interface OpsPolicyDeployment {
  deployment_id: string
  environment: PolicyEnvironment
  version: number
  state: PolicyState
  candidate_policy_hash: string | null
  stable_policy_hash: string
  is_current: boolean
  current_deployment_id: string | null
  current_version: number | null
  traffic_basis_points: number
  cohort_counts: { stable: number; candidate: number; shadow: number }
  thresholds: OpsPolicyThresholds
  thresholds_hash: string
  required_receipts: PolicyGate[]
  actor: 'redacted'
  reason: 'redacted'
  created_at: string
}

export interface OpsPolicyDeploymentDetail extends OpsPolicyDeployment {
  gate_receipts: OpsGateReceipt[]
  latest_health_window: OpsHealthWindow | null
  audit_events: OpsAuditEvent[]
}

export interface OpsPolicyPage<T> {
  items: T[]
  next_cursor: string | null
}
