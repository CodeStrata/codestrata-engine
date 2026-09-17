# CodeStrata Engine Measurement, Metrics & Evidence Contract

## Revision note — 15 September 2026

**Package revision: `ENGINE-2026-09-15-R1`.** Targeted launch amendment: first-class Engineering Hotspots; scoped repository-local ownership concentration; explicit boundary-spread and blast-radius summaries; report-facing capability coverage/freshness; visible HTML comparison and evidence views; installed-artifact report acceptance; and package revision verification. E08.3 is now a hard prerequisite of E10.2, bringing the plan to 99 hard story links. The 17 epics, 52 stories, 33 measurement groups, five analyzer families and four public outcomes are preserved. Engine remains database-free, Platform-independent and deterministic with YAML-only rule execution. No new score, analyzer family, public outcome, CodeGraph/RAG or customer-rule authoring scope is added.

This revision updates these five Markdown specifications. The master prompt book, all 52 split prompts and execution ZIP must be reconciled against this revision and reviewed before copying or G00 PASS; this delivery does not certify those older artifacts as updated. Existing numeric compatibility behavior is governed by the unchanged no-opaque-score contract; it is not a new launch score.

Version 1.2 | 15 September 2026 | Implementation planning baseline, pending team ratification in E01.1

This companion is created before deriving analyzer stories, as Engine specification v2.1 §13 requires. It specifies the launch measurements and shared semantics for the backlog. New numerical thresholds and resource defaults are proposed engineering starting points, not measurements of the current product or claims of accuracy. E01.1 records any adjustments before affected implementation starts. Locked product decisions remain unchanged.

## Ownership and launch shape

Five analyzer families produce four public outcomes: Architecture, Security, Quality, and Maintainability & Technical Debt. Inventory supplies context; Git contributes to the other outcomes. No database analysis or static observability family is added. Engine owns one repository or two explicit compatible states; Platform later selects/persists baselines and aggregates repository results.

The 33 entries below define bounded capability groups, not a claim that 33 individual YAML rules exhaust the catalog. Existing retained rules are inventoried and mapped to these groups before migration. Each actual bundled rule must have its own immutable ID/revision, parameter schema, default severity, applicable language depth, evidence contract and compliant/violating/UNKNOWN fixtures. Do not silently drop a working supported rule because its group has another example.

Launch reports use evidenced findings, named metrics, coverage and explicit outcome verdict/movement. This contract introduces no new opaque 0-100 overall score. If an existing numeric score remains in a supported compatibility projection, E01 must publish its exact old formula/version and limits; it cannot silently become the new canonical health definition. A score without a ratified derivation is unavailable/UNKNOWN, not a fabricated number.

## Shared fact and result semantics

Every fact has a schema/version, stable repository-local subject ID, source kind, value/unit, evidence IDs and extraction status. Evidence identifies the input revision or working-state digest, relative path/span or graph/feed/commit record, extractor version and limitation. Paths alone are not durable evidence identity. Never put absolute machine paths, Platform tenant IDs or credentials into the canonical body.

Use the existing Engine subject/fingerprint contract where it meets these rules, documenting deliberate compatibility changes. A repository root identity is explicit and local, not an inferred organization URL. File identity is normalized relative path under that repository; comparisons can apply verified Git rename mapping. Symbols add qualified kind/name and disambiguating source identity. Finding matching uses stable rule identity plus subject and occurrence semantics; source-line movement or message formatting alone cannot create a new finding. Ambiguous rename/occurrence mappings remain unknown.

| State | Required meaning |
|---|---|
| PASS | Applicable rule evaluated complete required evidence and its condition is not violated |
| FAIL | A rule violation is established with evidence; this is not an execution failure |
| UNKNOWN | Applicable evidence, supported semantics or coverage is insufficient for the requested conclusion |
| NOT_APPLICABLE | Explicit applicability predicate establishes that the check does not apply |
| ERROR | Input parsing, evaluator or infrastructure failure prevented required processing; retain safe reason and affected scope |

Enabled/disabled, suppressed and exempt are separate scope/configuration states. They do not become PASS or NOT_APPLICABLE to improve totals. A known positive finding can remain established while other subjects are unknown; an incomplete negative search cannot prove a clean outcome. Report aggregate coverage as partial and preserve subject-level results.

Metric records contain name/version, value or null, unit, scope, direction, numerator/denominator where relevant, evidence IDs, derivation and coverage. For boolean or descriptive inventory values, direction is neutral. Counts are exact nonnegative integers. Ratios lie in [0,1]; an empty denominator is NOT_APPLICABLE unless the rule explicitly defines another result. NaN/infinity are rejected. Decimal serialization is normalized to six fractional places for derived ratios; compare using the documented exact/rational value before presentation rounding.

Percentile operator v1 uses nearest rank: sorted N values, rank=max(1,ceil(p*N)) for 0<=p<=1; empty input is undefined/NOT_APPLICABLE. Deterministic order is by stable subject/rule/evidence ID, never message text or discovery order. Sum/min/max/distinct operate only on declared types. Missing values do not silently become zero. Where missing units could change a conclusion, report UNKNOWN or a declared lower bound, not an exact full-scope metric.

