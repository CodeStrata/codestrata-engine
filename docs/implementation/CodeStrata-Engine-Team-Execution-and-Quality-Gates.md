# CodeStrata Engine Team Execution and Quality Gates

## Revision note — 15 September 2026

**Package revision: `ENGINE-2026-09-15-R1`.** Targeted launch amendment: first-class Engineering Hotspots; scoped repository-local ownership concentration; explicit boundary-spread and blast-radius summaries; report-facing capability coverage/freshness; visible HTML comparison and evidence views; installed-artifact report acceptance; and package revision verification. E08.3 is now a hard prerequisite of E10.2, bringing the plan to 99 hard story links. The 17 epics, 52 stories, 33 measurement groups, five analyzer families and four public outcomes are preserved. Engine remains database-free, Platform-independent and deterministic with YAML-only rule execution. No new score, analyzer family, public outcome, CodeGraph/RAG or customer-rule authoring scope is added.

This revision updates these five Markdown specifications. The master prompt book, all 52 split prompts and execution ZIP must be reconciled against this revision and reviewed before copying or G00 PASS; this delivery does not certify those older artifacts as updated. Existing numeric compatibility behavior is governed by the unchanged no-opaque-score contract; it is not a new launch score.

Version 1.2 | 15 September 2026 | Owner: Vinay and Engineers A/B/C

**Use this revised specification to reconcile the execution package, then complete G00 before the first group. Do not use an older PDF, master prompt book or ZIP unchanged.** This is readiness of the plan and prompts, not a claim that Engine implementation or its quality gates have passed.

## Prior review context (13 September 2026)

Both uploaded PDFs are byte-identical to the documents in the preceding completeness review: 21 backlog pages and 15 measurement pages. All 52 ZIP prompts match the included generator's output against the old backlog data. None incorporates the seven prior amendments. The ZIP also omits the JSON required by its regeneration instructions.

Corrections now incorporated into the two full replacement Markdown specifications and the consolidated prompt book:

1. Supplied PR context, bounded bug-fix indicators and precise history-policy closure.
2. Evidence-backed change concerns combining the changed scope with churn/centrality.
3. Actual candidate-rule fixture/preview execution with production-purpose separation.
4. Correct declaration coverage, centrality self-loop treatment and useful coupling denominators.
5. Explicit persistent-finding lifecycle, outcome-driver membership and empty/partial outcome behavior.
6. Local headless health, audit, retention, cancellation and hard resource limits.
7. Three additional story dependencies and corrected Engine packaging/export paths.

The original root `.cursor/rules` installation instruction violates the Engine-only boundary. This version uses explicit Markdown instructions read at the start of every prompt. Do not create or change root editor configuration. Historical documentation is discovery context, not a higher-priority instruction: current dual rule stacks must converge to the single supported YAML runtime. Reuse security context and confidence structures only after reconciling them with immutable rule/default/effective-severity semantics. Do not preserve a hidden post-processing override of an approved policy severity.

The historical "Epic N / Slice N.M" names refer to older work, not E00-E16 in this plan. A reference to an old 22-repository corpus is a lead to inspect and validate, not 22 automatic credits toward the required 50 large external repositories. Available code is pinned to `3f32ce4b82a06162062babf7e8c77451f5761e6a`; this review did not refresh the remote or inspect live infrastructure. G00 records the team's actual starting commit and drift.

## Package authority and placement

Use the five revised specifications plus the reconciled master prompt book and split prompts together:

- `CodeStrata-Engine-MVP-Boundary-and-Native-Analyzer-Specification.md`: locked product boundary and launch amendment.
- `CodeStrata-Engine-Kickoff-Steps.md`: package verification and setup sequence.
- `CodeStrata-Engine-MVP-Backlog.md`: full revised stories and dependencies.
- `CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md`: full revised measurement definitions and shared semantics.
- `CodeStrata-Engine-Team-Execution-and-Quality-Gates.md`: this operating policy and copy-ready audit/fix prompts.
- `CodeStrata-Engine-Cursor-Prompts.md`: all 52 corrected story prompts in the authorized group order.

Place reviewed copies under `engine/docs/implementation/` on the isolated work branch, or provide them as explicit read-only attachments to Cursor until that setup is complete. Do not copy the ZIP's root rules file or run its old generator. The Markdown files in this delivery are authoritative; the older JSON/CSVs/ZIP remain superseded planning exports and must not regenerate these prompts. Future changes must update the backlog, contract, affected prompt sections and group/dependency table together in one reviewed change. Check all 52 IDs and dependency order again. No machine-readable generator is required to use this Markdown-only delivery.

