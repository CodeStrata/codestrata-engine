# CodeStrata Engine MVP - Implementation Backlog

## Revision note — 15 September 2026

**Package revision: `ENGINE-2026-09-15-R1`.** Targeted launch amendment: first-class Engineering Hotspots; scoped repository-local ownership concentration; explicit boundary-spread and blast-radius summaries; report-facing capability coverage/freshness; visible HTML comparison and evidence views; installed-artifact report acceptance; and package revision verification. E08.3 is now a hard prerequisite of E10.2, bringing the plan to 99 hard story links. The 17 epics, 52 stories, 33 measurement groups, five analyzer families and four public outcomes are preserved. Engine remains database-free, Platform-independent and deterministic with YAML-only rule execution. No new score, analyzer family, public outcome, CodeGraph/RAG or customer-rule authoring scope is added.

This revision updates these five Markdown specifications. The master prompt book, all 52 split prompts and execution ZIP must be reconciled against this revision and reviewed before copying or G00 PASS; this delivery does not certify those older artifacts as updated. Existing numeric compatibility behavior is governed by the unchanged no-opaque-score contract; it is not a new launch score.

Version 1.2 | 15 September 2026 | For Satish, Vinay and three Engine engineers

**Recommendation:** proceed with one isolated Engine release, developed by three engineers against fixed contracts. Release the verified Community package, test the published artifacts on representative repositories, then move the main team into Platform and Webapp assessment integration. Webapp foundations can progress earlier in a separately owned scope without assessment wiring.

This is a concrete planning backlog, not evidence that implementation or release gates have passed. It contains 17 epics, 52 implementation stories, a companion 33-entry measurement/evidence contract, 99 hard dependency links and a companion Markdown prompt book. This Markdown edition supersedes the older JSON/CSV exports; update its companion prompt book and measurement contract together.

## 1. Scope and source authority

The user's current instruction is the implementation boundary: **every repository file edit for these stories stays under `engine/`**. That includes runtime, tests, fixtures, schemas, dependencies, documentation, examples and release helpers. No edits to `platform/`, Webapp, `infrastructure/`, `vscode-plugin/`, root workflows, root scripts, root packaging/lockfiles, export manifests or database migrations. Reading them and running relevant existing checks is allowed. Scanning Platform source for dogfood is read-only and does not make it a Platform implementation epic.

No application code is changed by this planning task. The attached specifications remain unchanged. Their meaningful requirements have been mapped to Engine responsibilities; a table describing 57 Platform tables is not 57 Engine database stories.

| Input | Authority used |
|---|---|
| Engine boundary v2.1, 12 September | Five families, four outcomes, complete local utility, YAML runtime, RuleSets/overrides, trust, corpus and required measurement contract |
| Architecture v2.1 | Database-free Engine, one-way dependency, file artifacts, neutral execution and signed projections |
| AWS deployment reference v1.0 | API Gateway/Lambda retained; managed workers and data lake remain outside this Engine code backlog |
| Database v2.1 | Platform-only persistence; Engine receives resolved rules and emits versioned artifacts; Community consent categories |
| Platform boundary v1.1 | Governance ownership, comparison semantics and future Engine consumer requirements |
| Current monorepo | Available reviewed checkout: `3f32ce4b82a06162062babf7e8c77451f5761e6a`. Static inspected code, not a completed runtime acceptance audit |

The current package metadata says `codestrata` 0.2.1; the actual live registry/container release is a separate fact to confirm in E00.1. Do not call the new release 0.2.2 automatically: database/CLI/contract changes may require a different version and migration notice.

## 2. Bounded reconciliation decisions

1. **Engine §13 prerequisite is supplied here.** The companion Measurement, Metrics & Evidence Contract identifies launch definitions before analyzer story implementation. E01.1 ratifies proposed defaults and compatibility; it is a short engineering checkpoint, not a new market/product exercise.
2. **Engine completion is independent of Platform completion.** Engine §9 gate10 is split by the user's Engine-first sequence: Engine-owned neutral consumer/package fixtures must pass now; real hosted ingestion/governance/worker integration is explicitly carried to Platform. Do not mark that later gate as passed by a fake consumer.
3. **A few repositories are a checkpoint, not the entire release corpus.** Use five representative repositories early and again on published artifacts. The locked specification still requires dogfood, >=50 identified large external repos, and labeled flagship ground truth before stable release. This plan preserves that gate without adding Platform work to the Engine corpus run.
4. **No code is moved into Platform during boundary cleanup.** Isolate or remove active hosted/portfolio/strategic paths inside Engine, preserve compatible public adapters where sound, and write a handoff inventory. Rehoming features is later Platform work.
5. **The source-quarantine sentence in AWS Figure1 is erroneous.** Its text says Engine fetches source from quarantine. Use the consistent intended flow: authorized source/local checkout -> Engine -> result artifact quarantine -> Platform verification/admission. No source-quarantine service is introduced into Engine.
6. **The older Fargate API row is superseded.** API Gateway/Lambda remains the API target. This is context only; no AWS deployment ticket is in the Engine backlog.
7. **Server collection does not become an Engine dependency.** Preserve compatible existing optional telemetry; prepare/test separate evidence/graph exports through an isolated adapter. New collection capability is not claimed live until the separate server accepts that contract. Local analysis always works without it.
8. **Official release has a real operational prerequisite.** Current root CI validates but does not publish, and the Community export excludes workflow files. Nothing under Engine can automatically grant the missing OIDC/release identity or bypass that exclusion. Resolve R01 at kickoff, not at the end.

## 3. Verified reuse and implementation gaps

| Inspected implementation | Reuse | Required Engine work |
|---|---|---|
| `engine/pyproject.toml`: standalone package, Python>=3.12, CLI, optional AI/MCP extras, strict mypy and configured coverage threshold80 | Package and checks | Verify actual wheel/sdist dependency closure; versioned schemas/catalog/assets; no DB runtime |
| `infrastructure/knowledge_store/factory.py` inside Engine constructs `SqliteKnowledgeStore` | Knowledge ports and query shape | Replace active composition with memory/files; preserve old artifacts through explicit export only |
| `application/rules/executor.py` invokes Python applicability/evaluate methods | Registry/planner/emission/suppression patterns | Bounded typed YAML plan; migrate every launch rule, not two parallel production runtimes |
| `application/rules/security/pack.py`: eight existing hygiene rules, disabled by default; CVE explicitly deferred | Pattern/evidence fixtures | Validate YAML migration, activate only tested catalog, deepen supply chain and pinned-feed matching |
| Language providers Java/JS/Python/PHP/C# and manifest collectors | Actual extraction adapters | Publish supported depth; normalize facts/coverage and explicit unknowns |
| Git revision and `application/incremental/` substrate | Input observation, reuse and comparison patterns | Full bounded history/diff metrics, identity and cause-aware comparison |
| CLI/reporting/MCP/AI/telemetry code | Useful local UX, projections and consent scaffolding | Remove broad/hosted paths, file-only queries, AI equivalence and privacy checks |
| Root `scripts/release/` generates SBOM/checksum/provenance; export is allowlisted | Read/run existing compatible tools unchanged | Put any new Engine helper in exported Engine paths; verify signer/publisher route separately |

This is reuse plus substantive completion, not a rewrite of every analyzer. No automated Engine test suite was run for this planning audit. Historical test counts and static implementation presence are not acceptance evidence.

## 4. Three-engineer ownership and parallel work

Use roles A/B/C until Vinay assigns names. These are three people, not seven simultaneous workstreams.

| Engineer | Primary ownership | Review responsibility |
|---|---|---|
| A - Contracts and rule runtime | E01, E03, E04, then E07 Architecture and E11 local reports/CLI | Shared schema owner; reviews comparison and trust binding |
| B - Facts, flagship analysis and trust | E05, E06, E08, then E13 privacy and E14 verification/distribution | Security/evidence quality and redaction; reviews DSL safety |
| C - Isolation, change and release | E00, E02, E09, E10, E12; coordinates E15/E16 | Runtime boundary, compatibility, corpus execution and release operations |

Reserve roughly 20% of each engineer's capacity for review, fixtures and integration. This is planning capacity, not additional staffing. Each engineer has at most one primary implementation story in progress. Whoever finishes a lane early takes an independent fixture/defect story, not concurrent edits to another owner's schema or shared executor. Security and DSL changes require review by a second engineer before integration.

### Execution order and mandatory checkpoints

Use the exact P01-P52 table in the companion Team Execution and Quality Gates document. Work in groups of 10 across the whole team, with audits G10/G20/G30/G40/G50 and a final G52 after two release stories. Only dependency-ready stories in the current group may run concurrently. Audit cumulative integrated work, repair all delivered-scope gaps, rerun due checks and obtain a different engineer's review before unlocking the next group. Fix attempts do not advance the prompt count.

The first group's E00.2 establishes quality evidence and scope controls. Current root engine-tests runs pytest without explicit lint/type/coverage collection; record those checks separately through the Engine-owned runner and reviewer gate. Later E15.2 extends the harness instead of starting quality enforcement late. The full operating policy and commands in the companion document are normative for every story.

This remains a three-person plan. Trust work is concentrated on B later; A/C can help with fixtures/review within the agreed ownership. Do not claim all listed opportunities can run simultaneously or turn group numbers into calendar promises.

## 5. Protecting today's Community Engine

Use a dedicated `release/engine-next` integration branch from the verified baseline, which is covered by current `release/**` CI triggers. Epic branches merge there. Keep the stable branch, registry version, mirror branch and container tag unchanged until E16. No auto-update of customer installations. Never force-push or overwrite release tags/artifact versions. A branch alone is insufficient: publisher triggers, registry tags, cache directories and source-mirror target must also be isolated.

