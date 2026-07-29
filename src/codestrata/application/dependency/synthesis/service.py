"""Deterministic Dependency synthesis from assessment inventory (Phase 4.4.5).

Consumes DependencyAssessmentSection inventory projections only. Does not
reparse manifests, recollect evidence, or reevaluate hygiene rules.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.domain.dependency.assessment.enums import (
    DependencyAssessmentStatus,
    DependencySourceRole,
)
from codestrata.domain.dependency.assessment.models import (
    DependencyAggregationInventory,
    DependencyDeclarationInventory,
    DependencyDiagnosticsSummary,
    DependencyEvidenceSummary,
    DependencyFindingReference,
    DependencyHotspotInventory,
    DependencyManifestInventory,
)
from codestrata.domain.dependency.ids import (
    HYGIENE_RULE_IDS,
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.dependency.synthesis.enums import (
    DependencyConclusionAudience,
    DependencyConclusionKind,
    DependencyRecommendationKind,
    DependencySynthesisStatus,
    DependencyThemeKind,
    DependencyThemeScope,
)
from codestrata.domain.dependency.synthesis.identifiers import (
    MANIFEST_FINDING_CONCENTRATION_MIN_SHARE,
    PLUGIN_SHARE_MIN_FOR_THEME,
    POLICY_CONFLICTING,
    POLICY_DECLARED_ONLY,
    POLICY_DISABLED,
    POLICY_DUPLICATE,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_MUTABLE,
    POLICY_NO_PRODUCTION,
    POLICY_PRODUCTION_PARTIAL,
    POLICY_PRODUCTION_PRESENT,
    POLICY_TEST_FIXTURE,
    POLICY_UNBOUNDED,
    POLICY_UNRESOLVED,
    POLICY_UNSUPPORTED_ECOSYSTEM,
    POLICY_UNSUPPORTED_RESOLUTION,
    SYNTHESIS_VERSION,
    build_concentration_fact_id,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.dependency.synthesis.models import (
    DependencyConcentrationFact,
    DependencyConclusion,
    DependencyRecommendation,
    DependencySynthesisResult,
    DependencyTheme,
)

_RULE_THEME_KIND: dict[str, DependencyThemeKind] = {
    RULE_UNRESOLVED_VERSION: DependencyThemeKind.UNRESOLVED_VERSIONS,
    RULE_MUTABLE_VERSION: DependencyThemeKind.MUTABLE_VERSION_USAGE,
    RULE_UNBOUNDED_REQUIREMENT: DependencyThemeKind.UNBOUNDED_PYTHON_REQUIREMENTS,
    RULE_CONFLICTING_EXACT_VERSIONS: DependencyThemeKind.CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION: DependencyThemeKind.DUPLICATE_DECLARATIONS,
}

_RULE_TITLES: dict[str, str] = {
    RULE_UNRESOLVED_VERSION: "Unresolved versions",
    RULE_MUTABLE_VERSION: "Mutable version declarations",
    RULE_UNBOUNDED_REQUIREMENT: "Unbounded Python requirements",
    RULE_CONFLICTING_EXACT_VERSIONS: "Conflicting exact versions",
    RULE_DUPLICATE_DECLARATION: "Duplicate declarations",
}

_RULE_CONCLUSION: dict[str, tuple[DependencyConclusionKind, str]] = {
    RULE_UNRESOLVED_VERSION: (
        DependencyConclusionKind.UNRESOLVED_VERSIONS_PRESENT,
        POLICY_UNRESOLVED,
    ),
    RULE_MUTABLE_VERSION: (
        DependencyConclusionKind.MUTABLE_VERSIONS_PRESENT,
        POLICY_MUTABLE,
    ),
    RULE_UNBOUNDED_REQUIREMENT: (
        DependencyConclusionKind.UNBOUNDED_REQUIREMENTS_PRESENT,
        POLICY_UNBOUNDED,
    ),
    RULE_CONFLICTING_EXACT_VERSIONS: (
        DependencyConclusionKind.CONFLICTING_EXACT_VERSIONS_PRESENT,
        POLICY_CONFLICTING,
    ),
    RULE_DUPLICATE_DECLARATION: (
        DependencyConclusionKind.DUPLICATE_DECLARATIONS_PRESENT,
        POLICY_DUPLICATE,
    ),
}

_RULE_RECOMMENDATION: dict[
    str, tuple[DependencyRecommendationKind, str, str, str]
] = {
    RULE_UNRESOLVED_VERSION: (
        DependencyRecommendationKind.DEFINE_UNRESOLVED_LOCAL_VERSION,
        "define-unresolved-local-version",
        "Define proven-unresolved local version expressions",
        (
            "If resolving declared-version hygiene is in scope, define the missing "
            "local property or pin so the version expression is repository-provable."
        ),
    ),
    RULE_MUTABLE_VERSION: (
        DependencyRecommendationKind.REPLACE_MUTABLE_VERSION_DECLARATION,
        "replace-mutable-version-declaration",
        "Replace mutable version declarations",
        (
            "If stabilizing declared versions is in scope, replace SNAPSHOT/dynamic/"
            "mutable markers with exact declared versions in the referenced manifests."
        ),
    ),
    RULE_UNBOUNDED_REQUIREMENT: (
        DependencyRecommendationKind.CONSTRAIN_PYTHON_REQUIREMENT,
        "constrain-python-requirement",
        "Constrain unbounded Python requirements",
        (
            "If tightening Python requirement bounds is in scope, add an upper or "
            "exact constraint for the referenced unbounded declarations."
        ),
    ),
    RULE_CONFLICTING_EXACT_VERSIONS: (
        DependencyRecommendationKind.RECONCILE_CONFLICTING_EXACT_VERSIONS,
        "reconcile-conflicting-exact-versions",
        "Reconcile conflicting exact versions",
        (
            "If aligning declared versions is in scope, reconcile conflicting exact "
            "version pins for the same identity across referenced manifests."
        ),
    ),
    RULE_DUPLICATE_DECLARATION: (
        DependencyRecommendationKind.REMOVE_DUPLICATE_DECLARATIONS,
        "remove-duplicate-declarations",
        "Remove duplicate declarations",
        (
            "If cleaning declaration hygiene is in scope, remove or consolidate "
            "duplicate declarations for the same identity in the referenced manifests."
        ),
    ),
}

_FINDING_REF_LIMIT = 32
_HOTSPOT_REF_LIMIT = 16
_MANIFEST_REF_LIMIT = 16
_DIAGNOSTIC_REF_LIMIT = 16


def _pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: DependencyConclusionKind,
    audience: DependencyConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    source_role: DependencySourceRole,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    hotspot_ids: Sequence[str] = (),
    manifest_inventory_ids: Sequence[str] = (),
    diagnostic_ids: Sequence[str] = (),
    concentration_fact_ids: Sequence[str] = (),
    metadata: dict[str, str] | None = None,
) -> DependencyConclusion:
    support = (
        tuple(theme_ids)
        + tuple(finding_ids)
        + tuple(hotspot_ids)
        + tuple(manifest_inventory_ids)
        + tuple(diagnostic_ids)
        + tuple(concentration_fact_ids)
    )
    return DependencyConclusion(
        conclusion_id=build_conclusion_id(
            policy_id=policy_id,
            repository_id=repository_id,
            supporting_ids=support,
        ),
        policy_id=policy_id,
        kind=kind,
        audience=audience,
        title=title,
        summary=summary,
        technical_interpretation=technical_interpretation,
        source_role=source_role,
        theme_ids=tuple(sorted(set(theme_ids))),
        finding_ids=tuple(sorted(set(finding_ids)))[:_FINDING_REF_LIMIT],
        hotspot_ids=tuple(sorted(set(hotspot_ids)))[:_HOTSPOT_REF_LIMIT],
        manifest_inventory_ids=tuple(sorted(set(manifest_inventory_ids)))[
            :_MANIFEST_REF_LIMIT
        ],
        diagnostic_ids=tuple(sorted(set(diagnostic_ids)))[:_DIAGNOSTIC_REF_LIMIT],
        concentration_fact_ids=tuple(sorted(set(concentration_fact_ids))),
        metadata=dict(metadata or {}),
    )


def _make_recommendation(
    *,
    conclusion: DependencyConclusion,
    kind: DependencyRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conditional: bool = True,
) -> DependencyRecommendation:
    return DependencyRecommendation(
        recommendation_id=build_recommendation_id(
            conclusion_ids=(conclusion.conclusion_id,),
            action_key=action_key,
        ),
        kind=kind,
        title=title,
        action=action,
        rationale=rationale,
        conclusion_ids=(conclusion.conclusion_id,),
        theme_ids=conclusion.theme_ids,
        finding_ids=conclusion.finding_ids,
        hotspot_ids=conclusion.hotspot_ids,
        conditional=conditional,
        audience=conclusion.audience,
        metadata={"action_key": action_key, "kind": kind.value},
    )


def _rule_themes(
    refs: Sequence[DependencyFindingReference],
    hotspot_inventory: DependencyHotspotInventory,
    *,
    source_role: DependencySourceRole,
    scope: DependencyThemeScope,
) -> tuple[DependencyTheme, ...]:
    by_rule: dict[str, list[DependencyFindingReference]] = defaultdict(list)
    for item in refs:
        if item.source_role is not source_role:
            continue
        by_rule[item.rule_id].append(item)
    hotspots = (
        hotspot_inventory.production
        if source_role is DependencySourceRole.PRODUCTION
        else hotspot_inventory.test
        if source_role is DependencySourceRole.TEST
        else hotspot_inventory.unknown
    )
    hotspot_by_rule: dict[str, set[str]] = defaultdict(set)
    for hotspot in hotspots:
        for rule_id in hotspot.distinct_rule_ids:
            hotspot_by_rule[rule_id].add(hotspot.hotspot_id)

    themes: list[DependencyTheme] = []
    for rule_id in HYGIENE_RULE_IDS:
        items = by_rule.get(rule_id, [])
        if not items:
            continue
        kind = _RULE_THEME_KIND[rule_id]
        finding_ids = tuple(sorted(item.finding_id for item in items))
        themes.append(
            DependencyTheme(
                theme_id=build_theme_id(
                    kind=kind.value, scope=scope.value, subject=rule_id
                ),
                kind=kind,
                title=_RULE_TITLES.get(rule_id, rule_id),
                description=(
                    f"{len(finding_ids)} {source_role.value} finding(s) for `{rule_id}`."
                ),
                scope=scope,
                source_role=source_role,
                finding_ids=finding_ids,
                hotspot_ids=tuple(sorted(hotspot_by_rule.get(rule_id, ()))),
                rule_ids=(rule_id,),
                counts={"finding_count": len(finding_ids)},
            )
        )
    return tuple(sorted(themes, key=lambda item: (item.kind.value, item.theme_id)))


def _landscape_theme(
    evidence_summary: DependencyEvidenceSummary,
    declaration_inventory: DependencyDeclarationInventory,
    manifest_inventory: DependencyManifestInventory,
) -> DependencyTheme | None:
    if evidence_summary.declarations_collected <= 0 and not manifest_inventory.entries:
        return None
    ecosystems = evidence_summary.ecosystems
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.DEPENDENCY_LANDSCAPE.value,
            scope=DependencyThemeScope.REPOSITORY.value,
        ),
        kind=DependencyThemeKind.DEPENDENCY_LANDSCAPE,
        title="Dependency landscape",
        description=(
            f"{evidence_summary.declarations_collected} declared dependency fact(s) "
            f"across {len(manifest_inventory.entries)} manifest(s) and "
            f"{len(ecosystems)} ecosystem(s)."
        ),
        scope=DependencyThemeScope.REPOSITORY,
        source_role=DependencySourceRole.UNKNOWN,
        manifest_inventory_ids=tuple(
            item.manifest_inventory_id for item in manifest_inventory.entries
        )[:_MANIFEST_REF_LIMIT],
        counts={
            "declarations": evidence_summary.declarations_collected,
            "manifests": len(manifest_inventory.entries),
            "production_declarations": declaration_inventory.production.declaration_count,
            "test_declarations": declaration_inventory.test.declaration_count,
            "ecosystems": len(ecosystems),
        },
    )


def _manifest_distribution_theme(
    manifest_inventory: DependencyManifestInventory,
) -> DependencyTheme | None:
    if not manifest_inventory.entries:
        return None
    by_type: dict[str, int] = defaultdict(int)
    by_role: dict[str, int] = defaultdict(int)
    for item in manifest_inventory.entries:
        by_type[item.manifest_type] += 1
        by_role[item.source_role.value] += 1
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.MANIFEST_DISTRIBUTION.value,
            scope=DependencyThemeScope.REPOSITORY.value,
        ),
        kind=DependencyThemeKind.MANIFEST_DISTRIBUTION,
        title="Manifest distribution",
        description=(
            "Manifest inventory by type and source role "
            f"(types={dict(sorted(by_type.items()))}, "
            f"roles={dict(sorted(by_role.items()))})."
        ),
        scope=DependencyThemeScope.REPOSITORY,
        source_role=DependencySourceRole.UNKNOWN,
        manifest_inventory_ids=tuple(
            item.manifest_inventory_id for item in manifest_inventory.entries
        )[:_MANIFEST_REF_LIMIT],
        counts={**{f"type:{key}": value for key, value in sorted(by_type.items())},
                **{f"role:{key}": value for key, value in sorted(by_role.items())}},
    )


def _plugin_theme(
    declaration_inventory: DependencyDeclarationInventory,
) -> DependencyTheme | None:
    prod = declaration_inventory.production
    total = prod.declaration_count
    plugins = prod.plugin_count
    if plugins <= 0 or total <= 0:
        return None
    share = round(plugins / total, 4)
    if share < PLUGIN_SHARE_MIN_FOR_THEME and plugins < 3:
        return None
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.BUILD_PLUGIN_LANDSCAPE.value,
            scope=DependencyThemeScope.PRODUCTION.value,
        ),
        kind=DependencyThemeKind.BUILD_PLUGIN_LANDSCAPE,
        title="Build plugin landscape",
        description=(
            f"{plugins}/{total} production declarations are build plugins "
            f"({_pct(share)}); plugins are not active runtime dependencies."
        ),
        scope=DependencyThemeScope.PRODUCTION,
        source_role=DependencySourceRole.PRODUCTION,
        counts={"plugin_count": plugins, "declaration_count": total},
        share=share,
    )


def _version_resolution_theme(
    evidence_summary: DependencyEvidenceSummary,
    diagnostics_summary: DependencyDiagnosticsSummary,
) -> DependencyTheme | None:
    if (
        evidence_summary.proven_unresolved_count <= 0
        and evidence_summary.unsupported_resolution_count <= 0
        and not diagnostics_summary.records
    ):
        return None
    diag_ids = tuple(
        item.diagnostic_id
        for item in diagnostics_summary.records
        if item.diagnostic_code
        in {
            "unsupported_gradle_resolution",
            "unsupported_dynamic_gradle",
            "maven_parent_not_fetched",
            "unresolved_expression",
        }
    )
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.VERSION_RESOLUTION_COVERAGE.value,
            scope=DependencyThemeScope.COVERAGE.value,
        ),
        kind=DependencyThemeKind.VERSION_RESOLUTION_COVERAGE,
        title="Version resolution coverage",
        description=(
            f"Proven unresolved={evidence_summary.proven_unresolved_count}; "
            f"unsupported resolution={evidence_summary.unsupported_resolution_count}; "
            f"resolution-related diagnostics={len(diag_ids)}."
        ),
        scope=DependencyThemeScope.COVERAGE,
        source_role=DependencySourceRole.UNKNOWN,
        diagnostic_ids=diag_ids[:_DIAGNOSTIC_REF_LIMIT],
        counts={
            "proven_unresolved": evidence_summary.proven_unresolved_count,
            "unsupported_resolution": evidence_summary.unsupported_resolution_count,
            "diagnostic_count": len(diag_ids),
        },
    )


def _test_fixture_theme(
    test_refs: Sequence[DependencyFindingReference],
    hotspot_inventory: DependencyHotspotInventory,
) -> DependencyTheme | None:
    if not test_refs:
        return None
    finding_ids = tuple(sorted(item.finding_id for item in test_refs))
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.TEST_FIXTURE_HYGIENE.value,
            scope=DependencyThemeScope.TEST_OBSERVATION.value,
        ),
        kind=DependencyThemeKind.TEST_FIXTURE_HYGIENE,
        title="Test/fixture hygiene observations",
        description=(
            f"{len(finding_ids)} test/fixture dependency hygiene finding(s) are "
            "partitioned separately from production health."
        ),
        scope=DependencyThemeScope.TEST_OBSERVATION,
        source_role=DependencySourceRole.TEST,
        finding_ids=finding_ids,
        hotspot_ids=tuple(item.hotspot_id for item in hotspot_inventory.test)[
            :_HOTSPOT_REF_LIMIT
        ],
        rule_ids=tuple(sorted({item.rule_id for item in test_refs})),
        counts={"finding_count": len(finding_ids)},
    )


def _partial_ecosystem_theme(
    diagnostics_summary: DependencyDiagnosticsSummary,
    evidence_summary: DependencyEvidenceSummary,
) -> DependencyTheme | None:
    # Require explicit package.json / npm ecosystem relevance — not Maven
    # coordinates such as org.webjars.npm:*.
    npm_relevant = False
    for item in diagnostics_summary.records:
        path = (item.path or "").replace("\\", "/").lower()
        message = (item.message or "").lower()
        if path.endswith("package.json") or "/package.json:" in message:
            npm_relevant = True
            break
        if "package.json" in message and "org.webjars.npm" not in message:
            npm_relevant = True
            break
        if (
            "ecosystem:npm" in message
            or "ecosystem=npm" in message
            or "unsupported ecosystem npm" in message
        ):
            npm_relevant = True
            break
    if not npm_relevant:
        return None
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.PARTIAL_ECOSYSTEM_COVERAGE.value,
            scope=DependencyThemeScope.COVERAGE.value,
            subject="npm",
        ),
        kind=DependencyThemeKind.PARTIAL_ECOSYSTEM_COVERAGE,
        title="Partial ecosystem coverage",
        description=(
            "Repository evidence indicates npm/package.json relevance, but npm "
            "collection is out of scope for this milestone."
        ),
        scope=DependencyThemeScope.COVERAGE,
        source_role=DependencySourceRole.UNKNOWN,
        counts={"ecosystems_supported": len(evidence_summary.ecosystems)},
    )


def _declaration_hygiene_theme(
    production_refs: Sequence[DependencyFindingReference],
) -> DependencyTheme | None:
    if not production_refs:
        return None
    return DependencyTheme(
        theme_id=build_theme_id(
            kind=DependencyThemeKind.DECLARATION_HYGIENE.value,
            scope=DependencyThemeScope.PRODUCTION.value,
        ),
        kind=DependencyThemeKind.DECLARATION_HYGIENE,
        title="Production declaration hygiene",
        description=(
            f"{len(production_refs)} production hygiene finding(s) across "
            f"{len({item.rule_id for item in production_refs})} rule(s)."
        ),
        scope=DependencyThemeScope.PRODUCTION,
        source_role=DependencySourceRole.PRODUCTION,
        finding_ids=tuple(sorted(item.finding_id for item in production_refs)),
        rule_ids=tuple(sorted({item.rule_id for item in production_refs})),
        counts={"finding_count": len(production_refs)},
    )


def _ecosystem_concentration_facts(
    aggregation: DependencyAggregationInventory,
) -> tuple[DependencyConcentrationFact, ...]:
    buckets = aggregation.by_ecosystem
    total = sum(item.count for item in buckets)
    if total <= 0:
        return ()
    facts: list[DependencyConcentrationFact] = []
    for item in buckets:
        share = round(item.count / total, 4)
        facts.append(
            DependencyConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="ecosystem_share", subject=item.label
                ),
                kind="ecosystem_share",
                subject=item.label,
                count=item.count,
                total=total,
                share=share,
                source_role=DependencySourceRole.UNKNOWN,
            )
        )
    return tuple(facts)


def _plugin_management_facts(
    declaration_inventory: DependencyDeclarationInventory,
) -> tuple[DependencyConcentrationFact, ...]:
    prod = declaration_inventory.production
    total = prod.declaration_count
    if total <= 0:
        return ()
    facts: list[DependencyConcentrationFact] = []
    for kind, count in (
        ("plugin_share", prod.plugin_count),
        ("dependency_management_share", prod.dependency_management_count),
        ("active_share", prod.active_declaration_count),
    ):
        share = round(count / total, 4)
        facts.append(
            DependencyConcentrationFact(
                fact_id=build_concentration_fact_id(kind=kind, subject="production"),
                kind=kind,
                subject="production",
                count=count,
                total=total,
                share=share,
                source_role=DependencySourceRole.PRODUCTION,
            )
        )
    return tuple(facts)


def _manifest_finding_concentration(
    production_refs: Sequence[DependencyFindingReference],
    hotspot_inventory: DependencyHotspotInventory,
) -> tuple[DependencyConcentrationFact, ...]:
    total = len(production_refs)
    if total <= 0:
        return ()
    ordered = [
        item for item in hotspot_inventory.production if item.hygiene_finding_count > 0
    ]
    if not ordered:
        return ()
    top = ordered[:5]
    top_count = sum(item.hygiene_finding_count for item in top)
    share = round(top_count / total, 4)
    return (
        DependencyConcentrationFact(
            fact_id=build_concentration_fact_id(
                kind="top_manifest_finding_share",
                subject="production_top_manifests",
            ),
            kind="top_manifest_finding_share",
            subject="production_top_manifests",
            count=top_count,
            total=total,
            share=share,
            threshold=MANIFEST_FINDING_CONCENTRATION_MIN_SHARE,
            exceeds_threshold=share >= MANIFEST_FINDING_CONCENTRATION_MIN_SHARE,
            source_role=DependencySourceRole.PRODUCTION,
            supporting_finding_ids=tuple(
                sorted({fid for item in top for fid in item.finding_ids})
            ),
            supporting_hotspot_ids=tuple(item.hotspot_id for item in top),
            supporting_manifest_ids=tuple(
                item.manifest_inventory_id for item in top
            ),
        ),
    )


def synthesize_dependency(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: DependencyAssessmentStatus,
    finding_summaries: Sequence[DependencyFindingReference],
    hotspot_inventory: DependencyHotspotInventory,
    manifest_inventory: DependencyManifestInventory,
    declaration_inventory: DependencyDeclarationInventory,
    aggregation_inventory: DependencyAggregationInventory,
    evidence_summary: DependencyEvidenceSummary,
    diagnostics_summary: DependencyDiagnosticsSummary,
    include_synthesis: bool = True,
) -> DependencySynthesisResult:
    """Synthesize themes/conclusions/recommendations from inventory projections."""

    if not include_synthesis:
        return DependencySynthesisResult(
            status=DependencySynthesisStatus.NOT_REQUESTED
        )

    if not pack_enabled or section_status is DependencyAssessmentStatus.DISABLED:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=DependencyConclusionKind.DISABLED,
            audience=DependencyConclusionAudience.STATUS,
            title="Dependency synthesis disabled",
            summary="The dependency pack or assessment section is disabled.",
            technical_interpretation=(
                "No production-health themes, conclusions, or recommendations "
                "are generated while the pack/section gate is off."
            ),
            source_role=DependencySourceRole.UNKNOWN,
            metadata={"gate": "disabled"},
        )
        return DependencySynthesisResult(
            status=DependencySynthesisStatus.DISABLED,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        DependencyAssessmentStatus.INSUFFICIENT_EVIDENCE,
        DependencyAssessmentStatus.NOT_APPLICABLE,
        DependencyAssessmentStatus.FAILED,
    } or (
        evidence_summary.manifests_supported == 0
        and evidence_summary.declarations_collected == 0
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=DependencyConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=DependencyConclusionAudience.STATUS,
            title="Dependency inventory unavailable",
            summary=(
                "Dependency synthesis cannot produce production-health conclusions "
                "because usable dependency inventory evidence is unavailable."
            ),
            technical_interpretation=(
                f"Assessment status `{section_status.value}` with "
                f"supported_manifests={evidence_summary.manifests_supported} and "
                f"declarations={evidence_summary.declarations_collected}."
            ),
            source_role=DependencySourceRole.UNKNOWN,
            metadata={"section_status": section_status.value},
        )
        return DependencySynthesisResult(
            status=DependencySynthesisStatus.INSUFFICIENT_EVIDENCE,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    production_refs = [
        item
        for item in finding_summaries
        if item.source_role is DependencySourceRole.PRODUCTION
    ]
    test_refs = [
        item
        for item in finding_summaries
        if item.source_role is DependencySourceRole.TEST
    ]
    unknown_refs = [
        item
        for item in finding_summaries
        if item.source_role is DependencySourceRole.UNKNOWN
    ]

    themes: list[DependencyTheme] = []
    landscape = _landscape_theme(
        evidence_summary, declaration_inventory, manifest_inventory
    )
    if landscape is not None:
        themes.append(landscape)
    distribution = _manifest_distribution_theme(manifest_inventory)
    if distribution is not None:
        themes.append(distribution)
    plugins = _plugin_theme(declaration_inventory)
    if plugins is not None:
        themes.append(plugins)
    resolution = _version_resolution_theme(evidence_summary, diagnostics_summary)
    if resolution is not None:
        themes.append(resolution)
    hygiene = _declaration_hygiene_theme(production_refs)
    if hygiene is not None:
        themes.append(hygiene)
    themes.extend(
        _rule_themes(
            production_refs,
            hotspot_inventory,
            source_role=DependencySourceRole.PRODUCTION,
            scope=DependencyThemeScope.PRODUCTION,
        )
    )
    test_theme = _test_fixture_theme(test_refs, hotspot_inventory)
    if test_theme is not None:
        themes.append(test_theme)
    themes.extend(
        _rule_themes(
            test_refs,
            hotspot_inventory,
            source_role=DependencySourceRole.TEST,
            scope=DependencyThemeScope.TEST_OBSERVATION,
        )
    )
    partial_eco = _partial_ecosystem_theme(diagnostics_summary, evidence_summary)
    if partial_eco is not None:
        themes.append(partial_eco)

    ordered_themes = tuple(
        sorted(themes, key=lambda item: (item.kind.value, item.scope.value, item.theme_id))
    )
    themes_by_kind = {item.kind: item for item in ordered_themes}
    production_rule_themes = {
        theme.rule_ids[0]: theme
        for theme in ordered_themes
        if theme.scope is DependencyThemeScope.PRODUCTION and theme.rule_ids
    }

    concentration_facts = (
        _ecosystem_concentration_facts(aggregation_inventory)
        + _plugin_management_facts(declaration_inventory)
        + _manifest_finding_concentration(production_refs, hotspot_inventory)
    )

    conclusions: list[DependencyConclusion] = []
    recommendations: list[DependencyRecommendation] = []

    # Always: declared-only coverage conclusion.
    declared = _make_conclusion(
        repository_id=repository_id,
        policy_id=POLICY_DECLARED_ONLY,
        kind=DependencyConclusionKind.DECLARED_DEPENDENCIES_ONLY,
        audience=DependencyConclusionAudience.COVERAGE,
        title="Declared dependencies only",
        summary=(
            "Dependency Intelligence inspects declared-manifest facts only. "
            "Transitive/resolved dependency graphs are not constructed."
        ),
        technical_interpretation=(
            "No build-tool execution or registry lookup is performed. Absence of "
            "hygiene findings does not imply absence of dependency risk beyond "
            "declared-manifest evidence."
        ),
        source_role=DependencySourceRole.UNKNOWN,
        theme_ids=(
            (themes_by_kind[DependencyThemeKind.DEPENDENCY_LANDSCAPE].theme_id,)
            if DependencyThemeKind.DEPENDENCY_LANDSCAPE in themes_by_kind
            else ()
        ),
        metadata={"transitive_resolution": "not_performed"},
    )
    conclusions.append(declared)
    recommendations.append(
        _make_recommendation(
            conclusion=declared,
            kind=DependencyRecommendationKind.ADD_RESOLVED_GRAPH_ANALYSIS,
            action_key="add-resolved-graph-analysis",
            title="Add resolved-graph analysis when transitive risk is in scope",
            action=(
                "If transitive or resolved-graph risk assessment is required, add a "
                "separate resolved-graph analysis capability; this inventory remains "
                "declared-manifest only."
            ),
            rationale=(
                "Current evidence and synthesis intentionally exclude transitive "
                "resolution and registry lookups."
            ),
            conditional=True,
        )
    )

    if landscape is not None:
        landscape_conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LANDSCAPE,
            kind=DependencyConclusionKind.DEPENDENCY_LANDSCAPE_IDENTIFIED,
            audience=DependencyConclusionAudience.REPOSITORY,
            title="Dependency landscape identified",
            summary=landscape.description,
            technical_interpretation=(
                "Landscape facts come from Dependency Evidence inventories "
                "(ecosystems, manifests, declaration partitions)."
            ),
            source_role=DependencySourceRole.UNKNOWN,
            theme_ids=(landscape.theme_id,),
            manifest_inventory_ids=landscape.manifest_inventory_ids,
            metadata={
                "declarations": str(evidence_summary.declarations_collected),
                "manifests": str(len(manifest_inventory.entries)),
            },
        )
        conclusions.append(landscape_conclusion)

    # Unsupported Gradle / resolution coverage.
    gradle_diags = [
        item
        for item in diagnostics_summary.records
        if item.diagnostic_code
        in {"unsupported_gradle_resolution", "unsupported_dynamic_gradle"}
    ]
    if gradle_diags or evidence_summary.unsupported_resolution_count > 0:
        diag_ids = tuple(item.diagnostic_id for item in gradle_diags)
        theme_ids = (
            (themes_by_kind[DependencyThemeKind.VERSION_RESOLUTION_COVERAGE].theme_id,)
            if DependencyThemeKind.VERSION_RESOLUTION_COVERAGE in themes_by_kind
            else ()
        )
        unsupported = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_RESOLUTION,
            kind=DependencyConclusionKind.UNSUPPORTED_RESOLUTION_COVERAGE,
            audience=DependencyConclusionAudience.COVERAGE,
            title="Unsupported version-resolution coverage gaps",
            summary=(
                f"{evidence_summary.unsupported_resolution_count} unsupported "
                f"resolution signal(s) and {len(gradle_diags)} Gradle-related "
                "diagnostic(s) indicate coverage limits, not proven unresolved "
                "hygiene findings."
            ),
            technical_interpretation=(
                "Unsupported Gradle interpolation and related constructs remain "
                "diagnostics/coverage limitations. They must not be treated as "
                "unresolved-version findings without proven_unresolved status."
            ),
            source_role=DependencySourceRole.UNKNOWN,
            theme_ids=theme_ids,
            diagnostic_ids=diag_ids,
            metadata={
                "unsupported_resolution_count": str(
                    evidence_summary.unsupported_resolution_count
                ),
                "gradle_diagnostic_count": str(len(gradle_diags)),
            },
        )
        conclusions.append(unsupported)
        recommendations.append(
            _make_recommendation(
                conclusion=unsupported,
                kind=DependencyRecommendationKind.EXPAND_GRADLE_RESOLUTION_COVERAGE,
                action_key="expand-gradle-resolution-coverage",
                title="Expand Gradle resolution coverage when needed",
                action=(
                    "If repository-provable Gradle property/version resolution is "
                    "required, expand Dependency Evidence coverage "
                    "(properties/ext/catalogs) rather than treating unsupported "
                    "interpolations as hygiene findings."
                ),
                rationale=(
                    "Diagnostics show unsupported resolution mechanisms without "
                    "proven local unresolved status."
                ),
                conditional=True,
            )
        )

    if section_status is DependencyAssessmentStatus.PARTIALLY_SUCCEEDED or (
        evidence_summary.evidence_status == "partially_succeeded"
        and (
            # production parse failures or production partials
            any(
                item.source_role is DependencySourceRole.PRODUCTION
                and item.parse_status == "failed"
                for item in manifest_inventory.entries
            )
        )
    ):
        prod_partial_manifests = tuple(
            item.manifest_inventory_id
            for item in manifest_inventory.entries
            if item.source_role is DependencySourceRole.PRODUCTION
            and item.parse_status in {"failed", "partially_succeeded"}
        )
        if any(
            item.source_role is DependencySourceRole.PRODUCTION
            and item.parse_status == "failed"
            for item in manifest_inventory.entries
        ):
            partial = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_PRODUCTION_PARTIAL,
                kind=DependencyConclusionKind.PRODUCTION_COLLECTION_PARTIAL,
                audience=DependencyConclusionAudience.COVERAGE,
                title="Production dependency collection is partial",
                summary=(
                    "One or more production manifests failed to parse; production "
                    "inventory may be incomplete."
                ),
                technical_interpretation=(
                    "Assessment status reflects production usability. Failed "
                    "production manifests are coverage limitations, not hygiene findings."
                ),
                source_role=DependencySourceRole.PRODUCTION,
                manifest_inventory_ids=prod_partial_manifests,
                metadata={"section_status": section_status.value},
            )
            conclusions.append(partial)

    if partial_eco is not None:
        eco = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_ECOSYSTEM,
            kind=DependencyConclusionKind.UNSUPPORTED_ECOSYSTEM_COVERAGE,
            audience=DependencyConclusionAudience.COVERAGE,
            title="Unsupported ecosystem coverage",
            summary=partial_eco.description,
            technical_interpretation=(
                "npm/package.json is out of scope for current collectors. This is a "
                "coverage limitation, not a hygiene finding."
            ),
            source_role=DependencySourceRole.UNKNOWN,
            theme_ids=(partial_eco.theme_id,),
        )
        conclusions.append(eco)
        recommendations.append(
            _make_recommendation(
                conclusion=eco,
                kind=DependencyRecommendationKind.ADD_UNSUPPORTED_ECOSYSTEM_COVERAGE,
                action_key="add-unsupported-ecosystem-coverage",
                title="Add unsupported ecosystem collection when npm is in scope",
                action=(
                    "If npm dependency assessment is required, add package.json "
                    "collection to Dependency Evidence; do not invent npm findings "
                    "from absent evidence."
                ),
                rationale="Repository evidence indicated npm relevance without collectors.",
                conditional=True,
            )
        )

    if not production_refs:
        no_prod = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_PRODUCTION,
            kind=DependencyConclusionKind.NO_PRODUCTION_HYGIENE_FINDINGS,
            audience=DependencyConclusionAudience.PRODUCTION_HEALTH,
            title="No production dependency hygiene findings",
            summary=(
                "Under current Dependency Intelligence hygiene rules, no "
                "production-source findings were emitted."
            ),
            technical_interpretation=(
                "Primary production finding inventory is empty. This does not imply "
                "absence of all dependency risk; it means no production declaration "
                "matched the enabled hygiene rules among supported manifests."
            ),
            source_role=DependencySourceRole.PRODUCTION,
            theme_ids=(
                (themes_by_kind[DependencyThemeKind.DEPENDENCY_LANDSCAPE].theme_id,)
                if DependencyThemeKind.DEPENDENCY_LANDSCAPE in themes_by_kind
                else ()
            ),
            metadata={"production_finding_count": "0"},
        )
        conclusions.append(no_prod)
        recommendations.append(
            _make_recommendation(
                conclusion=no_prod,
                kind=DependencyRecommendationKind.ACKNOWLEDGE_NO_PRODUCTION_FINDINGS,
                action_key="acknowledge-no-production-hygiene-findings",
                title="Acknowledge empty production hygiene inventory",
                action=(
                    "No production dependency hygiene findings require remediation "
                    "under the current rule pack and evidence contract."
                ),
                rationale=(
                    "The production-primary finding inventory contains zero matches."
                ),
                conditional=False,
            )
        )
    else:
        prod_finding_ids = tuple(sorted(item.finding_id for item in production_refs))
        prod_hotspot_ids = tuple(
            item.hotspot_id
            for item in hotspot_inventory.production
            if item.hygiene_finding_count > 0
        )[:_HOTSPOT_REF_LIMIT]
        present = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_PRODUCTION_PRESENT,
            kind=DependencyConclusionKind.PRODUCTION_HYGIENE_FINDINGS_PRESENT,
            audience=DependencyConclusionAudience.PRODUCTION_HEALTH,
            title="Production dependency hygiene findings are present",
            summary=(
                f"{len(production_refs)} production hygiene finding(s) across "
                f"{len({item.rule_id for item in production_refs})} rule(s)."
            ),
            technical_interpretation=(
                "Production declarations matched one or more enabled hygiene rules. "
                "No composite dependency-health score is assigned."
            ),
            source_role=DependencySourceRole.PRODUCTION,
            theme_ids=tuple(
                theme.theme_id
                for theme in ordered_themes
                if theme.scope is DependencyThemeScope.PRODUCTION
            ),
            finding_ids=prod_finding_ids,
            hotspot_ids=prod_hotspot_ids,
            metadata={"production_finding_count": str(len(production_refs))},
        )
        conclusions.append(present)
        recommendations.append(
            _make_recommendation(
                conclusion=present,
                kind=DependencyRecommendationKind.REVIEW_DEPENDENCY_HYGIENE_FINDINGS,
                action_key="review-dependency-hygiene-findings",
                title="Review production dependency hygiene findings",
                action=(
                    "If improving declaration hygiene is in scope, review the "
                    "production-primary finding inventory and affected manifest "
                    "hotspots, then remediate referenced declarations."
                ),
                rationale=(
                    "Production findings identify hygiene rule matches; no priority "
                    "score is assigned."
                ),
                conditional=True,
            )
        )

        for rule_id in HYGIENE_RULE_IDS:
            theme = production_rule_themes.get(rule_id)
            if theme is None:
                continue
            kind, policy = _RULE_CONCLUSION[rule_id]
            rec_kind, action_key, rec_title, rec_action = _RULE_RECOMMENDATION[rule_id]
            rule_conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=policy,
                kind=kind,
                audience=DependencyConclusionAudience.PRODUCTION_HEALTH,
                title=f"Production theme: {theme.title}",
                summary=theme.description,
                technical_interpretation=(
                    f"Theme `{theme.theme_id}` aggregates production matches for "
                    f"`{rule_id}`."
                ),
                source_role=DependencySourceRole.PRODUCTION,
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                hotspot_ids=theme.hotspot_ids[:_HOTSPOT_REF_LIMIT],
                metadata={"rule_id": rule_id},
            )
            conclusions.append(rule_conclusion)
            recommendations.append(
                _make_recommendation(
                    conclusion=rule_conclusion,
                    kind=rec_kind,
                    action_key=action_key,
                    title=rec_title,
                    action=rec_action,
                    rationale=(
                        f"Derived from {theme.counts.get('finding_count', 0)} "
                        f"production finding(s) for `{rule_id}`."
                    ),
                    conditional=True,
                )
            )

    if test_refs:
        test_finding_ids = tuple(sorted(item.finding_id for item in test_refs))
        test_conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_TEST_FIXTURE,
            kind=DependencyConclusionKind.TEST_FIXTURE_FINDINGS_PRESENT,
            audience=DependencyConclusionAudience.TEST_OBSERVATION,
            title="Test/fixture dependency hygiene findings observed",
            summary=(
                f"{len(test_refs)} test/fixture hygiene finding(s) are present and "
                "exposed separately from the production-primary inventory."
            ),
            technical_interpretation=(
                "Test/fixture observation only. These findings must not be "
                "interpreted as production-health defects without separate review."
            ),
            source_role=DependencySourceRole.TEST,
            theme_ids=(
                (test_theme.theme_id,) if test_theme is not None else ()
            ),
            finding_ids=test_finding_ids,
            hotspot_ids=tuple(item.hotspot_id for item in hotspot_inventory.test)[
                :_HOTSPOT_REF_LIMIT
            ],
            metadata={
                "test_finding_count": str(len(test_refs)),
                "unknown_finding_count": str(len(unknown_refs)),
            },
        )
        conclusions.append(test_conclusion)
        recommendations.append(
            _make_recommendation(
                conclusion=test_conclusion,
                kind=DependencyRecommendationKind.REVIEW_TEST_FIXTURE_DECLARATIONS,
                action_key="review-test-fixture-declarations",
                title="Review test/fixture declarations separately",
                action=(
                    "If fixture maintainability is in scope, review test/fixture "
                    "findings separately; do not treat them as production-health "
                    "conclusions."
                ),
                rationale=(
                    "Test findings are inventory-partitioned and excluded from "
                    "production-health remediation recommendations."
                ),
                conditional=True,
            )
        )

    # Link recommendation IDs back onto conclusions.
    recs_by_conclusion: dict[str, list[str]] = defaultdict(list)
    for rec in recommendations:
        for conclusion_id in rec.conclusion_ids:
            recs_by_conclusion[conclusion_id].append(rec.recommendation_id)
    linked_conclusions = tuple(
        conclusion.model_copy(
            update={
                "recommendation_ids": tuple(
                    sorted(set(recs_by_conclusion.get(conclusion.conclusion_id, ())))
                )
            }
        )
        for conclusion in sorted(
            conclusions,
            key=lambda item: (item.kind.value, item.policy_id, item.conclusion_id),
        )
    )
    ordered_recs = tuple(
        sorted(
            recommendations,
            key=lambda item: (
                item.audience.value,
                item.kind.value,
                item.title,
                item.recommendation_id,
            ),
        )
    )

    status = (
        DependencySynthesisStatus.EMPTY
        if not production_refs
        and not test_refs
        and evidence_summary.declarations_collected == 0
        else DependencySynthesisStatus.SUCCEEDED
    )
    return DependencySynthesisResult(
        status=status,
        synthesis_version=SYNTHESIS_VERSION,
        themes=ordered_themes,
        theme_ids=tuple(item.theme_id for item in ordered_themes),
        concentration_facts=concentration_facts,
        conclusions=linked_conclusions,
        conclusion_ids=tuple(item.conclusion_id for item in linked_conclusions),
        recommendations=ordered_recs,
        recommendation_ids=tuple(item.recommendation_id for item in ordered_recs),
        diagnostics=(),
    )
