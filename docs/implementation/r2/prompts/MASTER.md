# CodeStrata Engine R2 Cursor Master Execution Prompt

You are implementing CodeStrata Engine R2 from package `ENGINE-R2-2026-10-03-R1`.

Before any code change, read:
- `CodeStrata-Engine-R2-Patch-Boundary.md`
- `CodeStrata-Engine-R2-Engineering-Health-Report-Contract.md`
- `CodeStrata-Engine-R2-Build-Plan.md`
- `CodeStrata-Engine-R2-Team-Execution-and-Quality-Gates.md`
- `reference/R2-Implementation-Audit.txt`

The reference HTML files define target experience/data projection, not production implementation source.

## Global rules

- Reuse existing Engine contracts and modules.
- Do not add a new analyzer family or OutcomeFamily.
- Four public outcomes only: Architecture, Security, Quality, Maintainability & Technical Debt.
- No opaque/composite score.
- No database.
- No Platform dependency.
- No Community custom-rule authoring/loading/import.
- No LLM-generated canonical truth.
- HTML/projectors do not calculate health, hotspot rank, lifecycle, deltas, movement or graph topology.
- Architecture Map projects canonical graph JSON only.
- Trend never mutates the user's working tree.
- Snapshot S_i cannot see S_(i+1)..HEAD source files or Git history.
- Existing `compare` remains pairwise completed-assessment CLI.
- Baseline remains `assess`; new fixed-five journey is `trend`.
- Execute one story prompt at a time and stop at gates.

At the end of every story return:
1. starting/final SHA;
2. files changed;
3. requirement mapping;
4. tests run and exact result;
5. generated artifacts;
6. limitations/open defects;
7. boundary statement;
8. whether next prompt is unlocked.
