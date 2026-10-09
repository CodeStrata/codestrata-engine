# CodeStrata Engine R2 Build Plan

**Revision:** `ENGINE-R2-2026-10-03-R1`  
**Base SHA:** `b9b71b45d8e5039257d7f209b0a45662b2604382`

## Execution model

Ten prompts, three gates. Execute one prompt at a time. A story is not accepted from a completion note alone; tests + artifacts + reviewer evidence are required.

| Prompt | Group | Story | Depends on | Gate |
|---|---:|---|---|---|
| R2-P01 | 1 | Freeze base and executable R2 contracts | — | — |
| R2-P02 | 1 | Attach baseline canonical history/trust records during assess | P01 | — |
| R2-P03 | 1 | Build four-outcome Engineering Health projection model | P02 | — |
| R2-P04 | 1 | Deliver baseline HTML including Architecture Map | P03 | **R2-G1** |
| R2-P05 | 2 | Implement first-parent selection and immutable snapshot materialization | G1 | — |
| R2-P06 | 2 | Implement leakage-safe five-snapshot orchestrator and `trend` CLI | P05 | — |
| R2-P07 | 2 | Implement durable five-slot trend artifact bundle | P06 | — |
| R2-P08 | 2 | Wire M27-M31 adjacent/span comparisons | P07 | — |
| R2-P09 | 2 | Deliver five-commit trend HTML | P08 | **R2-G2** |
| R2-P10 | 3 | Full R2 acceptance, installed-artifact validation and release handoff | G2 | **R2-G3** |

## R2-P01 — Freeze base and executable R2 contracts

### Deliver
- verify branch/base SHA and clean starting worktree;
- preserve existing package/version state until release qualification;
- add R2 implementation note/contract in Engine docs if repository process requires it;
- identify exact production functions/files to touch before edits;
- ratify CLI semantics: `assess` baseline, new fixed-five `trend`, existing `compare` unchanged;
- create no new analyzer/OutcomeFamily/score/schema unless an implementation blocker is proven.

### Acceptance
- working tree clean apart from intentional P01 changes;
- base SHA recorded;
- all exclusions in Patch Boundary asserted by tests/docs where practical;
- no production behavior change beyond scaffolding/contracts.

## R2-P02 — Attach baseline canonical history/trust records during assess

### Deliver
During normal assess, produce/attach the existing canonical records required by the primary baseline report:
- M22 hotspots;
- M25 ownership concentration;
- M26 co-change;
- capability coverage/freshness;
- Git history context;
- vulnerability-feed freshness;
- source revision/dirty/working digest;
- canonical graph reference already present in AnalysisResult.

Remove production dependence on a live-repo `observe_repository()` fallback for records that should have been sealed at assess time.

### Acceptance
- `AnalysisResult`/sealed report input contains records after assess;
- no hardcoded `JOURNEY_EVALUATION_TIME` in production R2 semantics;
- dirty baseline remains honest;
- missing Git/feed yields UNKNOWN rather than clean values;
- deterministic repeat with pinned inputs;
- existing M22/M25/M26 tests extended rather than reimplemented.

## R2-P03 — Four-outcome Engineering Health projection model

### Deliver
Create/adapt report view-model projection using existing canonical objects.

Primary outcomes exactly:
- Architecture
- Security
- Quality
- Maintainability & Technical Debt

Demote Inventory/Dependencies/Git to supporting evidence and Cloud/AI/Modernization to appendix/supporting output if still produced.

### Acceptance
- Quality is first-class report projection without new analyzer family;
- testing drivers map under Quality;
- output status cannot contradict coverage/trust;
- renderer/view-model does not compute hotspot rank/delta/lifecycle/movement;
- no new composite score;
- canonical finding/evidence IDs retained.

## R2-P04 — Baseline HTML + Architecture Map

### Deliver
Primary `assessment.html` aligned with `reference/baseline-report.html`:
- attention-first summary;
- four outcomes;
- Architecture Map from canonical graph JSON;
- Hotspots M22;
- ownership M25;
- co-change M26;
- Priority Actions;
- Coverage & Trust;
- supporting evidence/appendix.

### Architecture Map acceptance
- only canonical nodes/edges;
- component grouping only from canonical component identity;
- visual layout only may be computed in renderer;
- clicking/drill-down links to canonical IDs/evidence;
- no hidden node ranking or invented edges;
- unavailable state explicit;
- large graph display limits disclosed.

### R2-G1
Baseline gate must prove complete, partial, UNKNOWN/no-history, missing-feed and dirty-tree cases plus installed-wheel smoke.

