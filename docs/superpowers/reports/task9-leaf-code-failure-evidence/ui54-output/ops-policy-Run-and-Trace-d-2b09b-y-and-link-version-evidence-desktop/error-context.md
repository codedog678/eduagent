# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ops.spec.ts >> policy Run and Trace display stored immutable identity and link version evidence
- Location: e2e/ops.spec.ts:604:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('dialog', { name: '运行详情' }).getByText('candidate', { exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('dialog', { name: '运行详情' }).getByText('candidate', { exact: true }) with timeout 5000ms
  - waiting for getByRole('dialog', { name: '运行详情' }).getByText('candidate', { exact: true })
    - waiting for navigation to finish...
    - navigated to "http://127.0.0.1:56738/ops/#/runs"

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
  - heading "Runs" [level=1]
  - text: Read only
  - region "运行列表":
    - text: 全部状态
    - combobox
    - img "down"
    - text: 全部操作
    - combobox
    - img "down"
    - button "重置":
      - img
      - text: 重置
    - button "刷新":
      - img
      - text: 刷新
    - table:
      - rowgroup:
        - row "Run ID 状态 操作 策略绑定 租约 尝试 / 专家 用量 延迟 更新时间":
          - columnheader "Run ID"
          - columnheader "状态"
          - columnheader "操作"
          - columnheader "策略绑定"
          - columnheader "租约"
          - columnheader "尝试 / 专家"
          - columnheader "用量"
          - columnheader "延迟"
          - columnheader "更新时间"
          - columnheader
      - rowgroup:
        - row "run-1 completed learning_task 11111111-1111-1111-1111-111111111111 candidate · rehearsal bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb not fresh run-worker-a · fence 3 2 / 1 1 模型 / 2 工具 / 168 tokens 1.28 s 2026/10/30 10:00:01 查看运行 run-1 详情":
          - cell "run-1":
            - code: run-1
          - cell "completed"
          - cell "learning_task"
          - cell "11111111-1111-1111-1111-111111111111 candidate · rehearsal bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb":
            - link "11111111-1111-1111-1111-111111111111":
              - /url: "#/policies/11111111-1111-1111-1111-111111111111"
              - code: 11111111-1111-1111-1111-111111111111
            - text: candidate · rehearsal
            - code: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
          - cell "not fresh run-worker-a · fence 3"
          - cell "2 / 1"
          - cell "1 模型 / 2 工具 / 168 tokens"
          - cell "1.28 s"
          - cell "2026/10/30 10:00:01"
          - cell "查看运行 run-1 详情":
            - button "查看运行 run-1 详情":
              - img
              - text: 详情
    - button "上一页" [disabled]:
      - img
      - text: 上一页
    - text: 第 1 页
    - button "下一页":
      - text: 下一页
      - img
```

# Test source

```ts
  510 |   await page.goto('/ops/#/policies')
  511 |   await expect(page.getByRole('heading', { name: 'Policies', exact: true })).toBeVisible()
  512 |   await expect(page.getByText(deploymentId, { exact: true })).toBeVisible()
  513 |   if (testInfo.project.name === 'mobile') {
  514 |     const overflowTable = page.locator('.ant-table-content').first()
  515 |     expect(await overflowTable.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
  516 |     await overflowTable.hover()
  517 |     await page.mouse.wheel(900, 0)
  518 |     await expect.poll(() => overflowTable.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  519 |     await page.mouse.wheel(-900, 0)
  520 |   }
  521 |   await page.getByRole('button', { name: /下一页/ }).click()
  522 |   await expect(page.getByText(secondDeploymentId, { exact: true })).toBeVisible()
  523 |   await page.getByRole('button', { name: /上一页/ }).click()
  524 |   await page.getByLabel('策略状态').click()
  525 |   await page.getByTitle('frozen', { exact: true }).click()
  526 |   await expect(page.getByText(secondDeploymentId, { exact: true })).toBeVisible()
  527 |   await expect(page.getByRole('button', { name: /下一页/ })).toBeDisabled()
  528 |   await page.getByRole('button', { name: '重置' }).click()
  529 |   await page.getByLabel('策略环境').click()
  530 |   await page.getByTitle('rehearsal', { exact: true }).click()
  531 |   await page.getByRole('link', { name: `查看策略 ${deploymentId}` }).click()
  532 |   const detail = page.getByRole('region', { name: '策略版本详情' })
  533 |   await expect(detail.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
  534 |   await expect(detail.getByText('canary_health', { exact: true }).first()).toBeVisible()
  535 |   await expect(detail.getByText('commit_failure_rate', { exact: true }).first()).toBeVisible()
  536 |   await expect(detail.getByText('health_rollback', { exact: true })).toBeVisible()
  537 |   await expect(detail.getByText('promotion_transitioned', { exact: true })).toBeVisible()
  538 |   await expect(detail.getByText('canary → frozen', { exact: true })).toBeVisible()
  539 |   await expect(detail.getByText('未知', { exact: true }).first()).toBeVisible()
  540 |   await page.getByRole('tab', { name: '健康窗口' }).click()
  541 |   await expect(page.getByRole('region', { name: '策略证据列表' }).getByText('fail', { exact: true })).toBeVisible()
  542 |   await page.getByRole('tab', { name: '审计时间线' }).click()
  543 |   await expect(page.getByRole('region', { name: '策略证据列表' }).getByText('health_rollback', { exact: true })).toBeVisible()
  544 |   await expect(page.getByRole('button', { name: /晋升|回滚|冻结|发布|删除/ })).toHaveCount(0)
  545 |   expect(requests.every((request) => request.method === 'GET')).toBe(true)
  546 |   expect(requests.some((request) => request.url.includes('state=frozen'))).toBe(true)
  547 |   expect(requests.some((request) => request.url.includes('environment=rehearsal'))).toBe(true)
  548 |   await expectStableLayout(page)
  549 |   await page.getByRole('tab', { name: '部署' }).click()
  550 |   await expect(page.getByRole('region', { name: '策略证据列表' }).getByRole('link', { name: `查看策略 ${deploymentId}` })).toBeVisible()
  551 |   if (process.env.OPS_SCREENSHOT_DIR) {
  552 |     await page.screenshot({ path: `${process.env.OPS_SCREENSHOT_DIR}/policies-${testInfo.project.name}.png`, fullPage: true, animations: 'disabled' })
  553 |   }
  554 |   expect(errors).toEqual([])
  555 | })
  556 | 
  557 | test('policy loading, empty filters and stale requests do not restore old evidence', async ({ page }) => {
  558 |   let slowDone!: () => void
  559 |   const finished = new Promise<void>((resolve) => { slowDone = resolve })
  560 |   await mockOps(page, { delayPoliciesMs: 700, onSlowPolicyDone: slowDone })
  561 |   await page.goto('/ops/#/policies', { waitUntil: 'commit' })
  562 |   await expect(page.locator('.ant-skeleton')).toBeVisible()
  563 |   await page.getByLabel('策略环境').click()
  564 |   await page.getByTitle('production', { exact: true }).click()
  565 |   await expect(page.getByText('没有符合条件的策略证据')).toBeVisible()
  566 |   await finished
  567 |   await expect(page.getByText(deploymentId, { exact: true })).toHaveCount(0)
  568 |   await expectStableLayout(page)
  569 | })
  570 | 
  571 | test('policy errors and detail errors have independent retry recovery', async ({ page }) => {
  572 |   await mockOps(page, { policyFailureCount: 2, policyDetailFailureCount: 2 })
  573 |   await page.goto('/ops/#/policies')
  574 |   await expect(page.getByText('策略证据加载失败')).toBeVisible()
  575 |   await page.getByRole('button', { name: /重\s*试/ }).click()
  576 |   await expect(page.getByText(deploymentId, { exact: true })).toBeVisible()
  577 |   await page.getByRole('link', { name: `查看策略 ${deploymentId}` }).click()
  578 |   await expect(page.getByText('策略详情加载失败')).toBeVisible()
  579 |   await page.getByRole('region', { name: '策略版本详情' }).getByRole('button', { name: /重\s*试/ }).click()
  580 |   await expect(page.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
  581 | })
  582 | 
  583 | test('policy strict response guard rejects extra freeform fields', async ({ page }) => {
  584 |   await mockOps(page, { malformedPolicy: true })
  585 |   await page.goto('/ops/#/policies')
  586 |   await expect(page.getByText('策略证据加载失败')).toBeVisible()
  587 |   await expect(page.getByText(/响应格式错误/)).toBeVisible()
  588 |   await expect(page.getByText('must-not-render')).toHaveCount(0)
  589 | })
  590 | 
  591 | test('policy authentication uses existing Ops token and clears it on lock', async ({ page }) => {
  592 |   await mockOps(page, { requireToken: true })
  593 |   await page.goto(`/ops/#/policies/${deploymentId}`)
  594 |   await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
  595 |   await page.getByLabel('OPS API Token').fill('browser-test-token')
  596 |   await page.getByRole('button', { name: '验证并重试' }).click()
  597 |   await expect(page.getByRole('region', { name: '策略版本详情' })).toBeVisible()
  598 |   await expect(page.getByText('b'.repeat(64), { exact: true }).first()).toBeVisible()
  599 |   await page.getByRole('button', { name: '锁定控制台并清除会话 token' }).click()
  600 |   expect(await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token'))).toBeNull()
  601 |   await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
  602 | })
  603 | 
  604 | test('policy Run and Trace display stored immutable identity and link version evidence', async ({ page }, testInfo) => {
  605 |   await mockOps(page)
  606 |   await page.goto('/ops/#/runs')
  607 |   await page.getByRole('button', { name: '查看运行 run-1 详情' }).click()
  608 |   const drawer = page.getByRole('dialog', { name: '运行详情' })
  609 |   await expect(drawer.getByText('b'.repeat(64), { exact: true })).toBeVisible()
> 610 |   await expect(drawer.getByText('candidate', { exact: true })).toBeVisible()
      |                                                                ^ Error: expect(locator).toBeVisible() failed
  611 |   await drawer.getByRole('link', { name: 'a'.repeat(32) }).click()
  612 |   await expect(page.getByRole('heading', { name: '运行 Trace' })).toBeVisible()
  613 |   await expect(page.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  614 |   await expect(page.getByRole('region', { name: '运行策略绑定' }).getByText('candidate · rehearsal', { exact: true })).toBeVisible()
  615 |   if (process.env.OPS_SCREENSHOT_DIR) {
  616 |     await page.screenshot({ path: `${process.env.OPS_SCREENSHOT_DIR}/policy-trace-${testInfo.project.name}.png`, fullPage: true })
  617 |   }
  618 |   await page.getByRole('link', { name: deploymentId, exact: true }).click()
  619 |   await expect(page.getByRole('region', { name: '策略版本详情' }).getByText('rehearsal · 版本 2', { exact: false })).toBeVisible()
  620 |   await expect(page.getByText('当前版本 3', { exact: false }).first()).toBeVisible()
  621 |   await page.goto('/ops/#/trace/run-1')
  622 |   await expect(page.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  623 |   await expectStableLayout(page)
  624 | })
  625 | 
  626 | test('policy legacy Run and Trace identity remains unavailable without current policy fallback', async ({ page }) => {
  627 |   await mockOps(page, { legacyBinding: true })
  628 |   await page.goto('/ops/#/trace/run-1')
  629 |   await expect(page.getByText('策略绑定不可用')).toBeVisible()
  630 |   await expect(page.getByText('b'.repeat(64), { exact: true })).toHaveCount(0)
  631 |   await expect(page.getByRole('link', { name: deploymentId, exact: true })).toHaveCount(0)
  632 | })
  633 | 
  634 | for (const scenario of [
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
```