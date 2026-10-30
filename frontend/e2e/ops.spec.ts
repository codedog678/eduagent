import { expect, Page, test } from '@playwright/test'

const usage = {
  model_calls: 1,
  tool_calls: 2,
  input_tokens: 120,
  output_tokens: 48,
  estimated_cost_usd: '0.0021',
  uncertain: false,
}

const run = (id: string, status = 'completed') => ({
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
}

async function mockOps(page: Page, options: MockOptions = {}) {
  let runFailures = options.runFailureCount || 0
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
          ? { items: [run('run-2', 'running')], next_cursor: null }
          : { items: [run('run-1')], next_cursor: 'cursor-2' }
      await route.fulfill({ json: body })
      return
    }
    if (path === '/runs/run-1') {
      await route.fulfill({ json: runDetail })
      return
    }
    if (path === '/runs/run-1/trace') {
      await route.fulfill({ json: trace })
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
