# CodeStrata Engine R2 Patch Boundary

**Revision:** `ENGINE-R2-2026-10-03-R1`  
**Base:** `release/engine-next` @ `b9b71b45d8e5039257d7f209b0a45662b2604382`

## 1. Locked product boundary

R2 preserves the existing Engine product boundary:

> **CodeStrata Engine is the complete, trustworthy, local evidence and change-analysis runtime for one repository. Platform sells continuity, organizational context, portfolio intelligence, governance, curated decision IP, and the operating system around that evidence.**

Public Engineering Health outcomes remain exactly:

1. Architecture
2. Security
3. Quality
4. Maintainability & Technical Debt

Repository/technology inventory, dependency intelligence, Git/change intelligence, testing/CI evidence and the canonical graph are supporting evidence/context. They are not additional public health outcomes.

## 2. R2 allowed changes

### R2-A — Engineering Health report projection

Allowed:
- replace legacy-head-first primary HTML with a four-outcome Engineering Health primary report;
- add a first-class Quality projection from existing Quality evidence;
- relabel/group Technical Debt under Maintainability & Technical Debt;
- demote Technology Inventory, Dependencies and Git to supporting context/evidence;
- demote Cloud Readiness, AI Readiness and legacy Modernization from headline health outcomes;
- preserve existing Priority Actions but present them in the new report hierarchy;
- project canonical Engineering Hotspots, ownership, co-change, coverage/freshness and evidence;
- add Architecture Map visualization from the existing canonical graph JSON;
- keep `canonical-report.html` as an acceptance/debug sidecar.

Not allowed:
- HTML calculating new health/verdict/ranking/delta/lifecycle/movement;
- new composite score;
- hidden hotspot weighting;
- invented graph edges/components/centrality.

### R2-B — Baseline canonical wiring

Allowed:
- attach M22, M25, M26 and capability coverage/freshness during normal `assess` before report generation;
- attach source revision, dirty/working-state identity and digests;
- use bounded Git history as context for the current snapshot;
- pin production evaluation time rather than use a hardcoded journey date;
- stop production R2 output from depending on report-time re-observation of live HEAD when assess-time canonical records are available.

Baseline semantics:
- local `assess` continues to assess the current files on disk;
- dirty working trees are allowed and must be visibly identified as dirty;
- a dirty baseline must not be attributed to clean HEAD;
- baseline does not automatically compare to `previous/` and must not invent trend/movement.

### R2-C — five-snapshot local orchestrator

Allowed:
- add `codestrata trend --repo <path>`;
- select committed HEAD + four first-parent predecessors;
- display oldest -> newest;
- if fewer than five committed states exist, preserve requested slots and mark missing/unavailable rather than fabricate them;
- materialize immutable source trees into temporary directories without changing the user's working tree;
- pin one Engine/rules/config/feed/evaluation profile across the series;
- run the existing assessment pipeline independently on each snapshot;
- store series artifacts in a dedicated file-based trend bundle.

Trend semantics:
- uncommitted working-tree changes are **excluded** from trend;
- if the user's working tree is dirty, report that it was left untouched and that trend uses committed HEAD;
- no repository hooks/build/test execution solely to materialize snapshots;
- no database.

### R2-D — five-commit comparison/trend projection

Allowed:
- four adjacent comparisons: S1→S2, S2→S3, S3→S4, S4→HEAD;
- one span comparison: S1→HEAD;
- reuse M27 change summary, M28 finding lifecycle, M29 static blast radius, M30 outcome movement and M31 cause attribution;
- reuse named MetricDelta/Before-After-Delta semantics;
- map testing-specific movement under public Quality rather than create a fifth public outcome;
- preserve evidence binding to the originating source state/commit;
- render one local trend HTML bundle.

### R2-E — acceptance, fixtures, docs and gates

Allowed:
- extend existing R2-relevant tests and fixtures;
- add five-commit fixture repositories and leakage tests;
- add installed-artifact journeys;
- add R2 gate records/docs;
- build exact wheel/sdist/container using existing release machinery when entering fresh G50.

## 3. Architecture Map projection contract

The Engine already captures graph data. R2 may visualize it without changing analysis semantics.

Required behavior:
- source: the same canonical graph/AnalysisResult graph used by existing Engine logic such as M29;
- nodes: canonical graph nodes only;
- edges: canonical graph edges only;
- grouping: only canonical component/module membership; if absent, do not infer a new architecture boundary in HTML;
- default: component/module-level map where supported;
- drill-down: component → canonical nodes/files/findings/evidence;
- overlays may reference existing hotspot/findings/ownership context, but overlays do not change graph topology;
- graph layout algorithm may compute x/y coordinates only as rendering state;
- downloadable JSON retains canonical identifiers and edges;
- large graph handling may virtualize/filter visually but may not silently drop data or claim full display coverage.

## 4. Explicit exclusions

The following are outside R2:

- new analyzer family;
- new `OutcomeFamily` value;
- composite Engineering Health score;
- modernization score;
- predictive “will break next” claims;
- runtime/log/Datadog analysis;
- cross-repository or workspace aggregation;
- tenant/workspace/org concepts;
- portfolio graph;
- GraphRAG;
- database as default persistence;
- Platform APIs/UI/auth/policy lifecycle;
- Community customer custom-rule authoring/loading/import;
- LLM generation of canonical findings, metrics, verdicts or trend;
- arbitrary commit-count trend configuration in R2;
- hidden repository scan against five historical commits without immutable source-state assessment;
- mutation of the user's checkout;
- reuse of current/previous retention slots for five snapshots.

## 5. Non-negotiable correctness invariants

1. **No future-history leakage.** Snapshot S_i may only use Git history reachable from and ending at S_i.
2. **No source-state leakage.** S_i analysis must read S_i files, not current HEAD or dirty worktree files.
3. **Same pinned profile.** Five snapshots share Engine version, ruleset, config, external-feed snapshot and evaluation time unless a required capability explicitly reports otherwise.
4. **No HTML truth creation.** HTML projects supplied canonical/Comparison records.
5. **No missing-evidence optimism.** UNKNOWN/partial coverage never becomes clean/healthy by omission.
6. **No working-tree mutation.** Trend must leave user's index/worktree byte-for-byte/status-equivalent to pre-run state.
7. **No score.** Named metrics, ratios, counts and movements only.
8. **One repository only.** No portfolio semantics.
9. **Evidence remains traceable.** Every displayed finding, movement, action, hotspot and graph-related claim links to canonical identity/evidence or is explicitly unavailable.
10. **Community custom-rule boundary unchanged.**

## 6. Files outside the patch unless strictly required by command registration

Do not change:
- `platform/**`
- VS Code/Webapp/MVP wireframes
- portfolio/EIR paths
- AI modules as canonical truth producers
- SQLite as default persistence
- Community custom-rule exclusions
- published PyPI `0.2.1` bytes
- G52/publication state

`cli/community_contract.py` may only receive the minimum registration change needed for the new `trend` command; existing custom-rule exclusions must remain byte-for-byte semantically unchanged.
