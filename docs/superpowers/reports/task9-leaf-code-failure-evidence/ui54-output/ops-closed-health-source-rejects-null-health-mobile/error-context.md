# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ops.spec.ts >> closed health source rejects null-health
- Location: e2e/ops.spec.ts:741:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/响应格式错误/)
Expected: visible
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText(/响应格式错误/) with timeout 5000ms
  - waiting for getByText(/响应格式错误/)
  - Test timeout of 30000ms exceeded.

```

```yaml
- banner:
  - link "EduAgent Ops 首页":
    - /url: "#/runs"
    - strong: EduAgent Ops
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
      - heading [level=3]
      - list:
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
    - button "上一页" [disabled]:
      - img
      - text: 上一页
    - text: 第 1 页
    - button "下一页" [disabled]:
      - text: 下一页
      - img
    - region "策略版本详情":
      - heading "策略版本详情" [level=3]
      - link "关闭详情":
        - /url: "#/policies"
      - heading [level=3]
      - list:
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
        - listitem
```

# Test source

```ts
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
  734 |       : scenario === 'old-local' ? '本部署旧窗口证据，不代表最新健康通过' : 'unknown'
  735 |     await expect(detail.getByText(explanation, { exact: true })).toBeVisible()
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
> 751 |     await expect(page.getByText(/响应格式错误/)).toBeVisible()
      |                                            ^ Error: expect(locator).toBeVisible() failed
  752 |     await expect(page.getByText('private-source-value', { exact: true })).toHaveCount(0)
  753 |   })
  754 | }
  755 | 
```