Confidence is evidence strength, not calibrated probability: **high** for supported exact syntax/manifest/lock/Git evidence and fully resolved witness; **medium** for an explicitly documented static convention/association; **low** only for a labeled non-authoritative indicator. Unsupported evidence has no fabricated confidence. Default high-severity flagship findings require high-confidence supported evidence; each rule's fixtures must validate that declaration.

Canonical inputs bind source/base/head or dirty-tree/index digest, Engine/analyzer/operator/schema/DSL versions, resolved RuleSet and signed-package digests, final local configuration, external feed snapshot and evaluation_time when a time-relative metric is used. Operational run IDs, execution durations, signature bytes and generation timestamps are separate from the deterministic body. Repeat tests pin evaluation_time; “today” never enters an unrecorded formula.

### Report-facing capability coverage and freshness

The canonical envelope includes one record per declared capability, not only a family total: capability ID/version, scope, applicability/execution state, evaluated and eligible counts, unknown/error/excluded counts, coverage ratio or null with reason, evidence references and limitations. Keep coverage, freshness, confidence and signature trust separate. Unsupported, disabled, suppressed and unavailable scope remains visible. An unknown denominator is UNKNOWN, never 0% or 100%.

Freshness binds the pinned `evaluation_time`, source snapshot/digest, available source publication/update time, age and versioned freshness policy. Emit fresh/stale/UNKNOWN/NOT_APPLICABLE with a safe reason code and explanation. For vulnerability matching expose feed provider/version/digest, publication/update time, configured maximum age and missing/stale/unsupported-feed reasons; cached observed matches remain qualified, and insufficient feed freshness cannot prove a clean result. No silent network refresh. For Git-derived capabilities expose pinned head, requested window, observed time/commit bounds, included/excluded commit counts, shallow/truncation/merge/rename policy and history coverage reasons. Git recency describes the last included change; an old commit alone does not prove a stale checkout. If comparison to an upstream state is unavailable, say UNKNOWN rather than claiming the local head is current. Capabilities needing no time-sensitive source use NOT_APPLICABLE freshness with explanation. Missing source time yields UNKNOWN freshness, not the report generation time.

## Launch depth and bounded defaults

Java and JS/TS are the proposed deepest structural paths; Python, PHP and C#/.NET remain at their existing verifiable tiers. File detection alone does not earn structural-language support. Capabilities declare supported syntax/framework/build versions and test evidence before promotion. All five families must produce substantive supported results on the declared primary stacks; labeling every repository UNKNOWN is not launch completion.

For supported Java/JS/TS complexity, the starting branch map counts each if, for, while, do-while, catch, non-default switch case, ternary condition, and short-circuit &&/|| condition as one decision, excluding nested function bodies from the enclosing function. Else/default/finally do not add decisions. Switch expressions and optional/nullish constructs need explicit parser/version mapping before being claimed. Other languages require their own mapping; do not use token keyword counting as equivalent AST complexity.

Initial bounded defaults to ratify: YAML 1 MiB/document, maximum nesting 32, aliases disabled, RuleSet parent depth 8 and 1,000 effective rules; graph traversal maximum depth 32 with default impact depth4, 100,000 visited nodes and 500,000 visited edges; rule evaluation 5 seconds proposed soft budget with explicit numeric process-enforced hard cap and cancellation grace ratified in E01.1, overall run by measured size tier. Declare any stricter per-operator limit. Never execute repository build/test scripts, package installation hooks or arbitrary YAML code. These are proposed resource defaults; E01/E15 must tune against the declared supported capacity before publication.

One vulnerability-feed provider must be selected and normalized into a versioned offline cache before E06.2. Provider choice, redistribution terms, range semantics, freshness limit and unavailable behavior are an explicit bounded decision; there is no default silent online fallback. Proposed freshness is seven days at pinned evaluation_time, subject to the selected source's update model. Feed absence limits vulnerability checks, not the entire offline assessment. License/release-date facts use permitted deterministic metadata only; absence remains UNKNOWN.

## Rules, configuration and comparison

Every named analyzer check is implemented as bundled declarative YAML through the one compiler/evaluator. Trusted native code extracts facts and implements bounded generic operators. Inheritance, typed overrides, selector references, digest resolution and scoped exception semantics follow Engine v2.1 §5 exactly. RuleSet adoption labels never activate rules by themselves. Customer approval, organization permissions and exception lifecycle stay in Platform; Engine gets fully resolved subject scope and opaque references.

Numeric defaults named below are exposed typed parameters with validated bounds. A parameter value change is configuration and is hashed; changing its schema or predicate is new rule logic. Severity has default and effective values. Suppression/exemption changes affect coverage and provenance without rewriting historical findings. Signed base catalog identity and unsigned local configuration identity remain separate.

Each measurement supports baseline/candidate comparison only where schema, formula, identity, rule/operator settings, inputs and coverage allow it. Counts compare in units; ratios in absolute fractions. Proposed default change thresholds are strict >0 for counts and strict >0.01 for ratios; per-rule profiles can replace them explicitly. Descriptive inventory, centrality, ownership and ranked concern metrics do not automatically influence a health verdict. Raw deltas may be shown with clear cause/compatibility labels even when outcome movement is unavailable.

Engine produces repository-level movement and driver evidence. Platform will select compatible baselines and aggregate them; it must not reconstruct analyzer findings. Cause attribution records source/feed/configuration/mixed/undetermined. AI-adoption dates never establish causality. All output formats are projections from the same versioned result, and absence from an incomplete result cannot prove a finding resolved.

