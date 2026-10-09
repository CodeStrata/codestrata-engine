---
title: "CodeStrata Engine"
subtitle: "MVP Boundary & Native Analyzer Specification — v2.1 (15 September 2026 amendment)"
---

::: {.doc-meta}
<div><b>Document type:</b> Living product boundary and native-analyzer specification</div>
<div><b>Companion:</b> CodeStrata Platform MVP Boundary &amp; Product Specification v1.1</div>
<div><b>Revision:</b> 15 September 2026 — targeted launch evidence/report amendment</div>
:::

## Revision note — 15 September 2026

**Package revision: `ENGINE-2026-09-15-R1`.** Targeted launch amendment: first-class Engineering Hotspots; scoped repository-local ownership concentration; explicit boundary-spread and blast-radius summaries; report-facing capability coverage/freshness; visible HTML comparison and evidence views; installed-artifact report acceptance; and package revision verification. E08.3 is now a hard prerequisite of E10.2, bringing the plan to 99 hard story links. The 17 epics, 52 stories, 33 measurement groups, five analyzer families and four public outcomes are preserved. Engine remains database-free, Platform-independent and deterministic with YAML-only rule execution. No new score, analyzer family, public outcome, CodeGraph/RAG or customer-rule authoring scope is added.

This revision updates these five Markdown specifications. The master prompt book, all 52 split prompts and execution ZIP must be reconciled against this revision and reviewed before copying or G00 PASS; this delivery does not certify those older artifacts as updated. Existing numeric compatibility behavior is governed by the unchanged no-opaque-score contract; it is not a new launch score.

Existing product decisions are preserved; Section 5 and the decision register explicitly lock the RuleSet and governed-override foundation. The database-free Engine decision from the Architecture/Database baseline applies throughout.

## 1. Decision in one page

### Product boundary

> **CodeStrata Engine is the complete, trustworthy, local evidence and change-analysis runtime for one repository. Platform sells continuity, organizational context, portfolio intelligence, governance, curated decision IP, and the operating system around that evidence.**

The Engine must be valuable on its own. It must not depend on Platform, require an AI call, or hide the best deterministic analysis merely to create an upsell. Community trust is earned through reproducible evidence, precise scope, visible limitations, and useful local outcomes.

The commercial boundary is not “weak free analyzers versus strong paid analyzers.” It is:

- **Engine:** truth about one repository at a point in time or between two explicitly supplied states.
- **Platform:** memory and decisions across repositories, teams, releases, policies, and time, including customer-defined rule authoring and governance.

### MVP decision

Build five deep native analyzer families, supported by one shared fact/graph layer and one bounded YAML rule runtime:

1. **Repository & Technology Inventory** - establishes what exists and what coverage is possible.
2. **Architecture & Dependency Structure** - establishes how the repository is organized and coupled.
3. **Security & Supply Chain** - finds high-confidence source, configuration, secret, and dependency risks.
4. **Quality, Testing & Maintainability** - measures structural health, technical debt, and test/build discipline.
5. **Git & Change Intelligence** - connects structure to how the code changes and evaluates a supplied diff.

The four public assessment outcomes are **Architecture, Security, Quality, and Maintainability & Technical Debt**. Inventory is supporting context. Dependencies and Git intelligence contribute to multiple outcomes. Database-layer analysis and static observability posture are deferred past MVP as cross-cutting enrichments (see Section 4); Security and Architecture stand on their primary reads without them at launch. Cloud Readiness, AI Readiness, and static Performance remain experimental or deferred packs, not headline MVP outcomes.

Five families produce four outcomes because they don't map one-to-one, and that mapping is a stated decision rather than something to infer from each family's individual "Outcomes served" line:

| Family | Outcome(s) it produces | Role |
| --- | --- | --- |
| A. Repository & Technology Inventory | None directly | Supporting context and coverage baseline for the other four; not itself a scored outcome |
| B. Architecture & Dependency Structure | Architecture | Headline outcome |
| C. Security & Supply Chain | Security | Headline outcome; flagship depth tier |
| D. Quality, Testing & Maintainability | Quality; Maintainability & Technical Debt | Headline outcome; produces two of the four |
| E. Git & Change Intelligence | Contributes evidence to all four | Cross-cutting differentiator, not a fifth outcome |

### Depth investment tiering

Not every family earns equal validation effort before launch — spreading limited real-repository tuning cycles evenly across five families produces uniform shallowness, not uniform strength. Two surfaces are the flagship trust investment and receive first-class depth, adversarial review, and real-repository false-positive tuning before launch:

- **Security & Supply Chain** - the analyzer family most likely to be pressure-tested first by a buyer whose trigger is an audit, a regulatory requirement, or a customer security questionnaire.
- **The governed YAML rule-authoring pipeline** (draft, validate, sandboxed preview, human approval, signed distribution) - the capability that differentiates CodeStrata from a repository-intelligence tool, since it is what makes a customer's own standards enforceable and provable rather than merely observed.

Repository & Technology Inventory, Architecture & Dependency Structure, Quality/Testing & Maintainability, and Git & Change Intelligence ship at solid, evidence-backed v1 depth and iterate against real usage after launch. This is a build-sequencing decision, not a scope cut: all five families and all four public outcomes remain in the MVP boundary, and none may report a finding it cannot support merely because it received less initial tuning investment - insufficient coverage must still report `UNKNOWN`, never a confident but under-validated verdict.

The trust promise is precise:

> **Every canonical finding, metric, deviation, score, and verdict is traceable to evidence - or explicitly reported as `UNKNOWN`.**

This is a traceability and honesty guarantee, not a claim that static analysis is infallible. CodeStrata must expose coverage, confidence, derivation, and limitations rather than manufacture certainty.

### Non-negotiable execution rule

> **LLMs may author rules. Only the Engine executes rules.**

All CodeStrata and customer rules compile to the same versioned, declarative YAML DSL. Runtime execution is deterministic and contains no AI call, generated Python/JavaScript, arbitrary shell command, or dynamically loaded customer code. If a request cannot be represented by existing facts and operators, Platform must return **“requires a new Engine capability.”**

**Distribution boundary:** Community receives and runs only CodeStrata's bundled, prebuilt/pre-resolved signed YAML RuleSets as a supported product capability. Customer-specific rule creation, testing, approval, storage, governance, and distribution belong to Platform. Platform sends an approved rule package to the Engine, which executes it through the same deterministic runtime used for bundled rules.

## 2. Boundary tests

A capability belongs in **Engine** only when all of these are true:

- It can run locally against one repository or two explicitly supplied repository states.
- It produces reproducible evidence from declared inputs.
- It does not require tenant, organization, portfolio, billing, or hosted-service semantics.
- It can fail closed as `UNKNOWN`, `NOT_APPLICABLE`, or `ERROR` rather than inventing a pass.
- Its output is useful as a stable contract for Platform and third-party consumers.

A capability belongs in **Platform** when any of these are central to its value:

- cross-repository or business-system context;
- durable history across scans/releases and long-term drift;
- organizational ownership or team attribution;
- managed policies, approvals, exceptions, RBAC, audit, SSO, or tenant isolation;
- hosted SCM/ticket/telemetry integrations and operational workflow;
- GraphRAG, conversational interpretation, strategic recipes, executive reporting, or portfolio decisions;
- prediction or statistical calibration learned from customer outcomes.

**Dependency direction:** Platform imports/executes Engine contracts. Engine never imports Platform packages, calls Platform services, or requires Platform identities.

### 2.1 Community user experience

The expected Community journey is intentionally local and self-service:

```text
Install signed CLI/container
  -> codestrata init
  -> codestrata doctor
  -> codestrata assess --repo <path> --no-ai
  -> review local HTML + JSON + SARIF
  -> optionally query evidence through local read-only MCP
  -> optionally enable AI explanation and anonymous product telemetry
```

Community users receive:

- local CLI and container execution, plus stateless CI/GitHub Action usage;
- CodeStrata's bundled, prebuilt, signed YAML rule catalog;
- deterministic repository and change assessment without an account or AI provider;
- local HTML, JSON, and SARIF outputs with evidence lineage;
- documented configuration, parameters, suppressions, and exclusions;
- optional local/BYO AI explanation over completed evidence;
- optional anonymous product telemetry with transparent consent and a durable disable control;
- a narrow local read-only MCP interface for findings, metrics, components, dependencies, changes, and evidence.

Community is not a hosted multi-repository service and does not include customer-rule authoring, organization policies, portfolio continuity, GraphRAG, strategic recipes, governance, or managed enterprise integrations.

### 2.2 Supported execution modes

| Mode | Intended user | Source location | AI | Telemetry | Rule catalog |
|---|---|---|---|---|---|
| Community local | Developer/team | Remains on local machine | Off by default; optional local/BYO explanation | Available only with transparent consent; disable at any time | Bundled CodeStrata rules |
| Community CI | Repository team | CI runner | Off by default; optional explicitly configured provider | Available only when explicitly configured/consented | Bundled CodeStrata rules |
| Paid customer VPC | Regulated/enterprise customer | Remains inside customer-controlled network | Off, customer-hosted/BYO, or approved managed endpoint | Customer-admin controlled; local/exportable and external transmission optional | Bundled plus signed Platform-approved customer rules |
| Platform managed | Paid customer | According to contracted deployment/data policy | Managed and governed | Platform-administered under contract | Bundled plus governed customer rules |

### 2.3 Paid customer VPC execution

For paid customers, the Engine must be deployable as a headless, signed container/worker inside the customer's VPC or equivalent private environment. Source code, local repository graph, and raw evidence remain inside that boundary unless the customer explicitly configures export.

The VPC contract is:

```text
Platform/control plane or customer scheduler
  -> versioned job envelope + signed rule package
  -> Engine worker inside customer VPC
  -> local deterministic analysis
  -> signed/versioned assessment envelope
  -> customer-approved metadata/results export
```

This does not violate Engine independence. The worker accepts a platform-neutral job/rule-package contract and can run without Platform. Platform adds orchestration, identity, policy, persistence, governance, and user experience.

