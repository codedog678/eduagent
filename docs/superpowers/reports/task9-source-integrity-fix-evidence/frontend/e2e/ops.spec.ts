import { expect, Page, test } from '@playwright/test'

const usage = {
  model_calls: 1,
  tool_calls: 2,
  input_tokens: 120,
  output_tokens: 48,
  estimated_cost_usd: '0.0021',
  uncertain: false,
}

const deploymentId = '11111111-1111-1111-1111-111111111111'
const secondDeploymentId = '22222222-2222-2222-2222-222222222222'
const binding = {
  deployment_id: deploymentId,
  effective_policy_hash: 'b'.repeat(64),
  policy_cohort: 'candidate',
  namespace_class: 'rehearsal',
}

const run = (id: string, status = 'completed') => ({
  ...binding,
  run_id: id,
  operation: 'learning_task',
  status,
  trace_id: id === 'run-1' ? 'a'.repeat(32) : 'b'.repeat(32),
  attempt_count: 2,
  owner: 'run-worker-a',
  fencing_token: 3,
  lease_expires_at: '2026-10-30T10:01:00Z',
  lease_fresh: status === 'running',
  expert_job_count: 1,
  usage,
  latency_ms: 1280,
  created_at: '2026-10-30T10:00:00Z',
  updated_at: '2026-10-30T10:00:01.280Z',
})

const runDetail = {
  ...run('run-1'),
  attempts: [
    {
      number: 1,
      worker_id: 'run-worker-a',
      fencing_token: 2,
      status: 'retryable_failed',
      reason: 'lease_expired',
      started_at: '2026-10-30T09:59:55Z',
      deadline_at: '2026-10-30T10:01:55Z',
      finished_at: '2026-10-30T09:59:58Z',
      duration_ms: 3000,
    },
    {
      number: 2,
      worker_id: 'run-worker-b',
      fencing_token: 3,
      status: 'completed',
      reason: null,
      started_at: '2026-10-30T10:00:00Z',
      deadline_at: '2026-10-30T10:02:00Z',
      finished_at: '2026-10-30T10:00:01.280Z',
      duration_ms: 1280,
    },
  ],
  expert_jobs: [
    {
      job_id: 'job-1',
      parent_run_id: 'run-1',
      role: 'assessment',
      status: 'completed',
      attempt_count: 2,
      max_attempts: 3,
      error_code: null,
      deadline_at: '2026-10-30T10:01:00Z',
      created_at: '2026-10-30T10:00:00.100Z',
      updated_at: '2026-10-30T10:00:00.900Z',
      completed_at: '2026-10-30T10:00:00.900Z',
    },
  ],
}

const expertDetail = {
  job_id: 'job-1',
  parent_run_id: 'run-1',
  logical_key: 'plan:1:assessment',
  role: 'assessment',
  status: 'completed',
  input_hash: 'c'.repeat(64),
  policy_hash: 'd'.repeat(64),
  budget: {
    max_model_calls: 3,
    max_tool_calls: 4,
    max_output_tokens: 800,
    max_context_tokens: 6000,
    max_attempts: 3,
    deadline_at: '2026-10-30T10:01:00Z',
  },
  usage,
  source_refs: ['knowledge:grammar_tenses'],
  attempts: [
    {
      worker_id: 'expert-worker-a',
      fencing_token: 1,
      disposition: 'rejected',
      rejection_code: 'expert_token_stale',
      usage,
      source_refs: [],
      created_at: '2026-10-30T10:00:00.700Z',
    },
    {
      worker_id: 'expert-worker-b',
      fencing_token: 2,
      disposition: 'accepted',
      rejection_code: null,
      usage,
      source_refs: ['knowledge:grammar_tenses'],
      created_at: '2026-10-30T10:00:00.900Z',
    },
  ],
  error_code: null,
  created_at: '2026-10-30T10:00:00.100Z',
  updated_at: '2026-10-30T10:00:00.900Z',
  completed_at: '2026-10-30T10:00:00.900Z',
}