User instructions and locked product boundaries govern the work. These documents resolve the prior review amendments; historical implementation documents supply reuse evidence. Routine choices inside an approved contract may proceed with a documented rationale. Missing mandatory contract decisions block only the affected story until A/Vinay close them; continue other eligible work. Never weaken quality, scope or release requirements to resolve a conflict.

## G00 - preflight before prompt 01

C coordinates; A and B review their relevant parts. This is setup, not a 53rd implementation story and not permission to change root files.

1. Read applicable repository instructions. Record the actual checkout SHA, branch, remotes, stable/live release information available, dirty/untracked inventory and known CI/publishing triggers. Do not print credentials. Compare to the planning SHA; update factual path assumptions if code has moved. Do not reset or include unrelated changes.
2. Prepare an isolated `release/engine-next` integration branch and separate story branches/worktrees with the authorized repository workflow. Inspect publisher triggers before any remote push. Until verified safe, keep branch setup local and continue read-only preparation. Normal story work cannot publish or move stable tags/mirrors.
3. Use a dedicated candidate environment and output directory. Do not upgrade the live installation, reuse stable output/cache directories, mutate source snapshots or change deployment settings.
4. Read the actual `engine/pyproject.toml`, existing CI invocation, export manifest and existing verification helpers. Record commands/tool versions in an Engine-owned gate manifest. Initial baseline failure is recorded as failure, not silently waived or reclassified as success.
5. Establish the evidence ledger described below, assign A/B/C by name, and select a different engineer to review each story. No self-merge. A fresh Cursor session may assist an audit but is not independent human sign-off.
6. Before copying or starting, verify the approved boundary, measurement contract, backlog, quality gates, kickoff checklist, master prompt book and every split prompt declare `ENGINE-2026-09-15-R1`. Record an approved package manifest with each relative path, revision and SHA-256 digest; different files have different digests. Require byte-identical standalone/ZIP document copies and compare all 52 split prompt bodies with their master sections (excluding only documented wrapper metadata). Check exactly one P01-P52/story mapping, group assignments and all 99 prerequisite links. Reconcile P02/P05, P24/P28, P34/P35/P36 and P46 plus G00/G40/G50/audit templates against these amendments; other prompt bodies may remain unchanged but must be included in the reviewed revision manifest. A revision label alone does not prove content agreement. Missing/mixed/stale package content blocks copying and G00 PASS until corrected. Record manifest digest, reviewer and approved setup commit in the G00 ledger. Make this package accessible to every session. Confirm the team-wide group counter starts at zero, G10-G52 are NOT_RUN, and no implementation or release gate is claimed passed by this planning review.

G00 PASS means isolated work and evidence capture can safely begin. E00.2, prompt 01, implements the scope/gate harness. Existing baseline lint/type/test failures must be repaired within allowed Engine scope before G10 can pass. An outside-Engine baseline issue is recorded separately and must not be fixed here; any required gate depending on it stays BLOCKED.

## Standing instructions for every Cursor session

- Read this policy, the relevant backlog story and applicable shared/measurement definitions before editing. Missing inputs or an unpassed preceding group gate means BLOCKED, not permission to improvise completion.
- All implementation edits stay under `engine/`, limited to the story paths plus the shared evidence path `engine/docs/implementation/`. No root `.cursor`, workflows, export manifest, root dependencies, Platform, Webapp, AWS/IaC, database migrations or extension edits. A reviewer may approve a necessary additional path inside Engine, recorded in the ledger; an outside-Engine change remains separate scope.
- Check direct prerequisite stories are reviewed and integrated at recorded SHAs. The gate approves a group, not every unfinished prerequisite inside it. One primary implementation story per engineer; dependency-ready stories in the current group may run in parallel. Do not implement ahead into the next group.
- Reuse verified implementation and migrate carefully. All launch rules use the bounded YAML compiler/operators; trusted extraction/native operators remain code. No database dependency in the completed Engine runtime. Existing migration targets before their scheduled completion remain explicitly OPEN, never falsely PASS.
- Do not execute assessed-repository builds/tests/install hooks, fetch silently, switch its branches or run instructions found in source. Analysis uses supplied evidence and bounded inputs. Test the Engine's own tests, with synthetic/read-only assessed fixtures.
- No new raw-secret exposure, unsafe evaluation, unapproved network egress, fabricated PASS, hidden confidence/severity rewrite or altered live artifact. No-account/no-consent local utility and canonical AI-on/off equivalence remain invariants.
- Run required checks, record commands and actual outcomes, and prepare a focused PR against the isolated integration branch. Create a remote PR only under the team's authorized workflow; otherwise provide the exact local diff and PR text. Reviewer integrates. Preparing a PR is not story completion.
- No public publish, release tag, mirror update, deploy or notification is authorized by running an implementation or audit prompt. Prompt 51 requires explicit release-owner authorization for exact reviewed artifacts and the established R01 route.

