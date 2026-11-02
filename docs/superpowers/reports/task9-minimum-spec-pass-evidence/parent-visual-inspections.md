父侧于2026-11-02实际使用view_image查看本轮原始四张图片：

- screenshots/detail-prod-final-minimum-zero-desktop-left.png
- screenshots/detail-prod-final-minimum-zero-mobile-left.png
- screenshots/detail-prod-final-genuine-valid-desktop-left.png
- screenshots/detail-prod-final-genuine-valid-mobile-left.png

零样本详情的canary_health/shadow_health为unknown，无绿色健康来源行；
合法详情保留两个consumed_chain来源，标注来源版本、window和时间。
冻结candidate_min_runs/stable_min_runs均显示20；Actor/Reason已redacted。
mobile宽表只显示部分列，实际横滚证据由本轮JSON/trace提供，
不把截图当成所有列同时可见或初始scrollLeft=0的证明。
合法desktop的sticky header部分遮挡行属于本次取景状态。

四张图片的原字节SHA已由parent-retain.py核对
independent-execution-audit.json.actual_visual_inspections；
父侧仅认领本文件四张检查，不认领SPEC reviewer其余14张检查。
