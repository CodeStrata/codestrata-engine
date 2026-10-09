# Gate record template

One of these per gate (G10, G20, G30, G40, G50, G52), filed under
`engine/docs/implementation/gates/`.

```text
Gate: G10
Previous accepted SHA: <baseline>
Candidate SHA: <exact commit>
Scope: P01-P10, plus cumulative baseline
Due checks and command evidence: <table>
Not-yet-due gates: <owner story and rationale>
Findings: <IDs / expected vs actual / owner / evidence>
Repairs and final SHA: <commits>
Recheck results and test/skip/coverage totals: <evidence>
Independent reviewer: <name and review reference>
Decision: PASS | FAIL | BLOCKED
Next group unlocked: P11-P20 only if PASS
```