const trace = {
  ...binding,
  run_id: 'run-1',
  trace_id: 'a'.repeat(32),
  spans: [
    {
      span_id: '1'.repeat(16),
      trace_id: 'a'.repeat(32),
      parent_span_id: null,
      name: 'run.attempt',
      status: 'ok',
      attributes: {
        'worker.id': 'run-worker-b',
        'run.fencing_token': 3,
      },
      started_at: '2026-10-30T10:00:00Z',
      ended_at: '2026-10-30T10:00:01.280Z',
      duration_ms: 1280,
    },
    {
      span_id: '2'.repeat(16),
      trace_id: 'a'.repeat(32),
      parent_span_id: '1'.repeat(16),
      name: 'expert.wait',
      status: 'ok',
      attributes: {
        'expert.job_id': 'job-1',
        'expert.fencing_token': 2,
      },
      started_at: '2026-10-30T10:00:00.200Z',
      ended_at: '2026-10-30T10:00:00.900Z',
      duration_ms: 700,
    },
  ],
}

const workers = {
  items: [
    {
      worker_id: 'run-worker-a',
      instance_id: 'instance-run-a',
      process_type: 'run-worker',
      status: 'running',
      health: 'healthy',
      fresh: true,
      capabilities: ['learning_task'],
      current_run_id: 'run-1',
      current_job_id: null,
      heartbeat_age_seconds: 1.2,
      started_at: '2026-10-30T09:55:00Z',
      last_heartbeat_at: '2026-10-30T10:00:00Z',
      stopped_at: null,
    },
    {
      worker_id: 'expert-worker-stale',
      instance_id: 'instance-expert-stale',
      process_type: 'expert-worker',
      status: 'running',
      health: 'stale',
      fresh: false,
      capabilities: ['assessment', 'curriculum'],
      current_run_id: null,
      current_job_id: 'job-1',
      heartbeat_age_seconds: 121.4,
      started_at: '2026-10-30T09:55:00Z',
      last_heartbeat_at: '2026-10-30T09:58:00Z',
      stopped_at: null,
    },
  ],
  next_cursor: null,
}

type MockOptions = {
  runPages?: 'populated' | 'empty'
  runFailureCount?: number
  delayRunsMs?: number
  requireToken?: boolean
  policyEmpty?: boolean
  policyFailureCount?: number
  policyDetailFailureCount?: number
  malformedPolicy?: boolean
  legacyBinding?: boolean
  delayPoliciesMs?: number
  onSlowPolicyDone?: () => void
}