## R2-P05 — First-parent series + immutable snapshot materializer

### Deliver
- resolve committed HEAD;
- `rev-list --first-parent --max-count=5 HEAD` equivalent through allowed read-only Git abstraction;
- reverse for oldest→newest display;
- materialize each SHA to an isolated temp tree without checkout/worktree mutation;
- no hooks/build/tests executed merely for extraction;
- preserve missing slots if fewer than five commits.

Preferred implementation: read-only archive/ls-tree/show extraction through `run_readonly_git`; do not invoke raw mutating Git.

### Acceptance
- user worktree/index/status identical before/after;
- extracted file bytes match each commit tree;
- dirty uncommitted files never appear in trend snapshots;
- temp cleanup reliable on success/failure;
- no future source-state leakage.

## R2-P06 — Leakage-safe five-snapshot orchestrator + `trend`

### Deliver
Add `codestrata trend --repo <path>`.

One run:
1. freezes Engine/rules/config/feed/evaluation profile;
2. obtains five slots;
3. assesses each available snapshot through existing `run_assessment` pipeline;
4. forces Git history head to each S_i;
5. records per-slot result/source/config/feed digests;
6. preserves failed/missing slots as explicit UNKNOWN/unavailable.

### Acceptance
- snapshot S1 cannot see S2..HEAD files or Git history;
- `build_history_index(... head=S_i ...)` or equivalent enforces as-of-commit history;
- current live HEAD observer is not used for historical slots;
- hardcoded journey date not used;
- dirty worktree is ignored by trend and left unchanged;
- no LLM required.

## R2-P07 — Five-slot trend artifact bundle

### Deliver
Dedicated file artifact layout under trend namespace. Never use the two-slot baseline retention (`current/previous`) for the series.

Bundle contains:
- index/selection metadata;
- five requested slot records;
- available snapshot assessment artifacts;
- comparison artifacts;
- final trend HTML/JSON;
- exact digests/versions.

### Acceptance
- deterministic slot order;
- failed/missing slot preserved;
- no evidence deletion through current/previous rotation;
- rerun retention behavior explicit and tested;
- no database.

## R2-P08 — M27-M31 adjacent + span comparison wiring

### Deliver
For available compatible pairs:
- 4 adjacent comparisons;
- S1→HEAD span comparison;
- M27 range/change summary;
- M28 lifecycle;
- M29 graph delta/static impact;
- M30 movement across four public outcomes;
- M31 cause attribution;
- named Before/After/Delta metrics.

### Acceptance
- reuse `ScanComparisonService` and existing M27-M31 modules;
- no second compare engine;
- `compare` CLI semantics remain two completed files;
- testing movement does not become fifth headline;
- static blast radius described with bounds/cutoff/coverage;
- source/feed/config/engine digest attribution recorded;
- evidence base/candidate commits correct.

## R2-P09 — Five-commit trend HTML

### Deliver
Primary trend report aligned with `reference/five-commit-trend-report.html`:
- current HEAD four-outcome health;
- five source-state observations;
- adjacent and span selector;
- outcome movement;
- finding lifecycle;
- change summary;
- static impact/blast radius;
- Before/After/Delta;
- current hotspots/ownership/co-change;
- evidence drill-down.

### Acceptance
- HTML projects supplied values only;
- missing/failed slots remain visible;
- incompatible metrics retain gaps/reasons;
- equal finding counts do not imply Stable when identities change;
- all evidence bound to source commit;
- offline/no CDN;
- deterministic HTML from deterministic bundle.

### R2-G2
Must include explicit future-history/source-leakage adversarial tests and visual review of generated real report artifacts.

## R2-P10 — R2 acceptance + release handoff

### Deliver
Run and document:
- complete/partial/UNKNOWN/no-history/missing-feed/shallow-Git/dirty-tree cases;
- fewer-than-five-commit trend;
- failed middle snapshot;
- incompatible comparison;
- M29 cutoff/lower-bound;
- two-run determinism;
- installed wheel/sdist report journeys;
- container journey when existing release contract requires it;
- Community custom-rule exclusions unchanged;
- no Engine→Platform dependency.

### Acceptance
- `R2-G3` PASS on exact candidate SHA;
- exact artifact digests recorded;
- no unexplained skip;
- report screenshots/HTML alone are not evidence: expected vs actual canonical values recorded;
- public publication still blocked until the existing fresh G50 release qualification and release-owner approval pass;
- G52 remains unpassed until independent public-download smoke.
