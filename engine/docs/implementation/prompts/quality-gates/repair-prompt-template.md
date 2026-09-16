# Repair and re-audit prompt — copy, fill brackets, run per accepted defect batch

Use after an audit records accepted (not dismissed) defects. Integrate
repairs through the normal different-engineer review, then re-run the
audit prompt on the final repaired SHA before unlocking the next group.

```text
Repair the accepted defects [IDs] from checkpoint [gate] at [candidate SHA].
Read the gate report, execution policy and affected story/measurement contracts.
Preserve the Engine-only scope and stable release. No next-group features.

For each defect, reproduce it, add an independent expected regression fixture,
make the smallest complete correction and run the failing plus affected checks.
Do not relax assertions, skip tests, suppress UNKNOWN, change accepted formulas,
move code outside Engine or fabricate evidence to obtain PASS.

Record each repair commit, expected/actual behavior and test results. Integrate
through the normal different-engineer review. Then run the cumulative audit
again on the final repaired SHA and reconcile every prior defect. If repair
changes shared schemas/config/catalog, rerun all affected consumers/fixtures.
Return a reviewable repair record and re-audit result. Unlock the next group only
through a recorded PASS reviewed by an engineer other than the sole author.
```
