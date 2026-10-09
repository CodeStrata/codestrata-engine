# CodeStrata Engine R2 Cursor Execution Package

**Package revision:** `ENGINE-R2-2026-10-03-R1`  
**Base branch:** `release/engine-next`  
**Audited base SHA:** `b9b71b45d8e5039257d7f209b0a45662b2604382`  
**Target candidate version:** `0.2.2` (do not publish until fresh G50 and G52)  
**Stories:** 10  
**R2 gates:** 3

## Purpose

This package converts the current Engine into the standalone Engineering Health experience that will also define the future Platform/Webapp repository view.

Two user journeys are in scope:

```bash
# Current repository Engineering Health baseline
codestrata assess --repo .

# Engineering Health across committed HEAD + four first-parent predecessors
codestrata trend --repo .
```

`assess` remains the single-snapshot path. `trend` is new orchestration over five immutable committed source states. Existing `compare --baseline ... --candidate ...` remains the low-level pairwise completed-assessment command.

## Product boundary

R2 is **not** an Engine redesign. It is:

1. baseline canonical wiring,
2. four-outcome Engineering Health report projection,
3. read-only five-snapshot orchestration,
4. M27-M31 trend/comparison projection,
5. acceptance and release qualification.

R2 does **not** add a new analyzer family, fifth outcome, opaque health score, database, Platform dependency, portfolio intelligence, LLM-derived canonical truth, or Community custom-rule authoring/loading.

## Start here

1. Read `CodeStrata-Engine-R2-Kickoff-Steps.md`.
2. Read `CodeStrata-Engine-R2-Patch-Boundary.md`.
3. Read `CodeStrata-Engine-R2-Engineering-Health-Report-Contract.md`.
4. Read `CodeStrata-Engine-R2-Build-Plan.md`.
5. Read `CodeStrata-Engine-R2-Team-Execution-and-Quality-Gates.md`.
6. Execute `prompts/R2-P01.md` through `prompts/R2-P10.md` in order.
7. Stop at `R2-G1` after P04 and `R2-G2` after P09. Do not proceed through a failed gate.
8. After P10, run `R2-G3`. A G3 PASS makes the exact artifact eligible for the existing fresh G50 release qualification; it does not make G52/public publication pass.

## Reference artifacts

`reference/baseline-report.html` and `reference/five-commit-trend-report.html` are the target report experiences. They are presentation/data-contract references, not production source code to copy blindly.

`reference/implementation-guide.html` is the report-design handoff.  
`reference/R2-Implementation-Audit.txt` is the read-only implementation audit used to define this package.

The reference HTML may use fictional sample values. Production output must preserve actual canonical Engine states including UNKNOWN/NOT_APPLICABLE/partial coverage rather than reproducing sample values.

## Architecture Map addition

The baseline report must include a visual **Architecture Map** projected from the graph already present in Engine JSON/canonical output.

Rules:
- canonical nodes/edges remain authoritative;
- default view is component/module level when canonical component identity exists;
- drill-down may expose file/node evidence;
- visual layout coordinates are presentation only;
- renderer must not invent architecture, edges, centrality, risk, health, or impact;
- if graph/component identity is unavailable, show an explicit unavailable state;
- no hidden top-N ranking. If display limits are needed, disclose them and retain canonical data in downloadable JSON/evidence.

## Package verification

Run from the package root:

```bash
python3 verify_package.py
```

The verifier checks the manifest, SHA-256 hashes, required files, story/gate counts, and that no standalone font files are present in this package.