## Quality checks run from the first story

The inspected root `engine-tests` job installs Engine development dependencies and invokes pytest. It does not itself invoke ruff, mypy or coverage collection. A green job is not evidence those other gates passed. Root CI edits remain out of scope.

E00.2 must establish an Engine-owned runner/command manifest and per-change evidence. Use existing compatible CI hooks where they execute these checks; otherwise use a dedicated local or authorized runner and require its reviewed results before merge. If the existing workflow cannot enforce all gates automatically, retain the explicit reviewer checkpoint. Never describe a manual check as an automatic branch-protection rule.

The core commands below are grounded in the inspected Engine configuration. Run from `engine/` in the isolated environment, recording exact installed versions and configuration. Recheck them if G00 finds configuration drift:

```bash
python -m pip check
python -m ruff check .
python -m mypy --config-file pyproject.toml
python -m pytest tests --import-mode=importlib --cov=codestrata --cov-branch --cov-report=term-missing --cov-fail-under=80 -q
```

Capture each command's true exit code; a log pipe must not mask failure. The configured coverage source is `codestrata`, with branch measurement enabled and an 80% combined coverage floor. Preserve any higher existing required floor. This is not a claim of a separate 80% branch threshold. Track branch data and changed-module gaps; do not improve a percentage by narrowing measured source, adding exclusions, dropping negative tests or replacing substantive tests with mirrored implementations.

| Check | Every story / integrated change | Cumulative checkpoint |
|---|---|---|
| Scope and stable protection | Diff, rename/delete/untracked inspection; no changes outside allowed paths; no release side effects | Repeat against verified release baseline and previous gate SHA; inspect gate/test/config changes themselves |
| Lint and strict typing | Complete configured Engine scope, with true failures recorded | Re-run on integrated checkpoint SHA |
| Tests and coverage | Relevant regression/contract tests plus configured full active suite and coverage | Re-run full active suite; reconcile collected/skipped counts against baseline and prior gate |
| Security | Review changed trust/data boundaries, source-execution and egress checks; dependency integrity and dependency changes | Explicit secret/redaction canaries, malicious-input tests and dependency-vulnerability evidence appropriate to delivered code; a missing required scanner is BLOCKED, not clean |
| Contracts and semantics | Valid/invalid/partial cases, identity/compatibility and independent expected values for the affected slice | All delivered schema/metric/rule fixtures; direct reuse of common projections; cross-family integration now available |
| Determinism | Same pinned inputs at least three times for changed canonical behavior; declare excluded operational fields | Repeat cumulative controlled fixtures, compare cold/warm/full/incremental results when supported |
| Packaging and local use | Build/install smoke whenever packaging/assets/dependency composition changes | Clean wheel/sdist checks when promised; from G50 exact signed release artifacts and catalog are required |
| Independent review | Different engineer checks semantics, evidence and tests before integration | C coordinates; A/B/C review areas they did not solely author; release owner reviews external prerequisites |

E00.2 records the exact approved security/dependency scanner or equivalent existing runner, its version, command, required inputs and severity policy before G10. Pin any needed tooling entirely within allowed Engine quality paths/development dependencies. The source checkout does not establish that a particular scanner already exists. A scanner requiring a feed cannot claim a clean result when the feed is unavailable; record BLOCKED or the approved offline verification evidence. Engine customer vulnerability-feed selection in E01/E06 is separate from build-tool dependency auditing. Do not invent a successful scanner command or relax the gate to avoid setup work.