VPC requirements include no mandatory public internet access, allowlisted optional external feeds, configurable egress denial, customer-managed secrets, non-root container execution, resource limits, local artifact retention controls, audit logs, health checks, and documented upgrade/rollback behavior.

### 2.4 Telemetry contract

Telemetry is available in both Community and paid deployments, but it is not an analyzer read source and never affects findings, scores, or verdicts.

- **Community:** telemetry remains disabled until transparent consent is recorded. Users can inspect status, enable it, disable it permanently, or deny it for a run. Disabling must not reduce analysis capability.
- **Paid/managed:** product and operational telemetry is governed by the customer contract and tenant administration.
- **Paid VPC:** telemetry can remain local, export to a customer-controlled destination, or transmit an approved minimal event set to CodeStrata. External transmission must be separately configurable and fail closed when disabled.
- **Privacy:** never collect source code, snippets, secrets, file contents, raw findings/evidence, repository URLs/names, developer identities, customer-rule contents, or business identifiers through anonymous telemetry.
- **Permitted minimal data:** Engine/rule-pack version, installation pseudonymous ID where consented, command/event type, duration bucket, success/error category, analyzer applicability counts, coarse repository-size buckets, AI enabled/disabled, and provider category without prompts or responses.

Application logs, production metrics, and traces supplied for runtime analysis are customer data inputs, not CodeStrata product telemetry, and require separate Platform connectors and controls.

### 2.5 With-AI and without-AI modes

Both modes are first-class and supported:

- **Without AI:** the default reference path; all canonical facts, metrics, findings, deviations, scores, reports, and verdicts are complete and usable.
- **With AI:** adds clearly labelled explanation, summarization, navigation, and recommendation projections over completed evidence. Community uses local/BYO providers; paid deployments may also use governed Platform or customer-approved VPC endpoints.

For the same inputs, the canonical assessment envelope must be semantically identical in both modes. AI output is stored in a separate optional section/artifact and AI/provider failure cannot fail the assessment.

### 2.6 Sigstore-backed Engine, rule-pack, and result signatures

**Sigstore is mandatory for official CodeStrata distribution and is part of the core trust offering, not a later enterprise add-on.** Sigstore provides identity-bound signing, verification, and transparency records using Cosign, Fulcio, and Rekor; its bundles can carry the material needed for later verification.

CodeStrata must establish a verifiable software and analysis chain of custody:

- use Sigstore keyless CI signing with the release workflow's OIDC identity for official public releases;
- sign release files/Python distributions as blobs and publish their Sigstore bundles and checksums;
- sign OCI container images by immutable digest with Cosign, never by mutable tag alone;
- publish and sign an SBOM plus in-toto build provenance/attestation for each release;
- sign bundled CodeStrata rule packs and Platform-approved customer rule packages as immutable archives;
- verify rule-package schema, digest, issuer, signature, compatibility, and expiry/revocation policy before execution;
- record Engine artifact digest, Engine/analyzer/rule versions, rule-pack digest, configuration hash, input revisions, feed snapshot, and signature verification state in every assessment envelope;
- sign the final assessment envelope in official paid workflows so Platform and customers can verify that results were not changed after execution;
- publish exact verification commands and expected OIDC certificate identity/issuer in release and VPC documentation;
- make signature verification an automated release test and a paid/VPC admission check.

Public Community releases use Sigstore's public-good services and transparency log. Private customer rule packs and assessment results must not be submitted to a public transparency log without explicit approval; paid/VPC deployments support a customer-controlled/private Sigstore deployment, custom trust root, or approved offline/self-managed-key verification policy. Verification evidence must remain portable for restricted or air-gapped environments.

Community may modify the open source and run unsigned local builds, but reports must clearly identify them as unverified/custom builds. Paid and official CodeStrata workflows require trusted signatures according to deployment policy.

### 2.7 CodeStrata Verified Trust Chain

The customer-facing trust promise is a continuous chain, not a signing badge:

```text
Verified Engine release
  -> verified analyzer and rule-pack identity
  -> declared repository inputs and configuration
  -> deterministic execution
  -> complete evidence lineage or explicit UNKNOWN
  -> signed assessment envelope
  -> governed Platform interpretation and decision
```

The core trust offering combines Sigstore provenance, source-local/VPC execution, no-AI canonical assessment, AI-on/off equivalence, telemetry control, rule-package governance, reproducibility metadata, and evidence-backed outputs. A valid signature proves artifact identity and integrity; it does not prove analyzer correctness. The validation corpus and evidence contract prove analytical behavior.

## 3. Engine I/O contract

### Read sources

| Read source | MVP decision | Boundary |
|---|---|---|
| `source_tree` | **IN - core** | Files, symbols where reliable, configuration, CI, IaC, docs-as-evidence, tests, APIs, and repository topology. |
| `manifests_lockfiles` | **IN - core** | Maven, npm, Composer, NuGet/MSBuild already supported; normalize manifests and resolved lock data separately. |
| `git_history` | **IN - core, bounded** | Local commit/file history, churn, ownership concentration, hotspots, co-change, and bug-fix indicators. No organization identity claims. |
| `diff` | **IN - core** | Working tree, staged, commit range, or supplied patch/base/head. Assess only changed evidence plus deterministic impact. |
| `pr_context` | **IN - minimal** | Optional supplied title, description, base/head SHA, labels, and linked-reference strings. No hosted PR lifecycle. |
| `docs` | **IN - limited evidence** | README, ADRs, ownership/config files may support facts. No semantic RAG or model-written interpretation. |
| `external_feed` | **IN - narrow** | Pinned/cacheable vulnerability and license data only, with source/version/time recorded. Offline behavior must be explicit. |
| `tickets`, `telemetry`, `running_process`, `live_traffic` | **OUT** | Platform/later inputs. |

### Emits

| Emit | MVP decision | Required semantics |
|---|---|---|
| `finding` | **IN** | Rule ID/version, subject, severity, confidence, evidence, remediation, status. |
| `metric` | **IN** | Named value, unit, scope, derivation, coverage, and provenance. |
| `structure` | **IN** | Stable nodes/edges for repository, component, file, symbol, dependency, API, and CI/build relationships. |
| `label` | **IN** | Deterministic classifications such as source/test/config/generated/component/layer. |
| `deviation` | **IN - deterministic only** | Baseline-to-candidate movement or declared-pattern conformance with explicit thresholds and evidence. |
| `prediction` | **OUT** | Platform/later, after outcome data and calibration exist. |
| `attribution` | **OUT as a claim** | Git identities may be reported as repository facts; team/org/AI authorship attribution is not an MVP conclusion. |

Every result uses one normalized envelope: `run`, `analyzer`, `subject`, `observation`, `evidence`, `coverage`, `finding/metric/structure/label/deviation`, and reproducibility metadata. Engine version, analyzer version, rule-pack version, configuration hash, input revision(s), external-feed snapshot, and execution status are mandatory.

### Launch evidence and report refinement

Engineering Hotspots are first-class canonical records combining existing complexity/churn measurements, available structural centrality/reach, supported scoped ownership and active finding references. Each carries stable subject/state identity, the pinned history window, contributor coverage, evidence and a deterministic priority explanation. Preserve the Measurement Contract M22 complexity × churn ranking and stable component-ID tie-breaker; centrality/reach, ownership and finding references are display/context only, not hidden ranking weights. Missing required inputs yield UNKNOWN rank without erasing known evidence. This adds a record inside the existing result envelope, not an analyzer family or a new score.

M25 extends local concentration to supported repository/component/file scopes using attributable changed-line denominators and mapping evidence. M26 temporal co-change remains unchanged. M27/M29 explicitly report architecture-boundary spread and crossed-boundary count, affected components/tests and bounded static traversal with missing-data reasons and lower bounds. Crossed boundaries are not automatically violations or runtime impact.

### Report-facing capability coverage and freshness

The canonical envelope includes one record per declared capability, not only a family total: capability ID/version, scope, applicability/execution state, evaluated and eligible counts, unknown/error/excluded counts, coverage ratio or null with reason, evidence references and limitations. Keep coverage, freshness, confidence and signature trust separate. Unsupported, disabled, suppressed and unavailable scope remains visible. An unknown denominator is UNKNOWN, never 0% or 100%.

Freshness binds the pinned `evaluation_time`, source snapshot/digest, available source publication/update time, age and versioned freshness policy. Emit fresh/stale/UNKNOWN/NOT_APPLICABLE with a safe reason code and explanation. For vulnerability matching expose feed provider/version/digest, publication/update time, configured maximum age and missing/stale/unsupported-feed reasons; cached observed matches remain qualified, and insufficient feed freshness cannot prove a clean result. No silent network refresh. For Git-derived capabilities expose pinned head, requested window, observed time/commit bounds, included/excluded commit counts, shallow/truncation/merge/rename policy and history coverage reasons. Git recency describes the last included change; an old commit alone does not prove a stale checkout. If comparison to an upstream state is unavailable, say UNKNOWN rather than claiming the local head is current. Capabilities needing no time-sensitive source use NOT_APPLICABLE freshness with explanation. Missing source time yields UNKNOWN freshness, not the report generation time.

HTML must visibly present: (1) Engineering Hotspots with ranking/context labels, contributor values, priority explanations and linked findings/evidence; (2) repository/component/file ownership concentration with scope, denominator, pinned history and limitations; (3) temporal co-change with pair, support and union denominator; (4) change-summary/blast-radius counts, boundary spread/crossed-boundary pairs, affected components/tests and traversal limits; (5) per-capability coverage and freshness, including vulnerability feed and Git history with explicit UNKNOWN reasons; and (6) a Before / After / Delta table of compatible named metrics with units, scope, both coverages, outcome movement and linked qualifying/excluded drivers and cause/compatibility reasons. A first run visibly says no baseline and makes delta/movement unavailable; partial or incompatible comparisons retain qualified known observations without inventing zero, Stable or improvement. HTML projects the canonical Engine result, order, calculations and verdicts; it must never calculate its own scores, ranking, deltas or outcome movement. No new numeric score is added.

## 4. Native analyzer MVP specification

