# Defect ledger template (E15.1)

Record each finding as `<GATE>-D<nnn>` (example `G10-D001`). A/B own analyzer
defects; C coordinates corpus evidence. Do not silently delete a finding.

| Field | Value |
|---|---|
| ID | `<GATE>-D<nnn>` |
| Severity | blocker / major / minor |
| Story | E15.x / other |
| Owner | A / B / C (name) |
| Code evidence | path and behavior |
| Reproducible fixture | independent expected input |
| Expected | |
| Actual | |
| Affected checks | |
| Skip/unrun disclosure | |
| Status | open / not-a-defect / repaired |
| Repair SHA | |
| Reviewer | different engineer |

Rules:

- Failed, skipped or unrun required checks are never PASS.
- Unknown coverage denominator stays UNKNOWN.
- Convenience replacement of a failing corpus remote is forbidden.
- Public scan remains read-only; do not patch assessed repositories to hide failures.