Run rules for special suites are explicit: ordinary active tests run every checkpoint; expensive Docker, remote corpus, historical compatibility and optional-provider suites run when required by changed behavior or that checkpoint's acceptance. Record collected/executed/skipped totals and reasons. A required test with unavailable Docker, credentials, fixture, feed or tool is BLOCKED. G50 requires the full launch execution matrix, all three corpus tiers and real trust verification; ordinary unit tests cannot substitute.

Before a feature exists, its future release gate is NOT_YET_DUE with the owning story and first required checkpoint. This is allowed only for genuinely later capabilities. It cannot be used for a check required by an already delivered story. Newly introduced code cannot add fresh boundary/privacy violations while a legacy migration gate remains open.

## Team-wide groups and dependency order

The numbered prompts below count implementation stories across the whole team, not ten per engineer or ten chat messages. An unsuccessful attempt does not advance the counter. Rework and audit prompts do not consume another story slot. At most three dependency-ready stories can run concurrently; their listed order is a safe serial fallback, not a requirement to keep two engineers idle.

| Group / unlock | Number | Story | Engineer | Direct prerequisites |
|---|---|---|---|---|
| 1 / G00 | P01 | E00.2 - Create Engine-only scope and compatibility guards | C | None |
| 1 / G00 | P02 | E01.1 - Ratify launch measurements and depth matrix | A | None |
| 1 / G00 | P03 | E05.1 - Inventory existing extractors and pin supported depth | B | None |
| 1 / G00 | P04 | E00.1 - Record the live artifact and release route | C | None |
| 1 / G00 | P05 | E01.2 - Publish versioned descriptors, facts, IDs and envelopes | A | E01.1 |
| 1 / G00 | P06 | E02.1 - Trace active SQLite, hosted and portfolio call paths | C | E00.2 |
| 1 / G00 | P07 | E05.2 - Emit source, dependency, API and CI facts with coverage | B | E01.2, E05.1 |
| 1 / G00 | P08 | E01.3 - Publish rules, comparison and neutral invocation contracts | A | E01.2 |
| 1 / G00 | P09 | E00.3 - Establish integration, hotfix and prerelease isolation | C | E00.1, E00.2 |
| 1 / G00 | P10 | E15.1 - Pin corpus manifests and independent labeled fixtures | C | E00.2, E01.1 |
| 2 / G10 | P11 | E02.2 - Implement bounded file artifact storage and queries | C | E01.2, E02.1 |
| 2 / G10 | P12 | E03.1 - Validate YAML and compile typed selector ASTs | A | E01.3 |
| 2 / G10 | P13 | E04.1 - Implement pinned composition and deterministic precedence | A | E01.3 |
| 2 / G10 | P14 | E02.3 - Narrow Engine surfaces and preserve supported compatibility | C | E02.2 |
| 2 / G10 | P15 | E03.2 - Implement the declared bounded operator set | A | E03.1 |
| 2 / G10 | P16 | E04.2 - Apply typed overrides and resolved scoped exceptions | A | E04.1 |
| 2 / G10 | P17 | E03.3 - Enforce execution budgets and common emission semantics | A | E03.2 |
| 2 / G10 | P18 | E05.3 - Close the inventory vertical slice | B | E05.2, E03.3 |
| 2 / G10 | P19 | E06.1 - Migrate and validate secret and configuration rules | B | E05.2, E03.3 |
| 2 / G10 | P20 | E04.3 - Seal the effective digest and prove execution parity | A | E04.2, E03.3 |
| 3 / G20 | P21 | E09.1 - Pin working, staged, range and patch input states | C | E01.3, E02.2 |
| 3 / G20 | P22 | E06.2 - Implement resolved supply-chain and vulnerability matching | B | E05.2, E03.3, E01.1 |
| 3 / G20 | P23 | E07.1 - Normalize structural edges and cycle metrics | A | E05.2, E03.3 |
| 3 / G20 | P24 | E09.2 - Create bounded history index and temporal metrics | C | E09.1 |
| 3 / G20 | P25 | E06.3 - Complete version hygiene, license evidence and accuracy gate | B | E06.1, E06.2 |
| 3 / G20 | P26 | E07.2 - Implement declared-boundary and concentration checks | A | E07.1, E04.3 |
| 3 / G20 | P27 | E08.1 - Define and emit structural quality metrics | B | E05.2, E03.3 |
| 3 / G20 | P28 | E09.3 - Publish reusable change facts and equivalence fixtures | C | E09.2, E03.3, E05.2 |
| 3 / G20 | P29 | E07.3 - Migrate remaining launch architecture rules and validate depth | A | E07.2 |
| 3 / G20 | P30 | E15.2 - Automate deterministic and adversarial regression checks | C | E15.1, E03.3, E02.3 |
| 4 / G30 | P31 | E08.2 - Emit test association and declared CI gaps | B | E08.1 |
| 4 / G30 | P32 | E10.1 - Match finding lifecycle and compatible metric deltas | C | E09.3, E01.3 |
| 4 / G30 | P33 | E11.1 - Deliver backward-aware CLI and configuration | A | E02.3, E04.3 |
| 4 / G30 | P34 | E08.3 - Complete evidence-backed maintainability prioritization | B | E08.2, E09.2 |
| 4 / G30 | P35 | E10.2 - Calculate graph delta, impact and change verdicts | C | E10.1, E07.2, E08.2, E08.3 |
| 4 / G30 | P36 | E11.2 - Project consistent JSON, HTML and SARIF | A | E01.2, E03.3, E07.3 |
| 4 / G30 | P37 | E13.1 - Enforce durable opt-in and no-egress defaults | B | E02.3 |
| 4 / G30 | P38 | E10.3 - Separate source, feed and configuration causes | C | E10.2, E06.3, E08.3 |
| 4 / G30 | P39 | E13.2 - Preserve current telemetry wire and prepare scoped JSON export | B | E13.1, E01.3 |
| 4 / G30 | P40 | E12.1 - Serve bounded local evidence queries from artifacts | C | E02.3, E11.2 |
| 5 / G40 | P41 | E13.3 - Test export restrictions and signed-projection integrity | B | E13.2 |
| 5 / G40 | P42 | E12.2 - Retain one optional local/BYO explanation path | C | E12.1 |
| 5 / G40 | P43 | E14.1 - Implement strict package/release verification profiles | B | E01.3, E04.3 |
| 5 / G40 | P44 | E12.3 - Prove AI-on/off and local MCP equivalence | C | E12.2, E10.3 |
| 5 / G40 | P45 | E14.2 - Build standalone wheel, sdist and non-root container | B | E02.3, E14.1, E04.3 |
| 5 / G40 | P46 | E11.3 - Verify first assessment, partial run and comparison journeys | A | E11.1, E11.2, E06.3, E08.3, E10.3, E14.2 |
| 5 / G40 | P47 | E14.3 - Sign results and prove headless consumer interoperability | B | E14.2, E13.3 |
| 5 / G40 | P48 | E14.4 - Rehearse official public signing and publication preflight | B | E14.2, E00.3 |
| 5 / G40 | P49 | E15.3 - Review candidate against every Engine release gate | C | E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4, E15.2 |
| 5 / G40 | P50 | E16.1 - Freeze and sign off the exact release candidate | C | E15.3 |
| 6 / G50 | P51 | E16.2 - Publish through the authorized Engine-only route | C | E16.1 |
| 6 / G50 | P52 | E16.3 - Smoke-test published artifacts and transition the team | C | E16.2 |