const thresholds = {
  candidate_min_runs: 20, stable_min_runs: 20, window_max_runs: 50,
  commit_failure_rate: '0.05', terminal_failure_rate: '0.10',
  latency_increase_rate: '0.50', mean_cost_increase_rate: '0.30',
  unknown_rate: '0.10', relative_epsilon: '0.000001',
}
const stats = {
  run_count: 20, commit_failure_rate: '0.05', terminal_failure_rate: '0.10',
  p95_latency: '1.25', mean_cost: '0.01', structured_decision_count: 10,
  unknown_decision_count: 1, unknown_rate: '0.10', fault_injected_count: 1,
  injected_commit_failure_count: 1, natural_failure_count: 0,
  latency_increase_rate: null, mean_cost_increase_rate: null,
}
const healthWindow = {
  window_id: 'c'.repeat(64), deployment_id: deploymentId, deployment_version: 2,
  environment: 'rehearsal', metric_contract_version: 1, thresholds_hash: 'd'.repeat(64),
  candidate_stats: stats, stable_stats: { ...stats, mean_cost: null },
  decision: 'fail', triggered_thresholds: ['commit_failure_rate'],
  evaluated_at: '2026-10-30T10:03:00Z', created_at: '2026-10-30T10:03:00Z',
}
const auditEvent = {
  event_id: '33333333-3333-3333-3333-333333333333',
  environment: 'rehearsal', deployment_id: deploymentId, event_type: 'health_rollback',
  failed_deployment_id: null, health_window_id: 'c'.repeat(64), from_state: null, to_state: null,
  actor: 'redacted', reason: 'redacted', created_at: '2026-10-30T10:03:01Z',
}
const policyDeployment = (id = deploymentId) => ({
  deployment_id: id, environment: 'rehearsal', version: id === deploymentId ? 2 : 3,
  state: id === deploymentId ? 'canary' : 'frozen',
  candidate_policy_hash: 'b'.repeat(12), stable_policy_hash: 'a'.repeat(12),
  is_current: id !== deploymentId, current_deployment_id: secondDeploymentId,
  current_version: 3, traffic_basis_points: id === deploymentId ? 5000 : 0,
  cohort_counts: { stable: 20, candidate: 20, shadow: 10 }, thresholds,
  thresholds_hash: 'd'.repeat(64), required_receipts: ['canary_health'],
  actor: 'redacted', reason: 'redacted', created_at: '2026-10-30T10:00:00Z',
})
const policyDetail = (id = deploymentId) => ({
  ...policyDeployment(id), candidate_policy_hash: 'b'.repeat(64),
  stable_policy_hash: 'a'.repeat(64),
  gate_receipts: [{
    receipt_id: '44444444-4444-4444-4444-444444444444',
    policy_hash: 'b'.repeat(64), gate_type: 'canary_health', status: 'failed',
    evidence_hash: 'e'.repeat(64), sample_count: 20, cost: '0.02',
    issuer: 'redacted', issued_at: '2026-10-30T10:02:00Z',
    health_source: {
      relation: 'local', deployment_id: id, deployment_version: id === deploymentId ? 2 : 3,
      window_id: 'c'.repeat(64), thresholds_hash: 'd'.repeat(64), window_decision: 'fail',
      evaluated_at: '2026-10-30T10:03:00Z', is_latest_window: true,
    },
  }],
  latest_health_window: { ...healthWindow, deployment_id: id },
  audit_events: [
    auditEvent,
    { ...auditEvent, event_id: '55555555-5555-5555-5555-555555555555', event_type: 'promotion_transitioned',
      from_state: 'canary', to_state: 'frozen', health_window_id: null },
  ],
})

async function mockOps(page: Page, options: MockOptions = {}) {
  let runFailures = options.runFailureCount || 0
  let policyFailures = options.policyFailureCount || 0
  let detailFailures = options.policyDetailFailureCount || 0
  const withBinding = <T extends object>(value: T) => options.legacyBinding
    ? { ...value, deployment_id: null, effective_policy_hash: null, policy_cohort: null, namespace_class: null }
    : value
  await page.route('**/ops-api/ops/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/ops-api/ops', '')

    if (
      options.requireToken
      && request.headers().authorization !== 'Bearer browser-test-token'
    ) {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'valid Ops bearer token required' }),
      })
      return
    }

    if (path === '/runs') {
      if (options.delayRunsMs) {
        await new Promise((resolve) => setTimeout(resolve, options.delayRunsMs))
      }
      if (runFailures > 0) {
        runFailures -= 1
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'temporary database failure' }),
        })
        return
      }
      const cursor = url.searchParams.get('cursor')
      const body = options.runPages === 'empty'
        ? { items: [], next_cursor: null }
        : cursor === 'cursor-2'
          ? { items: [withBinding(run('run-2', 'running'))], next_cursor: null }
          : { items: [withBinding(run('run-1'))], next_cursor: 'cursor-2' }
      await route.fulfill({ json: body })
      return
    }
    if (path === '/runs/run-1') {
      await route.fulfill({ json: withBinding(runDetail) })
      return
    }
    if (path === '/runs/run-1/trace') {
      await route.fulfill({ json: withBinding(trace) })
      return
    }
    if (path === '/expert-jobs/job-1') {
      await route.fulfill({ json: expertDetail })
      return
    }
    if (path === '/workers') {
      await route.fulfill({ json: workers })
      return
    }
    if (path.startsWith('/policies/deployments/')) {
      if (detailFailures-- > 0) {
        await route.fulfill({ status: 503, json: { detail: 'policy detail unavailable' } })
        return
      }
      const id = path.split('/').at(-1)!
      await route.fulfill({ json: policyDetail(id) })
      return
    }
    if (path.startsWith('/policies/')) {
      if (options.delayPoliciesMs && !url.searchParams.has('environment')) {
        await new Promise((resolve) => setTimeout(resolve, options.delayPoliciesMs))
        options.onSlowPolicyDone?.()
      }
      if (policyFailures-- > 0) {
        await route.fulfill({ status: 503, json: { detail: 'policy evidence unavailable' } })
        return
      }
      if (options.policyEmpty || url.searchParams.get('environment') === 'production') {
        await route.fulfill({ json: { items: [], next_cursor: null } })
        return
      }
      const second = url.searchParams.get('cursor') === 'policy-page-2'
      let items: object[] = path.endsWith('deployments')
        ? [policyDeployment(second ? secondDeploymentId : deploymentId)]
        : path.endsWith('health-windows') ? [healthWindow] : [auditEvent]
      const state = url.searchParams.get('state')
      if (state) items = [policyDeployment(state === 'frozen' ? secondDeploymentId : deploymentId)]
      if (options.malformedPolicy) items = [{ ...items[0], details: { innocent: 'must-not-render' } }]
      await route.fulfill({ json: { items, next_cursor: second || state ? null : 'policy-page-2' } })
      return
    }
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: `unmocked path: ${path}` }),
    })
  })
}

