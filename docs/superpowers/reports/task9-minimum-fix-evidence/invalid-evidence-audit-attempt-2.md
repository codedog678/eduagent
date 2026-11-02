# Invalid Evidence Audit Attempt 2

Command: `finish_audit.py audit audit-corrected` in the same environment as
invalid-evidence-audit-attempt.md.
Tool command ID: 1c1146ff4ae063f356bf7f70836c8fc6; exit 1.
Failure occurred in bookkeeping, not product execution:

```text
Traceback (most recent call last):
  File "/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb/finish_audit.py", line 285, in <module>
    {"dependencies": dependencies, "audit": audit, "cleanup": cleanup}[sys.argv[1]]()
  File "/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb/finish_audit.py", line 136, in audit
    assert after.is_file(), before.name
           ^^^^^^^^^^^^^^^
AssertionError: audit-corrected-before.json
```

The current snapshot label was overwritten by an XML/paired-loop local variable,
so the in-progress snapshot was not excluded from already-complete pairs.
Correction: use a distinct snapshot_label.
Before/after snapshots retained; no source or index change and no model calls.
Next audit uses a new label audit-final.