A owns contracts/rules/architecture/reports; B owns facts/security/quality/privacy/trust; C owns isolation/Git/comparison/MCP and audit coordination. B has a heavier trust lane in group 5; A helps with independent artifact verification and C with qualification preparation within their assigned work. No extra staffing or calendar duration is implied. Reassign a ready story only with a recorded owner/reviewer change, and do not run two primary stories per person.

## Gate conditions after each group

| Gate | Scope | Minimum additional evidence before PASS |
|---|---|---|
| G10 | Prompts 01-10, foundations | Engine-only scope guard negative fixtures; real baseline checks; ratified shared measurement/depth/feed/history decisions; valid/invalid descriptor/envelope examples; fact/declaration identities; independent corpus/fixture manifest; actual live baseline investigation. R01 may remain an explicitly owned release blocker, not a reason to fabricate publishing readiness. |
| G20 | Prompts 01-20, runtime | No-database assess/restart/query path and retained compatibility; full bounded YAML operators and budget failures; deterministic composition/override/exception fixtures; actual candidate preview; common projections; inventory and first security vertical slices. Final signed preview admission remains E14, explicitly pending. |
| G30 | Prompts 01-30, analyzer/history | Pinned-feed vulnerability and version/license evidence; corrected ratio/graph fixtures; architecture depth, source quality, bounded Git/PR/message context and full-vs-incremental parity; automated cumulative/adversarial harness. Validate flagship confusion matrices against ratified labels. |
| G40 | Prompts 01-40, joined outcomes | Verify all E11.2 views with real complete, partial, UNKNOWN and no-baseline fixtures; run candidate build/install report smoke outside checkout, recording digest and installed assets. This is an interim install check; E14.2 official artifact qualification remains due at G50.  Source-to-test/CI evidence, maintainability join, finding lifecycle and outcome-driver mapping, change concerns, comparison cause/coverage fixtures, four-outcome local reports, narrow file-only MCP, durable opt-in and capability-gated export preparation. |
| G50 | Prompts 01-50, frozen candidate | Require E11.3/P46 report-view acceptance on independent installed wheel, sdist and container artifacts for complete, partial, UNKNOWN and no-baseline cases, with comparison drivers and canonical parity.  Full 50-repository breadth tier plus dogfood and labeled ground truth; no-consent/AI equivalence; local/private/CI execution matrix; real signature/purpose/tamper verification; independent wheel/sdist/container tests; exact candidate and all cumulative fixes. R01/R02 closed; R04/R05 later gates explicitly unpassed. Release-owner approval is still required for public publication. |
| G52 | Prompts 51-52, published artifact | Independent public-download verification, five pinned representative repositories, local CLI/MCP/reports/privacy/comparison smoke, rollback instructions and defined observation/support responsibility. Production checks cannot be simulated. |

