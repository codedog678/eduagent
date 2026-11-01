# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: health-binding.spec.ts >> real production HTTP assets and GET-only current health detail
- Location: live-e2e/health-binding.spec.ts:7:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^passed$/ })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^passed$/ }) with timeout 5000ms
  - waiting for locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^passed$/ })

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
          - row "查看策略 00000000-0000-0000-0000-000000000002 rehearsal 版本 1 registered historical 当前版本 3 S 778de32838c9 C 不可用 0% S 0 · C 0 · Shadow 0 2026/11/1 22:22:49":
            - cell "查看策略 00000000-0000-0000-0000-000000000002":
              - link "查看策略 00000000-0000-0000-0000-000000000002":
                - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                - code: 00000000-0000-0000-0000-000000000002
            - cell "rehearsal 版本 1":
              - text: rehearsal
              - strong: 版本 1
            - cell "registered"
            - cell "historical 当前版本 3"
            - cell "S 778de32838c9 C 不可用":
              - code: S 778de32838c9
              - code: C 不可用
            - cell "0%"
            - cell "S 0 · C 0 · Shadow 0"
            - cell "2026/11/1 22:22:49"
          - row "查看策略 00000000-0000-0000-0000-000000000001 production 版本 1 registered current 当前版本 1 S 778de32838c9 C 不可用 0% S 40 · C 0 · Shadow 0 2026/11/1 22:22:49":
            - cell "查看策略 00000000-0000-0000-0000-000000000001":
              - link "查看策略 00000000-0000-0000-0000-000000000001":
                - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                - code: 00000000-0000-0000-0000-000000000001
            - cell "production 版本 1":
              - text: production
              - strong: 版本 1
            - cell "registered"
            - cell "current 当前版本 1"
            - cell "S 778de32838c9 C 不可用":
              - code: S 778de32838c9
              - code: C 不可用
            - cell "0%"
            - cell "S 40 · C 0 · Shadow 0"
            - cell "2026/11/1 22:22:49"
          - row "查看策略 f9a512e1-95b3-4e2f-875b-1678de9389fb rehearsal 版本 2 canary historical 当前版本 3 S 778de32838c9 C c646dbb9a0d0 50% S 0 · C 0 · Shadow 0 2026/11/1 00:00:00":
            - cell "查看策略 f9a512e1-95b3-4e2f-875b-1678de9389fb":
              - link "查看策略 f9a512e1-95b3-4e2f-875b-1678de9389fb":
                - /url: "#/policies/f9a512e1-95b3-4e2f-875b-1678de9389fb"
                - code: f9a512e1-95b3-4e2f-875b-1678de9389fb
            - cell "rehearsal 版本 2":
              - text: rehearsal
              - strong: 版本 2
            - cell "canary"
            - cell "historical 当前版本 3"
            - cell "S 778de32838c9 C c646dbb9a0d0":
              - code: S 778de32838c9
              - code: C c646dbb9a0d0
            - cell "50%"
            - cell "S 0 · C 0 · Shadow 0"
            - cell "2026/11/1 00:00:00"
          - row "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0 rehearsal 版本 3 canary current 当前版本 3 S 778de32838c9 C c646dbb9a0d0 50% S 0 · C 0 · Shadow 0 2026/11/1 00:00:00":
            - cell "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0":
              - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0":
                - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                - code: ef94576b-f29f-4ecf-b530-2c37b63f66f0
            - cell "rehearsal 版本 3":
              - text: rehearsal
              - strong: 版本 3
            - cell "canary"
            - cell "current 当前版本 3"
            - cell "S 778de32838c9 C c646dbb9a0d0":
              - code: S 778de32838c9
              - code: C c646dbb9a0d0
            - cell "50%"
            - cell "S 0 · C 0 · Shadow 0"
            - cell "2026/11/1 00:00:00"
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
      - table:
        - rowgroup:
          - row "Deployment ef94576b-f29f-4ecf-b530-2c37b63f66f0":
            - rowheader "Deployment"
            - cell "ef94576b-f29f-4ecf-b530-2c37b63f66f0":
              - code: ef94576b-f29f-4ecf-b530-2c37b63f66f0
          - row "环境 / 版本 rehearsal · 版本 3 canary":
            - rowheader "环境 / 版本"
            - cell "rehearsal · 版本 3 canary"
          - row "当前部署 查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0 · 当前版本 3":
            - rowheader "当前部署"
            - cell "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0 · 当前版本 3":
              - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0":
                - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                - code: ef94576b-f29f-4ecf-b530-2c37b63f66f0
              - text: · 当前版本 3
          - row "Stable hash 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9":
            - rowheader "Stable hash"
            - cell "778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9":
              - code: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
          - row "Candidate hash c646dbb9a0d03014d9b26f2ea74bddef7b7e2a577541f559edc0efc2deb75c73":
            - rowheader "Candidate hash"
            - cell "c646dbb9a0d03014d9b26f2ea74bddef7b7e2a577541f559edc0efc2deb75c73":
              - code: c646dbb9a0d03014d9b26f2ea74bddef7b7e2a577541f559edc0efc2deb75c73
          - row "流量 / Cohort 50% candidate · Stable 0 / Candidate 0 / Shadow 0":
            - rowheader "流量 / Cohort"
            - cell "50% candidate · Stable 0 / Candidate 0 / Shadow 0"
          - row "Actor / Reason redacted / redacted":
            - rowheader "Actor / Reason"
            - cell "redacted / redacted"
          - row "创建 2026/11/1 00:00:00":
            - rowheader "创建"
            - cell "2026/11/1 00:00:00"
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
      - table:
        - rowgroup:
          - row "Gate 状态 样本 成本 USD Issuer 签发时间":
            - columnheader "Gate"
            - columnheader "状态"
            - columnheader "样本"
            - columnheader "成本 USD"
            - columnheader "Issuer"
            - columnheader "签发时间"
        - rowgroup:
          - row "canary_health passed 20 0.40000000 redacted 2026/11/1 22:22:50":
            - cell "canary_health"
            - cell "passed"
            - cell "20"
            - cell "0.40000000"
            - cell "redacted"
            - cell "2026/11/1 22:22:50"
      - heading "最新健康窗口" [level=3]
      - paragraph: hold 2026/11/1 22:22:50 · 指标协议 v1
      - paragraph: 触发阈值：baseline_shortage, cost_unavailable, structured_decisions_unavailable, matched_window_incomplete。未知指标保持未知，不作为零值。
      - table:
        - rowgroup:
          - row "指标 Candidate Stable":
            - columnheader "指标"
            - columnheader "Candidate"
            - columnheader "Stable"
        - rowgroup:
          - row "run_count 0 0":
            - cell "run_count"
            - cell "0"
            - cell "0"
          - row "commit_failure_rate 未知 未知":
            - cell "commit_failure_rate"
            - cell "未知"
            - cell "未知"
          - row "terminal_failure_rate 未知 未知":
            - cell "terminal_failure_rate"
            - cell "未知"
            - cell "未知"
          - row "p95_latency 未知 未知":
            - cell "p95_latency"
            - cell "未知"
            - cell "未知"
          - row "mean_cost 未知 未知":
            - cell "mean_cost"
            - cell "未知"
            - cell "未知"
          - row "structured_decision_count 0 0":
            - cell "structured_decision_count"
            - cell "0"
            - cell "0"
          - row "unknown_decision_count 0 0":
            - cell "unknown_decision_count"
            - cell "0"
            - cell "0"
          - row "unknown_rate 未知 未知":
            - cell "unknown_rate"
            - cell "未知"
            - cell "未知"
          - row "fault_injected_count 0 0":
            - cell "fault_injected_count"
            - cell "0"
            - cell "0"
          - row "injected_commit_failure_count 0 0":
            - cell "injected_commit_failure_count"
            - cell "0"
            - cell "0"
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
      - img "No data"
      - text: 暂无审计事件
      - paragraph: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test'
  2  | import { readFileSync, writeFileSync } from 'node:fs'
  3  | import { createHash } from 'node:crypto'
  4  | const own = '/tmp/m3-task9-code-20261102-5TNycP'
  5  | const sha = (data: Buffer) => createHash('sha256').update(data).digest('hex')
  6  | 
  7  | test('real production HTTP assets and GET-only current health detail', async ({ page }, info) => {
  8  |   const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))
  9  |   const errors: string[] = []
  10 |   const methods: string[] = []
  11 |   page.on('pageerror', e => errors.push(e.message))
  12 |   page.on('request', r => { if (r.url().includes('/ops-api/')) methods.push(r.method()) })
  13 |   const html = await page.request.get('/ops/')
  14 |   const bytes = await html.body()
  15 |   expect(bytes.equals(readFileSync(`${own}/frontend/dist/ops/index.html`))).toBeTruthy()
  16 |   const assets = [...bytes.toString().matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map(x => x[1])
  17 |   const hashes: Record<string, string> = { 'ops/index.html': sha(bytes) }
  18 |   for (const asset of assets) {
  19 |     const response = await page.request.get(asset)
  20 |     const data = await response.body()
  21 |     expect(data.equals(readFileSync(`${own}/frontend/dist${asset}`))).toBeTruthy()
  22 |     hashes[asset] = sha(data)
  23 |   }
  24 |   await page.goto(`/ops/#/policies/${fixture.current}`)
  25 |   const detail = page.getByRole('region', { name: '策略版本详情' })
  26 |   // The product section has a label but no explicit region role.
  27 |   const section = page.locator('section[aria-label="策略版本详情"]')
  28 |   await expect(section.locator('.ant-descriptions')).toBeVisible()
  29 |   await expect(section.getByText('canary_health', { exact: true })).toBeVisible()
> 30 |   await expect(section.locator('.ant-tag').filter({ hasText: /^passed$/ })).toBeVisible()
     |                                                                             ^ Error: expect(locator).toBeVisible() failed
  31 |   await expect(section.locator('.ant-tag').filter({ hasText: /^hold$/ })).toBeVisible()
  32 |   const response = await page.request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  33 |   const api = await response.json()
  34 |   expect(api.is_current).toBeTruthy()
  35 |   expect(api.latest_health_window.decision).toBe('hold')
  36 |   expect(api.gate_receipts[0].receipt_id).toBe(fixture.old_receipt_id)
  37 |   expect(fixture.receipt_deployment).not.toBe(fixture.current)
  38 |   const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  39 |   expect(width).toBeLessThanOrEqual(1)
  40 |   const table = section.locator('.ant-table-content').first()
  41 |   if (info.project.name === 'mobile') {
  42 |     expect(await table.evaluate(e => e.scrollWidth > e.clientWidth)).toBeTruthy()
  43 |     await table.hover()
  44 |     await page.mouse.wheel(800, 0)
  45 |     await expect.poll(() => table.evaluate(e => e.scrollLeft)).toBeGreaterThan(0)
  46 |     await page.mouse.wheel(-800, 0)
  47 |   }
  48 |   await section.screenshot({ path: `${own}/screenshots/live-cross-binding-${info.project.name}.png` })
  49 |   await page.screenshot({ path: `${own}/screenshots/live-policies-${info.project.name}.png`, fullPage: true })
  50 |   expect(errors).toEqual([])
  51 |   expect([...new Set(methods)]).toEqual(['GET'])
  52 |   expect(await page.getByRole('button', { name: /发布|回滚|冻结|取消|重新入队/ }).count()).toBe(0)
  53 |   writeFileSync(`${own}/production-${info.project.name}.json`, JSON.stringify({
  54 |     role: 'fresh browser observation of a defect, not a correctness PASS',
  55 |     hashes, methods, errors, bodyOverflow: width,
  56 |     current: fixture.current, actual_receipt: fixture.old_receipt_id, source_deployment: fixture.receipt_deployment,
  57 |   }, null, 2))
  58 | })
  59 | 
  60 | test('current detail must not label foreign health receipt passed', async ({ page }, info) => {
  61 |   const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))
  62 |   await page.goto(`/ops/#/policies/${fixture.current}`)
  63 |   const section = page.locator('section[aria-label="策略版本详情"]')
  64 |   await expect(section.locator('.ant-descriptions')).toBeVisible()
  65 |   await section.screenshot({ path: `${own}/screenshots/live-correctness-${info.project.name}.png` })
  66 |   await expect(section.locator('.ant-tag').filter({ hasText: /^passed$/ })).toHaveCount(0)
  67 | })
  68 | 
```