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
                - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                  - code [ref=e120]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
              - cell "rehearsal 版本 5" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 5
              - cell "canary" [ref=e125]
              - cell "current 当前版本 5" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: current
                  - generic [ref=e133]: 当前版本 5
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S 778de32838c9
                  - code [ref=e137]: C 2537b3d6216e
              - cell "50%" [ref=e138]
              - cell "S 0 · C 0 · Shadow 0" [ref=e139]
              - cell "2026/11/2 07:38:43" [ref=e140]
            - row [ref=e141]:
              - cell [ref=e142]:
                - link "查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2" [ref=e143] [cursor=pointer]:
                  - /url: "#/policies/ca47198b-1dd7-4952-a136-3fd199e945e2"
                  - code [ref=e144]: ca47198b-1dd7-4952-a136-3fd199e945e2
              - cell "rehearsal 版本 4" [ref=e145]:
                - generic [ref=e146]:
                  - generic [ref=e147]: rehearsal
                  - strong [ref=e148]: 版本 4
              - cell "shadow" [ref=e149]
              - cell "historical 当前版本 5" [ref=e154]:
                - generic [ref=e155]:
                  - generic [ref=e156]: historical
                  - generic [ref=e157]: 当前版本 5
              - cell [ref=e158]:
                - generic [ref=e159]:
                  - code [ref=e160]: S 778de32838c9
                  - code [ref=e161]: C 2537b3d6216e
              - cell "0%" [ref=e162]
              - cell "S 0 · C 0 · Shadow 0" [ref=e163]
              - cell "2026/11/2 07:38:43" [ref=e164]
            - row [ref=e165]:
              - cell [ref=e166]:
                - link "查看策略 6d050a6b-94dc-4b26-953b-44c44392a9bd" [ref=e167] [cursor=pointer]:
                  - /url: "#/policies/6d050a6b-94dc-4b26-953b-44c44392a9bd"
                  - code [ref=e168]: 6d050a6b-94dc-4b26-953b-44c44392a9bd
              - cell "rehearsal 版本 3" [ref=e169]:
                - generic [ref=e170]:
                  - generic [ref=e171]: rehearsal
                  - strong [ref=e172]: 版本 3
              - cell "registered" [ref=e173]
              - cell "historical 当前版本 5" [ref=e178]:
                - generic [ref=e179]:
                  - generic [ref=e180]: historical
                  - generic [ref=e181]: 当前版本 5
              - cell [ref=e182]:
                - generic [ref=e183]:
                  - code [ref=e184]: S 778de32838c9
                  - code [ref=e185]: C 2537b3d6216e
              - cell "0%" [ref=e186]
              - cell "S 0 · C 0 · Shadow 0" [ref=e187]
              - cell "2026/11/2 07:38:43" [ref=e188]
            - row [ref=e189]:
              - cell [ref=e190]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e191] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e192]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e193]:
                - generic [ref=e194]:
                  - generic [ref=e195]: rehearsal
                  - strong [ref=e196]: 版本 1
              - cell "registered" [ref=e197]
              - cell "historical 当前版本 5" [ref=e202]:
                - generic [ref=e203]:
                  - generic [ref=e204]: historical
                  - generic [ref=e205]: 当前版本 5
              - cell [ref=e206]:
                - generic [ref=e207]:
                  - code [ref=e208]: S 778de32838c9
                  - code [ref=e209]: C 不可用
              - cell "0%" [ref=e210]
              - cell "S 0 · C 0 · Shadow 0" [ref=e211]
              - cell "2026/11/2 07:38:43" [ref=e212]
            - row [ref=e213]:
              - cell [ref=e214]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e215] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e216]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e217]:
                - generic [ref=e218]:
                  - generic [ref=e219]: production
                  - strong [ref=e220]: 版本 1
              - cell "registered" [ref=e221]
              - cell "current 当前版本 1" [ref=e226]:
                - generic [ref=e227]:
                  - generic [ref=e228]: current
                  - generic [ref=e229]: 当前版本 1
              - cell [ref=e230]:
                - generic [ref=e231]:
                  - code [ref=e232]: S 778de32838c9
                  - code [ref=e233]: C 不可用
              - cell "0%" [ref=e234]
              - cell "S 61 · C 0 · Shadow 0" [ref=e235]
              - cell "2026/11/2 07:38:43" [ref=e236]
            - row [ref=e237]:
              - cell [ref=e238]:
                - link "查看策略 c7a25dfe-2e71-429d-ac98-e23d67a6a23d" [ref=e239] [cursor=pointer]:
                  - /url: "#/policies/c7a25dfe-2e71-429d-ac98-e23d67a6a23d"
                  - code [ref=e240]: c7a25dfe-2e71-429d-ac98-e23d67a6a23d
              - cell "rehearsal 版本 2" [ref=e241]:
                - generic [ref=e242]:
                  - generic [ref=e243]: rehearsal
                  - strong [ref=e244]: 版本 2
              - cell "canary" [ref=e245]
              - cell "historical 当前版本 5" [ref=e250]:
                - generic [ref=e251]:
                  - generic [ref=e252]: historical
                  - generic [ref=e253]: 当前版本 5
              - cell [ref=e254]:
                - generic [ref=e255]:
                  - code [ref=e256]: S 778de32838c9
                  - code [ref=e257]: C b8b1763edca4
              - cell "50%" [ref=e258]
              - cell "S 0 · C 0 · Shadow 0" [ref=e259]
              - cell "2026/11/1 00:00:00" [ref=e260]
      - generic "Policies 游标分页" [ref=e261]:
        - button "上一页" [disabled] [ref=e262]
        - generic [ref=e263]: 第 1 页
        - button "下一页" [disabled] [ref=e264]
      - region "策略版本详情" [ref=e265]:
        - generic [ref=e266]:
          - heading "策略版本详情" [level=3] [ref=e267]
          - link "关闭详情" [ref=e268] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e271]:
          - rowgroup [ref=e272]:
            - row [ref=e273]:
              - rowheader "Deployment" [ref=e274]
              - cell [ref=e275]:
                - code [ref=e277]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
            - row [ref=e278]:
              - rowheader "环境 / 版本" [ref=e279]
              - cell [ref=e280]:
                - generic [ref=e281]:
                  - text: rehearsal · 版本 5
                  - generic [ref=e282]: canary
            - row [ref=e286]:
              - rowheader "当前部署" [ref=e287]
              - cell [ref=e288]:
                - generic [ref=e289]:
                  - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e290] [cursor=pointer]:
                    - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                    - code [ref=e291]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
                  - text: · 当前版本 5
            - row [ref=e292]:
              - rowheader "Stable hash" [ref=e293]
              - cell [ref=e294]:
                - code [ref=e296]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e297]:
              - rowheader "Candidate hash" [ref=e298]
              - cell [ref=e299]:
                - code [ref=e301]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e302]:
              - rowheader "流量 / Cohort" [ref=e303]
              - cell "50% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e304]
            - row [ref=e306]:
              - rowheader "Actor / Reason" [ref=e307]
              - cell "redacted / redacted" [ref=e308]
            - row [ref=e310]:
              - rowheader "创建" [ref=e311]
              - cell "2026/11/2 07:38:43" [ref=e312]
        - paragraph [ref=e313]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e314]
        - generic [ref=e315]:
          - generic [ref=e316]:
            - term [ref=e317]: candidate_min_runs
            - definition [ref=e318]: "20"
          - generic [ref=e319]:
            - term [ref=e320]: stable_min_runs
            - definition [ref=e321]: "20"
          - generic [ref=e322]:
            - term [ref=e323]: window_max_runs
            - definition [ref=e324]: "50"
          - generic [ref=e325]:
            - term [ref=e326]: commit_failure_rate
            - definition [ref=e327]: "0.05"
          - generic [ref=e328]:
            - term [ref=e329]: terminal_failure_rate
            - definition [ref=e330]: "0.10"
          - generic [ref=e331]:
            - term [ref=e332]: latency_increase_rate
            - definition [ref=e333]: "0.50"
          - generic [ref=e334]:
            - term [ref=e335]: mean_cost_increase_rate
            - definition [ref=e336]: "0.30"
          - generic [ref=e337]:
            - term [ref=e338]: unknown_rate
            - definition [ref=e339]: "0.10"
          - generic [ref=e340]:
            - term [ref=e341]: relative_epsilon
            - definition [ref=e342]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e343]
        - paragraph [ref=e344]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e346]:
          - text: shadow_health
          - generic [ref=e347]: passed
        - table [ref=e357]:
          - rowgroup [ref=e366]:
            - row [ref=e367]:
              - columnheader "Gate" [ref=e368]
              - columnheader "状态" [ref=e369]
              - columnheader "健康来源" [ref=e370]
              - columnheader "样本" [ref=e371]
              - columnheader "成本 USD" [ref=e372]
              - columnheader "Issuer" [ref=e373]
              - columnheader "签发时间" [ref=e374]
          - rowgroup [ref=e375]:
            - row [ref=e376]:
              - cell "campaign_eligibility" [ref=e377]
              - cell "passed" [ref=e378]
              - cell "artifact 资格证据" [ref=e383]
              - cell "21" [ref=e384]
              - cell "1.25000000" [ref=e385]
              - cell "redacted" [ref=e386]
              - cell "2026/10/30 08:00:01" [ref=e387]
            - row [ref=e388]:
              - cell "canary_health" [ref=e389]
              - cell "passed" [ref=e390]
              - cell "本部署窗口 查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee 版本 5 · pass · 来源最新窗口 Window 6c872f478f22af3c528621b9e2d143dbf13f4c4fa1c630ec5cb4e55410d6cf89 2026/11/2 07:38:43" [ref=e395]:
                - generic [ref=e396]:
                  - strong [ref=e397]: 本部署窗口
                  - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e398] [cursor=pointer]:
                    - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                    - code [ref=e399]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
                  - generic [ref=e400]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e401]: Window 6c872f478f22af3c528621b9e2d143dbf13f4c4fa1c630ec5cb4e55410d6cf89
                  - generic [ref=e402]: 2026/11/2 07:38:43
              - cell "20" [ref=e403]
              - cell "0.40000000" [ref=e404]
              - cell "redacted" [ref=e405]
              - cell "2026/11/2 07:38:43" [ref=e406]
            - row [ref=e407]:
              - cell "formal_holdout" [ref=e408]
              - cell "passed" [ref=e409]
              - cell "artifact 资格证据" [ref=e414]
              - cell "23" [ref=e415]
              - cell "1.25000000" [ref=e416]
              - cell "redacted" [ref=e417]
              - cell "2026/10/30 08:00:03" [ref=e418]
            - row [ref=e419]:
              - cell "harness_qualification" [ref=e420]
              - cell "passed" [ref=e421]
              - cell "artifact 资格证据" [ref=e426]
              - cell "24" [ref=e427]
              - cell "1.25000000" [ref=e428]
              - cell "redacted" [ref=e429]
              - cell "2026/10/30 08:00:04" [ref=e430]
            - row [ref=e431]:
              - cell "judge_calibration" [ref=e432]
              - cell "passed" [ref=e433]
              - cell "artifact 资格证据" [ref=e438]
              - cell "22" [ref=e439]
              - cell "1.25000000" [ref=e440]
              - cell "redacted" [ref=e441]
              - cell "2026/10/30 08:00:02" [ref=e442]
            - row [ref=e443]:
              - cell "shadow_health" [ref=e444]
              - cell "passed" [ref=e445]
              - cell "已消费前序证据（非本部署新观测） 查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2 版本 4 · pass · 来源最新窗口 Window c9b681ede44d053cd72e08dc52b6f8ae05af5976d186385d6c0450ef2ada4603 2026/11/2 07:38:43" [ref=e450]:
                - generic [ref=e451]:
                  - strong [ref=e452]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 ca47198b-1dd7-4952-a136-3fd199e945e2" [ref=e453] [cursor=pointer]:
                    - /url: "#/policies/ca47198b-1dd7-4952-a136-3fd199e945e2"
                    - code [ref=e454]: ca47198b-1dd7-4952-a136-3fd199e945e2
                  - generic [ref=e455]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e456]: Window c9b681ede44d053cd72e08dc52b6f8ae05af5976d186385d6c0450ef2ada4603
                  - generic [ref=e457]: 2026/11/2 07:38:43
              - cell "20" [ref=e458]
              - cell "0.40000000" [ref=e459]
              - cell "redacted" [ref=e460]
              - cell "2026/11/2 07:38:43" [ref=e461]
        - heading "最新健康窗口" [level=3] [ref=e462]
        - paragraph [ref=e463]:
          - generic [ref=e464]: pass
          - text: 2026/11/2 07:38:43 · 指标协议 v1
        - paragraph [ref=e468]: 触发阈值：无。未知指标保持未知，不作为零值。
        - table [ref=e475]:
          - rowgroup [ref=e480]:
            - row [ref=e481]:
              - columnheader "指标" [ref=e482]
              - columnheader "Candidate" [ref=e483]
              - columnheader "Stable" [ref=e484]
          - rowgroup [ref=e485]:
            - row [ref=e486]:
              - cell "run_count" [ref=e487]
              - cell "20" [ref=e488]
              - cell "20" [ref=e489]
            - row [ref=e490]:
              - cell "commit_failure_rate" [ref=e491]
              - cell "0" [ref=e492]
              - cell "0" [ref=e493]
            - row [ref=e494]:
              - cell "terminal_failure_rate" [ref=e495]
              - cell "0" [ref=e496]
              - cell "0" [ref=e497]
            - row [ref=e498]:
              - cell "p95_latency" [ref=e499]
              - cell "1.000000" [ref=e500]
              - cell "1.000000" [ref=e501]
            - row [ref=e502]:
              - cell "mean_cost" [ref=e503]
              - cell "0.01000000" [ref=e504]
              - cell "0.01000000" [ref=e505]
            - row [ref=e506]:
              - cell "structured_decision_count" [ref=e507]
              - cell "200" [ref=e508]
              - cell "200" [ref=e509]
            - row [ref=e510]:
              - cell "unknown_decision_count" [ref=e511]
              - cell "0" [ref=e512]
              - cell "0" [ref=e513]
            - row [ref=e514]:
              - cell "unknown_rate" [ref=e515]
              - cell "0" [ref=e516]
              - cell "0" [ref=e517]
            - row [ref=e518]:
              - cell "fault_injected_count" [ref=e519]
              - cell "0" [ref=e520]
              - cell "0" [ref=e521]
            - row [ref=e522]:
              - cell "injected_commit_failure_count" [ref=e523]
              - cell "0" [ref=e524]
              - cell "0" [ref=e525]
            - row [ref=e526]:
              - cell "natural_failure_count" [ref=e527]
              - cell "0" [ref=e528]
              - cell "0" [ref=e529]
            - row [ref=e530]:
              - cell "latency_increase_rate" [ref=e531]
              - cell "0" [ref=e532]
              - cell "未知" [ref=e533]
            - row [ref=e534]:
              - cell "mean_cost_increase_rate" [ref=e535]
              - cell "0" [ref=e536]
              - cell "未知" [ref=e537]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e538]
        - list [ref=e539]:
          - listitem [ref=e540]:
            - generic [ref=e548]:
              - strong [ref=e549]: promotion_transitioned
              - generic [ref=e550]: shadow → canary
              - generic [ref=e551]: 2026/11/2 07:38:43 · rehearsal
              - link "查看策略 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee" [ref=e552] [cursor=pointer]:
                - /url: "#/policies/58ce9bbf-6a52-457b-a63b-1e0ea3c11bee"
                - code [ref=e553]: 58ce9bbf-6a52-457b-a63b-1e0ea3c11bee
              - generic [ref=e554]: "actor: redacted · reason: redacted"
        - paragraph [ref=e555]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
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