Install candidates in a separate virtual environment or pinned container. Use a separate versioned output/cache directory. Read old snapshots without mutating them; optional migration writes a new output and preserves original files. A user upgrading deliberately receives documented command/config/schema changes. Do not preserve an unsafe old runtime merely to avoid a migration note.

Engine-only PR scope guard checks both the individual change and final cumulative release diff. Baseline includes read-only consumer checks for current Platform and extension imports/DTO expectations. Preserve required legacy adapters inside Engine if they can be pure projections. If an unavoidable break requires a consumer change, keep the old contract/version available and defer cutover; do not fix it by editing another package. Existing unrelated workspace changes are excluded from the release diff.

Run the current Engine CI job plus Engine-owned checks. New helpers should live under paths already allowed by the Community export, such as `engine/verification/`, `engine/examples/`, `engine/schemas/` and packaged resources. The root export does not currently include a new top-level Engine Dockerfile or arbitrary `engine/scripts/` directory by default; use an allowed path, verify exported output, and do not loosen the root allowlist. Workflow files are explicitly excluded: adding `engine/.github/workflows/` is not a solution to R01.

## 6. Definition of Done for every story

- The story's output, dependency IDs, owner and allowed Engine paths are explicit. Source/spec references and measurement IDs are present where applicable.
- Public contracts are versioned and reviewed by A. No rule-specific evaluator/metric logic is duplicated in a report or simulated consumer.
- An analyzer slice includes input/facts, deterministic derivation, YAML evaluation, evidence, coverage/status, comparison-ready identity, projections and independent fixtures. Unsupported/missing cases remain explicit.
- All relevant Engine tests, lint, strict type checks and configured >=80% coverage pass without lowering gates or deleting negative tests. This records tests to perform, not results already obtained.
- No DB, Platform import, hosted identity, arbitrary source execution or consent dependency enters canonical runtime. Test both a clean installation and restarted file-only reading where relevant.
- Security/DSL/trust work receives independent review. Raw secrets and source instructions cannot escape into telemetry or gain execution authority.
- Documentation states what the result proves and its limits. Evidence of completion is linked in the story; a passing source test is not a published-artifact test.

Story data uses exact hard prerequisites. The group gate is an additional scheduling condition, not a replacement for direct prerequisites. All stories share the reviewed evidence path engine/docs/implementation; necessary further Engine-local path additions require recorded reviewer approval. Outside-Engine changes remain excluded.

## 7. Changes from v1.0

The seven completeness amendments are incorporated directly into the stories and measurement contract: supplied PR/history context; combined change concerns; executable preview; corrected formulas; exact lifecycle/outcome-driver semantics; headless operational controls; and dependency/packaging fixes. Hard prerequisites added: E05.2 -> E09.3, E08.2 -> E10.2, E14.2 -> E11.3; this revision also adds E08.3 -> E10.2. Total 99 links, acyclic. No new epic or story.

Additional prompt/process corrections: no root Cursor rules installation; no stale generator dependency; no claim of current remote verification; quality evidence begins in E00.2; all stories require another engineer's review; no automatic public release; cumulative audits every 10 stories. Actual implementation and all future checkpoint results are still pending.


## Epic register

| Epic | Outcome | Owner | Size | Entry and parallel opportunity |
|---|---|---|---|---|
| E00 | Protect the live release and establish the working baseline | C | M | Immediately; parallel: E01; E05 discovery; E15 corpus design |
| E01 | Freeze measurement and public Engine contracts | A | L | Immediately; parallel: E00; E05 discovery; E15 corpus design |
| E02 | Remove database and hosted runtime dependencies | C | L | After E01.2; migration audit can start immediately; parallel: E03; E05; E06 fixture work |
| E03 | Build the bounded YAML compiler and evaluator | A | XL | After E01.2/3; parallel: E02; E05; E09 fixture work |
| E04 | Resolve RuleSets and typed effective configuration | A | L | Pure resolution after E01.3; final handoff after E03; parallel: E06; E09; E14 trust scaffolding |
| E05 | Normalize fact extraction and repository inventory | B | L | Discovery now; implementation after E01.2; parallel: E02; E03; E09 |
| E06 | Deliver flagship Security and Supply Chain evidence | B | XL | After E05.2 and E03.3; parallel: E04; E07 where owner available; E09 |
| E07 | Deliver architecture structure and boundary checks | A | L | After E05.2 and E03.3; A takes this after E04; parallel: E06; E09 |
| E08 | Deliver Quality, Testing and Maintainability | B | L | After E05.2/E03.3; B takes this after E06; parallel: E07; E09/E10 |
| E09 | Build bounded Git history and diff inputs | C | L | After E01.2/E02.2; parallel: E04; E06; E07 |
| E10 | Implement supplied-state comparison and movement | C | L | After E09.3 and E01.3; parallel: E07; E08; E11 |
| E11 | Complete the local CLI and report journey | A | L | Schema-based adapters after E01.2; final journey after analyzer integration; parallel: E08; E10; E13 |
| E12 | Narrow local MCP and isolate optional AI | C | M | After E02.2; final checks after E11.2; parallel: E11; E13; E14 |
| E13 | Preserve privacy controls and optional collection adapter | B | M | Can prototype after E01.2; B completes after E08; parallel: E11; E12; E14 scaffolding |
| E14 | Complete trust verification and distributable Engine artifacts | B | XL | Trust-policy investigation starts at E00; implementation after E01.3; parallel: E07; E10; E11; E12 |
| E15 | Run corpus, determinism, security and scale acceptance | C (coordination); A/B own their defects | L | Corpus design immediately; closure after integrated candidate; parallel: All development epics, using each engineer's validation capacity |
| E16 | Release Community Engine and hand over to Platform | C | M | After E15.3 and external release prerequisite R01; parallel: Post-release Platform/Webapp planning; no overlapping engine feature changes |

## Detailed implementation stories

### E00 - Protect the live release and establish the working baseline

**Completion outcome:** An isolated next-release lane with a verified path to Community publication.

**Owner:** C | **Source:** User scope; Engine §§7,9

**External story prerequisites for epic completion:** None. Refer to individual story dependencies for when work can start.

#### E00.1 - Record the live artifact and release route

**Prompt:** P04 | **Group:** 1 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** None; also require the preceding group gate.

**Allowed implementation paths:** engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation.

**Deliver:** Record current PyPI/container/mirror versions, immutable digests, stable branch/tag and release identities in engine/docs/release/baseline.md. Inventory the existing authorized publisher as prerequisite R01.

**Acceptance:** Do not infer live version from pyproject 0.2.1 or tags. Verify install/rollback using the actual released artifact. Identify which workflow can obtain the required OIDC identity and publish Engine alone. If none exists, R01 is blocked, not assumed solved. No workflow, export-manifest or remote changes in this story.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E00.2 - Create Engine-only scope and compatibility guards

**Prompt:** P01 | **Group:** 1 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** None; also require the preceding group gate.

**Allowed implementation paths:** engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation; engine/pyproject.toml; engine/.gitignore.

**Deliver:** Engine-owned check plus PR checklist: changed tracked files must remain under engine/. Record clean baseline checks and outside-Engine consumer imports read-only.

**Acceptance:** Guard rejects edits, renames or deletions outside engine/, including root scripts, workflows, lockfiles and export manifest. Tests run through the existing engine-tests job. Baseline failures are recorded separately; they cannot be relabeled as new passing tests. No production publish credentials in normal tests. Establish the executable quality-command manifest and cumulative scope guard from the first story, not only at E15. Record full lint/type/test/coverage results and baseline failures. Inspect added/untracked files, rename source and destination, deletions, staged and unstaged changes and the cumulative release diff; compare against the pre-existing working-tree inventory without resetting unrelated work. Place checks in engine/verification and collect appropriate scope regression tests through the existing test path. Record reviewer and gate evidence under engine/docs/implementation. The existing root engine-tests command is not proof of lint/type/coverage execution; mandatory local or authorized-runner evidence is required until an existing compatible runner executes those checks. Do not edit root CI.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E00.3 - Establish integration, hotfix and prerelease isolation

**Prompt:** P09 | **Group:** 1 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E00.1, E00.2; also require the preceding group gate.

**Allowed implementation paths:** engine/tests/verification; engine/docs/release; engine/verification; engine/docs/implementation.

**Deliver:** Document release/engine-next integration branch, short epic branches, one stable maintenance lane and versioned candidate artifact/output namespaces.

