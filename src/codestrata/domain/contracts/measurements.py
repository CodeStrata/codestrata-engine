"""M01-M33 entries adopted from the Measurement, Metrics & Evidence Contract."""

from __future__ import annotations

from codestrata.domain.contracts.models import MeasurementEntry


def _m(
    id: str,
    name: str,
    family: str,
    outcome_role: str,
    subject: str,
    inputs: tuple[str, ...],
    formula: str,
    evidence: tuple[str, ...],
    missing_data: str,
    fixtures: tuple[str, ...],
    owning_stories: tuple[str, ...],
    *,
    formula_version: str = "v1",
    notes: tuple[str, ...] = (),
) -> MeasurementEntry:
    return MeasurementEntry(
        id=id,
        name=name,
        family=family,
        outcome_role=outcome_role,
        subject=subject,
        inputs=inputs,
        formula=formula,
        formula_version=formula_version,
        evidence=evidence,
        missing_data=missing_data,
        fixtures=fixtures,
        owning_stories=owning_stories,
        opaque_score=False,
        notes=notes,
    )


MEASUREMENTS: tuple[MeasurementEntry, ...] = (
    _m(
        "M01",
        "Repository classification and scope",
        "inventory",
        "context",
        "repository file",
        ("source tree", "exclusions", "manifests"),
        (
            "Count files by mutually exclusive primary class "
            "source/test/config/infra/docs/generated/vendor/binary/unknown. "
            "supported_fraction = supported eligible files / eligible files. "
            "Ignored files remain in scope inventory. Zero eligible files => "
            "NOT_APPLICABLE."
        ),
        (
            "normalized relative path",
            "content digest",
            "classifier version",
            "ignore reason",
            "manifest location",
        ),
        "Unreadable or dynamic regions classified unknown; detection is not structural support.",
        (
            "mixed-language",
            "generated-vendor",
            "symlink-escape",
            "binary",
            "empty-repo",
            "unreadable-subtree",
        ),
        ("E05.1", "E05.2", "E05.3"),
    ),
    _m(
        "M02",
        "Technology, component and dependency inventory",
        "inventory",
        "context",
        "package/component declaration",
        ("manifests", "lockfiles", "source roots", "build configuration"),
        (
            "Distinct normalized technology/component records with evidence. "
            "Dependency counts by declared coordinate and separately by resolved "
            "package identity/version. Edges retain directness and resolution status."
        ),
        ("manifest/lock location", "ecosystem/package identity", "source roots", "parser version"),
        "Missing resolution is not zero dependencies; unsupported manifests UNKNOWN for depth.",
        (
            "maven-resolved",
            "npm-missing-lock",
            "composer-nuget-lower-tier",
            "workspace-packages",
            "duplicate-coordinates",
        ),
        ("E05.1", "E05.2", "E05.3"),
    ),
    _m(
        "M03",
        "Configured build and CI checks",
        "inventory",
        "context",
        "CI job/step",
        ("CI/build/config source",),
        (
            "For each configured job/step record literal or safely parsed command, "
            "condition, tool category and target. Count statically observed "
            "test/coverage/lint/security invocations."
        ),
        ("CI path/line", "literal command", "condition", "deterministic parser rule"),
        "Indirect scripts or unknown expressions are unresolved invocations, not absent checks.",
        (
            "direct-command",
            "conditional-job",
            "delegated-script",
            "no-ci",
            "malformed-yaml",
        ),
        ("E05.1", "E05.2", "E05.3"),
    ),
    _m(
        "M04",
        "API and configuration surfaces",
        "inventory",
        "context",
        "declared API/config surface",
        ("supported source AST", "config"),
        (
            "Distinct statically declared API entrypoints and config/deployment "
            "surfaces keyed by source subject and declaration kind."
        ),
        ("declaration symbol/path/line", "extraction capability"),
        "Dynamic routing or unsupported framework => UNKNOWN area; detection-only if available.",
        (
            "supported-route",
            "no-routes",
            "dynamic-route",
            "generated-config",
            "unresolved-framework",
        ),
        ("E05.2", "E05.3"),
    ),
    _m(
        "M05",
        "Module dependency cycles",
        "architecture",
        "architecture",
        "module SCC",
        ("resolved module graph",),
        (
            "Number of strongly connected components of size >1 plus single-node "
            "self-loops, each reported once, with member IDs and witness edges. "
            "Lower is favorable. FAIL when count > 0."
        ),
        ("observed module edges", "source locations", "SCC membership", "witness path"),
        (
            "Known cycle can FAIL despite unrelated unknown edges; "
            "absent cycle needs complete coverage."
        ),
        (
            "a-b-a",
            "acyclic-a-b",
            "self-loop",
            "unresolved-import",
            "reordered-traversal",
        ),
        ("E07.1", "E07.3"),
    ),
    _m(
        "M06",
        "Cross-module coupling",
        "architecture",
        "architecture",
        "module / file import edge",
        ("module import/depends_on graph", "component IDs"),
        (
            "Per module fan_in/out = distinct other modules using/used by it. "
            "File import-edge external-edge ratio = distinct eligible resolved "
            "file import edges whose endpoint component IDs differ / all eligible "
            "resolved file import edges with both endpoint component IDs known. "
            "Same-component edges stay in the denominator; duplicates excluded. "
            "Zero edges => NOT_APPLICABLE."
        ),
        ("module edge IDs", "denominator", "unresolved/unmapped exclusions", "coverage"),
        "Unresolved imports make counts a lower bound; no confident threshold PASS.",
        ("boundary-10-11", "duplicate-edges", "zero-edges", "unknown-imports"),
        ("E07.1", "E07.3"),
        notes=("revised_denominator_same_component_included",),
    ),
    _m(
        "M07",
        "Declared boundary and direction violations",
        "architecture",
        "architecture",
        "disallowed edge identity",
        ("module graph", "explicit local pattern configuration"),
        (
            "Count unique disallowed source-target edge identities against declared "
            "layer/module constraints. No declared pattern => NOT_APPLICABLE."
        ),
        ("constraint identity", "configured scope", "direct dependency witness"),
        "Unresolved relevant edge => UNKNOWN for unproven negative scope; never invent layers.",
        (
            "compliant-api-public",
            "violating-api-internal",
            "unresolved-import",
            "selector-rebinding",
        ),
        ("E07.2", "E07.3"),
    ),
    _m(
        "M08",
        "Component concentration",
        "architecture",
        "architecture",
        "component",
        ("eligible source files", "component mapping"),
        (
            "Per component: nonblank noncomment source lines / total such lines in "
            "scoped repository. Advisory above 0.60 only with >=2 components."
        ),
        ("line-count derivation", "component membership", "denominator"),
        "Unmapped or unreadable eligible files invalidate full-repo share; report partial.",
        ("share-60-61", "single-component", "unmapped-files", "generated-exclusion"),
        ("E07.2", "E07.3"),
    ),
    _m(
        "M09",
        "Structural centrality and reach",
        "architecture",
        "architecture",
        "graph node",
        ("versioned module/file graph",),
        (
            "centrality(v) = count of distinct incoming neighbors u in V with u != v "
            "/ max(1, |V|-1). Deduplicate parallel edges. Self-loops do not enter "
            "the numerator. Reach = unique nodes via chosen edge/direction/depth "
            "excluding seed. Descriptive only."
        ),
        ("seed", "edge types", "node set", "traversal depth/direction/cutoff"),
        "Unresolved edges or exhausted bound => lower-bound reach plus UNKNOWN completeness.",
        (
            "diamond-dedupe",
            "cycle-termination",
            "disconnected",
            "depth-cutoff",
            "singleton",
            "self-loop",
            "two-node-with-self-loop",
            "parallel-edges",
            "unknown-universe",
        ),
        ("E07.2", "E07.3"),
        notes=("self_loops_excluded_from_numerator",),
    ),
    _m(
        "M10",
        "Secret and private-key findings",
        "security",
        "security",
        "rule+subject+occurrence",
        ("supported source/config literal evidence",),
        (
            "Count unique rule + source-subject + occurrence findings after supported "
            "placeholder classification. Identity independent of raw secret bytes."
        ),
        ("path/line", "detector ID", "safe secret type", "redacted span"),
        (
            "Unsupported encoding/language prevents a clean claim; "
            "never scan full Git history by default."
        ),
        (
            "synthetic-valid-format-key",
            "placeholder",
            "encoded-unsupported",
            "duplicate-literal",
            "zero-raw-secret-canary",
        ),
        ("E06.1",),
    ),
    _m(
        "M11",
        "Insecure configuration findings",
        "security",
        "security",
        "named configuration condition",
        ("static TLS/auth/CORS/debug config",),
        (
            "Separate counts for disabled verification/auth, permissive CORS and "
            "debug production configuration; production context must be evidenced."
        ),
        ("config path/line/value classification", "context evidence"),
        "Unknown environment or indirect config => UNKNOWN context, not assumed production.",
        (
            "true-false-settings",
            "placeholder",
            "conditional-environment",
            "conflicting-configuration",
            "unsupported-expression",
        ),
        ("E06.1",),
    ),
    _m(
        "M12",
        "Resolved dependency and version hygiene",
        "security",
        "security",
        "declaration ID in one scope",
        ("manifest declarations", "available lock resolution"),
        (
            "resolution_coverage = fully resolved eligible declaration IDs / all "
            "eligible declaration IDs in the same manifest/workspace/environment "
            "scope. Count each declaration once. Known positive denominator with "
            "none resolved = 0 coverage. Unknown denominator = UNKNOWN. Zero "
            "eligible = NOT_APPLICABLE. Mutable/unbounded/unresolved/duplicate/"
            "conflicting counted separately."
        ),
        (
            "declaration and lock paths",
            "package coordinates",
            "direct/transitive dependency path",
        ),
        (
            "Unknown ecosystem/range resolution => UNKNOWN; "
            "never install packages to infer resolution."
        ),
        (
            "pinned-vs-wildcard",
            "duplicate-conflict",
            "lock-mismatch",
            "transitive-package",
            "unknown-version-scheme",
            "one-declaration-two-resolved",
            "partly-resolved",
            "zero-denominator",
            "unknown-denominator",
            "ratio-not-above-one",
        ),
        ("E06.2",),
        notes=("revised_same_scope_denominator",),
    ),
    _m(
        "M13",
        "Known vulnerability matches",
        "security",
        "security",
        "advisory alias-group + package/version",
        ("resolved package versions", "pinned vulnerability feed"),
        (
            "Count distinct canonical advisory alias-group + ecosystem/package/version "
            "identities; retain all dependency paths without multiplying finding count."
        ),
        (
            "advisory ID/aliases/range",
            "source snapshot digest/time",
            "resolved package/path",
        ),
        (
            "No fresh supported feed or no exact version => UNKNOWN matching. "
            "Zero matches is not secure."
        ),
        (
            "affected-unaffected",
            "withdrawn-advisory",
            "alias-dedupe",
            "prerelease-boundary",
            "stale-feed",
            "same-code-new-advisory",
        ),
        ("E06.2",),
    ),
    _m(
        "M14",
        "Deterministic license metadata and declared risk",
        "security",
        "security",
        "package license expression",
        ("resolved package license metadata", "explicit allow/deny configuration"),
        (
            "Count known SPDX-compatible license expressions and unknowns; evaluate "
            "only supported expression semantics against explicit configured policy."
        ),
        ("package/license source", "configured decision rule"),
        (
            "Missing/conflicting metadata or unsupported expression => UNKNOWN, "
            "not guessed allow/deny."
        ),
        (
            "allowed-denied",
            "dual-license",
            "malformed-expression",
            "missing-metadata",
            "conflict",
        ),
        ("E06.3",),
    ),
    _m(
        "M15",
        "Security classification quality",
        "security",
        "validation",
        "labeled finding group",
        ("labeled evaluable findings and negatives",),
        (
            "precision=TP/(TP+FP); recall=TP/(TP+FN); report TP/FP/FN/TN and UNKNOWN "
            "by rule group. Zero denominator is undefined, not 100%."
        ),
        ("label manifest", "result identities", "reviewer decisions"),
        (
            "Unsupported cases disclosed separately; unexplained UNKNOWN in "
            "supported cases blocks promotion."
        ),
        (
            "planted-keys-config-advisory",
            "safe-lookalikes",
            "hidden-holdout",
            "independent-label-review",
        ),
        ("E06.3",),
    ),
    _m(
        "M16",
        "Source size and function complexity",
        "quality",
        "quality",
        "function",
        ("supported AST", "source tokens"),
        (
            "cyclomatic v1 = 1 + count of declared branch constructs with the frozen "
            "language map. Also report physical nonblank noncomment lines."
        ),
        ("function identity/span", "counted branch locations", "formula version"),
        "Unparsed function => UNKNOWN metric; never a misleading cross-language fallback number.",
        (
            "straight-line",
            "if-loop-case-boolean",
            "nested-functions",
            "malformed-syntax",
            "threshold-boundaries",
        ),
        ("E08.1",),
    ),
    _m(
        "M17",
        "Maximum nesting depth",
        "quality",
        "quality",
        "function",
        ("supported AST",),
        "Maximum control-flow nesting depth per function under the declared construct map.",
        ("function/span", "maximum-depth witness constructs"),
        "Unknown parse sections invalidate a negative claim; absent functions => NOT_APPLICABLE.",
        ("depth-4-5", "nested-lambda-separation", "malformed-block", "language-specific-syntax"),
        ("E08.1",),
    ),
    _m(
        "M18",
        "Token clone indicator",
        "quality",
        "quality",
        "eligible source lines",
        ("normalized eligible source token streams",),
        (
            "Exact normalized token runs >=50 tokens spanning >=5 lines; merge overlaps "
            "before duplicated-line numerator / eligible source-line denominator."
        ),
        ("matched file spans", "normalization version", "merged numerator/denominator"),
        "Unsupported tokenization or scan cutoff => partial ratio / UNKNOWN full scope.",
        (
            "exact-clone",
            "renamed-identifier-policy",
            "overlapping-runs",
            "generated-exclusions",
            "no-eligible-lines",
        ),
        ("E08.1",),
    ),
    _m(
        "M19",
        "Test inventory and association",
        "quality",
        "quality",
        "production unit",
        ("test declarations", "imports", "configured conventions"),
        (
            "Test counts by framework; fraction of eligible production units with at "
            "least one supported static test association. Not runtime coverage."
        ),
        ("test declarations", "source-to-test association", "method/confidence"),
        "Unsupported framework or indirect generation => UNKNOWN association scope.",
        (
            "direct-reference",
            "convention-only",
            "no-tests",
            "generated-tests",
            "ambiguous-association",
        ),
        ("E08.2",),
    ),
    _m(
        "M20",
        "Skipped/disabled tests",
        "quality",
        "quality",
        "test identity",
        ("supported test source syntax",),
        "Count explicitly skipped/disabled tests, with static literal reason where present.",
        ("test identity", "annotation/call span", "static condition"),
        "Dynamic skip condition => unknown eligibility, not unconditional disabled.",
        (
            "explicit-disabled",
            "enabled",
            "conditional",
            "unsupported-decorator",
            "test-deletion",
        ),
        ("E08.2",),
    ),
    _m(
        "M21",
        "Configured test and coverage invocation gaps",
        "quality",
        "quality",
        "declared test/coverage capability",
        ("M03 CI observations", "test/coverage configuration"),
        (
            "Boolean/count of declared test/coverage capabilities with no statically "
            "observed invocation in supported CI/build scope."
        ),
        ("configured tool", "job command evidence", "checked scope"),
        "External workflow or uninspected script => UNKNOWN. No runtime pass/fail percentage.",
        (
            "declared-invoked",
            "declared-absent",
            "delegated-script",
            "conditional-job",
            "no-ci-applicability",
        ),
        ("E08.2",),
    ),
    _m(
        "M22",
        "Churn-weighted complexity hotspots",
        "quality",
        "maintainability",
        "component",
        ("M16", "M24 in same repository/window"),
        (
            "ranking_value = sum of supported function complexities in the component "
            "* component changed lines in the pinned M24 window. Sort descending, "
            "then stable component ID ascending. Complexity and churn are ranking; "
            "centrality, reach, ownership and active findings are context_only."
        ),
        (
            "complexity subjects",
            "commit/file churn",
            "component mapping",
            "priority explanation",
            "contributor coverage reasons",
        ),
        "Missing required complexity/history => UNKNOWN rank in a separate partial list.",
        (
            "same-complexity-different-churn",
            "zero-churn",
            "missing-history",
            "stable-ties",
            "rename-mapping",
            "complete-unified-record",
            "equal-rank-different-context",
            "missing-context-known-rank",
            "partial-ranking-input",
            "dangling-finding-rejection",
        ),
        ("E08.3",),
        notes=("ranking_versus_context_roles", "no_hidden_weights"),
    ),
    _m(
        "M23",
        "Dependency staleness and concern ordering",
        "quality",
        "maintainability",
        "resolved package / finding",
        ("permitted pinned release-date metadata", "M10-M22", "pinned evaluation_time"),
        (
            "staleness_days = evaluation_time - installed-version publication_time. "
            "Finding-concern tuple: effective severity, valid evidence class, "
            "comparable hotspot, stable finding ID. No weighted overall score. "
            "Incomparable hotspot values sort after comparable ones, then finding ID."
        ),
        ("version/date source snapshot", "explicit evaluation_time", "ordering contributors"),
        "No release-date metadata => UNKNOWN age. Assessment date must be pinned.",
        (
            "known-old-new",
            "unknown-date",
            "future-invalid-timestamp",
            "identical-severity-ties",
            "changed-metadata-snapshot",
        ),
        ("E08.3",),
    ),
    _m(
        "M24",
        "Churn and recency",
        "git",
        "cross_cutting",
        "file/component",
        ("pinned local Git history", "rename policy"),
        (
            "Per file/component sum of added+deleted text lines in included commits. "
            "Recency uses pinned UTC evaluation_time and latest valid included commit "
            "time. v1 profile: all non-merge commits reachable from pinned head, "
            "committer timestamp within last 180 days then latest 1000, ordered "
            "timestamp descending then SHA. Root commits vs empty tree. Merge-only "
            "conflict-resolution edits excluded and disclosed. Bug-fix markers are "
            "contextual and never proven defect counts."
        ),
        ("commit SHA/time", "numstat", "rename map", "exact window"),
        "Shallow/absent history => partial/UNKNOWN; binary churn unknown.",
        (
            "known-edits",
            "rename",
            "merge",
            "binary",
            "shallow-history",
            "window-boundary",
            "merge-only-integration",
            "squash",
            "merge-conflict-only",
            "future-timestamp",
            "positive-misleading-bugfix-marker",
        ),
        ("E09.2", "E09.3"),
        notes=("history_profile_v1", "message_markers_not_defects"),
    ),
    _m(
        "M25",
        "Repository, component and file ownership concentration",
        "git",
        "cross_cutting",
        "repository|component|file",
        ("same bounded history", "explicit mailmap policy"),
        (
            "largest_share = max(contributor changed lines) / total attributable "
            "changed lines at that scope. Also count contributors needed to reach "
            ">=50% cumulative share. Do not average file ratios to obtain a "
            "component ratio. Sort contributors by lines desc, then stable identity."
        ),
        (
            "repository-local identity mapping",
            "commit contributions",
            "scope-specific denominator",
            "unattributed coverage",
        ),
        "Zero attributable churn => NOT_APPLICABLE; truncated history is partial-window.",
        (
            "two-contributors",
            "mailmap-alias",
            "zero-lines",
            "missing-identities",
            "declared-bots",
            "different-scope-concentrations",
            "weighted-component-aggregation",
            "file-rename-ambiguous",
            "shallow-history-scope-denominators",
        ),
        ("E09.2", "E09.3"),
        notes=("scoped_denominators",),
    ),
    _m(
        "M26",
        "Temporal co-change",
        "git",
        "cross_cutting",
        "file/component pair",
        ("included commits to file/component incidence",),
        (
            "For pair A,B: cochanged commit count / union commits touching A or B "
            "(Jaccard). Support >=3 cochanged commits to label a supported relation."
        ),
        ("commit IDs", "member files/components", "support", "union denominator"),
        "Incomplete window is a qualified observation; support < 3 is insufficient support.",
        (
            "always-together",
            "unrelated",
            "exactly-3-support",
            "bulk-formatting-commit",
            "shallow-history",
        ),
        ("E09.2", "E09.3"),
    ),
    _m(
        "M27",
        "Change size, spread and test touch",
        "git",
        "cross_cutting",
        "explicit change set",
        ("working/index/base-head/patch inputs", "optional supplied PR context"),
        (
            "Count changed text lines, files and mapped components. test_touch is "
            "whether the changed set contains known test/config-test units. Optional "
            "PR context is a bounded record with provenance/digest; narrative-only "
            "changes leave canonical analysis identical. Boundary-spread uses declared "
            "M07 membership when available; missing declarations are UNKNOWN not zero."
        ),
        ("diff hunks", "state digests", "file classes", "component IDs", "context digest"),
        "Unresolvable patch base or binary changes preserve partial size; no hosted lookup.",
        (
            "staged-vs-working",
            "rename",
            "add-delete",
            "binary",
            "patch-missing-base",
            "test-only-diff",
            "absent-pr-metadata",
            "valid-pr-metadata",
            "oversized-malformed-pr",
            "injection-text",
            "sha-conflict",
            "context-only-change",
            "telemetry-exclusion",
        ),
        ("E09.1", "E09.3"),
        notes=("supplied_context_untrusted",),
    ),
    _m(
        "M28",
        "Finding lifecycle and metric delta",
        "change",
        "all_four_outcomes",
        "matched finding / named metric",
        ("two explicit compatible canonical states",),
        (
            "Match by versioned stable rule/subject/evidence occurrence identity. "
            "Metric delta = candidate-base with pinned units/scope. Binary remaining "
            "violations are unchanged. Severity overrides are configuration, not source fixes."
        ),
        (
            "both artifact digests",
            "matching rule version",
            "evidence pair",
            "compatibility reasons",
        ),
        "Incompatible rules/coverage/identity => UNKNOWN, never synthetic resolution.",
        (
            "stable",
            "fixed",
            "new",
            "message-only",
            "rename",
            "coverage-loss",
            "policy-severity-change",
            "reduced-magnitude-still-violating",
            "binary-persistence",
            "severity-only-override",
            "unknown-comparator",
        ),
        ("E10.1", "E10.3"),
    ),
    _m(
        "M29",
        "Graph delta and static blast radius",
        "change",
        "architecture",
        "changed subject / affected subgraph",
        ("two compatible graphs", "changed subjects", "M07 membership", "M22/M24 context"),
        (
            "Sets of added/removed nodes/edges under stable IDs. Impact = changed seed "
            "plus unique reverse reachable dependents at configured edge/depth. "
            "crossed_boundary_count = distinct ordered pairs of declared boundary-member "
            "IDs joined by observed dependency edges in the bounded affected subgraph. "
            "Change-concern class uses high-churn and high-centrality predicates without "
            "a composite score. Default context_only."
        ),
        (
            "graph IDs",
            "edge witnesses",
            "seed list",
            "traversal limit",
            "test links",
            "boundary pair IDs",
        ),
        "Unresolved edges/cutoff => lower-bound impact; missing boundary/tests UNKNOWN not zero.",
        (
            "diamond",
            "cycles",
            "file-deletion",
            "rename",
            "missing-edge",
            "bound-cutoff",
            "high-churn-centrality-vs-ordinary",
            "unchanged-hotspot",
            "missing-history",
            "stable-ties",
            "no-declared-boundaries",
            "repeated-edges-same-pair",
            "exact-zero-vs-unavailable-tests",
        ),
        ("E10.2", "E10.3"),
        notes=("explicit_boundary_definitions", "context_only_predicate"),
    ),
    _m(
        "M30",
        "Thresholded outcome movement",
        "change",
        "all_four_outcomes",
        "outcome (architecture/security/quality/maintainability)",
        ("compatible metric/finding deltas", "launch driver manifest"),
        (
            "Qualifying change: strict delta beyond versioned threshold. Counts "
            "epsilon 0; ratios epsilon 0.01 absolute. Advisory metrics excluded unless "
            "configured. Classify Insufficient > Mixed > Deteriorated > Improved > "
            "Stable. Empty or entirely disabled/exempt driver sets are NOT_APPLICABLE, "
            "never healthy/Stable."
        ),
        (
            "qualifying drivers",
            "excluded contextual metrics",
            "threshold profile",
            "both coverages",
        ),
        "First run/no baseline => Insufficient/no comparison. Known partial deltas may display.",
        (
            "all-unchanged",
            "only-improvement",
            "only-deterioration",
            "mixed",
            "coverage-drop",
            "exact-epsilon-boundary",
            "empty-outcome",
            "disabled-all-scope",
            "known-violation-partial-coverage",
            "catalog-driver-mapping",
        ),
        ("E10.2", "E10.3"),
        notes=("outcome_driver_manifest",),
    ),
    _m(
        "M31",
        "Cause attribution",
        "change",
        "security_and_other",
        "comparison pair",
        ("input/Engine/rule/config/feed digests", "optional controlled paired reruns"),
        (
            "Source-only, feed-only, configuration-only, mixed or undetermined. Multiple "
            "changed dimensions require controlled equivalent-input comparisons."
        ),
        ("changed input dimensions", "controlled rerun references if performed"),
        "Lack of controlled evidence => mixed/undetermined, never a guessed dominant cause.",
        (
            "same-code-new-cve",
            "dependency-fix-same-feed",
            "severity-override",
            "source-and-feed-changed",
        ),
        ("E10.2", "E10.3"),
    ),
    _m(
        "M32",
        "Export and trust provenance",
        "cross_cutting",
        "trust",
        "canonical artifact / projection",
        ("canonical artifacts", "selected export profile"),
        (
            "Original canonical digest preserved. Exported projection lists original "
            "digest, allowed/withheld categories, export-policy version and separate "
            "signature metadata."
        ),
        (
            "original/projection manifest",
            "verification profile",
            "package digest",
            "withheld markers",
        ),
        "Missing original/evidence or untrusted key => unavailable/unverified/rejected by purpose.",
        (
            "full-export",
            "restricted-export",
            "no-export",
            "tampering",
            "stale-package",
            "wrong-purpose",
            "no-public-private-data-logging",
        ),
        ("E13.3",),
    ),
    _m(
        "M33",
        "Coverage, determinism and performance acceptance",
        "cross_cutting",
        "validation",
        "capability / corpus run",
        ("all artifacts", "capability records", "corpus manifests"),
        (
            "Per capability: evaluated eligible units / all eligible units; separately "
            "unknown/not-applicable/excluded/error. Three-repeat semantic digest "
            "equality. Record local health/progress/terminal, hard deadlines, "
            "cancellation grace, peak output/disk and retention."
        ),
        (
            "per-repo SHA/config/feed/hardware",
            "counts",
            "resource logs",
            "semantic hashes",
            "per-capability coverage/freshness",
        ),
        "Unknown denominator => coverage unknown. A survival run is not analytical correctness.",
        (
            "dogfood",
            "fifty-large-repos",
            "labeled-flagship",
            "resource-exhaustion",
            "corruption",
            "repeat-variation",
            "sigint-sigterm-hard-kill",
            "disk-full",
            "output-collision",
            "concurrent-reader",
            "retention-active-baseline",
            "audit-redaction",
        ),
        ("E15.1", "E15.2", "E15.3"),
    ),
)
