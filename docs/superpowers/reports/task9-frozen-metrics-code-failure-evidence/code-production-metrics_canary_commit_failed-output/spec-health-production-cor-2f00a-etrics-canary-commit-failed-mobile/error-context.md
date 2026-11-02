# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding metrics_canary_commit_failed
- Location: live-e2e/spec-health.spec.ts:14:1

# Error details

```
Error: authority-rejected metric leaf must not become green Ops evidence

expect(received).toEqual(expected) // deep equality

- Expected  - 0
+ Received  + 1

  Array [
+   "canary_health",
    "shadow_health",
  ]
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
                - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                  - code [ref=e119]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
              - cell "rehearsal 版本 5" [ref=e120]:
                - generic [ref=e121]:
                  - generic [ref=e122]: rehearsal
                  - strong [ref=e123]: 版本 5
              - cell "canary" [ref=e124]
              - cell "current 当前版本 5" [ref=e129]:
                - generic [ref=e130]:
                  - generic [ref=e131]: current
                  - generic [ref=e132]: 当前版本 5
              - cell [ref=e133]:
                - generic [ref=e134]:
                  - code [ref=e135]: S 778de32838c9
                  - code [ref=e136]: C 2537b3d6216e
              - cell "50%" [ref=e137]
              - cell "S 0 · C 0 · Shadow 0" [ref=e138]
              - cell "2026/11/2 07:38:43" [ref=e139]
            - row [ref=e140]:
              - cell [ref=e141]:
                - link "查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2" [ref=e142] [cursor=pointer]:
                  - /url: "#/policies/ca47198b-1dd7-4952-a136-3fd199e945e2"
                  - code [ref=e143]: ca47198b-1dd7-4952-a136-3fd199e945e2
              - cell "rehearsal 版本 4" [ref=e144]:
                - generic [ref=e145]:
                  - generic [ref=e146]: rehearsal
                  - strong [ref=e147]: 版本 4
              - cell "shadow" [ref=e148]
              - cell "historical 当前版本 5" [ref=e153]:
                - generic [ref=e154]:
                  - generic [ref=e155]: historical
                  - generic [ref=e156]: 当前版本 5
              - cell [ref=e157]:
                - generic [ref=e158]:
                  - code [ref=e159]: S 778de32838c9
                  - code [ref=e160]: C 2537b3d6216e
              - cell "0%" [ref=e161]
              - cell "S 0 · C 0 · Shadow 0" [ref=e162]
              - cell "2026/11/2 07:38:43" [ref=e163]
            - row [ref=e164]:
              - cell [ref=e165]:
                - link "查看策略 6d050a6b-94dc-4b26-953b-44c44392a9bd" [ref=e166] [cursor=pointer]:
                  - /url: "#/policies/6d050a6b-94dc-4b26-953b-44c44392a9bd"
                  - code [ref=e167]: 6d050a6b-94dc-4b26-953b-44c44392a9bd
              - cell "rehearsal 版本 3" [ref=e168]:
                - generic [ref=e169]:
                  - generic [ref=e170]: rehearsal
                  - strong [ref=e171]: 版本 3
              - cell "registered" [ref=e172]
              - cell "historical 当前版本 5" [ref=e177]:
                - generic [ref=e178]:
                  - generic [ref=e179]: historical
                  - generic [ref=e180]: 当前版本 5
              - cell [ref=e181]:
                - generic [ref=e182]:
                  - code [ref=e183]: S 778de32838c9
                  - code [ref=e184]: C 2537b3d6216e
              - cell "0%" [ref=e185]
              - cell "S 0 · C 0 · Shadow 0" [ref=e186]
              - cell "2026/11/2 07:38:43" [ref=e187]
            - row [ref=e188]:
              - cell [ref=e189]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e190] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e191]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e192]:
                - generic [ref=e193]:
                  - generic [ref=e194]: rehearsal
                  - strong [ref=e195]: 版本 1
              - cell "registered" [ref=e196]
              - cell "historical 当前版本 5" [ref=e201]:
                - generic [ref=e202]:
                  - generic [ref=e203]: historical
                  - generic [ref=e204]: 当前版本 5
              - cell [ref=e205]:
                - generic [ref=e206]:
                  - code [ref=e207]: S 778de32838c9
                  - code [ref=e208]: C 不可用
              - cell "0%" [ref=e209]
              - cell "S 0 · C 0 · Shadow 0" [ref=e210]
              - cell "2026/11/2 07:38:43" [ref=e211]
            - row [ref=e212]:
              - cell [ref=e213]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e214] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e215]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e216]:
                - generic [ref=e217]:
                  - generic [ref=e218]: production
                  - strong [ref=e219]: 版本 1
              - cell "registered" [ref=e220]
              - cell "current 当前版本 1" [ref=e225]:
                - generic [ref=e226]:
                  - generic [ref=e227]: current
                  - generic [ref=e228]: 当前版本 1
              - cell [ref=e229]:
                - generic [ref=e230]:
                  - code [ref=e231]: S 778de32838c9
                  - code [ref=e232]: C 不可用
              - cell "0%" [ref=e233]
              - cell "S 61 · C 0 · Shadow 0" [ref=e234]
              - cell "2026/11/2 07:38:43" [ref=e235]
            - row [ref=e236]:
              - cell [ref=e237]:
                - link "查看策略 c7a25dfe-2e71-429d-ac98-e23d67a6a23d" [ref=e238] [cursor=pointer]:
                  - /url: "#/policies/c7a25dfe-2e71-429d-ac98-e23d67a6a23d"
                  - code [ref=e239]: c7a25dfe-2e71-429d-ac98-e23d67a6a23d
              - cell "rehearsal 版本 2" [ref=e240]:
                - generic [ref=e241]:
                  - generic [ref=e242]: rehearsal
                  - strong [ref=e243]: 版本 2
              - cell "canary" [ref=e244]
              - cell "historical 当前版本 5" [ref=e249]:
                - generic [ref=e250]:
                  - generic [ref=e251]: historical
                  - generic [ref=e252]: 当前版本 5
              - cell [ref=e253]:
                - generic [ref=e254]:
                  - code [ref=e255]: S 778de32838c9
                  - code [ref=e256]: C b8b1763edca4
              - cell "50%" [ref=e257]
              - cell "S 0 · C 0 · Shadow 0" [ref=e258]
              - cell "2026/11/1 00:00:00" [ref=e259]
      - generic "Policies 游标分页" [ref=e260]:
        - button "上一页" [disabled] [ref=e261]
        - generic [ref=e262]: 第 1 页
        - button "下一页" [disabled] [ref=e263]
      - region "策略版本详情" [ref=e264]:
        - generic [ref=e265]:
          - heading "策略版本详情" [level=3] [ref=e266]
          - link "关闭详情" [ref=e267] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e270]:
          - rowgroup [ref=e271]:
            - row [ref=e272]:
              - rowheader "Deployment" [ref=e273]
              - cell [ref=e274]:
                - code [ref=e276]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
            - row [ref=e277]:
              - rowheader "环境 / 版本" [ref=e278]
              - cell [ref=e279]:
                - generic [ref=e280]:
                  - text: rehearsal · 版本 5
                  - generic [ref=e281]: canary
            - row [ref=e285]:
              - rowheader "当前部署" [ref=e286]
              - cell [ref=e287]:
                - generic [ref=e288]:
                  - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e289] [cursor=pointer]:
                    - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                    - code [ref=e290]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
                  - text: · 当前版本 5
            - row [ref=e291]:
              - rowheader "Stable hash" [ref=e292]
              - cell [ref=e293]:
                - code [ref=e295]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e296]:
              - rowheader "Candidate hash" [ref=e297]
              - cell [ref=e298]:
                - code [ref=e300]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e301]:
              - rowheader "流量 / Cohort" [ref=e302]
              - cell "50% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e303]
            - row [ref=e305]:
              - rowheader "Actor / Reason" [ref=e306]
              - cell "redacted / redacted" [ref=e307]
            - row [ref=e309]:
              - rowheader "创建" [ref=e310]
              - cell "2026/11/2 07:38:43" [ref=e311]
        - paragraph [ref=e312]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e313]
        - generic [ref=e314]:
          - generic [ref=e315]:
            - term [ref=e316]: candidate_min_runs
            - definition [ref=e317]: "20"
          - generic [ref=e318]:
            - term [ref=e319]: stable_min_runs
            - definition [ref=e320]: "20"
          - generic [ref=e321]:
            - term [ref=e322]: window_max_runs
            - definition [ref=e323]: "50"
          - generic [ref=e324]:
            - term [ref=e325]: commit_failure_rate
            - definition [ref=e326]: "0.05"
          - generic [ref=e327]:
            - term [ref=e328]: terminal_failure_rate
            - definition [ref=e329]: "0.10"
          - generic [ref=e330]:
            - term [ref=e331]: latency_increase_rate
            - definition [ref=e332]: "0.50"
          - generic [ref=e333]:
            - term [ref=e334]: mean_cost_increase_rate
            - definition [ref=e335]: "0.30"
          - generic [ref=e336]:
            - term [ref=e337]: unknown_rate
            - definition [ref=e338]: "0.10"
          - generic [ref=e339]:
            - term [ref=e340]: relative_epsilon
            - definition [ref=e341]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e342]
        - paragraph [ref=e343]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e345]:
          - text: shadow_health
          - generic [ref=e346]: passed
        - table [ref=e356]:
          - rowgroup [ref=e365]:
            - row [ref=e366]:
              - columnheader "Gate" [ref=e367]
              - columnheader "状态" [ref=e368]
              - columnheader "健康来源" [ref=e369]
              - columnheader "样本" [ref=e370]
              - columnheader "成本 USD" [ref=e371]
              - columnheader "Issuer" [ref=e372]
              - columnheader "签发时间" [ref=e373]
          - rowgroup [ref=e374]:
            - row [ref=e375]:
              - cell "campaign_eligibility" [ref=e376]
              - cell "passed" [ref=e377]
              - cell "artifact 资格证据" [ref=e382]
              - cell "21" [ref=e383]
              - cell "1.25000000" [ref=e384]
              - cell "redacted" [ref=e385]
              - cell "2026/10/30 08:00:01" [ref=e386]
            - row [ref=e387]:
              - cell "canary_health" [ref=e388]
              - cell "passed" [ref=e389]
              - cell "本部署窗口 查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee 版本 5 · pass · 来源最新窗口 Window 6c872f478f22af3c528621b9e2d143dbf13f4c4fa1c630ec5cb4e55410d6cf89 2026/11/2 07:38:43" [ref=e394]:
                - generic [ref=e395]:
                  - strong [ref=e396]: 本部署窗口
                  - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e397] [cursor=pointer]:
                    - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                    - code [ref=e398]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
                  - generic [ref=e399]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e400]: Window 6c872f478f22af3c528621b9e2d143dbf13f4c4fa1c630ec5cb4e55410d6cf89
                  - generic [ref=e401]: 2026/11/2 07:38:43
              - cell "20" [ref=e402]
              - cell "0.40000000" [ref=e403]
              - cell "redacted" [ref=e404]
              - cell "2026/11/2 07:38:43" [ref=e405]
            - row [ref=e406]:
              - cell "formal_holdout" [ref=e407]
              - cell "passed" [ref=e408]
              - cell "artifact 资格证据" [ref=e413]
              - cell "23" [ref=e414]
              - cell "1.25000000" [ref=e415]
              - cell "redacted" [ref=e416]
              - cell "2026/10/30 08:00:03" [ref=e417]
            - row [ref=e418]:
              - cell "harness_qualification" [ref=e419]
              - cell "passed" [ref=e420]
              - cell "artifact 资格证据" [ref=e425]
              - cell "24" [ref=e426]
              - cell "1.25000000" [ref=e427]
              - cell "redacted" [ref=e428]
              - cell "2026/10/30 08:00:04" [ref=e429]
            - row [ref=e430]:
              - cell "judge_calibration" [ref=e431]
              - cell "passed" [ref=e432]
              - cell "artifact 资格证据" [ref=e437]
              - cell "22" [ref=e438]
              - cell "1.25000000" [ref=e439]
              - cell "redacted" [ref=e440]
              - cell "2026/10/30 08:00:02" [ref=e441]
            - row [ref=e442]:
              - cell "shadow_health" [ref=e443]
              - cell "passed" [ref=e444]
              - cell "已消费前序证据（非本部署新观测） 查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2 版本 4 · pass · 来源最新窗口 Window c9b681ede44d053cd72e08dc52b6f8ae05af5976d186385d6c0450ef2ada4603 2026/11/2 07:38:43" [ref=e449]:
                - generic [ref=e450]:
                  - strong [ref=e451]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2" [ref=e452] [cursor=pointer]:
                    - /url: "#/policies/ca47198b-1dd7-4952-a136-3fd199e945e2"
                    - code [ref=e453]: ca47198b-1dd7-4952-a136-3fd199e945e2
                  - generic [ref=e454]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e455]: Window c9b681ede44d053cd72e08dc52b6f8ae05af5976d186385d6c0450ef2ada4603
                  - generic [ref=e456]: 2026/11/2 07:38:43
              - cell "20" [ref=e457]
              - cell "0.40000000" [ref=e458]
              - cell "redacted" [ref=e459]
              - cell "2026/11/2 07:38:43" [ref=e460]
        - heading "最新健康窗口" [level=3] [ref=e461]
        - paragraph [ref=e462]:
          - generic [ref=e463]: pass
          - text: 2026/11/2 07:38:43 · 指标协议 v1
        - paragraph [ref=e467]: 触发阈值：无。未知指标保持未知，不作为零值。
        - table [ref=e474]:
          - rowgroup [ref=e479]:
            - row [ref=e480]:
              - columnheader "指标" [ref=e481]
              - columnheader "Candidate" [ref=e482]
              - columnheader "Stable" [ref=e483]
          - rowgroup [ref=e484]:
            - row [ref=e485]:
              - cell "run_count" [ref=e486]
              - cell "20" [ref=e487]
              - cell "20" [ref=e488]
            - row [ref=e489]:
              - cell "commit_failure_rate" [ref=e490]
              - cell "0" [ref=e491]
              - cell "0" [ref=e492]
            - row [ref=e493]:
              - cell "terminal_failure_rate" [ref=e494]
              - cell "0" [ref=e495]
              - cell "0" [ref=e496]
            - row [ref=e497]:
              - cell "p95_latency" [ref=e498]
              - cell "1.000000" [ref=e499]
              - cell "1.000000" [ref=e500]
            - row [ref=e501]:
              - cell "mean_cost" [ref=e502]
              - cell "0.01000000" [ref=e503]
              - cell "0.01000000" [ref=e504]
            - row [ref=e505]:
              - cell "structured_decision_count" [ref=e506]
              - cell "200" [ref=e507]
              - cell "200" [ref=e508]
            - row [ref=e509]:
              - cell "unknown_decision_count" [ref=e510]
              - cell "0" [ref=e511]
              - cell "0" [ref=e512]
            - row [ref=e513]:
              - cell "unknown_rate" [ref=e514]
              - cell "0" [ref=e515]
              - cell "0" [ref=e516]
            - row [ref=e517]:
              - cell "fault_injected_count" [ref=e518]
              - cell "0" [ref=e519]
              - cell "0" [ref=e520]
            - row [ref=e521]:
              - cell "injected_commit_failure_count" [ref=e522]
              - cell "0" [ref=e523]
              - cell "0" [ref=e524]
            - row [ref=e525]:
              - cell "natural_failure_count" [ref=e526]
              - cell "0" [ref=e527]
              - cell "0" [ref=e528]
            - row [ref=e529]:
              - cell "latency_increase_rate" [ref=e530]
              - cell "0" [ref=e531]
              - cell "未知" [ref=e532]
            - row [ref=e533]:
              - cell "mean_cost_increase_rate" [ref=e534]
              - cell "0" [ref=e535]
              - cell "未知" [ref=e536]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e537]
        - list [ref=e538]:
          - listitem [ref=e539]:
            - generic [ref=e547]:
              - strong [ref=e548]: promotion_transitioned
              - generic [ref=e549]: shadow → canary
              - generic [ref=e550]: 2026/11/2 07:38:43 · rehearsal
              - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e551] [cursor=pointer]:
                - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                - code [ref=e552]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
              - generic [ref=e553]: "actor: redacted · reason: redacted"
        - paragraph [ref=e554]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  2   | import { readFileSync, writeFileSync } from 'node:fs'
  3   | import { createHash } from 'node:crypto'
  4   | import { join } from 'node:path'
  5   | 
  6   | const own = '/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814'
  7   | const scenario = process.env.SPEC_SCENARIO!
  8   | const historical = scenario.startsWith('history')
  9   | const validChain = scenario === 'genuine_valid' || scenario === 'leaf_active_valid'
  10  | const validLocal = scenario === 'leaf_local_valid' || scenario === 'leaf_shadow_valid'
  11  | const tag = process.env.SPEC_RUN_TAG || scenario
  12  | const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${tag}.json`), 'utf8'))
  13  | 
  14  | test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
  15  |   const requests: { method: string; url: string }[] = []
  16  |   const errors: string[] = []
  17  |   page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  18  |   page.on('pageerror', e => errors.push(e.message))
  19  |   page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  20  |   const response = await request.get(`/ops-api/ops/policies/deployments/${fixture.id}`)
  21  |   expect(response.status()).toBe(200)
  22  |   const body = await response.json()
  23  |   await page.goto(`/ops/#/policies/${fixture.id}`)
  24  |   const detail = page.getByRole('region', { name: '策略版本详情' })
  25  |   await expect(detail.getByText(fixture.policy_hash, { exact: true }).first()).toBeVisible()
  26  |   await expect(detail.getByText(/收据是历史证据，不代表可发布资格/)).toBeVisible()
  27  |   const sourceText = await detail.locator('strong').allTextContents()
  28  |   const source = detail.getByText(historical
  29  |     ? '本部署窗口'
  30  |     : '已消费前序证据（非本部署新观测）', { exact: true }).first()
  31  |   if (historical || validChain || validLocal) {
  32  |     const visibleSource = validLocal ? detail.getByText('本部署窗口', { exact: true }).first() : source
  33  |     await expect(visibleSource).toBeVisible()
  34  |     await visibleSource.scrollIntoViewIfNeeded()
  35  |     const box = await visibleSource.boundingBox()
  36  |     expect(box).not.toBeNull()
  37  |     expect(box!.x).toBeGreaterThanOrEqual(0)
  38  |     expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  39  |     await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  40  |       animations: 'disabled' })
  41  |   }
  42  |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  43  |     animations: 'disabled' })
  44  |   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  45  |   const scrollBefore = await detail.locator('.ant-table-content').evaluateAll(
  46  |     els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth })))
  47  |   if (info.project.name === 'mobile') {
  48  |     const table = detail.locator('.ant-table-content').first()
  49  |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  50  |     await table.hover()
  51  |     await page.mouse.wheel(1100, 0)
  52  |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(scrollBefore[0].left)
  53  |   }
  54  |   const hashes: Record<string, string> = {}
  55  |   const assetEvidence: { url: string; bytes: number; sha256: string; status: number }[] = []
  56  |   for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
  57  |     const asset = await request.get(url)
  58  |     const bytes = await asset.body()
  59  |     expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
  60  |     hashes[url] = createHash('sha256').update(bytes).digest('hex')
  61  |     assetEvidence.push({ url, bytes: bytes.length, sha256: hashes[url], status: asset.status() })
  62  |   }
  63  |   expect(Object.keys(hashes).length).toBeGreaterThan(0)
  64  |   expect(requests.every(r => r.method === 'GET')).toBe(true)
  65  |   expect(errors).toEqual([])
  66  |   expect(overflow).toBeLessThanOrEqual(1)
  67  |   await page.screenshot({ path: `${own}/screenshots/production-${tag}-${info.project.name}.png`,
  68  |     fullPage: true, animations: 'disabled' })
  69  |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}.png`,
  70  |     animations: 'disabled' })
  71  |   writeFileSync(`${own}/production-${tag}-${info.project.name}.json`,
  72  |     JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes,
  73  |       assetEvidence, scrollBefore,
  74  |       scrollAfter: await detail.locator('.ant-table-content').evaluateAll(
  75  |         els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth }))),
  76  |       requestContext: { detailGet: response.status(), assetGets: assetEvidence.length },
  77  |       viewport: page.viewportSize(),
  78  |     }, null, 2) + '\n')
  79  |   const health = body.gate_receipts.filter((r: { health_source: unknown }) => r.health_source)
  80  |   if (scenario === 'current') {
  81  |     expect(body.is_current).toBe(true)
  82  |     expect(body.latest_health_window.decision).toBe('hold')
  83  |     expect(health).toEqual([])
  84  |     await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
  85  |   } else if (historical) {
  86  |     expect(body.is_current).toBe(false)
  87  |     expect(health).toHaveLength(1)
  88  |     expect(health[0].receipt_id).toBe(fixture.old_receipt)
  89  |     expect(health[0].health_source.deployment_id).toBe(fixture.old)
  90  |     expect(health[0].health_source.window_id).toBe(fixture.old_window)
  91  |     const newer = await request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  92  |     const newBody = await newer.json()
  93  |     expect(newBody.latest_health_window.decision).toBe('pass')
  94  |     expect(newBody.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
  95  |       .not.toBe(fixture.old_receipt)
  96  |   } else if (scenario.startsWith('metrics_')) {
  97  |     const valid = scenario === 'metrics_active_valid'
  98  |     expect(fixture.leaf_proof.authority_accepts).toBe(valid)
  99  |     const expected = valid ? ['canary_health', 'shadow_health']
  100 |       : scenario.startsWith('metrics_canary_') ? ['shadow_health'] : []
  101 |     expect(health.map((r: { gate_type: string }) => r.gate_type).sort(),
> 102 |       'authority-rejected metric leaf must not become green Ops evidence').toEqual(expected)
      |                                                                            ^ Error: authority-rejected metric leaf must not become green Ops evidence
  103 |   } else if (scenario.startsWith('leaf_')) {
  104 |     const gate = scenario === 'leaf_shadow_valid' ? 'shadow_health' : 'canary_health'
  105 |     const ownLeaf = health.find((r: { gate_type: string }) => r.gate_type === gate)
  106 |     expect(fixture.leaf_proof.authority_accepts).toBe(validLocal || validChain)
  107 |     if (validLocal || validChain) {
  108 |       expect(ownLeaf.receipt_id).toBe(fixture.leaf_proof.receipt_id)
  109 |       expect(ownLeaf.health_source.relation).toBe(validLocal ? 'local' : 'consumed_chain')
  110 |       expect(health).toHaveLength(scenario === 'leaf_shadow_valid' ? 1 : 2)
  111 |     } else if (scenario === 'leaf_local_bad') {
  112 |       expect(ownLeaf).toBeUndefined()
  113 |       expect(health).toHaveLength(1)
  114 |       expect(health[0].gate_type).toBe('shadow_health')
  115 |       expect(health[0].health_source.relation).toBe('consumed_chain')
  116 |     } else {
  117 |       expect(health).toEqual([])
  118 |       await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  119 |     }
  120 |   } else if (validChain) {
  121 |     expect(health).toHaveLength(2)
  122 |     expect(health.every((r: { status: string; health_source: { relation: string } }) =>
  123 |       r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  124 |   } else {
  125 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
  126 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  127 |   }
  128 | })
  129 | 
```