function monitorBrowser(page: Page, ignoredConsoleErrors: RegExp[] = []) {
  const errors: string[] = []
  page.on('console', (message) => {
    if (
      message.type() === 'error'
      && !ignoredConsoleErrors.some((pattern) => pattern.test(message.text()))
    ) {
      errors.push(message.text())
    }
  })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('requestfailed', (request) => {
    const message = request.failure()?.errorText || 'request failed'
    if (!message.toLowerCase().includes('aborted')) {
      errors.push(`${request.url()}: ${message}`)
    }
  })
  return errors
}

async function expectStableLayout(page: Page) {
  const layout = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth
    const bodyOverflow = document.documentElement.scrollWidth - viewportWidth
    const header = document.querySelector('.ops-header')?.getBoundingClientRect()
    const main = document.querySelector('.ops-main')?.getBoundingClientRect()
    const clipped = Array.from(
      document.querySelectorAll<HTMLElement>(
        '.ops-nav a, .ops-page-heading h1, .ops-pagination button',
      ),
    ).filter((element) => (
      element.scrollWidth > element.clientWidth + 2
      || element.scrollHeight > element.clientHeight + 2
    )).map((element) => element.textContent?.trim() || element.className)
    return {
      bodyOverflow,
      clipped,
      coherentFlow: !header || !main || header.bottom <= main.top + 1,
    }
  })
  expect(layout.bodyOverflow).toBeLessThanOrEqual(1)
  expect(layout.clipped).toEqual([])
  expect(layout.coherentFlow).toBe(true)
}

test('renders populated Ops workflows with pagination, detail, trace, and stale workers', async ({ page }, testInfo) => {
  const browserErrors = monitorBrowser(page)
  await mockOps(page)

  await page.goto('/ops/#/runs', { waitUntil: 'commit' })
  await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible()
  await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /下一页/ }).click()
  await expect(page.getByText('run-2', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /上一页/ }).click()
  await expect(page.getByText('run-1', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '查看运行 run-1 详情' }).click()
  const drawer = page.getByRole('dialog', { name: '运行详情' })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByText('run-worker-b', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '检查' }).click()
  await expect(drawer.getByText('knowledge:grammar_tenses')).toBeVisible()

  await drawer.getByRole('link', { name: 'a'.repeat(32) }).click()
  await expect(page.getByRole('heading', { name: '运行 Trace' })).toBeVisible()
  await expect(page.getByText('expert.wait', { exact: true })).toBeVisible()
  await expect(page.getByRole('tree')).toBeVisible()

  await page.getByRole('link', { name: /Workers/ }).click()
  await expect(page.getByRole('heading', { name: 'Workers' })).toBeVisible()
  await expect(page.getByText('expert-worker-stale', { exact: true })).toBeVisible()
  await expect(page.getByText('stale', { exact: true }).first()).toBeVisible()

  await expect(page.getByRole('button', { name: /取消|重试任务|重新入队/ })).toHaveCount(0)
  await expectStableLayout(page)
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({
      path: `${process.env.OPS_SCREENSHOT_DIR}/ops-${testInfo.project.name}.png`,
      fullPage: true,
    })
  }
  expect(browserErrors).toEqual([])
})

