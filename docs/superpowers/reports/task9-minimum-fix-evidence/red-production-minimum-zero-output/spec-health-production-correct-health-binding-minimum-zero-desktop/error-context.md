# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding minimum_zero
- Location: live-e2e/spec-health.spec.ts:13:1

# Error details

```
Error: invalid latest approval or broken audit must not borrow older green consumption

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 44

- Array []
+ Array [
+   Object {
+     "cost": "0E-8",
+     "evidence_hash": "3af9b5dff29d77b599171da82df02d6e0c7e044c4fac80677cf348bc2d100874",
+     "gate_type": "canary_health",
+     "health_source": Object {
+       "deployment_id": "bba9cce9-1037-4281-bed1-264b21ddb335",
+       "deployment_version": 5,
+       "evaluated_at": "2026-11-02T03:25:00.310407Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "eabbbc00753ba76a13ffb64311c0ff781c3fe360d7995579cb2d1b74d4c8bb35",
+     },
+     "issued_at": "2026-11-02T03:25:00.310407Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "db6b16fc-00f2-4565-bb62-9d141923b160",
+     "sample_count": 0,
+     "status": "passed",
+   },
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "c28f7f5118c89b68db10ed5c575f6f2fb0e8f7fcb6172f1ca583c5d4dc428d7a",
+     "gate_type": "shadow_health",
+     "health_source": Object {
+       "deployment_id": "3a937b27-98f6-4c73-b561-2ed047ebea71",
+       "deployment_version": 4,
+       "evaluated_at": "2026-11-02T03:25:00.191475Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "b2c813c2d9eb06b56b7e3f5d36e20a42d7fd6eacbdd31a5cbdfa64bf50625ea2",
+     },
+     "issued_at": "2026-11-02T03:25:00.191475Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "97623d9a-801d-4d19-9e91-e5398e672cc3",
+     "sample_count": 20,
+     "status": "passed",
+   },
+ ]
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
                - link "查看策略 fccb3767-67c9-4bae-af52-1b64bc6d9871" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/fccb3767-67c9-4bae-af52-1b64bc6d9871"
                  - code [ref=e120]: fccb3767-67c9-4bae-af52-1b64bc6d9871
              - cell "rehearsal 版本 6" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 6
              - cell "active" [ref=e125]
              - cell "historical 当前版本 5" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: historical
                  - generic [ref=e133]: 当前版本 5
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S 778de32838c9
                  - code [ref=e137]: C 2537b3d6216e
              - cell "100%" [ref=e138]
              - cell "S 0 · C 0 · Shadow 0" [ref=e139]
              - cell "2026/11/2 03:25:00" [ref=e140]
            - row [ref=e141]:
              - cell [ref=e142]:
                - link "查看策略 bba9cce9-1037-4281-bed1-264b21ddb335" [ref=e143] [cursor=pointer]:
                  - /url: "#/policies/bba9cce9-1037-4281-bed1-264b21ddb335"
                  - code [ref=e144]: bba9cce9-1037-4281-bed1-264b21ddb335
              - cell "rehearsal 版本 5" [ref=e145]:
                - generic [ref=e146]:
                  - generic [ref=e147]: rehearsal
                  - strong [ref=e148]: 版本 5
              - cell "canary" [ref=e149]
              - cell "current 当前版本 5" [ref=e154]:
                - generic [ref=e155]:
                  - generic [ref=e156]: current
                  - generic [ref=e157]: 当前版本 5
              - cell [ref=e158]:
                - generic [ref=e159]:
                  - code [ref=e160]: S 778de32838c9
                  - code [ref=e161]: C 2537b3d6216e
              - cell "50%" [ref=e162]
              - cell "S 0 · C 0 · Shadow 0" [ref=e163]
              - cell "2026/11/2 03:25:00" [ref=e164]
            - row [ref=e165]:
              - cell [ref=e166]:
                - link "查看策略 3a937b27-98f6-4c73-b561-2ed047ebea71" [ref=e167] [cursor=pointer]:
                  - /url: "#/policies/3a937b27-98f6-4c73-b561-2ed047ebea71"
                  - code [ref=e168]: 3a937b27-98f6-4c73-b561-2ed047ebea71
              - cell "rehearsal 版本 4" [ref=e169]:
                - generic [ref=e170]:
                  - generic [ref=e171]: rehearsal
                  - strong [ref=e172]: 版本 4
              - cell "shadow" [ref=e173]
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
              - cell "2026/11/2 03:25:00" [ref=e188]
            - row [ref=e189]:
              - cell [ref=e190]:
                - link "查看策略 333e6d49-8cbb-44c6-9871-b2b2074fda52" [ref=e191] [cursor=pointer]:
                  - /url: "#/policies/333e6d49-8cbb-44c6-9871-b2b2074fda52"
                  - code [ref=e192]: 333e6d49-8cbb-44c6-9871-b2b2074fda52
              - cell "rehearsal 版本 3" [ref=e193]:
                - generic [ref=e194]:
                  - generic [ref=e195]: rehearsal
                  - strong [ref=e196]: 版本 3
              - cell "registered" [ref=e197]
              - cell "historical 当前版本 5" [ref=e202]:
                - generic [ref=e203]:
                  - generic [ref=e204]: historical
                  - generic [ref=e205]: 当前版本 5
              - cell [ref=e206]:
                - generic [ref=e207]:
                  - code [ref=e208]: S 778de32838c9
                  - code [ref=e209]: C 2537b3d6216e
              - cell "0%" [ref=e210]
              - cell "S 0 · C 0 · Shadow 0" [ref=e211]
              - cell "2026/11/2 03:25:00" [ref=e212]
            - row [ref=e213]:
              - cell [ref=e214]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e215] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e216]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e217]:
                - generic [ref=e218]:
                  - generic [ref=e219]: rehearsal
                  - strong [ref=e220]: 版本 1
              - cell "registered" [ref=e221]
              - cell "historical 当前版本 5" [ref=e226]:
                - generic [ref=e227]:
                  - generic [ref=e228]: historical
                  - generic [ref=e229]: 当前版本 5
              - cell [ref=e230]:
                - generic [ref=e231]:
                  - code [ref=e232]: S 778de32838c9
                  - code [ref=e233]: C 不可用
              - cell "0%" [ref=e234]
              - cell "S 0 · C 0 · Shadow 0" [ref=e235]
              - cell "2026/11/2 03:25:00" [ref=e236]
            - row [ref=e237]:
              - cell [ref=e238]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e239] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e240]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e241]:
                - generic [ref=e242]:
                  - generic [ref=e243]: production
                  - strong [ref=e244]: 版本 1
              - cell "registered" [ref=e245]
              - cell "current 当前版本 1" [ref=e250]:
                - generic [ref=e251]:
                  - generic [ref=e252]: current
                  - generic [ref=e253]: 当前版本 1
              - cell [ref=e254]:
                - generic [ref=e255]:
                  - code [ref=e256]: S 778de32838c9
                  - code [ref=e257]: C 不可用
              - cell "0%" [ref=e258]
              - cell "S 60 · C 0 · Shadow 0" [ref=e259]
              - cell "2026/11/2 03:25:00" [ref=e260]
            - row [ref=e261]:
              - cell [ref=e262]:
                - link "查看策略 21b0da3b-28d6-44a6-9141-d00325c9e950" [ref=e263] [cursor=pointer]:
                  - /url: "#/policies/21b0da3b-28d6-44a6-9141-d00325c9e950"
                  - code [ref=e264]: 21b0da3b-28d6-44a6-9141-d00325c9e950
              - cell "rehearsal 版本 2" [ref=e265]:
                - generic [ref=e266]:
                  - generic [ref=e267]: rehearsal
                  - strong [ref=e268]: 版本 2
              - cell "canary" [ref=e269]
              - cell "historical 当前版本 5" [ref=e274]:
                - generic [ref=e275]:
                  - generic [ref=e276]: historical
                  - generic [ref=e277]: 当前版本 5
              - cell [ref=e278]:
                - generic [ref=e279]:
                  - code [ref=e280]: S 778de32838c9
                  - code [ref=e281]: C a8413bc070db
              - cell "50%" [ref=e282]
              - cell "S 0 · C 0 · Shadow 0" [ref=e283]
              - cell "2026/11/1 00:00:00" [ref=e284]
      - generic "Policies 游标分页" [ref=e285]:
        - button "上一页" [disabled] [ref=e286]
        - generic [ref=e287]: 第 1 页
        - button "下一页" [disabled] [ref=e288]
      - region "策略版本详情" [ref=e289]:
        - generic [ref=e290]:
          - heading "策略版本详情" [level=3] [ref=e291]
          - link "关闭详情" [ref=e292] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e295]:
          - rowgroup [ref=e296]:
            - row [ref=e297]:
              - rowheader "Deployment" [ref=e298]
              - cell [ref=e299]:
                - code [ref=e301]: fccb3767-67c9-4bae-af52-1b64bc6d9871
            - row [ref=e302]:
              - rowheader "环境 / 版本" [ref=e303]
              - cell [ref=e304]:
                - generic [ref=e305]:
                  - text: rehearsal · 版本 6
                  - generic [ref=e306]: active
            - row [ref=e310]:
              - rowheader "当前部署" [ref=e311]
              - cell [ref=e312]:
                - generic [ref=e313]:
                  - link "查看策略 bba9cce9-1037-4281-bed1-264b21ddb335" [ref=e314] [cursor=pointer]:
                    - /url: "#/policies/bba9cce9-1037-4281-bed1-264b21ddb335"
                    - code [ref=e315]: bba9cce9-1037-4281-bed1-264b21ddb335
                  - text: · 当前版本 5
            - row [ref=e316]:
              - rowheader "Stable hash" [ref=e317]
              - cell [ref=e318]:
                - code [ref=e320]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e321]:
              - rowheader "Candidate hash" [ref=e322]
              - cell [ref=e323]:
                - code [ref=e325]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e326]:
              - rowheader "流量 / Cohort" [ref=e327]
              - cell "100% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e328]
            - row [ref=e330]:
              - rowheader "Actor / Reason" [ref=e331]
              - cell "redacted / redacted" [ref=e332]
            - row [ref=e334]:
              - rowheader "创建" [ref=e335]
              - cell "2026/11/2 03:25:00" [ref=e336]
        - paragraph [ref=e337]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e338]
        - generic [ref=e339]:
          - generic [ref=e340]:
            - term [ref=e341]: candidate_min_runs
            - definition [ref=e342]: "20"
          - generic [ref=e343]:
            - term [ref=e344]: stable_min_runs
            - definition [ref=e345]: "20"
          - generic [ref=e346]:
            - term [ref=e347]: window_max_runs
            - definition [ref=e348]: "50"
          - generic [ref=e349]:
            - term [ref=e350]: commit_failure_rate
            - definition [ref=e351]: "0.05"
          - generic [ref=e352]:
            - term [ref=e353]: terminal_failure_rate
            - definition [ref=e354]: "0.10"
          - generic [ref=e355]:
            - term [ref=e356]: latency_increase_rate
            - definition [ref=e357]: "0.50"
          - generic [ref=e358]:
            - term [ref=e359]: mean_cost_increase_rate
            - definition [ref=e360]: "0.30"
          - generic [ref=e361]:
            - term [ref=e362]: unknown_rate
            - definition [ref=e363]: "0.10"
          - generic [ref=e364]:
            - term [ref=e365]: relative_epsilon
            - definition [ref=e366]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e367]
        - paragraph [ref=e368]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e369]:
          - generic [ref=e370]:
            - text: canary_health
            - generic [ref=e371]: passed
          - generic [ref=e375]:
            - text: shadow_health
            - generic [ref=e376]: passed
          - generic [ref=e380]:
            - text: promotion_approval
            - generic [ref=e381]: passed
        - table [ref=e391]:
          - rowgroup [ref=e400]:
            - row [ref=e401]:
              - columnheader "Gate" [ref=e402]
              - columnheader "状态" [ref=e403]
              - columnheader "健康来源" [ref=e404]
              - columnheader "样本" [ref=e405]
              - columnheader "成本 USD" [ref=e406]
              - columnheader "Issuer" [ref=e407]
              - columnheader "签发时间" [ref=e408]
          - rowgroup [ref=e409]:
            - row [ref=e410]:
              - cell "campaign_eligibility" [ref=e411]
              - cell "passed" [ref=e412]
              - cell "artifact 资格证据" [ref=e417]
              - cell "21" [ref=e418]
              - cell "1.25000000" [ref=e419]
              - cell "redacted" [ref=e420]
              - cell "2026/10/30 08:00:01" [ref=e421]
            - row [ref=e422]:
              - cell "canary_health" [ref=e423]
              - cell "passed" [ref=e424]
              - cell "已消费前序证据（非本部署新观测） 查看策略 bba9cce9-1037-4281-bed1-264b21ddb335 版本 5 · pass · 来源最新窗口 Window eabbbc00753ba76a13ffb64311c0ff781c3fe360d7995579cb2d1b74d4c8bb35 2026/11/2 03:25:00" [ref=e429]:
                - generic [ref=e430]:
                  - strong [ref=e431]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 bba9cce9-1037-4281-bed1-264b21ddb335" [ref=e432] [cursor=pointer]:
                    - /url: "#/policies/bba9cce9-1037-4281-bed1-264b21ddb335"
                    - code [ref=e433]: bba9cce9-1037-4281-bed1-264b21ddb335
                  - generic [ref=e434]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e435]: Window eabbbc00753ba76a13ffb64311c0ff781c3fe360d7995579cb2d1b74d4c8bb35
                  - generic [ref=e436]: 2026/11/2 03:25:00
              - cell "0" [ref=e437]
              - cell "0E-8" [ref=e438]
              - cell "redacted" [ref=e439]
              - cell "2026/11/2 03:25:00" [ref=e440]
            - row [ref=e441]:
              - cell "formal_holdout" [ref=e442]
              - cell "passed" [ref=e443]
              - cell "artifact 资格证据" [ref=e448]
              - cell "23" [ref=e449]
              - cell "1.25000000" [ref=e450]
              - cell "redacted" [ref=e451]
              - cell "2026/10/30 08:00:03" [ref=e452]
            - row [ref=e453]:
              - cell "harness_qualification" [ref=e454]
              - cell "passed" [ref=e455]
              - cell "artifact 资格证据" [ref=e460]
              - cell "24" [ref=e461]
              - cell "1.25000000" [ref=e462]
              - cell "redacted" [ref=e463]
              - cell "2026/10/30 08:00:04" [ref=e464]
            - row [ref=e465]:
              - cell "judge_calibration" [ref=e466]
              - cell "passed" [ref=e467]
              - cell "artifact 资格证据" [ref=e472]
              - cell "22" [ref=e473]
              - cell "1.25000000" [ref=e474]
              - cell "redacted" [ref=e475]
              - cell "2026/10/30 08:00:02" [ref=e476]
            - row [ref=e477]:
              - cell "promotion_approval" [ref=e478]
              - cell "passed" [ref=e479]
              - cell "artifact 资格证据" [ref=e484]
              - cell "0" [ref=e485]
              - cell "0E-8" [ref=e486]
              - cell "redacted" [ref=e487]
              - cell "2026/11/2 03:25:00" [ref=e488]
            - row [ref=e489]:
              - cell "shadow_health" [ref=e490]
              - cell "passed" [ref=e491]
              - cell "已消费前序证据（非本部署新观测） 查看策略 3a937b27-98f6-4c73-b561-2ed047ebea71 版本 4 · pass · 来源最新窗口 Window b2c813c2d9eb06b56b7e3f5d36e20a42d7fd6eacbdd31a5cbdfa64bf50625ea2 2026/11/2 03:25:00" [ref=e496]:
                - generic [ref=e497]:
                  - strong [ref=e498]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 3a937b27-98f6-4c73-b561-2ed047ebea71" [ref=e499] [cursor=pointer]:
                    - /url: "#/policies/3a937b27-98f6-4c73-b561-2ed047ebea71"
                    - code [ref=e500]: 3a937b27-98f6-4c73-b561-2ed047ebea71
                  - generic [ref=e501]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e502]: Window b2c813c2d9eb06b56b7e3f5d36e20a42d7fd6eacbdd31a5cbdfa64bf50625ea2
                  - generic [ref=e503]: 2026/11/2 03:25:00
              - cell "20" [ref=e504]
              - cell "0.40000000" [ref=e505]
              - cell "redacted" [ref=e506]
              - cell "2026/11/2 03:25:00" [ref=e507]
        - heading "最新健康窗口" [level=3] [ref=e508]
        - generic [ref=e509]:
          - img "No data" [ref=e511]
          - generic [ref=e517]: 暂无健康窗口，指标不可用
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e518]
        - list [ref=e519]:
          - listitem [ref=e520]:
            - generic [ref=e528]:
              - strong [ref=e529]: promotion_transitioned
              - generic [ref=e530]: canary → active
              - generic [ref=e531]: 2026/11/2 03:25:00 · rehearsal
              - link "查看策略 fccb3767-67c9-4bae-af52-1b64bc6d9871" [ref=e532] [cursor=pointer]:
                - /url: "#/policies/fccb3767-67c9-4bae-af52-1b64bc6d9871"
                - code [ref=e533]: fccb3767-67c9-4bae-af52-1b64bc6d9871
              - generic [ref=e534]: "actor: redacted · reason: redacted"
        - paragraph [ref=e535]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test'
  2  | import { readFileSync, writeFileSync } from 'node:fs'
  3  | import { createHash } from 'node:crypto'
  4  | import { join } from 'node:path'
  5  | 
  6  | const own = '/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb'
  7  | const scenario = process.env.SPEC_SCENARIO!
  8  | const historical = scenario.startsWith('history')
  9  | const validChain = scenario === 'genuine_valid'
  10 | const tag = process.env.SPEC_RUN_TAG || scenario
  11 | const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${tag}.json`), 'utf8'))
  12 | 
  13 | test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
  14 |   const requests: { method: string; url: string }[] = []
  15 |   const errors: string[] = []
  16 |   page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  17 |   page.on('pageerror', e => errors.push(e.message))
  18 |   page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  19 |   const response = await request.get(`/ops-api/ops/policies/deployments/${fixture.id}`)
  20 |   expect(response.status()).toBe(200)
  21 |   const body = await response.json()
  22 |   await page.goto(`/ops/#/policies/${fixture.id}`)
  23 |   const detail = page.getByRole('region', { name: '策略版本详情' })
  24 |   await expect(detail.getByText(fixture.policy_hash, { exact: true }).first()).toBeVisible()
  25 |   await expect(detail.getByText(/收据是历史证据，不代表可发布资格/)).toBeVisible()
  26 |   const sourceText = await detail.locator('strong').allTextContents()
  27 |   const source = detail.getByText(historical
  28 |     ? '本部署窗口'
  29 |     : '已消费前序证据（非本部署新观测）', { exact: true }).first()
  30 |   if (historical || validChain) {
  31 |     await expect(source).toBeVisible()
  32 |     await source.scrollIntoViewIfNeeded()
  33 |     const box = await source.boundingBox()
  34 |     expect(box).not.toBeNull()
  35 |     expect(box!.x).toBeGreaterThanOrEqual(0)
  36 |     expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  37 |     await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  38 |       animations: 'disabled' })
  39 |   }
  40 |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  41 |     animations: 'disabled' })
  42 |   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  43 |   if (info.project.name === 'mobile' && scenario !== 'current') {
  44 |     const table = detail.locator('.ant-table-content').first()
  45 |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  46 |     await table.hover()
  47 |     await page.mouse.wheel(1100, 0)
  48 |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
  49 |   }
  50 |   const hashes: Record<string, string> = {}
  51 |   for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
  52 |     const asset = await request.get(url)
  53 |     const bytes = await asset.body()
  54 |     expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
  55 |     hashes[url] = createHash('sha256').update(bytes).digest('hex')
  56 |   }
  57 |   expect(Object.keys(hashes).length).toBeGreaterThan(0)
  58 |   expect(requests.every(r => r.method === 'GET')).toBe(true)
  59 |   expect(errors).toEqual([])
  60 |   expect(overflow).toBeLessThanOrEqual(1)
  61 |   await page.screenshot({ path: `${own}/screenshots/production-${tag}-${info.project.name}.png`,
  62 |     fullPage: true, animations: 'disabled' })
  63 |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}.png`,
  64 |     animations: 'disabled' })
  65 |   writeFileSync(`${own}/production-${tag}-${info.project.name}.json`,
  66 |     JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes }, null, 2) + '\n')
  67 |   const health = body.gate_receipts.filter((r: { health_source: unknown }) => r.health_source)
  68 |   if (scenario === 'current') {
  69 |     expect(body.is_current).toBe(true)
  70 |     expect(body.latest_health_window.decision).toBe('hold')
  71 |     expect(health).toEqual([])
  72 |     await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
  73 |   } else if (historical) {
  74 |     expect(body.is_current).toBe(false)
  75 |     expect(health).toHaveLength(1)
  76 |     expect(health[0].receipt_id).toBe(fixture.old_receipt)
  77 |     expect(health[0].health_source.deployment_id).toBe(fixture.old)
  78 |     expect(health[0].health_source.window_id).toBe(fixture.old_window)
  79 |     const newer = await request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  80 |     const newBody = await newer.json()
  81 |     expect(newBody.latest_health_window.decision).toBe('pass')
  82 |     expect(newBody.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
  83 |       .not.toBe(fixture.old_receipt)
  84 |   } else if (validChain) {
  85 |     expect(health).toHaveLength(2)
  86 |     expect(health.every((r: { status: string; health_source: { relation: string } }) =>
  87 |       r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  88 |   } else {
> 89 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
     |                                                                                                       ^ Error: invalid latest approval or broken audit must not borrow older green consumption
  90 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  91 |   }
  92 | })
  93 | 
```