At every checkpoint, audit **all work delivered so far**, with depth focused on the latest changes and their dependencies. Do not rerun the full 50 external repositories after every tiny fix unless that gate or a concrete regression risk requires it. Run them at E15/G50, and rerun impacted repository configurations after later fixes. Repeat all required cumulative tests on the final repaired checkpoint SHA.

### Required report-view evidence at G40 and G50

HTML must visibly present: (1) Engineering Hotspots with ranking/context labels, contributor values, priority explanations and linked findings/evidence; (2) repository/component/file ownership concentration with scope, denominator, pinned history and limitations; (3) temporal co-change with pair, support and union denominator; (4) change-summary/blast-radius counts, boundary spread/crossed-boundary pairs, affected components/tests and traversal limits; (5) per-capability coverage and freshness, including vulnerability feed and Git history with explicit UNKNOWN reasons; and (6) a Before / After / Delta table of compatible named metrics with units, scope, both coverages, outcome movement and linked qualifying/excluded drivers and cause/compatibility reasons. A first run visibly says no baseline and makes delta/movement unavailable; partial or incompatible comparisons retain qualified known observations without inventing zero, Stable or improvement. HTML projects the canonical Engine result, order, calculations and verdicts; it must never calculate its own scores, ranking, deltas or outcome movement. No new numeric score is added.

Generate reports by executing the installed Engine on pinned repository/Git/feed fixtures with independently expected real values; report screenshots or hand-authored envelopes alone do not pass. Verify every E11.2 visible view and its links against the canonical result for complete, partial, UNKNOWN and no-baseline inputs, plus compatible before/after movement and incompatible comparison. Include stale/missing vulnerability feed, shallow/missing Git history, unknown ownership mapping, impact cutoff and missing test association. Assert no synthetic zeros, healthy badges, trend or HTML-calculated score. Record installed artifact digest, canonical/result/report digests, expected/actual values, link checks and a visual review of the generated local HTML. G40 uses the current candidate build/install; G50 uses the exact qualified E14.2 release artifacts. No new prerequisite is added to P36: its report contract can be implemented independently, but the group cannot pass until its real upstream integrations and interim install checks pass.

## Audit, repair, re-audit, then proceed

