// f1fe877ca242ba68a3f50b0be674c5cc0ff35697
import { expect, test } from '@playwright/test';
const usage = {
  model_calls: 1,
  tool_calls: 2,
  input_tokens: 120,
  output_tokens: 48,
  estimated_cost_usd: '0.0021',
  uncertain: false
};
const deploymentId = '11111111-1111-1111-1111-111111111111';
const secondDeploymentId = '22222222-2222-2222-2222-222222222222';
const binding = {
  deployment_id: deploymentId,
  effective_policy_hash: 'b'.repeat(64),
  policy_cohort: 'candidate',
  namespace_class: 'rehearsal'
};
const run = (id, status = 'completed') => ({
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
  updated_at: '2026-10-30T10:00:01.280Z'
});
const runDetail = {
  ...run('run-1'),
  attempts: [{
    number: 1,
    worker_id: 'run-worker-a',
    fencing_token: 2,
    status: 'retryable_failed',
    reason: 'lease_expired',
    started_at: '2026-10-30T09:59:55Z',
    deadline_at: '2026-10-30T10:01:55Z',
    finished_at: '2026-10-30T09:59:58Z',
    duration_ms: 3000
  }, {
    number: 2,
    worker_id: 'run-worker-b',
    fencing_token: 3,
    status: 'completed',
    reason: null,
    started_at: '2026-10-30T10:00:00Z',
    deadline_at: '2026-10-30T10:02:00Z',
    finished_at: '2026-10-30T10:00:01.280Z',
    duration_ms: 1280
  }],
  expert_jobs: [{
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
    completed_at: '2026-10-30T10:00:00.900Z'
  }]
};
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
    deadline_at: '2026-10-30T10:01:00Z'
  },
  usage,
  source_refs: ['knowledge:grammar_tenses'],
  attempts: [{
    worker_id: 'expert-worker-a',
    fencing_token: 1,
    disposition: 'rejected',
    rejection_code: 'expert_token_stale',
    usage,
    source_refs: [],
    created_at: '2026-10-30T10:00:00.700Z'
  }, {
    worker_id: 'expert-worker-b',
    fencing_token: 2,
    disposition: 'accepted',
    rejection_code: null,
    usage,
    source_refs: ['knowledge:grammar_tenses'],
    created_at: '2026-10-30T10:00:00.900Z'
  }],
  error_code: null,
  created_at: '2026-10-30T10:00:00.100Z',
  updated_at: '2026-10-30T10:00:00.900Z',
  completed_at: '2026-10-30T10:00:00.900Z'
};
const trace = {
  ...binding,
  run_id: 'run-1',
  trace_id: 'a'.repeat(32),
  spans: [{
    span_id: '1'.repeat(16),
    trace_id: 'a'.repeat(32),
    parent_span_id: null,
    name: 'run.attempt',
    status: 'ok',
    attributes: {
      'worker.id': 'run-worker-b',
      'run.fencing_token': 3
    },
    started_at: '2026-10-30T10:00:00Z',
    ended_at: '2026-10-30T10:00:01.280Z',
    duration_ms: 1280
  }, {
    span_id: '2'.repeat(16),
    trace_id: 'a'.repeat(32),
    parent_span_id: '1'.repeat(16),
    name: 'expert.wait',
    status: 'ok',
    attributes: {
      'expert.job_id': 'job-1',
      'expert.fencing_token': 2
    },
    started_at: '2026-10-30T10:00:00.200Z',
    ended_at: '2026-10-30T10:00:00.900Z',
    duration_ms: 700
  }]
};
const workers = {
  items: [{
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
    stopped_at: null
  }, {
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
    stopped_at: null
  }],
  next_cursor: null
};
const thresholds = {
  candidate_min_runs: 20,
  stable_min_runs: 20,
  window_max_runs: 50,
  commit_failure_rate: '0.05',
  terminal_failure_rate: '0.10',
  latency_increase_rate: '0.50',
  mean_cost_increase_rate: '0.30',
  unknown_rate: '0.10',
  relative_epsilon: '0.000001'
};
const stats = {
  run_count: 20,
  commit_failure_rate: '0.05',
  terminal_failure_rate: '0.10',
  p95_latency: '1.25',
  mean_cost: '0.01',
  structured_decision_count: 10,
  unknown_decision_count: 1,
  unknown_rate: '0.10',
  fault_injected_count: 1,
  injected_commit_failure_count: 1,
  natural_failure_count: 0,
  latency_increase_rate: null,
  mean_cost_increase_rate: null
};
const healthWindow = {
  window_id: 'c'.repeat(64),
  deployment_id: deploymentId,
  deployment_version: 2,
  environment: 'rehearsal',
  metric_contract_version: 1,
  thresholds_hash: 'd'.repeat(64),
  candidate_stats: stats,
  stable_stats: {
    ...stats,
    mean_cost: null
  },
  decision: 'fail',
  triggered_thresholds: ['commit_failure_rate'],
  evaluated_at: '2026-10-30T10:03:00Z',
  created_at: '2026-10-30T10:03:00Z'
};
const auditEvent = {
  event_id: '33333333-3333-3333-3333-333333333333',
  environment: 'rehearsal',
  deployment_id: deploymentId,
  event_type: 'health_rollback',
  failed_deployment_id: null,
  health_window_id: 'c'.repeat(64),
  from_state: null,
  to_state: null,
  actor: 'redacted',
  reason: 'redacted',
  created_at: '2026-10-30T10:03:01Z'
};
const policyDeployment = (id = deploymentId) => ({
  deployment_id: id,
  environment: 'rehearsal',
  version: id === deploymentId ? 2 : 3,
  state: id === deploymentId ? 'canary' : 'frozen',
  candidate_policy_hash: 'b'.repeat(12),
  stable_policy_hash: 'a'.repeat(12),
  is_current: id !== deploymentId,
  current_deployment_id: secondDeploymentId,
  current_version: 3,
  traffic_basis_points: id === deploymentId ? 5000 : 0,
  cohort_counts: {
    stable: 20,
    candidate: 20,
    shadow: 10
  },
  thresholds,
  thresholds_hash: 'd'.repeat(64),
  required_receipts: ['canary_health'],
  actor: 'redacted',
  reason: 'redacted',
  created_at: '2026-10-30T10:00:00Z'
});
const policyDetail = (id = deploymentId) => ({
  ...policyDeployment(id),
  candidate_policy_hash: 'b'.repeat(64),
  stable_policy_hash: 'a'.repeat(64),
  gate_receipts: [{
    receipt_id: '44444444-4444-4444-4444-444444444444',
    policy_hash: 'b'.repeat(64),
    gate_type: 'canary_health',
    status: 'failed',
    evidence_hash: 'e'.repeat(64),
    sample_count: 20,
    cost: '0.02',
    issuer: 'redacted',
    issued_at: '2026-10-30T10:02:00Z',
    health_source: {
      relation: 'local',
      deployment_id: id,
      deployment_version: id === deploymentId ? 2 : 3,
      window_id: 'c'.repeat(64),
      thresholds_hash: 'd'.repeat(64),
      window_decision: 'fail',
      evaluated_at: '2026-10-30T10:03:00Z',
      is_latest_window: true
    }
  }],
  latest_health_window: {
    ...healthWindow,
    deployment_id: id
  },
  audit_events: [auditEvent, {
    ...auditEvent,
    event_id: '55555555-5555-5555-5555-555555555555',
    event_type: 'promotion_transitioned',
    from_state: 'canary',
    to_state: 'frozen',
    health_window_id: null
  }]
});
async function mockOps(page, options = {}) {
  let runFailures = options.runFailureCount || 0;
  let policyFailures = options.policyFailureCount || 0;
  let detailFailures = options.policyDetailFailureCount || 0;
  const withBinding = value => options.legacyBinding ? {
    ...value,
    deployment_id: null,
    effective_policy_hash: null,
    policy_cohort: null,
    namespace_class: null
  } : value;
  await page.route('**/ops-api/ops/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/ops-api/ops', '');
    if (options.requireToken && request.headers().authorization !== 'Bearer browser-test-token') {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'valid Ops bearer token required'
        })
      });
      return;
    }
    if (path === '/runs') {
      if (options.delayRunsMs) {
        await new Promise(resolve => setTimeout(resolve, options.delayRunsMs));
      }
      if (runFailures > 0) {
        runFailures -= 1;
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'temporary database failure'
          })
        });
        return;
      }
      const cursor = url.searchParams.get('cursor');
      const body = options.runPages === 'empty' ? {
        items: [],
        next_cursor: null
      } : cursor === 'cursor-2' ? {
        items: [withBinding(run('run-2', 'running'))],
        next_cursor: null
      } : {
        items: [withBinding(run('run-1'))],
        next_cursor: 'cursor-2'
      };
      await route.fulfill({
        json: body
      });
      return;
    }
    if (path === '/runs/run-1') {
      await route.fulfill({
        json: withBinding(runDetail)
      });
      return;
    }
    if (path === '/runs/run-1/trace') {
      await route.fulfill({
        json: withBinding(trace)
      });
      return;
    }
    if (path === '/expert-jobs/job-1') {
      await route.fulfill({
        json: expertDetail
      });
      return;
    }
    if (path === '/workers') {
      await route.fulfill({
        json: workers
      });
      return;
    }
    if (path.startsWith('/policies/deployments/')) {
      if (detailFailures-- > 0) {
        await route.fulfill({
          status: 503,
          json: {
            detail: 'policy detail unavailable'
          }
        });
        return;
      }
      const id = path.split('/').at(-1);
      await route.fulfill({
        json: policyDetail(id)
      });
      return;
    }
    if (path.startsWith('/policies/')) {
      if (options.delayPoliciesMs && !url.searchParams.has('environment')) {
        var _options$onSlowPolicy;
        await new Promise(resolve => setTimeout(resolve, options.delayPoliciesMs));
        (_options$onSlowPolicy = options.onSlowPolicyDone) === null || _options$onSlowPolicy === void 0 || _options$onSlowPolicy.call(options);
      }
      if (policyFailures-- > 0) {
        await route.fulfill({
          status: 503,
          json: {
            detail: 'policy evidence unavailable'
          }
        });
        return;
      }
      if (options.policyEmpty || url.searchParams.get('environment') === 'production') {
        await route.fulfill({
          json: {
            items: [],
            next_cursor: null
          }
        });
        return;
      }
      const second = url.searchParams.get('cursor') === 'policy-page-2';
      let items = path.endsWith('deployments') ? [policyDeployment(second ? secondDeploymentId : deploymentId)] : path.endsWith('health-windows') ? [healthWindow] : [auditEvent];
      const state = url.searchParams.get('state');
      if (state) items = [policyDeployment(state === 'frozen' ? secondDeploymentId : deploymentId)];
      if (options.malformedPolicy) items = [{
        ...items[0],
        details: {
          innocent: 'must-not-render'
        }
      }];
      await route.fulfill({
        json: {
          items,
          next_cursor: second || state ? null : 'policy-page-2'
        }
      });
      return;
    }
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: `unmocked path: ${path}`
      })
    });
  });
}
function monitorBrowser(page, ignoredConsoleErrors = []) {
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error' && !ignoredConsoleErrors.some(pattern => pattern.test(message.text()))) {
      errors.push(message.text());
    }
  });
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => {
    var _request$failure;
    const message = ((_request$failure = request.failure()) === null || _request$failure === void 0 ? void 0 : _request$failure.errorText) || 'request failed';
    if (!message.toLowerCase().includes('aborted')) {
      errors.push(`${request.url()}: ${message}`);
    }
  });
  return errors;
}
async function expectStableLayout(page) {
  const layout = await page.evaluate(() => {
    var _document$querySelect, _document$querySelect2;
    const viewportWidth = document.documentElement.clientWidth;
    const bodyOverflow = document.documentElement.scrollWidth - viewportWidth;
    const header = (_document$querySelect = document.querySelector('.ops-header')) === null || _document$querySelect === void 0 ? void 0 : _document$querySelect.getBoundingClientRect();
    const main = (_document$querySelect2 = document.querySelector('.ops-main')) === null || _document$querySelect2 === void 0 ? void 0 : _document$querySelect2.getBoundingClientRect();
    const clipped = Array.from(document.querySelectorAll('.ops-nav a, .ops-page-heading h1, .ops-pagination button')).filter(element => element.scrollWidth > element.clientWidth + 2 || element.scrollHeight > element.clientHeight + 2).map(element => {
      var _element$textContent;
      return ((_element$textContent = element.textContent) === null || _element$textContent === void 0 ? void 0 : _element$textContent.trim()) || element.className;
    });
    return {
      bodyOverflow,
      clipped,
      coherentFlow: !header || !main || header.bottom <= main.top + 1
    };
  });
  expect(layout.bodyOverflow).toBeLessThanOrEqual(1);
  expect(layout.clipped).toEqual([]);
  expect(layout.coherentFlow).toBe(true);
}
test('renders populated Ops workflows with pagination, detail, trace, and stale workers', async ({
  page
}, testInfo) => {
  const browserErrors = monitorBrowser(page);
  await mockOps(page);
  await page.goto('/ops/#/runs', {
    waitUntil: 'commit'
  });
  await expect(page.getByRole('heading', {
    name: 'Runs'
  })).toBeVisible();
  await expect(page.getByText('run-1', {
    exact: true
  })).toBeVisible();
  await page.getByRole('button', {
    name: /下一页/
  }).click();
  await expect(page.getByText('run-2', {
    exact: true
  })).toBeVisible();
  await page.getByRole('button', {
    name: /上一页/
  }).click();
  await expect(page.getByText('run-1', {
    exact: true
  })).toBeVisible();
  await page.getByRole('button', {
    name: '查看运行 run-1 详情'
  }).click();
  const drawer = page.getByRole('dialog', {
    name: '运行详情'
  });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText('run-worker-b', {
    exact: true
  })).toBeVisible();
  await drawer.getByRole('button', {
    name: '检查'
  }).click();
  await expect(drawer.getByText('knowledge:grammar_tenses')).toBeVisible();
  await drawer.getByRole('link', {
    name: 'a'.repeat(32)
  }).click();
  await expect(page.getByRole('heading', {
    name: '运行 Trace'
  })).toBeVisible();
  await expect(page.getByText('expert.wait', {
    exact: true
  })).toBeVisible();
  await expect(page.getByRole('tree')).toBeVisible();
  await page.getByRole('link', {
    name: /Workers/
  }).click();
  await expect(page.getByRole('heading', {
    name: 'Workers'
  })).toBeVisible();
  await expect(page.getByText('expert-worker-stale', {
    exact: true
  })).toBeVisible();
  await expect(page.getByText('stale', {
    exact: true
  }).first()).toBeVisible();
  await expect(page.getByRole('button', {
    name: /取消|重试任务|重新入队/
  })).toHaveCount(0);
  await expectStableLayout(page);
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({
      path: `${process.env.OPS_SCREENSHOT_DIR}/ops-${testInfo.project.name}.png`,
      fullPage: true
    });
  }
  expect(browserErrors).toEqual([]);
});
test('shows loading and empty states without layout shift', async ({
  page
}) => {
  const browserErrors = monitorBrowser(page);
  await mockOps(page, {
    runPages: 'empty'
  });
  await page.goto('/ops/#/runs', {
    waitUntil: 'commit'
  });
  await expect(page.locator('.ant-skeleton')).toBeVisible();
  await expect(page.getByText('没有符合条件的运行')).toBeVisible();
  await expectStableLayout(page);
  expect(browserErrors).toEqual([]);
});
test('shows retryable API errors and recovers', async ({
  page
}) => {
  const browserErrors = monitorBrowser(page, [/Failed to load resource:.*500 \(Internal Server Error\)/]);
  await mockOps(page, {
    runFailureCount: 2
  });
  await page.goto('/ops/#/runs');
  await expect(page.getByText('Runs 加载失败')).toBeVisible();
  await expect(page.getByText('temporary database failure')).toBeVisible();
  await page.getByRole('button', {
    name: /重\s*试/
  }).click();
  await expect(page.getByText('run-1', {
    exact: true
  })).toBeVisible();
  await expectStableLayout(page);
  expect(browserErrors).toEqual([]);
});
test('keeps bearer token in session storage and retries authorization', async ({
  page
}) => {
  const browserErrors = monitorBrowser(page, [/Failed to load resource:.*401 \(Unauthorized\)/]);
  await mockOps(page, {
    requireToken: true
  });
  await page.goto('/ops/#/runs');
  await expect(page.getByRole('heading', {
    name: '需要 Ops 访问凭证'
  })).toBeVisible();
  await page.getByLabel('OPS API Token').fill('browser-test-token');
  await page.getByRole('button', {
    name: '验证并重试'
  }).click();
  await expect(page.getByText('run-1', {
    exact: true
  })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token'))).toBe('browser-test-token');
  await expectStableLayout(page);
  expect(browserErrors).toEqual([]);
});
test('policy evidence filters, cursor pages, detail, metrics and audit are read only', async ({
  page
}, testInfo) => {
  const errors = monitorBrowser(page);
  const requests = [];
  page.on('request', request => {
    if (request.url().includes('/ops-api/')) requests.push({
      method: request.method(),
      url: request.url()
    });
  });
  await mockOps(page);
  await page.goto('/ops/#/policies');
  await expect(page.getByRole('heading', {
    name: 'Policies',
    exact: true
  })).toBeVisible();
  await expect(page.getByText(deploymentId, {
    exact: true
  })).toBeVisible();
  if (testInfo.project.name === 'mobile') {
    const overflowTable = page.locator('.ant-table-content').first();
    expect(await overflowTable.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
    await overflowTable.hover();
    await page.mouse.wheel(900, 0);
    await expect.poll(() => overflowTable.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
    await page.mouse.wheel(-900, 0);
  }
  await page.getByRole('button', {
    name: /下一页/
  }).click();
  await expect(page.getByText(secondDeploymentId, {
    exact: true
  })).toBeVisible();
  await page.getByRole('button', {
    name: /上一页/
  }).click();
  await page.getByLabel('策略状态').click();
  await page.getByTitle('frozen', {
    exact: true
  }).click();
  await expect(page.getByText(secondDeploymentId, {
    exact: true
  })).toBeVisible();
  await expect(page.getByRole('button', {
    name: /下一页/
  })).toBeDisabled();
  await page.getByRole('button', {
    name: '重置'
  }).click();
  await page.getByLabel('策略环境').click();
  await page.getByTitle('rehearsal', {
    exact: true
  }).click();
  await page.getByRole('link', {
    name: `查看策略 ${deploymentId}`
  }).click();
  const detail = page.getByRole('region', {
    name: '策略版本详情'
  });
  await expect(detail.getByText('b'.repeat(64), {
    exact: true
  }).first()).toBeVisible();
  await expect(detail.getByText('canary_health', {
    exact: true
  }).first()).toBeVisible();
  await expect(detail.getByText('commit_failure_rate', {
    exact: true
  }).first()).toBeVisible();
  await expect(detail.getByText('health_rollback', {
    exact: true
  })).toBeVisible();
  await expect(detail.getByText('promotion_transitioned', {
    exact: true
  })).toBeVisible();
  await expect(detail.getByText('canary → frozen', {
    exact: true
  })).toBeVisible();
  await expect(detail.getByText('未知', {
    exact: true
  }).first()).toBeVisible();
  await page.getByRole('tab', {
    name: '健康窗口'
  }).click();
  await expect(page.getByRole('region', {
    name: '策略证据列表'
  }).getByText('fail', {
    exact: true
  })).toBeVisible();
  await page.getByRole('tab', {
    name: '审计时间线'
  }).click();
  await expect(page.getByRole('region', {
    name: '策略证据列表'
  }).getByText('health_rollback', {
    exact: true
  })).toBeVisible();
  await expect(page.getByRole('button', {
    name: /晋升|回滚|冻结|发布|删除/
  })).toHaveCount(0);
  expect(requests.every(request => request.method === 'GET')).toBe(true);
  expect(requests.some(request => request.url.includes('state=frozen'))).toBe(true);
  expect(requests.some(request => request.url.includes('environment=rehearsal'))).toBe(true);
  await expectStableLayout(page);
  await page.getByRole('tab', {
    name: '部署'
  }).click();
  await expect(page.getByRole('region', {
    name: '策略证据列表'
  }).getByRole('link', {
    name: `查看策略 ${deploymentId}`
  })).toBeVisible();
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({
      path: `${process.env.OPS_SCREENSHOT_DIR}/policies-${testInfo.project.name}.png`,
      fullPage: true,
      animations: 'disabled'
    });
  }
  expect(errors).toEqual([]);
});
test('policy loading, empty filters and stale requests do not restore old evidence', async ({
  page
}) => {
  let slowDone;
  const finished = new Promise(resolve => {
    slowDone = resolve;
  });
  await mockOps(page, {
    delayPoliciesMs: 700,
    onSlowPolicyDone: slowDone
  });
  await page.goto('/ops/#/policies', {
    waitUntil: 'commit'
  });
  await expect(page.locator('.ant-skeleton')).toBeVisible();
  await page.getByLabel('策略环境').click();
  await page.getByTitle('production', {
    exact: true
  }).click();
  await expect(page.getByText('没有符合条件的策略证据')).toBeVisible();
  await finished;
  await expect(page.getByText(deploymentId, {
    exact: true
  })).toHaveCount(0);
  await expectStableLayout(page);
});
test('policy errors and detail errors have independent retry recovery', async ({
  page
}) => {
  await mockOps(page, {
    policyFailureCount: 2,
    policyDetailFailureCount: 2
  });
  await page.goto('/ops/#/policies');
  await expect(page.getByText('策略证据加载失败')).toBeVisible();
  await page.getByRole('button', {
    name: /重\s*试/
  }).click();
  await expect(page.getByText(deploymentId, {
    exact: true
  })).toBeVisible();
  await page.getByRole('link', {
    name: `查看策略 ${deploymentId}`
  }).click();
  await expect(page.getByText('策略详情加载失败')).toBeVisible();
  await page.getByRole('region', {
    name: '策略版本详情'
  }).getByRole('button', {
    name: /重\s*试/
  }).click();
  await expect(page.getByText('b'.repeat(64), {
    exact: true
  }).first()).toBeVisible();
});
test('policy strict response guard rejects extra freeform fields', async ({
  page
}) => {
  await mockOps(page, {
    malformedPolicy: true
  });
  await page.goto('/ops/#/policies');
  await expect(page.getByText('策略证据加载失败')).toBeVisible();
  await expect(page.getByText(/响应格式错误/)).toBeVisible();
  await expect(page.getByText('must-not-render')).toHaveCount(0);
});
test('policy authentication uses existing Ops token and clears it on lock', async ({
  page
}) => {
  await mockOps(page, {
    requireToken: true
  });
  await page.goto(`/ops/#/policies/${deploymentId}`);
  await expect(page.getByRole('heading', {
    name: '需要 Ops 访问凭证'
  })).toBeVisible();
  await page.getByLabel('OPS API Token').fill('browser-test-token');
  await page.getByRole('button', {
    name: '验证并重试'
  }).click();
  await expect(page.getByRole('region', {
    name: '策略版本详情'
  })).toBeVisible();
  await expect(page.getByText('b'.repeat(64), {
    exact: true
  }).first()).toBeVisible();
  await page.getByRole('button', {
    name: '锁定控制台并清除会话 token'
  }).click();
  expect(await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token'))).toBeNull();
  await expect(page.getByRole('heading', {
    name: '需要 Ops 访问凭证'
  })).toBeVisible();
});
test('policy Run and Trace display stored immutable identity and link version evidence', async ({
  page
}, testInfo) => {
  await mockOps(page);
  await page.goto('/ops/#/runs');
  await page.getByRole('button', {
    name: '查看运行 run-1 详情'
  }).click();
  const drawer = page.getByRole('dialog', {
    name: '运行详情'
  });
  await expect(drawer.getByText('b'.repeat(64), {
    exact: true
  })).toBeVisible();
  await expect(drawer.getByText('candidate', {
    exact: true
  })).toBeVisible();
  await drawer.getByRole('link', {
    name: 'a'.repeat(32)
  }).click();
  await expect(page.getByRole('heading', {
    name: '运行 Trace'
  })).toBeVisible();
  await expect(page.getByText('b'.repeat(64), {
    exact: true
  })).toBeVisible();
  await expect(page.getByRole('region', {
    name: '运行策略绑定'
  }).getByText('candidate · rehearsal', {
    exact: true
  })).toBeVisible();
  if (process.env.OPS_SCREENSHOT_DIR) {
    await page.screenshot({
      path: `${process.env.OPS_SCREENSHOT_DIR}/policy-trace-${testInfo.project.name}.png`,
      fullPage: true
    });
  }
  await page.getByRole('link', {
    name: deploymentId,
    exact: true
  }).click();
  await expect(page.getByRole('region', {
    name: '策略版本详情'
  }).getByText('rehearsal · 版本 2', {
    exact: false
  })).toBeVisible();
  await expect(page.getByText('当前版本 3', {
    exact: false
  }).first()).toBeVisible();
  await page.goto('/ops/#/trace/run-1');
  await expect(page.getByText('b'.repeat(64), {
    exact: true
  })).toBeVisible();
  await expectStableLayout(page);
});
test('policy legacy Run and Trace identity remains unavailable without current policy fallback', async ({
  page
}) => {
  await mockOps(page, {
    legacyBinding: true
  });
  await page.goto('/ops/#/trace/run-1');
  await expect(page.getByText('策略绑定不可用')).toBeVisible();
  await expect(page.getByText('b'.repeat(64), {
    exact: true
  })).toHaveCount(0);
  await expect(page.getByRole('link', {
    name: deploymentId,
    exact: true
  })).toHaveCount(0);
});
for (const scenario of [{
  name: 'actor freeform',
  path: '/policies/deployments',
  page: '#/policies',
  body: {
    items: [{
      ...policyDeployment(),
      actor: 'innocent-private-value'
    }],
    next_cursor: null
  }
}, {
  name: 'hash identity',
  path: '/policies/deployments',
  page: '#/policies',
  body: {
    items: [{
      ...policyDeployment(),
      stable_policy_hash: 'innocent-private-value'
    }],
    next_cursor: null
  }
}, {
  name: 'missing required binding',
  path: '/runs/run-1/trace',
  page: '#/trace/run-1',
  body: {
    ...trace,
    effective_policy_hash: undefined
  }
}, {
  name: 'raw namespace',
  path: '/runs/run-1/trace',
  page: '#/trace/run-1',
  body: {
    ...trace,
    namespace_class: 'innocent-private-value'
  }
}, {
  name: 'detail nested extras',
  path: `/policies/deployments/${deploymentId}`,
  page: `#/policies/${deploymentId}`,
  body: {
    ...policyDetail(),
    gate_receipts: [{
      ...policyDetail().gate_receipts[0],
      details: {
        innocent: 'innocent-private-value'
      }
    }]
  }
}, {
  name: 'detail invalid metric',
  path: `/policies/deployments/${deploymentId}`,
  page: `#/policies/${deploymentId}`,
  body: {
    ...policyDetail(),
    latest_health_window: {
      ...healthWindow,
      candidate_stats: {
        ...stats,
        unknown_rate: '2'
      }
    }
  }
}]) {
  test(`policy strict typed response rejects ${scenario.name}`, async ({
    page
  }) => {
    await mockOps(page);
    await page.route(`**/ops-api/ops${scenario.path}*`, route => route.fulfill({
      json: scenario.body
    }));
    await page.goto(`/ops/${scenario.page}`);
    await expect(page.getByText(/响应格式错误/)).toBeVisible();
    await expect(page.getByText('innocent-private-value', {
      exact: true
    })).toHaveCount(0);
    await expectStableLayout(page);
  });
}
test('policy strict health and audit guards reject freeform aggregates and reasons', async ({
  page
}) => {
  await mockOps(page);
  await page.route('**/ops-api/ops/policies/health-windows*', route => route.fulfill({
    json: {
      items: [{
        ...healthWindow,
        candidate_stats: {
          ...stats,
          mean_cost: 'innocent-private-value'
        }
      }],
      next_cursor: null
    }
  }));
  await page.route('**/ops-api/ops/policies/audit*', route => route.fulfill({
    json: {
      items: [{
        ...auditEvent,
        reason: 'innocent-private-value'
      }],
      next_cursor: null
    }
  }));
  await page.goto('/ops/#/policies');
  await page.getByRole('tab', {
    name: '健康窗口'
  }).click();
  await expect(page.getByText(/响应格式错误/)).toBeVisible();
  await page.getByRole('tab', {
    name: '审计时间线'
  }).click();
  await expect(page.getByText(/响应格式错误/)).toBeVisible();
  await expect(page.getByText('innocent-private-value', {
    exact: true
  })).toHaveCount(0);
});
test('policy detail empty evidence is explicitly unavailable', async ({
  page
}) => {
  await mockOps(page);
  await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, route => route.fulfill({
    json: {
      ...policyDetail(),
      required_receipts: [],
      gate_receipts: [],
      latest_health_window: null,
      audit_events: []
    }
  }));
  await page.goto(`/ops/#/policies/${deploymentId}`);
  await expect(page.getByText('暂无 Gate 收据')).toBeVisible();
  await expect(page.getByText('暂无健康窗口，指标不可用')).toBeVisible();
  await expect(page.getByText('暂无审计事件')).toBeVisible();
});
test('policy detail selection ignores delayed previous version responses', async ({
  page
}) => {
  await mockOps(page);
  let started;
  let release;
  let fulfilled;
  const pending = new Promise(resolve => {
    release = resolve;
  });
  const initial = new Promise(resolve => {
    started = resolve;
  });
  const completed = new Promise(resolve => {
    fulfilled = resolve;
  });
  await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, async route => {
    started();
    await pending;
    await route.fulfill({
      json: policyDetail()
    });
    fulfilled();
  });
  await page.goto(`/ops/#/policies/${deploymentId}`);
  await initial;
  await page.getByRole('button', {
    name: /下一页/
  }).click();
  await page.getByRole('region', {
    name: '策略证据列表'
  }).getByRole('link', {
    name: `查看策略 ${secondDeploymentId}`
  }).click();
  const detail = page.getByRole('region', {
    name: '策略版本详情'
  });
  await expect(detail.getByText('rehearsal · 版本 3', {
    exact: false
  })).toBeVisible();
  release();
  await completed;
  await expect(detail.getByText('rehearsal · 版本 3', {
    exact: false
  })).toBeVisible();
  await expect(detail.getByText('rehearsal · 版本 2', {
    exact: false
  })).toHaveCount(0);
});
for (const scenario of ['consumed', 'old-local', 'missing']) {
  test(`health source ${scenario} is explicit and does not claim a new passing window`, async ({
    page
  }) => {
    await mockOps(page);
    const body = policyDetail(secondDeploymentId);
    body.state = 'active';
    body.latest_health_window = {
      ...body.latest_health_window,
      decision: 'hold',
      triggered_thresholds: []
    };
    if (scenario === 'missing') {
      body.gate_receipts = [];
    } else {
      body.gate_receipts[0].status = 'passed';
      body.gate_receipts[0].health_source.window_decision = 'pass';
      body.gate_receipts[0].health_source.is_latest_window = false;
      if (scenario === 'consumed') {
        body.gate_receipts[0].health_source.relation = 'consumed_chain';
        body.gate_receipts[0].health_source.deployment_id = deploymentId;
        body.gate_receipts[0].health_source.deployment_version = 2;
      }
    }
    await page.route(`**/ops-api/ops/policies/deployments/${secondDeploymentId}`, route => route.fulfill({
      json: body
    }));
    await page.goto(`/ops/#/policies/${secondDeploymentId}`);
    const detail = page.getByRole('region', {
      name: '策略版本详情'
    });
    await expect(detail.getByText('hold', {
      exact: true
    })).toBeVisible();
    const explanation = scenario === 'consumed' ? '已消费前序证据（非本部署新观测）' : scenario === 'old-local' ? '本部署旧窗口证据，不代表最新健康通过' : 'unknown';
    await expect(detail.getByText(explanation, {
      exact: true
    })).toBeVisible();
    await expectStableLayout(page);
  });
}
for (const mutation of ['extra', 'wrong-local', 'null-health', 'nonpassing-consumed']) {
  test(`closed health source rejects ${mutation}`, async ({
    page
  }) => {
    await mockOps(page);
    const body = policyDetail();
    const receipt = body.gate_receipts[0];
    if (mutation === 'extra') Object.assign(receipt.health_source, {
      details: 'private-source-value'
    });
    if (mutation === 'wrong-local') receipt.health_source.deployment_id = secondDeploymentId;
    if (mutation === 'null-health') Object.assign(receipt, {
      health_source: null
    });
    if (mutation === 'nonpassing-consumed') receipt.health_source.relation = 'consumed_chain';
    await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, route => route.fulfill({
      json: body
    }));
    await page.goto(`/ops/#/policies/${deploymentId}`);
    await expect(page.getByText(/响应格式错误/)).toBeVisible();
    await expect(page.getByText('private-source-value', {
      exact: true
    })).toHaveCount(0);
  });
}
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJleHBlY3QiLCJ0ZXN0IiwidXNhZ2UiLCJtb2RlbF9jYWxscyIsInRvb2xfY2FsbHMiLCJpbnB1dF90b2tlbnMiLCJvdXRwdXRfdG9rZW5zIiwiZXN0aW1hdGVkX2Nvc3RfdXNkIiwidW5jZXJ0YWluIiwiZGVwbG95bWVudElkIiwic2Vjb25kRGVwbG95bWVudElkIiwiYmluZGluZyIsImRlcGxveW1lbnRfaWQiLCJlZmZlY3RpdmVfcG9saWN5X2hhc2giLCJyZXBlYXQiLCJwb2xpY3lfY29ob3J0IiwibmFtZXNwYWNlX2NsYXNzIiwicnVuIiwiaWQiLCJzdGF0dXMiLCJydW5faWQiLCJvcGVyYXRpb24iLCJ0cmFjZV9pZCIsImF0dGVtcHRfY291bnQiLCJvd25lciIsImZlbmNpbmdfdG9rZW4iLCJsZWFzZV9leHBpcmVzX2F0IiwibGVhc2VfZnJlc2giLCJleHBlcnRfam9iX2NvdW50IiwibGF0ZW5jeV9tcyIsImNyZWF0ZWRfYXQiLCJ1cGRhdGVkX2F0IiwicnVuRGV0YWlsIiwiYXR0ZW1wdHMiLCJudW1iZXIiLCJ3b3JrZXJfaWQiLCJyZWFzb24iLCJzdGFydGVkX2F0IiwiZGVhZGxpbmVfYXQiLCJmaW5pc2hlZF9hdCIsImR1cmF0aW9uX21zIiwiZXhwZXJ0X2pvYnMiLCJqb2JfaWQiLCJwYXJlbnRfcnVuX2lkIiwicm9sZSIsIm1heF9hdHRlbXB0cyIsImVycm9yX2NvZGUiLCJjb21wbGV0ZWRfYXQiLCJleHBlcnREZXRhaWwiLCJsb2dpY2FsX2tleSIsImlucHV0X2hhc2giLCJwb2xpY3lfaGFzaCIsImJ1ZGdldCIsIm1heF9tb2RlbF9jYWxscyIsIm1heF90b29sX2NhbGxzIiwibWF4X291dHB1dF90b2tlbnMiLCJtYXhfY29udGV4dF90b2tlbnMiLCJzb3VyY2VfcmVmcyIsImRpc3Bvc2l0aW9uIiwicmVqZWN0aW9uX2NvZGUiLCJ0cmFjZSIsInNwYW5zIiwic3Bhbl9pZCIsInBhcmVudF9zcGFuX2lkIiwibmFtZSIsImF0dHJpYnV0ZXMiLCJlbmRlZF9hdCIsIndvcmtlcnMiLCJpdGVtcyIsImluc3RhbmNlX2lkIiwicHJvY2Vzc190eXBlIiwiaGVhbHRoIiwiZnJlc2giLCJjYXBhYmlsaXRpZXMiLCJjdXJyZW50X3J1bl9pZCIsImN1cnJlbnRfam9iX2lkIiwiaGVhcnRiZWF0X2FnZV9zZWNvbmRzIiwibGFzdF9oZWFydGJlYXRfYXQiLCJzdG9wcGVkX2F0IiwibmV4dF9jdXJzb3IiLCJ0aHJlc2hvbGRzIiwiY2FuZGlkYXRlX21pbl9ydW5zIiwic3RhYmxlX21pbl9ydW5zIiwid2luZG93X21heF9ydW5zIiwiY29tbWl0X2ZhaWx1cmVfcmF0ZSIsInRlcm1pbmFsX2ZhaWx1cmVfcmF0ZSIsImxhdGVuY3lfaW5jcmVhc2VfcmF0ZSIsIm1lYW5fY29zdF9pbmNyZWFzZV9yYXRlIiwidW5rbm93bl9yYXRlIiwicmVsYXRpdmVfZXBzaWxvbiIsInN0YXRzIiwicnVuX2NvdW50IiwicDk1X2xhdGVuY3kiLCJtZWFuX2Nvc3QiLCJzdHJ1Y3R1cmVkX2RlY2lzaW9uX2NvdW50IiwidW5rbm93bl9kZWNpc2lvbl9jb3VudCIsImZhdWx0X2luamVjdGVkX2NvdW50IiwiaW5qZWN0ZWRfY29tbWl0X2ZhaWx1cmVfY291bnQiLCJuYXR1cmFsX2ZhaWx1cmVfY291bnQiLCJoZWFsdGhXaW5kb3ciLCJ3aW5kb3dfaWQiLCJkZXBsb3ltZW50X3ZlcnNpb24iLCJlbnZpcm9ubWVudCIsIm1ldHJpY19jb250cmFjdF92ZXJzaW9uIiwidGhyZXNob2xkc19oYXNoIiwiY2FuZGlkYXRlX3N0YXRzIiwic3RhYmxlX3N0YXRzIiwiZGVjaXNpb24iLCJ0cmlnZ2VyZWRfdGhyZXNob2xkcyIsImV2YWx1YXRlZF9hdCIsImF1ZGl0RXZlbnQiLCJldmVudF9pZCIsImV2ZW50X3R5cGUiLCJmYWlsZWRfZGVwbG95bWVudF9pZCIsImhlYWx0aF93aW5kb3dfaWQiLCJmcm9tX3N0YXRlIiwidG9fc3RhdGUiLCJhY3RvciIsInBvbGljeURlcGxveW1lbnQiLCJ2ZXJzaW9uIiwic3RhdGUiLCJjYW5kaWRhdGVfcG9saWN5X2hhc2giLCJzdGFibGVfcG9saWN5X2hhc2giLCJpc19jdXJyZW50IiwiY3VycmVudF9kZXBsb3ltZW50X2lkIiwiY3VycmVudF92ZXJzaW9uIiwidHJhZmZpY19iYXNpc19wb2ludHMiLCJjb2hvcnRfY291bnRzIiwic3RhYmxlIiwiY2FuZGlkYXRlIiwic2hhZG93IiwicmVxdWlyZWRfcmVjZWlwdHMiLCJwb2xpY3lEZXRhaWwiLCJnYXRlX3JlY2VpcHRzIiwicmVjZWlwdF9pZCIsImdhdGVfdHlwZSIsImV2aWRlbmNlX2hhc2giLCJzYW1wbGVfY291bnQiLCJjb3N0IiwiaXNzdWVyIiwiaXNzdWVkX2F0IiwiaGVhbHRoX3NvdXJjZSIsInJlbGF0aW9uIiwid2luZG93X2RlY2lzaW9uIiwiaXNfbGF0ZXN0X3dpbmRvdyIsImxhdGVzdF9oZWFsdGhfd2luZG93IiwiYXVkaXRfZXZlbnRzIiwibW9ja09wcyIsInBhZ2UiLCJvcHRpb25zIiwicnVuRmFpbHVyZXMiLCJydW5GYWlsdXJlQ291bnQiLCJwb2xpY3lGYWlsdXJlcyIsInBvbGljeUZhaWx1cmVDb3VudCIsImRldGFpbEZhaWx1cmVzIiwicG9saWN5RGV0YWlsRmFpbHVyZUNvdW50Iiwid2l0aEJpbmRpbmciLCJ2YWx1ZSIsImxlZ2FjeUJpbmRpbmciLCJyb3V0ZSIsInJlcXVlc3QiLCJ1cmwiLCJVUkwiLCJwYXRoIiwicGF0aG5hbWUiLCJyZXBsYWNlIiwicmVxdWlyZVRva2VuIiwiaGVhZGVycyIsImF1dGhvcml6YXRpb24iLCJmdWxmaWxsIiwiY29udGVudFR5cGUiLCJib2R5IiwiSlNPTiIsInN0cmluZ2lmeSIsImRldGFpbCIsImRlbGF5UnVuc01zIiwiUHJvbWlzZSIsInJlc29sdmUiLCJzZXRUaW1lb3V0IiwiY3Vyc29yIiwic2VhcmNoUGFyYW1zIiwiZ2V0IiwicnVuUGFnZXMiLCJqc29uIiwic3RhcnRzV2l0aCIsInNwbGl0IiwiYXQiLCJkZWxheVBvbGljaWVzTXMiLCJoYXMiLCJfb3B0aW9ucyRvblNsb3dQb2xpY3kiLCJvblNsb3dQb2xpY3lEb25lIiwiY2FsbCIsInBvbGljeUVtcHR5Iiwic2Vjb25kIiwiZW5kc1dpdGgiLCJtYWxmb3JtZWRQb2xpY3kiLCJkZXRhaWxzIiwiaW5ub2NlbnQiLCJtb25pdG9yQnJvd3NlciIsImlnbm9yZWRDb25zb2xlRXJyb3JzIiwiZXJyb3JzIiwib24iLCJtZXNzYWdlIiwidHlwZSIsInNvbWUiLCJwYXR0ZXJuIiwidGV4dCIsInB1c2giLCJlcnJvciIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwidG9Mb3dlckNhc2UiLCJpbmNsdWRlcyIsImV4cGVjdFN0YWJsZUxheW91dCIsImxheW91dCIsImV2YWx1YXRlIiwiX2RvY3VtZW50JHF1ZXJ5U2VsZWN0IiwiX2RvY3VtZW50JHF1ZXJ5U2VsZWN0MiIsInZpZXdwb3J0V2lkdGgiLCJkb2N1bWVudCIsImRvY3VtZW50RWxlbWVudCIsImNsaWVudFdpZHRoIiwiYm9keU92ZXJmbG93Iiwic2Nyb2xsV2lkdGgiLCJoZWFkZXIiLCJxdWVyeVNlbGVjdG9yIiwiZ2V0Qm91bmRpbmdDbGllbnRSZWN0IiwibWFpbiIsImNsaXBwZWQiLCJBcnJheSIsImZyb20iLCJxdWVyeVNlbGVjdG9yQWxsIiwiZmlsdGVyIiwiZWxlbWVudCIsInNjcm9sbEhlaWdodCIsImNsaWVudEhlaWdodCIsIm1hcCIsIl9lbGVtZW50JHRleHRDb250ZW50IiwidGV4dENvbnRlbnQiLCJ0cmltIiwiY2xhc3NOYW1lIiwiY29oZXJlbnRGbG93IiwiYm90dG9tIiwidG9wIiwidG9CZUxlc3NUaGFuT3JFcXVhbCIsInRvRXF1YWwiLCJ0b0JlIiwidGVzdEluZm8iLCJicm93c2VyRXJyb3JzIiwiZ290byIsIndhaXRVbnRpbCIsImdldEJ5Um9sZSIsInRvQmVWaXNpYmxlIiwiZ2V0QnlUZXh0IiwiZXhhY3QiLCJjbGljayIsImRyYXdlciIsImZpcnN0IiwidG9IYXZlQ291bnQiLCJwcm9jZXNzIiwiZW52IiwiT1BTX1NDUkVFTlNIT1RfRElSIiwic2NyZWVuc2hvdCIsInByb2plY3QiLCJmdWxsUGFnZSIsImxvY2F0b3IiLCJnZXRCeUxhYmVsIiwiZmlsbCIsInNlc3Npb25TdG9yYWdlIiwiZ2V0SXRlbSIsInJlcXVlc3RzIiwibWV0aG9kIiwib3ZlcmZsb3dUYWJsZSIsImhvdmVyIiwibW91c2UiLCJ3aGVlbCIsInBvbGwiLCJzY3JvbGxMZWZ0IiwidG9CZUdyZWF0ZXJUaGFuIiwiZ2V0QnlUaXRsZSIsInRvQmVEaXNhYmxlZCIsImV2ZXJ5IiwiYW5pbWF0aW9ucyIsInNsb3dEb25lIiwiZmluaXNoZWQiLCJ0b0JlTnVsbCIsInNjZW5hcmlvIiwidW5kZWZpbmVkIiwic3RhcnRlZCIsInJlbGVhc2UiLCJmdWxmaWxsZWQiLCJwZW5kaW5nIiwiaW5pdGlhbCIsImNvbXBsZXRlZCIsImV4cGxhbmF0aW9uIiwibXV0YXRpb24iLCJyZWNlaXB0IiwiT2JqZWN0IiwiYXNzaWduIl0sInNvdXJjZXMiOlsib3BzLnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZXhwZWN0LCBQYWdlLCB0ZXN0IH0gZnJvbSAnQHBsYXl3cmlnaHQvdGVzdCdcblxuY29uc3QgdXNhZ2UgPSB7XG4gIG1vZGVsX2NhbGxzOiAxLFxuICB0b29sX2NhbGxzOiAyLFxuICBpbnB1dF90b2tlbnM6IDEyMCxcbiAgb3V0cHV0X3Rva2VuczogNDgsXG4gIGVzdGltYXRlZF9jb3N0X3VzZDogJzAuMDAyMScsXG4gIHVuY2VydGFpbjogZmFsc2UsXG59XG5cbmNvbnN0IGRlcGxveW1lbnRJZCA9ICcxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEnXG5jb25zdCBzZWNvbmREZXBsb3ltZW50SWQgPSAnMjIyMjIyMjItMjIyMi0yMjIyLTIyMjItMjIyMjIyMjIyMjIyJ1xuY29uc3QgYmluZGluZyA9IHtcbiAgZGVwbG95bWVudF9pZDogZGVwbG95bWVudElkLFxuICBlZmZlY3RpdmVfcG9saWN5X2hhc2g6ICdiJy5yZXBlYXQoNjQpLFxuICBwb2xpY3lfY29ob3J0OiAnY2FuZGlkYXRlJyxcbiAgbmFtZXNwYWNlX2NsYXNzOiAncmVoZWFyc2FsJyxcbn1cblxuY29uc3QgcnVuID0gKGlkOiBzdHJpbmcsIHN0YXR1cyA9ICdjb21wbGV0ZWQnKSA9PiAoe1xuICAuLi5iaW5kaW5nLFxuICBydW5faWQ6IGlkLFxuICBvcGVyYXRpb246ICdsZWFybmluZ190YXNrJyxcbiAgc3RhdHVzLFxuICB0cmFjZV9pZDogaWQgPT09ICdydW4tMScgPyAnYScucmVwZWF0KDMyKSA6ICdiJy5yZXBlYXQoMzIpLFxuICBhdHRlbXB0X2NvdW50OiAyLFxuICBvd25lcjogJ3J1bi13b3JrZXItYScsXG4gIGZlbmNpbmdfdG9rZW46IDMsXG4gIGxlYXNlX2V4cGlyZXNfYXQ6ICcyMDI2LTEwLTMwVDEwOjAxOjAwWicsXG4gIGxlYXNlX2ZyZXNoOiBzdGF0dXMgPT09ICdydW5uaW5nJyxcbiAgZXhwZXJ0X2pvYl9jb3VudDogMSxcbiAgdXNhZ2UsXG4gIGxhdGVuY3lfbXM6IDEyODAsXG4gIGNyZWF0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAwWicsXG4gIHVwZGF0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAxLjI4MFonLFxufSlcblxuY29uc3QgcnVuRGV0YWlsID0ge1xuICAuLi5ydW4oJ3J1bi0xJyksXG4gIGF0dGVtcHRzOiBbXG4gICAge1xuICAgICAgbnVtYmVyOiAxLFxuICAgICAgd29ya2VyX2lkOiAncnVuLXdvcmtlci1hJyxcbiAgICAgIGZlbmNpbmdfdG9rZW46IDIsXG4gICAgICBzdGF0dXM6ICdyZXRyeWFibGVfZmFpbGVkJyxcbiAgICAgIHJlYXNvbjogJ2xlYXNlX2V4cGlyZWQnLFxuICAgICAgc3RhcnRlZF9hdDogJzIwMjYtMTAtMzBUMDk6NTk6NTVaJyxcbiAgICAgIGRlYWRsaW5lX2F0OiAnMjAyNi0xMC0zMFQxMDowMTo1NVonLFxuICAgICAgZmluaXNoZWRfYXQ6ICcyMDI2LTEwLTMwVDA5OjU5OjU4WicsXG4gICAgICBkdXJhdGlvbl9tczogMzAwMCxcbiAgICB9LFxuICAgIHtcbiAgICAgIG51bWJlcjogMixcbiAgICAgIHdvcmtlcl9pZDogJ3J1bi13b3JrZXItYicsXG4gICAgICBmZW5jaW5nX3Rva2VuOiAzLFxuICAgICAgc3RhdHVzOiAnY29tcGxldGVkJyxcbiAgICAgIHJlYXNvbjogbnVsbCxcbiAgICAgIHN0YXJ0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAwWicsXG4gICAgICBkZWFkbGluZV9hdDogJzIwMjYtMTAtMzBUMTA6MDI6MDBaJyxcbiAgICAgIGZpbmlzaGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMDowMS4yODBaJyxcbiAgICAgIGR1cmF0aW9uX21zOiAxMjgwLFxuICAgIH0sXG4gIF0sXG4gIGV4cGVydF9qb2JzOiBbXG4gICAge1xuICAgICAgam9iX2lkOiAnam9iLTEnLFxuICAgICAgcGFyZW50X3J1bl9pZDogJ3J1bi0xJyxcbiAgICAgIHJvbGU6ICdhc3Nlc3NtZW50JyxcbiAgICAgIHN0YXR1czogJ2NvbXBsZXRlZCcsXG4gICAgICBhdHRlbXB0X2NvdW50OiAyLFxuICAgICAgbWF4X2F0dGVtcHRzOiAzLFxuICAgICAgZXJyb3JfY29kZTogbnVsbCxcbiAgICAgIGRlYWRsaW5lX2F0OiAnMjAyNi0xMC0zMFQxMDowMTowMFonLFxuICAgICAgY3JlYXRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDAuMTAwWicsXG4gICAgICB1cGRhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMDowMC45MDBaJyxcbiAgICAgIGNvbXBsZXRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDAuOTAwWicsXG4gICAgfSxcbiAgXSxcbn1cblxuY29uc3QgZXhwZXJ0RGV0YWlsID0ge1xuICBqb2JfaWQ6ICdqb2ItMScsXG4gIHBhcmVudF9ydW5faWQ6ICdydW4tMScsXG4gIGxvZ2ljYWxfa2V5OiAncGxhbjoxOmFzc2Vzc21lbnQnLFxuICByb2xlOiAnYXNzZXNzbWVudCcsXG4gIHN0YXR1czogJ2NvbXBsZXRlZCcsXG4gIGlucHV0X2hhc2g6ICdjJy5yZXBlYXQoNjQpLFxuICBwb2xpY3lfaGFzaDogJ2QnLnJlcGVhdCg2NCksXG4gIGJ1ZGdldDoge1xuICAgIG1heF9tb2RlbF9jYWxsczogMyxcbiAgICBtYXhfdG9vbF9jYWxsczogNCxcbiAgICBtYXhfb3V0cHV0X3Rva2VuczogODAwLFxuICAgIG1heF9jb250ZXh0X3Rva2VuczogNjAwMCxcbiAgICBtYXhfYXR0ZW1wdHM6IDMsXG4gICAgZGVhZGxpbmVfYXQ6ICcyMDI2LTEwLTMwVDEwOjAxOjAwWicsXG4gIH0sXG4gIHVzYWdlLFxuICBzb3VyY2VfcmVmczogWydrbm93bGVkZ2U6Z3JhbW1hcl90ZW5zZXMnXSxcbiAgYXR0ZW1wdHM6IFtcbiAgICB7XG4gICAgICB3b3JrZXJfaWQ6ICdleHBlcnQtd29ya2VyLWEnLFxuICAgICAgZmVuY2luZ190b2tlbjogMSxcbiAgICAgIGRpc3Bvc2l0aW9uOiAncmVqZWN0ZWQnLFxuICAgICAgcmVqZWN0aW9uX2NvZGU6ICdleHBlcnRfdG9rZW5fc3RhbGUnLFxuICAgICAgdXNhZ2UsXG4gICAgICBzb3VyY2VfcmVmczogW10sXG4gICAgICBjcmVhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMDowMC43MDBaJyxcbiAgICB9LFxuICAgIHtcbiAgICAgIHdvcmtlcl9pZDogJ2V4cGVydC13b3JrZXItYicsXG4gICAgICBmZW5jaW5nX3Rva2VuOiAyLFxuICAgICAgZGlzcG9zaXRpb246ICdhY2NlcHRlZCcsXG4gICAgICByZWplY3Rpb25fY29kZTogbnVsbCxcbiAgICAgIHVzYWdlLFxuICAgICAgc291cmNlX3JlZnM6IFsna25vd2xlZGdlOmdyYW1tYXJfdGVuc2VzJ10sXG4gICAgICBjcmVhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMDowMC45MDBaJyxcbiAgICB9LFxuICBdLFxuICBlcnJvcl9jb2RlOiBudWxsLFxuICBjcmVhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMDowMC4xMDBaJyxcbiAgdXBkYXRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDAuOTAwWicsXG4gIGNvbXBsZXRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDAuOTAwWicsXG59XG5cbmNvbnN0IHRyYWNlID0ge1xuICAuLi5iaW5kaW5nLFxuICBydW5faWQ6ICdydW4tMScsXG4gIHRyYWNlX2lkOiAnYScucmVwZWF0KDMyKSxcbiAgc3BhbnM6IFtcbiAgICB7XG4gICAgICBzcGFuX2lkOiAnMScucmVwZWF0KDE2KSxcbiAgICAgIHRyYWNlX2lkOiAnYScucmVwZWF0KDMyKSxcbiAgICAgIHBhcmVudF9zcGFuX2lkOiBudWxsLFxuICAgICAgbmFtZTogJ3J1bi5hdHRlbXB0JyxcbiAgICAgIHN0YXR1czogJ29rJyxcbiAgICAgIGF0dHJpYnV0ZXM6IHtcbiAgICAgICAgJ3dvcmtlci5pZCc6ICdydW4td29ya2VyLWInLFxuICAgICAgICAncnVuLmZlbmNpbmdfdG9rZW4nOiAzLFxuICAgICAgfSxcbiAgICAgIHN0YXJ0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAwWicsXG4gICAgICBlbmRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDEuMjgwWicsXG4gICAgICBkdXJhdGlvbl9tczogMTI4MCxcbiAgICB9LFxuICAgIHtcbiAgICAgIHNwYW5faWQ6ICcyJy5yZXBlYXQoMTYpLFxuICAgICAgdHJhY2VfaWQ6ICdhJy5yZXBlYXQoMzIpLFxuICAgICAgcGFyZW50X3NwYW5faWQ6ICcxJy5yZXBlYXQoMTYpLFxuICAgICAgbmFtZTogJ2V4cGVydC53YWl0JyxcbiAgICAgIHN0YXR1czogJ29rJyxcbiAgICAgIGF0dHJpYnV0ZXM6IHtcbiAgICAgICAgJ2V4cGVydC5qb2JfaWQnOiAnam9iLTEnLFxuICAgICAgICAnZXhwZXJ0LmZlbmNpbmdfdG9rZW4nOiAyLFxuICAgICAgfSxcbiAgICAgIHN0YXJ0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAwLjIwMFonLFxuICAgICAgZW5kZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAwOjAwLjkwMFonLFxuICAgICAgZHVyYXRpb25fbXM6IDcwMCxcbiAgICB9LFxuICBdLFxufVxuXG5jb25zdCB3b3JrZXJzID0ge1xuICBpdGVtczogW1xuICAgIHtcbiAgICAgIHdvcmtlcl9pZDogJ3J1bi13b3JrZXItYScsXG4gICAgICBpbnN0YW5jZV9pZDogJ2luc3RhbmNlLXJ1bi1hJyxcbiAgICAgIHByb2Nlc3NfdHlwZTogJ3J1bi13b3JrZXInLFxuICAgICAgc3RhdHVzOiAncnVubmluZycsXG4gICAgICBoZWFsdGg6ICdoZWFsdGh5JyxcbiAgICAgIGZyZXNoOiB0cnVlLFxuICAgICAgY2FwYWJpbGl0aWVzOiBbJ2xlYXJuaW5nX3Rhc2snXSxcbiAgICAgIGN1cnJlbnRfcnVuX2lkOiAncnVuLTEnLFxuICAgICAgY3VycmVudF9qb2JfaWQ6IG51bGwsXG4gICAgICBoZWFydGJlYXRfYWdlX3NlY29uZHM6IDEuMixcbiAgICAgIHN0YXJ0ZWRfYXQ6ICcyMDI2LTEwLTMwVDA5OjU1OjAwWicsXG4gICAgICBsYXN0X2hlYXJ0YmVhdF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDBaJyxcbiAgICAgIHN0b3BwZWRfYXQ6IG51bGwsXG4gICAgfSxcbiAgICB7XG4gICAgICB3b3JrZXJfaWQ6ICdleHBlcnQtd29ya2VyLXN0YWxlJyxcbiAgICAgIGluc3RhbmNlX2lkOiAnaW5zdGFuY2UtZXhwZXJ0LXN0YWxlJyxcbiAgICAgIHByb2Nlc3NfdHlwZTogJ2V4cGVydC13b3JrZXInLFxuICAgICAgc3RhdHVzOiAncnVubmluZycsXG4gICAgICBoZWFsdGg6ICdzdGFsZScsXG4gICAgICBmcmVzaDogZmFsc2UsXG4gICAgICBjYXBhYmlsaXRpZXM6IFsnYXNzZXNzbWVudCcsICdjdXJyaWN1bHVtJ10sXG4gICAgICBjdXJyZW50X3J1bl9pZDogbnVsbCxcbiAgICAgIGN1cnJlbnRfam9iX2lkOiAnam9iLTEnLFxuICAgICAgaGVhcnRiZWF0X2FnZV9zZWNvbmRzOiAxMjEuNCxcbiAgICAgIHN0YXJ0ZWRfYXQ6ICcyMDI2LTEwLTMwVDA5OjU1OjAwWicsXG4gICAgICBsYXN0X2hlYXJ0YmVhdF9hdDogJzIwMjYtMTAtMzBUMDk6NTg6MDBaJyxcbiAgICAgIHN0b3BwZWRfYXQ6IG51bGwsXG4gICAgfSxcbiAgXSxcbiAgbmV4dF9jdXJzb3I6IG51bGwsXG59XG5cbnR5cGUgTW9ja09wdGlvbnMgPSB7XG4gIHJ1blBhZ2VzPzogJ3BvcHVsYXRlZCcgfCAnZW1wdHknXG4gIHJ1bkZhaWx1cmVDb3VudD86IG51bWJlclxuICBkZWxheVJ1bnNNcz86IG51bWJlclxuICByZXF1aXJlVG9rZW4/OiBib29sZWFuXG4gIHBvbGljeUVtcHR5PzogYm9vbGVhblxuICBwb2xpY3lGYWlsdXJlQ291bnQ/OiBudW1iZXJcbiAgcG9saWN5RGV0YWlsRmFpbHVyZUNvdW50PzogbnVtYmVyXG4gIG1hbGZvcm1lZFBvbGljeT86IGJvb2xlYW5cbiAgbGVnYWN5QmluZGluZz86IGJvb2xlYW5cbiAgZGVsYXlQb2xpY2llc01zPzogbnVtYmVyXG4gIG9uU2xvd1BvbGljeURvbmU/OiAoKSA9PiB2b2lkXG59XG5cbmNvbnN0IHRocmVzaG9sZHMgPSB7XG4gIGNhbmRpZGF0ZV9taW5fcnVuczogMjAsIHN0YWJsZV9taW5fcnVuczogMjAsIHdpbmRvd19tYXhfcnVuczogNTAsXG4gIGNvbW1pdF9mYWlsdXJlX3JhdGU6ICcwLjA1JywgdGVybWluYWxfZmFpbHVyZV9yYXRlOiAnMC4xMCcsXG4gIGxhdGVuY3lfaW5jcmVhc2VfcmF0ZTogJzAuNTAnLCBtZWFuX2Nvc3RfaW5jcmVhc2VfcmF0ZTogJzAuMzAnLFxuICB1bmtub3duX3JhdGU6ICcwLjEwJywgcmVsYXRpdmVfZXBzaWxvbjogJzAuMDAwMDAxJyxcbn1cbmNvbnN0IHN0YXRzID0ge1xuICBydW5fY291bnQ6IDIwLCBjb21taXRfZmFpbHVyZV9yYXRlOiAnMC4wNScsIHRlcm1pbmFsX2ZhaWx1cmVfcmF0ZTogJzAuMTAnLFxuICBwOTVfbGF0ZW5jeTogJzEuMjUnLCBtZWFuX2Nvc3Q6ICcwLjAxJywgc3RydWN0dXJlZF9kZWNpc2lvbl9jb3VudDogMTAsXG4gIHVua25vd25fZGVjaXNpb25fY291bnQ6IDEsIHVua25vd25fcmF0ZTogJzAuMTAnLCBmYXVsdF9pbmplY3RlZF9jb3VudDogMSxcbiAgaW5qZWN0ZWRfY29tbWl0X2ZhaWx1cmVfY291bnQ6IDEsIG5hdHVyYWxfZmFpbHVyZV9jb3VudDogMCxcbiAgbGF0ZW5jeV9pbmNyZWFzZV9yYXRlOiBudWxsLCBtZWFuX2Nvc3RfaW5jcmVhc2VfcmF0ZTogbnVsbCxcbn1cbmNvbnN0IGhlYWx0aFdpbmRvdyA9IHtcbiAgd2luZG93X2lkOiAnYycucmVwZWF0KDY0KSwgZGVwbG95bWVudF9pZDogZGVwbG95bWVudElkLCBkZXBsb3ltZW50X3ZlcnNpb246IDIsXG4gIGVudmlyb25tZW50OiAncmVoZWFyc2FsJywgbWV0cmljX2NvbnRyYWN0X3ZlcnNpb246IDEsIHRocmVzaG9sZHNfaGFzaDogJ2QnLnJlcGVhdCg2NCksXG4gIGNhbmRpZGF0ZV9zdGF0czogc3RhdHMsIHN0YWJsZV9zdGF0czogeyAuLi5zdGF0cywgbWVhbl9jb3N0OiBudWxsIH0sXG4gIGRlY2lzaW9uOiAnZmFpbCcsIHRyaWdnZXJlZF90aHJlc2hvbGRzOiBbJ2NvbW1pdF9mYWlsdXJlX3JhdGUnXSxcbiAgZXZhbHVhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMzowMFonLCBjcmVhdGVkX2F0OiAnMjAyNi0xMC0zMFQxMDowMzowMFonLFxufVxuY29uc3QgYXVkaXRFdmVudCA9IHtcbiAgZXZlbnRfaWQ6ICczMzMzMzMzMy0zMzMzLTMzMzMtMzMzMy0zMzMzMzMzMzMzMzMnLFxuICBlbnZpcm9ubWVudDogJ3JlaGVhcnNhbCcsIGRlcGxveW1lbnRfaWQ6IGRlcGxveW1lbnRJZCwgZXZlbnRfdHlwZTogJ2hlYWx0aF9yb2xsYmFjaycsXG4gIGZhaWxlZF9kZXBsb3ltZW50X2lkOiBudWxsLCBoZWFsdGhfd2luZG93X2lkOiAnYycucmVwZWF0KDY0KSwgZnJvbV9zdGF0ZTogbnVsbCwgdG9fc3RhdGU6IG51bGwsXG4gIGFjdG9yOiAncmVkYWN0ZWQnLCByZWFzb246ICdyZWRhY3RlZCcsIGNyZWF0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAzOjAxWicsXG59XG5jb25zdCBwb2xpY3lEZXBsb3ltZW50ID0gKGlkID0gZGVwbG95bWVudElkKSA9PiAoe1xuICBkZXBsb3ltZW50X2lkOiBpZCwgZW52aXJvbm1lbnQ6ICdyZWhlYXJzYWwnLCB2ZXJzaW9uOiBpZCA9PT0gZGVwbG95bWVudElkID8gMiA6IDMsXG4gIHN0YXRlOiBpZCA9PT0gZGVwbG95bWVudElkID8gJ2NhbmFyeScgOiAnZnJvemVuJyxcbiAgY2FuZGlkYXRlX3BvbGljeV9oYXNoOiAnYicucmVwZWF0KDEyKSwgc3RhYmxlX3BvbGljeV9oYXNoOiAnYScucmVwZWF0KDEyKSxcbiAgaXNfY3VycmVudDogaWQgIT09IGRlcGxveW1lbnRJZCwgY3VycmVudF9kZXBsb3ltZW50X2lkOiBzZWNvbmREZXBsb3ltZW50SWQsXG4gIGN1cnJlbnRfdmVyc2lvbjogMywgdHJhZmZpY19iYXNpc19wb2ludHM6IGlkID09PSBkZXBsb3ltZW50SWQgPyA1MDAwIDogMCxcbiAgY29ob3J0X2NvdW50czogeyBzdGFibGU6IDIwLCBjYW5kaWRhdGU6IDIwLCBzaGFkb3c6IDEwIH0sIHRocmVzaG9sZHMsXG4gIHRocmVzaG9sZHNfaGFzaDogJ2QnLnJlcGVhdCg2NCksIHJlcXVpcmVkX3JlY2VpcHRzOiBbJ2NhbmFyeV9oZWFsdGgnXSxcbiAgYWN0b3I6ICdyZWRhY3RlZCcsIHJlYXNvbjogJ3JlZGFjdGVkJywgY3JlYXRlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDA6MDBaJyxcbn0pXG5jb25zdCBwb2xpY3lEZXRhaWwgPSAoaWQgPSBkZXBsb3ltZW50SWQpID0+ICh7XG4gIC4uLnBvbGljeURlcGxveW1lbnQoaWQpLCBjYW5kaWRhdGVfcG9saWN5X2hhc2g6ICdiJy5yZXBlYXQoNjQpLFxuICBzdGFibGVfcG9saWN5X2hhc2g6ICdhJy5yZXBlYXQoNjQpLFxuICBnYXRlX3JlY2VpcHRzOiBbe1xuICAgIHJlY2VpcHRfaWQ6ICc0NDQ0NDQ0NC00NDQ0LTQ0NDQtNDQ0NC00NDQ0NDQ0NDQ0NDQnLFxuICAgIHBvbGljeV9oYXNoOiAnYicucmVwZWF0KDY0KSwgZ2F0ZV90eXBlOiAnY2FuYXJ5X2hlYWx0aCcsIHN0YXR1czogJ2ZhaWxlZCcsXG4gICAgZXZpZGVuY2VfaGFzaDogJ2UnLnJlcGVhdCg2NCksIHNhbXBsZV9jb3VudDogMjAsIGNvc3Q6ICcwLjAyJyxcbiAgICBpc3N1ZXI6ICdyZWRhY3RlZCcsIGlzc3VlZF9hdDogJzIwMjYtMTAtMzBUMTA6MDI6MDBaJyxcbiAgICBoZWFsdGhfc291cmNlOiB7XG4gICAgICByZWxhdGlvbjogJ2xvY2FsJywgZGVwbG95bWVudF9pZDogaWQsIGRlcGxveW1lbnRfdmVyc2lvbjogaWQgPT09IGRlcGxveW1lbnRJZCA/IDIgOiAzLFxuICAgICAgd2luZG93X2lkOiAnYycucmVwZWF0KDY0KSwgdGhyZXNob2xkc19oYXNoOiAnZCcucmVwZWF0KDY0KSwgd2luZG93X2RlY2lzaW9uOiAnZmFpbCcsXG4gICAgICBldmFsdWF0ZWRfYXQ6ICcyMDI2LTEwLTMwVDEwOjAzOjAwWicsIGlzX2xhdGVzdF93aW5kb3c6IHRydWUsXG4gICAgfSxcbiAgfV0sXG4gIGxhdGVzdF9oZWFsdGhfd2luZG93OiB7IC4uLmhlYWx0aFdpbmRvdywgZGVwbG95bWVudF9pZDogaWQgfSxcbiAgYXVkaXRfZXZlbnRzOiBbXG4gICAgYXVkaXRFdmVudCxcbiAgICB7IC4uLmF1ZGl0RXZlbnQsIGV2ZW50X2lkOiAnNTU1NTU1NTUtNTU1NS01NTU1LTU1NTUtNTU1NTU1NTU1NTU1JywgZXZlbnRfdHlwZTogJ3Byb21vdGlvbl90cmFuc2l0aW9uZWQnLFxuICAgICAgZnJvbV9zdGF0ZTogJ2NhbmFyeScsIHRvX3N0YXRlOiAnZnJvemVuJywgaGVhbHRoX3dpbmRvd19pZDogbnVsbCB9LFxuICBdLFxufSlcblxuYXN5bmMgZnVuY3Rpb24gbW9ja09wcyhwYWdlOiBQYWdlLCBvcHRpb25zOiBNb2NrT3B0aW9ucyA9IHt9KSB7XG4gIGxldCBydW5GYWlsdXJlcyA9IG9wdGlvbnMucnVuRmFpbHVyZUNvdW50IHx8IDBcbiAgbGV0IHBvbGljeUZhaWx1cmVzID0gb3B0aW9ucy5wb2xpY3lGYWlsdXJlQ291bnQgfHwgMFxuICBsZXQgZGV0YWlsRmFpbHVyZXMgPSBvcHRpb25zLnBvbGljeURldGFpbEZhaWx1cmVDb3VudCB8fCAwXG4gIGNvbnN0IHdpdGhCaW5kaW5nID0gPFQgZXh0ZW5kcyBvYmplY3Q+KHZhbHVlOiBUKSA9PiBvcHRpb25zLmxlZ2FjeUJpbmRpbmdcbiAgICA/IHsgLi4udmFsdWUsIGRlcGxveW1lbnRfaWQ6IG51bGwsIGVmZmVjdGl2ZV9wb2xpY3lfaGFzaDogbnVsbCwgcG9saWN5X2NvaG9ydDogbnVsbCwgbmFtZXNwYWNlX2NsYXNzOiBudWxsIH1cbiAgICA6IHZhbHVlXG4gIGF3YWl0IHBhZ2Uucm91dGUoJyoqL29wcy1hcGkvb3BzLyoqJywgYXN5bmMgKHJvdXRlKSA9PiB7XG4gICAgY29uc3QgcmVxdWVzdCA9IHJvdXRlLnJlcXVlc3QoKVxuICAgIGNvbnN0IHVybCA9IG5ldyBVUkwocmVxdWVzdC51cmwoKSlcbiAgICBjb25zdCBwYXRoID0gdXJsLnBhdGhuYW1lLnJlcGxhY2UoJy9vcHMtYXBpL29wcycsICcnKVxuXG4gICAgaWYgKFxuICAgICAgb3B0aW9ucy5yZXF1aXJlVG9rZW5cbiAgICAgICYmIHJlcXVlc3QuaGVhZGVycygpLmF1dGhvcml6YXRpb24gIT09ICdCZWFyZXIgYnJvd3Nlci10ZXN0LXRva2VuJ1xuICAgICkge1xuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7XG4gICAgICAgIHN0YXR1czogNDAxLFxuICAgICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IGRldGFpbDogJ3ZhbGlkIE9wcyBiZWFyZXIgdG9rZW4gcmVxdWlyZWQnIH0pLFxuICAgICAgfSlcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGlmIChwYXRoID09PSAnL3J1bnMnKSB7XG4gICAgICBpZiAob3B0aW9ucy5kZWxheVJ1bnNNcykge1xuICAgICAgICBhd2FpdCBuZXcgUHJvbWlzZSgocmVzb2x2ZSkgPT4gc2V0VGltZW91dChyZXNvbHZlLCBvcHRpb25zLmRlbGF5UnVuc01zKSlcbiAgICAgIH1cbiAgICAgIGlmIChydW5GYWlsdXJlcyA+IDApIHtcbiAgICAgICAgcnVuRmFpbHVyZXMgLT0gMVxuICAgICAgICBhd2FpdCByb3V0ZS5mdWxmaWxsKHtcbiAgICAgICAgICBzdGF0dXM6IDUwMCxcbiAgICAgICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgZGV0YWlsOiAndGVtcG9yYXJ5IGRhdGFiYXNlIGZhaWx1cmUnIH0pLFxuICAgICAgICB9KVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIGNvbnN0IGN1cnNvciA9IHVybC5zZWFyY2hQYXJhbXMuZ2V0KCdjdXJzb3InKVxuICAgICAgY29uc3QgYm9keSA9IG9wdGlvbnMucnVuUGFnZXMgPT09ICdlbXB0eSdcbiAgICAgICAgPyB7IGl0ZW1zOiBbXSwgbmV4dF9jdXJzb3I6IG51bGwgfVxuICAgICAgICA6IGN1cnNvciA9PT0gJ2N1cnNvci0yJ1xuICAgICAgICAgID8geyBpdGVtczogW3dpdGhCaW5kaW5nKHJ1bigncnVuLTInLCAncnVubmluZycpKV0sIG5leHRfY3Vyc29yOiBudWxsIH1cbiAgICAgICAgICA6IHsgaXRlbXM6IFt3aXRoQmluZGluZyhydW4oJ3J1bi0xJykpXSwgbmV4dF9jdXJzb3I6ICdjdXJzb3ItMicgfVxuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IGJvZHkgfSlcbiAgICAgIHJldHVyblxuICAgIH1cbiAgICBpZiAocGF0aCA9PT0gJy9ydW5zL3J1bi0xJykge1xuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IHdpdGhCaW5kaW5nKHJ1bkRldGFpbCkgfSlcbiAgICAgIHJldHVyblxuICAgIH1cbiAgICBpZiAocGF0aCA9PT0gJy9ydW5zL3J1bi0xL3RyYWNlJykge1xuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IHdpdGhCaW5kaW5nKHRyYWNlKSB9KVxuICAgICAgcmV0dXJuXG4gICAgfVxuICAgIGlmIChwYXRoID09PSAnL2V4cGVydC1qb2JzL2pvYi0xJykge1xuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IGV4cGVydERldGFpbCB9KVxuICAgICAgcmV0dXJuXG4gICAgfVxuICAgIGlmIChwYXRoID09PSAnL3dvcmtlcnMnKSB7XG4gICAgICBhd2FpdCByb3V0ZS5mdWxmaWxsKHsganNvbjogd29ya2VycyB9KVxuICAgICAgcmV0dXJuXG4gICAgfVxuICAgIGlmIChwYXRoLnN0YXJ0c1dpdGgoJy9wb2xpY2llcy9kZXBsb3ltZW50cy8nKSkge1xuICAgICAgaWYgKGRldGFpbEZhaWx1cmVzLS0gPiAwKSB7XG4gICAgICAgIGF3YWl0IHJvdXRlLmZ1bGZpbGwoeyBzdGF0dXM6IDUwMywganNvbjogeyBkZXRhaWw6ICdwb2xpY3kgZGV0YWlsIHVuYXZhaWxhYmxlJyB9IH0pXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3QgaWQgPSBwYXRoLnNwbGl0KCcvJykuYXQoLTEpIVxuICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IHBvbGljeURldGFpbChpZCkgfSlcbiAgICAgIHJldHVyblxuICAgIH1cbiAgICBpZiAocGF0aC5zdGFydHNXaXRoKCcvcG9saWNpZXMvJykpIHtcbiAgICAgIGlmIChvcHRpb25zLmRlbGF5UG9saWNpZXNNcyAmJiAhdXJsLnNlYXJjaFBhcmFtcy5oYXMoJ2Vudmlyb25tZW50JykpIHtcbiAgICAgICAgYXdhaXQgbmV3IFByb21pc2UoKHJlc29sdmUpID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgb3B0aW9ucy5kZWxheVBvbGljaWVzTXMpKVxuICAgICAgICBvcHRpb25zLm9uU2xvd1BvbGljeURvbmU/LigpXG4gICAgICB9XG4gICAgICBpZiAocG9saWN5RmFpbHVyZXMtLSA+IDApIHtcbiAgICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IHN0YXR1czogNTAzLCBqc29uOiB7IGRldGFpbDogJ3BvbGljeSBldmlkZW5jZSB1bmF2YWlsYWJsZScgfSB9KVxuICAgICAgICByZXR1cm5cbiAgICAgIH1cbiAgICAgIGlmIChvcHRpb25zLnBvbGljeUVtcHR5IHx8IHVybC5zZWFyY2hQYXJhbXMuZ2V0KCdlbnZpcm9ubWVudCcpID09PSAncHJvZHVjdGlvbicpIHtcbiAgICAgICAgYXdhaXQgcm91dGUuZnVsZmlsbCh7IGpzb246IHsgaXRlbXM6IFtdLCBuZXh0X2N1cnNvcjogbnVsbCB9IH0pXG4gICAgICAgIHJldHVyblxuICAgICAgfVxuICAgICAgY29uc3Qgc2Vjb25kID0gdXJsLnNlYXJjaFBhcmFtcy5nZXQoJ2N1cnNvcicpID09PSAncG9saWN5LXBhZ2UtMidcbiAgICAgIGxldCBpdGVtczogb2JqZWN0W10gPSBwYXRoLmVuZHNXaXRoKCdkZXBsb3ltZW50cycpXG4gICAgICAgID8gW3BvbGljeURlcGxveW1lbnQoc2Vjb25kID8gc2Vjb25kRGVwbG95bWVudElkIDogZGVwbG95bWVudElkKV1cbiAgICAgICAgOiBwYXRoLmVuZHNXaXRoKCdoZWFsdGgtd2luZG93cycpID8gW2hlYWx0aFdpbmRvd10gOiBbYXVkaXRFdmVudF1cbiAgICAgIGNvbnN0IHN0YXRlID0gdXJsLnNlYXJjaFBhcmFtcy5nZXQoJ3N0YXRlJylcbiAgICAgIGlmIChzdGF0ZSkgaXRlbXMgPSBbcG9saWN5RGVwbG95bWVudChzdGF0ZSA9PT0gJ2Zyb3plbicgPyBzZWNvbmREZXBsb3ltZW50SWQgOiBkZXBsb3ltZW50SWQpXVxuICAgICAgaWYgKG9wdGlvbnMubWFsZm9ybWVkUG9saWN5KSBpdGVtcyA9IFt7IC4uLml0ZW1zWzBdLCBkZXRhaWxzOiB7IGlubm9jZW50OiAnbXVzdC1ub3QtcmVuZGVyJyB9IH1dXG4gICAgICBhd2FpdCByb3V0ZS5mdWxmaWxsKHsganNvbjogeyBpdGVtcywgbmV4dF9jdXJzb3I6IHNlY29uZCB8fCBzdGF0ZSA/IG51bGwgOiAncG9saWN5LXBhZ2UtMicgfSB9KVxuICAgICAgcmV0dXJuXG4gICAgfVxuICAgIGF3YWl0IHJvdXRlLmZ1bGZpbGwoe1xuICAgICAgc3RhdHVzOiA0MDQsXG4gICAgICBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBkZXRhaWw6IGB1bm1vY2tlZCBwYXRoOiAke3BhdGh9YCB9KSxcbiAgICB9KVxuICB9KVxufVxuXG5mdW5jdGlvbiBtb25pdG9yQnJvd3NlcihwYWdlOiBQYWdlLCBpZ25vcmVkQ29uc29sZUVycm9yczogUmVnRXhwW10gPSBbXSkge1xuICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW11cbiAgcGFnZS5vbignY29uc29sZScsIChtZXNzYWdlKSA9PiB7XG4gICAgaWYgKFxuICAgICAgbWVzc2FnZS50eXBlKCkgPT09ICdlcnJvcidcbiAgICAgICYmICFpZ25vcmVkQ29uc29sZUVycm9ycy5zb21lKChwYXR0ZXJuKSA9PiBwYXR0ZXJuLnRlc3QobWVzc2FnZS50ZXh0KCkpKVxuICAgICkge1xuICAgICAgZXJyb3JzLnB1c2gobWVzc2FnZS50ZXh0KCkpXG4gICAgfVxuICB9KVxuICBwYWdlLm9uKCdwYWdlZXJyb3InLCAoZXJyb3IpID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKVxuICBwYWdlLm9uKCdyZXF1ZXN0ZmFpbGVkJywgKHJlcXVlc3QpID0+IHtcbiAgICBjb25zdCBtZXNzYWdlID0gcmVxdWVzdC5mYWlsdXJlKCk/LmVycm9yVGV4dCB8fCAncmVxdWVzdCBmYWlsZWQnXG4gICAgaWYgKCFtZXNzYWdlLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoJ2Fib3J0ZWQnKSkge1xuICAgICAgZXJyb3JzLnB1c2goYCR7cmVxdWVzdC51cmwoKX06ICR7bWVzc2FnZX1gKVxuICAgIH1cbiAgfSlcbiAgcmV0dXJuIGVycm9yc1xufVxuXG5hc3luYyBmdW5jdGlvbiBleHBlY3RTdGFibGVMYXlvdXQocGFnZTogUGFnZSkge1xuICBjb25zdCBsYXlvdXQgPSBhd2FpdCBwYWdlLmV2YWx1YXRlKCgpID0+IHtcbiAgICBjb25zdCB2aWV3cG9ydFdpZHRoID0gZG9jdW1lbnQuZG9jdW1lbnRFbGVtZW50LmNsaWVudFdpZHRoXG4gICAgY29uc3QgYm9keU92ZXJmbG93ID0gZG9jdW1lbnQuZG9jdW1lbnRFbGVtZW50LnNjcm9sbFdpZHRoIC0gdmlld3BvcnRXaWR0aFxuICAgIGNvbnN0IGhlYWRlciA9IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy5vcHMtaGVhZGVyJyk/LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpXG4gICAgY29uc3QgbWFpbiA9IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy5vcHMtbWFpbicpPy5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKVxuICAgIGNvbnN0IGNsaXBwZWQgPSBBcnJheS5mcm9tKFxuICAgICAgZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbDxIVE1MRWxlbWVudD4oXG4gICAgICAgICcub3BzLW5hdiBhLCAub3BzLXBhZ2UtaGVhZGluZyBoMSwgLm9wcy1wYWdpbmF0aW9uIGJ1dHRvbicsXG4gICAgICApLFxuICAgICkuZmlsdGVyKChlbGVtZW50KSA9PiAoXG4gICAgICBlbGVtZW50LnNjcm9sbFdpZHRoID4gZWxlbWVudC5jbGllbnRXaWR0aCArIDJcbiAgICAgIHx8IGVsZW1lbnQuc2Nyb2xsSGVpZ2h0ID4gZWxlbWVudC5jbGllbnRIZWlnaHQgKyAyXG4gICAgKSkubWFwKChlbGVtZW50KSA9PiBlbGVtZW50LnRleHRDb250ZW50Py50cmltKCkgfHwgZWxlbWVudC5jbGFzc05hbWUpXG4gICAgcmV0dXJuIHtcbiAgICAgIGJvZHlPdmVyZmxvdyxcbiAgICAgIGNsaXBwZWQsXG4gICAgICBjb2hlcmVudEZsb3c6ICFoZWFkZXIgfHwgIW1haW4gfHwgaGVhZGVyLmJvdHRvbSA8PSBtYWluLnRvcCArIDEsXG4gICAgfVxuICB9KVxuICBleHBlY3QobGF5b3V0LmJvZHlPdmVyZmxvdykudG9CZUxlc3NUaGFuT3JFcXVhbCgxKVxuICBleHBlY3QobGF5b3V0LmNsaXBwZWQpLnRvRXF1YWwoW10pXG4gIGV4cGVjdChsYXlvdXQuY29oZXJlbnRGbG93KS50b0JlKHRydWUpXG59XG5cbnRlc3QoJ3JlbmRlcnMgcG9wdWxhdGVkIE9wcyB3b3JrZmxvd3Mgd2l0aCBwYWdpbmF0aW9uLCBkZXRhaWwsIHRyYWNlLCBhbmQgc3RhbGUgd29ya2VycycsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcbiAgY29uc3QgYnJvd3NlckVycm9ycyA9IG1vbml0b3JCcm93c2VyKHBhZ2UpXG4gIGF3YWl0IG1vY2tPcHMocGFnZSlcblxuICBhd2FpdCBwYWdlLmdvdG8oJy9vcHMvIy9ydW5zJywgeyB3YWl0VW50aWw6ICdjb21taXQnIH0pXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHsgbmFtZTogJ1J1bnMnIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgncnVuLTEnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC/kuIvkuIDpobUvIH0pLmNsaWNrKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdydW4tMicsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL+S4iuS4gOmhtS8gfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ3J1bi0xJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfmn6XnnIvov5DooYwgcnVuLTEg6K+m5oOFJyB9KS5jbGljaygpXG4gIGNvbnN0IGRyYXdlciA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICfov5DooYzor6bmg4UnIH0pXG4gIGF3YWl0IGV4cGVjdChkcmF3ZXIpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KGRyYXdlci5nZXRCeVRleHQoJ3J1bi13b3JrZXItYicsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZHJhd2VyLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAn5qOA5p+lJyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChkcmF3ZXIuZ2V0QnlUZXh0KCdrbm93bGVkZ2U6Z3JhbW1hcl90ZW5zZXMnKSkudG9CZVZpc2libGUoKVxuXG4gIGF3YWl0IGRyYXdlci5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6ICdhJy5yZXBlYXQoMzIpIH0pLmNsaWNrKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywgeyBuYW1lOiAn6L+Q6KGMIFRyYWNlJyB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ2V4cGVydC53YWl0JywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3RyZWUnKSkudG9CZVZpc2libGUoKVxuXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiAvV29ya2Vycy8gfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICdXb3JrZXJzJyB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ2V4cGVydC13b3JrZXItc3RhbGUnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnc3RhbGUnLCB7IGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkpLnRvQmVWaXNpYmxlKClcblxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL+WPlua2iHzph43or5Xku7vliqF86YeN5paw5YWl6ZifLyB9KSkudG9IYXZlQ291bnQoMClcbiAgYXdhaXQgZXhwZWN0U3RhYmxlTGF5b3V0KHBhZ2UpXG4gIGlmIChwcm9jZXNzLmVudi5PUFNfU0NSRUVOU0hPVF9ESVIpIHtcbiAgICBhd2FpdCBwYWdlLnNjcmVlbnNob3Qoe1xuICAgICAgcGF0aDogYCR7cHJvY2Vzcy5lbnYuT1BTX1NDUkVFTlNIT1RfRElSfS9vcHMtJHt0ZXN0SW5mby5wcm9qZWN0Lm5hbWV9LnBuZ2AsXG4gICAgICBmdWxsUGFnZTogdHJ1ZSxcbiAgICB9KVxuICB9XG4gIGV4cGVjdChicm93c2VyRXJyb3JzKS50b0VxdWFsKFtdKVxufSlcblxudGVzdCgnc2hvd3MgbG9hZGluZyBhbmQgZW1wdHkgc3RhdGVzIHdpdGhvdXQgbGF5b3V0IHNoaWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGJyb3dzZXJFcnJvcnMgPSBtb25pdG9yQnJvd3NlcihwYWdlKVxuICBhd2FpdCBtb2NrT3BzKHBhZ2UsIHsgcnVuUGFnZXM6ICdlbXB0eScgfSlcblxuICBhd2FpdCBwYWdlLmdvdG8oJy9vcHMvIy9ydW5zJywgeyB3YWl0VW50aWw6ICdjb21taXQnIH0pXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJy5hbnQtc2tlbGV0b24nKSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+ayoeacieespuWQiOadoeS7tueahOi/kOihjCcpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdFN0YWJsZUxheW91dChwYWdlKVxuICBleHBlY3QoYnJvd3NlckVycm9ycykudG9FcXVhbChbXSlcbn0pXG5cbnRlc3QoJ3Nob3dzIHJldHJ5YWJsZSBBUEkgZXJyb3JzIGFuZCByZWNvdmVycycsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBicm93c2VyRXJyb3JzID0gbW9uaXRvckJyb3dzZXIoXG4gICAgcGFnZSxcbiAgICBbL0ZhaWxlZCB0byBsb2FkIHJlc291cmNlOi4qNTAwIFxcKEludGVybmFsIFNlcnZlciBFcnJvclxcKS9dLFxuICApXG4gIGF3YWl0IG1vY2tPcHMocGFnZSwgeyBydW5GYWlsdXJlQ291bnQ6IDIgfSlcblxuICBhd2FpdCBwYWdlLmdvdG8oJy9vcHMvIy9ydW5zJylcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdSdW5zIOWKoOi9veWksei0pScpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgndGVtcG9yYXJ5IGRhdGFiYXNlIGZhaWx1cmUnKSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAv6YeNXFxzKuivlS8gfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ3J1bi0xJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3RTdGFibGVMYXlvdXQocGFnZSlcbiAgZXhwZWN0KGJyb3dzZXJFcnJvcnMpLnRvRXF1YWwoW10pXG59KVxuXG50ZXN0KCdrZWVwcyBiZWFyZXIgdG9rZW4gaW4gc2Vzc2lvbiBzdG9yYWdlIGFuZCByZXRyaWVzIGF1dGhvcml6YXRpb24nLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgY29uc3QgYnJvd3NlckVycm9ycyA9IG1vbml0b3JCcm93c2VyKFxuICAgIHBhZ2UsXG4gICAgWy9GYWlsZWQgdG8gbG9hZCByZXNvdXJjZTouKjQwMSBcXChVbmF1dGhvcml6ZWRcXCkvXSxcbiAgKVxuICBhd2FpdCBtb2NrT3BzKHBhZ2UsIHsgcmVxdWlyZVRva2VuOiB0cnVlIH0pXG5cbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcnVucycpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHsgbmFtZTogJ+mcgOimgSBPcHMg6K6/6Zeu5Yet6K+BJyB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBwYWdlLmdldEJ5TGFiZWwoJ09QUyBBUEkgVG9rZW4nKS5maWxsKCdicm93c2VyLXRlc3QtdG9rZW4nKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAn6aqM6K+B5bm26YeN6K+VJyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgncnVuLTEnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGV4cGVjdChcbiAgICBhd2FpdCBwYWdlLmV2YWx1YXRlKCgpID0+IHNlc3Npb25TdG9yYWdlLmdldEl0ZW0oJ2VkdWFnZW50Lm9wcy50b2tlbicpKSxcbiAgKS50b0JlKCdicm93c2VyLXRlc3QtdG9rZW4nKVxuICBhd2FpdCBleHBlY3RTdGFibGVMYXlvdXQocGFnZSlcbiAgZXhwZWN0KGJyb3dzZXJFcnJvcnMpLnRvRXF1YWwoW10pXG59KVxuXG50ZXN0KCdwb2xpY3kgZXZpZGVuY2UgZmlsdGVycywgY3Vyc29yIHBhZ2VzLCBkZXRhaWwsIG1ldHJpY3MgYW5kIGF1ZGl0IGFyZSByZWFkIG9ubHknLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XG4gIGNvbnN0IGVycm9ycyA9IG1vbml0b3JCcm93c2VyKHBhZ2UpXG4gIGNvbnN0IHJlcXVlc3RzOiBBcnJheTx7IG1ldGhvZDogc3RyaW5nOyB1cmw6IHN0cmluZyB9PiA9IFtdXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCAocmVxdWVzdCkgPT4ge1xuICAgIGlmIChyZXF1ZXN0LnVybCgpLmluY2x1ZGVzKCcvb3BzLWFwaS8nKSkgcmVxdWVzdHMucHVzaCh7IG1ldGhvZDogcmVxdWVzdC5tZXRob2QoKSwgdXJsOiByZXF1ZXN0LnVybCgpIH0pXG4gIH0pXG4gIGF3YWl0IG1vY2tPcHMocGFnZSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcG9saWNpZXMnKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICdQb2xpY2llcycsIGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dChkZXBsb3ltZW50SWQsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgaWYgKHRlc3RJbmZvLnByb2plY3QubmFtZSA9PT0gJ21vYmlsZScpIHtcbiAgICBjb25zdCBvdmVyZmxvd1RhYmxlID0gcGFnZS5sb2NhdG9yKCcuYW50LXRhYmxlLWNvbnRlbnQnKS5maXJzdCgpXG4gICAgZXhwZWN0KGF3YWl0IG92ZXJmbG93VGFibGUuZXZhbHVhdGUoKGVsZW1lbnQpID0+IGVsZW1lbnQuc2Nyb2xsV2lkdGggPiBlbGVtZW50LmNsaWVudFdpZHRoKSkudG9CZSh0cnVlKVxuICAgIGF3YWl0IG92ZXJmbG93VGFibGUuaG92ZXIoKVxuICAgIGF3YWl0IHBhZ2UubW91c2Uud2hlZWwoOTAwLCAwKVxuICAgIGF3YWl0IGV4cGVjdC5wb2xsKCgpID0+IG92ZXJmbG93VGFibGUuZXZhbHVhdGUoKGVsZW1lbnQpID0+IGVsZW1lbnQuc2Nyb2xsTGVmdCkpLnRvQmVHcmVhdGVyVGhhbigwKVxuICAgIGF3YWl0IHBhZ2UubW91c2Uud2hlZWwoLTkwMCwgMClcbiAgfVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAv5LiL5LiA6aG1LyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dChzZWNvbmREZXBsb3ltZW50SWQsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL+S4iuS4gOmhtS8gfSkuY2xpY2soKVxuICBhd2FpdCBwYWdlLmdldEJ5TGFiZWwoJ+etlueVpeeKtuaAgScpLmNsaWNrKClcbiAgYXdhaXQgcGFnZS5nZXRCeVRpdGxlKCdmcm96ZW4nLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KHNlY29uZERlcGxveW1lbnRJZCwgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL+S4i+S4gOmhtS8gfSkpLnRvQmVEaXNhYmxlZCgpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfph43nva4nIH0pLmNsaWNrKClcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCfnrZbnlaXnjq/looMnKS5jbGljaygpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlUaXRsZSgncmVoZWFyc2FsJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiBg5p+l55yL562W55WlICR7ZGVwbG95bWVudElkfWAgfSkuY2xpY2soKVxuICBjb25zdCBkZXRhaWwgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAn562W55Wl54mI5pys6K+m5oOFJyB9KVxuICBhd2FpdCBleHBlY3QoZGV0YWlsLmdldEJ5VGV4dCgnYicucmVwZWF0KDY0KSwgeyBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdjYW5hcnlfaGVhbHRoJywgeyBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdjb21taXRfZmFpbHVyZV9yYXRlJywgeyBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdoZWFsdGhfcm9sbGJhY2snLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdwcm9tb3Rpb25fdHJhbnNpdGlvbmVkJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QoZGV0YWlsLmdldEJ5VGV4dCgnY2FuYXJ5IOKGkiBmcm96ZW4nLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCfmnKrnn6UnLCB7IGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RhYicsIHsgbmFtZTogJ+WBpeW6t+eql+WPoycgfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+etlueVpeivgeaNruWIl+ihqCcgfSkuZ2V0QnlUZXh0KCdmYWlsJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgndGFiJywgeyBuYW1lOiAn5a6h6K6h5pe26Ze057q/JyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAn562W55Wl6K+B5o2u5YiX6KGoJyB9KS5nZXRCeVRleHQoJ2hlYWx0aF9yb2xsYmFjaycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC/mmYvljYd85Zue5ruafOWGu+e7k3zlj5HluIN85Yig6ZmkLyB9KSkudG9IYXZlQ291bnQoMClcbiAgZXhwZWN0KHJlcXVlc3RzLmV2ZXJ5KChyZXF1ZXN0KSA9PiByZXF1ZXN0Lm1ldGhvZCA9PT0gJ0dFVCcpKS50b0JlKHRydWUpXG4gIGV4cGVjdChyZXF1ZXN0cy5zb21lKChyZXF1ZXN0KSA9PiByZXF1ZXN0LnVybC5pbmNsdWRlcygnc3RhdGU9ZnJvemVuJykpKS50b0JlKHRydWUpXG4gIGV4cGVjdChyZXF1ZXN0cy5zb21lKChyZXF1ZXN0KSA9PiByZXF1ZXN0LnVybC5pbmNsdWRlcygnZW52aXJvbm1lbnQ9cmVoZWFyc2FsJykpKS50b0JlKHRydWUpXG4gIGF3YWl0IGV4cGVjdFN0YWJsZUxheW91dChwYWdlKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgndGFiJywgeyBuYW1lOiAn6YOo572yJyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAn562W55Wl6K+B5o2u5YiX6KGoJyB9KS5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6IGDmn6XnnIvnrZbnlaUgJHtkZXBsb3ltZW50SWR9YCB9KSkudG9CZVZpc2libGUoKVxuICBpZiAocHJvY2Vzcy5lbnYuT1BTX1NDUkVFTlNIT1RfRElSKSB7XG4gICAgYXdhaXQgcGFnZS5zY3JlZW5zaG90KHsgcGF0aDogYCR7cHJvY2Vzcy5lbnYuT1BTX1NDUkVFTlNIT1RfRElSfS9wb2xpY2llcy0ke3Rlc3RJbmZvLnByb2plY3QubmFtZX0ucG5nYCwgZnVsbFBhZ2U6IHRydWUsIGFuaW1hdGlvbnM6ICdkaXNhYmxlZCcgfSlcbiAgfVxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKVxufSlcblxudGVzdCgncG9saWN5IGxvYWRpbmcsIGVtcHR5IGZpbHRlcnMgYW5kIHN0YWxlIHJlcXVlc3RzIGRvIG5vdCByZXN0b3JlIG9sZCBldmlkZW5jZScsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBsZXQgc2xvd0RvbmUhOiAoKSA9PiB2b2lkXG4gIGNvbnN0IGZpbmlzaGVkID0gbmV3IFByb21pc2U8dm9pZD4oKHJlc29sdmUpID0+IHsgc2xvd0RvbmUgPSByZXNvbHZlIH0pXG4gIGF3YWl0IG1vY2tPcHMocGFnZSwgeyBkZWxheVBvbGljaWVzTXM6IDcwMCwgb25TbG93UG9saWN5RG9uZTogc2xvd0RvbmUgfSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcG9saWNpZXMnLCB7IHdhaXRVbnRpbDogJ2NvbW1pdCcgfSlcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLmFudC1za2VsZXRvbicpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlMYWJlbCgn562W55Wl546v5aKDJykuY2xpY2soKVxuICBhd2FpdCBwYWdlLmdldEJ5VGl0bGUoJ3Byb2R1Y3Rpb24nLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCfmsqHmnInnrKblkIjmnaHku7bnmoTnrZbnlaXor4Hmja4nKSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBmaW5pc2hlZFxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoZGVwbG95bWVudElkLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVDb3VudCgwKVxuICBhd2FpdCBleHBlY3RTdGFibGVMYXlvdXQocGFnZSlcbn0pXG5cbnRlc3QoJ3BvbGljeSBlcnJvcnMgYW5kIGRldGFpbCBlcnJvcnMgaGF2ZSBpbmRlcGVuZGVudCByZXRyeSByZWNvdmVyeScsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBhd2FpdCBtb2NrT3BzKHBhZ2UsIHsgcG9saWN5RmFpbHVyZUNvdW50OiAyLCBwb2xpY3lEZXRhaWxGYWlsdXJlQ291bnQ6IDIgfSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcG9saWNpZXMnKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+etlueVpeivgeaNruWKoOi9veWksei0pScpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC/ph41cXHMq6K+VLyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dChkZXBsb3ltZW50SWQsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6IGDmn6XnnIvnrZbnlaUgJHtkZXBsb3ltZW50SWR9YCB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgn562W55Wl6K+m5oOF5Yqg6L295aSx6LSlJykpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+etlueVpeeJiOacrOivpuaDhScgfSkuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC/ph41cXHMq6K+VLyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnYicucmVwZWF0KDY0KSwgeyBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpXG59KVxuXG50ZXN0KCdwb2xpY3kgc3RyaWN0IHJlc3BvbnNlIGd1YXJkIHJlamVjdHMgZXh0cmEgZnJlZWZvcm0gZmllbGRzJywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGF3YWl0IG1vY2tPcHMocGFnZSwgeyBtYWxmb3JtZWRQb2xpY3k6IHRydWUgfSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcG9saWNpZXMnKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+etlueVpeivgeaNruWKoOi9veWksei0pScpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgv5ZON5bqU5qC85byP6ZSZ6K+vLykpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdtdXN0LW5vdC1yZW5kZXInKSkudG9IYXZlQ291bnQoMClcbn0pXG5cbnRlc3QoJ3BvbGljeSBhdXRoZW50aWNhdGlvbiB1c2VzIGV4aXN0aW5nIE9wcyB0b2tlbiBhbmQgY2xlYXJzIGl0IG9uIGxvY2snLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgYXdhaXQgbW9ja09wcyhwYWdlLCB7IHJlcXVpcmVUb2tlbjogdHJ1ZSB9KVxuICBhd2FpdCBwYWdlLmdvdG8oYC9vcHMvIy9wb2xpY2llcy8ke2RlcGxveW1lbnRJZH1gKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICfpnIDopoEgT3BzIOiuv+mXruWHreivgScgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdPUFMgQVBJIFRva2VuJykuZmlsbCgnYnJvd3Nlci10ZXN0LXRva2VuJylcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ+mqjOivgeW5tumHjeivlScgfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+etlueVpeeJiOacrOivpuaDhScgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdiJy5yZXBlYXQoNjQpLCB7IGV4YWN0OiB0cnVlIH0pLmZpcnN0KCkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ+mUgeWumuaOp+WItuWPsOW5tua4hemZpOS8muivnSB0b2tlbicgfSkuY2xpY2soKVxuICBleHBlY3QoYXdhaXQgcGFnZS5ldmFsdWF0ZSgoKSA9PiBzZXNzaW9uU3RvcmFnZS5nZXRJdGVtKCdlZHVhZ2VudC5vcHMudG9rZW4nKSkpLnRvQmVOdWxsKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywgeyBuYW1lOiAn6ZyA6KaBIE9wcyDorr/pl67lh63or4EnIH0pKS50b0JlVmlzaWJsZSgpXG59KVxuXG50ZXN0KCdwb2xpY3kgUnVuIGFuZCBUcmFjZSBkaXNwbGF5IHN0b3JlZCBpbW11dGFibGUgaWRlbnRpdHkgYW5kIGxpbmsgdmVyc2lvbiBldmlkZW5jZScsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcbiAgYXdhaXQgbW9ja09wcyhwYWdlKVxuICBhd2FpdCBwYWdlLmdvdG8oJy9vcHMvIy9ydW5zJylcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ+afpeeci+i/kOihjCBydW4tMSDor6bmg4UnIH0pLmNsaWNrKClcbiAgY29uc3QgZHJhd2VyID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ+i/kOihjOivpuaDhScgfSlcbiAgYXdhaXQgZXhwZWN0KGRyYXdlci5nZXRCeVRleHQoJ2InLnJlcGVhdCg2NCksIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KGRyYXdlci5nZXRCeVRleHQoJ2NhbmRpZGF0ZScsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZHJhd2VyLmdldEJ5Um9sZSgnbGluaycsIHsgbmFtZTogJ2EnLnJlcGVhdCgzMikgfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICfov5DooYwgVHJhY2UnIH0pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnYicucmVwZWF0KDY0KSwgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+i/kOihjOetlueVpee7keWumicgfSkuZ2V0QnlUZXh0KCdjYW5kaWRhdGUgwrcgcmVoZWFyc2FsJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBpZiAocHJvY2Vzcy5lbnYuT1BTX1NDUkVFTlNIT1RfRElSKSB7XG4gICAgYXdhaXQgcGFnZS5zY3JlZW5zaG90KHsgcGF0aDogYCR7cHJvY2Vzcy5lbnYuT1BTX1NDUkVFTlNIT1RfRElSfS9wb2xpY3ktdHJhY2UtJHt0ZXN0SW5mby5wcm9qZWN0Lm5hbWV9LnBuZ2AsIGZ1bGxQYWdlOiB0cnVlIH0pXG4gIH1cbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6IGRlcGxveW1lbnRJZCwgZXhhY3Q6IHRydWUgfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+etlueVpeeJiOacrOivpuaDhScgfSkuZ2V0QnlUZXh0KCdyZWhlYXJzYWwgwrcg54mI5pysIDInLCB7IGV4YWN0OiBmYWxzZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+W9k+WJjeeJiOacrCAzJywgeyBleGFjdDogZmFsc2UgfSkuZmlyc3QoKSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBwYWdlLmdvdG8oJy9vcHMvIy90cmFjZS9ydW4tMScpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnYicucmVwZWF0KDY0KSwgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3RTdGFibGVMYXlvdXQocGFnZSlcbn0pXG5cbnRlc3QoJ3BvbGljeSBsZWdhY3kgUnVuIGFuZCBUcmFjZSBpZGVudGl0eSByZW1haW5zIHVuYXZhaWxhYmxlIHdpdGhvdXQgY3VycmVudCBwb2xpY3kgZmFsbGJhY2snLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgYXdhaXQgbW9ja09wcyhwYWdlLCB7IGxlZ2FjeUJpbmRpbmc6IHRydWUgfSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvdHJhY2UvcnVuLTEnKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+etlueVpee7keWumuS4jeWPr+eUqCcpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnYicucmVwZWF0KDY0KSwgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlQ291bnQoMClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiBkZXBsb3ltZW50SWQsIGV4YWN0OiB0cnVlIH0pKS50b0hhdmVDb3VudCgwKVxufSlcblxuZm9yIChjb25zdCBzY2VuYXJpbyBvZiBbXG4gIHsgbmFtZTogJ2FjdG9yIGZyZWVmb3JtJywgcGF0aDogJy9wb2xpY2llcy9kZXBsb3ltZW50cycsIHBhZ2U6ICcjL3BvbGljaWVzJyxcbiAgICBib2R5OiB7IGl0ZW1zOiBbeyAuLi5wb2xpY3lEZXBsb3ltZW50KCksIGFjdG9yOiAnaW5ub2NlbnQtcHJpdmF0ZS12YWx1ZScgfV0sIG5leHRfY3Vyc29yOiBudWxsIH0gfSxcbiAgeyBuYW1lOiAnaGFzaCBpZGVudGl0eScsIHBhdGg6ICcvcG9saWNpZXMvZGVwbG95bWVudHMnLCBwYWdlOiAnIy9wb2xpY2llcycsXG4gICAgYm9keTogeyBpdGVtczogW3sgLi4ucG9saWN5RGVwbG95bWVudCgpLCBzdGFibGVfcG9saWN5X2hhc2g6ICdpbm5vY2VudC1wcml2YXRlLXZhbHVlJyB9XSwgbmV4dF9jdXJzb3I6IG51bGwgfSB9LFxuICB7IG5hbWU6ICdtaXNzaW5nIHJlcXVpcmVkIGJpbmRpbmcnLCBwYXRoOiAnL3J1bnMvcnVuLTEvdHJhY2UnLCBwYWdlOiAnIy90cmFjZS9ydW4tMScsXG4gICAgYm9keTogeyAuLi50cmFjZSwgZWZmZWN0aXZlX3BvbGljeV9oYXNoOiB1bmRlZmluZWQgfSB9LFxuICB7IG5hbWU6ICdyYXcgbmFtZXNwYWNlJywgcGF0aDogJy9ydW5zL3J1bi0xL3RyYWNlJywgcGFnZTogJyMvdHJhY2UvcnVuLTEnLFxuICAgIGJvZHk6IHsgLi4udHJhY2UsIG5hbWVzcGFjZV9jbGFzczogJ2lubm9jZW50LXByaXZhdGUtdmFsdWUnIH0gfSxcbiAgeyBuYW1lOiAnZGV0YWlsIG5lc3RlZCBleHRyYXMnLCBwYXRoOiBgL3BvbGljaWVzL2RlcGxveW1lbnRzLyR7ZGVwbG95bWVudElkfWAsIHBhZ2U6IGAjL3BvbGljaWVzLyR7ZGVwbG95bWVudElkfWAsXG4gICAgYm9keTogeyAuLi5wb2xpY3lEZXRhaWwoKSwgZ2F0ZV9yZWNlaXB0czogW3sgLi4ucG9saWN5RGV0YWlsKCkuZ2F0ZV9yZWNlaXB0c1swXSwgZGV0YWlsczogeyBpbm5vY2VudDogJ2lubm9jZW50LXByaXZhdGUtdmFsdWUnIH0gfV0gfSB9LFxuICB7IG5hbWU6ICdkZXRhaWwgaW52YWxpZCBtZXRyaWMnLCBwYXRoOiBgL3BvbGljaWVzL2RlcGxveW1lbnRzLyR7ZGVwbG95bWVudElkfWAsIHBhZ2U6IGAjL3BvbGljaWVzLyR7ZGVwbG95bWVudElkfWAsXG4gICAgYm9keTogeyAuLi5wb2xpY3lEZXRhaWwoKSwgbGF0ZXN0X2hlYWx0aF93aW5kb3c6IHsgLi4uaGVhbHRoV2luZG93LCBjYW5kaWRhdGVfc3RhdHM6IHsgLi4uc3RhdHMsIHVua25vd25fcmF0ZTogJzInIH0gfSB9IH0sXG5dKSB7XG4gIHRlc3QoYHBvbGljeSBzdHJpY3QgdHlwZWQgcmVzcG9uc2UgcmVqZWN0cyAke3NjZW5hcmlvLm5hbWV9YCwgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gICAgYXdhaXQgbW9ja09wcyhwYWdlKVxuICAgIGF3YWl0IHBhZ2Uucm91dGUoYCoqL29wcy1hcGkvb3BzJHtzY2VuYXJpby5wYXRofSpgLCAocm91dGUpID0+IHJvdXRlLmZ1bGZpbGwoeyBqc29uOiBzY2VuYXJpby5ib2R5IH0pKVxuICAgIGF3YWl0IHBhZ2UuZ290byhgL29wcy8ke3NjZW5hcmlvLnBhZ2V9YClcbiAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoL+WTjeW6lOagvOW8j+mUmeivry8pKS50b0JlVmlzaWJsZSgpXG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdpbm5vY2VudC1wcml2YXRlLXZhbHVlJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlQ291bnQoMClcbiAgICBhd2FpdCBleHBlY3RTdGFibGVMYXlvdXQocGFnZSlcbiAgfSlcbn1cblxudGVzdCgncG9saWN5IHN0cmljdCBoZWFsdGggYW5kIGF1ZGl0IGd1YXJkcyByZWplY3QgZnJlZWZvcm0gYWdncmVnYXRlcyBhbmQgcmVhc29ucycsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBhd2FpdCBtb2NrT3BzKHBhZ2UpXG4gIGF3YWl0IHBhZ2Uucm91dGUoJyoqL29wcy1hcGkvb3BzL3BvbGljaWVzL2hlYWx0aC13aW5kb3dzKicsIChyb3V0ZSkgPT4gcm91dGUuZnVsZmlsbCh7XG4gICAganNvbjogeyBpdGVtczogW3sgLi4uaGVhbHRoV2luZG93LCBjYW5kaWRhdGVfc3RhdHM6IHsgLi4uc3RhdHMsIG1lYW5fY29zdDogJ2lubm9jZW50LXByaXZhdGUtdmFsdWUnIH0gfV0sIG5leHRfY3Vyc29yOiBudWxsIH0sXG4gIH0pKVxuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9vcHMtYXBpL29wcy9wb2xpY2llcy9hdWRpdConLCAocm91dGUpID0+IHJvdXRlLmZ1bGZpbGwoe1xuICAgIGpzb246IHsgaXRlbXM6IFt7IC4uLmF1ZGl0RXZlbnQsIHJlYXNvbjogJ2lubm9jZW50LXByaXZhdGUtdmFsdWUnIH1dLCBuZXh0X2N1cnNvcjogbnVsbCB9LFxuICB9KSlcbiAgYXdhaXQgcGFnZS5nb3RvKCcvb3BzLyMvcG9saWNpZXMnKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgndGFiJywgeyBuYW1lOiAn5YGl5bq356qX5Y+jJyB9KS5jbGljaygpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgv5ZON5bqU5qC85byP6ZSZ6K+vLykpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RhYicsIHsgbmFtZTogJ+WuoeiuoeaXtumXtOe6vycgfSkuY2xpY2soKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoL+WTjeW6lOagvOW8j+mUmeivry8pKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnaW5ub2NlbnQtcHJpdmF0ZS12YWx1ZScsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZUNvdW50KDApXG59KVxuXG50ZXN0KCdwb2xpY3kgZGV0YWlsIGVtcHR5IGV2aWRlbmNlIGlzIGV4cGxpY2l0bHkgdW5hdmFpbGFibGUnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgYXdhaXQgbW9ja09wcyhwYWdlKVxuICBhd2FpdCBwYWdlLnJvdXRlKGAqKi9vcHMtYXBpL29wcy9wb2xpY2llcy9kZXBsb3ltZW50cy8ke2RlcGxveW1lbnRJZH1gLCAocm91dGUpID0+IHJvdXRlLmZ1bGZpbGwoe1xuICAgIGpzb246IHsgLi4ucG9saWN5RGV0YWlsKCksIHJlcXVpcmVkX3JlY2VpcHRzOiBbXSwgZ2F0ZV9yZWNlaXB0czogW10sIGxhdGVzdF9oZWFsdGhfd2luZG93OiBudWxsLCBhdWRpdF9ldmVudHM6IFtdIH0sXG4gIH0pKVxuICBhd2FpdCBwYWdlLmdvdG8oYC9vcHMvIy9wb2xpY2llcy8ke2RlcGxveW1lbnRJZH1gKVxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ+aaguaXoCBHYXRlIOaUtuaNricpKS50b0JlVmlzaWJsZSgpXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgn5pqC5peg5YGl5bq356qX5Y+j77yM5oyH5qCH5LiN5Y+v55SoJykpLnRvQmVWaXNpYmxlKClcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCfmmoLml6DlrqHorqHkuovku7YnKSkudG9CZVZpc2libGUoKVxufSlcblxudGVzdCgncG9saWN5IGRldGFpbCBzZWxlY3Rpb24gaWdub3JlcyBkZWxheWVkIHByZXZpb3VzIHZlcnNpb24gcmVzcG9uc2VzJywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGF3YWl0IG1vY2tPcHMocGFnZSlcbiAgbGV0IHN0YXJ0ZWQhOiAoKSA9PiB2b2lkXG4gIGxldCByZWxlYXNlITogKCkgPT4gdm9pZFxuICBsZXQgZnVsZmlsbGVkITogKCkgPT4gdm9pZFxuICBjb25zdCBwZW5kaW5nID0gbmV3IFByb21pc2U8dm9pZD4oKHJlc29sdmUpID0+IHsgcmVsZWFzZSA9IHJlc29sdmUgfSlcbiAgY29uc3QgaW5pdGlhbCA9IG5ldyBQcm9taXNlPHZvaWQ+KChyZXNvbHZlKSA9PiB7IHN0YXJ0ZWQgPSByZXNvbHZlIH0pXG4gIGNvbnN0IGNvbXBsZXRlZCA9IG5ldyBQcm9taXNlPHZvaWQ+KChyZXNvbHZlKSA9PiB7IGZ1bGZpbGxlZCA9IHJlc29sdmUgfSlcbiAgYXdhaXQgcGFnZS5yb3V0ZShgKiovb3BzLWFwaS9vcHMvcG9saWNpZXMvZGVwbG95bWVudHMvJHtkZXBsb3ltZW50SWR9YCwgYXN5bmMgKHJvdXRlKSA9PiB7XG4gICAgc3RhcnRlZCgpXG4gICAgYXdhaXQgcGVuZGluZ1xuICAgIGF3YWl0IHJvdXRlLmZ1bGZpbGwoeyBqc29uOiBwb2xpY3lEZXRhaWwoKSB9KVxuICAgIGZ1bGZpbGxlZCgpXG4gIH0pXG4gIGF3YWl0IHBhZ2UuZ290byhgL29wcy8jL3BvbGljaWVzLyR7ZGVwbG95bWVudElkfWApXG4gIGF3YWl0IGluaXRpYWxcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL+S4i+S4gOmhtS8gfSkuY2xpY2soKVxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAn562W55Wl6K+B5o2u5YiX6KGoJyB9KS5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6IGDmn6XnnIvnrZbnlaUgJHtzZWNvbmREZXBsb3ltZW50SWR9YCB9KS5jbGljaygpXG4gIGNvbnN0IGRldGFpbCA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICfnrZbnlaXniYjmnKzor6bmg4UnIH0pXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdyZWhlYXJzYWwgwrcg54mI5pysIDMnLCB7IGV4YWN0OiBmYWxzZSB9KSkudG9CZVZpc2libGUoKVxuICByZWxlYXNlKClcbiAgYXdhaXQgY29tcGxldGVkXG4gIGF3YWl0IGV4cGVjdChkZXRhaWwuZ2V0QnlUZXh0KCdyZWhlYXJzYWwgwrcg54mI5pysIDMnLCB7IGV4YWN0OiBmYWxzZSB9KSkudG9CZVZpc2libGUoKVxuICBhd2FpdCBleHBlY3QoZGV0YWlsLmdldEJ5VGV4dCgncmVoZWFyc2FsIMK3IOeJiOacrCAyJywgeyBleGFjdDogZmFsc2UgfSkpLnRvSGF2ZUNvdW50KDApXG59KVxuXG5mb3IgKGNvbnN0IHNjZW5hcmlvIG9mIFsnY29uc3VtZWQnLCAnb2xkLWxvY2FsJywgJ21pc3NpbmcnXSBhcyBjb25zdCkge1xuICB0ZXN0KGBoZWFsdGggc291cmNlICR7c2NlbmFyaW99IGlzIGV4cGxpY2l0IGFuZCBkb2VzIG5vdCBjbGFpbSBhIG5ldyBwYXNzaW5nIHdpbmRvd2AsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICAgIGF3YWl0IG1vY2tPcHMocGFnZSlcbiAgICBjb25zdCBib2R5ID0gcG9saWN5RGV0YWlsKHNlY29uZERlcGxveW1lbnRJZClcbiAgICBib2R5LnN0YXRlID0gJ2FjdGl2ZSdcbiAgICBib2R5LmxhdGVzdF9oZWFsdGhfd2luZG93ID0geyAuLi5ib2R5LmxhdGVzdF9oZWFsdGhfd2luZG93LCBkZWNpc2lvbjogJ2hvbGQnLCB0cmlnZ2VyZWRfdGhyZXNob2xkczogW10gfVxuICAgIGlmIChzY2VuYXJpbyA9PT0gJ21pc3NpbmcnKSB7XG4gICAgICBib2R5LmdhdGVfcmVjZWlwdHMgPSBbXVxuICAgIH0gZWxzZSB7XG4gICAgICBib2R5LmdhdGVfcmVjZWlwdHNbMF0uc3RhdHVzID0gJ3Bhc3NlZCdcbiAgICAgIGJvZHkuZ2F0ZV9yZWNlaXB0c1swXS5oZWFsdGhfc291cmNlLndpbmRvd19kZWNpc2lvbiA9ICdwYXNzJ1xuICAgICAgYm9keS5nYXRlX3JlY2VpcHRzWzBdLmhlYWx0aF9zb3VyY2UuaXNfbGF0ZXN0X3dpbmRvdyA9IGZhbHNlXG4gICAgICBpZiAoc2NlbmFyaW8gPT09ICdjb25zdW1lZCcpIHtcbiAgICAgICAgYm9keS5nYXRlX3JlY2VpcHRzWzBdLmhlYWx0aF9zb3VyY2UucmVsYXRpb24gPSAnY29uc3VtZWRfY2hhaW4nXG4gICAgICAgIGJvZHkuZ2F0ZV9yZWNlaXB0c1swXS5oZWFsdGhfc291cmNlLmRlcGxveW1lbnRfaWQgPSBkZXBsb3ltZW50SWRcbiAgICAgICAgYm9keS5nYXRlX3JlY2VpcHRzWzBdLmhlYWx0aF9zb3VyY2UuZGVwbG95bWVudF92ZXJzaW9uID0gMlxuICAgICAgfVxuICAgIH1cbiAgICBhd2FpdCBwYWdlLnJvdXRlKGAqKi9vcHMtYXBpL29wcy9wb2xpY2llcy9kZXBsb3ltZW50cy8ke3NlY29uZERlcGxveW1lbnRJZH1gLCAocm91dGUpID0+IHJvdXRlLmZ1bGZpbGwoeyBqc29uOiBib2R5IH0pKVxuICAgIGF3YWl0IHBhZ2UuZ290byhgL29wcy8jL3BvbGljaWVzLyR7c2Vjb25kRGVwbG95bWVudElkfWApXG4gICAgY29uc3QgZGV0YWlsID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ+etlueVpeeJiOacrOivpuaDhScgfSlcbiAgICBhd2FpdCBleHBlY3QoZGV0YWlsLmdldEJ5VGV4dCgnaG9sZCcsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKClcbiAgICBjb25zdCBleHBsYW5hdGlvbiA9IHNjZW5hcmlvID09PSAnY29uc3VtZWQnID8gJ+W3sua2iOi0ueWJjeW6j+ivgeaNru+8iOmdnuacrOmDqOe9suaWsOingua1i++8iSdcbiAgICAgIDogc2NlbmFyaW8gPT09ICdvbGQtbG9jYWwnID8gJ+acrOmDqOe9suaXp+eql+WPo+ivgeaNru+8jOS4jeS7o+ihqOacgOaWsOWBpeW6t+mAmui/hycgOiAndW5rbm93bidcbiAgICBhd2FpdCBleHBlY3QoZGV0YWlsLmdldEJ5VGV4dChleHBsYW5hdGlvbiwgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKVxuICAgIGF3YWl0IGV4cGVjdFN0YWJsZUxheW91dChwYWdlKVxuICB9KVxufVxuXG5mb3IgKGNvbnN0IG11dGF0aW9uIG9mIFsnZXh0cmEnLCAnd3JvbmctbG9jYWwnLCAnbnVsbC1oZWFsdGgnLCAnbm9ucGFzc2luZy1jb25zdW1lZCddIGFzIGNvbnN0KSB7XG4gIHRlc3QoYGNsb3NlZCBoZWFsdGggc291cmNlIHJlamVjdHMgJHttdXRhdGlvbn1gLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgICBhd2FpdCBtb2NrT3BzKHBhZ2UpXG4gICAgY29uc3QgYm9keSA9IHBvbGljeURldGFpbCgpXG4gICAgY29uc3QgcmVjZWlwdCA9IGJvZHkuZ2F0ZV9yZWNlaXB0c1swXVxuICAgIGlmIChtdXRhdGlvbiA9PT0gJ2V4dHJhJykgT2JqZWN0LmFzc2lnbihyZWNlaXB0LmhlYWx0aF9zb3VyY2UsIHsgZGV0YWlsczogJ3ByaXZhdGUtc291cmNlLXZhbHVlJyB9KVxuICAgIGlmIChtdXRhdGlvbiA9PT0gJ3dyb25nLWxvY2FsJykgcmVjZWlwdC5oZWFsdGhfc291cmNlLmRlcGxveW1lbnRfaWQgPSBzZWNvbmREZXBsb3ltZW50SWRcbiAgICBpZiAobXV0YXRpb24gPT09ICdudWxsLWhlYWx0aCcpIE9iamVjdC5hc3NpZ24ocmVjZWlwdCwgeyBoZWFsdGhfc291cmNlOiBudWxsIH0pXG4gICAgaWYgKG11dGF0aW9uID09PSAnbm9ucGFzc2luZy1jb25zdW1lZCcpIHJlY2VpcHQuaGVhbHRoX3NvdXJjZS5yZWxhdGlvbiA9ICdjb25zdW1lZF9jaGFpbidcbiAgICBhd2FpdCBwYWdlLnJvdXRlKGAqKi9vcHMtYXBpL29wcy9wb2xpY2llcy9kZXBsb3ltZW50cy8ke2RlcGxveW1lbnRJZH1gLCAocm91dGUpID0+IHJvdXRlLmZ1bGZpbGwoeyBqc29uOiBib2R5IH0pKVxuICAgIGF3YWl0IHBhZ2UuZ290byhgL29wcy8jL3BvbGljaWVzLyR7ZGVwbG95bWVudElkfWApXG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC/lk43lupTmoLzlvI/plJnor68vKSkudG9CZVZpc2libGUoKVxuICAgIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgncHJpdmF0ZS1zb3VyY2UtdmFsdWUnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVDb3VudCgwKVxuICB9KVxufVxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxNQUFNLEVBQVFDLElBQUksUUFBUSxrQkFBa0I7QUFFckQsTUFBTUMsS0FBSyxHQUFHO0VBQ1pDLFdBQVcsRUFBRSxDQUFDO0VBQ2RDLFVBQVUsRUFBRSxDQUFDO0VBQ2JDLFlBQVksRUFBRSxHQUFHO0VBQ2pCQyxhQUFhLEVBQUUsRUFBRTtFQUNqQkMsa0JBQWtCLEVBQUUsUUFBUTtFQUM1QkMsU0FBUyxFQUFFO0FBQ2IsQ0FBQztBQUVELE1BQU1DLFlBQVksR0FBRyxzQ0FBc0M7QUFDM0QsTUFBTUMsa0JBQWtCLEdBQUcsc0NBQXNDO0FBQ2pFLE1BQU1DLE9BQU8sR0FBRztFQUNkQyxhQUFhLEVBQUVILFlBQVk7RUFDM0JJLHFCQUFxQixFQUFFLEdBQUcsQ0FBQ0MsTUFBTSxDQUFDLEVBQUUsQ0FBQztFQUNyQ0MsYUFBYSxFQUFFLFdBQVc7RUFDMUJDLGVBQWUsRUFBRTtBQUNuQixDQUFDO0FBRUQsTUFBTUMsR0FBRyxHQUFHQSxDQUFDQyxFQUFVLEVBQUVDLE1BQU0sR0FBRyxXQUFXLE1BQU07RUFDakQsR0FBR1IsT0FBTztFQUNWUyxNQUFNLEVBQUVGLEVBQUU7RUFDVkcsU0FBUyxFQUFFLGVBQWU7RUFDMUJGLE1BQU07RUFDTkcsUUFBUSxFQUFFSixFQUFFLEtBQUssT0FBTyxHQUFHLEdBQUcsQ0FBQ0osTUFBTSxDQUFDLEVBQUUsQ0FBQyxHQUFHLEdBQUcsQ0FBQ0EsTUFBTSxDQUFDLEVBQUUsQ0FBQztFQUMxRFMsYUFBYSxFQUFFLENBQUM7RUFDaEJDLEtBQUssRUFBRSxjQUFjO0VBQ3JCQyxhQUFhLEVBQUUsQ0FBQztFQUNoQkMsZ0JBQWdCLEVBQUUsc0JBQXNCO0VBQ3hDQyxXQUFXLEVBQUVSLE1BQU0sS0FBSyxTQUFTO0VBQ2pDUyxnQkFBZ0IsRUFBRSxDQUFDO0VBQ25CMUIsS0FBSztFQUNMMkIsVUFBVSxFQUFFLElBQUk7RUFDaEJD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