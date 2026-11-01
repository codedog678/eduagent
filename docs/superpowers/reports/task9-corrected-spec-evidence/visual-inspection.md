# Independent Visual Inspection

Reviewer: fresh full Task9 SPEC, HEAD e29bdb4.

- Desktop 1440x900 and mobile 390x844 are Chromium desktop emulation viewports.
- Actual production dist served on 33291, real PostgreSQL 55432, no route mocks
  in live tests. Page HTTP assets were independently compared byte-for-byte with
  the built dist and hashed in production-http*.json.
- Gate detail failed: desktop/mobile both show red failed for formal_holdout.
- Gate detail unknown: desktop/mobile both show neutral unknown for formal_holdout.
- Neither F1 page shows the replaced green passed receipt.
- Full-page live failed/unknown screenshots inspected for navigation/layout;
  detailed element screenshots inspected to avoid downscaled long-table text.
- Live policy mobile inspected: status tooltip, redacted actor/reason, 50% traffic,
  exact old/current deployment, candidate/stable metrics and rollback relations.
- Live Trace mobile inspected: old candidate, rehearsal, full immutable hash and
  old deployment link, no raw namespace.
- Old/new Run drawer screenshots inspected in both viewports: candidate/stable
  and their distinct full hash/deployment binding. Additional two unknown live
  executions captured legible drawer images; full-page v1 images were retained.
- Mocked UI policies desktop and Ops mobile screenshots inspected for compact
  layout, status/metrics, scrollbar accommodation and no nested cards.
- Mobile tables intentionally scroll horizontally; hash fields wrap.
- No blocking visual defect found. Long full-page screenshots are downscaled
  by the image viewer; legible detail/drawer screenshots are the primary evidence.
- v1 fresh-live.spec.ts was preserved as fresh-live-v1.spec.ts after a screenshot-
  only tmp adjustment. Product code, frozen tests and golden evidence unchanged.
