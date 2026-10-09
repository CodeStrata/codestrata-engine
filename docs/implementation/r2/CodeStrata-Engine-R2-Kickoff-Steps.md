# CodeStrata Engine R2 Kickoff Steps

**Package revision:** `ENGINE-R2-2026-10-03-R1`  
**Expected branch:** `release/engine-next`  
**Audited base SHA:** `b9b71b45d8e5039257d7f209b0a45662b2604382`

## Phase 0 — Package verification

From this package directory:

```bash
python3 verify_package.py
```

Expected: PASS with 10 prompts, 3 gates and all manifest hashes matching.

## Phase 1 — Repository preflight

In the CodeStrata repository:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git rev-parse origin/release/engine-next
```

Expected starting branch: `release/engine-next`.

The audit saw four generated Gradle fixture lock/hash files dirty. Before R2 code, inspect exact paths and restore/remove **only those generated fixture artifacts** using the repository's normal cleanup practice. Do not discard any intentional engineer work.

Then require:

```bash
git status --short
```

to be clean before P01 implementation starts.

If HEAD has legitimately advanced beyond `b9b71b45d8e5039257d7f209b0a45662b2604382`, stop and run a short change-impact audit against the R2 boundary before executing prompts. Do not reset valid merged work merely to match the audited SHA.

## Phase 2 — Load authoritative R2 context in Cursor

Attach/read these files in the Cursor session:

1. `CodeStrata-Engine-R2-Patch-Boundary.md`
2. `CodeStrata-Engine-R2-Engineering-Health-Report-Contract.md`
3. `CodeStrata-Engine-R2-Build-Plan.md`
4. `CodeStrata-Engine-R2-Team-Execution-and-Quality-Gates.md`
5. `reference/R2-Implementation-Audit.txt`
6. `reference/baseline-report.html`
7. `reference/five-commit-trend-report.html`
8. `reference/implementation-guide.html`

Tell Cursor:

> These are the R2 authoritative build artifacts. The HTML files are report experience/data-contract references, not code to copy as production implementation. Preserve the current Engine architecture and reuse existing canonical M22-M31 and graph contracts.

## Phase 3 — Execution

Run prompts in order:

```text
R2-P01
R2-P02
R2-P03
R2-P04
STOP → R2-G1

R2-P05
R2-P06
R2-P07
R2-P08
R2-P09
STOP → R2-G2

R2-P10
STOP → R2-G3
```

Do not batch prompts past a gate.

## Phase 4 — Gate evidence

For each gate, have Cursor produce a read-only audit containing:
- candidate SHA;
- changed files;
- test results;
- generated artifact paths/digests;
- expected vs actual report data;
- boundary check;
- unresolved defects.

A report that “looks good” is not sufficient.

## Phase 5 — Release handoff

After R2-G3 PASS:

1. freeze exact R2 candidate SHA;
2. build exact release artifacts;
3. run a **fresh G50** using the existing Engine release gate contract;
4. obtain release-owner approval;
5. publish exact approved `0.2.2` bytes;
6. run independent G52 public-download smoke.

Do not reuse prior G50 PASS paperwork for the R2 candidate.