## Fixtures and completion rule

Every M-entry below inherits this fixture matrix in addition to its specific variants: compliant/known-positive, violating/known-negative as applicable, missing input, partial coverage, unsupported syntax, deterministic repeat, and baseline/candidate transition. For a descriptive metric, use exact expected value/structure rather than inventing a PASS/FAIL rule. Tests include threshold equality and just-beyond-threshold values, wrong schema and corrupt evidence. An independent expected result must exist before comparing old and new implementations; matching an old bug is not correctness.

Every analyzer story closes the full slice: input -> fact -> metric/graph -> YAML check where applicable -> evidence/status -> comparison-ready identity -> common JSON/HTML/SARIF projection -> fixtures. Before the final report UI exists, test the common projection contract with Engine-local adapters; story closure requires the real common projections to pass, not a mock used as permanent acceptance.

Family coverage, metric UNKNOWNs, disabled scope, aggregate failures and confidence survive the consumer fixture. A consumer validates standard schemas and relationships without recomputing formulas or importing analyzer internals. Engine contract readiness does not claim live Platform ingestion; that integration is a follow-on release gate under the user's Engine-first sequence.

All definitions below are traceable to the supplied Engine v2.1 §§3-5,9,12-13 and Platform v1.1 §10.1. Formula/default choices added here are proposed and versioned, not attributed to the original specifications.

## Revised shared contracts required before affected implementation

### Outcome drivers and persistent finding lifecycle

E01 publishes a versioned launch manifest mapping each rule/metric to family, outcome or contextual role, applicability, unit, direction, epsilon and required coverage. Use this manifest for outcome aggregation and comparison. Empty or entirely disabled/exempt driver sets are unavailable/NOT_APPLICABLE, not healthy. Preserve known violations even with unrelated unknown scope. A first run cannot show a trend.

A persistent finding improves/worsens only under a declared, compatible violation magnitude and comparator. Binary violations that remain present are unchanged; passing the rule condition after complete compatible reevaluation resolves them. Severity overrides and other policy changes are configuration, not customer code improvements. Display raw qualified deltas separately where whole-outcome comparison is incompatible.

### Supplied context, preview and severity provenance

Optional supplied PR context has a bounded typed schema and separate digest/provenance. Validate revision agreement. Source/PR/commit text is untrusted input, not proof or instructions. Narrative-only context changes do not alter canonical findings/metrics/verdicts. Commit-message bug-fix markers are bounded, versioned contextual indicators and never counts of proven defects.

Candidate-rule preview uses the same compiler, operators, evidence semantics and permitted input scope as production. Bind candidate/selector/config/input/version digests and expected/actual fixture results to preview-only output. Never reuse stale test/preview evidence or promote its signer/purpose to production. Customer approvals and authoring UI remain Platform work; local developer fixtures remain clearly custom.

Reuse existing confidence/context structures only after a documented mapping into these semantics. Any context-derived default severity must be versioned and visible; do not let old post-processing silently rewrite approved effective severity. Preserve existing valid rule IDs and freeze a compatible identifier grammar in E01; historical documentation cannot overrule current customer-namespace requirements.

### Headless operations and quality evidence

Version local health/progress/terminal status independently of assessment truth. Define hard deadlines, cancellation grace and resource/output/file limits; process failure cannot expose a completed manifest or successful signature. Local retention protects source, supplied baselines and active readers; interrupted writes, disk full and output conflicts are explicit failures. Structured local audit records are redacted and independent of optional outbound telemetry. No new HTTP service or AWS dependency is required.

The Team Execution and Quality Gates document supplies G00, per-change checks and cumulative G10/G20/G30/G40/G50/G52 audits. Future gates remain NOT_RUN/NOT_YET_DUE; passed planning validation is not evidence of passed Engine runtime tests. This contract retains 33 measurement groups, with the review amendments integrated below.


## M01 - Repository classification and scope

**Family / outcome:** Inventory / Context

**Inputs and scope:** Source tree, exclusions, manifests

**Definition and calculation:** Count files by mutually exclusive primary class: source/test/config/infra/docs/generated/vendor/binary/unknown. Supported fraction = supported eligible files / eligible files; publish numerator and denominator. Ignored files stay in scope inventory.

**Rule, threshold and interpretation:** No health verdict; classification metric only. Zero eligible files => NOT_APPLICABLE.

**Required evidence:** Normalized relative path, content digest, classifier version, ignore reason and manifest location.

**Missing/partial behavior:** Unreadable/dynamic regions classified unknown; a detection count does not prove structural support.

**Required fixtures:** Mixed-language; generated/vendor; symlink escape; binary; empty repo; unreadable subtree.

**Owning stories:** E05.1, E05.2, E05.3.

## M02 - Technology, component and dependency inventory

**Family / outcome:** Inventory / Context

**Inputs and scope:** Manifests, lockfiles, source roots, build configuration

**Definition and calculation:** Distinct normalized technology/component records with evidence; dependency count separately by declared coordinate and resolved package identity/version. Edges retain directness and resolution status.

**Rule, threshold and interpretation:** No invented health score. Parseable unsupported ecosystem is disclosed as detection-only.

**Required evidence:** Manifest/lock location, ecosystem/package identity, source roots, parser version.

