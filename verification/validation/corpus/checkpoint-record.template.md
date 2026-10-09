# Checkpoint evidence template (E15.1)

Copy to `engine/docs/implementation/gates/` for G10–G52. Fill every field.
Do not record failed or unrun checks as PASS.

```text
Gate: <G10|G20|G30|G40|G50|G52>
Package revision: ENGINE-2026-09-15-R1
Previous accepted SHA: <baseline>
Candidate SHA: <exact commit>
Repaired SHA: <if any>
Dirty inventory: <porcelain; do not reset unrelated work>
Environment: <os, python, tool versions>
Corpus pin digest: <sha256 of engine/verification/validation/corpus YAML>
Config digest: <if applicable>
Feed digest: <if applicable>
Hardware: <cpu, ram, declared host>

Due checks and true exit codes:
- pip check:
- ruff:
- mypy:
- pytest+coverage:
- pip-audit:
- story/contract suite:
- corpus run (when due): dogfood / 50-large / flagship labels

Collected / executed / skipped: <counts and reasons>
Coverage numerator/denominator: <never unknown as 0% or 100%>
Not-yet-due gates: <owner story>
Findings: <IDs>
Independent reviewer: <name other than author>
Decision: PASS | FAIL | BLOCKED | NOT_YET_DUE
Next group unlocked: <only if PASS>
```
