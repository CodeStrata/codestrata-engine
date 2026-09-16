# Cumulative audit prompt — copy, fill brackets, run in a fresh session

Run this in a **fresh Cursor session**, reviewed by an engineer other than whoever authored the stories being audited. Package revision `ENGINE-2026-09-15-R1`. Full context: `CodeStrata-Engine-Team-Execution-and-Quality-Gates.md` sections "Gate conditions after each group", "Required report-view evidence at G40 and G50" and "Audit, repair, re-audit, then proceed".

```text
Audit CodeStrata Engine checkpoint [G10/G20/G30/G40/G50/G52].
Read engine/docs/implementation/CodeStrata-Engine-Team-Execution-and-Quality-Gates.md,
the revised backlog, measurement contract and completed story prompts.
The declared scope is prompts [start-end], cumulative through prompt [N].
Use original baseline [SHA], previous accepted gate [SHA] and candidate [SHA].
Verify these references and the actual working tree before trusting any status.

Do not implement next-group features, edit outside engine/, alter root editor/CI
configuration, lower a gate, publish, tag, deploy or send notifications.

1. Confirm all due stories, reviewed prerequisite SHAs and gate prerequisites.
2. Inspect cumulative and latest-group diffs, including additions, renames,
   deletions, untracked files, tests/config/gate changes and source export paths.
3. Map every delivered acceptance criterion and measurement to implementation,
   independent expected fixtures, actual execution evidence and limitations.
4. Run the exact due lint/type/test/coverage/security/contract/boundary checks.
   Test adversarial and negative behavior, not only fixtures written by the
   implementation author. Audit skipped tests and baseline failures explicitly.
5. Check supplied inputs, stable IDs, coverage/UNKNOWN, no-database stage,
   YAML/preview purposes, comparison causes, data egress and installed artifacts
   as they become due. At G40/G50 verify every named E11.2 report view against
   canonical outputs, including complete/partial/UNKNOWN/no-baseline cases,
   boundary/impact limits, ownership/co-change, freshness and linked movement
   drivers. G40 requires interim installed-candidate smoke; G50 requires the
   P46 exact-artifact wheel/sdist/container checks. No HTML-owned calculations.
   Do not pretend unbuilt future capabilities passed.
6. Write a redacted checkpoint report with reproducible defect IDs, code evidence,
   owner, severity, required repair and regression tests. Record commands and
   true exit codes, exact SHA/digests, tool versions and remaining uncertainty.
7. Return PASS only if all due acceptance is proven, no real delivered-scope gap
   remains, and independent engineer review is recorded. Otherwise FAIL/BLOCKED.
   Do not unlock the next group merely because ten prompts were attempted.
```