“Native” means CodeStrata owns the fact model, evaluation semantics, evidence shape, and quality contract. A parser library or narrowly integrated scanner may assist extraction, but opaque third-party output is never the authoritative domain model. This adopts MegaLinter’s descriptor/runner/reporting discipline without becoming a wrapper for a large tool collection.

### A. Repository & Technology Inventory

**Reads:** `source_tree`, manifests/lockfiles, limited docs, CI configuration  
**Emits:** `structure`, `label`, `metric`  
**Outcomes served:** all four; coverage and applicability foundation

MVP capabilities:

- language/framework/build/package-manager detection with evidence;
- source/test/config/infra/generated/vendor classification and exclusions;
- module/component boundaries using build files, directory conventions, namespaces, and explicit configuration;
- build and CI command discovery, including whether tests, coverage, lint, and security checks are actually invoked;
- API/configuration/deployment surface inventory where deterministically detectable;
- coverage map showing supported, partially supported, ignored, and unknown repository regions.

**Depth rule:** do not add a language merely for file counting. A launch-supported language must reach the minimum structural contract needed by the enabled analyzers. Current Java, JavaScript/TypeScript, Python, PHP, and C#/.NET support stays only to the verified depth recorded in the analyzer manifest.

### B. Architecture & Dependency Structure

**Reads:** `source_tree`, manifests/lockfiles, optional diff  
**Emits:** `structure`, `metric`, `finding`, `deviation`  
**Outcome:** Architecture, with Maintainability support

MVP capabilities:

- repository -> component/module -> file -> symbol graph where parser confidence permits;
- import/depends-on/implements/exposes-API/uses-dependency edges; call edges only where reliable;
- dependency cycles, invalid direction, declared layer-boundary violation;
- excessive cross-module coupling and component concentration;
- centrality and blast-radius reach at module/file level;
- diff impact: changed nodes, directly affected dependents, transitively affected components, and impacted tests;
- deterministic conformance against configured architecture patterns.

**Not MVP:** universal function-level call graphs, distributed-system topology, runtime service maps, inferred business domains, or cross-repository graphs.

### C. Security & Supply Chain

**Reads:** `source_tree`, manifests/lockfiles, narrow external feeds, optional git history/diff  
**Emits:** `finding`, `metric`, `label`, `deviation`  
**Outcome:** Security

MVP capabilities:

- high-confidence secret/private-key and credential-literal detection with safe redaction;
- insecure configuration patterns already modeled: disabled TLS/hostname verification, disabled authentication, permissive CORS, debug-enabled production configuration;
- dependency inventory with direct/transitive/resolved distinction where ecosystem data permits;
- known-vulnerability matching with feed identity/freshness and explicit `UNKNOWN` when unavailable;
- version hygiene: mutable, unresolved, unbounded, duplicate, and conflicting declarations;
- license identification/risk only where deterministic package metadata exists;
- diff verdict for introduced, resolved, worsened, or unchanged security findings.

**Not MVP:** broad taint-analysis claims, runtime exploitability, secrets-history scanning of every commit by default, malware detection, container/runtime posture, or proprietary threat correlation.

### D. Quality, Testing & Maintainability/Technical Debt

**Reads:** `source_tree`, CI/build configuration, git history, optional diff  
**Emits:** `metric`, `finding`, `label`, `deviation`  
**Outcomes:** Quality and Maintainability & Technical Debt

MVP capabilities:

- size, complexity, nesting, duplication/clone indicators, and maintainability markers where language support is verified;
- test inventory and source-to-test association with confidence;
- disabled/skipped tests, declared tests not observed by build/CI configuration, and coverage configured but not invoked;
- churn-weighted complexity hotspots;
- repository/component/file ownership concentration where local evidence supports it; no organizational bus-factor or productivity claim;
- aging/stale dependency and high-risk component prioritization where evidence is available;
- change-quality metrics: change size, surface spread, test-touch evidence, and risk amplification when high-churn/high-centrality code changes.

**Not MVP:** subjective code-style breadth, auto-fixing/formatting, developer productivity scoring, performance claims without runtime evidence, or strategic modernization roadmaps.

### E. Git & Change Intelligence

**Reads:** `git_history`, `diff`, minimal `pr_context`, plus facts/graph from A-D  
**Emits:** `metric`, `structure`, `finding`, `label`, `deviation`  
**Outcomes:** all four; primary differentiator

MVP capabilities:

- one-pass bounded history index: commits -> files -> components;
- churn, recency, repository/component/file ownership concentration, hotspots, and temporal co-change;
- rename-aware file identity where Git data supports it;
- working-tree, staged, commit-range, and supplied base/head comparison;
- finding lifecycle: `new`, `resolved`, `improved`, `worsened`, `unchanged`, `unknown`;
- graph delta and deterministic blast radius;
- change verdict derived from named rules and evidence, never model prose;
- minimal PR metadata attached as context, never trusted as proof.

**Not MVP:** AI-authorship detection, human intent inference, defect prediction, organizational performance attribution, hosted PR comments/check lifecycle, ticket correlation, or long-term standing state.

### F. Cross-cutting database-layer analysis — deferred past MVP

**Status:** Deferred. Documented here as a specified post-launch enrichment, not built or validated for MVP launch. Security & Supply Chain's primary reads already cover configuration and secret risk without this capability; deferring it protects validation cycles for the flagship depth-tier surfaces in Section 1 rather than spreading tuning effort across a sixth partially-built capability.

**Reads:** `source_tree`, manifests/lockfiles, configuration, migrations, optional diff/history  
**Emits:** `structure`, `label`, `metric`, `finding`, `deviation`  
**Outcomes served (post-MVP):** Architecture, Security, Quality, Maintainability & Technical Debt

This is a supporting capability used by the five analyzer families, not a sixth headline assessment head.

The Engine may determine from repository evidence, once built:

- database technologies, drivers, ORMs, data-access libraries, repositories, DAOs, entities, and query builders;
- migration-defined tables, columns, relationships, indexes, constraints, and schema changes;
- embedded SQL and stored-procedure references where statically resolvable;
- component -> repository/DAO -> entity/query -> declared table relationships;
- direct database access that bypasses declared architectural boundaries;
- code shapes suggesting N+1 access, queries inside loops, missing batching/pagination, or absent timeout/transaction configuration;
- database configuration and secret risks;
- data-access coupling, ownership concentration, change history, and blast radius.

The Engine must label this **Code-defined Database Architecture** or **Potential Static Database Risk**. Without database/runtime access it cannot claim actual production schema alignment, data distribution, query plans, latency, lock contention, index utilization, connection-pool health, runtime permissions, or executed-query behavior. Those require Platform/later connectors and must be labelled **Runtime-observed Database Behavior**.

### G. Cross-cutting static observability posture — deferred past MVP

**Status:** Deferred. Documented here as a specified post-launch enrichment, not built or validated for MVP launch, for the same reason as database-layer analysis above.

**Reads:** `source_tree`, manifests/lockfiles, configuration, CI/deployment definitions, optional diff/history  
**Emits:** `structure`, `label`, `metric`, `finding`, `deviation`  
**Outcomes served (post-MVP):** Architecture, Security, Quality, Maintainability & Technical Debt

The Engine may determine, once built:

- logging frameworks and structured/unstructured logging patterns;
- metrics libraries, exporters, OpenTelemetry instrumentation, and health/readiness endpoints;
- trace/correlation-ID propagation where statically resolvable;
- instrumentation coverage across detected components and entry points;
- exception handling that suppresses errors and missing signals around critical boundaries;
- monitoring/alert configuration stored in the repository;
- sensitive-data logging risks and observability dependencies that appear unused;
- whether repository-defined CI/deployment configuration exposes relevant endpoints or exporters.

The Engine must call this **Static Observability Posture**, never production observability health. Without logs, metrics, traces, alerts, or live traffic it cannot prove signal delivery, trace continuity, SLO attainment, alert effectiveness, dashboard usefulness, cardinality/cost health, incident detectability, or service health. Runtime conclusions belong to Platform/later after explicit telemetry integration.

For both database and observability analysis, once built, every output must carry an evidence mode:

| Evidence mode | Meaning |
|---|---|
| `declared` | Present in configuration, manifest, migration, schema, or policy. |
| `detected_static` | Established from code structure or deterministic pattern analysis. |
| `inferred_ai` | Optional AI interpretation over cited evidence; never canonical. |
| `observed_runtime` | Requires a Platform/later runtime connector; unavailable to source-only Engine scans. |

## 5. YAML rule DSL and analyzer contract

### Separation of responsibilities

- **Native extractors/analyzers** turn repository inputs into versioned facts, graph structures, and base metrics.
- **YAML rules** select and evaluate those facts using bounded operators, then emit normalized outcomes.
- **Community distribution** includes only CodeStrata-authored, bundled YAML rule packs. Community users may configure supported parameters and suppressions, but custom-rule authoring/loading is not a supported Community product surface.
- **Platform LLM chat** translates natural language into candidate YAML, explains it, validates it against the Engine schema/capabilities, runs it in a sandboxed preview, and requests human approval.
- **Platform rule management** versions, stores, governs, packages, and delivers approved customer rules to the Engine.
- **Engine runtime** verifies signed Effective RuleSets, validates their contracts, compiles, plans, executes, and records results deterministically.
- **RuleSet resolution** uses Engine-owned contracts; Platform resolves customer composition, while CodeStrata release tooling pre-resolves Community RuleSets.

No rule-specific code is generated. YAML is data, not a scripting escape hatch.

### Locked rule-system hierarchy

```text
Analyzer -> Facts/Graph/Metrics -> Rule -> RuleSet -> Policy -> Resolved Effective RuleSet -> Signed Package -> Engine compile/execute
```

**Rule** is immutable evaluation logic, with a declared parameter schema, default severity and evidence contract. **RuleSet** is versioned composition, adoption defaults and named reusable selectors. **Policy** is customer governance: approved typed overrides, exceptions, approval and workspace assignment. An **Effective RuleSet** is the immutable, fully resolved execution configuration. The signed policy package is its distribution container; it is not another rule language.