test('shows loading and empty states without layout shift', async ({ page }) => {
  const browserErrors = monitorBrowser(page)
  await mockOps(page, { runPages: 'empty' })

  await page.goto('/ops/#/runs', { waitUntil: 'commit' })
  await expect(page.locator('.ant-skeleton')).toBeVisible()
  await expect(page.getByText('没有符合条件的运行')).toBeVisible()
  await expectStableLayout(page)
  expect(browserErrors).toEqual([])
})

test('shows retryable API errors and recovers', async ({ page }) => {
  const browserErrors = monitorBrowser(
    page,
    [/Failed to load resource:.*500 \(Internal Server Error\)/],
  )
  await mockOps(page, { runFailureCount: 2 })

  await page.goto('/ops/#/runs')
  await expect(page.getByText('Runs 加载失败')).toBeVisible()
  await expect(page.getByText('temporary database failure')).toBeVisible()
  await page.getByRole('button', { name: /重\s*试/ }).click()
  await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  await expectStableLayout(page)
  expect(browserErrors).toEqual([])
})

test('keeps bearer token in session storage and retries authorization', async ({ page }) => {
  const browserErrors = monitorBrowser(
    page,
    [/Failed to load resource:.*401 \(Unauthorized\)/],
  )
  await mockOps(page, { requireToken: true })

  await page.goto('/ops/#/runs')
  await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
  await page.getByLabel('OPS API Token').fill('browser-test-token')
  await page.getByRole('button', { name: '验证并重试' }).click()
  await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  expect(
    await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token')),
  ).toBe('browser-test-token')
  await expectStableLayout(page)
  expect(browserErrors).toEqual([])
})

