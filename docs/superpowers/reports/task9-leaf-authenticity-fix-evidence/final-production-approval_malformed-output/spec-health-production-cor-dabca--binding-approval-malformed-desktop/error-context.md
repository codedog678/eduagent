# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding approval_malformed
- Location: live-e2e/spec-health.spec.ts:14:1

# Error details

```
Error: invalid latest approval or broken audit must not borrow older green consumption

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 44

- Array []
+ Array [
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "df220b649aba7ff4439fb5559daf90db38b1d3a2c937a067669381d7653c91f7",
+     "gate_type": "canary_health",
+     "health_source": Object {
+       "deployment_id": "297e333a-2ed7-48c1-bd05-826ae1606e38",
+       "deployment_version": 5,
+       "evaluated_at": "2026-11-02T06:21:05.397588Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2",
+     },
+     "issued_at": "2026-11-02T06:21:05.397588Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "26f116c3-d12a-4521-80b5-d84acd772e90",
+     "sample_count": 20,
+     "status": "passed",
+   },
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "935e0fba6090279dd3cd511853acf4241c63cd93d621547b1dc3d81cf4d81e60",
+     "gate_type": "shadow_health",
+     "health_source": Object {
+       "deployment_id": "4e3e4706-a5d5-4dff-9cde-c51e0ca0da66",
+       "deployment_version": 4,
+       "evaluated_at": "2026-11-02T06:21:05.281617Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7",
+     },
+     "issued_at": "2026-11-02T06:21:05.281617Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "05e7ba74-7936-46b2-b393-de429d002169",
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
                - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                  - code [ref=e120]: d21ce845-a939-4a30-a589-1713e1667512
              - cell "rehearsal 版本 6" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 6
              - cell "active" [ref=e125]
              - cell "current 当前版本 6" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: current
                  - generic [ref=e133]: 当前版本 6
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S 778de32838c9
                  - code [ref=e137]: C 2537b3d6216e
              - cell "100%" [ref=e138]
              - cell "S 0 · C 0 · Shadow 0" [ref=e139]
              - cell "2026/11/2 06:21:05" [ref=e140]
            - row [ref=e141]:
              - cell [ref=e142]:
                - link "查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38" [ref=e143] [cursor=pointer]:
                  - /url: "#/policies/297e333a-2ed7-48c1-bd05-826ae1606e38"
                  - code [ref=e144]: 297e333a-2ed7-48c1-bd05-826ae1606e38
              - cell "rehearsal 版本 5" [ref=e145]:
                - generic [ref=e146]:
                  - generic [ref=e147]: rehearsal
                  - strong [ref=e148]: 版本 5
              - cell "canary" [ref=e149]
              - cell "historical 当前版本 6" [ref=e154]:
                - generic [ref=e155]:
                  - generic [ref=e156]: historical
                  - generic [ref=e157]: 当前版本 6
              - cell [ref=e158]:
                - generic [ref=e159]:
                  - code [ref=e160]: S 778de32838c9
                  - code [ref=e161]: C 2537b3d6216e
              - cell "50%" [ref=e162]
              - cell "S 0 · C 0 · Shadow 0" [ref=e163]
              - cell "2026/11/2 06:21:05" [ref=e164]
            - row [ref=e165]:
              - cell [ref=e166]:
                - link "查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66" [ref=e167] [cursor=pointer]:
                  - /url: "#/policies/4e3e4706-a5d5-4dff-9cde-c51e0ca0da66"
                  - code [ref=e168]: 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66
              - cell "rehearsal 版本 4" [ref=e169]:
                - generic [ref=e170]:
                  - generic [ref=e171]: rehearsal
                  - strong [ref=e172]: 版本 4
              - cell "shadow" [ref=e173]
              - cell "historical 当前版本 6" [ref=e178]:
                - generic [ref=e179]:
                  - generic [ref=e180]: historical
                  - generic [ref=e181]: 当前版本 6
              - cell [ref=e182]:
                - generic [ref=e183]:
                  - code [ref=e184]: S 778de32838c9
                  - code [ref=e185]: C 2537b3d6216e
              - cell "0%" [ref=e186]
              - cell "S 0 · C 0 · Shadow 0" [ref=e187]
              - cell "2026/11/2 06:21:05" [ref=e188]
            - row [ref=e189]:
              - cell [ref=e190]:
                - link "查看策略 3209df6e-86d8-4fa1-b381-026cebd9302e" [ref=e191] [cursor=pointer]:
                  - /url: "#/policies/3209df6e-86d8-4fa1-b381-026cebd9302e"
                  - code [ref=e192]: 3209df6e-86d8-4fa1-b381-026cebd9302e
              - cell "rehearsal 版本 3" [ref=e193]:
                - generic [ref=e194]:
                  - generic [ref=e195]: rehearsal
                  - strong [ref=e196]: 版本 3
              - cell "registered" [ref=e197]
              - cell "historical 当前版本 6" [ref=e202]:
                - generic [ref=e203]:
                  - generic [ref=e204]: historical
                  - generic [ref=e205]: 当前版本 6
              - cell [ref=e206]:
                - generic [ref=e207]:
                  - code [ref=e208]: S 778de32838c9
                  - code [ref=e209]: C 2537b3d6216e
              - cell "0%" [ref=e210]
              - cell "S 0 · C 0 · Shadow 0" [ref=e211]
              - cell "2026/11/2 06:21:05" [ref=e212]
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
              - cell "historical 当前版本 6" [ref=e226]:
                - generic [ref=e227]:
                  - generic [ref=e228]: historical
                  - generic [ref=e229]: 当前版本 6
              - cell [ref=e230]:
                - generic [ref=e231]:
                  - code [ref=e232]: S 778de32838c9
                  - code [ref=e233]: C 不可用
              - cell "0%" [ref=e234]
              - cell "S 0 · C 0 · Shadow 0" [ref=e235]
              - cell "2026/11/2 06:21:05" [ref=e236]
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
              - cell "2026/11/2 06:21:05" [ref=e260]
            - row [ref=e261]:
              - cell [ref=e262]:
                - link "查看策略 ee895571-0ac5-41f9-a73f-cb5360af7252" [ref=e263] [cursor=pointer]:
                  - /url: "#/policies/ee895571-0ac5-41f9-a73f-cb5360af7252"
                  - code [ref=e264]: ee895571-0ac5-41f9-a73f-cb5360af7252
              - cell "rehearsal 版本 2" [ref=e265]:
                - generic [ref=e266]:
                  - generic [ref=e267]: rehearsal
                  - strong [ref=e268]: 版本 2
              - cell "canary" [ref=e269]
              - cell "historical 当前版本 6" [ref=e274]:
                - generic [ref=e275]:
                  - generic [ref=e276]: historical
                  - generic [ref=e277]: 当前版本 6
              - cell [ref=e278]:
                - generic [ref=e279]:
                  - code [ref=e280]: S 778de32838c9
                  - code [ref=e281]: C 97689ad93155
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
                - code [ref=e301]: d21ce845-a939-4a30-a589-1713e1667512
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
                  - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e314] [cursor=pointer]:
                    - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                    - code [ref=e315]: d21ce845-a939-4a30-a589-1713e1667512
                  - text: · 当前版本 6
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
              - cell "2026/11/2 06:21:05" [ref=e336]
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
            - text: shadow_health
            - generic [ref=e371]: passed
          - generic [ref=e375]:
            - text: canary_health
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
              - cell "已消费前序证据（非本部署新观测） 查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38 版本 5 · pass · 来源最新窗口 Window a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2 2026/11/2 06:21:05" [ref=e429]:
                - generic [ref=e430]:
                  - strong [ref=e431]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38" [ref=e432] [cursor=pointer]:
                    - /url: "#/policies/297e333a-2ed7-48c1-bd05-826ae1606e38"
                    - code [ref=e433]: 297e333a-2ed7-48c1-bd05-826ae1606e38
                  - generic [ref=e434]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e435]: Window a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2
                  - generic [ref=e436]: 2026/11/2 06:21:05
              - cell "20" [ref=e437]
              - cell "0.40000000" [ref=e438]
              - cell "redacted" [ref=e439]
              - cell "2026/11/2 06:21:05" [ref=e440]
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
              - cell "20" [ref=e485]
              - cell "0E-8" [ref=e486]
              - cell "redacted" [ref=e487]
              - cell "2026/11/2 06:21:05" [ref=e488]
            - row [ref=e489]:
              - cell "shadow_health" [ref=e490]
              - cell "passed" [ref=e491]
              - cell "已消费前序证据（非本部署新观测） 查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66 版本 4 · pass · 来源最新窗口 Window b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7 2026/11/2 06:21:05" [ref=e496]:
                - generic [ref=e497]:
                  - strong [ref=e498]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66" [ref=e499] [cursor=pointer]:
                    - /url: "#/policies/4e3e4706-a5d5-4dff-9cde-c51e0ca0da66"
                    - code [ref=e500]: 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66
                  - generic [ref=e501]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e502]: Window b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7
                  - generic [ref=e503]: 2026/11/2 06:21:05
              - cell "20" [ref=e504]
              - cell "0.40000000" [ref=e505]
              - cell "redacted" [ref=e506]
              - cell "2026/11/2 06:21:05" [ref=e507]
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
              - generic [ref=e531]: 2026/11/2 06:21:05 · rehearsal
              - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e532] [cursor=pointer]:
                - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                - code [ref=e533]: d21ce845-a939-4a30-a589-1713e1667512
              - generic [ref=e534]: "actor: redacted · reason: redacted"
        - paragraph [ref=e535]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
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
  47  |   if (info.project.name === 'mobile' && scenario !== 'current') {
  48  |     const table = detail.locator('.ant-table-content').first()
  49  |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  50  |     await table.hover()
  51  |     await page.mouse.wheel(1100, 0)
  52  |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
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
  96  |   } else if (scenario.startsWith('leaf_')) {
  97  |     const gate = scenario === 'leaf_shadow_valid' ? 'shadow_health' : 'canary_health'
  98  |     const ownLeaf = health.find((r: { gate_type: string }) => r.gate_type === gate)
  99  |     expect(fixture.leaf_proof.authority_accepts).toBe(validLocal || validChain)
  100 |     if (validLocal || validChain) {
  101 |       expect(ownLeaf.receipt_id).toBe(fixture.leaf_proof.receipt_id)
  102 |       expect(ownLeaf.health_source.relation).toBe(validLocal ? 'local' : 'consumed_chain')
  103 |       expect(health).toHaveLength(scenario === 'leaf_shadow_valid' ? 1 : 2)
  104 |     } else if (scenario === 'leaf_local_bad') {
  105 |       expect(ownLeaf).toBeUndefined()
  106 |       expect(health).toHaveLength(1)
  107 |       expect(health[0].gate_type).toBe('shadow_health')
  108 |       expect(health[0].health_source.relation).toBe('consumed_chain')
  109 |     } else {
  110 |       expect(health).toEqual([])
  111 |       await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  112 |     }
  113 |   } else if (validChain) {
  114 |     expect(health).toHaveLength(2)
  115 |     expect(health.every((r: { status: string; health_source: { relation: string } }) =>
  116 |       r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  117 |   } else {
> 118 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
      |                                                                                                       ^ Error: invalid latest approval or broken audit must not borrow older green consumption
  119 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  120 |   }
  121 | })
  122 | 
```