Engine owns the Rule/RuleSet/Effective RuleSet schemas, bounded operators and deterministic resolution semantics. Platform uses those contracts to resolve organization/customer composition and distribute signed immutable results. Engine verifies, validates, compiles and executes the supplied Effective RuleSet without querying Platform. Community receives prebuilt/pre-resolved signed CodeStrata RuleSets. Documented local parameters, exclusions and suppressions remain supported; their final values are pinned in the run configuration hash alongside the signed base digest, and are not represented as a newly CodeStrata-signed customer RuleSet.

Engine uses memory, bounded file indexes and versioned JSON/JSONL artifacts; no SQLite, PostgreSQL or other database dependency is introduced. The resolver is a contract/library capability, not a service or Engine governance store.

### Required rule shape

```yaml
api_version: codestrata.io/rules/v1
kind: Rule
metadata:
  id: acme.architecture.no-internal-module-import
  version: 1.0.0
  title: Public API modules must not import internal implementation modules
  category: architecture
  owner: acme

applies_to:
  languages: [java]
  requires:
    facts: [module.declaration, graph.imports]

select:
  source: repository_graph
  nodes:
    all:
      - type: module
      - path_pattern: "**/api/**"

condition:
  exists_path:
    edge_types: [imports]
    to: {fact: module.path_pattern, value: "**/internal/**"}
    traversal: direct
    max_depth: 1

emit:
  finding:
    default_severity: high
    message:
      template: "{{dependency_path}} crosses a declared API/internal boundary"
      bindings:
        dependency_path: {type: string, evidence: dependency_path}
    documentation_url: https://docs.codestrata.ai/rules/architecture/no-internal-module-import
  metric:
    name: api_internal_import_violation_count
    operation: count

evidence:
  include: [source_location, dependency_path]
```

This rule reads only facts the Architecture & Dependency Structure family produces at launch (module declarations and import edges) rather than the now-deferred database-layer analysis, so the example a buyer sees running is one the MVP can actually execute end to end.

It ships with three fixtures so it demonstrates the trust promise alongside the mechanism:

- **Compliant fixture:** an `api` module that only imports other `api`/public modules - the rule finds no violation, and the report shows a clean pass with the checked evidence path.
- **Violating fixture:** an `api` module that directly imports an `internal` module - the rule fires with the finding, severity, and dependency-path evidence shown above.
- **Incomplete-evidence fixture:** a repository with an import the graph cannot statically resolve (a dynamic or reflective import, or a module path outside declared source roots) - the rule reports `UNKNOWN` for that edge rather than a silent pass, and coverage/confidence disclose exactly what could and couldn't be evaluated.

### RuleSet composition and reusable selectors

The examples define the bounded v1 contract shape; illustrative digest tokens must be replaced with real content digests before validation/signing. Documentation URLs are stable publication targets to supply with the catalog, not assertions that a page is already deployed.

```yaml
api_version: codestrata.io/ruleset/v1
kind: RuleSet
metadata:
  id: acme.engineering-standard
  version: 1.0.0
extends:
  - id: codestrata.engineering-health
    version: 1.0.0
    digest: "sha256:<pinned-parent-digest>"
selectors:
  acme.production_modules:
    source: repository_graph
    nodes:
      all:
        - type: module
        - generated: false
        - test: false
rules:
  acme.architecture.no-internal-module-import:
    revision: 1.0.0
    digest: "sha256:<pinned-rule-digest>"
    default_enabled: true
    adoption: recommended
```

A Rule that uses a reusable selector pins its AST definition. This is an alternative Rule revision's selection fragment, not an override of the preceding Rule:

```yaml
select:
  selector_ref: acme.production_modules
  selector_digest: "sha256:<pinned-selector-ast-digest>"
```

Policy configuration and the resulting finding projection remain distinct:

```yaml
# Approved policy configuration fragment; the Rule revision is unchanged.
rules:
  acme.architecture.no-internal-module-import:
    enabled: true
    severity_override: critical
---
# Finding projection after a violation, under that resolved policy.
rule_id: acme.architecture.no-internal-module-import
default_severity: high
effective_severity: critical
override_source: acme.engineering-policy@3
```

For an optional member, set `default_enabled: false` and `adoption: optional` on its RuleSet entry. Merely defining a reusable selector neither changes an existing Rule nor enables it.

### Typed overrides and immutable logic

| Change | Required treatment |
| --- | --- |
| Severity | Typed severity validation; no rule-logic revalidation; preserve rule revision and record override provenance |
| Enable/disable | Boolean validation; no rule-logic revalidation; expose disabled/exempt scope and changed coverage |
| Approved parameters/thresholds | Only fields exposed by the pinned Rule's typed schema, within declared bounds; schema validation and preview of the effective configuration |
| Safe metadata/message/remediation | Validate allowlisted presentation fields, typed placeholders and stable documentation URLs; no rule-logic revalidation |
| Selector/condition/operator semantics | New immutable Rule revision and full schema, capability, compliant/violating/UNKNOWN fixture validation and preview |

All customer changes require human approval, policy versioning, resolution and signed distribution. Validation reuse is bound to the exact rule digest, DSL/Engine compatibility and applicable configuration; it is not permission to skip the checks required for a new override. Typed parameter values may vary the rule's declared threshold behavior without a new revision; changing the parameter schema, selected evidence, predicate structure, traversal semantics or operator meaning is a logic change. Rebinding or editing a selector used by a Rule is a logic change, not a lightweight override.

### Deterministic resolution and precedence

1. Pin every RuleSet parent, Rule revision and selector reference by immutable version and content digest. No floating versions, mutable URLs or runtime fetching. Reject missing references, cycles, incompatible schemas/capabilities, unknown fields and excessive composition depth/size.
2. Resolve parent RuleSets before children. In an explicit ordered `extends` list, later parents take precedence over earlier parents for supported configuration fields; child entries take precedence over parents. Changing that order changes the digest. Merge rule maps by stable rule ID and typed parameter maps by declared field; scalar/list values replace atomically, with no implicit deletion or null-as-reset. Omitted fields inherit.
3. For each included Rule, use its intrinsic default severity/parameter values, then inherited RuleSet defaults, then child RuleSet defaults, then the approved policy override, then an approved matching scoped exception. `default_enabled` is mandatory after RuleSet resolution; an explicit policy `enabled` takes precedence. `adoption: recommended|optional` is a RuleSet UI/documentation label, never an immutable Rule property or an independent activation switch.
4. Parent disagreement on a Rule revision requires an explicit child pin and validation of that chosen revision; configuration precedence cannot replace logic silently. Selector IDs are namespaced and pinned: identical definitions may deduplicate, conflicting definitions cannot shadow one another. A consumer that changes a referenced selector must create a new Rule revision.
5. Across separately assigned workspace policies, identical revisions and effective settings execute once with all policy attributions. Conflicting revisions/settings are rejected before dispatch; assignment time, database row order and policy name never decide precedence. Matching exceptions may combine disjoint fields or identical values; conflicting values on overlapping scope are rejected, without an implicit most-specific-wins rule. Governance cannot use an exception to hide a cross-policy conflict.
6. Materialize all defaults, enabled states, typed values, safe presentation metadata, pinned selector ASTs and any bounded scoped exception configuration. Include policy/version attribution, override sources and exception references. No unresolved inheritance or mutable approval lookup reaches Engine.
7. Canonically serialize the Effective RuleSet using a versioned serialization profile and hash it. Bind Rule/RuleSet/selector digests, ordered composition, fully resolved settings/scopes, resolver and DSL/capability versions, and the approved policy/exception references into `effective_ruleset_digest`. The signed package manifest binds that digest, payload digests, execution purpose, compatibility and validity. Assessment reproducibility metadata records it plus package digest, resolver version, rule digests, run configuration hash and verification state. Identical pinned resolution inputs yield identical resolved bytes/digest; signatures and operational timestamps remain separate.

### Selector, traversal and finding presentation decisions

Selectors are a custom **structured YAML query AST**, inspired by established filtering, set and graph-query concepts. JSONPath addresses document paths rather than CodeStrata's typed evidence graph; embedded Cypher/SQL or general-purpose query strings would expand the runtime and sandbox surface. The structured AST supports static validation, safe LLM drafting, reviewable diffs, versioning, signing and bounded deterministic evaluation. Customer executable functions, custom JS/Python, dynamic imports and generic executable template languages remain prohibited; trusted Engine-native operators remain implementation code.

Dependency resolution and graph traversal are separate dimensions: `dependency_view: declared|resolved` selects manifest declarations or resolved dependency facts; `traversal: direct|transitive` selects one edge or a bounded path. `direct` has depth 1; `transitive` requires a positive bounded `max_depth`. Unsupported/unresolved facts or a bound that prevents a conclusive answer produce explicit coverage/UNKNOWN, never a false pass. Do not introduce Spectral's single `resolved: true|false` boolean.

Rules declare `default_severity`; effective configuration may override it without changing evaluation logic. Findings expose `default_severity`, `effective_severity` and `override_source` when applicable; the existing severity projection means effective severity. `enabled` is a separate boolean, and `off` is never a severity. Use the existing severity vocabulary. Safe messages permit only typed bindings to known facts/evidence, with escaped rendering and no expressions, loops or calls. Preserve stable `documentation_url` links. Fingerprints use stable rule/subject/evidence identity under the existing matching contract and never rendered message text.

These independent fragments illustrate traversal choices; changing between them changes Rule logic and requires a new revision:

```yaml
condition:
  exists_path:
    edge_types: [imports]
    traversal: direct
    max_depth: 1
---
condition:
  exists_path:
    edge_types: [depends_on]
    dependency_view: resolved
    traversal: transitive
    max_depth: 4
```

`dependency_view` applies only to operators/facts supporting that distinction. Choosing resolved lockfile evidence does not imply transitive traversal; declared evidence may also be traversed when its graph contract supports it. Missing template bindings cannot be fabricated: use the schema-defined missing-value representation and disclose the evidence limitation. Message rendering cannot alter evaluation status or finding identity.