test('policy evidence filters, cursor pages, detail, metrics and audit are read only', async ({ page }, testInfo) => {
  const errors = monitorBrowser(page)
  const requests: Array<{ method: string; url: string }> = []
  page.on('request', (request) => {
    if (request.url().includes('/ops-api/')) requests.push({ method: request.method(), url: request.url() })
  })
  await mockOps(page)
  await page.goto('/ops/#/policies')
  await expect(page.getByRole('heading', { name: 'Policies', exact: true })).toBeVisible()
  await expect(page.getByText(deploymentId, { exact: true })).toBeVisible()
  if (testInfo.project.name === 'mobile') {
    const overflowTable = page.locator('.ant-table-content').first()
    expect(await overflowTable.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
    await overflowTable.hover()
    await page.mouse.wheel(900, 0)
    await expect.poll(() => overflowTable.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
    await page.mouse.wheel(-900, 0)
  }
  await page.getByRole('button', { name: /下一页/ }).click()
  await expect(page.getByText(secondDeploymentId, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /上一页/ }).click()
  await page.getByLabel('策略状态').click()
  await page.getByTitle('frozen', { exact: true }).click()
  await expect(page.getByText(secondDeploymentId, { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /下一页/ })).toBeDisabled()
  await page.getByRole('button', { name: '重置' }).click()
  await page.getByLabel('策略环境').click()
  await page.getByTitle('rehearsal', { exact: true }).click()
  await page.getByRole('link', { name: `查看策略 ${deploymentId}` }).click()
  const detail = page.getByRole('region', { name: '策略版本详情' })
  await expect(detail.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
  await expect(detail.getByText('canary_health', { exact: true }).first()).toBeVisible()
  await expect(detail.getByText('commit_failure_rate', { exact: true }).first()).toBeVisible()
  await expect(detail.getByText('health_rollback', { exact: true })).toBeVisible()
  await expect(detail.getByText('promotion_transitioned', { exact: true })).toBeVisible()
  await expect(detail.getByText('canary → frozen', { exact: true })).toBeVisible()
  await expect(detail.getByText('未知', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: '健康窗口' }).click()
  await expect(page.getByRole('region', { name: '策略证据列表' }).getByText('fail', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '审计时间线' }).click()
  await expect(page.getByRole('region', { name: '策略证据列表' }).getByText('health_rollback', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /晋升|回滚|冻结|发布|删除/ })).toHaveCount(0)
  expect(requests.every((request) => request.method === 'GET')).toBe(true)
  expect(requests.some((request) => request.url.includes('state=frozen'))).toBe(true)
  expect(requests.some((request) => request.url.includes('environment=rehearsal'))).toBe(true)
  await expectStableLayout(page)
  await page.getByRole('tab', { name: '部署' }).click()
  await expect(page.getByRole('region', { name: '策略证据列表' }).getByRole('link', { name: `查看策略 ${deploymentId}` })).toBeVisible()
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({ path: `${process.env.OPS_SCREENSHOT_DIR}/policies-${testInfo.project.name}.png`, fullPage: true, animations: 'disabled' })
  }
  expect(errors).toEqual([])
})

test('policy loading, empty filters and stale requests do not restore old evidence', async ({ page }) => {
  let slowDone!: () => void
  const finished = new Promise<void>((resolve) => { slowDone = resolve })
  await mockOps(page, { delayPoliciesMs: 700, onSlowPolicyDone: slowDone })
  await page.goto('/ops/#/policies', { waitUntil: 'commit' })
  await expect(page.locator('.ant-skeleton')).toBeVisible()
  await page.getByLabel('策略环境').click()
  await page.getByTitle('production', { exact: true }).click()
  await expect(page.getByText('没有符合条件的策略证据')).toBeVisible()
  await finished
  await expect(page.getByText(deploymentId, { exact: true })).toHaveCount(0)
  await expectStableLayout(page)
})

test('policy errors and detail errors have independent retry recovery', async ({ page }) => {
  await mockOps(page, { policyFailureCount: 2, policyDetailFailureCount: 2 })
  await page.goto('/ops/#/policies')
  await expect(page.getByText('策略证据加载失败')).toBeVisible()
  await page.getByRole('button', { name: /重\s*试/ }).click()
  await expect(page.getByText(deploymentId, { exact: true })).toBeVisible()
  await page.getByRole('link', { name: `查看策略 ${deploymentId}` }).click()
  await expect(page.getByText('策略详情加载失败')).toBeVisible()
  await page.getByRole('region', { name: '策略版本详情' }).getByRole('button', { name: /重\s*试/ }).click()
  await expect(page.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
})

test('policy strict response guard rejects extra freeform fields', async ({ page }) => {
  await mockOps(page, { malformedPolicy: true })
  await page.goto('/ops/#/policies')
  await expect(page.getByText('策略证据加载失败')).toBeVisible()
  await expect(page.getByText(/响应格式错误/)).toBeVisible()
  await expect(page.getByText('must-not-render')).toHaveCount(0)
})

test('policy authentication uses existing Ops token and clears it on lock', async ({ page }) => {
  await mockOps(page, { requireToken: true })
  await page.goto(`/ops/#/policies/${deploymentId}`)
  await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
  await page.getByLabel('OPS API Token').fill('browser-test-token')
  await page.getByRole('button', { name: '验证并重试' }).click()
  await expect(page.getByRole('region', { name: '策略版本详情' })).toBeVisible()
  await expect(page.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '锁定控制台并清除会话 token' }).click()
  expect(await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token'))).toBeNull()
  await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
})

test('policy Run and Trace display stored immutable identity and link version evidence', async ({ page }, testInfo) => {
  await mockOps(page)
  await page.goto('/ops/#/runs')
  await page.getByRole('button', { name: '查看运行 run-1 详情' }).click()
  const drawer = page.getByRole('dialog', { name: '运行详情' })
  await expect(drawer.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  await expect(drawer.getByText('candidate', { exact: true })).toBeVisible()
  await drawer.getByRole('link', { name: 'a'.repeat(32) }).click()
  await expect(page.getByRole('heading', { name: '运行 Trace' })).toBeVisible()
  await expect(page.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '运行策略绑定' }).getByText('candidate · rehearsal', { exact: true })).toBeVisible()
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({ path: `${process.env.OPS_SCREENSHOT_DIR}/policy-trace-${testInfo.project.name}.png`, fullPage: true })
  }
  await page.getByRole('link', { name: deploymentId, exact: true }).click()
  await expect(page.getByRole('region', { name: '策略版本详情' }).getByText('rehearsal · 版本 2', { exact: false })).toBeVisible()
  await expect(page.getByText('当前版本 3', { exact: false }).first()).toBeVisible()
  await page.goto('/ops/#/trace/run-1')
  await expect(page.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  await expectStableLayout(page)
})

test('policy legacy Run and Trace identity remains unavailable without current policy fallback', async ({ page }) => {
  await mockOps(page, { legacyBinding: true })
  await page.goto('/ops/#/trace/run-1')
  await expect(page.getByText('策略绑定不可用')).toBeVisible()
  await expect(page.getByText('b'.repeat(64), { exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: deploymentId, exact: true })).toHaveCount(0)
})

for (const scenario of [
  { name: 'actor freeform', path: '/policies/deployments', page: '#/policies',
    body: { items: [{ ...policyDeployment(), actor: 'innocent-private-value' }], next_cursor: null } },
  { name: 'hash identity', path: '/policies/deployments', page: '#/policies',
    body: { items: [{ ...policyDeployment(), stable_policy_hash: 'innocent-private-value' }], next_cursor: null } },
  { name: 'missing required binding', path: '/runs/run-1/trace', page: '#/trace/run-1',
    body: { ...trace, effective_policy_hash: undefined } },
  { name: 'raw namespace', path: '/runs/run-1/trace', page: '#/trace/run-1',
    body: { ...trace, namespace_class: 'innocent-private-value' } },
  { name: 'detail nested extras', path: `/policies/deployments/${deploymentId}`, page: `#/policies/${deploymentId}`,
    body: { ...policyDetail(), gate_receipts: [{ ...policyDetail().gate_receipts[0], details: { innocent: 'innocent-private-value' } }] } },
  { name: 'detail invalid metric', path: `/policies/deployments/${deploymentId}`, page: `#/policies/${deploymentId}`,
    body: { ...policyDetail(), latest_health_window: { ...healthWindow, candidate_stats: { ...stats, unknown_rate: '2' } } } },
]) {
  test(`policy strict typed response rejects ${scenario.name}`, async ({ page }) => {
    await mockOps(page)
    await page.route(`**/ops-api/ops${scenario.path}*`, (route) => route.fulfill({ json: scenario.body }))
    await page.goto(`/ops/${scenario.page}`)
    await expect(page.getByText(/响应格式错误/)).toBeVisible()
    await expect(page.getByText('innocent-private-value', { exact: true })).toHaveCount(0)
    await expectStableLayout(page)
  })
}

test('policy strict health and audit guards reject freeform aggregates and reasons', async ({ page }) => {
  await mockOps(page)
  await page.route('**/ops-api/ops/policies/health-windows*', (route) => route.fulfill({
    json: { items: [{ ...healthWindow, candidate_stats: { ...stats, mean_cost: 'innocent-private-value' } }], next_cursor: null },
  }))
  await page.route('**/ops-api/ops/policies/audit*', (route) => route.fulfill({
    json: { items: [{ ...auditEvent, reason: 'innocent-private-value' }], next_cursor: null },
  }))
  await page.goto('/ops/#/policies')
  await page.getByRole('tab', { name: '健康窗口' }).click()
  await expect(page.getByText(/响应格式错误/)).toBeVisible()
  await page.getByRole('tab', { name: '审计时间线' }).click()
  await expect(page.getByText(/响应格式错误/)).toBeVisible()
  await expect(page.getByText('innocent-private-value', { exact: true })).toHaveCount(0)
})

test('policy detail empty evidence is explicitly unavailable', async ({ page }) => {
  await mockOps(page)
  await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, (route) => route.fulfill({
    json: { ...policyDetail(), required_receipts: [], gate_receipts: [], latest_health_window: null, audit_events: [] },
  }))
  await page.goto(`/ops/#/policies/${deploymentId}`)
  await expect(page.getByText('暂无 Gate 收据')).toBeVisible()
  await expect(page.getByText('暂无健康窗口，指标不可用')).toBeVisible()
  await expect(page.getByText('暂无审计事件')).toBeVisible()
})