**Missing/partial behavior:** Missing resolution cannot be represented as no dependencies; unsupported manifests UNKNOWN for dependency depth.

**Required fixtures:** Maven/npm resolved vs missing lock; Composer/NuGet lower tiers; workspace packages; duplicate coordinates.

**Owning stories:** E05.1, E05.2, E05.3.

## M03 - Configured build and CI checks

**Family / outcome:** Inventory / Context

**Inputs and scope:** CI/build/config source

**Definition and calculation:** For each configured job/step record literal or safely parsed command, condition, tool category and target. Counts: test/coverage/lint/security invocations statically observed.

**Rule, threshold and interpretation:** Descriptive only; observed configuration never means the job ran or passed.

**Required evidence:** CI path/line, literal command, condition, deterministic parser rule.

**Missing/partial behavior:** Indirect scripts or unknown expressions => unresolved invocation, not absent check.

**Required fixtures:** Direct command; conditional job; delegated script; no CI; malformed YAML.

**Owning stories:** E05.1, E05.2, E05.3.

## M04 - API and configuration surfaces

**Family / outcome:** Inventory / Context

**Inputs and scope:** Supported source AST and config

**Definition and calculation:** Distinct statically declared API entrypoints/config/deployment surfaces keyed by source subject and declaration kind.

**Rule, threshold and interpretation:** No runtime availability or observability score.

**Required evidence:** Declaration symbol/path/line and extraction capability.

**Missing/partial behavior:** Dynamic routing/framework unsupported => UNKNOWN area with detected-only inventory if available.

**Required fixtures:** Supported route; no routes; dynamic route; generated config; unresolved framework.

**Owning stories:** E05.2, E05.3.

## M05 - Module dependency cycles

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Resolved module graph

**Definition and calculation:** Number of strongly connected components of size >1 plus single-node self-loops, each reported once; include member IDs and witness edges. Lower is favorable.

**Rule, threshold and interpretation:** arch.cycles: FAIL when count >0, default medium; incomplete negative graph cannot PASS.

**Required evidence:** Observed module edges and source locations, SCC membership and witness path.

**Missing/partial behavior:** Known cycle can FAIL despite unrelated unknown edges; absent cycle needs complete relevant edge coverage.

**Required fixtures:** A->B->A; acyclic A->B; self-loop; unresolved import; reordered file traversal.

**Owning stories:** E07.1, E07.3.

## M06 - Cross-module coupling

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module import/depends_on graph

**Definition and calculation:** Per module fan_in/out = distinct other modules using/used by it. For the file import-edge view, external-edge ratio = distinct eligible resolved file import edges whose endpoint component IDs differ / all eligible resolved file import edges with both endpoint component IDs known in the same scope. Include same-component edges in the denominator; exclude duplicate edges. Publish unresolved/unmapped exclusions and coverage. Lower fan_out favorable only under the same scope; ratio is descriptive.

**Rule, threshold and interpretation:** arch.fan_out: default threshold 10 distinct modules, medium, declared configurable; ratio descriptive.

**Required evidence:** Module edge IDs and denominator.

**Missing/partial behavior:** Zero edges ratio NOT_APPLICABLE; unresolved imports make count lower-bound and no confident threshold PASS.

**Required fixtures:** Boundary at 10/11; duplicate edges; zero edges; unknown imports.

**Owning stories:** E07.1, E07.3.

## M07 - Declared boundary and direction violations

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Module graph and explicit local pattern configuration

**Definition and calculation:** Count unique disallowed source-target edge identities against declared layer/module constraints. Lower is favorable.

**Rule, threshold and interpretation:** arch.boundary: FAIL >0, high; bundled API/internal example direct depth1. No declared pattern => NOT_APPLICABLE.

**Required evidence:** Constraint identity, configured scope and direct dependency witness.

**Missing/partial behavior:** Unresolved relevant edge => UNKNOWN for unproven negative scope; never invent intermediate boundary.

**Required fixtures:** Compliant API/public; violating API/internal; unresolved import; selector rebinding.

**Owning stories:** E07.2, E07.3.

## M08 - Component concentration

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Eligible source files and component mapping

**Definition and calculation:** For each component: nonblank noncomment source lines / total such lines in scoped repository. Maximum share reported; lower concentration not automatically better.

**Rule, threshold and interpretation:** arch.concentration: advisory finding above configured 0.60 share only with >=2 components; low default.

**Required evidence:** Line-count derivation, component membership and denominator.

**Missing/partial behavior:** Unmapped or unreadable eligible files invalidate full-repo share; report observed partial value.

**Required fixtures:** 60%/61%; single component; unmapped files; generated exclusion.

**Owning stories:** E07.2, E07.3.

## M09 - Structural centrality and reach

**Family / outcome:** Architecture / Architecture

**Inputs and scope:** Versioned module/file graph

**Definition and calculation:** For graph node universe V, centrality(v) = count of distinct incoming neighbors u in V with u != v / max(1, |V|-1). Deduplicate parallel edges; self-loops do not enter numerator but may enter M05 cycle detection. Reach = unique nodes via chosen edge/direction/depth excluding seed. Descriptive; partial universe or unresolved edges cannot prove exact whole-scope centrality.

**Rule, threshold and interpretation:** No universal centrality PASS/FAIL; use impact context, not defect probability.