### Governed exceptions and launch scope

Platform owns first-class governed policy/rule exceptions: bounded organization/workspace/repository/subject scope, targeted policy/rule revisions, typed action, reason, accountable owner, expiry, authorized approval and an audit trail. An exception may apply a supported override, including disabling evaluation for a declared scope; it cannot introduce executable logic, select new evidence through arbitrary queries, or convert missing evidence into PASS. Engine receives only the resolved scoped override and opaque immutable exception reference, plus package validity needed for admission; reason, owner and approval workflow stay in Platform.

Creation, amendment, renewal and withdrawal produce attributable versions/events. Platform checks eligibility at resolution, dispatch and existing authorization checkpoints; package validity cannot extend beyond the earliest included exception expiry. Expiry/revocation stops new use, triggers re-resolution/distribution under approved policy, and never edits old results or silently modifies a pinned retry. An incompatible or expired job fails visibly and needs a new manifest. Offline verification uses the existing bounded validity/trust policy; it cannot promise instant revocation awareness. Reports distinguish exempt/disabled scope and coverage from compliance. A finding disposition remains an annotation and does not itself authorize an executable exception.

This foundation does not add an analyzer family, public outcome, microservice, Engine database, customer function API or general query runtime. Compliant, violating and incomplete/UNKNOWN fixtures remain required. Add resolution fixtures for inheritance, conflicts, invalid typed overrides, selector rebinding, exception scope/expiry, stable digests and message-independent identity. Community telemetry remains disabled until explicit opt-in and never affects analysis.

### Bounded v1 operators

- selection/filtering: `all`, `any`, `not`, `equals`, `in`, `matches`, `exists`;
- numeric/set: `count`, `sum`, `min`, `max`, `ratio`, `distinct`, `percentile`;
- graph: `neighbors`, `degree`, `exists_path`, `reachable`, `cycle`, `crosses_boundary`;
- change: `changed`, `introduced`, `removed`, `increased_by`, `decreased_by`, `compare`;
- threshold/composition: `threshold`, `and`, `or`, named metric reference.

Disallowed: loops, recursion, network/file access, arbitrary expressions, embedded templates with execution semantics, external commands, imports, reflection, or user-defined functions.

### AnalyzerDescriptor minimum contract

Every native analyzer declares: stable ID/version; `reads`; `emits`; applicability; required fact schemas; supported language/depth; evidence requirements; deterministic class; timeout/memory/file budgets; network policy; configuration schema; coverage contract; failure modes; and fixture set.

Rules may only reference registered, versioned facts and operators. Missing facts yield `UNKNOWN`/`NOT_APPLICABLE`, never `PASS`. Rule compilation is separate from execution and produces a serializable execution plan. Engine accepts an approved rule package through a platform-neutral input contract without importing, calling, authenticating with, or otherwise knowing about Platform.

Because the Engine is open source, developers can technically modify or invoke its internals. The enforceable product boundary is support and distribution: Community ships, documents, and supports bundled CodeStrata rule packs; Platform sells the managed customer-rule lifecycle.

## 6. AI responsibility model

CodeStrata is an AI-native engineering intelligence company, but AI does not replace the Engine's truth function.

> **The Engine establishes what is true. AI helps people understand, customize, and act on that truth.**

This is a product advantage. As AI writes more software, customers need an independent system that verifies what changed and explains why it matters without asking another model to judge its own work.

### 6.1 Trusted execution boundary

The canonical assessment path is always:

```text
Repository inputs
      -> native deterministic analyzers
      -> versioned facts, graph and metrics
      -> verified immutable Effective RuleSet from signed package
      -> bounded YAML compiler and execution plan
      -> deterministic rule execution
      -> findings, evidence, deviation and verdict
```

AI must not:

- create or alter canonical facts during an assessment;
- decide whether a deterministic rule passed or failed;
- change severity, confidence, metrics, deviation, or release verdicts;
- fill missing evidence or convert `UNKNOWN` into `PASS`;
- execute generated code, arbitrary commands, or unapproved rules;
- make AI-authorship, intent, performance, or defect-prediction claims without appropriate evidence and calibration.

### 6.2 AI in Community Engine

Community's core assessment works fully offline and without AI. A narrow optional AI experience may be provided for local/BYO models, but it remains a projection over completed Engine evidence.

Allowed optional capabilities:

- explain a finding, metric, dependency path, or change verdict in plain language;
- summarize repository structure or blast radius from cited Engine evidence;
- suggest remediation alternatives tied to specific findings;
- provide evidence-grounded onboarding for an unfamiliar repository;
- answer read-only questions through the narrow local MCP evidence interface.

Every output must be labelled `AI-generated`, cite the evidence IDs it used, disclose the provider/model when available, and remain outside canonical fields used for scoring or gating. AI failure must never fail or change an assessment.

Community does **not** receive customer-rule authoring. It runs the bundled CodeStrata YAML catalog and may adjust documented parameters and suppressions.

### 6.3 AI in Platform

Platform is the primary commercial AI surface:

- natural-language customer policy -> candidate bounded YAML rule;
- rule explanation, validation, simulation, correction, approval, versioning, and governance;
- conversational investigation across findings, components, repositories, releases, and policies;
- evidence-grounded engineering and executive summaries;
- correlation across Engine evidence and, later, tickets, telemetry, ownership, and business context;
- prioritization against organizational objectives and constraints;
- modernization options, decision support, and governed action plans;
- GraphRAG and retrieval across accumulated portfolio engineering memory;
- later, remediation proposals or code changes behind explicit human review and approval.

Platform AI uses a four-level claim contract:

| Claim class | Meaning | Required treatment |
|---|---|---|
| **Observed** | Directly present in Engine or connected-source evidence | Cite immutable evidence and source. |
| **Derived** | Deterministically calculated from observed evidence | Cite inputs and derivation/rule version. |
| **Inferred** | Model interpretation of observed/derived evidence | Label as inference, cite grounding, expose uncertainty. |
| **Recommended** | Proposed action involving judgment or trade-offs | Label as recommendation; consequential action requires an accountable human. |

AI may author customer rules, but only the deterministic Engine evaluates them. Platform must refuse or escalate a requested policy when the Engine lacks the required facts or bounded operators.

### 6.4 AI in product development and validation

AI should substantially amplify how CodeStrata builds the Engine without entering the trusted runtime:

- propose analyzer primitives and candidate YAML rules;
- migrate existing Python rule definitions to YAML;
- generate good/bad fixtures, mutations, edge cases, and adversarial tests;
- identify coverage gaps and investigate false positives/negatives;
- review analyzer code, schemas, evidence lineage, and performance changes;
- turn vulnerability/framework research into candidate rules;
- produce documentation, examples, migration guidance, and benchmark analysis.

AI-generated artifacts enter a release only after human review and the same deterministic tests, benchmarks, security controls, and release gates as human-authored work.

### 6.5 AI as an operating partner

CodeStrata should operate as an AI-native company. AI can support product research, customer-discovery synthesis, account preparation, marketing, support triage, engineering, testing, internal knowledge, security review, and assessment drafting. Humans remain accountable for customer commitments, pricing, security decisions, production releases, and conclusions represented as verified facts.

### 6.6 AI product position

CodeStrata should not position itself as “AI that scans code.” The stronger position is:

> **CodeStrata is an AI-native engineering intelligence company built on a deterministic evidence Engine. AI turns verified software evidence into policies, explanations, priorities, and decisions.**

The Engine makes CodeStrata's AI credible. Platform makes Engine evidence contextual, conversational, organizational, and commercially valuable.

## 7. Reconciliation with the current public Engine

Assessment is against public repository commit `ca18a660f164f8c2bd9983a81faf1f82094a1abc` inspected on 2026-09-09. The repository already has a substantial Python package, repository/assessment graphs, a shared rule platform, eight assessment heads, incremental-analysis scaffolding, reports, telemetry contracts, optional AI providers, local knowledge/MCP/agent features, and portfolio artifact concepts. Most current rules are implemented as Python classes/functions with typed metadata and settings; they are **not yet the agreed YAML-authored rule system**.