1. Finish and review all ten stories in the active group; integrate them on the isolated branch. Stop new-feature work at the group boundary. Freeze the checkpoint candidate SHA and capture the last passing gate SHA plus original release baseline.
2. Run the audit prompt below in a fresh session, with another engineer reviewing the output. Compare code and executable tests against each delivered acceptance criterion, not just the completion notes.
3. Record each finding as `G20-D001` or the relevant gate prefix, with severity, story, code evidence, reproducible fixture, expected/actual behavior, owner and affected checks. Audit every test skip, baseline failure and weakened assertion or gate.
4. Run the repair prompt for each accepted gap. Patch only the missing behavior and regression tests in Engine. Add no next-group features. If review shows an item is not a defect, close it with evidence and reviewer rationale; do not silently delete it.
5. Re-run failed checks, affected dependency regressions and the cumulative mandatory suite. Re-audit the final integrated fix SHA with a different engineer reviewing. Any later code/config/catalog change invalidates the affected PASS evidence.
6. Mark the gate PASS only when every defect against delivered acceptance is repaired or evidenced as not a defect, all due checks pass and there is no unexplained skip. Out-of-scope enhancements may be deferred explicitly. Actual missing accepted behavior or trust/privacy/scope faults cannot be deferred to claim PASS.
7. Record reviewer sign-off and the exact next group unlocked. No PASS, no next group. A blocked external requirement is recorded with its owner; independent work in the current group may continue without pretending the blocked story is complete.

R01 is due at kickoff for investigation and before official signing rehearsal for operational closure. If only an outside-Engine workflow change can close it, prepare the exact operation and separate scope decision for the release owner. Keep independent Engine work moving until that dependency is required. Do not grant Cursor permission to alter root workflows merely because a batch would otherwise stop.

## Evidence record and statuses

Store reviewable summaries under `engine/docs/implementation/gates/`. Each record includes gate/story IDs, input/spec version, base/candidate/repaired SHA, dirty-state check, environment/tool versions, artifact/catalog/config/feed digests where applicable, exact commands, start/end times and exit codes, test and skip counts, coverage numerator/denominator/results, fixture provenance, defects/repairs/retests, reviewer and release decision.

Keep sensitive/raw logs in `engine/.quality-runs/<unique-run-id>/`, ignored and excluded from public export; redact before attaching any excerpt to tracked records or a PR. E00.2 may edit `engine/.gitignore` to protect these outputs. Inspect ignored outputs and export behavior rather than assuming an ignore rule is an access control. No raw customer/source/secret data belongs in public release evidence. Summaries reference private log digests/locations accessible to the authorized team.

Use `NOT_RUN`, `IN_PROGRESS`, `FAIL`, `BLOCKED`, `NOT_YET_DUE` or `PASS`; a missing command/tool is not PASS. Story states are `Not started`, `In progress`, `Ready for review`, `Integrated`, `Reopened` and `Accepted at gate`. Record dependencies against integrated reviewed SHAs, not a text label. Public-release operations also need their operational receipts, not a merged documentation PR.

Suggested gate record:

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

## Copy-ready cumulative audit prompt

Replace the bracketed fields before use; these are execution inputs, not prefilled evidence.

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

## Copy-ready repair and re-audit prompt

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

## Release and team transition

G50 authorizes preparation for publication; it is not itself publication permission. Prompt 51 runs only after the release owner approves exact qualified artifacts and R01 route. Prompt 52 verifies published bytes; it cannot be replaced by a local build or mock registry. Retain the five-repository smoke and three-business-day proposed observation window from the backlog. Once smoke passes, A/B can shift to Platform/Webapp work while C handles the defined support window. A blocking regression stops further promotion and follows the approved rollback/yank process without overwriting versions.

Webapp foundation work is a separate scope/capacity allocation. It cannot consume one of the three Engine engineers without changing the plan, and it cannot use these prompts to wire assessments or change Platform/AWS/database code. The existing data lake is retained; E13 owns consented export preparation, while actual new collector/server capability remains R05.

## Validation performed for this delivery

This 15 September 2026 document amendment preserves 17 epic IDs, 52 story IDs and 33 measurement IDs. The revised backlog and P01-P52 dependency table contain 99 hard story links; E08.3 -> E10.2 is the added link. Prerequisites remain earlier in the numbered order and the graph is acyclic; groups remain 10, 10, 10, 10, 10 and 2. This validates document structure only. The prior PDF/generator/prompt comparisons describe the earlier delivery and do not certify this revision. The master prompt book, all split prompts and execution ZIP require reconciliation and review against this revision before copying or G00 PASS. No Engine runtime or release gate was run; G10/G20/G30/G40/G50/G52 remain NOT_RUN.

No Engine implementation prompts, runtime quality commands, cloud changes, repository commits or public releases were executed by this document review. The team must produce those results as it works. Complete execution-package reconciliation before G00; future gate PASS results are deliberately empty.
