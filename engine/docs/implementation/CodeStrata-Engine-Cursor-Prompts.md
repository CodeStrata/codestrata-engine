# CodeStrata Engine Cursor Prompts

Version 1.2 | 52 story prompts | 15 September 2026

**Package revision `ENGINE-2026-09-15-R1`.** Regenerated directly from the revised backlog and measurement contract of this revision — every story-specific field (deliverable, acceptance including the 15 September amendments, allowed paths, prerequisites, measurement definitions) is sourced from those two documents, not hand-edited. Use with the revised Boundary specification, backlog, measurement contract and Team Execution and Quality Gates document, all `ENGINE-2026-09-15-R1`. Copy one numbered prompt at a time. Every prompt requires the standing policy; do not assume Cursor auto-loads a root rules file. Run G00 first. Checkpoints and repair prompts are in the companion execution document. No implementation or release has been executed by this delivery.

## Numbered index

| Group / Gate | Prompt | Story | Owner | Hard prerequisites |
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
| 1 / G00 | P10 | E15.1 - Pin corpus manifests and independent labeled fixtures | C (coordination); A/B own their defects | E00.2, E01.1 |
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
| 3 / G20 | P30 | E15.2 - Automate deterministic and adversarial regression checks | C (coordination); A/B own their defects | E15.1, E03.3, E02.3 |
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
| 5 / G40 | P49 | E15.3 - Review candidate against every Engine release gate | C (coordination); A/B own their defects | E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4, E15.2 |
| 5 / G40 | P50 | E16.1 - Freeze and sign off the exact release candidate | C | E15.3 |
| 6 / G50 | P51 | E16.2 - Publish through the authorized Engine-only route | C | E16.1 |
| 6 / G50 | P52 | E16.3 - Smoke-test published artifacts and transition the team | C | E16.2 |

## Prompt sections

## P01 - E00.2: Create Engine-only scope and compatibility guards

**Owner:** C | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E00.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: none. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation; engine/pyproject.toml; engine/.gitignore.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Engine-owned check plus PR checklist: changed tracked files must remain under engine/. Record clean baseline checks and outside-Engine consumer imports read-only.

### Acceptance criteria

Guard rejects edits, renames or deletions outside engine/, including root scripts, workflows, lockfiles and export manifest. Tests run through the existing engine-tests job. Baseline failures are recorded separately; they cannot be relabeled as new passing tests. No production publish credentials in normal tests. Establish the executable quality-command manifest and cumulative scope guard from the first story, not only at E15. Record full lint/type/test/coverage results and baseline failures. Inspect added/untracked files, rename source and destination, deletions, staged and unstaged changes and the cumulative release diff; compare against the pre-existing working-tree inventory without resetting unrelated work. Place checks in engine/verification and collect appropriate scope regression tests through the existing test path. Record reviewer and gate evidence under engine/docs/implementation. The existing root engine-tests command is not proof of lint/type/coverage execution; mandatory local or authorized-runner evidence is required until an existing compatible runner executes those checks. Do not edit root CI.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P01 of 52, not a whole epic or a release authorization.

## P02 - E01.1: Ratify launch measurements and depth matrix

**Owner:** A | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E01.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: none. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Adopt the companion Measurement, Metrics & Evidence Contract; record formula/default changes before analyzer coding. Close launch depth, feed source/freshness, history and budget choices in an Engine-owned decision file.

### Acceptance criteria

Every M01-M33 has inputs, formula, subject, evidence, missing-data behavior and fixtures. Java and JS/TS are the proposed deepest paths; Python/PHP/C# retain only verified tiers. Thresholds below are proposed engineering defaults, not calibrated universal standards. No broad product redefinition. Ratify the revised M06/M09/M12 denominators, M24 history/message indicators, M27 supplied context, M29 change-concern predicate and M28-M30 lifecycle/outcome-driver manifest. Close numeric hard deadlines, cancellation grace, regex/memory/file/output limits and the supported depth/feed/profile choices before their affected stories. Map existing rule IDs, confidence taxonomy and context-derived severity to the new contract: do not invent an incompatible ID restriction or retain a hidden severity rewrite after an approved override. Record each decision and independent reviewer; Cursor cannot self-ratify proposed defaults. Ratify M22 ranking/context roles, M25 scoped denominators, M27/M29 boundary definitions and report-facing coverage/freshness reasons before implementation; preserve the no-opaque-score decision. Propagate this revision into P02 and affected prompts before G00.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P02 of 52, not a whole epic or a release authorization.

## P03 - E05.1: Inventory existing extractors and pin supported depth

**Owner:** B | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E05.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: none. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Reuse/deepen Java, JS/TS, Python, PHP and C# providers; fixture map for build/manifests, language and source classification.

### Acceptance criteria

Count detection separately from structural support. Map actual parser outputs to facts; unsupported syntax/frameworks stay declared. Do not install dependencies or execute tests, hooks, package scripts or builds to discover evidence. Early discovery has no dependency on completed runtime.

### Measurement definitions

#### M01 - Repository classification and scope

**Family / outcome:** Inventory / Context

**Inputs and scope:** Source tree, exclusions, manifests

**Definition and calculation:** Count files by mutually exclusive primary class: source/test/config/infra/docs/generated/vendor/binary/unknown. Supported fraction = supported eligible files / eligible files; publish numerator and denominator. Ignored files stay in scope inventory.

**Rule, threshold and interpretation:** No health verdict; classification metric only. Zero eligible files => NOT_APPLICABLE.

**Required evidence:** Normalized relative path, content digest, classifier version, ignore reason and manifest location.

**Missing/partial behavior:** Unreadable/dynamic regions classified unknown; a detection count does not prove structural support.

**Required fixtures:** Mixed-language; generated/vendor; symlink escape; binary; empty repo; unreadable subtree.

**Owning stories:** E05.1, E05.2, E05.3.

#### M02 - Technology, component and dependency inventory

**Family / outcome:** Inventory / Context

**Inputs and scope:** Manifests, lockfiles, source roots, build configuration

**Definition and calculation:** Distinct normalized technology/component records with evidence; dependency count separately by declared coordinate and resolved package identity/version. Edges retain directness and resolution status.

**Rule, threshold and interpretation:** No invented health score. Parseable unsupported ecosystem is disclosed as detection-only.

**Required evidence:** Manifest/lock location, ecosystem/package identity, source roots, parser version.

**Missing/partial behavior:** Missing resolution cannot be represented as no dependencies; unsupported manifests UNKNOWN for dependency depth.

**Required fixtures:** Maven/npm resolved vs missing lock; Composer/NuGet lower tiers; workspace packages; duplicate coordinates.

**Owning stories:** E05.1, E05.2, E05.3.

#### M03 - Configured build and CI checks

**Family / outcome:** Inventory / Context

**Inputs and scope:** CI/build/config source

**Definition and calculation:** For each configured job/step record literal or safely parsed command, condition, tool category and target. Counts: test/coverage/lint/security invocations statically observed.

**Rule, threshold and interpretation:** Descriptive only; observed configuration never means the job ran or passed.

**Required evidence:** CI path/line, literal command, condition, deterministic parser rule.

**Missing/partial behavior:** Indirect scripts or unknown expressions => unresolved invocation, not absent check.

**Required fixtures:** Direct command; conditional job; delegated script; no CI; malformed YAML.

**Owning stories:** E05.1, E05.2, E05.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P03 of 52, not a whole epic or a release authorization.

## P04 - E00.1: Record the live artifact and release route

**Owner:** C | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E00.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: none. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Record current PyPI/container/mirror versions, immutable digests, stable branch/tag and release identities in engine/docs/release/baseline.md. Inventory the existing authorized publisher as prerequisite R01.

### Acceptance criteria

Do not infer live version from pyproject 0.2.1 or tags. Verify install/rollback using the actual released artifact. Identify which workflow can obtain the required OIDC identity and publish Engine alone. If none exists, R01 is blocked, not assumed solved. No workflow, export-manifest or remote changes in this story.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P04 of 52, not a whole epic or a release authorization.

## P05 - E01.2: Publish versioned descriptors, facts, IDs and envelopes

**Owner:** A | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E01.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E01.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

AnalyzerDescriptor plus neutral assessment/fact/graph/evidence schemas, stable identity, canonical serialization profile and complete example artifact set.

### Acceptance criteria

Descriptor includes reads/emits, applicability, depth, schemas, budgets, network, coverage and failures. Envelope separates deterministic body from time/signature/run metadata. No tenant/workspace/portfolio/job identity in analysis body. Existing subject/finding identity is mapped deliberately; unknown fields and unsupported major versions reject. Publish the launch outcome-driver manifest with rule/metric ID, family, outcome/context role, applicability, direction, comparison unit, epsilon, coverage requirement and empty-scope behavior. Canonical required scopes and known violations cannot disappear through aggregation. Bind any source-derived context severity choice into the versioned rule/default/config contract; preserve default/effective severity and approved override provenance. Publish the first-class M22 Engineering Hotspot schema, scoped M25 records, M27/M29 change-summary fields and per-capability coverage/freshness schema with complete, partial, UNKNOWN and no-baseline example envelopes. Validate contributor roles, evidence/finding references and canonical priority explanation. P05 must carry these requirements.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P05 of 52, not a whole epic or a release authorization.

## P06 - E02.1: Trace active SQLite, hosted and portfolio call paths

**Owner:** C | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E02.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E00.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Map CLI/assess/compare/MCP/provider factory imports, installed dependencies and current persisted snapshots. Classify each old surface: retain, adapt, deprecate or quarantine.

### Acceptance criteria

Trace runtime composition as well as imports: factory.py currently constructs SqliteKnowledgeStore. Record Platform/extension consumers before narrowing interfaces. Do not copy code into platform/ or workers/. Historical code may remain isolated only if absent from supported runtime and default package dependency closure.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P06 of 52, not a whole epic or a release authorization.

## P07 - E05.2: Emit source, dependency, API and CI facts with coverage

**Owner:** B | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E05.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E01.2, E05.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Stable repository/component/file/symbol IDs; manifest and lock facts; static import/API/config/build/CI observations; classification and evidence references.

### Acceptance criteria

Preserve declared vs resolved dependencies; missing lockfile is not resolved absence. Evidence includes exact local source revision/content digest and location. Symlink escape, huge/binary/generated/vendor files and parse failure produce bounded, visible scope. CI command found in YAML proves configuration, not successful execution. Use declaration IDs as the unit for dependency-resolution coverage and preserve resolution occurrences separately. For normalized change facts, expose stable file/component mapping before E09.3 closes.

### Measurement definitions

#### M01 - Repository classification and scope

**Family / outcome:** Inventory / Context

**Inputs and scope:** Source tree, exclusions, manifests

**Definition and calculation:** Count files by mutually exclusive primary class: source/test/config/infra/docs/generated/vendor/binary/unknown. Supported fraction = supported eligible files / eligible files; publish numerator and denominator. Ignored files stay in scope inventory.

**Rule, threshold and interpretation:** No health verdict; classification metric only. Zero eligible files => NOT_APPLICABLE.

**Required evidence:** Normalized relative path, content digest, classifier version, ignore reason and manifest location.

**Missing/partial behavior:** Unreadable/dynamic regions classified unknown; a detection count does not prove structural support.

**Required fixtures:** Mixed-language; generated/vendor; symlink escape; binary; empty repo; unreadable subtree.

**Owning stories:** E05.1, E05.2, E05.3.

#### M02 - Technology, component and dependency inventory

**Family / outcome:** Inventory / Context

**Inputs and scope:** Manifests, lockfiles, source roots, build configuration

**Definition and calculation:** Distinct normalized technology/component records with evidence; dependency count separately by declared coordinate and resolved package identity/version. Edges retain directness and resolution status.

**Rule, threshold and interpretation:** No invented health score. Parseable unsupported ecosystem is disclosed as detection-only.

**Required evidence:** Manifest/lock location, ecosystem/package identity, source roots, parser version.

**Missing/partial behavior:** Missing resolution cannot be represented as no dependencies; unsupported manifests UNKNOWN for dependency depth.

**Required fixtures:** Maven/npm resolved vs missing lock; Composer/NuGet lower tiers; workspace packages; duplicate coordinates.

**Owning stories:** E05.1, E05.2, E05.3.

#### M03 - Configured build and CI checks

**Family / outcome:** Inventory / Context

**Inputs and scope:** CI/build/config source

**Definition and calculation:** For each configured job/step record literal or safely parsed command, condition, tool category and target. Counts: test/coverage/lint/security invocations statically observed.

**Rule, threshold and interpretation:** Descriptive only; observed configuration never means the job ran or passed.

**Required evidence:** CI path/line, literal command, condition, deterministic parser rule.

**Missing/partial behavior:** Indirect scripts or unknown expressions => unresolved invocation, not absent check.

**Required fixtures:** Direct command; conditional job; delegated script; no CI; malformed YAML.

**Owning stories:** E05.1, E05.2, E05.3.

#### M04 - API and configuration surfaces

**Family / outcome:** Inventory / Context

**Inputs and scope:** Supported source AST and config

**Definition and calculation:** Distinct statically declared API entrypoints/config/deployment surfaces keyed by source subject and declaration kind.