| Current capability | Decision | Required change before/after MVP |
|---|---|---|
| CLI, config validation, local repository assessment | **KEEP** | Preserve as the primary Community entry point; make offline deterministic mode the reference path. |
| Inventory, build, dependency, CI discovery | **STRENGTHEN** | Normalize facts, add explicit coverage/applicability, deepen supported ecosystems instead of adding breadth. |
| Repository and assessment graphs | **STRENGTHEN** | Stabilize node/edge schemas, identity, evidence lineage, centrality, impact, and graph delta. |
| Shared rule registry/planner/executor, suppression, confidence, traceability | **STRENGTHEN** | Make it the single runtime; add YAML schema/compiler and migrate launch rules off bespoke Python evaluation. |
| Architecture rules | **STRENGTHEN** | Keep cycles/direction/boundaries/coupling/concentration; remove enterprise-standard semantics from Community core unless expressed by local config/YAML. |
| Dependency rules and ecosystem parsers | **STRENGTHEN** | Preserve current version-hygiene rules; deepen lockfile resolution, vulnerability provenance, transitive evidence, and diff lifecycle. |
| Security rules | **STRENGTHEN** | Keep the high-confidence current patterns; improve redaction, fixtures, confidence, language coverage, and change status. |
| Technical-debt and testing heads | **STRENGTHEN** | Merge public story into Quality/Maintainability; add churn weighting and stronger test/CI evidence. |
| `git_revision` SHA/dirty-state support | **BUILD** | Add bounded history index, churn, ownership concentration, co-change, hotspots, renames, and per-range changes. |
| Completed-scan comparison/incremental scaffolding | **STRENGTHEN** | Add first-class working/staged/range diff input, normalized delta, and deterministic deviation. |
| AnalyzerDescriptor + normalized multi-emit envelope | **BUILD** | Turn Vinay's READS x EMITS taxonomy into the executable analyzer contract. |
| Declarative YAML rule schema/compiler | **BUILD** | Required launch foundation; bundled and Platform-delivered rules use the same execution path. Community supports bundled CodeStrata packs only. |
| Cloud Readiness head | **DEFER** | Retain code as an experimental pack if stable; remove from the four headline outcomes and release gate. |
| AI Readiness head | **DEFER** | Retain as experimental; do not confuse repository AI-technology inventory with AI-change risk or authorship. |
| Static Performance head | **DEFER** | Retain as experimental indicators; do not make performance conclusions without runtime evidence. |
| Optional AI narrative and provider stack | **KEEP NARROW / MOVE UP** | Keep optional local/BYO evidence explanation in Community. Move strategic reasoning, managed providers, GraphRAG, and organization-aware AI to Platform. AI must never affect facts/findings/verdicts. |
| Modernization Advisor and multi-agent workflows | **MOVE TO PLATFORM** | Strategic interpretation/recipes are commercial decision IP. |
| Local read-only MCP over Engine evidence | **KEEP, NARROW** | Expose repository/snapshot/component/finding/evidence/metric/dependency/change/lineage queries only. |
| Local knowledge store | **KEEP, NARROW** | Memory and bounded versioned JSON/JSONL file indexes for one repository and supplied comparisons; migrate SQLite out of the runtime. No database, GraphRAG or organizational memory. |
| Portfolio identity, `intelligence/<portfolio-id>`, EIR lifecycle/promotion | **MOVE TO PLATFORM** | Engine emits an assessment envelope/snapshot; it must not know `portfolio_id` or EIR lifecycle. |
| Community Cloud publishing and hosted report lifecycle | **MOVE TO PLATFORM** | Local artifact generation stays; hosted tenancy/publishing belongs outside Engine. |
| Telemetry consent/privacy contracts | **KEEP only if isolated** | Telemetry remains optional, disabled by default, fail-silent, and irrelevant to analysis. Aggregation/analytics is Platform. |
| Local, CI, and headless container execution | **STRENGTHEN** | Make Community self-service and make the same Engine deployable as a signed paid VPC worker through platform-neutral envelopes. |
| With-AI / without-AI assessment modes | **STRENGTHEN** | Make no-AI the reference path; isolate optional AI projections and verify canonical-output equivalence. |
| Sigstore release, rule-pack, and assessment signing | **BUILD** | Add keyless signing for official public artifacts, Cosign image/blob verification, signed SBOM/provenance, private/offline VPC trust policy, rule-package verification, and paid result signatures. |
| Extension entry points/allowlists | **DEFER as product surface** | Preserve compatibility, but do not let extension breadth displace native analyzers or permit unsafe customer rule execution. |
| HTML, JSON, SARIF/report outputs | **KEEP/STRENGTHEN** | One normalized result model; every output is a projection, not a separate truth. |
| Packaging, CI, tests, coverage, releases | **STRENGTHEN** | External installation and reproducibility are hard release gates. |

Migration principle: do not delete working code merely because it is outside the headline scope. Isolate it, mark it experimental, or move it behind a stable contract. Do not allow compatibility work to delay the five native analyzer families.

## 8. Engine vs Platform vs deferred

| Capability | Engine MVP | Platform MVP/later | Deferred |
|---|---:|---:|---:|
| One-repository facts, graph, findings, metrics, evidence | Yes | Consumes | - |
| Local baseline/candidate comparison and deterministic deviation | Yes | Persists/visualizes | - |
| Git churn, hotspots, co-change, repository/component/file ownership concentration | Yes | Aggregates through time/org | - |
| Minimal supplied PR context | Yes | Hosted SCM app/checks/comments | - |
| YAML schema/compiler/runtime | Executes bundled and approved rule packages | Authors/governs/distributes customer rules | - |
| Customer rule creation by LLM chat | No Community authoring surface | Yes | - |
| Evidence-grounded AI explanation | Optional local/BYO, non-authoritative | Managed and organization-aware | - |
| AI summaries and recommendations | Local evidence only; clearly labelled | Cross-repository, historical, and strategic | - |
| AI modification of findings/scores/verdicts | Never | Never | - |
| Engineering Health example recipe | Optional open example | Managed/strategic recipes | - |
| Portfolio/system graph and cross-repo correlation | - | Yes | - |
| Long-term drift/standing state across releases | Emits comparable snapshots | Yes | - |
| Organizational attribution and team policy | - | Yes | - |
| GraphRAG, semantic retrieval, strategic conversation | - | Yes | - |
| Enterprise governance, RBAC, audit, SSO, VPC controls | - | Yes | - |
| Headless Engine execution inside customer VPC | Signed Engine worker and neutral contracts | Orchestration, policy, identity, persistence, support | - |
| Product telemetry | Optional, consented, disable at any time | Contract/admin governed; VPC destination configurable | - |
| Without-AI canonical assessment | Complete reference behavior | Complete reference behavior | - |
| With-AI evidence explanation | Optional local/BYO projection | Governed managed or customer-approved endpoint | - |
| Sigstore releases/rule packs/result provenance | Mandatory for official distribution | Enforces trusted packages and chain of custody; supports private/offline VPC trust | - |
| Ticket and telemetry correlation | - | Later | Yes for launch |
| Runtime/live-traffic analysis | - | Later product | Yes for launch |
| Prediction/statistical calibration | - | After labeled outcomes | Yes for launch |
| AI-authorship detection | - | Only with explicit provenance and careful claims | Yes for launch |
| Universal precise call graph | Partial where reliable | Consumes | Yes beyond selected-stack follow-up |

## 9. Launch operating model

Work starts in parallel across workstreams, merges behind stable contracts, and ships only when every release gate passes — this document defines correct MVP boundaries and readiness criteria, not a delivery schedule. If a stream is under pressure for any reason, cut analyzer breadth or experimental surfaces before weakening determinism, evidence, installation, or the Engine/Platform boundary. Scope protection does not depend on how long any stream takes.

### Parallel workstreams

| Stream | Deliverable | Can start when | Does not wait for |
|---|---|---|---|
| A. Contract & YAML runtime | AnalyzerDescriptor, fact/output schemas, YAML validator/compiler/planner, operator v1 | Immediately | New Git analyzers |
| B. Existing analyzer migration | Inventory, Architecture, Security, Dependencies, Quality/Testing launch rules on the shared contract | Draft contracts stable | Platform or UI |
| C. Git & diff intelligence | History index, churn/ownership/co-change/hotspots, live diff, graph delta, deviation | Identity/output contracts drafted | Full YAML migration |
| D. Boundary extraction | Remove/isolate portfolio/EIR, hosted publishing, strategic agents, AI narrative dependencies | Immediately | Analyzer feature work |
| E. Trust & validation | Good/bad fixtures, public validation corpus, determinism/coverage/performance checks | Immediately | All analyzers complete |
| F. Distribution & experience | Clean install, signed package/container, CLI, HTML/JSON/SARIF, narrow MCP, VPC worker profile, telemetry controls, docs | Immediately | Platform |
| G. Platform integration contract | Versioned assessment-envelope ingest and rule-package handoff tests | Engine envelope drafted | Platform feature completeness |

Suggested ownership is by stream, not by phase. Contract changes require one designated schema owner; analyzer teams build against released schema versions. Integration happens continuously through fixtures and envelope compatibility tests.

### Release gates

The Engine MVP is launch-ready only when every gate passes:

1. **Boundary gate:** dependency audit proves no Engine import/runtime dependency on Platform; no portfolio/tenant/EIR identity in the canonical Engine envelope.
2. **Determinism gate:** same repository revision + config + rule pack + feed snapshot produces semantically identical output; ordering and IDs are stable.
3. **Rule-runtime gate:** every launch rule is YAML-defined and passes schema validation, compilation, budget enforcement, evidence validation, and good/bad fixtures; no AI/code generation occurs at runtime.
4. **Analyzer-depth gate:** each of the five families satisfies its declared coverage contract on the public validation corpus. Unsupported analysis reports `UNKNOWN`/`NOT_APPLICABLE`.
5. **Change gate:** working/staged/range diff produces correct finding lifecycle, graph delta, blast radius, and deterministic deviation on controlled fixtures.
6. **Evidence gate:** every finding and verdict traces to concrete evidence and derivation; secrets are redacted; confidence and coverage are visible.
7. **External-use gate:** a clean machine can install the published artifact, assess an external repository, and open useful HTML/JSON/SARIF without monorepo paths or private services.
8. **Quality gate:** lint, strict type checks, full tests, configured coverage threshold, schema compatibility tests, and security checks run on every change and release.
9. **Performance gate:** declared repository-size fixtures complete within published budgets; timeouts degrade explicitly without corrupting the run.
10. **Platform-contract gate:** Platform can ingest the versioned assessment envelope and deliver an approved, versioned customer rule package back to an unmodified Engine runtime; the Community CLI exposes only bundled CodeStrata rule packs as its supported catalog.
11. **Execution-mode gate:** Community local, Community CI, paid VPC worker, with-AI, and without-AI paths conform to the same canonical Engine contracts.
12. **AI-equivalence gate:** canonical assessment output is semantically identical with AI disabled or enabled; only the separate AI projection may differ.
13. **Telemetry/privacy gate:** Community consent/disable behavior, paid/VPC administration, fail-closed egress, and prohibited-data tests pass without changing analysis capability.
14. **Sigstore supply-chain gate:** official release blobs and OCI images verify against the expected OIDC issuer and workflow identity; SBOM/in-toto attestations and rule-pack bundles verify; VPC private/offline verification passes; reports identify the exact verified or custom build that produced them.

### Validation corpus

The release gates above reference "the public validation corpus" without defining it. That corpus has three tiers, each proving something different — collapsing them into one headline number would let a passing count stand in for questions it doesn't actually answer.

1. **Dogfood tier — CodeStrata's own repositories.** The Engine and Platform run continuously against CodeStrata's own Engine and Platform codebases (and any other CodeStrata-owned repositories), specifically to prove **consistency**: the same revision, config, rule pack, and feed snapshot produce semantically identical output across repeated runs (Determinism gate), and a genuine code change produces a traceable, expected change in findings rather than unexplained drift. This is the only tier where the team has full ground truth on what changed and why, which makes it the fastest, most trustworthy signal for catching a nondeterminism or regression bug before it reaches a repository nobody on the team understands from the inside. Dogfooding proves the Engine is reliable on code CodeStrata knows; it does not by itself prove the Engine is accurate on code it doesn't.