**Required evidence:** Seed/edge types/node set and traversal depth, direction and cutoff metadata.

**Missing/partial behavior:** Unresolved edges or exhausted traversal bound => lower-bound reach plus UNKNOWN completeness.

**Required fixtures:** Diamond dedupe; cycle termination; disconnected nodes; depth cutoff. Singleton; self-loop; two-node graph with self-loop and external incoming edge; parallel edges; unknown universe.

**Owning stories:** E07.2, E07.3.

## M10 - Secret and private-key findings

**Family / outcome:** Security / Security

**Inputs and scope:** Supported source/config literal evidence

**Definition and calculation:** Count unique rule + source-subject + occurrence findings after supported placeholder classification. Lower favorable. Keep identity independent of raw secret bytes.

**Rule, threshold and interpretation:** security.secret/private_key: high or critical per reviewed bundled rule; no raw value retention.

**Required evidence:** Path/line, detector ID, safe secret type and redacted span.

**Missing/partial behavior:** Unsupported encoding/language prevents clean claim for that scope; never scan full Git history by default.

**Required fixtures:** Synthetic valid-format key; placeholder; encoded/unsupported; duplicate literal; zero raw-secret canary leakage.

**Owning stories:** E06.1.

## M11 - Insecure configuration findings

**Family / outcome:** Security / Security

**Inputs and scope:** Static supported TLS/auth/CORS/debug config

**Definition and calculation:** Separate counts for disabled verification/auth, permissive CORS and debug production configuration; exact production context must be evidenced.

**Rule, threshold and interpretation:** Each condition is a named YAML rule with default severity migrated/reviewed from current catalog. No generic runtime exploitability claim.

**Required evidence:** Config path/line/value classification and context evidence.

**Missing/partial behavior:** Unknown environment/indirect config => UNKNOWN context, not assumed production.

**Required fixtures:** True/false settings; placeholder; conditional environment; conflicting configuration; unsupported expression.

**Owning stories:** E06.1.

## M12 - Resolved dependency and version hygiene

**Family / outcome:** Security / Security

**Inputs and scope:** Manifest declarations and available lock resolution

**Definition and calculation:** Resolution coverage = fully resolved eligible declaration IDs / all eligible declaration IDs in the same manifest/workspace/environment scope. Count each declaration once; all required contexts must be established to count complete. Resolved package/version occurrences and transitive inventory are separate counts. A known positive denominator with none resolved gives 0 coverage plus missing-resolution status; unknown denominator UNKNOWN; zero eligible declarations NOT_APPLICABLE. Count mutable/unbounded/unresolved/duplicate/conflicting declarations separately.

**Rule, threshold and interpretation:** Named dependency YAML rules retain audited IDs/defaults; missing version evidence is a gap, not a safe dependency.

**Required evidence:** Declaration and lock paths, package coordinates, direct/transitive dependency path.

**Missing/partial behavior:** Unknown ecosystem/range resolution yields UNKNOWN; never install packages to infer resolution.

**Required fixtures:** Pinned vs wildcard; duplicate/conflict; lock mismatch; transitive package; unknown version scheme. One declaration/two resolved versions/transitive packages; partly resolved contexts; zero/unknown denominator; no ratio above one.

**Owning stories:** E06.2.

## M13 - Known vulnerability matches

**Family / outcome:** Security / Security

**Inputs and scope:** Resolved package versions + pinned vulnerability feed

**Definition and calculation:** Count distinct canonical advisory alias-group + ecosystem/package/version identities; retain all dependency paths without multiplying finding count. Lower favorable for same feed.

**Rule, threshold and interpretation:** security.known_vulnerability uses deterministic feed severity; missing severity remains unknown and visible. Explicit configured fallback, if any, must be versioned.

**Required evidence:** Advisory ID/aliases/range/source snapshot digest/time plus resolved package/path.

**Missing/partial behavior:** No fresh supported feed or no exact version => UNKNOWN matching scope. Zero matches means none in that snapshot, not secure.

**Required fixtures:** Affected/unaffected versions; withdrawn advisory; alias dedupe; prerelease boundary; stale feed; same code/new advisory.

**Owning stories:** E06.2.

## M14 - Deterministic license metadata and declared risk

**Family / outcome:** Security / Security

**Inputs and scope:** Resolved package license metadata and explicit allow/deny configuration

**Definition and calculation:** Count known SPDX-compatible license expressions and unknowns; evaluate only supported expression semantics against explicit configured policy.

**Rule, threshold and interpretation:** license.disallowed: configured deny result, default medium; absent policy => metadata only. No legal compliance verdict.

**Required evidence:** Package/license source and configured decision rule.

**Missing/partial behavior:** Missing/conflicting metadata or unsupported expression => UNKNOWN, not disallowed or allowed by guess.

**Required fixtures:** Allowed/denied; dual license; malformed expression; missing metadata; conflict.

**Owning stories:** E06.3.

## M15 - Security classification quality

**Family / outcome:** Security / Validation

**Inputs and scope:** Labeled evaluable findings and negatives

**Definition and calculation:** Precision=TP/(TP+FP); recall=TP/(TP+FN); report TP/FP/FN/TN and UNKNOWN by rule group. Do not remove missed known-supported positives from FN.

