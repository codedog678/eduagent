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
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e120]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 1
              - cell "registered" [ref=e125]
              - cell "historical 当前版本 3" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: historical
                  - generic [ref=e133]: 当前版本 3
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S 778de32838c9
                  - code [ref=e137]: C 不可用
              - cell "0%" [ref=e138]
              - cell "S 0 · C 0 · Shadow 0" [ref=e139]
              - cell "2026/11/1 22:22:49" [ref=e140]
            - row [ref=e141]:
              - cell [ref=e142]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e143] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e144]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e145]:
                - generic [ref=e146]:
                  - generic [ref=e147]: production
                  - strong [ref=e148]: 版本 1
              - cell "registered" [ref=e149]
              - cell "current 当前版本 1" [ref=e154]:
                - generic [ref=e155]:
                  - generic [ref=e156]: current
                  - generic [ref=e157]: 当前版本 1
              - cell [ref=e158]:
                - generic [ref=e159]:
                  - code [ref=e160]: S 778de32838c9
                  - code [ref=e161]: C 不可用
              - cell "0%" [ref=e162]
              - cell "S 40 · C 0 · Shadow 0" [ref=e163]
              - cell "2026/11/1 22:22:49" [ref=e164]
            - row [ref=e165]:
              - cell [ref=e166]:
                - link "查看策略 f9a512e1-95b3-4e2f-875b-1678de9389fb" [ref=e167] [cursor=pointer]:
                  - /url: "#/policies/f9a512e1-95b3-4e2f-875b-1678de9389fb"
                  - code [ref=e168]: f9a512e1-95b3-4e2f-875b-1678de9389fb
              - cell "rehearsal 版本 2" [ref=e169]:
                - generic [ref=e170]:
                  - generic [ref=e171]: rehearsal
                  - strong [ref=e172]: 版本 2
              - cell "canary" [ref=e173]
              - cell "historical 当前版本 3" [ref=e178]:
                - generic [ref=e179]:
                  - generic [ref=e180]: historical
                  - generic [ref=e181]: 当前版本 3
              - cell [ref=e182]:
                - generic [ref=e183]:
                  - code [ref=e184]: S 778de32838c9
                  - code [ref=e185]: C c646dbb9a0d0
              - cell "50%" [ref=e186]
              - cell "S 0 · C 0 · Shadow 0" [ref=e187]
              - cell "2026/11/1 00:00:00" [ref=e188]
            - row [ref=e189]:
              - cell [ref=e190]:
                - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0" [ref=e191] [cursor=pointer]:
                  - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                  - code [ref=e192]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
              - cell "rehearsal 版本 3" [ref=e193]:
                - generic [ref=e194]:
                  - generic [ref=e195]: rehearsal
                  - strong [ref=e196]: 版本 3
              - cell "canary" [ref=e197]
              - cell "current 当前版本 3" [ref=e202]:
                - generic [ref=e203]:
                  - generic [ref=e204]: current
                  - generic [ref=e205]: 当前版本 3
              - cell [ref=e206]:
                - generic [ref=e207]:
                  - code [ref=e208]: S 778de32838c9
                  - code [ref=e209]: C c646dbb9a0d0
              - cell "50%" [ref=e210]
              - cell "S 0 · C 0 · Shadow 0" [ref=e211]
              - cell "2026/11/1 00:00:00" [ref=e212]
      - generic "Policies 游标分页" [ref=e213]:
        - button "上一页" [disabled] [ref=e214]
        - generic [ref=e215]: 第 1 页
        - button "下一页" [disabled] [ref=e216]
      - region "策略版本详情" [ref=e217]:
        - generic [ref=e218]:
          - heading "策略版本详情" [level=3] [ref=e219]
          - link "关闭详情" [ref=e220] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e223]:
          - rowgroup [ref=e224]:
            - row [ref=e225]:
              - rowheader "Deployment" [ref=e226]
              - cell [ref=e227]:
                - code [ref=e229]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
            - row [ref=e230]:
              - rowheader "环境 / 版本" [ref=e231]
              - cell [ref=e232]:
                - generic [ref=e233]:
                  - text: rehearsal · 版本 3
                  - generic [ref=e234]: canary
            - row [ref=e238]:
              - rowheader "当前部署" [ref=e239]
              - cell [ref=e240]:
                - generic [ref=e241]:
                  - link "查看策略 ef94576b-f29f-4ecf-b530-2c37b63f66f0" [ref=e242] [cursor=pointer]:
                    - /url: "#/policies/ef94576b-f29f-4ecf-b530-2c37b63f66f0"
                    - code [ref=e243]: ef94576b-f29f-4ecf-b530-2c37b63f66f0
                  - text: · 当前版本 3
            - row [ref=e244]:
              - rowheader "Stable hash" [ref=e245]
              - cell [ref=e246]:
                - code [ref=e248]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e249]:
              - rowheader "Candidate hash" [ref=e250]
              - cell [ref=e251]:
                - code [ref=e253]: c646dbb9a0d03014d9b26f2ea74bddef7b7e2a577541f559edc0efc2deb75c73
            - row [ref=e254]:
              - rowheader "流量 / Cohort" [ref=e255]
              - cell "50% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e256]
            - row [ref=e258]:
              - rowheader "Actor / Reason" [ref=e259]
              - cell "redacted / redacted" [ref=e260]
            - row [ref=e262]:
              - rowheader "创建" [ref=e263]
              - cell "2026/11/1 00:00:00" [ref=e264]
        - paragraph [ref=e265]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e266]
        - generic [ref=e267]:
          - generic [ref=e268]:
            - term [ref=e269]: candidate_min_runs
            - definition [ref=e270]: "20"
          - generic [ref=e271]:
            - term [ref=e272]: stable_min_runs
            - definition [ref=e273]: "20"
          - generic [ref=e274]:
            - term [ref=e275]: window_max_runs
            - definition [ref=e276]: "50"
          - generic [ref=e277]:
            - term [ref=e278]: commit_failure_rate
            - definition [ref=e279]: "0.05"
          - generic [ref=e280]:
            - term [ref=e281]: terminal_failure_rate
            - definition [ref=e282]: "0.10"
          - generic [ref=e283]:
            - term [ref=e284]: latency_increase_rate
            - definition [ref=e285]: "0.50"
          - generic [ref=e286]:
            - term [ref=e287]: mean_cost_increase_rate
            - definition [ref=e288]: "0.30"
          - generic [ref=e289]:
            - term [ref=e290]: unknown_rate
            - definition [ref=e291]: "0.10"
          - generic [ref=e292]:
            - term [ref=e293]: relative_epsilon
            - definition [ref=e294]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e295]
        - table [ref=e302]:
          - rowgroup [ref=e310]:
            - row [ref=e311]:
              - columnheader "Gate" [ref=e312]
              - columnheader "状态" [ref=e313]
              - columnheader "样本" [ref=e314]
              - columnheader "成本 USD" [ref=e315]
              - columnheader "Issuer" [ref=e316]
              - columnheader "签发时间" [ref=e317]
          - rowgroup [ref=e318]:
            - row [ref=e319]:
              - cell "canary_health" [ref=e320]
              - cell "passed" [ref=e321]
              - cell "20" [ref=e326]
              - cell "0.40000000" [ref=e327]
              - cell "redacted" [ref=e328]
              - cell "2026/11/1 22:22:50" [ref=e329]
        - heading "最新健康窗口" [level=3] [ref=e330]
        - paragraph [ref=e331]:
          - generic [ref=e332]: hold
          - text: 2026/11/1 22:22:50 · 指标协议 v1
        - paragraph [ref=e335]: 触发阈值：baseline_shortage, cost_unavailable, structured_decisions_unavailable, matched_window_incomplete。未知指标保持未知，不作为零值。
        - table [ref=e342]:
          - rowgroup [ref=e347]:
            - row [ref=e348]:
              - columnheader "指标" [ref=e349]
              - columnheader "Candidate" [ref=e350]
              - columnheader "Stable" [ref=e351]
          - rowgroup [ref=e352]:
            - row [ref=e353]:
              - cell "run_count" [ref=e354]
              - cell "0" [ref=e355]
              - cell "0" [ref=e356]
            - row [ref=e357]:
              - cell "commit_failure_rate" [ref=e358]
              - cell "未知" [ref=e359]
              - cell "未知" [ref=e360]
            - row [ref=e361]:
              - cell "terminal_failure_rate" [ref=e362]
              - cell "未知" [ref=e363]
              - cell "未知" [ref=e364]
            - row [ref=e365]:
              - cell "p95_latency" [ref=e366]
              - cell "未知" [ref=e367]
              - cell "未知" [ref=e368]
            - row [ref=e369]:
              - cell "mean_cost" [ref=e370]
              - cell "未知" [ref=e371]
              - cell "未知" [ref=e372]
            - row [ref=e373]:
              - cell "structured_decision_count" [ref=e374]
              - cell "0" [ref=e375]
              - cell "0" [ref=e376]
            - row [ref=e377]:
              - cell "unknown_decision_count" [ref=e378]
              - cell "0" [ref=e379]
              - cell "0" [ref=e380]
            - row [ref=e381]:
              - cell "unknown_rate" [ref=e382]
              - cell "未知" [ref=e383]
              - cell "未知" [ref=e384]
            - row [ref=e385]:
              - cell "fault_injected_count" [ref=e386]
              - cell "0" [ref=e387]
              - cell "0" [ref=e388]
            - row [ref=e389]:
              - cell "injected_commit_failure_count" [ref=e390]
              - cell "0" [ref=e391]
              - cell "0" [ref=e392]
            - row [ref=e393]:
              - cell "natural_failure_count" [ref=e394]
              - cell "0" [ref=e395]
              - cell "0" [ref=e396]
            - row [ref=e397]:
              - cell "latency_increase_rate" [ref=e398]
              - cell "未知" [ref=e399]
              - cell "未知" [ref=e400]
            - row [ref=e401]:
              - cell "mean_cost_increase_rate" [ref=e402]
              - cell "未知" [ref=e403]
              - cell "未知" [ref=e404]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e405]
        - generic [ref=e406]:
          - img "No data" [ref=e408]
          - generic [ref=e414]: 暂无审计事件
        - paragraph [ref=e415]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
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