**Rule, threshold and interpretation:** No runtime availability or observability score.

**Required evidence:** Declaration symbol/path/line and extraction capability.

**Missing/partial behavior:** Dynamic routing/framework unsupported => UNKNOWN area with detected-only inventory if available.

**Required fixtures:** Supported route; no routes; dynamic route; generated config; unresolved framework.

**Owning stories:** E05.2, E05.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P07 of 52, not a whole epic or a release authorization.

## P08 - E01.3: Publish rules, comparison and neutral invocation contracts

**Owner:** A | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E01.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E01.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Rule, RuleSet, Effective RuleSet, signed-package manifest, comparison envelope and headless local job schemas. Supply good/bad consumer examples under engine/tests/contracts.

### Acceptance criteria

Bind resolved ruleset/package/config/feed/input digests and versions; preview purpose is distinct. Compare schema preserves compatibility and cause attribution. Invocation accepts local paths, pinned inputs and export/trust configuration, not Platform credentials. Validate independently installed wheel without importing Platform. Include bounded optional locally supplied PR title/description/base/head/labels/linked-reference strings and their supplied provenance/context digest. Define neutral candidate-validation and preview inputs/results, permitted scope, purpose and expiry, plus local progress/cancellation/terminal-state schema. No hosted calls or approval identities enter canonical computation.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P08 of 52, not a whole epic or a release authorization.

## P09 - E00.3: Establish integration, hotfix and prerelease isolation

**Owner:** C | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E00.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E00.1, E00.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Document release/engine-next integration branch, short epic branches, one stable maintenance lane and versioned candidate artifact/output namespaces.

### Acceptance criteria

