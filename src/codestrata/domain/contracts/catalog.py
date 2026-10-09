"""Assemble and load the E01.1 launch ratification."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib import resources
from pathlib import Path

import yaml

from codestrata.domain.contracts.enums import (
    ContributorRole,
    DepthTier,
    DriverKind,
    OutcomeFamily,
)
from codestrata.domain.contracts.formula_fixtures import FORMULA_FIXTURES
from codestrata.domain.contracts.identity import (
    CONFIDENCE_MAP,
    LAUNCH_RULE_IDS,
    RULE_ID_GRAMMAR,
    SEVERITY_POLICY,
)
from codestrata.domain.contracts.measurements import MEASUREMENTS
from codestrata.domain.contracts.models import (
    BudgetLimits,
    CoverageFreshnessReason,
    FeedPolicy,
    HistoryProfile,
    LanguageDepthPin,
    LaunchRatification,
    M22Roles,
    M29Predicate,
    NoOpaqueScore,
    OutcomeDriver,
)

RATIFICATION_ID = "e01.1-launch-ratification"
RATIFICATION_VERSION = "1.0.0"
PACKAGE_REVISION = "ENGINE-2026-09-15-R1"
CONTRACT_VERSION = "1.2"

RESOURCE_PACKAGE = "codestrata.resources.contracts"
RESOURCE_NAME = "launch-ratification-v1.yaml"


def build_launch_ratification() -> LaunchRatification:
    return LaunchRatification(
        ratification_id=RATIFICATION_ID,
        package_revision=PACKAGE_REVISION,
        contract_version=CONTRACT_VERSION,
        proposed_by="Abhinav (Engineer A)",
        independent_reviewer="Sangram Gaikwad (accepted 2026-09-19; Cursor cannot self-ratify)",
        reviewer_status="accepted",
        no_opaque_score=NoOpaqueScore(
            canonical_health_score=False,
            compatibility_numeric_requires_published_formula=True,
            unpublished_derivation="unavailable/UNKNOWN, never a fabricated number",
        ),
        measurements=MEASUREMENTS,
        depth_matrix=_depth_matrix(),
        feed=_feed(),
        history=_history(),
        budgets=_budgets(),
        coverage_freshness_reasons=_freshness_reasons(),
        confidence_map=CONFIDENCE_MAP,
        severity=SEVERITY_POLICY,
        rule_id_grammar=RULE_ID_GRAMMAR,
        outcome_drivers=_outcome_drivers(),
        m22_roles=M22Roles(
            ranking_value="sum(supported function complexity) * component changed lines",
            ranking_contributors=("complexity", "churn"),
            context_only_contributors=(
                "centrality",
                "reach",
                "ownership",
                "active_finding_references",
            ),
            tie_break="stable component ID ascending",
            missing_required="UNKNOWN rank in separately identified partial list by subject ID",
            contextual_missing_does_not_invalidate_rank=True,
            no_hidden_weights=True,
        ),
        m29_predicate=M29Predicate(
            high_churn=(
                "changed_lines > 0 and changed_lines > nearest-rank p90 of components "
                "with >0 churn in the same pinned M24 window"
            ),
            high_centrality=("M09 centrality(v) > nearest-rank p90 of the comparable universe V"),
            ranking=(
                "class both > churn-only > centrality-only > ordinary; then more "
                "changed lines; then higher centrality; then subject ID. No weighted score."
            ),
            default_role="context_only",
            verdict_requires_yaml=True,
            no_composite_score=True,
        ),
        formula_fixtures=FORMULA_FIXTURES,
        retained_existing_rule_ids=LAUNCH_RULE_IDS,
    )


def _depth_matrix() -> tuple[LanguageDepthPin, ...]:
    promotion = (
        "File detection is not structural support. Promote a syntax/framework only "
        "after parser/version evidence and fixtures. JS/TS complexity is currently "
        "unsupported and stays UNKNOWN until E08.1 lands a mapped extractor."
    )
    return (
        LanguageDepthPin(
            language="java",
            launch_tier=DepthTier.DEEPEST_TARGET,
            detection=True,
            structural="launch deepest path; current inventory PARTIAL package/Spring-JPA",
            complexity=(
                "launch deepest path; current inventory PARTIAL brace-aware regex, not javac"
            ),
            frameworks="jpa, spring-web structural patterns only",
            current_verified="PARTIAL structural and PARTIAL complexity (E05.1 pin)",
            promotion_rule=promotion,
        ),
        LanguageDepthPin(
            language="javascript",
            launch_tier=DepthTier.DEEPEST_TARGET,
            detection=True,
            structural="launch deepest path with TypeScript via the JS provider",
            complexity="required for deepest launch quality; currently no extractor (UNKNOWN)",
            frameworks="react detection-listed, not structural",
            current_verified="PARTIAL imports; complexity unsupported (E05.1 pin)",
            promotion_rule=promotion,
        ),
        LanguageDepthPin(
            language="typescript",
            launch_tier=DepthTier.DEEPEST_TARGET,
            detection=True,
            structural="served by javascript provider",
            complexity="same as javascript; currently unsupported",
            frameworks="same as javascript",
            current_verified="detected; structurally JS provider",
            promotion_rule=promotion,
        ),
        LanguageDepthPin(
            language="python",
            launch_tier=DepthTier.VERIFIED_RETAINED,
            detection=True,
            structural="retain verified PARTIAL package-path / TYPE_CHECKING imports",
            complexity="retain verified stdlib AST; do not silently match Java/JS launch depth",
            frameworks="none structural (django/flask/fastapi unsupported)",
            current_verified="PARTIAL (E05.1 pin)",
            promotion_rule=promotion,
        ),
        LanguageDepthPin(
            language="php",
            launch_tier=DepthTier.VERIFIED_RETAINED,
            detection=True,
            structural="retain verified use/require/include units",
            complexity="retain verified existing complexity provider",
            frameworks="codeigniter/laminas/laravel/symfony as currently evidenced",
            current_verified="PARTIAL (E05.1 pin)",
            promotion_rule=promotion,
        ),
        LanguageDepthPin(
            language="csharp",
            launch_tier=DepthTier.VERIFIED_RETAINED,
            detection=True,
            structural="retain verified using/using-static units; no Roslyn",
            complexity="retain verified existing complexity provider",
            frameworks="aspnet/efcore/wcf as currently evidenced",
            current_verified="PARTIAL (E05.1 pin)",
            promotion_rule=promotion,
        ),
    )


def _feed() -> FeedPolicy:
    return FeedPolicy(
        provider_id="osv.dev",
        provider_name="OSV (osv-vulnerabilities snapshot)",
        cache_kind="versioned offline cache of published OSV records; no live fetch during assess",
        redistribution=(
            "Use the published OSV data license/terms on the pinned snapshot. "
            "Do not scrape NVD HTML. Redistribute only the snapshot Engine is licensed to ship."
        ),
        range_semantics=(
            "OSV affected.ranges: ECOSYSTEM and SEMVER as declared per ecosystem; "
            "GIT ranges only when the assessed repository commit is the OSV GIT repo. "
            "Alias groups use OSV aliases. Withdrawn records do not count as matches."
        ),
        freshness_max_age_days=7,
        evaluation_time_binding=(
            "pinned evaluation_time; age = evaluation_time - feed publication/update time"
        ),
        silent_online_fallback=False,
        unavailable_behavior=(
            "M13 matching scope UNKNOWN; remainder of the offline assessment continues. "
            "Cannot prove a clean vulnerability result."
        ),
        stale_behavior=(
            "Emit stale freshness; cached observed matches remain qualified; no clean claim."
        ),
        license_metadata=(
            "License and release-date facts use permitted deterministic metadata only; "
            "absence remains UNKNOWN. No registry install."
        ),
    )


def _history() -> HistoryProfile:
    return HistoryProfile(
        profile_id="git.history.reachable-non-merge-180d-1000",
        version="v1",
        traversal="all non-merge commits reachable from the pinned head",
        merge_policy=(
            "Exclude merge commits. Disclose merge-only conflict-resolution edits. "
            "Do not combine first-parent-only traversal with skipping merges. A "
            "first-parent-diff profile is a different version."
        ),
        window_days=180,
        max_commits=1000,
        order="committer timestamp descending, then SHA ascending",
        root_diff="root commits compare to the empty tree; others to their sole parent",
        future_timestamp="invalid for recency; disclose and exclude from recency numerator",
        rename_policy=(
            "Git rename mapping when the pinned history records it; ambiguous stays unknown"
        ),
        mailmap_policy=(
            "apply repository .mailmap when present; unlabeled bots are ordinary identities"
        ),
        bugfix_markers=(
            r"\bfix(?:es|ed)?\b",
            r"\bbugfix\b",
            r"\bhotfix\b",
            r"\bresolve[sd]?\b",
        ),
        bugfix_markers_are_proven_defects=False,
    )


def _budgets() -> BudgetLimits:
    return BudgetLimits(
        yaml_document_bytes=1_048_576,
        yaml_max_nesting=32,
        yaml_aliases_enabled=False,
        ruleset_parent_depth=8,
        max_effective_rules=1_000,
        graph_max_depth=32,
        graph_default_impact_depth=4,
        graph_max_visited_nodes=100_000,
        graph_max_visited_edges=500_000,
        rule_soft_budget_seconds=5,
        rule_hard_deadline_seconds=15,
        cancellation_grace_seconds=2,
        regex_match_timeout_milliseconds=100,
        regex_max_steps=1_000_000,
        max_source_file_bytes=10_485_760,
        max_memory_rss_bytes_tier_10k=2 * 1024**3,
        max_memory_rss_bytes_tier_100k=8 * 1024**3,
        max_output_artifact_bytes=268_435_456,
        wall_seconds_tier_10k=600,
        wall_seconds_tier_100k=1800,
        process_enforced_hard_cap=True,
        cooperative_callback_only_forbidden=True,
    )


def _freshness_reasons() -> tuple[CoverageFreshnessReason, ...]:
    return (
        CoverageFreshnessReason(
            code="feed_missing",
            applies_to="vulnerability",
            meaning="No pinned feed snapshot is present.",
        ),
        CoverageFreshnessReason(
            code="feed_stale",
            applies_to="vulnerability",
            meaning="Feed age exceeds seven days at pinned evaluation_time.",
        ),
        CoverageFreshnessReason(
            code="feed_unsupported",
            applies_to="vulnerability",
            meaning="Ecosystem or range type is outside the ratified OSV profile.",
        ),
        CoverageFreshnessReason(
            code="git_history_missing",
            applies_to="git",
            meaning="No usable local Git history for the requested window.",
        ),
        CoverageFreshnessReason(
            code="git_history_shallow",
            applies_to="git",
            meaning="Shallow or truncated history; full-window measurement UNKNOWN.",
        ),
        CoverageFreshnessReason(
            code="git_window_partial",
            applies_to="git",
            meaning="Included commits exist but the 180-day/1000-commit bound cut off coverage.",
        ),
        CoverageFreshnessReason(
            code="unknown_denominator",
            applies_to="coverage",
            meaning="Eligible unit count is unknown; never emit 0% or 100%.",
        ),
        CoverageFreshnessReason(
            code="not_time_sensitive",
            applies_to="freshness",
            meaning="Capability has no time-sensitive source; freshness NOT_APPLICABLE.",
            cannot_prove_clean=False,
        ),
        CoverageFreshnessReason(
            code="source_time_missing",
            applies_to="freshness",
            meaning="Missing source publication time; do not use report generation time.",
        ),
        CoverageFreshnessReason(
            code="no_baseline",
            applies_to="comparison",
            meaning="First run; delta and outcome movement unavailable.",
        ),
    )


def _d(
    id: str,
    kind: DriverKind,
    family: OutcomeFamily,
    role: str,
    applicability: str,
    direction: str,
    unit: str,
    epsilon: str,
    coverage: str,
    empty: str,
    contributor_role: ContributorRole | None = None,
) -> OutcomeDriver:
    return OutcomeDriver(
        id=id,
        kind=kind,
        family=family,
        outcome_or_context_role=role,
        applicability=applicability,
        direction=direction,
        comparison_unit=unit,
        epsilon=epsilon,
        coverage_requirement=coverage,
        empty_scope=empty,
        contributor_role=contributor_role,
    )


def _outcome_drivers() -> tuple[OutcomeDriver, ...]:
    complete = "complete applicable evidence required for PASS/Stable"
    empty = "NOT_APPLICABLE, never healthy"
    return (
        _d(
            "architecture.dependency-cycle",
            DriverKind.RULE,
            OutcomeFamily.ARCHITECTURE,
            "outcome_driver",
            "resolved module graph",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "architecture.invalid-dependency-direction",
            DriverKind.RULE,
            OutcomeFamily.ARCHITECTURE,
            "outcome_driver",
            "declared direction constraints",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "architecture.layer-boundary-violation",
            DriverKind.RULE,
            OutcomeFamily.ARCHITECTURE,
            "outcome_driver",
            "declared M07 patterns",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "architecture.excessive-cross-module-coupling",
            DriverKind.RULE,
            OutcomeFamily.ARCHITECTURE,
            "outcome_driver",
            "module fan_out vs threshold 10",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "architecture.framework-leakage",
            DriverKind.RULE,
            OutcomeFamily.ARCHITECTURE,
            "outcome_driver",
            "supported framework usage vs declared boundary",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "architecture.component-concentration",
            DriverKind.METRIC,
            OutcomeFamily.ARCHITECTURE,
            "advisory",
            ">=2 components",
            "descriptive",
            "ratio",
            "0.01",
            "partial share allowed with coverage",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "M09.centrality",
            DriverKind.METRIC,
            OutcomeFamily.ARCHITECTURE,
            "context",
            "complete universe V",
            "descriptive",
            "ratio",
            "0.01",
            "partial universe cannot prove exact centrality",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "security.private-key-material",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "supported source/config literals",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.credential-literal",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "supported source/config literals",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.placeholder-credential",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "context",
            "supported placeholders",
            "descriptive",
            "count",
            "0",
            "placeholders are hygiene signals",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "security.tls-verification-disabled",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "evidenced production-relevant config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.hostname-verification-disabled",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "evidenced production-relevant config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.authentication-disabled",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "evidenced production-relevant config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.permissive-cors-origin",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "evidenced production-relevant config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "security.debug-enabled",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "evidenced production-relevant config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "dependency.unresolved-version",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "eligible declarations",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "dependency.mutable-version",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "eligible declarations",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "dependency.unbounded-requirement",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "eligible declarations",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "dependency.conflicting-exact-versions",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "eligible declarations",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "dependency.duplicate-declaration",
            DriverKind.RULE,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "eligible declarations",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "M13.known_vulnerability",
            DriverKind.METRIC,
            OutcomeFamily.SECURITY,
            "outcome_driver",
            "resolved versions plus fresh pinned OSV snapshot",
            "lower_count_favorable",
            "count",
            "0",
            "fresh supported feed required; else UNKNOWN not clean",
            empty,
        ),
        _d(
            "technical_debt.excessive-branching",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported AST complexity map",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "technical_debt.large-callable",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported AST size map",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "technical_debt.deep-nesting",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported AST nesting map",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "technical_debt.excessive-parameters",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported AST parameter map",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "technical_debt.oversized-type",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported AST type-size map",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "testing.test-001",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "supported test syntax",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "testing.test-002",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "advisory",
            "unconfirmed test candidates",
            "descriptive",
            "count",
            "0",
            "candidates are not measured runtime coverage",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "testing.test-003",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "declared tests without observation",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "testing.test-005",
            DriverKind.RULE,
            OutcomeFamily.QUALITY,
            "outcome_driver",
            "complete supported CI config",
            "lower_count_favorable",
            "count",
            "0",
            complete,
            empty,
        ),
        _d(
            "M18.clone_indicator",
            DriverKind.METRIC,
            OutcomeFamily.QUALITY,
            "advisory",
            "supported tokenization",
            "lower_ratio_favorable",
            "ratio",
            "0.01",
            "partial ratio cannot prove full-scope cleanliness",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "M22.hotspot",
            DriverKind.METRIC,
            OutcomeFamily.MAINTAINABILITY,
            "context",
            "complete complexity and M24 history",
            "descriptive",
            "count",
            "0",
            "partial records excluded from comparable ranking",
            empty,
            ContributorRole.RANKING,
        ),
        _d(
            "M25.ownership_concentration",
            DriverKind.METRIC,
            OutcomeFamily.MAINTAINABILITY,
            "context",
            "attributable churn at that scope",
            "descriptive",
            "ratio",
            "0.01",
            "scope-specific denominator; do not average file ratios",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
        _d(
            "M29.change_concern",
            DriverKind.METRIC,
            OutcomeFamily.ARCHITECTURE,
            "context",
            "changed subjects plus comparable churn/centrality",
            "descriptive",
            "class",
            "n/a",
            "partial contributors visible; no verdict unless YAML maps it",
            empty,
            ContributorRole.CONTEXT_ONLY,
        ),
    )


def dump_payload(ratification: LaunchRatification) -> dict[str, object]:
    return ratification.model_dump(mode="json")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_yaml_bytes(ratification: LaunchRatification | None = None) -> bytes:
    payload = dump_payload(ratification or build_launch_ratification())
    text = yaml.safe_dump(payload, sort_keys=True, allow_unicode=False)
    return text.replace("\r\n", "\n").encode("utf-8")


@lru_cache(maxsize=1)
def load_launch_ratification() -> LaunchRatification:
    return build_launch_ratification()


def packaged_yaml_path() -> Path:
    return Path(str(resources.files(RESOURCE_PACKAGE).joinpath(RESOURCE_NAME)))


def docs_yaml_path(engine_root: Path) -> Path:
    return engine_root / "docs" / "contracts" / "launch-ratification-v1.yaml"