test('policy detail selection ignores delayed previous version responses', async ({ page }) => {
  await mockOps(page)
  let started!: () => void
  let release!: () => void
  let fulfilled!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  const initial = new Promise<void>((resolve) => { started = resolve })
  const completed = new Promise<void>((resolve) => { fulfilled = resolve })
  await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, async (route) => {
    started()
    await pending
    await route.fulfill({ json: policyDetail() })
    fulfilled()
  })
  await page.goto(`/ops/#/policies/${deploymentId}`)
  await initial
  await page.getByRole('button', { name: /下一页/ }).click()
  await page.getByRole('region', { name: '策略证据列表' }).getByRole('link', { name: `查看策略 ${secondDeploymentId}` }).click()
  const detail = page.getByRole('region', { name: '策略版本详情' })
  await expect(detail.getByText('rehearsal · 版本 3', { exact: false })).toBeVisible()
  release()
  await completed
  await expect(detail.getByText('rehearsal · 版本 3', { exact: false })).toBeVisible()
  await expect(detail.getByText('rehearsal · 版本 2', { exact: false })).toHaveCount(0)
})

for (const scenario of ['consumed', 'old-local', 'missing'] as const) {
  test(`health source ${scenario} is explicit and does not claim a new passing window`, async ({ page }) => {
    await mockOps(page)
    const body = policyDetail(secondDeploymentId)
    body.state = 'active'
    body.latest_health_window = { ...body.latest_health_window, decision: 'hold', triggered_thresholds: [] }
    if (scenario === 'missing') {
      body.gate_receipts = []
    } else {
      body.gate_receipts[0].status = 'passed'
      body.gate_receipts[0].health_source.window_decision = 'pass'
      body.gate_receipts[0].health_source.is_latest_window = false
      if (scenario === 'consumed') {
        body.gate_receipts[0].health_source.relation = 'consumed_chain'
        body.gate_receipts[0].health_source.deployment_id = deploymentId
        body.gate_receipts[0].health_source.deployment_version = 2
      }
    }
    await page.route(`**/ops-api/ops/policies/deployments/${secondDeploymentId}`, (route) => route.fulfill({ json: body }))
    await page.goto(`/ops/#/policies/${secondDeploymentId}`)
    const detail = page.getByRole('region', { name: '策略版本详情' })
    await expect(detail.getByText('hold', { exact: true })).toBeVisible()
    const explanation = scenario === 'consumed' ? '已消费前序证据（非本部署新观测）'
      : scenario === 'old-local' ? '本部署旧窗口证据，不代表最新健康通过' : 'unknown'
    await expect(detail.getByText(explanation, { exact: true })).toBeVisible()
    await expectStableLayout(page)
  })
}

for (const mutation of ['extra', 'wrong-local', 'null-health', 'nonpassing-consumed'] as const) {
  test(`closed health source rejects ${mutation}`, async ({ page }) => {
    await mockOps(page)
    const body = policyDetail()
    const receipt = body.gate_receipts[0]
    if (mutation === 'extra') Object.assign(receipt.health_source, { details: 'private-source-value' })
    if (mutation === 'wrong-local') receipt.health_source.deployment_id = secondDeploymentId
    if (mutation === 'null-health') Object.assign(receipt, { health_source: null })
    if (mutation === 'nonpassing-consumed') receipt.health_source.relation = 'consumed_chain'
    await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, (route) => route.fulfill({ json: body }))
    await page.goto(`/ops/#/policies/${deploymentId}`)
    await expect(page.getByText(/响应格式错误/)).toBeVisible()
    await expect(page.getByText('private-source-value', { exact: true })).toHaveCount(0)
  })
}
