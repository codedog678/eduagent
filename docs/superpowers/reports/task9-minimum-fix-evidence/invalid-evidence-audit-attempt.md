# Invalid Evidence Audit Attempt

Role: fix implementer evidence bookkeeping; not a product regression failure.
Command:
`env PYTHONDONTWRITEBYTECODE=1 TASK9_MATRIX_SNAPSHOT=final-snapshot.json /tmp/eduagent-m3-patched-runtime/bin/python /tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb/finish_audit.py audit`

Tool command ID: 5131956d37600ddd5bd74c61842dc87f; exit 1.
No product source/index mutation or model requests.
Protected snapshot: audit-before.json; audit-after.json completed after diagnosis.

Original output:

```text
Traceback (most recent call last):
  File "/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb/finish_audit.py", line 282, in <module>
    {"dependencies": dependencies, "audit": audit, "cleanup": cleanup}[sys.argv[1]]()
  File "/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb/finish_audit.py", line 150, in audit
    assert not body["errors"] and body["overflow"] <= 1
               ~~~~^^^^^^^^^^
TypeError: list indices must be integers or slices, not str
```

Cause: `production-*.json` also matches the production-batch.json list, which
is not a per-viewport page record.
Correction: select only `-desktop.json` and `-mobile.json` records.
Fresh audit label: audit-corrected. Existing raw attempts are not overwritten.