**Rule, threshold and interpretation:** Proposed release thresholds: >=0.95 precision and >=0.90 recall; >=20 positive and >=20 negative cases per flagship group. Zero denominator => undefined, not 100%.

**Required evidence:** Label manifest fixed before tuning, result identities and reviewer decisions.

**Missing/partial behavior:** Unsupported cases disclosed separately; unexplained UNKNOWN in declared supported cases counts as missed evaluation and blocks promotion.

**Required fixtures:** Planted keys/config/advisory ranges; safe lookalikes; hidden holdout; independent label review.

**Owning stories:** E06.3.

## M16 - Source size and function complexity

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported AST and source tokens

**Definition and calculation:** Per function cyclomatic v1 = 1 + count of declared branch constructs, with language-specific mapping frozen before use; report physical nonblank noncomment lines and function distribution.

**Rule, threshold and interpretation:** quality.complexity: default >15 medium; size >80 function lines low; configurable and explicitly heuristic.

**Required evidence:** Function identity/span, counted branch locations and formula version.

**Missing/partial behavior:** Parser cannot establish function => UNKNOWN metric, never fallback to misleading cross-language number.

**Required fixtures:** Straight-line; if/loop/case/boolean mapping; nested functions; malformed syntax; threshold boundaries.

**Owning stories:** E08.1.

## M17 - Maximum nesting depth

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported AST

**Definition and calculation:** Maximum control-flow nesting depth per function under declared language construct map; lower favorable at same scope.

**Rule, threshold and interpretation:** quality.nesting: >4 medium, configurable.

**Required evidence:** Function/span and maximum-depth witness constructs.

**Missing/partial behavior:** Unknown parse sections invalidate negative claim; absent functions => NOT_APPLICABLE.

**Required fixtures:** Depth4/5; nested lambda separation; malformed block; language-specific branch syntax.

**Owning stories:** E08.1.

## M18 - Token clone indicator

**Family / outcome:** Quality / Quality

**Inputs and scope:** Normalized eligible source token streams

**Definition and calculation:** Identify exact normalized token runs >=50 tokens spanning >=5 lines; merge overlaps before duplicated-line numerator / eligible source-line denominator. Version token normalization.

**Rule, threshold and interpretation:** quality.clone_indicator: ratio >0.10 low advisory; indicative clone, not proof duplication is wrong.

**Required evidence:** Matched file spans, normalization version, merged numerator/denominator.

**Missing/partial behavior:** Unsupported tokenization or scan cutoff => partial ratio/UNKNOWN full scope.

**Required fixtures:** Exact clone; renamed identifier policy; overlapping runs; generated exclusions; no eligible lines.

**Owning stories:** E08.1.

## M19 - Test inventory and association

**Family / outcome:** Quality / Quality

**Inputs and scope:** Test declarations, imports and configured conventions

**Definition and calculation:** Test counts by framework; fraction of eligible production units with at least one supported static test association. Evidence strength distinguishes import/reference from naming convention.

**Rule, threshold and interpretation:** quality.test_association: advisory only; do not label as measured runtime test coverage.

**Required evidence:** Test declarations, source-to-test association and its method/confidence.

**Missing/partial behavior:** Unsupported framework/indirect test generation => UNKNOWN association scope.

**Required fixtures:** Direct reference; convention-only; no tests; generated tests; ambiguous association.

**Owning stories:** E08.2.

## M20 - Skipped/disabled tests

**Family / outcome:** Quality / Quality

**Inputs and scope:** Supported test source syntax

**Definition and calculation:** Count explicitly skipped/disabled tests, with reason where static literal; lower favorable only with unchanged test scope.

**Rule, threshold and interpretation:** testing.disabled: >0 low/medium per catalog; distinguish conditional skips.

**Required evidence:** Test identity, annotation/call span and static condition.

**Missing/partial behavior:** Dynamic skip condition => unknown eligibility, not unconditional disabled.

**Required fixtures:** Explicit disabled; enabled; conditional; unsupported decorator; test deletion.

**Owning stories:** E08.2.

## M21 - Configured test and coverage invocation gaps

**Family / outcome:** Quality / Quality

**Inputs and scope:** M03 CI observations plus test/coverage configuration

**Definition and calculation:** Boolean/count of declared test/coverage capabilities with no statically observed invocation in supported CI/build scope.

**Rule, threshold and interpretation:** testing.ci_gap: medium only for proven absent invocation in complete supported config; otherwise UNKNOWN.

**Required evidence:** Configured tool, job command evidence and checked scope.

**Missing/partial behavior:** External workflow or script not inspected => UNKNOWN. No runtime pass/fail or coverage percentage.

**Required fixtures:** Declared+invoked; declared+absent; delegated script; conditional job; no CI applicability.

**Owning stories:** E08.2.

## M22 - Churn-weighted complexity hotspots

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

## M23 - Dependency staleness and concern ordering

**Family / outcome:** Quality / Maintainability

**Inputs and scope:** Resolved dependency release dates from permitted pinned metadata; M10-M22

**Definition and calculation:** Staleness days = declared evaluation_time minus known installed-version publication_time. Concern order tuple: effective severity, valid evidence class, hotspot where comparable, stable finding ID; no weighted overall score.

**Rule, threshold and interpretation:** maintainability.dependency_age: >730 days low advisory if dates known; age does not prove insecure/unsupported.

