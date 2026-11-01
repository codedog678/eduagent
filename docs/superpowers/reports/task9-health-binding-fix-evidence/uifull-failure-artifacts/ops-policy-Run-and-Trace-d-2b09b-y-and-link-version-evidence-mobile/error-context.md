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

Locator: getByRole('region', { name: '策略版本详情' }).getByText('版本 2')
Expected: visible
Error: strict mode violation: getByRole('region', { name: '策略版本详情' }).getByText('版本 2') resolved to 2 elements:
    1) <span>…</span> aka getByText('rehearsal · 版本 2 canary')
    2) <span>…</span> aka getByText('版本 2 · fail · 来源最新窗口')

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '策略版本详情' }).getByText('版本 2') with timeout 5000ms
  - waiting for getByRole('region', { name: '策略版本详情' }).getByText('版本 2')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - link "EduAgent Ops 首页" [ref=e5] [cursor=pointer]:
      - /url: "#/runs"
      - strong [ref=e10]: EduAgent Ops
    - navigation "Ops 导航" [ref=e11]:
      - link "Runs" [ref=e12] [cursor=pointer]:
        - /url: "#/runs"
      - link "Trace" [ref=e15] [cursor=pointer]:
        - /url: "#/runs"
      - link "Workers" [ref=e20] [cursor=pointer]:
        - /url: "#/workers"
      - link "Policies" [ref=e24] [cursor=pointer]:
        - /url: "#/policies"
    - button "锁定控制台并清除会话 token" [ref=e28] [cursor=pointer]:
      - generic [ref=e34]: 锁定
  - main [ref=e35]:
    - generic [ref=e36]:
      - generic [ref=e37]:
        - text: OPERATIONS
        - heading "Policies" [level=1] [ref=e38]
      - generic [ref=e39]: Read only
    - region "Policies 只读证据" [ref=e44]:
      - generic [ref=e45]:
        - generic [ref=e46]:
          - generic [ref=e48] [cursor=pointer]:
            - generic [ref=e49]:
              - generic: 全部环境
              - combobox "策略环境" [ref=e50]
            - img "down" [ref=e52]
          - generic [ref=e56] [cursor=pointer]:
            - generic [ref=e57]:
              - generic: 全部状态
              - combobox "策略状态" [ref=e58]
            - img "down" [ref=e60]
          - button "重置" [ref=e64] [cursor=pointer]
        - button "刷新" [ref=e70] [cursor=pointer]
      - generic [ref=e78]:
        - tablist [ref=e79]:
          - generic [ref=e81]:
            - tab "部署" [selected] [ref=e83] [cursor=pointer]
            - tab "健康窗口" [ref=e85] [cursor=pointer]
            - tab "审计时间线" [ref=e87] [cursor=pointer]
        - generic:
          - generic:
            - tabpanel "部署"
      - region "策略证据列表" [ref=e88]:
        - table [ref=e95]:
          - rowgroup [ref=e105]:
            - row [ref=e106]:
              - columnheader "Deployment" [ref=e107]
              - columnheader "环境 / 版本" [ref=e108]
              - columnheader "状态" [ref=e109]
              - columnheader "当前部署" [ref=e110]
              - columnheader "Stable / Candidate" [ref=e111]
              - columnheader "Candidate 流量" [ref=e112]
              - columnheader "Cohort 运行数" [ref=e113]
              - columnheader "创建时间" [ref=e114]
          - rowgroup [ref=e115]:
            - row [ref=e116]:
              - cell [ref=e117]:
                - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                  - code [ref=e119]: 11111111-1111-1111-1111-111111111111
              - cell "rehearsal 版本 2" [ref=e120]:
                - generic [ref=e121]:
                  - generic [ref=e122]: rehearsal
                  - strong [ref=e123]: 版本 2
              - cell "canary" [ref=e124]
              - cell "historical 当前版本 3" [ref=e129]:
                - generic [ref=e130]:
                  - generic [ref=e131]: historical
                  - generic [ref=e132]: 当前版本 3
              - cell [ref=e133]:
                - generic [ref=e134]:
                  - code [ref=e135]: S aaaaaaaaaaaa
                  - code [ref=e136]: C bbbbbbbbbbbb
              - cell "50%" [ref=e137]
              - cell "S 20 · C 20 · Shadow 10" [ref=e138]
              - cell "2026/10/30 10:00:00" [ref=e139]
      - generic "Policies 游标分页" [ref=e140]:
        - button "上一页" [disabled] [ref=e141]
        - generic [ref=e142]: 第 1 页
        - button "下一页" [ref=e143] [cursor=pointer]
      - region "策略版本详情" [ref=e147]:
        - generic [ref=e148]:
          - heading "策略版本详情" [level=3] [ref=e149]
          - link "关闭详情" [ref=e150] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e153]:
          - rowgroup [ref=e154]:
            - row [ref=e155]:
              - rowheader "Deployment" [ref=e156]
              - cell [ref=e157]:
                - code [ref=e159]: 11111111-1111-1111-1111-111111111111
            - row [ref=e160]:
              - rowheader "环境 / 版本" [ref=e161]
              - cell [ref=e162]:
                - generic [ref=e163]:
                  - text: rehearsal · 版本 2
                  - generic [ref=e164]: canary
            - row [ref=e168]:
              - rowheader "当前部署" [ref=e169]
              - cell [ref=e170]:
                - generic [ref=e171]:
                  - link "查看策略 22222222-2222-2222-2222-222222222222" [ref=e172] [cursor=pointer]:
                    - /url: "#/policies/22222222-2222-2222-2222-222222222222"
                    - code [ref=e173]: 22222222-2222-2222-2222-222222222222
                  - text: · 当前版本 3
            - row [ref=e174]:
              - rowheader "Stable hash" [ref=e175]
              - cell [ref=e176]:
                - code [ref=e178]: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
            - row [ref=e179]:
              - rowheader "Candidate hash" [ref=e180]
              - cell [ref=e181]:
                - code [ref=e183]: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
            - row [ref=e184]:
              - rowheader "流量 / Cohort" [ref=e185]
              - cell "50% candidate · Stable 20 / Candidate 20 / Shadow 10" [ref=e186]
            - row [ref=e188]:
              - rowheader "Actor / Reason" [ref=e189]
              - cell "redacted / redacted" [ref=e190]
            - row [ref=e192]:
              - rowheader "创建" [ref=e193]
              - cell "2026/10/30 10:00:00" [ref=e194]
        - paragraph [ref=e195]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e196]
        - generic [ref=e197]:
          - generic [ref=e198]:
            - term [ref=e199]: candidate_min_runs
            - definition [ref=e200]: "20"
          - generic [ref=e201]:
            - term [ref=e202]: stable_min_runs
            - definition [ref=e203]: "20"
          - generic [ref=e204]:
            - term [ref=e205]: window_max_runs
            - definition [ref=e206]: "50"
          - generic [ref=e207]:
            - term [ref=e208]: commit_failure_rate
            - definition [ref=e209]: "0.05"
          - generic [ref=e210]:
            - term [ref=e211]: terminal_failure_rate
            - definition [ref=e212]: "0.10"
          - generic [ref=e213]:
            - term [ref=e214]: latency_increase_rate
            - definition [ref=e215]: "0.50"
          - generic [ref=e216]:
            - term [ref=e217]: mean_cost_increase_rate
            - definition [ref=e218]: "0.30"
          - generic [ref=e219]:
            - term [ref=e220]: unknown_rate
            - definition [ref=e221]: "0.10"
          - generic [ref=e222]:
            - term [ref=e223]: relative_epsilon
            - definition [ref=e224]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e225]
        - paragraph [ref=e226]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e228]:
          - text: canary_health
          - generic [ref=e229]: failed
        - table [ref=e240]:
          - rowgroup [ref=e249]:
            - row [ref=e250]:
              - columnheader "Gate" [ref=e251]
              - columnheader "状态" [ref=e252]
              - columnheader "健康来源" [ref=e253]
              - columnheader "样本" [ref=e254]
              - columnheader "成本 USD" [ref=e255]
              - columnheader "Issuer" [ref=e256]
              - columnheader "签发时间" [ref=e257]
          - rowgroup [ref=e258]:
            - row [ref=e259]:
              - cell "canary_health" [ref=e260]
              - cell "failed" [ref=e261]
              - cell "本部署窗口 查看策略 11111111-1111-1111-1111-111111111111 版本 2 · fail · 来源最新窗口 Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc 2026/10/30 10:03:00" [ref=e267]:
                - generic [ref=e268]:
                  - strong [ref=e269]: 本部署窗口
                  - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e270] [cursor=pointer]:
                    - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                    - code [ref=e271]: 11111111-1111-1111-1111-111111111111
                  - generic [ref=e272]: 版本 2 · fail · 来源最新窗口
                  - code [ref=e273]: Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
                  - generic [ref=e274]: 2026/10/30 10:03:00
              - cell "20" [ref=e275]
              - cell "0.02" [ref=e276]
              - cell "redacted" [ref=e277]
              - cell "2026/10/30 10:02:00" [ref=e278]
        - heading "最新健康窗口" [level=3] [ref=e279]
        - paragraph [ref=e280]:
          - generic [ref=e281]: fail
          - text: 2026/10/30 10:03:00 · 指标协议 v1
        - paragraph [ref=e286]: 触发阈值：commit_failure_rate。未知指标保持未知，不作为零值。
        - table [ref=e293]:
          - rowgroup [ref=e298]:
            - row [ref=e299]:
              - columnheader "指标" [ref=e300]
              - columnheader "Candidate" [ref=e301]
              - columnheader "Stable" [ref=e302]
          - rowgroup [ref=e303]:
            - row [ref=e304]:
              - cell "run_count" [ref=e305]
              - cell "20" [ref=e306]
              - cell "20" [ref=e307]
            - row [ref=e308]:
              - cell "commit_failure_rate" [ref=e309]
              - cell "0.05" [ref=e310]
              - cell "0.05" [ref=e311]
            - row [ref=e312]:
              - cell "terminal_failure_rate" [ref=e313]
              - cell "0.10" [ref=e314]
              - cell "0.10" [ref=e315]
            - row [ref=e316]:
              - cell "p95_latency" [ref=e317]
              - cell "1.25" [ref=e318]
              - cell "1.25" [ref=e319]
            - row [ref=e320]:
              - cell "mean_cost" [ref=e321]
              - cell "0.01" [ref=e322]
              - cell "未知" [ref=e323]
            - row [ref=e324]:
              - cell "structured_decision_count" [ref=e325]
              - cell "10" [ref=e326]
              - cell "10" [ref=e327]
            - row [ref=e328]:
              - cell "unknown_decision_count" [ref=e329]
              - cell "1" [ref=e330]
              - cell "1" [ref=e331]
            - row [ref=e332]:
              - cell "unknown_rate" [ref=e333]
              - cell "0.10" [ref=e334]
              - cell "0.10" [ref=e335]
            - row [ref=e336]:
              - cell "fault_injected_count" [ref=e337]
              - cell "1" [ref=e338]
              - cell "1" [ref=e339]
            - row [ref=e340]:
              - cell "injected_commit_failure_count" [ref=e341]
              - cell "1" [ref=e342]
              - cell "1" [ref=e343]
            - row [ref=e344]:
              - cell "natural_failure_count" [ref=e345]
              - cell "0" [ref=e346]
              - cell "0" [ref=e347]
            - row [ref=e348]:
              - cell "latency_increase_rate" [ref=e349]
              - cell "未知" [ref=e350]
              - cell "未知" [ref=e351]
            - row [ref=e352]:
              - cell "mean_cost_increase_rate" [ref=e353]
              - cell "未知" [ref=e354]
              - cell "未知" [ref=e355]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e356]
        - list [ref=e357]:
          - listitem [ref=e358]:
            - generic [ref=e367]:
              - strong [ref=e368]: health_rollback
              - generic [ref=e369]: 2026/10/30 10:03:01 · rehearsal
              - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e370] [cursor=pointer]:
                - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                - code [ref=e371]: 11111111-1111-1111-1111-111111111111
              - code [ref=e372]: Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
              - generic [ref=e373]: "actor: redacted · reason: redacted"
          - listitem [ref=e374]:
            - generic [ref=e382]:
              - strong [ref=e383]: promotion_transitioned
              - generic [ref=e384]: canary → frozen
              - generic [ref=e385]: 2026/10/30 10:03:01 · rehearsal
              - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e386] [cursor=pointer]:
                - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                - code [ref=e387]: 11111111-1111-1111-1111-111111111111
              - generic [ref=e388]: "actor: redacted · reason: redacted"
        - paragraph [ref=e389]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
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
  610 |   await expect(drawer.getByText('candidate', { exact: true })).toBeVisible()
  611 |   await drawer.getByRole('link', { name: 'a'.repeat(32) }).click()
  612 |   await expect(page.getByRole('heading', { name: '运行 Trace' })).toBeVisible()
  613 |   await expect(page.getByText('b'.repeat(64), { exact: true })).toBeVisible()
  614 |   await expect(page.getByRole('region', { name: '运行策略绑定' }).getByText('candidate · rehearsal', { exact: true })).toBeVisible()
  615 |   if (process.env.OPS_SCREENSHOT_DIR) {
  616 |     await page.screenshot({ path: `${process.env.OPS_SCREENSHOT_DIR}/policy-trace-${testInfo.project.name}.png`, fullPage: true })
  617 |   }
  618 |   await page.getByRole('link', { name: deploymentId, exact: true }).click()
> 619 |   await expect(page.getByRole('region', { name: '策略版本详情' }).getByText('版本 2', { exact: false })).toBeVisible()
      |                                                                                                  ^ Error: expect(locator).toBeVisible() failed
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
  711 | for (const scenario of ['consumed', 'old-local', 'missing'] as const) {
  712 |   test(`health source ${scenario} is explicit and does not claim a new passing window`, async ({ page }) => {
  713 |     await mockOps(page)
  714 |     const body = policyDetail(secondDeploymentId)
  715 |     body.state = 'active'
  716 |     body.latest_health_window = { ...body.latest_health_window, decision: 'hold', triggered_thresholds: [] }
  717 |     if (scenario === 'missing') {
  718 |       body.gate_receipts = []
  719 |     } else {
```