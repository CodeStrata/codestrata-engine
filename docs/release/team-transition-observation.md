# Team transition and observation window (E16.3)

Package revision `ENGINE-2026-09-15-R1`.

## Roles after published-artifact smoke passes

| Owner | Responsibility |
|---|---|
| **C** | Release support during the observation window; triage blocking Engine regressions |
| **A / B** | Platform and Webapp foundations (separate capacity; no assessment wiring until smoke PASS) |

Observation window: **three business days** starting after G52 smoke PASS on the
**candidate** PyPI semver (not after rollback rehearsal on `0.2.1`).

## Blocking regression policy

When a blocking regression is confirmed:

1. Preserve evidence (wheel digest, logs under `engine/.quality-runs/`).
2. Stop recommending the candidate semver.
3. Roll back users to the trusted prior version (`0.2.1` today) using hash-pinned
   install instructions in `baseline.md`.
4. Do **not** overwrite or mutate published immutable versions; use yank/rollback
   policy owned by the release owner.

Non-blocking declared coverage gaps enter the patch queue with truthful release notes.

## Production readiness

Passing Engine G52 on published bytes is **Community Engine release support**, not
commercial Platform production readiness. R04 hosted integration remains explicitly
unpassed until a future Platform gate.

## Current status (2026-09-30)

| Item | Status |
|---|---|
| E16.2 candidate on PyPI | **Not published** (`0.2.2` absent) |
| G52 / E16.3 smoke on candidate | **BLOCKED** — prerequisite E16.2 incomplete |
| Rollback digest guard | **PASS** — live `0.2.1` wheel hash matches `targets.yaml` |
| Observation window | **Not started** |

Update this table when E16.2 closes and G52 smoke completes.
