# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: health-binding.spec.ts >> current detail must not label foreign health receipt passed
- Location: live-e2e/health-binding.spec.ts:58:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })
Expected: 0
Received: 1
Timeout:  5000ms

Call log:
  - Expect "toHaveCount" locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ }) with timeout 5000ms
  - waiting for locator('section[aria-label="策略版本详情"]').locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })
    14 × locator resolved to 1 element
       - unexpected value "1"

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
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e119]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e120]:
                - generic [ref=e121]:
                  - generic [ref=e122]: rehearsal
                  - strong [ref=e123]: 版本 1
              - cell "registered" [ref=e124]
              - cell "historical 当前版本 3" [ref=e129]:
                - generic [ref=e130]:
                  - generic [ref=e131]: historical
                  - generic [ref=e132]: 当前版本 3
              - cell [ref=e133]:
                - generic [ref=e134]:
                  - code [ref=e135]: S 778de32838c9
                  - code [ref=e136]: C 不可用
              - cell "0%" [ref=e137]
              - cell "S 0 · C 0 · Shadow 0" [ref=e138]
              - cell "2026/11/1 22:22:49" [ref=e139]
            - row [ref=e140]:
              - cell [ref=e141]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e142] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e143]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e144]:
                - generic [ref=e145]:
                  - generic [ref=e146]: production
                  - strong [ref=e147]: 版本 1
              - cell "registered" [ref=e148]
              - cell "current 当前版本 1" [ref=e153]:
                - generic [ref=e154]:
                  - generic [ref=e155]: current
                  - generic [ref=e156]: 当前版本 1
              - cell [ref=e157]:
                - generic [ref=e158]:
                  - code [ref=e159]: S 778de32838c9
                  - code [ref=e160]: C 不可用
              - cell "0%" [ref=e161]
              - cell "S 40 · C 0 · Shadow 0" [ref=e162]
              - cell "2026/11/1 22:22:49" [ref=e163]
            - row [ref=e164]:
              - cell [ref=e165]:
                - link "查看策略 f9a512e1-95b3-4e2f-875b-1678de9389fb" [ref=e166] [cursor=pointer]:
                  - /url: "#/policies/f9a512e1-95b3-4e2f-875b-1678de9389fb"
                  - code [ref=e167]: f9a512e1-95b3-4e2f-875b-1678de9389fb
              - cell "rehearsal 版本 2" [ref=e168]:
                - generic [ref=e169]:
                  - generic [ref=e170]: rehearsal
                  - strong [ref=e171]: 版本 2
              - cell "canary" [ref=e172]
              - cell "historical 当前版本 3" [ref=e177]:
                - generic [ref=e178]:
                  - generic [ref=e179]: historical
                  - generic [ref=e180]: 当前版本 3
              - cell [ref=e181]:
                - generic [ref=e182]:
                  - code [ref=e183]: S 778de32838c9
                  - code [ref=e184]: C c646dbb9a0d0
              - cell "50%" [ref=e185]
              - cell "S 0 · C 0 · Shadow 0" [ref=e186]
              - cell "2026/11/1 00:00:00" [ref=e187]
            - row [ref=e188]:
              - cell [ref=e189]:
                - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0" [ref=e190] [cursor=pointer]:
                  - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                  - code [ref=e191]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
              - cell "rehearsal 版本 3" [ref=e192]:
                - generic [ref=e193]:
                  - generic [ref=e194]: rehearsal
                  - strong [ref=e195]: 版本 3
              - cell "canary" [ref=e196]
              - cell "current 当前版本 3" [ref=e201]:
                - generic [ref=e202]:
                  - generic [ref=e203]: current
                  - generic [ref=e204]: 当前版本 3
              - cell [ref=e205]:
                - generic [ref=e206]:
                  - code [ref=e207]: S 778de32838c9
                  - code [ref=e208]: C c646dbb9a0d0
              - cell "50%" [ref=e209]
              - cell "S 0 · C 0 · Shadow 0" [ref=e210]
              - cell "2026/11/1 00:00:00" [ref=e211]
      - generic "Policies 游标分页" [ref=e212]:
        - button "上一页" [disabled] [ref=e213]
        - generic [ref=e214]: 第 1 页
        - button "下一页" [disabled] [ref=e215]
      - region "策略版本详情" [ref=e216]:
        - generic [ref=e217]:
          - heading "策略版本详情" [level=3] [ref=e218]
          - link "关闭详情" [ref=e219] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e222]:
          - rowgroup [ref=e223]:
            - row [ref=e224]:
              - rowheader "Deployment" [ref=e225]
              - cell [ref=e226]:
                - code [ref=e228]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
            - row [ref=e229]:
              - rowheader "环境 / 版本" [ref=e230]
              - cell [ref=e231]:
                - generic [ref=e232]:
                  - text: rehearsal · 版本 3
                  - generic [ref=e233]: canary
            - row [ref=e237]:
              - rowheader "当前部署" [ref=e238]
              - cell [ref=e239]:
                - generic [ref=e240]:
                  - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0" [ref=e241] [cursor=pointer]:
                    - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                    - code [ref=e242]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
                  - text: · 当前版本 3
            - row [ref=e243]:
              - rowheader "Stable hash" [ref=e244]
              - cell [ref=e245]:
                - code [ref=e247]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e248]:
              - rowheader "Candidate hash" [ref=e249]
              - cell [ref=e250]:
                - code [ref=e252]: c646dbb9a0d03014d9b26f2ea74bddef7b7e2a577541f559edc0efc2deb75c73
            - row [ref=e253]:
              - rowheader "流量 / Cohort" [ref=e254]
              - cell "50% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e255]
            - row [ref=e257]:
              - rowheader "Actor / Reason" [ref=e258]
              - cell "redacted / redacted" [ref=e259]
            - row [ref=e261]:
              - rowheader "创建" [ref=e262]
              - cell "2026/11/1 00:00:00" [ref=e263]
        - paragraph [ref=e264]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e265]
        - generic [ref=e266]:
          - generic [ref=e267]:
            - term [ref=e268]: candidate_min_runs
            - definition [ref=e269]: "20"
          - generic [ref=e270]:
            - term [ref=e271]: stable_min_runs
            - definition [ref=e272]: "20"
          - generic [ref=e273]:
            - term [ref=e274]: window_max_runs
            - definition [ref=e275]: "50"
          - generic [ref=e276]:
            - term [ref=e277]: commit_failure_rate
            - definition [ref=e278]: "0.05"
          - generic [ref=e279]:
            - term [ref=e280]: terminal_failure_rate
            - definition [ref=e281]: "0.10"
          - generic [ref=e282]:
            - term [ref=e283]: latency_increase_rate
            - definition [ref=e284]: "0.50"
          - generic [ref=e285]:
            - term [ref=e286]: mean_cost_increase_rate
            - definition [ref=e287]: "0.30"
          - generic [ref=e288]:
            - term [ref=e289]: unknown_rate
            - definition [ref=e290]: "0.10"
          - generic [ref=e291]:
            - term [ref=e292]: relative_epsilon
            - definition [ref=e293]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e294]
        - table [ref=e301]:
          - rowgroup [ref=e309]:
            - row [ref=e310]:
              - columnheader "Gate" [ref=e311]
              - columnheader "状态" [ref=e312]
              - columnheader "样本" [ref=e313]
              - columnheader "成本 USD" [ref=e314]
              - columnheader "Issuer" [ref=e315]
              - columnheader "签发时间" [ref=e316]
          - rowgroup [ref=e317]:
            - row [ref=e318]:
              - cell "canary_health" [ref=e319]
              - cell "passed" [ref=e320]
              - cell "20" [ref=e325]
              - cell "0.40000000" [ref=e326]
              - cell "redacted" [ref=e327]
              - cell "2026/11/1 22:22:50" [ref=e328]
        - heading "最新健康窗口" [level=3] [ref=e329]
        - paragraph [ref=e330]:
          - generic [ref=e331]: hold
          - text: 2026/11/1 22:22:50 · 指标协议 v1
        - paragraph [ref=e334]: 触发阈值：baseline_shortage, cost_unavailable, structured_decisions_unavailable, matched_window_incomplete。未知指标保持未知，不作为零值。
        - table [ref=e341]:
          - rowgroup [ref=e346]:
            - row [ref=e347]:
              - columnheader "指标" [ref=e348]
              - columnheader "Candidate" [ref=e349]
              - columnheader "Stable" [ref=e350]
          - rowgroup [ref=e351]:
            - row [ref=e352]:
              - cell "run_count" [ref=e353]
              - cell "0" [ref=e354]
              - cell "0" [ref=e355]
            - row [ref=e356]:
              - cell "commit_failure_rate" [ref=e357]
              - cell "未知" [ref=e358]
              - cell "未知" [ref=e359]
            - row [ref=e360]:
              - cell "terminal_failure_rate" [ref=e361]
              - cell "未知" [ref=e362]
              - cell "未知" [ref=e363]
            - row [ref=e364]:
              - cell "p95_latency" [ref=e365]
              - cell "未知" [ref=e366]
              - cell "未知" [ref=e367]
            - row [ref=e368]:
              - cell "mean_cost" [ref=e369]
              - cell "未知" [ref=e370]
              - cell "未知" [ref=e371]
            - row [ref=e372]:
              - cell "structured_decision_count" [ref=e373]
              - cell "0" [ref=e374]
              - cell "0" [ref=e375]
            - row [ref=e376]:
              - cell "unknown_decision_count" [ref=e377]
              - cell "0" [ref=e378]
              - cell "0" [ref=e379]
            - row [ref=e380]:
              - cell "unknown_rate" [ref=e381]
              - cell "未知" [ref=e382]
              - cell "未知" [ref=e383]
            - row [ref=e384]:
              - cell "fault_injected_count" [ref=e385]
              - cell "0" [ref=e386]
              - cell "0" [ref=e387]
            - row [ref=e388]:
              - cell "injected_commit_failure_count" [ref=e389]
              - cell "0" [ref=e390]
              - cell "0" [ref=e391]
            - row [ref=e392]:
              - cell "natural_failure_count" [ref=e393]
              - cell "0" [ref=e394]
              - cell "0" [ref=e395]
            - row [ref=e396]:
              - cell "latency_increase_rate" [ref=e397]
              - cell "未知" [ref=e398]
              - cell "未知" [ref=e399]
            - row [ref=e400]:
              - cell "mean_cost_increase_rate" [ref=e401]
              - cell "未知" [ref=e402]
              - cell "未知" [ref=e403]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e404]
        - generic [ref=e405]:
          - img "No data" [ref=e407]
          - generic [ref=e413]: 暂无审计事件
        - paragraph [ref=e414]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
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
  25 |   const section = page.locator('section[aria-label="策略版本详情"]')
  26 |   await expect(section.locator('.ant-descriptions')).toBeVisible()
  27 |   await expect(section.getByText('canary_health', { exact: true })).toBeVisible()
  28 |   await expect(section.locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })).toBeVisible()
  29 |   await expect(section.locator('.ant-tag').filter({ hasText: /^\s*hold\s*$/ })).toBeVisible()
  30 |   const response = await page.request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  31 |   const api = await response.json()
  32 |   expect(api.is_current).toBeTruthy()
  33 |   expect(api.latest_health_window.decision).toBe('hold')
  34 |   expect(api.gate_receipts[0].receipt_id).toBe(fixture.old_receipt_id)
  35 |   expect(fixture.receipt_deployment).not.toBe(fixture.current)
  36 |   const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  37 |   expect(width).toBeLessThanOrEqual(1)
  38 |   const table = section.locator('.ant-table-content').first()
  39 |   if (info.project.name === 'mobile') {
  40 |     expect(await table.evaluate(e => e.scrollWidth > e.clientWidth)).toBeTruthy()
  41 |     await table.hover()
  42 |     await page.mouse.wheel(800, 0)
  43 |     await expect.poll(() => table.evaluate(e => e.scrollLeft)).toBeGreaterThan(0)
  44 |     await page.mouse.wheel(-800, 0)
  45 |   }
  46 |   await section.screenshot({ path: `${own}/screenshots/live2-cross-binding-${info.project.name}.png` })
  47 |   await page.screenshot({ path: `${own}/screenshots/live2-policies-${info.project.name}.png`, fullPage: true })
  48 |   expect(errors).toEqual([])
  49 |   expect([...new Set(methods)]).toEqual(['GET'])
  50 |   expect(await page.getByRole('button', { name: /发布|回滚|冻结|取消|重新入队/ }).count()).toBe(0)
  51 |   writeFileSync(`${own}/production-${info.project.name}.json`, JSON.stringify({
  52 |     role: 'fresh browser observation of a defect, not a correctness PASS',
  53 |     hashes, methods, errors, bodyOverflow: width,
  54 |     current: fixture.current, actual_receipt: fixture.old_receipt_id, source_deployment: fixture.receipt_deployment,
  55 |   }, null, 2))
  56 | })
  57 | 
  58 | test('current detail must not label foreign health receipt passed', async ({ page }, info) => {
  59 |   const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))
  60 |   await page.goto(`/ops/#/policies/${fixture.current}`)
  61 |   const section = page.locator('section[aria-label="策略版本详情"]')
  62 |   await expect(section.locator('.ant-descriptions')).toBeVisible()
  63 |   await section.screenshot({ path: `${own}/screenshots/live2-correctness-${info.project.name}.png` })
> 64 |   await expect(section.locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })).toHaveCount(0)
     |                                                                                   ^ Error: expect(locator).toHaveCount(expected) failed
  65 | })
  66 | 
```