**Required evidence:** Version/date source snapshot and explicit evaluation_time; ordering contributors.

**Missing/partial behavior:** No release-date metadata => UNKNOWN age. Assessment date must be pinned for repeatability.

**Required fixtures:** Known old/new; unknown date; future/invalid timestamp; identical severity ties; changed metadata snapshot.

**Owning stories:** E08.3.

**Ordering distinction:** The existing M23 finding-concern tuple is separate from the M22 Engineering Hotspot list. Its severity/evidence/hotspot inputs are labeled as ranking inputs for that tuple; centrality/reach/ownership and temporal co-change are contextual and add no hidden weight. Publish the versioned evidence-class ordering and handling of incomparable hotspot values in E01.1. HTML displays the canonical order and explanation; it never computes another priority or score.

## M24 - Churn and recency

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Pinned local Git history and rename policy

**Definition and calculation:** Per file/component sum added+deleted text lines in included commits; recency uses pinned UTC evaluation_time and the recorded latest valid included commit time. Proposed v1 history profile for E01.1 ratification: all non-merge commits reachable from pinned head, bounded by UTC committer timestamp within the last 180 days and then latest 1000, ordered timestamp descending then SHA. Root commits compare to empty tree; non-root commits to their sole parent. Merge-only conflict-resolution edits are excluded and must be disclosed; a later first-parent-diff profile is a different version. Never combine first-parent-only traversal with skipping merges without disclosing lost coverage. Future timestamps are invalid for recency and disclosed. A separate contextual bug-fix marker counts included commit messages matching a ratified bounded versioned marker set; it does not count proven bugs fixed.

**Rule, threshold and interpretation:** Descriptive only. E01.1 ratifies traversal/merge/time/marker defaults before E09 implementation. Message markers never influence a defect, productivity or authorship verdict.

**Required evidence:** Commit SHA/time, numstat, rename map and exact window.

**Missing/partial behavior:** Shallow/absent history => partial/UNKNOWN full-window measurement; binary churn unknown.

**Required fixtures:** Known edits; rename; merge; binary; shallow history; exact window boundary. Merge-only integration with reachable feature commits; squash; merge conflict-only edits disclosed; future timestamp; positive/misleading bug-fix marker.

**Owning stories:** E09.2, E09.3.

## M25 - Repository, component and file ownership concentration

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

## M26 - Temporal co-change

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Included commits to file/component incidence

**Definition and calculation:** For pair A,B: cochanged commit count / union commits touching A or B (Jaccard); report support count, require >=3 cochanged commits to label supported relation.

**Rule, threshold and interpretation:** Evidence of co-change, not architectural dependency or causal relation.

**Required evidence:** Commit IDs, member files/components, support and union denominator.

**Missing/partial behavior:** Window incomplete => qualified observed result; fewer than3 support => insufficient support.

**Required fixtures:** Always together; unrelated; exactly3 support; bulk formatting commit; shallow history.

**Owning stories:** E09.2, E09.3.

## M27 - Change size, spread and test touch

**Family / outcome:** Git / Cross-cutting

**Inputs and scope:** Explicit working/index/base-head/patch inputs

**Definition and calculation:** Count changed text lines, files and mapped components. test_touch = whether changed set contains known test/config-test units, separately from impacted-unit association. Optional supplied PR title/description/base/head SHAs/labels/linked-reference strings live in a bounded context record with supplied provenance/digest. Context must agree with claimed source revisions or disclose conflict. No hosted lookup; context narrative never proves code behavior. Narrative-only changes leave canonical analysis identical.

**Rule, threshold and interpretation:** Descriptive; missing test touch is not proof changes are untested.

**Required evidence:** Diff hunks, state digests, file classes and component IDs.

**Missing/partial behavior:** Unresolvable patch base or binary changes preserve partial size/impact limits.

**Required fixtures:** Staged vs working; rename; add/delete; binary; patch missing base; test-only diff. Absent/valid/oversized/malformed PR metadata; injection text; SHA conflict; context-only change; telemetry exclusion and escaped rendering.

**Owning stories:** E09.1, E09.3.

**Explicit change-summary fields:** Publish changed-file and changed-component IDs/counts, unmapped changed-file count and mapping coverage, plus architecture-boundary spread when declared M07 boundary membership is available: the distinct declared boundary-member IDs containing changed subjects, with count and mapping evidence. Identify the boundary dimension/profile (for example layers); do not combine dimensions or infer architectural boundaries from folder names. Missing declarations/membership is UNKNOWN, not zero crossed boundaries. E09 emits the changed-scope facts; E10.2 joins architecture facts and publishes the boundary/impact summary under M29.

## M28 - Finding lifecycle and metric delta

**Family / outcome:** Change / All four

**Inputs and scope:** Two explicit compatible canonical states

**Definition and calculation:** Match by versioned stable rule/subject/evidence occurrence identity. Metric delta = candidate-base with pinned units/scope. Finding lifecycle as specified; absent finding resolved only after complete compatible reevaluation. Persistent findings use a rule-declared versioned violation magnitude for improved/worsened. A binary violation that remains present is unchanged; decreasing below the rule condition is resolved only with complete compatible reevaluation. Severity overrides are config changes, not source fixes. Without a comparable magnitude, do not invent intermediate movement.