**Acceptance:** Existing CI push pattern covers release/**. Normal merges do not publish or move stable tags. Candidate installs use a separate virtual environment and local output directory, never upgrade live installs or rewrite existing snapshots. Backport live hotfixes deliberately into next; preserve exact rollback artifacts.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E01 - Freeze measurement and public Engine contracts

**Completion outcome:** One versioned contract for all five families and four outcomes.

**Owner:** A | **Source:** Engine §§3,5,12,13; Architecture §4

**External story prerequisites for epic completion:** None. Refer to individual story dependencies for when work can start.

#### E01.1 - Ratify launch measurements and depth matrix

**Prompt:** P02 | **Group:** 1 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** None; also require the preceding group gate.

**Allowed implementation paths:** engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.

**Deliver:** Adopt the companion Measurement, Metrics & Evidence Contract; record formula/default changes before analyzer coding. Close launch depth, feed source/freshness, history and budget choices in an Engine-owned decision file.

**Acceptance:** Every M01-M33 has inputs, formula, subject, evidence, missing-data behavior and fixtures. Java and JS/TS are the proposed deepest paths; Python/PHP/C# retain only verified tiers. Thresholds below are proposed engineering defaults, not calibrated universal standards. No broad product redefinition. Ratify the revised M06/M09/M12 denominators, M24 history/message indicators, M27 supplied context, M29 change-concern predicate and M28-M30 lifecycle/outcome-driver manifest. Close numeric hard deadlines, cancellation grace, regex/memory/file/output limits and the supported depth/feed/profile choices before their affected stories. Map existing rule IDs, confidence taxonomy and context-derived severity to the new contract: do not invent an incompatible ID restriction or retain a hidden severity rewrite after an approved override. Record each decision and independent reviewer; Cursor cannot self-ratify proposed defaults.

**15 September 2026 acceptance amendment:** Ratify M22 ranking/context roles, M25 scoped denominators, M27/M29 boundary definitions and report-facing coverage/freshness reasons before implementation; preserve the no-opaque-score decision. Propagate this revision into P02 and affected prompts before G00.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E01.2 - Publish versioned descriptors, facts, IDs and envelopes

**Prompt:** P05 | **Group:** 1 | **Owner:** A | **Size:** L | **Status:** Not started

**Hard prerequisites:** E01.1; also require the preceding group gate.

**Allowed implementation paths:** engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.

**Deliver:** AnalyzerDescriptor plus neutral assessment/fact/graph/evidence schemas, stable identity, canonical serialization profile and complete example artifact set.

**Acceptance:** Descriptor includes reads/emits, applicability, depth, schemas, budgets, network, coverage and failures. Envelope separates deterministic body from time/signature/run metadata. No tenant/workspace/portfolio/job identity in analysis body. Existing subject/finding identity is mapped deliberately; unknown fields and unsupported major versions reject. Publish the launch outcome-driver manifest with rule/metric ID, family, outcome/context role, applicability, direction, comparison unit, epsilon, coverage requirement and empty-scope behavior. Canonical required scopes and known violations cannot disappear through aggregation. Bind any source-derived context severity choice into the versioned rule/default/config contract; preserve default/effective severity and approved override provenance.

**15 September 2026 acceptance amendment:** Publish the first-class M22 Engineering Hotspot schema, scoped M25 records, M27/M29 change-summary fields and per-capability coverage/freshness schema with complete, partial, UNKNOWN and no-baseline example envelopes. Validate contributor roles, evidence/finding references and canonical priority explanation. P05 must carry these requirements.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E01.3 - Publish rules, comparison and neutral invocation contracts

**Prompt:** P08 | **Group:** 1 | **Owner:** A | **Size:** L | **Status:** Not started

**Hard prerequisites:** E01.2; also require the preceding group gate.

**Allowed implementation paths:** engine/schemas; engine/src/codestrata/domain; engine/docs/contracts; engine/tests/contracts; engine/docs/implementation.

**Deliver:** Rule, RuleSet, Effective RuleSet, signed-package manifest, comparison envelope and headless local job schemas. Supply good/bad consumer examples under engine/tests/contracts.

**Acceptance:** Bind resolved ruleset/package/config/feed/input digests and versions; preview purpose is distinct. Compare schema preserves compatibility and cause attribution. Invocation accepts local paths, pinned inputs and export/trust configuration, not Platform credentials. Validate independently installed wheel without importing Platform. Include bounded optional locally supplied PR title/description/base/head/labels/linked-reference strings and their supplied provenance/context digest. Define neutral candidate-validation and preview inputs/results, permitted scope, purpose and expiry, plus local progress/cancellation/terminal-state schema. No hosted calls or approval identities enter canonical computation.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E02 - Remove database and hosted runtime dependencies

**Completion outcome:** Standalone assess, compare and local MCP use memory/files only.

**Owner:** C | **Source:** Architecture §§0.1,1.2,4.4; Engine §7

**External story prerequisites for epic completion:** E00.2, E01.2. Refer to individual story dependencies for when work can start.

#### E02.1 - Trace active SQLite, hosted and portfolio call paths

**Prompt:** P06 | **Group:** 1 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E00.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Map CLI/assess/compare/MCP/provider factory imports, installed dependencies and current persisted snapshots. Classify each old surface: retain, adapt, deprecate or quarantine.

**Acceptance:** Trace runtime composition as well as imports: factory.py currently constructs SqliteKnowledgeStore. Record Platform/extension consumers before narrowing interfaces. Do not copy code into platform/ or workers/. Historical code may remain isolated only if absent from supported runtime and default package dependency closure.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E02.2 - Implement bounded file artifact storage and queries

**Prompt:** P11 | **Group:** 2 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.2, E02.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Atomic versioned JSON/JSONL manifests, bounded indexes, integrity checks, streaming reads and query ports; replace production factory composition.

**Acceptance:** Fresh wheel can assess, restart, open evidence and compare offline with sqlite3.connect blocked and no DB drivers/services. Interrupted writes do not expose partial completed snapshots. Limit memory, reject path escapes, detect corrupt/missing blobs; rebuild derived indexes from valid manifests. No destructive auto-migration. Prove interruption, concurrent output collision, concurrent readers, disk-full behavior, local retention/cleanup and protection of source, supplied baselines and unrelated files. Expose a completed manifest only after atomic finalization. Preserve safe incomplete status; never sign killed/partial output as successful completion. Support local status/health without an HTTP service or database.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E02.3 - Narrow Engine surfaces and preserve supported compatibility

**Prompt:** P14 | **Group:** 2 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E02.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store; engine/src/codestrata/application/knowledge; engine/src/codestrata/integration; engine/src/codestrata/artifacts; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Remove active portfolio/EIR/hosted submission/strategic-agent paths from Community execution. Keep small Engine-local compatibility projections only where safe; document deprecated commands and old snapshot export.

**Acceptance:** No Platform calls from canonical runtime; no customer rule authoring or portfolio lifecycle through CLI/MCP. Legacy SQLite export, if needed, is a separately invoked maintainer helper, never imported by the runtime. Read-only outside-Engine consumer checks identify breaking contracts; do not fix them by editing outside engine/. Old files and prior installs remain untouched.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E03 - Build the bounded YAML compiler and evaluator

**Completion outcome:** One safe declarative runtime for every launch executable rule.

**Owner:** A | **Source:** Engine §5; Architecture §4.2

**External story prerequisites for epic completion:** E01.3. Refer to individual story dependencies for when work can start.

#### E03.1 - Validate YAML and compile typed selector ASTs

**Prompt:** P12 | **Group:** 2 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.

**Deliver:** Safe loader, schema/capability validation, pinned selector binding and serializable intermediate plan.

**Acceptance:** Reject duplicate keys, unknown tags/fields, executable strings, alias expansion, invalid types and excessive nesting/bytes. No eval/import/shell/network/file operator. Unsupported facts or operators return a structured capability error. A selector change cannot masquerade as presentation metadata.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E03.2 - Implement the declared bounded operator set

**Prompt:** P15 | **Group:** 2 | **Owner:** A | **Size:** L | **Status:** Not started

**Hard prerequisites:** E03.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.

**Deliver:** Typed selection, numeric/set, graph, change and threshold operators listed in Engine §5, with truth tables and cost limits.

**Acceptance:** Direct traversal is depth 1; transitive has positive bounded max_depth. declared/resolved dependency view is independent. UNKNOWN propagates under three-valued evaluation; a cutoff never proves absence. Empty/zero denominators, numeric rounding, percentile definition and cycle behavior match the measurement contract. Every operator has positive, negative and budget fixtures.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E03.3 - Enforce execution budgets and common emission semantics

**Prompt:** P17 | **Group:** 2 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E03.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/src/codestrata/domain/rules; engine/tests/application/rules; engine/docs/implementation.

**Deliver:** Planner/executor integration, per-rule/workload budgets, cancellation, evidence validation and minimal generic JSON/HTML/SARIF projections. These common adapters land here; E11 improves the complete CLI/report experience.

**Acceptance:** No legacy Python rule evaluate() path in launch catalog; trusted Python extractors/operators remain allowed. Malicious regex/graph/input fixtures terminate within configured budgets. FAIL is a supported violation; ERROR is processing failure. Disabled/suppressed scope remains visible. Same effective plan and facts yield identical results. Freeze numeric hard limits and cancellation behavior from E01.1; enforce process-level termination for pathological regex/native parsing as appropriate. Prove timeout/grace/termination and bounded diagnostics. No deadline may depend solely on a cooperative in-process callback. Add preview execution parity through the same compiler and operators; purpose checks integrate with E14.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E04 - Resolve RuleSets and typed effective configuration

**Completion outcome:** Shared pure resolver; no policy service, approval store or tenant logic.

**Owner:** A | **Source:** Engine §5 locked refinements; Platform §9; Database §5.1

**External story prerequisites for epic completion:** E01.3, E03.3. Refer to individual story dependencies for when work can start.

#### E04.1 - Implement pinned composition and deterministic precedence

**Prompt:** P13 | **Group:** 2 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.

**Deliver:** Pure in-memory/file RuleSet resolver plus release-time pre-resolution command for bundled catalog.

**Acceptance:** Reject missing/cyclic/floating references and excessive size/depth. Later ordered parents override earlier configuration; explicit child revision resolves parent revision conflict. Maps merge by defined fields; lists/scalars replace, omitted inherits, null is not reset. Conflicting selector ASTs cannot shadow. Resolve identical input bytes deterministically.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E04.2 - Apply typed overrides and resolved scoped exceptions

**Prompt:** P16 | **Group:** 2 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E04.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.

**Deliver:** Bounded typed override model for severity, enabled, exposed parameters, presentation fields and pre-authorized subject scope.

**Acceptance:** Reject off as severity, out-of-range parameters and executable messages. Selector/schema/operator changes require new rule revision. Deduplicate equal cross-policy effective rules retaining opaque attributions; reject conflicting revisions/settings and overlapping exception values. Only opaque references and resolved local subject scopes reach Engine; no approver, organization or workspace authority model.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E04.3 - Seal the effective digest and prove execution parity

**Prompt:** P20 | **Group:** 2 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E04.2, E03.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules; engine/schemas; engine/tests/contracts; engine/docs/contracts; engine/docs/implementation.

**Deliver:** Canonical resolved bytes/digest with resolver/DSL/capability versions, defaults, scoped settings and attribution. Integrate prebuilt Community packages and neutral customer-package fixtures.

**Acceptance:** Compare reviewed candidate and resolved production bytes. Expiry cannot exceed included exception validity; time is supplied as execution context and admission records it separately. Changing parent order/effective settings changes digest; changing rendered message never changes finding fingerprint. Local parameters hash separately from signed base. Preview never silently becomes production. Execute candidate compliant/violating/UNKNOWN fixtures and permitted snapshot previews through a neutral local entrypoint using the production compiler/operators. Return typed diagnostics, expected/actual fixture outcomes, coverage and preview-only results bound to candidate/selector/effective-setting/input/Engine/DSL digests. Stale preview evidence, parameter changes, selector rebinding, scope violations and attempted production promotion must fail the applicable checks. Approval remains Platform-owned; no customer-authoring Community CLI surface.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E05 - Normalize fact extraction and repository inventory

**Completion outcome:** Reliable inputs and scope for every family, without executing repository code.

**Owner:** B | **Source:** Engine §4A; Architecture §4.1

**External story prerequisites for epic completion:** E01.2, E03.3. Refer to individual story dependencies for when work can start.

#### E05.1 - Inventory existing extractors and pin supported depth

**Prompt:** P03 | **Group:** 1 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** None; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.

**Deliver:** Reuse/deepen Java, JS/TS, Python, PHP and C# providers; fixture map for build/manifests, language and source classification.

**Acceptance:** Count detection separately from structural support. Map actual parser outputs to facts; unsupported syntax/frameworks stay declared. Do not install dependencies or execute tests, hooks, package scripts or builds to discover evidence. Early discovery has no dependency on completed runtime.

**Measurement IDs:** M01, M02, M03. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E05.2 - Emit source, dependency, API and CI facts with coverage

**Prompt:** P07 | **Group:** 1 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E01.2, E05.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.

**Deliver:** Stable repository/component/file/symbol IDs; manifest and lock facts; static import/API/config/build/CI observations; classification and evidence references.

**Acceptance:** Preserve declared vs resolved dependencies; missing lockfile is not resolved absence. Evidence includes exact local source revision/content digest and location. Symlink escape, huge/binary/generated/vendor files and parse failure produce bounded, visible scope. CI command found in YAML proves configuration, not successful execution. Use declaration IDs as the unit for dependency-resolution coverage and preserve resolution occurrences separately. For normalized change facts, expose stable file/component mapping before E09.3 closes.

**Measurement IDs:** M01, M02, M03, M04. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E05.3 - Close the inventory vertical slice

**Prompt:** P18 | **Group:** 2 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E05.2, E03.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/services/analyzers; engine/src/codestrata/domain/repository_graph; engine/tests; engine/docs/implementation.

**Deliver:** Capability manifests and inventory/coverage projections through common envelope and report adapters.

**Acceptance:** All M01-M04 fixtures cover valid/absent/partial/unsupported/corrupt/deterministic cases. Inventory supplies no invented health score. Every enabled analyzer sees compatible registered facts. No parser-specific logic required by the consumer contract.

**Measurement IDs:** M01, M02, M03, M04. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E06 - Deliver flagship Security and Supply Chain evidence

**Completion outcome:** Redacted, reproducible security results with pinned feed provenance.

**Owner:** B | **Source:** Engine §4C; §§1,9 flagship depth

**External story prerequisites for epic completion:** E01.1, E03.3, E05.2. Refer to individual story dependencies for when work can start.

#### E06.1 - Migrate and validate secret and configuration rules

**Prompt:** P19 | **Group:** 2 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E05.2, E03.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.

**Deliver:** Convert applicable existing eight hygiene rules into bundled YAML; deepen verified patterns and redact before any persisted evidence or diagnostics.

**Acceptance:** Known real-format synthetic keys, placeholders and safe lookalikes have distinct expected behavior. Raw secret values never appear in reports, logs, telemetry, fixture output snapshots or MCP output. TLS/auth/CORS/debug findings cite exact supported configuration evidence, without runtime exploitability claims. Reuse security context classification as evidence only where supported; reconcile any old severity/confidence adjustment with the immutable rule contract. A post-processing stage must not silently override approved effective severity or alter canonical rules outside the YAML runtime.

**Measurement IDs:** M10, M11. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E06.2 - Implement resolved supply-chain and vulnerability matching

**Prompt:** P22 | **Group:** 3 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E05.2, E03.3, E01.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.

**Deliver:** Normalize selected feed to pinned local snapshots; deterministic package/version/range matching, alias deduplication and direct/transitive path evidence.

**Acceptance:** Feed provider/license/freshness decision is closed before this story. Offline cache absence/staleness reports UNKNOWN for matching scope, never zero CVEs. Test withdrawn advisories, aliases, prereleases, unsupported version schemes, missing lock roots and transitive paths. No mandatory live lookup during canonical evaluation. For M12, count fully resolved eligible declarations divided by eligible declarations in the same declared contexts. Multiple resolved versions/transitive packages cannot inflate coverage above one. Test partial contexts, one declaration/multiple versions, missing locks, zero and unknown denominator.

**Measurement IDs:** M12, M13. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E06.3 - Complete version hygiene, license evidence and accuracy gate

**Prompt:** P25 | **Group:** 3 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E06.1, E06.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/evidence; engine/src/codestrata/application/rules/security; engine/src/codestrata/application/rules/dependency; engine/tests; engine/docs/implementation.

**Deliver:** YAML rules for unresolved/mutable/conflicting declarations, deterministic license metadata and published per-rule validation results.

**Acceptance:** License risk is against an explicit configured allow/deny list, not legal compliance. Publish confusion counts and precision/recall on labeled evaluable units, UNKNOWN separately. Proposed release bar: precision >=95% and recall >=90% per flagship rule group with >=20 positive and >=20 negative labeled cases; no known critical false-negative or secret leak. Team ratifies targets before tuning; no cherry-picked exclusions.

**Measurement IDs:** M14, M15. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E07 - Deliver architecture structure and boundary checks

**Completion outcome:** Inspectable module/file relationships and conformance within verified precision.

**Owner:** A | **Source:** Engine §4B; §5 module example

**External story prerequisites for epic completion:** E03.3, E04.3, E05.2. Refer to individual story dependencies for when work can start.

#### E07.1 - Normalize structural edges and cycle metrics

**Prompt:** P23 | **Group:** 3 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E05.2, E03.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Observed/declared edge types, stable graph IDs, module SCC cycle count and coupling metrics through YAML rules.

**Acceptance:** Implement imports, depends_on, implements, exposes_API and uses_dependency only at supported confidence/depth. Call edges remain limited to reliable cases. No cross-repository/runtime-topology inference. Cycle and coupling fixtures include unresolved edges and partial source roots.

**Measurement IDs:** M05, M06. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E07.2 - Implement declared-boundary and concentration checks

**Prompt:** P26 | **Group:** 3 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E07.1, E04.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Module-boundary example, allowed direction/pattern configuration, component concentration and reach metrics.

**Acceptance:** API-to-internal direct import fixture violates; API-to-public passes; unresolved import yields UNKNOWN. Every violation shows the concrete path. Separate dependency_view from traversal; bounded reach discloses truncation. Local pattern configuration is explicit and included in run digest. M09 excludes the seed from distinct incoming neighbors and deduplicates parallel edges within the declared node universe. Test singleton/self-loop/two-node graphs and partial universes. Define M06 external-edge ratio over eligible file import edges classified by component, rather than a module graph containing only cross-module edges.

**Measurement IDs:** M07, M08, M09. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E07.3 - Migrate remaining launch architecture rules and validate depth

**Prompt:** P29 | **Group:** 3 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E07.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/domain/repository_graph; engine/src/codestrata/application/rules/architecture; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Parity map from retained Python rules to YAML IDs and four-outcome graph/evidence projections.

**Acceptance:** Every retained launch rule has compliant, violating and incomplete fixtures, stable identity and validated defaults. No silent old-to-new score equivalence claims. Validate Java and JS/TS structural paths and declared lower tiers; output supports later comparison without consumer analyzer logic.

**Measurement IDs:** M05, M06, M07, M08, M09. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E08 - Deliver Quality, Testing and Maintainability

**Completion outcome:** Two outcomes from measured structural and test/build evidence.

**Owner:** B | **Source:** Engine §4D

**External story prerequisites for epic completion:** E03.3, E05.2, E09.2. Refer to individual story dependencies for when work can start.

#### E08.1 - Define and emit structural quality metrics

**Prompt:** P27 | **Group:** 3 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E05.2, E03.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Size, supported function complexity/nesting and token-clone indicators, all with exact versioned derivations.

**Acceptance:** No universal language-independent maintainability index. Explicitly define token/branch rules for each supported language; ratio denominator and clone overlap handling match contract. Timeout/unsupported syntax gives partial coverage, not a zero. All outputs project from one canonical body.

**Measurement IDs:** M16, M17, M18. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E08.2 - Emit test association and declared CI gaps

**Prompt:** P31 | **Group:** 4 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E08.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Static test inventory/association, skipped-test counts and declared-test/coverage-command gaps.

**Acceptance:** Do not call test association measured runtime coverage. CI invocation evidence is static and conditional-job uncertainty remains visible. A missing coverage report is not 0% code coverage. Positive, negative, partial CI and unsupported test framework cases have expectations.

**Measurement IDs:** M19, M20, M21. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E08.3 - Complete evidence-backed maintainability prioritization

**Prompt:** P34 | **Group:** 4 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E08.2, E09.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/rules/testing; engine/src/codestrata/application/rules/technical_debt; engine/src/codestrata/application/evidence; engine/tests; engine/docs/implementation.

**Deliver:** Churn-weighted complexity, dependency staleness where metadata exists and deterministic risk tuples; migrate retained debt/testing rules to YAML.

**Acceptance:** Hotspots cite both complexity and history window. No developer productivity/blame or cost-to-fix estimate. Stable ordering uses declared tie-breakers; missing history produces UNKNOWN hotspot metric but does not erase static findings. Policy/default changes remain visible. Provide exact churn/complexity and eligible component evidence for E10.2 change concerns. Do not equate a high hotspot rank with runtime failure probability or introduce an opaque aggregate score.

**15 September 2026 acceptance amendment:** P34 emits the unified M22 Engineering Hotspot records and preserves complexity × churn ordering and stable component-ID ties. Centrality/reach, supported scoped ownership and active finding links are contextual only. Emit pinned history, contributor coverage and priority explanation. Test context-only changes cannot change rank, and partial/UNKNOWN ranking inputs remain unranked with known static evidence retained. Reuse supported structure only; do not add a new analyzer.

**Measurement IDs:** M22, M23. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E09 - Build bounded Git history and diff inputs

**Completion outcome:** One-pass file/component history and supplied change evidence.

**Owner:** C | **Source:** Engine §4E; §12 history decision

**External story prerequisites for epic completion:** E01.3, E02.2, E03.3, E05.2. Refer to individual story dependencies for when work can start.

#### E09.1 - Pin working, staged, range and patch input states

**Prompt:** P21 | **Group:** 3 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.3, E02.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.

**Deliver:** Read-only Git input resolver and local-state digests; preserve base/head/tree/index/patch identity without mutating the checkout.

**Acceptance:** Working-tree/staged mode, rename, binary, shallow history, missing base, submodules and supplied patch fixtures are explicit. Never fetch silently or switch branch. A patch without resolvable base may supply changed-line facts but not a fabricated full comparison. No PR comments/checks or hosted GitHub integration. Accept optional bounded supplied PR metadata through E01.3, without GitHub/ticket lookup. Conflicting base/head context is visible; narrative context is untrusted and cannot change canonical facts/findings/verdicts. Test absent/oversized/malformed/injection text, base/head mismatch and context-only changes. Escape projections and exclude raw metadata from anonymous telemetry.

**Measurement IDs:** M27. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E09.2 - Create bounded history index and temporal metrics

**Prompt:** P24 | **Group:** 3 | **Owner:** C | **Size:** L | **Status:** Not started

**Hard prerequisites:** E09.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.

**Deliver:** Single-pass JSONL/file index for commits, renames, file/component churn, recency, ownership concentration and co-change.

**Acceptance:** Default window and merge/rename policy are pinned. Shallow/truncated history advertises exact observed bounds. Identity is repository-local and respects pinned mailmap policy; no organization attribution. Parse rename/numstat deterministically; binary sizes remain unknown. Use the ratified M24 history traversal/time/merge policy, with exact observed bounds, pinned UTC evaluation time and deterministic ties. Never silently combine first-parent traversal with skipping all merges. Implement bounded versioned commit-message bug-fix markers as context only, with observed commit evidence and no verified-defects/intent/productivity claims. Test merge-only integration, squash, future timestamps, boundary and shallow history.

**15 September 2026 acceptance amendment:** P24/P28 must implement and verify M25 repository/component/file concentration using subject-local attributable-line denominators, pinned identities/history and mapping coverage. Preserve M26 temporal co-change/support semantics. Expose observed/requested history bounds and freshness/UNKNOWN reasons for each Git-derived capability; no organizational bus-factor or productivity claim.

**Measurement IDs:** M24, M25, M26. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E09.3 - Publish reusable change facts and equivalence fixtures

**Prompt:** P28 | **Group:** 3 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E09.2, E03.3, E05.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/infrastructure/knowledge_store/git_revision.py; engine/src/codestrata/application/incremental; engine/src/codestrata/repository_auth; engine/tests; engine/docs/implementation.

**Deliver:** Normalized change events and graph/input identity fixtures; incremental reuse eligibility against a full reference assessment.

**Acceptance:** Cache key binds source/config/rule/operator/feed versions. Rename moves location without arbitrary finding churn when matching is supported. Ambiguous lineage is UNKNOWN. Selective and full evaluation match semantically; use full fallback when proof is insufficient. Prove raw Git observations join E05.2 stable file/component identities; unsupported mappings remain explicit. PR narrative-only changes cannot alter analysis truth; history/message indicators retain separate provenance.

**15 September 2026 acceptance amendment:** P24/P28 must implement and verify M25 repository/component/file concentration using subject-local attributable-line denominators, pinned identities/history and mapping coverage. Preserve M26 temporal co-change/support semantics. Expose observed/requested history bounds and freshness/UNKNOWN reasons for each Git-derived capability; no organizational bus-factor or productivity claim.

**Measurement IDs:** M24, M25, M26, M27. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E10 - Implement supplied-state comparison and movement

**Completion outcome:** Traceable repository-level deltas without hosted baseline ownership.

**Owner:** C | **Source:** Engine §4E; Platform §10.1; Architecture §5.3

**External story prerequisites for epic completion:** E01.3, E06.3, E07.2, E08.2, E08.3, E09.3. Refer to individual story dependencies for when work can start.

#### E10.1 - Match finding lifecycle and compatible metric deltas

**Prompt:** P32 | **Group:** 4 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E09.3, E01.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.

**Deliver:** Versioned finding matching and new/resolved/improved/worsened/unchanged/unknown lifecycle over explicitly supplied states.

**Acceptance:** Absence under failed/incomplete coverage never resolves a finding. Message-only changes keep identity; severity overrides do not look like code fixes. Rule/schema/config/feed compatibility checked before movement. Old incompatible snapshots remain readable or explicitly unsupported, never silently converted to equivalent truth. Persistent findings improve/worsen only against a rule-declared compatible violation magnitude. A remaining binary violation is unchanged; falling below the condition resolves only after complete compatible reevaluation. Severity/config/message/location changes cannot masquerade as a code fix. Test magnitude reduction that still violates, binary persistence, empty outcome and disabled-all scope.

**Measurement IDs:** M28. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E10.2 - Calculate graph delta, impact and change verdicts

**Prompt:** P35 | **Group:** 4 | **Owner:** C | **Size:** L | **Status:** Not started

**Hard prerequisites:** E10.1, E07.2, E08.2, E08.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.

**Deliver:** Changed graph nodes/edges, bounded reverse-dependency blast radius, test-touch evidence and deterministic outcome movement.

**Acceptance:** Precedence is Insufficient evidence > Mixed > Deteriorated > Improved > Stable. Improved requires real favorable movement. No composite average hides deterioration. Impact is static possible reach, not runtime impact probability. Exceeding budget marks incomplete evidence. Execute the versioned M29 change-concern join over changed subjects and declared base/candidate churn/centrality evidence. Emit individual reasons, scope/denominators, thresholds and witnesses; retain partial known contributors. Test changed high-churn/high-centrality, ordinary change, unchanged hotspot, deletion/rename and missing data. Use E08.2 associations for impacted tests. Outcome movement uses the explicit E01 driver manifest and M30 empty/partial-scope rules, not an implicit list or average.

**15 September 2026 acceptance amendment:** P35 consumes E08.3 hotspot/churn/complexity evidence; wait for that reviewed prerequisite. Implement M27/M29 boundary spread, distinct crossed-boundary pairs, affected-component/test sets and counts with base/candidate witnesses, de-duplication, coverage and traversal cutoffs/lower bounds. Test absent declarations versus exact zero and partial test associations. Keep concerns contextual and outcome drivers explicit.

**Measurement IDs:** M29, M30, M31. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E10.3 - Separate source, feed and configuration causes

**Prompt:** P38 | **Group:** 4 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E10.2, E06.3, E08.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/incremental; engine/src/codestrata/services; engine/src/codestrata/models/scan_comparison.py; engine/tests; engine/docs/implementation.

**Deliver:** Cause metadata and controlled comparison fixtures for unchanged code/new CVE, dependency fix, policy override, changed coverage and mixed inputs.

**Acceptance:** Same-code feed change labeled feed-driven. If source and feed both change, controlled reruns can isolate causes; otherwise report mixed/undetermined. Compare all five families without Platform imports, DB or hidden baseline selection. Preserve explicit qualifying changes and denominators.

**Measurement IDs:** M28, M29, M30, M31. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E11 - Complete the local CLI and report journey

**Completion outcome:** Useful local init/doctor/assess/compare with JSON, HTML and SARIF.

**Owner:** A | **Source:** Engine §§2.1,7,9

**External story prerequisites for epic completion:** E01.2, E02.3, E03.3, E04.3, E06.3, E07.3, E08.3, E10.3, E14.2. Refer to individual story dependencies for when work can start.

#### E11.1 - Deliver backward-aware CLI and configuration

**Prompt:** P33 | **Group:** 4 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E02.3, E04.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.

**Deliver:** init, doctor, assess --repo --no-ai and explicit compare contract; documented bundled parameters/exclusions/suppressions and migration messages.

**Acceptance:** No credentials/login prompt or collection opt-in required for assess. Doctor lists supported capabilities/trust/config, not mandatory cloud setup. Command/exit/config compatibility is mapped from live baseline. Community does not expose custom-rule creation/loading as a supported UI. Defaults include only validated bundled catalog.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E11.2 - Project consistent JSON, HTML and SARIF

**Prompt:** P36 | **Group:** 4 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.2, E03.3, E07.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.

**Deliver:** One canonical result to three outputs, with evidence drilldown, four outcomes, supporting inventory/Git views and separate coverage/trust states.

**Acceptance:** HTML works locally without CDN/server and escapes source/messages. SARIF fingerprints and severity mapping are stable; UNKNOWN is disclosed without manufacturing a clean scan. Metrics that do not fit SARIF findings stay in documented properties/JSON. Display default/effective severity, suppressions and exception attribution. Show snapshot status, execution status, coverage and verification independently; unavailable/NOT_APPLICABLE outcome is not a healthy badge. Preserve preview purpose and context-only change concerns. All outputs obey the ratified driver manifest and corrected metric semantics.

**15 September 2026 acceptance amendment:** P36: HTML must visibly present: (1) Engineering Hotspots with ranking/context labels, contributor values, priority explanations and linked findings/evidence; (2) repository/component/file ownership concentration with scope, denominator, pinned history and limitations; (3) temporal co-change with pair, support and union denominator; (4) change-summary/blast-radius counts, boundary spread/crossed-boundary pairs, affected components/tests and traversal limits; (5) per-capability coverage and freshness, including vulnerability feed and Git history with explicit UNKNOWN reasons; and (6) a Before / After / Delta table of compatible named metrics with units, scope, both coverages, outcome movement and linked qualifying/excluded drivers and cause/compatibility reasons. A first run visibly says no baseline and makes delta/movement unavailable; partial or incompatible comparisons retain qualified known observations without inventing zero, Stable or improvement. HTML projects the canonical Engine result, order, calculations and verdicts; it must never calculate its own scores, ranking, deltas or outcome movement. No new numeric score is added.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E11.3 - Verify first assessment, partial run and comparison journeys

**Prompt:** P46 | **Group:** 5 | **Owner:** A | **Size:** M | **Status:** Not started

**Hard prerequisites:** E11.1, E11.2, E06.3, E08.3, E10.3, E14.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/cli; engine/src/codestrata/reporting; engine/src/codestrata/resources; engine/docs; engine/examples; engine/tests; engine/docs/implementation.

**Deliver:** End-to-end clean-directory journeys over built wheel, including helpful actionable failures and compatible comparison.

**Acceptance:** A first run says no baseline; no trend invented. A meaningful finding can be traced to source evidence and after a controlled fix has expected lifecycle. Failed family retains coverage limitations; secret redaction holds in every format. Docs and samples require no monorepo-only paths. Run these journeys on the built candidate wheel from E14.2, installed outside checkout with no source-tree PYTHONPATH. Record artifact digest and verify installed schemas/catalog/assets and no-database restart behavior.

**15 September 2026 acceptance amendment:** P46: Generate reports by executing the installed Engine on pinned repository/Git/feed fixtures with independently expected real values; report screenshots or hand-authored envelopes alone do not pass. Verify every E11.2 visible view and its links against the canonical result for complete, partial, UNKNOWN and no-baseline inputs, plus compatible before/after movement and incompatible comparison. Include stale/missing vulnerability feed, shallow/missing Git history, unknown ownership mapping, impact cutoff and missing test association. Assert no synthetic zeros, healthy badges, trend or HTML-calculated score. Record installed artifact digest, canonical/result/report digests, expected/actual values, link checks and a visual review of the generated local HTML. Run the full journey on the E14.2 wheel outside checkout; G50 repeats report acceptance across independent wheel, sdist and container installations of the exact candidate.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E12 - Narrow local MCP and isolate optional AI

**Completion outcome:** Read-only evidence access with optional non-canonical explanation.

**Owner:** C | **Source:** Engine §§2.5,6.2,7

**External story prerequisites for epic completion:** E02.3, E10.3, E11.2. Refer to individual story dependencies for when work can start.

#### E12.1 - Serve bounded local evidence queries from artifacts

**Prompt:** P40 | **Group:** 4 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E02.3, E11.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.

**Deliver:** Repository/snapshot/component/finding/metric/dependency/change/evidence/lineage tools with pagination and explicit local root scope.

**Acceptance:** No database, mutation, assessment execution, rule activation, shell, hosted calls, portfolio query or GraphRAG tool. Reject arbitrary paths and unknown artifact versions. Tests attempt unauthorized files, oversized results and query budgets; read-only access does not need collection consent.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E12.2 - Retain one optional local/BYO explanation path

**Prompt:** P42 | **Group:** 5 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E12.1; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.

**Deliver:** Reuse one existing provider adapter behind optional dependencies; explanation artifact cites permitted evidence IDs and provider/model.

**Acceptance:** AI is disabled by default and excluded from canonical computation. Network denial/provider failure yields an explanation error without changing assessment status or canonical digest. No arbitrary tool execution from source instructions. Prompt/evidence egress is explicitly enabled independently of product telemetry.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E12.3 - Prove AI-on/off and local MCP equivalence

**Prompt:** P44 | **Group:** 5 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E12.2, E10.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/interfaces/mcp; engine/src/codestrata/ai; engine/src/codestrata/application/knowledge; engine/tests; engine/docs/mcp; engine/docs/implementation.

**Deliver:** Mode matrix over same pinned inputs; provider success, timeout, injection and disabled cases.

**Acceptance:** Canonical findings/metrics/severity/coverage/verdicts remain semantically identical; only separate AI artifact differs. MCP returns same canonical evidence without requiring an AI provider. Export limitations and missing citations are visible; unsupported AI claims cannot enter scores.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E13 - Preserve privacy controls and optional collection adapter

**Completion outcome:** No-consent local operation plus compatible, isolated opt-in collection.

**Owner:** B | **Source:** Architecture §0; Database §§2,7; Engine §2.4

**External story prerequisites for epic completion:** E01.3, E02.3. Refer to individual story dependencies for when work can start.

#### E13.1 - Enforce durable opt-in and no-egress defaults

**Prompt:** P37 | **Group:** 4 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E02.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.

**Deliver:** Local versioned consent/preferences, per-run deny, inspect/enable/disable controls and cancellation of pending collection.

**Acceptance:** No consent means no evidence/graph/telemetry transmissions from local Engine adapters. Noninteractive CI never invents consent. Disable survives restart and cancels queued sends. Upload/analytics failure cannot fail analysis. Prohibited-data canaries cover logs, retry queues and telemetry serialization.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E13.2 - Preserve current telemetry wire and prepare scoped JSON export

**Prompt:** P39 | **Group:** 4 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E13.1, E01.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.

**Deliver:** Maintain accepted existing aggregate payload semantics. Separately serialize permitted evidence/graph export with schema/digest/notice/category fields; use a local fake collector for new capability contracts.

**Acceptance:** Do not edit Community API, S3 or infrastructure. Existing telemetry does not carry findings/snippets/repo names. New evidence/graph upload remains unavailable unless the actual collector advertises supported schema and receipt/capability checks; no speculative live v2 calls. Local preview/export proves payload construction without claiming server readiness.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E13.3 - Test export restrictions and signed-projection integrity

**Prompt:** P41 | **Group:** 5 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E13.2; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/telemetry; engine/src/codestrata/cli/telemetry_cmd.py; engine/tests; engine/docs; engine/docs/implementation.

**Deliver:** Explicit full/restricted/no-export modes for headless invocation with a manifest of withheld categories.

**Acceptance:** No-export retains local functionality and emits no data transfer. Redaction cannot mutate signed canonical bytes: preserve local original and produce a separate projection with original digest/export-policy/withheld markers for signing. Test revocation/expired receipt using fake collector; actual server deletion/admission remains follow-on work.

**Measurement IDs:** M32. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E14 - Complete trust verification and distributable Engine artifacts

**Completion outcome:** Verifiable wheel, sdist, container, bundled packages and offline result provenance.

**Owner:** B | **Source:** Engine §§2.3,2.6,9; Architecture §§4.3,6.3

**External story prerequisites for epic completion:** E00.3, E01.3, E02.3, E04.3, E13.3. Refer to individual story dependencies for when work can start.

#### E14.1 - Implement strict package/release verification profiles

**Prompt:** P43 | **Group:** 5 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E01.3, E04.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Public Sigstore expected identity/issuer/bundle verification and one bounded private/offline self-managed-key profile, with version/expiry/revocation-policy checks.

**Acceptance:** Real cryptographic valid/tampered/wrong-issuer/wrong-purpose/expired/unsupported fixtures, not a mocked signature boolean. Public distribution and private result signer roles are distinct. Private rule/result contents never enter a public transparency log. Offline profile states freshness limits, not instant revocation.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E14.2 - Build standalone wheel, sdist and non-root container

**Prompt:** P45 | **Group:** 5 | **Owner:** B | **Size:** L | **Status:** Not started

**Hard prerequisites:** E02.3, E14.1, E04.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Engine-contained build/release verifier under allowed export paths; container build recipe under engine/examples. Bundle resolved YAML/schemas/assets and pinned runtime lock inputs inside engine/.

**Acceptance:** Install wheel and sdist outside checkout; no monorepo PYTHONPATH or DB dependency. Container supports no-network execution, read-only source, non-root user, explicit writable temp/output, CPU/memory/time limits and cleanup. SBOM covers resolved runtime dependencies; provenance/checksums bind exact artifact digests. No new root workflow/export-manifest edits. Explicit Engine-local packaging files are permitted. Keep reproducible lock inputs in exported paths; verify public source export and wheel/sdist inclusion separately. Supply a local health/status command or file protocol, retention configuration, bounded audit events, SIGINT/SIGTERM/grace/hard-stop behavior, and cleanup/disk-full/read-only-source fixtures. No raw source/PR text/secrets in operational logs. Bind measured limits into the headless contract.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E14.3 - Sign results and prove headless consumer interoperability

**Prompt:** P47 | **Group:** 5 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E14.2, E13.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Neutral local invocation runner and Engine-owned consumer fixtures; detached result/projection signatures from a separate signing process.

**Acceptance:** Same Engine accepts a valid prepared customer Effective RuleSet, emits standard artifacts and is read by an independent schema consumer without custom analyzer code. Reject invalid/preview-only package for production purpose. Analysis process cannot access signer credentials. Local restricted/no-export runs and cancellation work without AWS or Platform. Actual lease, upload and hosted admission are not claimed. Actually run valid preview-purpose and production-purpose packages in separate permitted contexts, not only rejection fixtures. Preview signer cannot authorize production. Validate local health, cancellation, retention and operational audit with denied egress and no consent; preserve analysis/signing separation and never finalize killed output as successful. Actual hosted leases, admission and audit persistence remain R04.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E14.4 - Rehearse official public signing and publication preflight

**Prompt:** P48 | **Group:** 5 | **Owner:** B | **Size:** M | **Status:** Not started

**Hard prerequisites:** E14.2, E00.3; also require the preceding group gate.

**Allowed implementation paths:** engine/src/codestrata/application/release; engine/src/codestrata/resources; engine/verification; engine/examples; engine/docs/release; engine/tests; engine/docs/implementation; engine/pyproject.toml; engine/MANIFEST.in.

**Deliver:** Run the Engine-contained release preflight through the authorized route established in R01; produce verifiable candidate blobs/image/catalog/SBOM/provenance.

**Acceptance:** Official public artifacts verify against approved OIDC identity and immutable digests. Existing read-only monorepo CI cannot be relabeled as a publisher. Do not bypass workflow export exclusions. If R01 needs outside-Engine code changes, record the exact blocked release operation for separate authorization; coding completion alone does not close this story.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E15 - Run corpus, determinism, security and scale acceptance

**Completion outcome:** Reviewed evidence for release, not just a count of passing tests.

**Owner:** C (coordination); A/B own their defects | **Source:** Engine §9 all three corpus tiers

**External story prerequisites for epic completion:** E00.2, E01.1, E02.3, E03.3, E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4. Refer to individual story dependencies for when work can start.

#### E15.1 - Pin corpus manifests and independent labeled fixtures

**Prompt:** P10 | **Group:** 1 | **Owner:** C (coordination); A/B own their defects | **Size:** M | **Status:** Not started

**Hard prerequisites:** E00.2, E01.1; also require the preceding group gate.

**Allowed implementation paths:** engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.

**Deliver:** Three tiers: CodeStrata dogfood, >=50 large identified external repositories, and labeled flagship ground truth. Store URL/SHA/license/size/language, window, inputs and expectations.

**Acceptance:** Five early representatives: supported Java, JS/TS, mixed build/monorepo, retained lower-depth stack, and partial/unsupported case. Select all 50 with explicit scale/diversity criteria; no duplicate clones or convenience replacement to hide failures. Fixture labels precede tuning. Public scan is read-only; no repository code changes. Prepare corpus manifests and independent fixture labels early; existing 22-repository documentation is a discovery lead, not evidence that it meets the 50-large-repository bar. Create checkpoint evidence and defect-ledger templates. Keep public-reproducible inputs under engine/verification/validation and engine/tests without private/customer content.

**Measurement IDs:** M33. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E15.2 - Automate deterministic and adversarial regression checks

**Prompt:** P30 | **Group:** 3 | **Owner:** C (coordination); A/B own their defects | **Size:** L | **Status:** Not started

**Hard prerequisites:** E15.1, E03.3, E02.3; also require the preceding group gate.

**Allowed implementation paths:** engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.

**Deliver:** Engine-owned lint/type/coverage, contract, tamper, malicious-source, report escaping, no-egress and repeated-run harnesses. Use existing CI test invocation and local/authorized runner where needed.

**Acceptance:** Keep configured 80% coverage minimum and strict checks; no skipped-test inflation. At least three repeats per corpus configuration with semantic comparison excluding only declared operational fields. Full-vs-incremental parity, old-client contracts and installed artifacts are covered. No executing scanned project tests/build scripts. Extend the checks already established in E00.2 and G10/G20; do not defer quality enforcement until this story. Keep the configured 80% combined coverage floor with branch measurement enabled; do not call it a separate 80% branch threshold. Every skip, unavailable tool and unrun required check is disclosed. Re-run affected prior checks and cumulative regressions after repairs.

**Measurement IDs:** M33. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E15.3 - Review candidate against every Engine release gate

**Prompt:** P49 | **Group:** 5 | **Owner:** C (coordination); A/B own their defects | **Size:** L | **Status:** Not started

**Hard prerequisites:** E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4, E15.2; also require the preceding group gate.

**Allowed implementation paths:** engine/tests; engine/verification/validation; engine/verification; engine/docs/validation; engine/docs/implementation.

**Deliver:** Retain per-repository results, resource envelopes, confusion matrices, UNKNOWN coverage, release-gate ledger and independently reviewed exception list.

**Acceptance:** All three tiers run before stable release; five repos do not replace 50. Security/rule semantics meet ratified bar; other declared depth gaps visible and reviewed. No open trust/privacy/determinism/installation blockers. Proposed operational budget tiers are replaced by measured published limits; unsupported is not counted as successfully assessed. Include cumulative checkpoint evidence through G40 and all repairs on the exact candidate. No unresolved defect against delivered acceptance criteria, unexplained skip, unsupported verification claim or release blocker may pass. Remaining Platform/R05 work is explicitly out of this gate, not a waiver for missing Engine behavior.

**Measurement IDs:** M33. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

### E16 - Release Community Engine and hand over to Platform

**Completion outcome:** A published, verified Community release followed by bounded real-world smoke checks.

**Owner:** C | **Source:** User release sequence; Engine §9

**External story prerequisites for epic completion:** E15.3. Refer to individual story dependencies for when work can start.

#### E16.1 - Freeze and sign off the exact release candidate

**Prompt:** P50 | **Group:** 5 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E15.3; also require the preceding group gate.

**Allowed implementation paths:** engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.

**Deliver:** Freeze source commit, version, package/catalog/container digests, compatibility map and review record. Prepare release notes and verified rollback instructions.

**Acceptance:** No mutating stable artifacts or reusing an existing version. Version chosen from actual live baseline, not assumed 0.2.2. Verify Engine-only diff and source-export inventory. Do not update VS Code, Platform, Webapp, AWS deployment, root scripts or export rules as part of release. Material post-freeze change creates a new candidate. G50 must verify this exact qualified candidate before prompt 51 is released. A change after E15.3 invalidates affected evidence and requires requalification; never rebuild different bytes and reuse an earlier signature/test record.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E16.2 - Publish through the authorized Engine-only route

**Prompt:** P51 | **Group:** 6 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E16.1; also require the preceding group gate.

**Allowed implementation paths:** engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.

**Deliver:** Release owner publishes precisely reviewed Engine source/package/image artifacts with signatures, attestations and verification instructions.

**Acceptance:** External R01 is closed and release approval records exact digests. No bulk mirror publish, Platform deployment or forced user upgrade. Verify public downloads independently. If publisher cannot operate without forbidden code changes, release remains blocked; do not claim success from a local build. Requires G50 PASS and release-owner authorization identifying exact versions/digests/registries and the R01 route. This planning/prompt document does not itself authorize a public release. Prepare a reviewable publication plan if authorization is absent; do not publish, move tags or update mirrors automatically.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

#### E16.3 - Smoke-test published artifacts and transition the team

**Prompt:** P52 | **Group:** 6 | **Owner:** C | **Size:** M | **Status:** Not started

**Hard prerequisites:** E16.2; also require the preceding group gate.

**Allowed implementation paths:** engine/docs/release; engine/CHANGELOG.md; engine/pyproject.toml; engine/src/codestrata/__init__.py; engine/tests; engine/docs/implementation.

**Deliver:** Install the published version on a clean host and assess five pinned representative repos, exercising CLI, reports, no-consent mode, MCP and one known comparison.

**Acceptance:** Verify expected results and signatures using published bytes, not source checkout. Proposed 3-business-day observation window starts after smoke passes; assign C to release support while A/B prepare Platform/Webapp foundations. Blocking regression stops new recommendation and triggers documented rollback to a trusted prior version. Platform assessment integration opens only after these checks; no false production-readiness claim. Complete G52 on independently downloaded public bytes. Preserve the original five-repository smoke and defined observation window; no Platform assessment integration begins until published-artifact smoke passes. Continue Engine support for blocking regressions.

**Measurement IDs:** Shared contracts / operational requirements. All stories inherit the shared measurement semantics and execution policy.

**Completion evidence:** Actual checks, artifacts/commit references, limitations and different-engineer review; the next checkpoint must accept this story before the next group opens.

## Release prerequisites outside the Engine code backlog

These are operational/interface dependencies, not permission to edit other code or add Platform implementation stories.

| ID | Owner | Due | Required evidence | Effect if unresolved |
|---|---|---|---|---|
| R01 - official signing and publishing route | Vinay / authorized release owner; C investigates | Resolve at kickoff; rehearse before candidate qualification | Actual maintained route capable of OIDC-constrained public signing, registry/image publication and Engine-only source export; identities, permissions and trigger behavior verified | E14.4 and E16.2 blocked. Read-only root CI and excluded workflows cannot satisfy this. Any needed outside-Engine change requires a separately scoped decision, not an unnoticed backlog edit |
| R02 - actual live artifact baseline | C + release owner | E00.1 | Live package/image/mirror versions and digests; ability to install trusted prior release | Cannot claim live protection or safe rollback until verified |
| R03 - feed and supported depth | A/B, reviewed by Vinay | E01.1 before E06.2 | Named provider, permitted cache/metadata usage, freshness/range policy, primary and retained language tiers | Affected metrics remain unimplemented, not silently broadened or falsely clean |
| R04 - real hosted integration | Future Platform owner | After Engine release and published-artifact smoke | Actual worker/package roundtrip, upload/admission, tenancy and reports | Engine consumer readiness can pass now; commercial Platform acceptance remains open |
| R05 - new Community collection service | Future Community/Platform owner | Before enabling new live evidence/graph upload | Receipt/capability/schema/revocation/deletion support in actual service | Local/compatible telemetry continues; new export upload stays capability-gated. No API or lake changes hidden in this backlog |

R01 is a material feasibility finding, not a request to widen scope in advance. Complete the allowed Engine preparation and determine whether the existing release system can run it unchanged. If it cannot, report the exact required release operation and scope decision while continuing independent Engine work. Do not call a release “done” by weakening Sigstore requirements or bypassing the export policy.

## Release gate ledger and final acceptance

| Engine §9 gate | Engine backlog proof | Later work explicitly not claimed |
|---|---|---|
| 1 Boundary | E00/E02 installed dependency and runtime call audit | No Platform feature migration |
| 2 Determinism | E01 canonical identity; E09 reuse; E15 repeated corpus | No guarantee of arbitrary legacy formula equivalence |
| 3 YAML runtime | E03/E04; migration parity in E05-E08 | Platform draft/approval UI |
| 4 Analyzer depth | E05-E09 and E15 capability/corpus results | Extra language/framework breadth |
| 5 Change | E09/E10 working/staged/range/patch fixtures | Hosted PR lifecycle or required checks |
| 6 Evidence | All measurement slices; E11 outputs; E15 canaries | Hosted evidence permission layer |
| 7 External use | E14 built wheel/sdist/container; E16 downloaded release | Hosted onboarding |
| 8 Quality | Engine-owned checks via existing CI/authorized runner | Root workflow edits |
| 9 Performance | E15 all three tiers with published measured budgets | Platform bulk ingestion/load |
| 10 Platform contract | E01/E04/E14 independent consumer and customer-package fixtures | R04 actual hosted roundtrip, not marked passed |
| 11 Execution modes | E14 local/CI/headless private profile; E12 AI modes | Actual ECS provisioning, worker identity/lease/dispatch |
| 12 AI equivalence | E12 same inputs/canonical bytes | Governed hosted AI |
| 13 Privacy | E13 no-consent, denied egress, restricted export and client checks | R05 new collection server and tenant admin controls |
| 14 Sigstore | E14 real crypto/public signing rehearsal/private offline profile; E16 publication verification | Broad custom enterprise trust-root services |

Completion means the published Community artifact runs all five families to declared depth, outputs four evidence-backed outcomes, compares supplied states, executes only the supported YAML catalog, uses no database, supports narrow read-only local MCP and optional isolated AI, respects no-consent/no-egress mode, and has verifiable release/catalog provenance. It also supplies the neutral interfaces needed for later Platform-approved packages. It does not mean the commercial product or customer-VPC control plane is deployed.

Use five actual representative repositories for early pilot and post-publication smoke; choose them from the pinned 50-repository corpus. Their names/SHAs are assigned in E15.1 instead of invented in this planning document. Suggested mix is Java, JS/TS, multi-module mixed repository, retained lower-depth stack and unsupported/partial case. Include a controlled base/head fixture for a known change; random public edits are not reliable ground truth.

Proposed observation window is three business days after successful public-download smoke. A confirmed secret leak, unsigned/untrusted artifact labeled verified, canonical nondeterminism, data corruption, failed clean install or material live compatibility regression blocks promotion/continued recommendation. Preserve the bad artifact's evidence, stop new recommendations and use the approved rollback/yank policy without overwriting immutable versions. Nonblocking declared coverage gaps go into the patch queue with truthful release notes.

## Webapp foundation that can proceed separately

This is a handoff boundary, not part of the 17 Engine epics and not extra capacity assigned to the same three people. If one of them is assigned UI work now, Engine capacity decreases explicitly. Foundation work may run alongside Engine only with a separately allocated owner/capacity; after release A/B can shift while C handles the short observation window.

| Foundation | Can start without assessment integration | What requires separate Platform foundation | Do not wire yet |
|---|---|---|---|
| Webapp shell/design system | Routing, layout, accessible controls, loading/error states, mock fixture boundary and typed API client interfaces | Hosting/configuration decisions when actually deploying | Assessment execution or fake success through production routes |
| Signup/login screens | Forms, PKCE flow UI, terms version display, declined acceptance and session states | Real IdP setup/token validation, principal provisioning and recorded acceptance | Local-storage users presented as real authentication |
| GitHub connection screens | Installation selection, authorized repo picker and default/override branch UI with mocks | GitHub App credentials, state/installation validation, source permissions and safe backend token storage | GitHub App private keys or installation tokens in browser |
| Organization/workspace screens | Create/edit forms, memberships, role-aware navigation, configuration validation | Actual identity/tenant/RLS/authorization and organization repository catalog | Client-side-only permissions, a second incompatible data model |
| Repository membership configuration | Default branch UI, explicit selection, unavailable-branch states, free-plan one-repo UX | Server-side source verification, branch validation and entitlement enforcement | Starting assessments, baseline/report creation or worker registration success mocks in production |
| Assessment/report route placeholders | Honest empty states and development-only contract fixtures | Engine integration plus Platform job/artifact/report APIs later | Fabricated scores/history or fixtures mixed into real customer data |

Real signup, GitHub connection and workspace persistence are assessment-independent, but they are not backend-independent. They need a small separately scoped Platform identity/source/workspace foundation. Until that exists, keep those UI flows explicitly mocked and isolated from production configuration.

## Platform handoff package after Engine release

- Public versioned schemas and capability manifests, machine-readable definitions, stable identity/matching rules and compatibility matrix.
- Bundled signed Effective RuleSet, pure resolution API, approved-package fixture, preview-purpose negative fixture, typed overrides/conflict/expiry examples and safe-message semantics.
- Canonical assessment/evidence/graph/comparison artifacts with valid, partial, UNKNOWN, incompatible and tampered examples; restricted signed projection and withheld-data examples.
- Independently installed wheel/container invocation and resource contract, supported private/offline trust profile, signer separation, CLI/config migration notes and rollback digests.
- Full Engine release evidence plus five-repo published-artifact smoke report. Hosted gates R04/R05 remain explicitly open.
- Ownership inventory for the old hosted/portfolio/strategic surfaces removed from the active Engine path. Rehoming them is Platform scope and should reuse code only where its new boundary is sound.

## Source pointers and planning validation

Source review uses the available checkout pinned to [codestrata-platform commit 3f32ce4](https://github.com/CodeStrata/codestrata-platform/tree/3f32ce4b82a06162062babf7e8c77451f5761e6a). This edition uses the available pinned checkout; G00 must record the team's actual baseline and drift. Engine package paths in the epic records are relative to that monorepo; some proposed child schema/helper files do not exist yet and are deliverables, not current implementation claims.

Material inspected paths: `engine/pyproject.toml`, `engine/src/codestrata/infrastructure/knowledge_store/factory.py`, `engine/src/codestrata/application/rules/executor.py`, `engine/src/codestrata/application/rules/security/pack.py`, language/evidence providers, Git revision/incremental modules, MCP/telemetry entrypoints, `.github/workflows/ci.yml`, `public-export-manifest.yaml`, and `scripts/release/`.

The supplied document sections are referenced per epic. The latest RuleSet/override/exception refinements are fully carried into E01/E03/E04/E10/E11/E14. Source documents are not silently revised by this backlog. The older AWS source-quarantine wording and Fargate API row are resolved explicitly in §2.

This 15 September 2026 document amendment preserves 17 epic IDs, 52 story IDs and 33 measurement IDs. The revised backlog and P01-P52 dependency table contain 99 hard story links; E08.3 -> E10.2 is the added link. Prerequisites remain earlier in the numbered order and the graph is acyclic; groups remain 10, 10, 10, 10, 10 and 2. This validates document structure only. The prior PDF/generator/prompt comparisons describe the earlier delivery and do not certify this revision. The master prompt book, all split prompts and execution ZIP require reconciliation and review against this revision before copying or G00 PASS. No Engine runtime or release gate was run; G10/G20/G30/G40/G50/G52 remain NOT_RUN.

This review created Markdown planning documents only. No implementation prompts, external tickets, code changes, branches or releases were executed.
