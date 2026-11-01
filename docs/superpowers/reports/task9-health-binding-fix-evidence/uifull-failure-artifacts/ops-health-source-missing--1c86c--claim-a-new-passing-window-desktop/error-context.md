# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ops.spec.ts >> health source missing is explicit and does not claim a new passing window
- Location: e2e/ops.spec.ts:712:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: '策略版本详情' }).getByText('暂无 Gate 收据', { exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '策略版本详情' }).getByText('暂无 Gate 收据', { exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: '策略版本详情' }).getByText('暂无 Gate 收据', { exact: true })

```

```yaml
- banner:
  - link "EduAgent Ops 首页":
    - /url: "#/runs"
    - strong: EduAgent Ops
    - text: 只读运行面板
  - navigation "Ops 导航":
    - link "Runs":
      - /url: "#/runs"
    - link "Trace":
      - /url: "#/runs"
    - link "Workers":
      - /url: "#/workers"
    - link "Policies":
      - /url: "#/policies"
  - button "锁定控制台并清除会话 token":
    - img
    - text: 锁定
- main:
  - text: OPERATIONS
  - heading "Policies" [level=1]
  - text: Read only
  - region "Policies 只读证据":
    - text: 全部环境
    - combobox "策略环境"
    - img "down"
    - text: 全部状态
    - combobox "策略状态"
    - img "down"
    - button "重置":
      - img
      - text: 重置
    - button "刷新":
      - img
      - text: 刷新
    - tablist:
      - tab "部署" [selected]
      - tab "健康窗口"
      - tab "审计时间线"
    - tabpanel "部署"
    - region "策略证据列表":
      - table:
        - rowgroup:
          - row "Deployment 环境 / 版本 状态 当前部署 Stable / Candidate Candidate 流量 Cohort 运行数 创建时间":
            - columnheader "Deployment"
            - columnheader "环境 / 版本"
            - columnheader "状态"
            - columnheader "当前部署"
            - columnheader "Stable / Candidate"
            - columnheader "Candidate 流量"
            - columnheader "Cohort 运行数"
            - columnheader "创建时间"
        - rowgroup:
          - row "查看策略 11111111-1111-1111-1111-111111111111 rehearsal 版本 2 canary historical 当前版本 3 S aaaaaaaaaaaa C bbbbbbbbbbbb 50% S 20 · C 20 · Shadow 10 2026/10/30 10:00:00":
            - cell "查看策略 11111111-1111-1111-1111-111111111111":
              - link "查看策略 11111111-1111-1111-1111-111111111111":
                - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                - code: 11111111-1111-1111-1111-111111111111
            - cell "rehearsal 版本 2":
              - text: rehearsal
              - strong: 版本 2
            - cell "canary"
            - cell "historical 当前版本 3"
            - cell "S aaaaaaaaaaaa C bbbbbbbbbbbb":
              - code: S aaaaaaaaaaaa
              - code: C bbbbbbbbbbbb
            - cell "50%"
            - cell "S 20 · C 20 · Shadow 10"
            - cell "2026/10/30 10:00:00"
    - button "上一页" [disabled]:
      - img
      - text: 上一页
    - text: 第 1 页
    - button "下一页":
      - text: 下一页
      - img
    - region "策略版本详情":
      - heading "策略版本详情" [level=3]
      - link "关闭详情":
        - /url: "#/policies"
      - table:
        - rowgroup:
          - row "Deployment 22222222-2222-2222-2222-222222222222":
            - rowheader "Deployment"
            - cell "22222222-2222-2222-2222-222222222222":
              - code: 22222222-2222-2222-2222-222222222222
          - row "环境 / 版本 rehearsal · 版本 3 active":
            - rowheader "环境 / 版本"
            - cell "rehearsal · 版本 3 active"
          - row "当前部署 查看策略 22222222-2222-2222-2222-222222222222 · 当前版本 3":
            - rowheader "当前部署"
            - cell "查看策略 22222222-2222-2222-2222-222222222222 · 当前版本 3":
              - link "查看策略 22222222-2222-2222-2222-222222222222":
                - /url: "#/policies/22222222-2222-2222-2222-222222222222"
                - code: 22222222-2222-2222-2222-222222222222
              - text: · 当前版本 3
          - row "Stable hash aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":
            - rowheader "Stable hash"
            - cell "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":
              - code: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
          - row "Candidate hash bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb":
            - rowheader "Candidate hash"
            - cell "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb":
              - code: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
          - row "流量 / Cohort 0% candidate · Stable 20 / Candidate 20 / Shadow 10":
            - rowheader "流量 / Cohort"
            - cell "0% candidate · Stable 20 / Candidate 20 / Shadow 10"
          - row "Actor / Reason redacted / redacted":
            - rowheader "Actor / Reason"
            - cell "redacted / redacted"
          - row "创建 2026/10/30 10:00:00":
            - rowheader "创建"
            - cell "2026/10/30 10:00:00"
      - paragraph: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
      - heading "冻结阈值" [level=3]
      - term: candidate_min_runs
      - definition: "20"
      - term: stable_min_runs
      - definition: "20"
      - term: window_max_runs
      - definition: "50"
      - term: commit_failure_rate
      - definition: "0.05"
      - term: terminal_failure_rate
      - definition: "0.10"
      - term: latency_increase_rate
      - definition: "0.50"
      - term: mean_cost_increase_rate
      - definition: "0.30"
      - term: unknown_rate
      - definition: "0.10"
      - term: relative_epsilon
      - definition: "0.000001"
      - heading "Gate Receipts" [level=3]
      - paragraph: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
      - text: canary_health unknown
      - heading "最新健康窗口" [level=3]
      - paragraph: hold 2026/10/30 10:03:00 · 指标协议 v1
      - paragraph: 触发阈值：无。未知指标保持未知，不作为零值。
      - table:
        - rowgroup:
          - row "指标 Candidate Stable":
            - columnheader "指标"
            - columnheader "Candidate"
            - columnheader "Stable"
        - rowgroup:
          - row "run_count 20 20":
            - cell "run_count"
            - cell "20"
            - cell "20"
          - row "commit_failure_rate 0.05 0.05":
            - cell "commit_failure_rate"
            - cell "0.05"
            - cell "0.05"
          - row "terminal_failure_rate 0.10 0.10":
            - cell "terminal_failure_rate"
            - cell "0.10"
            - cell "0.10"
          - row "p95_latency 1.25 1.25":
            - cell "p95_latency"
            - cell "1.25"
            - cell "1.25"
          - row "mean_cost 0.01 未知":
            - cell "mean_cost"
            - cell "0.01"
            - cell "未知"
          - row "structured_decision_count 10 10":
            - cell "structured_decision_count"
            - cell "10"
            - cell "10"
          - row "unknown_decision_count 1 1":
            - cell "unknown_decision_count"
            - cell "1"
            - cell "1"
          - row "unknown_rate 0.10 0.10":
            - cell "unknown_rate"
            - cell "0.10"
            - cell "0.10"
          - row "fault_injected_count 1 1":
            - cell "fault_injected_count"
            - cell "1"
            - cell "1"
          - row "injected_commit_failure_count 1 1":
            - cell "injected_commit_failure_count"
            - cell "1"
            - cell "1"
          - row "natural_failure_count 0 0":
            - cell "natural_failure_count"
            - cell "0"
            - cell "0"
          - row "latency_increase_rate 未知 未知":
            - cell "latency_increase_rate"
            - cell "未知"
            - cell "未知"
          - row "mean_cost_increase_rate 未知 未知":
            - cell "mean_cost_increase_rate"
            - cell "未知"
            - cell "未知"
      - heading "回滚 / 冻结审计时间线" [level=3]
      - list:
        - listitem:
          - strong: health_rollback
          - text: 2026/10/30 10:03:01 · rehearsal
          - link "查看策略 11111111-1111-1111-1111-111111111111":
            - /url: "#/policies/11111111-1111-1111-1111-111111111111"
            - code: 11111111-1111-1111-1111-111111111111
          - code: Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
          - text: "actor: redacted · reason: redacted"
        - listitem:
          - strong: promotion_transitioned
          - text: canary → frozen 2026/10/30 10:03:01 · rehearsal
          - link "查看策略 11111111-1111-1111-1111-111111111111":
            - /url: "#/policies/11111111-1111-1111-1111-111111111111"
            - code: 11111111-1111-1111-1111-111111111111
          - text: "actor: redacted · reason: redacted"
      - paragraph: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  635 |   { name: 'actor freeform', path: '/policies/deployments', page: '#/policies',
  636 |     body: { items: [{ ...policyDeployment(), actor: 'innocent-private-value' }], next_cursor: null } },
  637 |   { name: 'hash identity', path: '/policies/deployments', page: '#/policies',
  638 |     body: { items: [{ ...policyDeployment(), stable_policy_hash: 'innocent-private-value' }], next_cursor: null } },
  639 |   { name: 'missing required binding', path: '/runs/run-1/trace', page: '#/trace/run-1',
  640 |     body: { ...trace, effective_policy_hash: undefined } },
  641 |   { name: 'raw namespace', path: '/runs/run-1/trace', page: '#/trace/run-1',
  642 |     body: { ...trace, namespace_class: 'innocent-private-value' } },
  643 |   { name: 'detail nested extras', path: `/policies/deployments/${deploymentId}`, page: `#/policies/${deploymentId}`,
  644 |     body: { ...policyDetail(), gate_receipts: [{ ...policyDetail().gate_receipts[0], details: { innocent: 'innocent-private-value' } }] } },
  645 |   { name: 'detail invalid metric', path: `/policies/deployments/${deploymentId}`, page: `#/policies/${deploymentId}`,
  646 |     body: { ...policyDetail(), latest_health_window: { ...healthWindow, candidate_stats: { ...stats, unknown_rate: '2' } } } },
  647 | ]) {
  648 |   test(`policy strict typed response rejects ${scenario.name}`, async ({ page }) => {
  649 |     await mockOps(page)
  650 |     await page.route(`**/ops-api/ops${scenario.path}*`, (route) => route.fulfill({ json: scenario.body }))
  651 |     await page.goto(`/ops/${scenario.page}`)
  652 |     await expect(page.getByText(/响应格式错误/)).toBeVisible()
  653 |     await expect(page.getByText('innocent-private-value', { exact: true })).toHaveCount(0)
  654 |     await expectStableLayout(page)
  655 |   })
  656 | }
  657 | 
  658 | test('policy strict health and audit guards reject freeform aggregates and reasons', async ({ page }) => {
  659 |   await mockOps(page)
  660 |   await page.route('**/ops-api/ops/policies/health-windows*', (route) => route.fulfill({
  661 |     json: { items: [{ ...healthWindow, candidate_stats: { ...stats, mean_cost: 'innocent-private-value' } }], next_cursor: null },
  662 |   }))
  663 |   await page.route('**/ops-api/ops/policies/audit*', (route) => route.fulfill({
  664 |     json: { items: [{ ...auditEvent, reason: 'innocent-private-value' }], next_cursor: null },
  665 |   }))
  666 |   await page.goto('/ops/#/policies')
  667 |   await page.getByRole('tab', { name: '健康窗口' }).click()
  668 |   await expect(page.getByText(/响应格式错误/)).toBeVisible()
  669 |   await page.getByRole('tab', { name: '审计时间线' }).click()
  670 |   await expect(page.getByText(/响应格式错误/)).toBeVisible()
  671 |   await expect(page.getByText('innocent-private-value', { exact: true })).toHaveCount(0)
  672 | })
  673 | 
  674 | test('policy detail empty evidence is explicitly unavailable', async ({ page }) => {
  675 |   await mockOps(page)
  676 |   await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, (route) => route.fulfill({
  677 |     json: { ...policyDetail(), required_receipts: [], gate_receipts: [], latest_health_window: null, audit_events: [] },
  678 |   }))
  679 |   await page.goto(`/ops/#/policies/${deploymentId}`)
  680 |   await expect(page.getByText('暂无 Gate 收据')).toBeVisible()
  681 |   await expect(page.getByText('暂无健康窗口，指标不可用')).toBeVisible()
  682 |   await expect(page.getByText('暂无审计事件')).toBeVisible()
  683 | })
  684 | 
  685 | test('policy detail selection ignores delayed previous version responses', async ({ page }) => {
  686 |   await mockOps(page)
  687 |   let started!: () => void
  688 |   let release!: () => void
  689 |   let fulfilled!: () => void
  690 |   const pending = new Promise<void>((resolve) => { release = resolve })
  691 |   const initial = new Promise<void>((resolve) => { started = resolve })
  692 |   const completed = new Promise<void>((resolve) => { fulfilled = resolve })
  693 |   await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, async (route) => {
  694 |     started()
  695 |     await pending
  696 |     await route.fulfill({ json: policyDetail() })
  697 |     fulfilled()
  698 |   })
  699 |   await page.goto(`/ops/#/policies/${deploymentId}`)
  700 |   await initial
  701 |   await page.getByRole('button', { name: /下一页/ }).click()
  702 |   await page.getByRole('region', { name: '策略证据列表' }).getByRole('link', { name: `查看策略 ${secondDeploymentId}` }).click()
  703 |   const detail = page.getByRole('region', { name: '策略版本详情' })
  704 |   await expect(detail.getByText('rehearsal · 版本 3', { exact: false })).toBeVisible()
  705 |   release()
  706 |   await completed
  707 |   await expect(detail.getByText('rehearsal · 版本 3', { exact: false })).toBeVisible()
  708 |   await expect(detail.getByText('rehearsal · 版本 2', { exact: false })).toHaveCount(0)
  709 | })
  710 | 
  711 | for (const scenario of ['consumed', 'old-local', 'missing'] as const) {
  712 |   test(`health source ${scenario} is explicit and does not claim a new passing window`, async ({ page }) => {
  713 |     await mockOps(page)
  714 |     const body = policyDetail(secondDeploymentId)
  715 |     body.state = 'active'
  716 |     body.latest_health_window = { ...body.latest_health_window, decision: 'hold', triggered_thresholds: [] }
  717 |     if (scenario === 'missing') {
  718 |       body.gate_receipts = []
  719 |     } else {
  720 |       body.gate_receipts[0].status = 'passed'
  721 |       body.gate_receipts[0].health_source.window_decision = 'pass'
  722 |       body.gate_receipts[0].health_source.is_latest_window = false
  723 |       if (scenario === 'consumed') {
  724 |         body.gate_receipts[0].health_source.relation = 'consumed_chain'
  725 |         body.gate_receipts[0].health_source.deployment_id = deploymentId
  726 |         body.gate_receipts[0].health_source.deployment_version = 2
  727 |       }
  728 |     }
  729 |     await page.route(`**/ops-api/ops/policies/deployments/${secondDeploymentId}`, (route) => route.fulfill({ json: body }))
  730 |     await page.goto(`/ops/#/policies/${secondDeploymentId}`)
  731 |     const detail = page.getByRole('region', { name: '策略版本详情' })
  732 |     await expect(detail.getByText('hold', { exact: true })).toBeVisible()
  733 |     const explanation = scenario === 'consumed' ? '已消费前序证据（非本部署新观测）'
  734 |       : scenario === 'old-local' ? '本部署旧窗口证据，不代表最新健康通过' : '暂无 Gate 收据'
> 735 |     await expect(detail.getByText(explanation, { exact: true })).toBeVisible()
      |                                                                  ^ Error: expect(locator).toBeVisible() failed
  736 |     await expectStableLayout(page)
  737 |   })
  738 | }
  739 | 
  740 | for (const mutation of ['extra', 'wrong-local', 'null-health', 'nonpassing-consumed'] as const) {
  741 |   test(`closed health source rejects ${mutation}`, async ({ page }) => {
  742 |     await mockOps(page)
  743 |     const body = policyDetail()
  744 |     const receipt = body.gate_receipts[0]
  745 |     if (mutation === 'extra') Object.assign(receipt.health_source, { details: 'private-source-value' })
  746 |     if (mutation === 'wrong-local') receipt.health_source.deployment_id = secondDeploymentId
  747 |     if (mutation === 'null-health') Object.assign(receipt, { health_source: null })
  748 |     if (mutation === 'nonpassing-consumed') receipt.health_source.relation = 'consumed_chain'
  749 |     await page.route(`**/ops-api/ops/policies/deployments/${deploymentId}`, (route) => route.fulfill({ json: body }))
  750 |     await page.goto(`/ops/#/policies/${deploymentId}`)
  751 |     await expect(page.getByText(/响应格式错误/)).toBeVisible()
  752 |     await expect(page.getByText('private-source-value', { exact: true })).toHaveCount(0)
  753 |   })
  754 | }
  755 | 
```