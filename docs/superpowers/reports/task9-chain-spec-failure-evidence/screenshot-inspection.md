# Actual Screenshot Inspection

The following 17 OWN screenshots were opened with view_image during this review.
Archive PNG hashes were checked separately; this does not claim every archived PNG was visually inspected.

| OWN screenshots | Count | Observed |
| --- | --- | --- |
| screenshots/policies-{desktop,mobile}.png | 2 | Filters/table/detail in existing Ops layout; responsive table rather than document-wide overflow. |
| screenshots/policy-trace-{desktop,mobile}.png | 2 | Stored binding and links remain visible; no promotion mutation control. |
| screenshots/detail-current-{desktop,mobile}-left.png | 2 | Current hold does not present another deployment's passed health source. |
| screenshots/detail-history-{desktop,mobile}-left.png | 2 | Old local receipt/window remains associated with the old deployment. |
| screenshots/detail-approval_malformed_latest-{desktop,mobile}-left.png | 2 | Raw approval passed may remain visible; health source is unknown, not consumed. |
| screenshots/detail-genuine_malformed_latest_valid-{desktop,mobile}-left.png | 2 | Genuine malformed latest masks old consumption; unknown health-source display. |
| screenshots/detail-genuine_valid-{desktop,mobile}-left.png | 2 | Both valid consumed health sources shown. |
| screenshots/detail-referenced_canary_poison-{desktop,mobile}-left.png | 2 | Canary health unknown while Shadow still passed/consumed: matches API and failing correctness assertion. |
| screenshots/detail-referenced_canary_poison-mobile.png | 1 | Actual table horizontal scroll with body overflow <= 1; right columns shown. |

Desktop section/full-page capture can place a sticky header over a mid-page row.
This is not reported as a product defect. Mobile table clipping before horizontal scrolling is expected.
Network assertions and screenshots are complementary; no correctness PASS was assigned merely for obtaining a screenshot.