**Rule, threshold and interpretation:** New/worsened unfavorable; resolved/improved favorable; message-only changes unchanged. Local source edit versus policy override is distinguished.

**Required evidence:** Both artifact digests, matching rule version, evidence pair and compatibility reasons.

**Missing/partial behavior:** Incompatible rules/coverage/identity => UNKNOWN, never synthetic resolution.

**Required fixtures:** Stable; fixed; new; message-only; rename; coverage loss; policy-severity change. Reduced magnitude while still violating; binary persistence; severity-only override; unknown comparator.

**Owning stories:** E10.1, E10.3.

## M29 - Graph delta and static blast radius

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

## M30 - Thresholded outcome movement

**Family / outcome:** Change / All four

**Inputs and scope:** Compatible metric/finding deltas with directions and declared epsilon

**Definition and calculation:** Qualifying change: strict delta beyond versioned threshold; counts default epsilon0, ratios epsilon0.01 absolute, advisory metrics excluded unless configured. Classify Insufficient > Mixed > Deteriorated > Improved > Stable. Use the versioned launch driver manifest to define exactly which rules/metrics belong to each outcome, applicability, directions, epsilons, required coverage and scope compatibility. Empty or entirely disabled/exempt eligible driver sets yield unavailable/NOT_APPLICABLE, never healthy/Stable by default. Snapshot execution/status/coverage/trust remain separate; a known violation survives unrelated incomplete evidence.

**Rule, threshold and interpretation:** Improved needs >=1 favorable and no unfavorable; Stable has neither. Required covered metric UNKNOWN or incompatible policy forces Insufficient. No overall numerical average.

**Required evidence:** Qualifying drivers, excluded contextual metrics, threshold profile and both coverages.

**Missing/partial behavior:** First run/no baseline => Insufficient/no comparison. Known partial deltas may display without full-outcome verdict.

**Required fixtures:** All unchanged; only improvement; only deterioration; mixed; coverage drop; exact epsilon boundary. Empty outcome; disabled-all scope; known violation with partial coverage; catalog driver mapping.

**Owning stories:** E10.2, E10.3.

## M31 - Cause attribution

**Family / outcome:** Change / Security and other outcomes

**Inputs and scope:** Input/Engine/rule/config/feed digests and optional controlled paired reruns

**Definition and calculation:** Source-only, feed-only, configuration-only, mixed or undetermined attribution. If multiple dimensions differ, only controlled equivalent-input comparisons justify isolated cause.

**Rule, threshold and interpretation:** Feed-driven CVE changes cannot be called customer code deterioration. No AI-causality inference.

**Required evidence:** Changed input dimensions and controlled rerun references if performed.

**Missing/partial behavior:** Lack of controlled evidence => mixed/undetermined, never guessing dominant cause.

**Required fixtures:** Same code/new CVE; dependency fix/same feed; severity override; source+feed changed.

**Owning stories:** E10.2, E10.3.

## M32 - Export and trust provenance

**Family / outcome:** Cross-cutting / Trust

**Inputs and scope:** Canonical artifacts and selected export profile

**Definition and calculation:** Original canonical digest preserved; exported projection lists original digest, allowed/withheld categories, export-policy version and separate signature metadata.

**Rule, threshold and interpretation:** No-export produces no external transfer. A signed projection cannot claim unseen evidence was externally verified.

**Required evidence:** Original/projection manifest, verification profile, package digest and withheld markers.

**Missing/partial behavior:** Missing original/evidence or untrusted key => explicit unavailable/unverified or rejected according to purpose.

**Required fixtures:** Full/restricted/no export; tampering; stale package; wrong purpose; no public private-data logging.

**Owning stories:** E13.3.

## M33 - Coverage, determinism and performance acceptance

**Family / outcome:** Cross-cutting / Validation

**Inputs and scope:** All artifacts, capability records and corpus manifests

**Definition and calculation:** Per capability: evaluated eligible units / all eligible units; separately unknown/not-applicable/excluded/error. Runtime wall duration/peak RSS on declared host. Three-repeat semantic digest equality. Also record local health/progress/terminal states, hard deadlines/cancellation grace, peak output/disk usage and retention behavior. Freeze numerical bounds before affected qualification; failed/unrun checks are never recorded as PASS.

**Rule, threshold and interpretation:** Proposed initial tiers: <=10k eligible files 10min/2GiB; <=100k 30min/8GiB on 4vCPU. Measure/tune before publication; exceeding budget never silently truncates success.

**Required evidence:** Per-repo SHA/config/feed/hardware, counts, resource logs and semantic hashes.

**Missing/partial behavior:** Unknown denominator => coverage unknown. A survival run is not proof of analytical correctness.

**Required fixtures:** Dogfood; >=50 identified large repos; labeled flagship subset; resource exhaustion; corruption; repeat variation. SIGINT/SIGTERM/hard kill; disk full; output collision; concurrent reader; retention preserving active baseline; audit redaction.

**Owning stories:** E15.1, E15.2, E15.3.

**Report acceptance:** Per-capability coverage/freshness records defined above must survive JSON and HTML projection, including vulnerability-feed and Git-history reasons. Verify the visible report views in E11.2 and installed-artifact journeys in E11.3/P46 at G50; G40 verifies the delivered report projection and candidate-install smoke. A rendered healthy-looking empty table cannot substitute for explicit UNKNOWN or no-baseline behavior.