2. **External breadth tier — at least 50 large, identified open-source repositories.** Selected for real-world diversity (language mix, framework variety, monorepo vs. polyrepo, repository size and age) rather than convenience. This tier proves the Engine survives code nobody on the team has context on: it doesn't crash, doesn't silently mis-scope, degrades to `UNKNOWN`/`NOT_APPLICABLE` rather than inventing a pass on unsupported ground, and completes within the declared performance budgets (Performance gate) at realistic scale. A design partner's own technical evaluation will implicitly replicate this tier, so it must run on repositories the team does not already understand from the inside. Both Engine and Platform run against this tier — Platform's ingestion, workspace aggregation, and bulk-repository handling at this scale is itself part of what the tier proves (see Platform §3).

3. **Ground-truth tier — a smaller, labeled subset for the flagship depth-tier analyzers.** A bounded set of repositories with known, documented findings (planted CVEs, known secrets, deliberate architecture violations) specifically for Security & Supply Chain and the governed rule-authoring pipeline (Section 1, Depth investment tiering). This is what turns "flagship depth" from a stated priority into a measured false-positive/false-negative rate. Breadth without this tier can show the Engine runs everywhere without ever showing whether its highest-stakes findings are actually right.

**Gating scope.** All three tiers run, and results are reviewed, before any release — this is the baseline commitment. Per the Protect-vs-Iterate test (Platform §15), what differs by family is the bar applied to what the corpus finds: Security & Supply Chain and the governed rule-authoring pipeline must clear their declared coverage and precision/recall bar on the corpus before release, since these are the surfaces a buyer pressure-tests first. The other three families (Inventory, Architecture, Quality/Maintainability) must run clean of crashes and undeclared failures across the corpus, but may carry documented, visible gaps that continue closing post-launch, consistent with their solid-v1-and-iterate status. A gap is acceptable; an unreviewed or undisclosed one is not.

This corpus is also the closure evidence for the still-open launch-language-depth decision (Section 12): the external tier's actual language and framework mix is what confirms or revises the Java + JS/TS default, not a standalone research exercise.

### Scope-cut order if a gate is at risk

Database-layer and static-observability cross-cutting analysis are already deferred past MVP (Section 4) and are not part of what remains to protect. If a gate covering what remains in scope is at risk, cut in this order:

1. experimental Cloud/AI Readiness/Performance packs from release messaging and default execution;
2. additional AI providers or advanced narratives beyond one supported optional evidence-explanation path;
3. extension marketplace/productization;
4. extra language breadth;
5. deeper symbol/call precision beyond the selected reliable stacks;
6. nonessential output formats beyond JSON + HTML + SARIF.

Do **not** cut: YAML determinism, evidence lineage, architecture/security depth, Git/diff fundamentals, external installability, or the Engine/Platform independence test.

## 10. Decisions adopted from reference products and research