Existing CI push pattern covers release/**. Normal merges do not publish or move stable tags. Candidate installs use a separate virtual environment and local output directory, never upgrade live installs or rewrite existing snapshots. Backport live hotfixes deliberately into next; preserve exact rollback artifacts.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P09 of 52, not a whole epic or a release authorization.

## P10 - E15.1: Pin corpus manifests and independent labeled fixtures

**Owner:** C (coordination); A/B own their defects | **Group:** 1 | **Required preceding gate:** G00 PASS

### Start instructions

Implement only E15.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G00 PASS on a recorded reviewed SHA and direct prerequisites: E00.2, E01.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Three tiers: CodeStrata dogfood, >=50 large identified external repositories, and labeled flagship ground truth. Store URL/SHA/license/size/language, window, inputs and expectations.

### Acceptance criteria

Five early representatives: supported Java, JS/TS, mixed build/monorepo, retained lower-depth stack, and partial/unsupported case. Select all 50 with explicit scale/diversity criteria; no duplicate clones or convenience replacement to hide failures. Fixture labels precede tuning. Public scan is read-only; no repository code changes. Prepare corpus manifests and independent fixture labels early; existing 22-repository documentation is a discovery lead, not evidence that it meets the 50-large-repository bar. Create checkpoint evidence and defect-ledger templates. Keep public-reproducible inputs under engine/verification/validation and engine/tests without private/customer content.

### Measurement definitions

#### M33 - Coverage, determinism and performance acceptance

**Family / outcome:** Cross-cutting / Validation

**Inputs and scope:** All artifacts, capability records and corpus manifests

**Definition and calculation:** Per capability: evaluated eligible units / all eligible units; separately unknown/not-applicable/excluded/error. Runtime wall duration/peak RSS on declared host. Three-repeat semantic digest equality. Also record local health/progress/terminal states, hard deadlines/cancellation grace, peak output/disk usage and retention behavior. Freeze numerical bounds before affected qualification; failed/unrun checks are never recorded as PASS.

**Rule, threshold and interpretation:** Proposed initial tiers: <=10k eligible files 10min/2GiB; <=100k 30min/8GiB on 4vCPU. Measure/tune before publication; exceeding budget never silently truncates success.

**Required evidence:** Per-repo SHA/config/feed/hardware, counts, resource logs and semantic hashes.

**Missing/partial behavior:** Unknown denominator => coverage unknown. A survival run is not proof of analytical correctness.

**Required fixtures:** Dogfood; >=50 identified large repos; labeled flagship subset; resource exhaustion; corruption; repeat variation. SIGINT/SIGTERM/hard kill; disk full; output collision; concurrent reader; retention preserving active baseline; audit redaction.

**Owning stories:** E15.1, E15.2, E15.3.

**Report acceptance:** Per-capability coverage/freshness records defined above must survive JSON and HTML projection, including vulnerability-feed and Git-history reasons. Verify the visible report views in E11.2 and installed-artifact journeys in E11.3/P46 at G50; G40 verifies the delivered report projection and candidate-install smoke. A rendered healthy-looking empty table cannot substitute for explicit UNKNOWN or no-baseline behavior.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P10 of 52, not a whole epic or a release authorization.

## P11 - E02.2: Implement bounded file artifact storage and queries

**Owner:** C | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E02.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E01.2, E02.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Atomic versioned JSON/JSONL manifests, bounded indexes, integrity checks, streaming reads and query ports; replace production factory composition.

### Acceptance criteria

Fresh wheel can assess, restart, open evidence and compare offline with sqlite3.connect blocked and no DB drivers/services. Interrupted writes do not expose partial completed snapshots. Limit memory, reject path escapes, detect corrupt/missing blobs; rebuild derived indexes from valid manifests. No destructive auto-migration. Prove interruption, concurrent output collision, concurrent readers, disk-full behavior, local retention/cleanup and protection of source, supplied baselines and unrelated files. Expose a completed manifest only after atomic finalization. Preserve safe incomplete status; never sign killed/partial output as successful completion. Support local status/health without an HTTP service or database.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P11 of 52, not a whole epic or a release authorization.

## P12 - E03.1: Validate YAML and compile typed selector ASTs

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E03.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E01.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Safe loader, schema/capability validation, pinned selector binding and serializable intermediate plan.

### Acceptance criteria

Reject duplicate keys, unknown tags/fields, executable strings, alias expansion, invalid types and excessive nesting/bytes. No eval/import/shell/network/file operator. Unsupported facts or operators return a structured capability error. A selector change cannot masquerade as presentation metadata.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P12 of 52, not a whole epic or a release authorization.

## P13 - E04.1: Implement pinned composition and deterministic precedence

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E04.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E01.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Pure in-memory/file RuleSet resolver plus release-time pre-resolution command for bundled catalog.

### Acceptance criteria

Reject missing/cyclic/floating references and excessive size/depth. Later ordered parents override earlier configuration; explicit child revision resolves parent revision conflict. Maps merge by defined fields; lists/scalars replace, omitted inherits, null is not reset. Conflicting selector ASTs cannot shadow. Resolve identical input bytes deterministically.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P13 of 52, not a whole epic or a release authorization.

## P14 - E02.3: Narrow Engine surfaces and preserve supported compatibility

**Owner:** C | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E02.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E02.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Remove active portfolio/EIR/hosted submission/strategic-agent paths from Community execution. Keep small Engine-local compatibility projections only where safe; document deprecated commands and old snapshot export.

### Acceptance criteria

No Platform calls from canonical runtime; no customer rule authoring or portfolio lifecycle through CLI/MCP. Legacy SQLite export, if needed, is a separately invoked maintainer helper, never imported by the runtime. Read-only outside-Engine consumer checks identify breaking contracts; do not fix them by editing outside engine/. Old files and prior installs remain untouched.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P14 of 52, not a whole epic or a release authorization.

## P15 - E03.2: Implement the declared bounded operator set

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E03.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E03.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Typed selection, numeric/set, graph, change and threshold operators listed in Engine §5, with truth tables and cost limits.

### Acceptance criteria

Direct traversal is depth 1; transitive has positive bounded max_depth. declared/resolved dependency view is independent. UNKNOWN propagates under three-valued evaluation; a cutoff never proves absence. Empty/zero denominators, numeric rounding, percentile definition and cycle behavior match the measurement contract. Every operator has positive, negative and budget fixtures.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P15 of 52, not a whole epic or a release authorization.

## P16 - E04.2: Apply typed overrides and resolved scoped exceptions

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E04.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E04.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Bounded typed override model for severity, enabled, exposed parameters, presentation fields and pre-authorized subject scope.

### Acceptance criteria

Reject off as severity, out-of-range parameters and executable messages. Selector/schema/operator changes require new rule revision. Deduplicate equal cross-policy effective rules retaining opaque attributions; reject conflicting revisions/settings and overlapping exception values. Only opaque references and resolved local subject scopes reach Engine; no approver, organization or workspace authority model.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P16 of 52, not a whole epic or a release authorization.

## P17 - E03.3: Enforce execution budgets and common emission semantics

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E03.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E03.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Planner/executor integration, per-rule/workload budgets, cancellation, evidence validation and minimal generic JSON/HTML/SARIF projections. These common adapters land here; E11 improves the complete CLI/report experience.

### Acceptance criteria

No legacy Python rule evaluate() path in launch catalog; trusted Python extractors/operators remain allowed. Malicious regex/graph/input fixtures terminate within configured budgets. FAIL is a supported violation; ERROR is processing failure. Disabled/suppressed scope remains visible. Same effective plan and facts yield identical results. Freeze numeric hard limits and cancellation behavior from E01.1; enforce process-level termination for pathological regex/native parsing as appropriate. Prove timeout/grace/termination and bounded diagnostics. No deadline may depend solely on a cooperative in-process callback. Add preview execution parity through the same compiler and operators; purpose checks integrate with E14.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P17 of 52, not a whole epic or a release authorization.

## P18 - E05.3: Close the inventory vertical slice

**Owner:** B | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E05.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E05.2, E03.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Capability manifests and inventory/coverage projections through common envelope and report adapters.

### Acceptance criteria

All M01-M04 fixtures cover valid/absent/partial/unsupported/corrupt/deterministic cases. Inventory supplies no invented health score. Every enabled analyzer sees compatible registered facts. No parser-specific logic required by the consumer contract.

### Measurement definitions

#### M01 - Repository classification and scope

**Family / outcome:** Inventory / Context

**Inputs and scope:** Source tree, exclusions, manifests

**Definition and calculation:** Count files by mutually exclusive primary class: source/test/config/infra/docs/generated/vendor/binary/unknown. Supported fraction = supported eligible files / eligible files; publish numerator and denominator. Ignored files stay in scope inventory.

**Rule, threshold and interpretation:** No health verdict; classification metric only. Zero eligible files => NOT_APPLICABLE.

**Required evidence:** Normalized relative path, content digest, classifier version, ignore reason and manifest location.

**Missing/partial behavior:** Unreadable/dynamic regions classified unknown; a detection count does not prove structural support.

**Required fixtures:** Mixed-language; generated/vendor; symlink escape; binary; empty repo; unreadable subtree.

**Owning stories:** E05.1, E05.2, E05.3.

#### M02 - Technology, component and dependency inventory

**Family / outcome:** Inventory / Context

**Inputs and scope:** Manifests, lockfiles, source roots, build configuration

**Definition and calculation:** Distinct normalized technology/component records with evidence; dependency count separately by declared coordinate and resolved package identity/version. Edges retain directness and resolution status.

**Rule, threshold and interpretation:** No invented health score. Parseable unsupported ecosystem is disclosed as detection-only.

**Required evidence:** Manifest/lock location, ecosystem/package identity, source roots, parser version.

**Missing/partial behavior:** Missing resolution cannot be represented as no dependencies; unsupported manifests UNKNOWN for dependency depth.

**Required fixtures:** Maven/npm resolved vs missing lock; Composer/NuGet lower tiers; workspace packages; duplicate coordinates.

**Owning stories:** E05.1, E05.2, E05.3.

#### M03 - Configured build and CI checks

**Family / outcome:** Inventory / Context

**Inputs and scope:** CI/build/config source

**Definition and calculation:** For each configured job/step record literal or safely parsed command, condition, tool category and target. Counts: test/coverage/lint/security invocations statically observed.

**Rule, threshold and interpretation:** Descriptive only; observed configuration never means the job ran or passed.

**Required evidence:** CI path/line, literal command, condition, deterministic parser rule.

**Missing/partial behavior:** Indirect scripts or unknown expressions => unresolved invocation, not absent check.

**Required fixtures:** Direct command; conditional job; delegated script; no CI; malformed YAML.

**Owning stories:** E05.1, E05.2, E05.3.

#### M04 - API and configuration surfaces

**Family / outcome:** Inventory / Context

**Inputs and scope:** Supported source AST and config

**Definition and calculation:** Distinct statically declared API entrypoints/config/deployment surfaces keyed by source subject and declaration kind.

**Rule, threshold and interpretation:** No runtime availability or observability score.

**Required evidence:** Declaration symbol/path/line and extraction capability.

**Missing/partial behavior:** Dynamic routing/framework unsupported => UNKNOWN area with detected-only inventory if available.

**Required fixtures:** Supported route; no routes; dynamic route; generated config; unresolved framework.

**Owning stories:** E05.2, E05.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P18 of 52, not a whole epic or a release authorization.

## P19 - E06.1: Migrate and validate secret and configuration rules

**Owner:** B | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E06.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E05.2, E03.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Convert applicable existing eight hygiene rules into bundled YAML; deepen verified patterns and redact before any persisted evidence or diagnostics.

### Acceptance criteria

Known real-format synthetic keys, placeholders and safe lookalikes have distinct expected behavior. Raw secret values never appear in reports, logs, telemetry, fixture output snapshots or MCP output. TLS/auth/CORS/debug findings cite exact supported configuration evidence, without runtime exploitability claims. Reuse security context classification as evidence only where supported; reconcile any old severity/confidence adjustment with the immutable rule contract. A post-processing stage must not silently override approved effective severity or alter canonical rules outside the YAML runtime.

### Measurement definitions

#### M10 - Secret and private-key findings

**Family / outcome:** Security / Security

**Inputs and scope:** Supported source/config literal evidence

**Definition and calculation:** Count unique rule + source-subject + occurrence findings after supported placeholder classification. Lower favorable. Keep identity independent of raw secret bytes.

**Rule, threshold and interpretation:** security.secret/private_key: high or critical per reviewed bundled rule; no raw value retention.

**Required evidence:** Path/line, detector ID, safe secret type and redacted span.

**Missing/partial behavior:** Unsupported encoding/language prevents clean claim for that scope; never scan full Git history by default.

**Required fixtures:** Synthetic valid-format key; placeholder; encoded/unsupported; duplicate literal; zero raw-secret canary leakage.

**Owning stories:** E06.1.

#### M11 - Insecure configuration findings

**Family / outcome:** Security / Security

**Inputs and scope:** Static supported TLS/auth/CORS/debug config

**Definition and calculation:** Separate counts for disabled verification/auth, permissive CORS and debug production configuration; exact production context must be evidenced.

**Rule, threshold and interpretation:** Each condition is a named YAML rule with default severity migrated/reviewed from current catalog. No generic runtime exploitability claim.

**Required evidence:** Config path/line/value classification and context evidence.

**Missing/partial behavior:** Unknown environment/indirect config => UNKNOWN context, not assumed production.

**Required fixtures:** True/false settings; placeholder; conditional environment; conflicting configuration; unsupported expression.

**Owning stories:** E06.1.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P19 of 52, not a whole epic or a release authorization.

## P20 - E04.3: Seal the effective digest and prove execution parity

**Owner:** A | **Group:** 2 | **Required preceding gate:** G10 PASS

### Start instructions

Implement only E04.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G10 PASS on a recorded reviewed SHA and direct prerequisites: E04.2, E03.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Canonical resolved bytes/digest with resolver/DSL/capability versions, defaults, scoped settings and attribution. Integrate prebuilt Community packages and neutral customer-package fixtures.

### Acceptance criteria

Compare reviewed candidate and resolved production bytes. Expiry cannot exceed included exception validity; time is supplied as execution context and admission records it separately. Changing parent order/effective settings changes digest; changing rendered message never changes finding fingerprint. Local parameters hash separately from signed base. Preview never silently becomes production. Execute candidate compliant/violating/UNKNOWN fixtures and permitted snapshot previews through a neutral local entrypoint using the production compiler/operators. Return typed diagnostics, expected/actual fixture outcomes, coverage and preview-only results bound to candidate/selector/effective-setting/input/Engine/DSL digests. Stale preview evidence, parameter changes, selector rebinding, scope violations and attempted production promotion must fail the applicable checks. Approval remains Platform-owned; no customer-authoring Community CLI surface.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P20 of 52, not a whole epic or a release authorization.

## P21 - E09.1: Pin working, staged, range and patch input states

**Owner:** C | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E09.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E01.3, E02.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Read-only Git input resolver and local-state digests; preserve base/head/tree/index/patch identity without mutating the checkout.

### Acceptance criteria

Working-tree/staged mode, rename, binary, shallow history, missing base, submodules and supplied patch fixtures are explicit. Never fetch silently or switch branch. A patch without resolvable base may supply changed-line facts but not a fabricated full comparison. No PR comments/checks or hosted GitHub integration. Accept optional bounded supplied PR metadata through E01.3, without GitHub/ticket lookup. Conflicting base/head context is visible; narrative context is untrusted and cannot change canonical facts/findings/verdicts. Test absent/oversized/malformed/injection text, base/head mismatch and context-only changes. Escape projections and exclude raw metadata from anonymous telemetry.

### Measurement definitions

#### M27 - Change size, spread and test touch

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Explicit working/index/base-head/patch inputs

**Definition and calculation:** Count changed text lines, files and mapped components. test_touch = whether changed set contains known test/config-test units, separately from impacted-unit association. Optional supplied PR title/description/base/head SHAs/labels/linked-reference strings live in a bounded context record with supplied provenance/digest. Context must agree with claimed source revisions or disclose conflict. No hosted lookup; context narrative never proves code behavior. Narrative-only changes leave canonical analysis identical.

**Rule, threshold and interpretation:** Descriptive; missing test touch is not proof changes are untested.

**Required evidence:** Diff hunks, state digests, file classes and component IDs.

**Missing/partial behavior:** Unresolvable patch base or binary changes preserve partial size/impact limits.

**Required fixtures:** Staged vs working; rename; add/delete; binary; patch missing base; test-only diff. Absent/valid/oversized/malformed PR metadata; injection text; SHA conflict; context-only change; telemetry exclusion and escaped rendering.

**Owning stories:** E09.1, E09.3.

**Explicit change-summary fields:** Publish changed-file and changed-component IDs/counts, unmapped changed-file count and mapping coverage, plus architecture-boundary spread when declared M07 boundary membership is available: the distinct declared boundary-member IDs containing changed subjects, with count and mapping evidence. Identify the boundary dimension/profile (for example layers); do not combine dimensions or infer architectural boundaries from folder names. Missing declarations/membership is UNKNOWN, not zero crossed boundaries. E09 emits the changed-scope facts; E10.2 joins architecture facts and publishes the boundary/impact summary under M29.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P21 of 52, not a whole epic or a release authorization.

## P22 - E06.2: Implement resolved supply-chain and vulnerability matching

**Owner:** B | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E06.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E05.2, E03.3, E01.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Normalize selected feed to pinned local snapshots; deterministic package/version/range matching, alias deduplication and direct/transitive path evidence.

### Acceptance criteria

Feed provider/license/freshness decision is closed before this story. Offline cache absence/staleness reports UNKNOWN for matching scope, never zero CVEs. Test withdrawn advisories, aliases, prereleases, unsupported version schemes, missing lock roots and transitive paths. No mandatory live lookup during canonical evaluation. For M12, count fully resolved eligible declarations divided by eligible declarations in the same declared contexts. Multiple resolved versions/transitive packages cannot inflate coverage above one. Test partial contexts, one declaration/multiple versions, missing locks, zero and unknown denominator.

### Measurement definitions

#### M12 - Resolved dependency and version hygiene

**Family / outcome:** Security / Security

**Inputs and scope:** Manifest declarations and available lock resolution

**Definition and calculation:** Resolution coverage = fully resolved eligible declaration IDs / all eligible declaration IDs in the same manifest/workspace/environment scope. Count each declaration once; all required contexts must be established to count complete. Resolved package/version occurrences and transitive inventory are separate counts. A known positive denominator with none resolved gives 0 coverage plus missing-resolution status; unknown denominator UNKNOWN; zero eligible declarations NOT_APPLICABLE. Count mutable/unbounded/unresolved/duplicate/conflicting declarations separately.

**Rule, threshold and interpretation:** Named dependency YAML rules retain audited IDs/defaults; missing version evidence is a gap, not a safe dependency.

**Required evidence:** Declaration and lock paths, package coordinates, direct/transitive dependency path.

**Missing/partial behavior:** Unknown ecosystem/range resolution yields UNKNOWN; never install packages to infer resolution.

**Required fixtures:** Pinned vs wildcard; duplicate/conflict; lock mismatch; transitive package; unknown version scheme. One declaration/two resolved versions/transitive packages; partly resolved contexts; zero/unknown denominator; no ratio above one.

**Owning stories:** E06.2.

#### M13 - Known vulnerability matches

**Family / outcome:** Security / Security

**Inputs and scope:** Resolved package versions + pinned vulnerability feed

**Definition and calculation:** Count distinct canonical advisory alias-group + ecosystem/package/version identities; retain all dependency paths without multiplying finding count. Lower favorable for same feed.

**Rule, threshold and interpretation:** security.known_vulnerability uses deterministic feed severity; missing severity remains unknown and visible. Explicit configured fallback, if any, must be versioned.

**Required evidence:** Advisory ID/aliases/range/source snapshot digest/time plus resolved package/path.

**Missing/partial behavior:** No fresh supported feed or no exact version => UNKNOWN matching scope. Zero matches means none in that snapshot, not secure.

**Required fixtures:** Affected/unaffected versions; withdrawn advisory; alias dedupe; prerelease boundary; stale feed; same code/new advisory.

**Owning stories:** E06.2.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P22 of 52, not a whole epic or a release authorization.

## P23 - E07.1: Normalize structural edges and cycle metrics

**Owner:** A | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E07.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E05.2, E03.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Observed/declared edge types, stable graph IDs, module SCC cycle count and coupling metrics through YAML rules.

### Acceptance criteria

Implement imports, depends_on, implements, exposes_API and uses_dependency only at supported confidence/depth. Call edges remain limited to reliable cases. No cross-repository/runtime-topology inference. Cycle and coupling fixtures include unresolved edges and partial source roots.

### Measurement definitions

#### M05 - Module dependency cycles

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Resolved module graph

**Definition and calculation:** Number of strongly connected components of size >1 plus single-node self-loops, each reported once; include member IDs and witness edges. Lower is favorable.

**Rule, threshold and interpretation:** arch.cycles: FAIL when count >0, default medium; incomplete negative graph cannot PASS.

**Required evidence:** Observed module edges and source locations, SCC membership and witness path.

**Missing/partial behavior:** Known cycle can FAIL despite unrelated unknown edges; absent cycle needs complete relevant edge coverage.

**Required fixtures:** A->B->A; acyclic A->B; self-loop; unresolved import; reordered file traversal.

**Owning stories:** E07.1, E07.3.

#### M06 - Cross-module coupling

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module import/depends_on graph

**Definition and calculation:** Per module fan_in/out = distinct other modules using/used by it. For the file import-edge view, external-edge ratio = distinct eligible resolved file import edges whose endpoint component IDs differ / all eligible resolved file import edges with both endpoint component IDs known in the same scope. Include same-component edges in the denominator; exclude duplicate edges. Publish unresolved/unmapped exclusions and coverage. Lower fan_out favorable only under the same scope; ratio is descriptive.

**Rule, threshold and interpretation:** arch.fan_out: default threshold 10 distinct modules, medium, declared configurable; ratio descriptive.

**Required evidence:** Module edge IDs and denominator.

**Missing/partial behavior:** Zero edges ratio NOT_APPLICABLE; unresolved imports make count lower-bound and no confident threshold PASS.

**Required fixtures:** Boundary at 10/11; duplicate edges; zero edges; unknown imports.

**Owning stories:** E07.1, E07.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P23 of 52, not a whole epic or a release authorization.

## P24 - E09.2: Create bounded history index and temporal metrics

**Owner:** C | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E09.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E09.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Single-pass JSONL/file index for commits, renames, file/component churn, recency, ownership concentration and co-change.

### Acceptance criteria

Default window and merge/rename policy are pinned. Shallow/truncated history advertises exact observed bounds. Identity is repository-local and respects pinned mailmap policy; no organization attribution. Parse rename/numstat deterministically; binary sizes remain unknown. Use the ratified M24 history traversal/time/merge policy, with exact observed bounds, pinned UTC evaluation time and deterministic ties. Never silently combine first-parent traversal with skipping all merges. Implement bounded versioned commit-message bug-fix markers as context only, with observed commit evidence and no verified-defects/intent/productivity claims. Test merge-only integration, squash, future timestamps, boundary and shallow history. P24/P28 must implement and verify M25 repository/component/file concentration using subject-local attributable-line denominators, pinned identities/history and mapping coverage. Preserve M26 temporal co-change/support semantics. Expose observed/requested history bounds and freshness/UNKNOWN reasons for each Git-derived capability; no organizational bus-factor or productivity claim.

### Measurement definitions

#### M24 - Churn and recency

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Pinned local Git history and rename policy

**Definition and calculation:** Per file/component sum added+deleted text lines in included commits; recency uses pinned UTC evaluation_time and the recorded latest valid included commit time. Proposed v1 history profile for E01.1 ratification: all non-merge commits reachable from pinned head, bounded by UTC committer timestamp within the last 180 days and then latest 1000, ordered timestamp descending then SHA. Root commits compare to empty tree; non-root commits to their sole parent. Merge-only conflict-resolution edits are excluded and must be disclosed; a later first-parent-diff profile is a different version. Never combine first-parent-only traversal with skipping merges without disclosing lost coverage. Future timestamps are invalid for recency and disclosed. A separate contextual bug-fix marker counts included commit messages matching a ratified bounded versioned marker set; it does not count proven bugs fixed.

**Rule, threshold and interpretation:** Descriptive only. E01.1 ratifies traversal/merge/time/marker defaults before E09 implementation. Message markers never influence a defect, productivity or authorship verdict.

**Required evidence:** Commit SHA/time, numstat, rename map and exact window.

**Missing/partial behavior:** Shallow/absent history => partial/UNKNOWN full-window measurement; binary churn unknown.

**Required fixtures:** Known edits; rename; merge; binary; shallow history; exact window boundary. Merge-only integration with reachable feature commits; squash; merge conflict-only edits disclosed; future timestamp; positive/misleading bug-fix marker.

**Owning stories:** E09.2, E09.3.

#### M25 - Repository, component and file ownership concentration

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Same bounded history with explicit mailmap policy

**Definition and calculation:** Largest contributor changed-line share = max(contributor changed lines)/total attributable changed lines; also count contributors needed to reach >=50% cumulative share.

**Rule, threshold and interpretation:** Descriptive concentration, not true organizational bus factor or employee performance.

**Required evidence:** Repository-local identity mapping, commit contributions and denominator.

**Missing/partial behavior:** Zero attributable churn => NOT_APPLICABLE; truncated history discloses partial window.

**Required fixtures:** Two contributors; mailmap alias; zero lines; missing identities; bots explicitly labeled only when declared.

**Owning stories:** E09.2, E09.3.

**Scoped derivation:** Apply the same largest-contributor share and contributors-to-50% formulas independently to each repository, component and file supported by repository-local history. Aggregate attributable added+deleted lines within that subject, using the pinned M24 window, identity/mailmap and rename policy and stable component mapping. Do not average file ratios to obtain a component ratio. Sort contributors by changed lines descending, then stable local identity for ties. Expose attributable-line denominator, unattributed/unknown contribution coverage, mapping evidence and scope ID. Ambiguous file/component mappings are UNKNOWN at that scope; preserve valid broader or narrower observations. Zero attributable lines is NOT_APPLICABLE with any missing-identity limitation still visible. Partial history cannot claim complete-window ownership. These are change-concentration observations, not code ownership authority, organizational bus factor, productivity or blame.

**Additional fixtures:** Different concentrations within one repository; weighted component aggregation; file rename and ambiguous mapping; missing contributor identity; shallow history and scope-specific denominators. Retain M26 temporal co-change unchanged, including support, union denominator and incomplete-history behavior.

#### M26 - Temporal co-change

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Included commits to file/component incidence

**Definition and calculation:** For pair A,B: cochanged commit count / union commits touching A or B (Jaccard); report support count, require >=3 cochanged commits to label supported relation.

**Rule, threshold and interpretation:** Evidence of co-change, not architectural dependency or causal relation.

**Required evidence:** Commit IDs, member files/components, support and union denominator.

**Missing/partial behavior:** Window incomplete => qualified observed result; fewer than3 support => insufficient support.

**Required fixtures:** Always together; unrelated; exactly3 support; bulk formatting commit; shallow history.

**Owning stories:** E09.2, E09.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P24 of 52, not a whole epic or a release authorization.

## P25 - E06.3: Complete version hygiene, license evidence and accuracy gate

**Owner:** B | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E06.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E06.1, E06.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

YAML rules for unresolved/mutable/conflicting declarations, deterministic license metadata and published per-rule validation results.

### Acceptance criteria

License risk is against an explicit configured allow/deny list, not legal compliance. Publish confusion counts and precision/recall on labeled evaluable units, UNKNOWN separately. Proposed release bar: precision >=95% and recall >=90% per flagship rule group with >=20 positive and >=20 negative labeled cases; no known critical false-negative or secret leak. Team ratifies targets before tuning; no cherry-picked exclusions.

### Measurement definitions

#### M14 - Deterministic license metadata and declared risk

**Family / outcome:** Security / Security

**Inputs and scope:** Resolved package license metadata and explicit allow/deny configuration

**Definition and calculation:** Count known SPDX-compatible license expressions and unknowns; evaluate only supported expression semantics against explicit configured policy.

**Rule, threshold and interpretation:** license.disallowed: configured deny result, default medium; absent policy => metadata only. No legal compliance verdict.

**Required evidence:** Package/license source and configured decision rule.

**Missing/partial behavior:** Missing/conflicting metadata or unsupported expression => UNKNOWN, not disallowed or allowed by guess.

**Required fixtures:** Allowed/denied; dual license; malformed expression; missing metadata; conflict.

**Owning stories:** E06.3.

#### M15 - Security classification quality

**Family / outcome:** Security / Validation

**Inputs and scope:** Labeled evaluable findings and negatives

**Definition and calculation:** Precision=TP/(TP+FP); recall=TP/(TP+FN); report TP/FP/FN/TN and UNKNOWN by rule group. Do not remove missed known-supported positives from FN.

**Rule, threshold and interpretation:** Proposed release thresholds: >=0.95 precision and >=0.90 recall; >=20 positive and >=20 negative cases per flagship group. Zero denominator => undefined, not 100%.

**Required evidence:** Label manifest fixed before tuning, result identities and reviewer decisions.

**Missing/partial behavior:** Unsupported cases disclosed separately; unexplained UNKNOWN in declared supported cases counts as missed evaluation and blocks promotion.

**Required fixtures:** Planted keys/config/advisory ranges; safe lookalikes; hidden holdout; independent label review.

**Owning stories:** E06.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P25 of 52, not a whole epic or a release authorization.

## P26 - E07.2: Implement declared-boundary and concentration checks

**Owner:** A | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E07.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E07.1, E04.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Module-boundary example, allowed direction/pattern configuration, component concentration and reach metrics.

### Acceptance criteria

API-to-internal direct import fixture violates; API-to-public passes; unresolved import yields UNKNOWN. Every violation shows the concrete path. Separate dependency_view from traversal; bounded reach discloses truncation. Local pattern configuration is explicit and included in run digest. M09 excludes the seed from distinct incoming neighbors and deduplicates parallel edges within the declared node universe. Test singleton/self-loop/two-node graphs and partial universes. Define M06 external-edge ratio over eligible file import edges classified by component, rather than a module graph containing only cross-module edges.

### Measurement definitions

#### M07 - Declared boundary and direction violations

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module graph and explicit local pattern configuration

**Definition and calculation:** Count unique disallowed source-target edge identities against declared layer/module constraints. Lower is favorable.

**Rule, threshold and interpretation:** arch.boundary: FAIL >0, high; bundled API/internal example direct depth1. No declared pattern => NOT_APPLICABLE.

**Required evidence:** Constraint identity, configured scope and direct dependency witness.

**Missing/partial behavior:** Unresolved relevant edge => UNKNOWN for unproven negative scope; never invent intermediate boundary.

**Required fixtures:** Compliant API/public; violating API/internal; unresolved import; selector rebinding.

**Owning stories:** E07.2, E07.3.

#### M08 - Component concentration

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Eligible source files and component mapping

**Definition and calculation:** For each component: nonblank noncomment source lines / total such lines in scoped repository. Maximum share reported; lower concentration not automatically better.

**Rule, threshold and interpretation:** arch.concentration: advisory finding above configured 0.60 share only with >=2 components; low default.

**Required evidence:** Line-count derivation, component membership and denominator.

**Missing/partial behavior:** Unmapped or unreadable eligible files invalidate full-repo share; report observed partial value.

**Required fixtures:** 60%/61%; single component; unmapped files; generated exclusion.

**Owning stories:** E07.2, E07.3.

#### M09 - Structural centrality and reach

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Versioned module/file graph

**Definition and calculation:** For graph node universe V, centrality(v) = count of distinct incoming neighbors u in V with u != v / max(1, |V|-1). Deduplicate parallel edges; self-loops do not enter numerator but may enter M05 cycle detection. Reach = unique nodes via chosen edge/direction/depth excluding seed. Descriptive; partial universe or unresolved edges cannot prove exact whole-scope centrality.

**Rule, threshold and interpretation:** No universal centrality PASS/FAIL; use impact context, not defect probability.

**Required evidence:** Seed/edge types/node set and traversal depth, direction and cutoff metadata.

**Missing/partial behavior:** Unresolved edges or exhausted traversal bound => lower-bound reach plus UNKNOWN completeness.

**Required fixtures:** Diamond dedupe; cycle termination; disconnected nodes; depth cutoff. Singleton; self-loop; two-node graph with self-loop and external incoming edge; parallel edges; unknown universe.

**Owning stories:** E07.2, E07.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P26 of 52, not a whole epic or a release authorization.

## P27 - E08.1: Define and emit structural quality metrics

**Owner:** B | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E08.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E05.2, E03.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Size, supported function complexity/nesting and token-clone indicators, all with exact versioned derivations.

### Acceptance criteria

No universal language-independent maintainability index. Explicitly define token/branch rules for each supported language; ratio denominator and clone overlap handling match contract. Timeout/unsupported syntax gives partial coverage, not a zero. All outputs project from one canonical body.

### Measurement definitions

#### M16 - Source size and function complexity

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported AST and source tokens

**Definition and calculation:** Per function cyclomatic v1 = 1 + count of declared branch constructs, with language-specific mapping frozen before use; report physical nonblank noncomment lines and function distribution.

**Rule, threshold and interpretation:** quality.complexity: default >15 medium; size >80 function lines low; configurable and explicitly heuristic.

**Required evidence:** Function identity/span, counted branch locations and formula version.

**Missing/partial behavior:** Parser cannot establish function => UNKNOWN metric, never fallback to misleading cross-language number.

**Required fixtures:** Straight-line; if/loop/case/boolean mapping; nested functions; malformed syntax; threshold boundaries.

**Owning stories:** E08.1.

#### M17 - Maximum nesting depth

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported AST

**Definition and calculation:** Maximum control-flow nesting depth per function under declared language construct map; lower favorable at same scope.

**Rule, threshold and interpretation:** quality.nesting: >4 medium, configurable.

**Required evidence:** Function/span and maximum-depth witness constructs.

**Missing/partial behavior:** Unknown parse sections invalidate negative claim; absent functions => NOT_APPLICABLE.

**Required fixtures:** Depth4/5; nested lambda separation; malformed block; language-specific branch syntax.

**Owning stories:** E08.1.

#### M18 - Token clone indicator

**Family / outcome:** Quality / Quality

**Inputs and scope:** Normalized eligible source token streams

**Definition and calculation:** Identify exact normalized token runs >=50 tokens spanning >=5 lines; merge overlaps before duplicated-line numerator / eligible source-line denominator. Version token normalization.

**Rule, threshold and interpretation:** quality.clone_indicator: ratio >0.10 low advisory; indicative clone, not proof duplication is wrong.

**Required evidence:** Matched file spans, normalization version, merged numerator/denominator.

**Missing/partial behavior:** Unsupported tokenization or scan cutoff => partial ratio/UNKNOWN full scope.

**Required fixtures:** Exact clone; renamed identifier policy; overlapping runs; generated exclusions; no eligible lines.

**Owning stories:** E08.1.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P27 of 52, not a whole epic or a release authorization.

## P28 - E09.3: Publish reusable change facts and equivalence fixtures

**Owner:** C | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E09.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E09.2, E03.3, E05.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Normalized change events and graph/input identity fixtures; incremental reuse eligibility against a full reference assessment.

### Acceptance criteria

Cache key binds source/config/rule/operator/feed versions. Rename moves location without arbitrary finding churn when matching is supported. Ambiguous lineage is UNKNOWN. Selective and full evaluation match semantically; use full fallback when proof is insufficient. Prove raw Git observations join E05.2 stable file/component identities; unsupported mappings remain explicit. PR narrative-only changes cannot alter analysis truth; history/message indicators retain separate provenance. P24/P28 must implement and verify M25 repository/component/file concentration using subject-local attributable-line denominators, pinned identities/history and mapping coverage. Preserve M26 temporal co-change/support semantics. Expose observed/requested history bounds and freshness/UNKNOWN reasons for each Git-derived capability; no organizational bus-factor or productivity claim.

### Measurement definitions

#### M24 - Churn and recency

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Pinned local Git history and rename policy

**Definition and calculation:** Per file/component sum added+deleted text lines in included commits; recency uses pinned UTC evaluation_time and the recorded latest valid included commit time. Proposed v1 history profile for E01.1 ratification: all non-merge commits reachable from pinned head, bounded by UTC committer timestamp within the last 180 days and then latest 1000, ordered timestamp descending then SHA. Root commits compare to empty tree; non-root commits to their sole parent. Merge-only conflict-resolution edits are excluded and must be disclosed; a later first-parent-diff profile is a different version. Never combine first-parent-only traversal with skipping merges without disclosing lost coverage. Future timestamps are invalid for recency and disclosed. A separate contextual bug-fix marker counts included commit messages matching a ratified bounded versioned marker set; it does not count proven bugs fixed.

**Rule, threshold and interpretation:** Descriptive only. E01.1 ratifies traversal/merge/time/marker defaults before E09 implementation. Message markers never influence a defect, productivity or authorship verdict.

**Required evidence:** Commit SHA/time, numstat, rename map and exact window.

**Missing/partial behavior:** Shallow/absent history => partial/UNKNOWN full-window measurement; binary churn unknown.

**Required fixtures:** Known edits; rename; merge; binary; shallow history; exact window boundary. Merge-only integration with reachable feature commits; squash; merge conflict-only edits disclosed; future timestamp; positive/misleading bug-fix marker.

**Owning stories:** E09.2, E09.3.

#### M25 - Repository, component and file ownership concentration

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Same bounded history with explicit mailmap policy

**Definition and calculation:** Largest contributor changed-line share = max(contributor changed lines)/total attributable changed lines; also count contributors needed to reach >=50% cumulative share.

**Rule, threshold and interpretation:** Descriptive concentration, not true organizational bus factor or employee performance.

**Required evidence:** Repository-local identity mapping, commit contributions and denominator.

**Missing/partial behavior:** Zero attributable churn => NOT_APPLICABLE; truncated history discloses partial window.

**Required fixtures:** Two contributors; mailmap alias; zero lines; missing identities; bots explicitly labeled only when declared.

**Owning stories:** E09.2, E09.3.

**Scoped derivation:** Apply the same largest-contributor share and contributors-to-50% formulas independently to each repository, component and file supported by repository-local history. Aggregate attributable added+deleted lines within that subject, using the pinned M24 window, identity/mailmap and rename policy and stable component mapping. Do not average file ratios to obtain a component ratio. Sort contributors by changed lines descending, then stable local identity for ties. Expose attributable-line denominator, unattributed/unknown contribution coverage, mapping evidence and scope ID. Ambiguous file/component mappings are UNKNOWN at that scope; preserve valid broader or narrower observations. Zero attributable lines is NOT_APPLICABLE with any missing-identity limitation still visible. Partial history cannot claim complete-window ownership. These are change-concentration observations, not code ownership authority, organizational bus factor, productivity or blame.

**Additional fixtures:** Different concentrations within one repository; weighted component aggregation; file rename and ambiguous mapping; missing contributor identity; shallow history and scope-specific denominators. Retain M26 temporal co-change unchanged, including support, union denominator and incomplete-history behavior.

#### M26 - Temporal co-change

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Included commits to file/component incidence

**Definition and calculation:** For pair A,B: cochanged commit count / union commits touching A or B (Jaccard); report support count, require >=3 cochanged commits to label supported relation.

**Rule, threshold and interpretation:** Evidence of co-change, not architectural dependency or causal relation.

**Required evidence:** Commit IDs, member files/components, support and union denominator.

**Missing/partial behavior:** Window incomplete => qualified observed result; fewer than3 support => insufficient support.

**Required fixtures:** Always together; unrelated; exactly3 support; bulk formatting commit; shallow history.

**Owning stories:** E09.2, E09.3.

#### M27 - Change size, spread and test touch

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Explicit working/index/base-head/patch inputs

**Definition and calculation:** Count changed text lines, files and mapped components. test_touch = whether changed set contains known test/config-test units, separately from impacted-unit association. Optional supplied PR title/description/base/head SHAs/labels/linked-reference strings live in a bounded context record with supplied provenance/digest. Context must agree with claimed source revisions or disclose conflict. No hosted lookup; context narrative never proves code behavior. Narrative-only changes leave canonical analysis identical.

**Rule, threshold and interpretation:** Descriptive; missing test touch is not proof changes are untested.

**Required evidence:** Diff hunks, state digests, file classes and component IDs.

**Missing/partial behavior:** Unresolvable patch base or binary changes preserve partial size/impact limits.

**Required fixtures:** Staged vs working; rename; add/delete; binary; patch missing base; test-only diff. Absent/valid/oversized/malformed PR metadata; injection text; SHA conflict; context-only change; telemetry exclusion and escaped rendering.

**Owning stories:** E09.1, E09.3.

**Explicit change-summary fields:** Publish changed-file and changed-component IDs/counts, unmapped changed-file count and mapping coverage, plus architecture-boundary spread when declared M07 boundary membership is available: the distinct declared boundary-member IDs containing changed subjects, with count and mapping evidence. Identify the boundary dimension/profile (for example layers); do not combine dimensions or infer architectural boundaries from folder names. Missing declarations/membership is UNKNOWN, not zero crossed boundaries. E09 emits the changed-scope facts; E10.2 joins architecture facts and publishes the boundary/impact summary under M29.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P28 of 52, not a whole epic or a release authorization.

## P29 - E07.3: Migrate remaining launch architecture rules and validate depth

**Owner:** A | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E07.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E07.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Parity map from retained Python rules to YAML IDs and four-outcome graph/evidence projections.

### Acceptance criteria

Every retained launch rule has compliant, violating and incomplete fixtures, stable identity and validated defaults. No silent old-to-new score equivalence claims. Validate Java and JS/TS structural paths and declared lower tiers; output supports later comparison without consumer analyzer logic.

### Measurement definitions

#### M05 - Module dependency cycles

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Resolved module graph

**Definition and calculation:** Number of strongly connected components of size >1 plus single-node self-loops, each reported once; include member IDs and witness edges. Lower is favorable.

**Rule, threshold and interpretation:** arch.cycles: FAIL when count >0, default medium; incomplete negative graph cannot PASS.

**Required evidence:** Observed module edges and source locations, SCC membership and witness path.

**Missing/partial behavior:** Known cycle can FAIL despite unrelated unknown edges; absent cycle needs complete relevant edge coverage.

**Required fixtures:** A->B->A; acyclic A->B; self-loop; unresolved import; reordered file traversal.

**Owning stories:** E07.1, E07.3.

#### M06 - Cross-module coupling

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module import/depends_on graph

**Definition and calculation:** Per module fan_in/out = distinct other modules using/used by it. For the file import-edge view, external-edge ratio = distinct eligible resolved file import edges whose endpoint component IDs differ / all eligible resolved file import edges with both endpoint component IDs known in the same scope. Include same-component edges in the denominator; exclude duplicate edges. Publish unresolved/unmapped exclusions and coverage. Lower fan_out favorable only under the same scope; ratio is descriptive.

**Rule, threshold and interpretation:** arch.fan_out: default threshold 10 distinct modules, medium, declared configurable; ratio descriptive.

**Required evidence:** Module edge IDs and denominator.

**Missing/partial behavior:** Zero edges ratio NOT_APPLICABLE; unresolved imports make count lower-bound and no confident threshold PASS.

**Required fixtures:** Boundary at 10/11; duplicate edges; zero edges; unknown imports.

**Owning stories:** E07.1, E07.3.

#### M07 - Declared boundary and direction violations

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module graph and explicit local pattern configuration

**Definition and calculation:** Count unique disallowed source-target edge identities against declared layer/module constraints. Lower is favorable.

**Rule, threshold and interpretation:** arch.boundary: FAIL >0, high; bundled API/internal example direct depth1. No declared pattern => NOT_APPLICABLE.

**Required evidence:** Constraint identity, configured scope and direct dependency witness.

**Missing/partial behavior:** Unresolved relevant edge => UNKNOWN for unproven negative scope; never invent intermediate boundary.

**Required fixtures:** Compliant API/public; violating API/internal; unresolved import; selector rebinding.

**Owning stories:** E07.2, E07.3.

#### M08 - Component concentration

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Eligible source files and component mapping

**Definition and calculation:** For each component: nonblank noncomment source lines / total such lines in scoped repository. Maximum share reported; lower concentration not automatically better.

**Rule, threshold and interpretation:** arch.concentration: advisory finding above configured 0.60 share only with >=2 components; low default.

**Required evidence:** Line-count derivation, component membership and denominator.

**Missing/partial behavior:** Unmapped or unreadable eligible files invalidate full-repo share; report observed partial value.

**Required fixtures:** 60%/61%; single component; unmapped files; generated exclusion.

**Owning stories:** E07.2, E07.3.

#### M09 - Structural centrality and reach

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Versioned module/file graph

**Definition and calculation:** For graph node universe V, centrality(v) = count of distinct incoming neighbors u in V with u != v / max(1, |V|-1). Deduplicate parallel edges; self-loops do not enter numerator but may enter M05 cycle detection. Reach = unique nodes via chosen edge/direction/depth excluding seed. Descriptive; partial universe or unresolved edges cannot prove exact whole-scope centrality.

**Rule, threshold and interpretation:** No universal centrality PASS/FAIL; use impact context, not defect probability.

**Required evidence:** Seed/edge types/node set and traversal depth, direction and cutoff metadata.

**Missing/partial behavior:** Unresolved edges or exhausted traversal bound => lower-bound reach plus UNKNOWN completeness.

**Required fixtures:** Diamond dedupe; cycle termination; disconnected nodes; depth cutoff. Singleton; self-loop; two-node graph with self-loop and external incoming edge; parallel edges; unknown universe.

**Owning stories:** E07.2, E07.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P29 of 52, not a whole epic or a release authorization.

## P30 - E15.2: Automate deterministic and adversarial regression checks

**Owner:** C (coordination); A/B own their defects | **Group:** 3 | **Required preceding gate:** G20 PASS

### Start instructions

Implement only E15.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G20 PASS on a recorded reviewed SHA and direct prerequisites: E15.1, E03.3, E02.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Engine-owned lint/type/coverage, contract, tamper, malicious-source, report escaping, no-egress and repeated-run harnesses. Use existing CI test invocation and local/authorized runner where needed.

### Acceptance criteria

Keep configured 80% coverage minimum and strict checks; no skipped-test inflation. At least three repeats per corpus configuration with semantic comparison excluding only declared operational fields. Full-vs-incremental parity, old-client contracts and installed artifacts are covered. No executing scanned project tests/build scripts. Extend the checks already established in E00.2 and G10/G20; do not defer quality enforcement until this story. Keep the configured 80% combined coverage floor with branch measurement enabled; do not call it a separate 80% branch threshold. Every skip, unavailable tool and unrun required check is disclosed. Re-run affected prior checks and cumulative regressions after repairs.

### Measurement definitions

#### M33 - Coverage, determinism and performance acceptance

**Family / outcome:** Cross-cutting / Validation

**Inputs and scope:** All artifacts, capability records and corpus manifests

**Definition and calculation:** Per capability: evaluated eligible units / all eligible units; separately unknown/not-applicable/excluded/error. Runtime wall duration/peak RSS on declared host. Three-repeat semantic digest equality. Also record local health/progress/terminal states, hard deadlines/cancellation grace, peak output/disk usage and retention behavior. Freeze numerical bounds before affected qualification; failed/unrun checks are never recorded as PASS.

**Rule, threshold and interpretation:** Proposed initial tiers: <=10k eligible files 10min/2GiB; <=100k 30min/8GiB on 4vCPU. Measure/tune before publication; exceeding budget never silently truncates success.

**Required evidence:** Per-repo SHA/config/feed/hardware, counts, resource logs and semantic hashes.

**Missing/partial behavior:** Unknown denominator => coverage unknown. A survival run is not proof of analytical correctness.

**Required fixtures:** Dogfood; >=50 identified large repos; labeled flagship subset; resource exhaustion; corruption; repeat variation. SIGINT/SIGTERM/hard kill; disk full; output collision; concurrent reader; retention preserving active baseline; audit redaction.

**Owning stories:** E15.1, E15.2, E15.3.

**Report acceptance:** Per-capability coverage/freshness records defined above must survive JSON and HTML projection, including vulnerability-feed and Git-history reasons. Verify the visible report views in E11.2 and installed-artifact journeys in E11.3/P46 at G50; G40 verifies the delivered report projection and candidate-install smoke. A rendered healthy-looking empty table cannot substitute for explicit UNKNOWN or no-baseline behavior.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P30 of 52, not a whole epic or a release authorization.

## P31 - E08.2: Emit test association and declared CI gaps

**Owner:** B | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E08.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E08.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Static test inventory/association, skipped-test counts and declared-test/coverage-command gaps.

### Acceptance criteria

Do not call test association measured runtime coverage. CI invocation evidence is static and conditional-job uncertainty remains visible. A missing coverage report is not 0% code coverage. Positive, negative, partial CI and unsupported test framework cases have expectations.

### Measurement definitions

#### M19 - Test inventory and association

**Family / outcome:** Quality / Quality

**Inputs and scope:** Test declarations, imports and configured conventions

**Definition and calculation:** Test counts by framework; fraction of eligible production units with at least one supported static test association. Evidence strength distinguishes import/reference from naming convention.

**Rule, threshold and interpretation:** quality.test_association: advisory only; do not label as measured runtime test coverage.

**Required evidence:** Test declarations, source-to-test association and its method/confidence.

**Missing/partial behavior:** Unsupported framework/indirect test generation => UNKNOWN association scope.

**Required fixtures:** Direct reference; convention-only; no tests; generated tests; ambiguous association.

**Owning stories:** E08.2.

#### M20 - Skipped/disabled tests

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported test source syntax

**Definition and calculation:** Count explicitly skipped/disabled tests, with reason where static literal; lower favorable only with unchanged test scope.

**Rule, threshold and interpretation:** testing.disabled: >0 low/medium per catalog; distinguish conditional skips.

**Required evidence:** Test identity, annotation/call span and static condition.

**Missing/partial behavior:** Dynamic skip condition => unknown eligibility, not unconditional disabled.

**Required fixtures:** Explicit disabled; enabled; conditional; unsupported decorator; test deletion.

**Owning stories:** E08.2.

#### M21 - Configured test and coverage invocation gaps

**Family / outcome:** Quality / Quality

**Inputs and scope:** M03 CI observations plus test/coverage configuration

**Definition and calculation:** Boolean/count of declared test/coverage capabilities with no statically observed invocation in supported CI/build scope.

**Rule, threshold and interpretation:** testing.ci_gap: medium only for proven absent invocation in complete supported config; otherwise UNKNOWN.

**Required evidence:** Configured tool, job command evidence and checked scope.

**Missing/partial behavior:** External workflow or script not inspected => UNKNOWN. No runtime pass/fail or coverage percentage.

**Required fixtures:** Declared+invoked; declared+absent; delegated script; conditional job; no CI applicability.

**Owning stories:** E08.2.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P31 of 52, not a whole epic or a release authorization.

## P32 - E10.1: Match finding lifecycle and compatible metric deltas

**Owner:** C | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E10.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E09.3, E01.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Versioned finding matching and new/resolved/improved/worsened/unchanged/unknown lifecycle over explicitly supplied states.

### Acceptance criteria

Absence under failed/incomplete coverage never resolves a finding. Message-only changes keep identity; severity overrides do not look like code fixes. Rule/schema/config/feed compatibility checked before movement. Old incompatible snapshots remain readable or explicitly unsupported, never silently converted to equivalent truth. Persistent findings improve/worsen only against a rule-declared compatible violation magnitude. A remaining binary violation is unchanged; falling below the condition resolves only after complete compatible reevaluation. Severity/config/message/location changes cannot masquerade as a code fix. Test magnitude reduction that still violates, binary persistence, empty outcome and disabled-all scope.

### Measurement definitions

#### M28 - Finding lifecycle and metric delta

**Family / outcome:** Change / All four

**Inputs and scope:** Two explicit compatible canonical states

**Definition and calculation:** Match by versioned stable rule/subject/evidence occurrence identity. Metric delta = candidate-base with pinned units/scope. Finding lifecycle as specified; absent finding resolved only after complete compatible reevaluation. Persistent findings use a rule-declared versioned violation magnitude for improved/worsened. A binary violation that remains present is unchanged; decreasing below the rule condition is resolved only with complete compatible reevaluation. Severity overrides are config changes, not source fixes. Without a comparable magnitude, do not invent intermediate movement.

**Rule, threshold and interpretation:** New/worsened unfavorable; resolved/improved favorable; message-only changes unchanged. Local source edit versus policy override is distinguished.

**Required evidence:** Both artifact digests, matching rule version, evidence pair and compatibility reasons.

**Missing/partial behavior:** Incompatible rules/coverage/identity => UNKNOWN, never synthetic resolution.

**Required fixtures:** Stable; fixed; new; message-only; rename; coverage loss; policy-severity change. Reduced magnitude while still violating; binary persistence; severity-only override; unknown comparator.

**Owning stories:** E10.1, E10.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P32 of 52, not a whole epic or a release authorization.

## P33 - E11.1: Deliver backward-aware CLI and configuration

**Owner:** A | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E11.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E02.3, E04.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

init, doctor, assess --repo --no-ai and explicit compare contract; documented bundled parameters/exclusions/suppressions and migration messages.

### Acceptance criteria

No credentials/login prompt or collection opt-in required for assess. Doctor lists supported capabilities/trust/config, not mandatory cloud setup. Command/exit/config compatibility is mapped from live baseline. Community does not expose custom-rule creation/loading as a supported UI. Defaults include only validated bundled catalog.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P33 of 52, not a whole epic or a release authorization.

## P34 - E08.3: Complete evidence-backed maintainability prioritization

**Owner:** B | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E08.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E08.2, E09.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Churn-weighted complexity, dependency staleness where metadata exists and deterministic risk tuples; migrate retained debt/testing rules to YAML.

### Acceptance criteria

Hotspots cite both complexity and history window. No developer productivity/blame or cost-to-fix estimate. Stable ordering uses declared tie-breakers; missing history produces UNKNOWN hotspot metric but does not erase static findings. Policy/default changes remain visible. Provide exact churn/complexity and eligible component evidence for E10.2 change concerns. Do not equate a high hotspot rank with runtime failure probability or introduce an opaque aggregate score. P34 emits the unified M22 Engineering Hotspot records and preserves complexity × churn ordering and stable component-ID ties. Centrality/reach, supported scoped ownership and active finding links are contextual only. Emit pinned history, contributor coverage and priority explanation. Test context-only changes cannot change rank, and partial/UNKNOWN ranking inputs remain unranked with known static evidence retained. Reuse supported structure only; do not add a new analyzer.

### Measurement definitions

#### M22 - Churn-weighted complexity hotspots

**Family / outcome:** Quality / Maintainability

**Inputs and scope:** M16 and M24 in same repository/window

**Definition and calculation:** For component: sum of supported function complexities in it * component changed lines in pinned history window. Sort descending; tie by stable component ID.

**Rule, threshold and interpretation:** maintainability.hotspot: informational top-ranked concerns; optional threshold only if explicitly configured.

**Required evidence:** Complexity subjects, commit/file churn and component mapping.

**Missing/partial behavior:** Missing history or structure => UNKNOWN hotspot, retain separate known measurements.

**Required fixtures:** Same complexity/different churn; zero churn; missing history; stable ties; rename mapping.

**Owning stories:** E08.3.

**Engineering Hotspot record (canonical, versioned):** Emit a stable record ID and repository-local component subject ID, input-state digest, complexity/churn contributor records and their measurement versions, structural centrality/reach where already supported, component/file ownership concentration references where supported, active finding IDs for the same state/scope, exact pinned M24 history profile/window, per-contributor coverage/UNKNOWN reasons, evidence IDs and a deterministic priority explanation. File ownership drill-down does not imply a new file-level hotspot ranking. Unsupported contributors stay explicit; do not invent missing metrics or add extraction scope.

**Ranking versus context:** Preserve M22's existing component complexity × component changed-lines value as the sole hotspot ranking value; descending exact value, then stable component ID ascending. This is the existing named measurement, not a new health score. Mark complexity and churn as `ranking`; centrality, reach, ownership and active finding references are `context_only`. No hidden weights, severity boosts or missing-as-zero values. Explanation names the formula/version, input values, scope/window and tie-breaker. Missing required complexity/history yields UNKNOWN rank; partial required inputs may show an observed value but cannot enter the complete comparable ranking. Keep such records in a separately identified partial/UNKNOWN list ordered by subject ID. Missing contextual evidence does not invalidate a complete complexity/churn rank. Changing only a contextual contributor must not change the rank. Active references exclude resolved findings and retain suppression/exemption state without silently changing rank.

**Additional fixtures:** Complete unified record; equal ranking values with different ownership/centrality/findings; missing context with known rank; missing or partial ranking input; dangling/wrong-state finding reference rejection; exact priority explanation and stable IDs across deterministic repeats.

#### M23 - Dependency staleness and concern ordering

**Family / outcome:** Quality / Maintainability

**Inputs and scope:** Resolved dependency release dates from permitted pinned metadata; M10-M22

**Definition and calculation:** Staleness days = declared evaluation_time minus known installed-version publication_time. Concern order tuple: effective severity, valid evidence class, hotspot where comparable, stable finding ID; no weighted overall score.

**Rule, threshold and interpretation:** maintainability.dependency_age: >730 days low advisory if dates known; age does not prove insecure/unsupported.

**Required evidence:** Version/date source snapshot and explicit evaluation_time; ordering contributors.

**Missing/partial behavior:** No release-date metadata => UNKNOWN age. Assessment date must be pinned for repeatability.

**Required fixtures:** Known old/new; unknown date; future/invalid timestamp; identical severity ties; changed metadata snapshot.

**Owning stories:** E08.3.

**Ordering distinction:** The existing M23 finding-concern tuple is separate from the M22 Engineering Hotspot list. Its severity/evidence/hotspot inputs are labeled as ranking inputs for that tuple; centrality/reach/ownership and temporal co-change are contextual and add no hidden weight. Publish the versioned evidence-class ordering and handling of incomparable hotspot values in E01.1. HTML displays the canonical order and explanation; it never computes another priority or score.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P34 of 52, not a whole epic or a release authorization.

## P35 - E10.2: Calculate graph delta, impact and change verdicts

**Owner:** C | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E10.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E10.1, E07.2, E08.2, E08.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Changed graph nodes/edges, bounded reverse-dependency blast radius, test-touch evidence and deterministic outcome movement.

### Acceptance criteria

Precedence is Insufficient evidence > Mixed > Deteriorated > Improved > Stable. Improved requires real favorable movement. No composite average hides deterioration. Impact is static possible reach, not runtime impact probability. Exceeding budget marks incomplete evidence. Execute the versioned M29 change-concern join over changed subjects and declared base/candidate churn/centrality evidence. Emit individual reasons, scope/denominators, thresholds and witnesses; retain partial known contributors. Test changed high-churn/high-centrality, ordinary change, unchanged hotspot, deletion/rename and missing data. Use E08.2 associations for impacted tests. Outcome movement uses the explicit E01 driver manifest and M30 empty/partial-scope rules, not an implicit list or average. P35 consumes E08.3 hotspot/churn/complexity evidence; wait for that reviewed prerequisite. Implement M27/M29 boundary spread, distinct crossed-boundary pairs, affected-component/test sets and counts with base/candidate witnesses, de-duplication, coverage and traversal cutoffs/lower bounds. Test absent declarations versus exact zero and partial test associations. Keep concerns contextual and outcome drivers explicit.

### Measurement definitions

#### M29 - Graph delta and static blast radius

**Family / outcome:** Change / Architecture

**Inputs and scope:** Two compatible graphs + changed subjects

**Definition and calculation:** Sets of added/removed nodes/edges under stable IDs. Impact = changed seed plus unique reverse reachable dependents at configured edge/depth; impacted tests via supported association. Named contextual change concern joins changed subjects to the configured comparable base/candidate churn and centrality measures, recording chosen snapshot, window, denominators, threshold/profile and individual evidence reasons. Deleted subjects use available base evidence. E01.1 ratifies exact high-churn/high-centrality predicates and deterministic ranking; no calibrated probability or opaque composite score. Partial contributors remain visible.

**Rule, threshold and interpretation:** Possible static impact only; configured bound default depth4, deterministic. Change concerns are context-only by default; any configured verdict-driving rule requires explicit YAML semantics and outcome-driver mapping.

**Required evidence:** Graph IDs, edge witnesses, seed list, traversal limit and test links.

**Missing/partial behavior:** Unresolved edges/cutoff => lower-bound impact with incomplete coverage.

**Required fixtures:** Diamond; cycles; file deletion; rename; missing edge; bound cutoff. Changed high-churn/high-centrality vs ordinary component; unchanged hotspot; missing history; deletion/rename; stable ties.

**Owning stories:** E10.2, E10.3.

**Explicit boundary and impact metrics:** Carry M27 change size/spread and boundary membership into the canonical change summary. Report affected-component IDs/count, affected-test IDs/count via supported static associations, and unique visited nodes/edges. Count architectural boundaries crossed as distinct ordered pairs of declared boundary-member IDs joined by observed dependency edges in the bounded affected subgraph, where source and target membership differ. Keep this `crossed_boundary_count` separate from boundary-spread count, cross-boundary edge count and actual YAML boundary violations; crossing a boundary is not automatically a violation. Record graph side (base/candidate), boundary dimension/profile, pair IDs and edge witnesses. Report base and candidate separately where compatible; never merge them into an ambiguous count. Deleted subjects use base evidence. De-duplicate diamond/cycle paths by stable IDs.

Record changed seeds, edge kinds, traversal direction, maximum depth/nodes/edges, visited totals, cutoff reason, unresolved mappings/edges and test-association coverage. Known affected sets/counts under a cutoff are labeled lower bounds; missing boundary or test evidence is UNKNOWN, not a zero. An exact zero requires complete applicable evidence. This is possible static blast radius, never executed-test coverage or runtime impact probability. Consume E08.3's canonical hotspot/churn/complexity evidence with E07.2 structure and E08.2 test associations; E08.3 is a hard prerequisite. Preserve the existing context-only M29 concern predicate and M26 temporal co-change without turning either into a new score.

**Additional fixtures:** One/multiple/no declared boundaries; repeated edges crossing the same pair; diamond/cycle de-duplication; unmapped boundary; separate base/candidate and deletion; exact-zero versus unavailable tests; depth/node/edge cutoff lower bounds.

#### M30 - Thresholded outcome movement

**Family / outcome:** Change / All four

**Inputs and scope:** Compatible metric/finding deltas with directions and declared epsilon

**Definition and calculation:** Qualifying change: strict delta beyond versioned threshold; counts default epsilon0, ratios epsilon0.01 absolute, advisory metrics excluded unless configured. Classify Insufficient > Mixed > Deteriorated > Improved > Stable. Use the versioned launch driver manifest to define exactly which rules/metrics belong to each outcome, applicability, directions, epsilons, required coverage and scope compatibility. Empty or entirely disabled/exempt eligible driver sets yield unavailable/NOT_APPLICABLE, never healthy/Stable by default. Snapshot execution/status/coverage/trust remain separate; a known violation survives unrelated incomplete evidence.

**Rule, threshold and interpretation:** Improved needs >=1 favorable and no unfavorable; Stable has neither. Required covered metric UNKNOWN or incompatible policy forces Insufficient. No overall numerical average.

**Required evidence:** Qualifying drivers, excluded contextual metrics, threshold profile and both coverages.

**Missing/partial behavior:** First run/no baseline => Insufficient/no comparison. Known partial deltas may display without full-outcome verdict.

**Required fixtures:** All unchanged; only improvement; only deterioration; mixed; coverage drop; exact epsilon boundary. Empty outcome; disabled-all scope; known violation with partial coverage; catalog driver mapping.

**Owning stories:** E10.2, E10.3.

#### M31 - Cause attribution

**Family / outcome:** Change / Security and other outcomes

**Inputs and scope:** Input/Engine/rule/config/feed digests and optional controlled paired reruns

**Definition and calculation:** Source-only, feed-only, configuration-only, mixed or undetermined attribution. If multiple dimensions differ, only controlled equivalent-input comparisons justify isolated cause.

**Rule, threshold and interpretation:** Feed-driven CVE changes cannot be called customer code deterioration. No AI-causality inference.

**Required evidence:** Changed input dimensions and controlled rerun references if performed.

**Missing/partial behavior:** Lack of controlled evidence => mixed/undetermined, never guessing dominant cause.

**Required fixtures:** Same code/new CVE; dependency fix/same feed; severity override; source+feed changed.

**Owning stories:** E10.2, E10.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P35 of 52, not a whole epic or a release authorization.

## P36 - E11.2: Project consistent JSON, HTML and SARIF

**Owner:** A | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E11.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E01.2, E03.3, E07.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

One canonical result to three outputs, with evidence drilldown, four outcomes, supporting inventory/Git views and separate coverage/trust states.

### Acceptance criteria

HTML works locally without CDN/server and escapes source/messages. SARIF fingerprints and severity mapping are stable; UNKNOWN is disclosed without manufacturing a clean scan. Metrics that do not fit SARIF findings stay in documented properties/JSON. Display default/effective severity, suppressions and exception attribution. Show snapshot status, execution status, coverage and verification independently; unavailable/NOT_APPLICABLE outcome is not a healthy badge. Preserve preview purpose and context-only change concerns. All outputs obey the ratified driver manifest and corrected metric semantics. P36: HTML must visibly present: (1) Engineering Hotspots with ranking/context labels, contributor values, priority explanations and linked findings/evidence; (2) repository/component/file ownership concentration with scope, denominator, pinned history and limitations; (3) temporal co-change with pair, support and union denominator; (4) change-summary/blast-radius counts, boundary spread/crossed-boundary pairs, affected components/tests and traversal limits; (5) per-capability coverage and freshness, including vulnerability feed and Git history with explicit UNKNOWN reasons; and (6) a Before / After / Delta table of compatible named metrics with units, scope, both coverages, outcome movement and linked qualifying/excluded drivers and cause/compatibility reasons. A first run visibly says no baseline and makes delta/movement unavailable; partial or incompatible comparisons retain qualified known observations without inventing zero, Stable or improvement. HTML projects the canonical Engine result, order, calculations and verdicts; it must never calculate its own scores, ranking, deltas or outcome movement. No new numeric score is added.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P36 of 52, not a whole epic or a release authorization.

## P37 - E13.1: Enforce durable opt-in and no-egress defaults

**Owner:** B | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E13.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E02.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Local versioned consent/preferences, per-run deny, inspect/enable/disable controls and cancellation of pending collection.

### Acceptance criteria

No consent means no evidence/graph/telemetry transmissions from local Engine adapters. Noninteractive CI never invents consent. Disable survives restart and cancels queued sends. Upload/analytics failure cannot fail analysis. Prohibited-data canaries cover logs, retry queues and telemetry serialization.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P37 of 52, not a whole epic or a release authorization.

## P38 - E10.3: Separate source, feed and configuration causes

**Owner:** C | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E10.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E10.2, E06.3, E08.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Cause metadata and controlled comparison fixtures for unchanged code/new CVE, dependency fix, policy override, changed coverage and mixed inputs.

### Acceptance criteria

Same-code feed change labeled feed-driven. If source and feed both change, controlled reruns can isolate causes; otherwise report mixed/undetermined. Compare all five families without Platform imports, DB or hidden baseline selection. Preserve explicit qualifying changes and denominators.

### Measurement definitions

#### M28 - Finding lifecycle and metric delta

**Family / outcome:** Change / All four

**Inputs and scope:** Two explicit compatible canonical states

**Definition and calculation:** Match by versioned stable rule/subject/evidence occurrence identity. Metric delta = candidate-base with pinned units/scope. Finding lifecycle as specified; absent finding resolved only after complete compatible reevaluation. Persistent findings use a rule-declared versioned violation magnitude for improved/worsened. A binary violation that remains present is unchanged; decreasing below the rule condition is resolved only with complete compatible reevaluation. Severity overrides are config changes, not source fixes. Without a comparable magnitude, do not invent intermediate movement.

**Rule, threshold and interpretation:** New/worsened unfavorable; resolved/improved favorable; message-only changes unchanged. Local source edit versus policy override is distinguished.

**Required evidence:** Both artifact digests, matching rule version, evidence pair and compatibility reasons.

**Missing/partial behavior:** Incompatible rules/coverage/identity => UNKNOWN, never synthetic resolution.

**Required fixtures:** Stable; fixed; new; message-only; rename; coverage loss; policy-severity change. Reduced magnitude while still violating; binary persistence; severity-only override; unknown comparator.

**Owning stories:** E10.1, E10.3.

#### M29 - Graph delta and static blast radius

**Family / outcome:** Change / Architecture

**Inputs and scope:** Two compatible graphs + changed subjects

**Definition and calculation:** Sets of added/removed nodes/edges under stable IDs. Impact = changed seed plus unique reverse reachable dependents at configured edge/depth; impacted tests via supported association. Named contextual change concern joins changed subjects to the configured comparable base/candidate churn and centrality measures, recording chosen snapshot, window, denominators, threshold/profile and individual evidence reasons. Deleted subjects use available base evidence. E01.1 ratifies exact high-churn/high-centrality predicates and deterministic ranking; no calibrated probability or opaque composite score. Partial contributors remain visible.

**Rule, threshold and interpretation:** Possible static impact only; configured bound default depth4, deterministic. Change concerns are context-only by default; any configured verdict-driving rule requires explicit YAML semantics and outcome-driver mapping.

**Required evidence:** Graph IDs, edge witnesses, seed list, traversal limit and test links.

**Missing/partial behavior:** Unresolved edges/cutoff => lower-bound impact with incomplete coverage.

**Required fixtures:** Diamond; cycles; file deletion; rename; missing edge; bound cutoff. Changed high-churn/high-centrality vs ordinary component; unchanged hotspot; missing history; deletion/rename; stable ties.

**Owning stories:** E10.2, E10.3.

**Explicit boundary and impact metrics:** Carry M27 change size/spread and boundary membership into the canonical change summary. Report affected-component IDs/count, affected-test IDs/count via supported static associations, and unique visited nodes/edges. Count architectural boundaries crossed as distinct ordered pairs of declared boundary-member IDs joined by observed dependency edges in the bounded affected subgraph, where source and target membership differ. Keep this `crossed_boundary_count` separate from boundary-spread count, cross-boundary edge count and actual YAML boundary violations; crossing a boundary is not automatically a violation. Record graph side (base/candidate), boundary dimension/profile, pair IDs and edge witnesses. Report base and candidate separately where compatible; never merge them into an ambiguous count. Deleted subjects use base evidence. De-duplicate diamond/cycle paths by stable IDs.

Record changed seeds, edge kinds, traversal direction, maximum depth/nodes/edges, visited totals, cutoff reason, unresolved mappings/edges and test-association coverage. Known affected sets/counts under a cutoff are labeled lower bounds; missing boundary or test evidence is UNKNOWN, not a zero. An exact zero requires complete applicable evidence. This is possible static blast radius, never executed-test coverage or runtime impact probability. Consume E08.3's canonical hotspot/churn/complexity evidence with E07.2 structure and E08.2 test associations; E08.3 is a hard prerequisite. Preserve the existing context-only M29 concern predicate and M26 temporal co-change without turning either into a new score.

**Additional fixtures:** One/multiple/no declared boundaries; repeated edges crossing the same pair; diamond/cycle de-duplication; unmapped boundary; separate base/candidate and deletion; exact-zero versus unavailable tests; depth/node/edge cutoff lower bounds.

#### M30 - Thresholded outcome movement

**Family / outcome:** Change / All four

**Inputs and scope:** Compatible metric/finding deltas with directions and declared epsilon

**Definition and calculation:** Qualifying change: strict delta beyond versioned threshold; counts default epsilon0, ratios epsilon0.01 absolute, advisory metrics excluded unless configured. Classify Insufficient > Mixed > Deteriorated > Improved > Stable. Use the versioned launch driver manifest to define exactly which rules/metrics belong to each outcome, applicability, directions, epsilons, required coverage and scope compatibility. Empty or entirely disabled/exempt eligible driver sets yield unavailable/NOT_APPLICABLE, never healthy/Stable by default. Snapshot execution/status/coverage/trust remain separate; a known violation survives unrelated incomplete evidence.

**Rule, threshold and interpretation:** Improved needs >=1 favorable and no unfavorable; Stable has neither. Required covered metric UNKNOWN or incompatible policy forces Insufficient. No overall numerical average.

**Required evidence:** Qualifying drivers, excluded contextual metrics, threshold profile and both coverages.

**Missing/partial behavior:** First run/no baseline => Insufficient/no comparison. Known partial deltas may display without full-outcome verdict.

**Required fixtures:** All unchanged; only improvement; only deterioration; mixed; coverage drop; exact epsilon boundary. Empty outcome; disabled-all scope; known violation with partial coverage; catalog driver mapping.

**Owning stories:** E10.2, E10.3.

#### M31 - Cause attribution

**Family / outcome:** Change / Security and other outcomes

**Inputs and scope:** Input/Engine/rule/config/feed digests and optional controlled paired reruns

**Definition and calculation:** Source-only, feed-only, configuration-only, mixed or undetermined attribution. If multiple dimensions differ, only controlled equivalent-input comparisons justify isolated cause.

**Rule, threshold and interpretation:** Feed-driven CVE changes cannot be called customer code deterioration. No AI-causality inference.

**Required evidence:** Changed input dimensions and controlled rerun references if performed.

**Missing/partial behavior:** Lack of controlled evidence => mixed/undetermined, never guessing dominant cause.

**Required fixtures:** Same code/new CVE; dependency fix/same feed; severity override; source+feed changed.

**Owning stories:** E10.2, E10.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P38 of 52, not a whole epic or a release authorization.

## P39 - E13.2: Preserve current telemetry wire and prepare scoped JSON export

**Owner:** B | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E13.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E13.1, E01.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Maintain accepted existing aggregate payload semantics. Separately serialize permitted evidence/graph export with schema/digest/notice/category fields; use a local fake collector for new capability contracts.

### Acceptance criteria

Do not edit Community API, S3 or infrastructure. Existing telemetry does not carry findings/snippets/repo names. New evidence/graph upload remains unavailable unless the actual collector advertises supported schema and receipt/capability checks; no speculative live v2 calls. Local preview/export proves payload construction without claiming server readiness.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P39 of 52, not a whole epic or a release authorization.

## P40 - E12.1: Serve bounded local evidence queries from artifacts

**Owner:** C | **Group:** 4 | **Required preceding gate:** G30 PASS

### Start instructions

Implement only E12.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G30 PASS on a recorded reviewed SHA and direct prerequisites: E02.3, E11.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Repository/snapshot/component/finding/metric/dependency/change/evidence/lineage tools with pagination and explicit local root scope.

### Acceptance criteria

No database, mutation, assessment execution, rule activation, shell, hosted calls, portfolio query or GraphRAG tool. Reject arbitrary paths and unknown artifact versions. Tests attempt unauthorized files, oversized results and query budgets; read-only access does not need collection consent.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P40 of 52, not a whole epic or a release authorization.

## P41 - E13.3: Test export restrictions and signed-projection integrity

**Owner:** B | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E13.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E13.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Explicit full/restricted/no-export modes for headless invocation with a manifest of withheld categories.

### Acceptance criteria

No-export retains local functionality and emits no data transfer. Redaction cannot mutate signed canonical bytes: preserve local original and produce a separate projection with original digest/export-policy/withheld markers for signing. Test revocation/expired receipt using fake collector; actual server deletion/admission remains follow-on work.

### Measurement definitions

#### M32 - Export and trust provenance

**Family / outcome:** Cross-cutting / Trust

**Inputs and scope:** Canonical artifacts and selected export profile

**Definition and calculation:** Original canonical digest preserved; exported projection lists original digest, allowed/withheld categories, export-policy version and separate signature metadata.

**Rule, threshold and interpretation:** No-export produces no external transfer. A signed projection cannot claim unseen evidence was externally verified.

**Required evidence:** Original/projection manifest, verification profile, package digest and withheld markers.

**Missing/partial behavior:** Missing original/evidence or untrusted key => explicit unavailable/unverified or rejected according to purpose.

**Required fixtures:** Full/restricted/no export; tampering; stale package; wrong purpose; no public private-data logging.

**Owning stories:** E13.3.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P41 of 52, not a whole epic or a release authorization.

## P42 - E12.2: Retain one optional local/BYO explanation path

**Owner:** C | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E12.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E12.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Reuse one existing provider adapter behind optional dependencies; explanation artifact cites permitted evidence IDs and provider/model.

### Acceptance criteria

AI is disabled by default and excluded from canonical computation. Network denial/provider failure yields an explanation error without changing assessment status or canonical digest. No arbitrary tool execution from source instructions. Prompt/evidence egress is explicitly enabled independently of product telemetry.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P42 of 52, not a whole epic or a release authorization.

## P43 - E14.1: Implement strict package/release verification profiles

**Owner:** B | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E14.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E01.3, E04.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Public Sigstore expected identity/issuer/bundle verification and one bounded private/offline self-managed-key profile, with version/expiry/revocation-policy checks.

### Acceptance criteria

Real cryptographic valid/tampered/wrong-issuer/wrong-purpose/expired/unsupported fixtures, not a mocked signature boolean. Public distribution and private result signer roles are distinct. Private rule/result contents never enter a public transparency log. Offline profile states freshness limits, not instant revocation.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P43 of 52, not a whole epic or a release authorization.

## P44 - E12.3: Prove AI-on/off and local MCP equivalence

**Owner:** C | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E12.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E12.2, E10.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Mode matrix over same pinned inputs; provider success, timeout, injection and disabled cases.

### Acceptance criteria

Canonical findings/metrics/severity/coverage/verdicts remain semantically identical; only separate AI artifact differs. MCP returns same canonical evidence without requiring an AI provider. Export limitations and missing citations are visible; unsupported AI claims cannot enter scores.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P44 of 52, not a whole epic or a release authorization.

## P45 - E14.2: Build standalone wheel, sdist and non-root container

**Owner:** B | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E14.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E02.3, E14.1, E04.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Engine-contained build/release verifier under allowed export paths; container build recipe under engine/examples. Bundle resolved YAML/schemas/assets and pinned runtime lock inputs inside engine/.

### Acceptance criteria

Install wheel and sdist outside checkout; no monorepo PYTHONPATH or DB dependency. Container supports no-network execution, read-only source, non-root user, explicit writable temp/output, CPU/memory/time limits and cleanup. SBOM covers resolved runtime dependencies; provenance/checksums bind exact artifact digests. No new root workflow/export-manifest edits. Explicit Engine-local packaging files are permitted. Keep reproducible lock inputs in exported paths; verify public source export and wheel/sdist inclusion separately. Supply a local health/status command or file protocol, retention configuration, bounded audit events, SIGINT/SIGTERM/grace/hard-stop behavior, and cleanup/disk-full/read-only-source fixtures. No raw source/PR text/secrets in operational logs. Bind measured limits into the headless contract.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P45 of 52, not a whole epic or a release authorization.

## P46 - E11.3: Verify first assessment, partial run and comparison journeys

**Owner:** A | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E11.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E11.1, E11.2, E06.3, E08.3, E10.3, E14.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

End-to-end clean-directory journeys over built wheel, including helpful actionable failures and compatible comparison.

### Acceptance criteria

A first run says no baseline; no trend invented. A meaningful finding can be traced to source evidence and after a controlled fix has expected lifecycle. Failed family retains coverage limitations; secret redaction holds in every format. Docs and samples require no monorepo-only paths. Run these journeys on the built candidate wheel from E14.2, installed outside checkout with no source-tree PYTHONPATH. Record artifact digest and verify installed schemas/catalog/assets and no-database restart behavior. P46: Generate reports by executing the installed Engine on pinned repository/Git/feed fixtures with independently expected real values; report screenshots or hand-authored envelopes alone do not pass. Verify every E11.2 visible view and its links against the canonical result for complete, partial, UNKNOWN and no-baseline inputs, plus compatible before/after movement and incompatible comparison. Include stale/missing vulnerability feed, shallow/missing Git history, unknown ownership mapping, impact cutoff and missing test association. Assert no synthetic zeros, healthy badges, trend or HTML-calculated score. Record installed artifact digest, canonical/result/report digests, expected/actual values, link checks and a visual review of the generated local HTML. Run the full journey on the E14.2 wheel outside checkout; G50 repeats report acceptance across independent wheel, sdist and container installations of the exact candidate.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P46 of 52, not a whole epic or a release authorization.

## P47 - E14.3: Sign results and prove headless consumer interoperability

**Owner:** B | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E14.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E14.2, E13.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Neutral local invocation runner and Engine-owned consumer fixtures; detached result/projection signatures from a separate signing process.

### Acceptance criteria

Same Engine accepts a valid prepared customer Effective RuleSet, emits standard artifacts and is read by an independent schema consumer without custom analyzer code. Reject invalid/preview-only package for production purpose. Analysis process cannot access signer credentials. Local restricted/no-export runs and cancellation work without AWS or Platform. Actual lease, upload and hosted admission are not claimed. Actually run valid preview-purpose and production-purpose packages in separate permitted contexts, not only rejection fixtures. Preview signer cannot authorize production. Validate local health, cancellation, retention and operational audit with denied egress and no consent; preserve analysis/signing separation and never finalize killed output as successful. Actual hosted leases, admission and audit persistence remain R04.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P47 of 52, not a whole epic or a release authorization.

## P48 - E14.4: Rehearse official public signing and publication preflight

**Owner:** B | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E14.4. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E14.2, E00.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Run the Engine-contained release preflight through the authorized route established in R01; produce verifiable candidate blobs/image/catalog/SBOM/provenance.

### Acceptance criteria

Official public artifacts verify against approved OIDC identity and immutable digests. Existing read-only monorepo CI cannot be relabeled as a publisher. Do not bypass workflow export exclusions. If R01 needs outside-Engine code changes, record the exact blocked release operation for separate authorization; coding completion alone does not close this story.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P48 of 52, not a whole epic or a release authorization.

## P49 - E15.3: Review candidate against every Engine release gate

**Owner:** C (coordination); A/B own their defects | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E15.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4, E15.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Retain per-repository results, resource envelopes, confusion matrices, UNKNOWN coverage, release-gate ledger and independently reviewed exception list.

### Acceptance criteria

All three tiers run before stable release; five repos do not replace 50. Security/rule semantics meet ratified bar; other declared depth gaps visible and reviewed. No open trust/privacy/determinism/installation blockers. Proposed operational budget tiers are replaced by measured published limits; unsupported is not counted as successfully assessed. Include cumulative checkpoint evidence through G40 and all repairs on the exact candidate. No unresolved defect against delivered acceptance criteria, unexplained skip, unsupported verification claim or release blocker may pass. Remaining Platform/R05 work is explicitly out of this gate, not a waiver for missing Engine behavior.

### Measurement definitions

#### M33 - Coverage, determinism and performance acceptance

**Family / outcome:** Cross-cutting / Validation

**Inputs and scope:** All artifacts, capability records and corpus manifests

**Definition and calculation:** Per capability: evaluated eligible units / all eligible units; separately unknown/not-applicable/excluded/error. Runtime wall duration/peak RSS on declared host. Three-repeat semantic digest equality. Also record local health/progress/terminal states, hard deadlines/cancellation grace, peak output/disk usage and retention behavior. Freeze numerical bounds before affected qualification; failed/unrun checks are never recorded as PASS.

**Rule, threshold and interpretation:** Proposed initial tiers: <=10k eligible files 10min/2GiB; <=100k 30min/8GiB on 4vCPU. Measure/tune before publication; exceeding budget never silently truncates success.

**Required evidence:** Per-repo SHA/config/feed/hardware, counts, resource logs and semantic hashes.

**Missing/partial behavior:** Unknown denominator => coverage unknown. A survival run is not proof of analytical correctness.

**Required fixtures:** Dogfood; >=50 identified large repos; labeled flagship subset; resource exhaustion; corruption; repeat variation. SIGINT/SIGTERM/hard kill; disk full; output collision; concurrent reader; retention preserving active baseline; audit redaction.

**Owning stories:** E15.1, E15.2, E15.3.

**Report acceptance:** Per-capability coverage/freshness records defined above must survive JSON and HTML projection, including vulnerability-feed and Git-history reasons. Verify the visible report views in E11.2 and installed-artifact journeys in E11.3/P46 at G50; G40 verifies the delivered report projection and candidate-install smoke. A rendered healthy-looking empty table cannot substitute for explicit UNKNOWN or no-baseline behavior.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P49 of 52, not a whole epic or a release authorization.

## P50 - E16.1: Freeze and sign off the exact release candidate

**Owner:** C | **Group:** 5 | **Required preceding gate:** G40 PASS

### Start instructions

Implement only E16.1. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G40 PASS on a recorded reviewed SHA and direct prerequisites: E15.3. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Freeze source commit, version, package/catalog/container digests, compatibility map and review record. Prepare release notes and verified rollback instructions.

### Acceptance criteria

No mutating stable artifacts or reusing an existing version. Version chosen from actual live baseline, not assumed 0.2.2. Verify Engine-only diff and source-export inventory. Do not update VS Code, Platform, Webapp, AWS deployment, root scripts or export rules as part of release. Material post-freeze change creates a new candidate. G50 must verify this exact qualified candidate before prompt 51 is released. A change after E15.3 invalidates affected evidence and requires requalification; never rebuild different bytes and reuse an earlier signature/test record.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P50 of 52, not a whole epic or a release authorization.

## P51 - E16.2: Publish through the authorized Engine-only route

**Owner:** C | **Group:** 6 | **Required preceding gate:** G50 PASS

### Start instructions

Implement only E16.2. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G50 PASS on a recorded reviewed SHA and direct prerequisites: E16.1. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Release owner publishes precisely reviewed Engine source/package/image artifacts with signatures, attestations and verification instructions.

### Acceptance criteria

External R01 is closed and release approval records exact digests. No bulk mirror publish, Platform deployment or forced user upgrade. Verify public downloads independently. If publisher cannot operate without forbidden code changes, release remains blocked; do not claim success from a local build. Requires G50 PASS and release-owner authorization identifying exact versions/digests/registries and the R01 route. This planning/prompt document does not itself authorize a public release. Prepare a reviewable publication plan if authorization is absent; do not publish, move tags or update mirrors automatically.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P51 of 52, not a whole epic or a release authorization.

## P52 - E16.3: Smoke-test published artifacts and transition the team

**Owner:** C | **Group:** 6 | **Required preceding gate:** G50 PASS

### Start instructions

Implement only E16.3. Before editing, read the revised backlog story, the full shared semantics and applicable measurements in CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, and the standing policy/checks in CodeStrata-Engine-Team-Execution-and-Quality-Gates.md under engine/docs/implementation or supplied as explicit reviewed inputs. If unavailable, report BLOCKED; do not use the old ZIP/JSON as fallback.

Verify G50 PASS on a recorded reviewed SHA and direct prerequisites: E16.2. Verify the current checkout/dirty inventory and eligible integration branch. Historical Epic/Slice numbering is unrelated. No self-merge, next-group implementation, outside-Engine edits, root Cursor configuration, live upgrade, automatic publish/tag/deploy or notifications. New behaviors must preserve no-consent local utility, evidence honesty and the single YAML runtime boundary.

### Read and change scope

Read actual implementation around these paths; some proposed files may not exist yet. Verify behavior rather than treating old docs as locked design. Reuse stable code within the revised contract. Allowed edits: engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.. Any further Engine-local path needs recorded reviewer approval; outside-Engine scope remains forbidden.

### Deliverable

Install the published version on a clean host and assess five pinned representative repos, exercising CLI, reports, no-consent mode, MCP and one known comparison.

### Acceptance criteria

Verify expected results and signatures using published bytes, not source checkout. Proposed 3-business-day observation window starts after smoke passes; assign C to release support while A/B prepare Platform/Webapp foundations. Blocking regression stops new recommendation and triggers documented rollback to a trusted prior version. Platform assessment integration opens only after these checks; no false production-readiness claim. Complete G52 on independently downloaded public bytes. Preserve the original five-repository smoke and defined observation window; no Platform assessment integration begins until published-artifact smoke passes. Continue Engine support for blocking regressions.

### Measurement definitions

This story owns shared contract, operation or release requirements. Read the full shared measurement semantics; lack of a per-story M ID does not waive those requirements.

### Verify and report

Run the due scope/lint/strict-type/full-active-test/coverage/security and affected contract/regression checks from the execution policy. Add independent expected fixtures for new logic, including negative/partial/unsupported cases and budget failures where applicable. Do not fabricate tests for a read-only story; capture its actual inspected evidence and baseline gate results. Preserve the configured coverage floor, never hide skips, and record true exit codes. Future unimplemented gates remain explicitly not yet due; every acceptance item promised here must be proven.

Produce a concise completion record: changed files; exact SHA and artifact/config/input digests where relevant; acceptance-to-test map; commands/results and skip reasons; known limitations; defect IDs; reviewer required; and PR text for release/engine-next. A different engineer reviews before integration. If any criterion fails, mark the story incomplete and repair it; do not advance the counter. This prompt is P52 of 52, not a whole epic or a release authorization.
