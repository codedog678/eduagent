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
      - generic [ref=e9]:
        - strong [ref=e10]: EduAgent Ops
        - generic [ref=e11]: 只读运行面板
    - navigation "Ops 导航" [ref=e12]:
      - link "Runs" [ref=e13] [cursor=pointer]:
        - /url: "#/runs"
      - link "Trace" [ref=e16] [cursor=pointer]:
        - /url: "#/runs"
      - link "Workers" [ref=e21] [cursor=pointer]:
        - /url: "#/workers"
      - link "Policies" [ref=e25] [cursor=pointer]:
        - /url: "#/policies"
    - button "锁定控制台并清除会话 token" [ref=e29] [cursor=pointer]:
      - generic [ref=e35]: 锁定
  - main [ref=e36]:
    - generic [ref=e37]:
      - generic [ref=e38]:
        - text: OPERATIONS
        - heading "Policies" [level=1] [ref=e39]
      - generic [ref=e40]: Read only
    - region "Policies 只读证据" [ref=e45]:
      - generic [ref=e46]:
        - generic [ref=e47]:
          - generic [ref=e49] [cursor=pointer]:
            - generic [ref=e50]:
              - generic: 全部环境
              - combobox "策略环境" [ref=e51]
            - img "down" [ref=e53]
          - generic [ref=e57] [cursor=pointer]:
            - generic [ref=e58]:
              - generic: 全部状态
              - combobox "策略状态" [ref=e59]
            - img "down" [ref=e61]
          - button "重置" [ref=e65] [cursor=pointer]
        - button "刷新" [ref=e71] [cursor=pointer]
      - generic [ref=e79]:
        - tablist [ref=e80]:
          - generic [ref=e82]:
            - tab "部署" [selected] [ref=e84] [cursor=pointer]
            - tab "健康窗口" [ref=e86] [cursor=pointer]
            - tab "审计时间线" [ref=e88] [cursor=pointer]
        - generic:
          - generic:
            - tabpanel "部署"
      - region "策略证据列表" [ref=e89]:
        - table [ref=e96]:
          - rowgroup [ref=e106]:
            - row [ref=e107]:
              - columnheader "Deployment" [ref=e108]
              - columnheader "环境 / 版本" [ref=e109]
              - columnheader "状态" [ref=e110]
              - columnheader "当前部署" [ref=e111]
              - columnheader "Stable / Candidate" [ref=e112]
              - columnheader "Candidate 流量" [ref=e113]
              - columnheader "Cohort 运行数" [ref=e114]
              - columnheader "创建时间" [ref=e115]
          - rowgroup [ref=e116]:
            - row [ref=e117]:
              - cell [ref=e118]:
                - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                  - code [ref=e120]: 11111111-1111-1111-1111-111111111111
              - cell "rehearsal 版本 2" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 2
              - cell "canary" [ref=e125]
              - cell "historical 当前版本 3" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: historical
                  - generic [ref=e133]: 当前版本 3
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S aaaaaaaaaaaa
                  - code [ref=e137]: C bbbbbbbbbbbb
              - cell "50%" [ref=e138]
              - cell "S 20 · C 20 · Shadow 10" [ref=e139]
              - cell "2026/10/30 10:00:00" [ref=e140]
      - generic "Policies 游标分页" [ref=e141]:
        - button "上一页" [disabled] [ref=e142]
        - generic [ref=e143]: 第 1 页
        - button "下一页" [ref=e144] [cursor=pointer]
      - region "策略版本详情" [ref=e148]:
        - generic [ref=e149]:
          - heading "策略版本详情" [level=3] [ref=e150]
          - link "关闭详情" [ref=e151] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e154]:
          - rowgroup [ref=e155]:
            - row [ref=e156]:
              - rowheader "Deployment" [ref=e157]
              - cell [ref=e158]:
                - code [ref=e160]: 11111111-1111-1111-1111-111111111111
            - row [ref=e161]:
              - rowheader "环境 / 版本" [ref=e162]
              - cell [ref=e163]:
                - generic [ref=e164]:
                  - text: rehearsal · 版本 2
                  - generic [ref=e165]: canary
            - row [ref=e169]:
              - rowheader "当前部署" [ref=e170]
              - cell [ref=e171]:
                - generic [ref=e172]:
                  - link "查看策略 22222222-2222-2222-2222-222222222222" [ref=e173] [cursor=pointer]:
                    - /url: "#/policies/22222222-2222-2222-2222-222222222222"
                    - code [ref=e174]: 22222222-2222-2222-2222-222222222222
                  - text: · 当前版本 3
            - row [ref=e175]:
              - rowheader "Stable hash" [ref=e176]
              - cell [ref=e177]:
                - code [ref=e179]: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
            - row [ref=e180]:
              - rowheader "Candidate hash" [ref=e181]
              - cell [ref=e182]:
                - code [ref=e184]: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
            - row [ref=e185]:
              - rowheader "流量 / Cohort" [ref=e186]
              - cell "50% candidate · Stable 20 / Candidate 20 / Shadow 10" [ref=e187]
            - row [ref=e189]:
              - rowheader "Actor / Reason" [ref=e190]
              - cell "redacted / redacted" [ref=e191]
            - row [ref=e193]:
              - rowheader "创建" [ref=e194]
              - cell "2026/10/30 10:00:00" [ref=e195]
        - paragraph [ref=e196]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e197]
        - generic [ref=e198]:
          - generic [ref=e199]:
            - term [ref=e200]: candidate_min_runs
            - definition [ref=e201]: "20"
          - generic [ref=e202]:
            - term [ref=e203]: stable_min_runs
            - definition [ref=e204]: "20"
          - generic [ref=e205]:
            - term [ref=e206]: window_max_runs
            - definition [ref=e207]: "50"
          - generic [ref=e208]:
            - term [ref=e209]: commit_failure_rate
            - definition [ref=e210]: "0.05"
          - generic [ref=e211]:
            - term [ref=e212]: terminal_failure_rate
            - definition [ref=e213]: "0.10"
          - generic [ref=e214]:
            - term [ref=e215]: latency_increase_rate
            - definition [ref=e216]: "0.50"
          - generic [ref=e217]:
            - term [ref=e218]: mean_cost_increase_rate
            - definition [ref=e219]: "0.30"
          - generic [ref=e220]:
            - term [ref=e221]: unknown_rate
            - definition [ref=e222]: "0.10"
          - generic [ref=e223]:
            - term [ref=e224]: relative_epsilon
            - definition [ref=e225]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e226]
        - paragraph [ref=e227]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e229]:
          - text: canary_health
          - generic [ref=e230]: failed
        - table [ref=e241]:
          - rowgroup [ref=e250]:
            - row [ref=e251]:
              - columnheader "Gate" [ref=e252]
              - columnheader "状态" [ref=e253]
              - columnheader "健康来源" [ref=e254]
              - columnheader "样本" [ref=e255]
              - columnheader "成本 USD" [ref=e256]
              - columnheader "Issuer" [ref=e257]
              - columnheader "签发时间" [ref=e258]
          - rowgroup [ref=e259]:
            - row [ref=e260]:
              - cell "canary_health" [ref=e261]
              - cell "failed" [ref=e262]
              - cell "本部署窗口 查看策略 11111111-1111-1111-1111-111111111111 版本 2 · fail · 来源最新窗口 Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc 2026/10/30 10:03:00" [ref=e268]:
                - generic [ref=e269]:
                  - strong [ref=e270]: 本部署窗口
                  - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e271] [cursor=pointer]:
                    - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                    - code [ref=e272]: 11111111-1111-1111-1111-111111111111
                  - generic [ref=e273]: 版本 2 · fail · 来源最新窗口
                  - code [ref=e274]: Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
                  - generic [ref=e275]: 2026/10/30 10:03:00
              - cell "20" [ref=e276]
              - cell "0.02" [ref=e277]
              - cell "redacted" [ref=e278]
              - cell "2026/10/30 10:02:00" [ref=e279]
        - heading "最新健康窗口" [level=3] [ref=e280]
        - paragraph [ref=e281]:
          - generic [ref=e282]: fail
          - text: 2026/10/30 10:03:00 · 指标协议 v1
        - paragraph [ref=e287]: 触发阈值：commit_failure_rate。未知指标保持未知，不作为零值。
        - table [ref=e294]:
          - rowgroup [ref=e299]:
            - row [ref=e300]:
              - columnheader "指标" [ref=e301]
              - columnheader "Candidate" [ref=e302]
              - columnheader "Stable" [ref=e303]
          - rowgroup [ref=e304]:
            - row [ref=e305]:
              - cell "run_count" [ref=e306]
              - cell "20" [ref=e307]
              - cell "20" [ref=e308]
            - row [ref=e309]:
              - cell "commit_failure_rate" [ref=e310]
              - cell "0.05" [ref=e311]
              - cell "0.05" [ref=e312]
            - row [ref=e313]:
              - cell "terminal_failure_rate" [ref=e314]
              - cell "0.10" [ref=e315]
              - cell "0.10" [ref=e316]
            - row [ref=e317]:
              - cell "p95_latency" [ref=e318]
              - cell "1.25" [ref=e319]
              - cell "1.25" [ref=e320]
            - row [ref=e321]:
              - cell "mean_cost" [ref=e322]
              - cell "0.01" [ref=e323]
              - cell "未知" [ref=e324]
            - row [ref=e325]:
              - cell "structured_decision_count" [ref=e326]
              - cell "10" [ref=e327]
              - cell "10" [ref=e328]
            - row [ref=e329]:
              - cell "unknown_decision_count" [ref=e330]
              - cell "1" [ref=e331]
              - cell "1" [ref=e332]
            - row [ref=e333]:
              - cell "unknown_rate" [ref=e334]
              - cell "0.10" [ref=e335]
              - cell "0.10" [ref=e336]
            - row [ref=e337]:
              - cell "fault_injected_count" [ref=e338]
              - cell "1" [ref=e339]
              - cell "1" [ref=e340]
            - row [ref=e341]:
              - cell "injected_commit_failure_count" [ref=e342]
              - cell "1" [ref=e343]
              - cell "1" [ref=e344]
            - row [ref=e345]:
              - cell "natural_failure_count" [ref=e346]
              - cell "0" [ref=e347]
              - cell "0" [ref=e348]
            - row [ref=e349]:
              - cell "latency_increase_rate" [ref=e350]
              - cell "未知" [ref=e351]
              - cell "未知" [ref=e352]
            - row [ref=e353]:
              - cell "mean_cost_increase_rate" [ref=e354]
              - cell "未知" [ref=e355]
              - cell "未知" [ref=e356]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e357]
        - list [ref=e358]:
          - listitem [ref=e359]:
            - generic [ref=e368]:
              - strong [ref=e369]: health_rollback
              - generic [ref=e370]: 2026/10/30 10:03:01 · rehearsal
              - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e371] [cursor=pointer]:
                - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                - code [ref=e372]: 11111111-1111-1111-1111-111111111111
              - code [ref=e373]: Window cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
              - generic [ref=e374]: "actor: redacted · reason: redacted"
          - listitem [ref=e375]:
            - generic [ref=e383]:
              - strong [ref=e384]: promotion_transitioned
              - generic [ref=e385]: canary → frozen
              - generic [ref=e386]: 2026/10/30 10:03:01 · rehearsal
              - link "查看策略 11111111-1111-1111-1111-111111111111" [ref=e387] [cursor=pointer]:
                - /url: "#/policies/11111111-1111-1111-1111-111111111111"
                - code [ref=e388]: 11111111-1111-1111-1111-111111111111
              - generic [ref=e389]: "actor: redacted · reason: redacted"
        - paragraph [ref=e390]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
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