- From [MegaLinter](https://github.com/oxsecurity/megalinter): adopt declarative descriptors, consistent runners/reporters, execution budgets, and fixture-driven verification. Reject “many wrapped tools equals intelligence” as the CodeStrata product model.
- From [RepoWise](https://github.com/repowise-dev/repowise): adopt Git history as first-class repository evidence, index once/serve many locally, and combine churn/co-change with structural graphs. Reject model-written documentation and semantic retrieval as Engine truth.
- From [Alibaba OpenCodeReview](https://github.com/alibaba/open-code-review): adopt their deterministic scope selection, rule matching, and evidence-positioning discipline around the model. Reject their model-as-verdict pattern — OpenCodeReview's LLM agent renders the actual finding inside a deterministic pipeline; CodeStrata's rule execution must remain fully YAML-deterministic, with AI never deciding pass/fail on a canonical rule.
- From [Truxt](https://www.truxt.ai/): adopt the Platform lesson that engineering signals become more valuable when connected into one operational model, every answer exposes its evidence, and insight progresses toward governed action. Do not absorb its AI ROI, prompt/session capture, token optimization, coaching, broad connector, prediction, agent-workforce, or exploit-validation scope into the Engine MVP.
- From [Vinay's Repo Analysis Atlas](https://codestrata.github.io/repo-analysis-atlas/#innerloop-story): adopt READS x EMITS as the AnalyzerDescriptor architecture and use the periodic table to expose coverage/gaps, not as a mandate to implement every cell.
- From [Sigstore](https://docs.sigstore.dev/): use identity-bound signing and verification for official release files, images, SBOMs, attestations, rule packs, and paid assessment envelopes, with private/offline trust options for restricted customer environments.
- From the [current CodeStrata Engine](https://github.com/CodeStrata/codestrata-engine): preserve the strong CLI, graph, rule, evidence, incremental, reporting, and privacy foundations; narrow product claims and remove commercial concepts from the Engine boundary.

## 11. Market position and sales comparison

CodeStrata does not need to claim that it replaces every analysis or review product. Its defendable category is a versioned engineering-intelligence and decision system built on an open deterministic truth layer.

| Product/category | Established strength | CodeStrata's honest position |
|---|---|---|
| [CAST Imaging](https://www.castsoftware.com/imaging) | Deep enterprise application mapping, data access, transactions, and broad technology coverage | Do not claim immediate mapping parity. Win on lightweight/open adoption, transparent evidence, Git/change intelligence, deterministic YAML policy extensibility, and AI-native decision workflows. |
| [Truxt](https://www.truxt.ai/) | Engineering/AI operational graph, AI ROI, broad connectors, evidence-backed answers, agent governance, and action | Treat as a Platform-level competitor and market validator. Differentiate first through deeper open repository evidence, deterministic customer policy execution, source-local/VPC trust, and signed assessment provenance; defer organization-wide AI ROI and agent control. |
| [CodeScene](https://codescene.com/manage-and-reduce-technical-debt) | Behavioral analysis and hotspot-based technical-debt prioritization | Adopt the proven principle that complex code matters more when it changes frequently. Differentiate with architecture/security evidence, governed customer policies, and portfolio decision intelligence. |
| [SonarQube](https://www.sonarsource.com/docs/evaluation-guide.pdf) | Mature code-quality/security rules, language coverage, and quality gates | Do not compete on rule count. Coexist with or ingest useful evidence while adding repository structure, architecture boundaries, Git behavior, blast radius, cross-domain correlation, and leadership decisions. |
| [CodeRabbit](https://docs.coderabbit.ai/guides/code-review-overview) | AI-assisted PR review, summaries, suggestions, and fixes | CodeStrata's primary value is independently measured repository state, governed deterministic policy, evidence-backed deviation, and continuity beyond a single PR conversation. |
| [Alibaba OpenCodeReview](https://github.com/alibaba/open-code-review) | Deterministic pipeline controls combined with agent-assisted review | Share the deterministic-around-AI philosophy but cover the broader repository health, history, policy, and decision lifecycle. |
| [RepoWise](https://repowise.dev/architecture) | Live, priced, open-core repository graph, Git intelligence, health scoring, and agent-native MCP context, with a growing enterprise compliance tier (SSO/SCIM, RBAC, audit trail, SBOM/VEX) | Do not contest developer-context/agent-productivity ground where RepoWise already ships and iterates fast; assume it leads there until benchmarks prove otherwise. CodeStrata's own buyer is the compliance/governance function reacting to an audit, regulatory requirement, or board-level AI-governance question - a different line item than RepoWise's developer-productivity motion, even inside the same account. Differentiate specifically on customer-authored governed policy (LLM-drafted, human-approved, YAML-deterministic) and Sigstore-signed chain of custody on the assessment artifact itself, not on repeating their git/graph substrate at equal or lesser depth. Coexistence, not replacement, is the working assumption until evidence says otherwise. |
| MegaLinter and conventional static analyzers | Breadth, language coverage, and tool orchestration | Use external evidence selectively; do not become another linter bundle. CodeStrata owns normalized evidence semantics, correlation, versioned state, change, and decision context. |

### What CodeStrata should take from Truxt now

Truxt reinforces five choices already present in the CodeStrata direction:

1. **One connected operational model:** Engine produces the single-repository truth model; Platform connects repository, change, policy, delivery, runtime, and organizational context later.
2. **Every answer carries evidence:** evidence must be visible in AI conversations and executive summaries, not merely stored in a backend object.
3. **From metrics to decisions:** dashboards are insufficient; Platform should explain drivers, options, and next action while preserving observed/derived/inferred/recommended claim classes.
4. **AI governance as a paid outcome:** explicit AI/tool provenance may be connected to commits, PRs, findings, and policy only when the source provides that provenance. CodeStrata does not infer AI authorship from code alone.
5. **A compound product loop:** CodeStrata's version is **Capture -> Prove -> Compare -> Connect -> Decide -> Governed Action**. Engine owns Capture/Prove/local Compare; Platform owns Connect/Decide/Governed Action.

Do not copy Truxt's breadth into this launch. AI spend/ROI, prompt and session surveillance, DORA/incident correlation, token routing, coaching, autonomous agent squads, predictive risk, and exploit validation require different data, security controls, buyer proof, and product maturity. They remain Platform/later opportunities, not Engine backlog inputs.

Recommended sales explanation:

> **SonarQube and similar tools identify code-rule violations. CodeRabbit and OpenCodeReview review changes. CodeScene and RepoWise add behavioral and repository intelligence. CAST creates deep enterprise application maps. CodeStrata connects architecture, security, quality, technical debt, dependencies, and Git behavior into a versioned engineering state - governed by customer-authored, signed policy - then uses governed AI to help teams define policies, understand deviations, and decide what to fix, fund, modernize, or defer. Every material conclusion is traceable to evidence.**

Until CodeStrata publishes comparative benchmarks, sales and marketing must not claim better language coverage than SonarQube, deeper application mapping than CAST, better PR review than CodeRabbit/OpenCodeReview, better behavioral analysis than CodeScene, or better Git intelligence than RepoWise.

Initial differentiation to prove:

1. deterministic, inspectable, open Engine;
2. unified evidence across Architecture, Security, Quality, and Maintainability & Technical Debt;
3. source structure combined with Git/change behavior;
4. 100% traceability or explicit `UNKNOWN`;
5. customer policies authored conversationally and executed deterministically;
6. Platform continuity across repositories and releases;
7. AI reasoning over verified evidence rather than inventing the assessment.

## 12. Open decisions for collaborative refinement

Only decisions that can materially change build scope remain here:

| Decision | Default recommendation | Closure evidence |
|---|---|---|
| Launch language depth | Java + JS/TS as deepest structural paths; retain other current languages at explicitly lower declared tiers | External validation-corpus tier's actual language/framework mix (Section 9) and customer/design-partner repository mix |
| External vulnerability feed | One provider and pinned cache format, with offline `UNKNOWN` behavior | License, reproducibility, freshness, and rate-limit evaluation |
| History window default | Bounded by commit count/time with deterministic override | Performance tests across small/medium/large histories |
| Baseline representation | Explicit base revision or supplied prior snapshot; never hidden Platform state | Diff fixtures and Platform ingest contract |
| Open recipe | One transparent “Engineering Health” example only if it adds no separate runtime | Demonstrates composition without delaying gates |
| Experimental packs | Ship disabled vs exclude from first package | Dependency/isolation test and documentation clarity |

## 13. Backlog derivation contract

This document is the high-level scope input for backlog creation. The backlog must not be produced as a list of vague analyzer features. First create the detailed **CodeStrata Engine Measurement, Metrics & Evidence Contract**. That contract defines, for every assessment head and capability:

- question answered and engineering outcome served;
- read sources and applicability;
- extracted fact schemas and stable subject identity;
- metric name, definition, unit, direction, scope, and calculation;
- YAML rules, thresholds, severity, and confidence;
- required evidence and evidence mode;
- coverage contract and language depth;
- `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`, and `ERROR` behavior;
- baseline/candidate comparison and finding lifecycle;
- Engine output and Platform continuity consumer;
- positive, negative, partial-coverage, unsupported, and determinism fixtures.

Each backlog epic is then derived from one bounded capability. Each implementation story should deliver a vertical evidence slice:

```text
Read source
  -> extract versioned fact
  -> calculate metric/structure
  -> execute bundled YAML rule
  -> emit evidence-backed result
  -> compare baseline/candidate where applicable
  -> project to JSON/HTML/SARIF
  -> prove with fixtures and release gates
```

An analyzer story is not complete merely because code runs. Its Definition of Done requires:

- declared inputs, subject, applicability, and output contract;
- deterministic calculation and stable identifiers;
- YAML without executable code;
- evidence IDs on every material output;
- visible derivation, coverage, confidence, and limitations;
- explicit unsupported behavior rather than silent pass;
- good/bad, missing-input, partial-coverage, and change fixtures;
- repeated-run equivalence;
- schema validation and Platform ingestion without analyzer-specific logic;
- documentation of what the result does and does not prove.

Recommended backlog hierarchy:

1. **Foundation epics:** AnalyzerDescriptor, fact/evidence schemas, YAML compiler/runtime, repository identity, normalized envelope.
2. **Analyzer epics:** Inventory; Architecture; Security/Supply Chain; Quality; Maintainability & Technical Debt; Git/Change — Security/Supply Chain and the governed rule-authoring pipeline sequenced first for flagship depth. Database and observability cross-cutting capability groups are deferred past MVP and excluded from this backlog pass.
3. **Trust epics:** validation corpus, determinism, coverage, evidence completeness, telemetry privacy, Sigstore CI identity/signing/verification, private VPC trust roots, signed rule packs/results, SBOM/in-toto provenance, security, performance budgets.
4. **Experience epics:** Community local/CI journey, with-AI/without-AI modes, CLI, reports, narrow MCP, clean installation, packaging, documentation.
5. **Boundary epics:** remove/isolate portfolio/EIR/hosted/strategic AI concepts and validate Platform-neutral contracts.
6. **Integration epics:** Platform envelope ingestion, approved customer-rule package handoff, paid VPC worker deployment, and customer-controlled telemetry/export.

Backlog creation may begin only after the measurement contract identifies the launch metrics and evidence requirements. This prevents teams from implementing incompatible definitions behind the same assessment head.

## 14. Change discipline for this living document

- Record scope changes as explicit decisions, not silent edits to tables.
- A new Engine capability must identify its read source, emit type, evidence contract, owning analyzer family, and release-gate impact.
- A new Platform capability must state which stable Engine output it consumes; it may not introduce a reverse dependency.
- A new YAML operator requires security review, deterministic semantics, complexity/budget rules, compiler tests, and at least one reusable rule that justifies it.
- Analyzer count is not a success metric. Trust, coverage, reproducibility, precision, and usefulness of change evidence are.

### Decision register

This register contains only decisions that constrain the backlog. Items in Section 12 remain **PROVISIONAL** until their closure evidence is available.

| Status | Decision | Why it is locked / when to reconsider |
|---|---|---|
| **LOCKED** | Engine is a Platform-independent, single-repository truth and change runtime; Platform owns organizational continuity and decisions. | This is the product and dependency boundary. Reconsider only through an explicit company-level product decision. |
| **LOCKED** | MVP contains five native analyzer families and four public outcomes, built at tiered depth: Security & Supply Chain and the governed rule-authoring pipeline receive flagship validation investment before launch; Inventory, Architecture, Quality, and Git & Change ship at solid v1 depth and iterate post-launch. | Depth and evidence quality matter more than headline breadth, and uneven validation investment beats even validation investment spread too thin. Add a family only when it needs distinct facts, execution, and outcomes. |
| **LOCKED** | All executable rules use the bounded, versioned YAML DSL. | One deterministic runtime serves CodeStrata and customer rules without generated code or runtime AI. Reconsider only if the DSL cannot safely express a proven recurring need. |
| **LOCKED** | Community receives CodeStrata's bundled rule packs; Platform owns customer-rule authoring, approval, governance, and distribution. | This preserves an open, useful Engine while protecting the commercial policy lifecycle. |
| **LOCKED** | AI cannot create or alter canonical facts, metrics, findings, deviations, scores, or verdicts. | With-AI and without-AI modes must produce the same canonical assessment. AI may explain cited evidence and, in Platform, author governed rules and decisions. |
| **LOCKED** | Every material result carries evidence or an explicit `UNKNOWN`; coverage and limitations are visible. | CodeStrata guarantees traceability and honesty, not infallibility. Reconsider only by strengthening the contract, never by hiding uncertainty. |
| **LOCKED** | Git history, supplied diff, and deterministic deviation are MVP capabilities. | They distinguish CodeStrata from a conventional point-in-time scanner and connect repository structure to change behavior. |
| **LOCKED** | Cross-cutting database-layer analysis and static observability posture are deferred past MVP. | They are documented, specified capabilities, not cancelled ones — deferring them protects validation cycles for the flagship depth-tier surfaces instead of thinning effort across a partially-built sixth capability. Reconsider once Security & Supply Chain and the governed-rule pipeline have cleared their own depth bar. |
| **LOCKED** | Database and observability analysis, once built, is source-derived; runtime claims require later telemetry or live-system inputs. | The Engine may prove code-defined structure and static posture but must not claim behavior it has not observed. |
| **LOCKED** | Community runs locally or in CI; paid customers may run the same headless Engine inside their VPC. | Source and raw evidence can remain customer-controlled while Platform consumes stable, platform-neutral assessment contracts. |
| **LOCKED** | Telemetry is transparent and controllable in every edition and never changes analysis. | Community requires consent and durable disable; paid/VPC destinations and egress remain customer-administered. |
| **LOCKED** | Sigstore-backed identity, signing, SBOM/provenance, rule-package verification, and result provenance are part of the core trust offering. | Official artifacts require a verifiable chain of custody; private/offline VPC policies protect customer confidentiality. |
| **LOCKED** | Portfolio intelligence, persistent drift, GraphRAG, strategic agents, enterprise governance, prediction, and organizational attribution remain Platform/later. | Their value depends on durable organizational or operational context rather than one deterministic repository assessment. |
| **LOCKED** | The measurement, metrics, and evidence contract precedes backlog implementation. | Engineers need stable questions, facts, calculations, subjects, and evidence semantics before stories are assigned. |
| **LOCKED** | Launch scope is protected through parallel workstreams, acceptance gates, and explicit scope cuts, independent of schedule. | Delivery pace may vary with capacity; scope cuts must follow the declared order and must never expand scope or weaken trust gates. |
| **LOCKED** | The Engine and Platform validate against a three-tier corpus before any release: CodeStrata's own repositories (dogfood/consistency), at least 50 large identified external open-source repositories (breadth/scale), and a labeled ground-truth subset (precision/recall) — defined in Section 9. | Consistency alone cannot prove accuracy on code the team doesn't already understand; breadth alone cannot prove the flagship depth-tier findings are correct. All three are required and are not interchangeable with each other. |

| **LOCKED — 2026-09-12** | Rule → RuleSet → Policy → immutable Effective RuleSet → signed package is the rule foundation; Engine owns contracts and execution, Platform owns customer resolution/governance. | Formalizes composition without changing the five families, four outcomes or dependency boundary. |
| **LOCKED — 2026-09-12** | Structured YAML selector ASTs, explicit dependency/traversal semantics, typed overrides, RuleSet adoption defaults and safe message bindings. | Logic changes require new Rule revisions; effective settings and provenance enter the digest; rendered text never defines finding identity. |
| **LOCKED — 2026-09-12** | Governed scoped exceptions are Platform MVP; Engine receives resolved overrides and references only. | Preserve approval, expiry, visible coverage and immutable historical results without adding a GRC suite. |
| **LOCKED — baseline carried forward** | Engine is database-free; use memory and versioned local artifacts. | Aligns this specification with the authoritative Architecture and Database baseline; no reverse dependency. |
