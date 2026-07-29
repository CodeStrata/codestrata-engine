"""Deterministic Technical Debt synthesis from assessment inventory (Phase 4.3.5).

Consumes finding inventory + hotspots only. Does not re-evaluate rules or parse
source. Produces themes, concentration facts, conclusions, and recommendations.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.application.rules.technical_debt.recommendations import recommendation_for
from codestrata.domain.technical_debt.assessment.enums import (
    TechnicalDebtAssessmentStatus,
    TechnicalDebtCoverageAreaStatus,
    TechnicalDebtSourceRole,
)
from codestrata.domain.technical_debt.assessment.models import (
    TechnicalDebtCoverageSummary,
    TechnicalDebtFindingReference,
    TechnicalDebtHotspot,
    TechnicalDebtHotspotInventory,
)
from codestrata.domain.technical_debt.ids import COMPLEXITY_RULE_IDS
from codestrata.domain.technical_debt.synthesis.enums import (
    TechnicalDebtConclusionAudience,
    TechnicalDebtConclusionKind,
    TechnicalDebtSynthesisStatus,
)
from codestrata.domain.technical_debt.synthesis.identifiers import (
    HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE,
    PACKAGE_CONCENTRATION_MIN_SHARE,
    POLICY_COMPLEXITY_PRESENT,
    POLICY_DISABLED,
    POLICY_HOTSPOT_CONCENTRATION,
    POLICY_MULTI_RULE_HOTSPOTS,
    POLICY_NO_PRODUCTION,
    POLICY_PACKAGE_CONCENTRATION,
    POLICY_PARTIAL_COVERAGE,
    POLICY_TEST_MAINTAINABILITY,
    SYNTHESIS_VERSION,
    build_concentration_fact_id,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
    theme_policy_id,
)
from codestrata.domain.technical_debt.synthesis.models import (
    TechnicalDebtConcentrationFact,
    TechnicalDebtConclusion,
    TechnicalDebtRecommendation,
    TechnicalDebtSynthesisResult,
    TechnicalDebtTheme,
)
from codestrata.domain.technical_debt.taxonomy import TechnicalDebtCategory

_RULE_TITLES: dict[str, str] = {
    "technical_debt.large-callable": "Large callables",
    "technical_debt.excessive-branching": "Excessive branching",
    "technical_debt.deep-nesting": "Deep nesting",
    "technical_debt.excessive-parameters": "Excessive parameters",
    "technical_debt.oversized-type": "Oversized types/modules",
}


def _pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def _build_themes(
    refs: Sequence[TechnicalDebtFindingReference],
    hotspots: Sequence[TechnicalDebtHotspot],
    *,
    source_role: TechnicalDebtSourceRole,
) -> tuple[TechnicalDebtTheme, ...]:
    by_rule: dict[str, list[TechnicalDebtFindingReference]] = defaultdict(list)
    for item in refs:
        if item.source_role is not source_role:
            continue
        by_rule[item.rule_id].append(item)
    hotspot_by_rule: dict[str, set[str]] = defaultdict(set)
    for hotspot in hotspots:
        if hotspot.source_role is not source_role:
            continue
        for rule_id in hotspot.rule_ids:
            hotspot_by_rule[rule_id].add(hotspot.hotspot_id)

    themes: list[TechnicalDebtTheme] = []
    for rule_id in COMPLEXITY_RULE_IDS:
        items = by_rule.get(rule_id, [])
        if not items:
            continue
        finding_ids = tuple(sorted(item.finding_id for item in items))
        high = sum(1 for item in items if item.severity == "high")
        medium = sum(1 for item in items if item.severity == "medium")
        themes.append(
            TechnicalDebtTheme(
                theme_id=build_theme_id(
                    taxonomy_id=TechnicalDebtCategory.COMPLEXITY.value,
                    rule_id=rule_id,
                    source_role=source_role.value,
                ),
                taxonomy_id=TechnicalDebtCategory.COMPLEXITY.value,
                rule_id=rule_id,
                title=_RULE_TITLES.get(rule_id, rule_id),
                source_role=source_role,
                finding_ids=finding_ids,
                hotspot_ids=tuple(sorted(hotspot_by_rule.get(rule_id, ()))),
                finding_count=len(finding_ids),
                high_severity_count=high,
                medium_severity_count=medium,
            )
        )
    return tuple(sorted(themes, key=lambda item: (item.rule_id, item.theme_id)))


def _package_concentration_facts(
    refs: Sequence[TechnicalDebtFindingReference],
) -> tuple[TechnicalDebtConcentrationFact, ...]:
    production = [item for item in refs if item.source_role is TechnicalDebtSourceRole.PRODUCTION]
    total = len(production)
    if total == 0:
        return ()
    by_package: dict[str, list[TechnicalDebtFindingReference]] = defaultdict(list)
    for item in production:
        by_package[item.package or "(unknown)"].append(item)
    facts: list[TechnicalDebtConcentrationFact] = []
    for package, items in sorted(by_package.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        count = len(items)
        share = round(count / total, 4)
        facts.append(
            TechnicalDebtConcentrationFact(
                fact_id=build_concentration_fact_id(kind="package_share", subject=package),
                kind="package_share",
                subject=package,
                count=count,
                total=total,
                share=share,
                threshold=PACKAGE_CONCENTRATION_MIN_SHARE,
                exceeds_threshold=share >= PACKAGE_CONCENTRATION_MIN_SHARE,
                source_role=TechnicalDebtSourceRole.PRODUCTION,
                supporting_finding_ids=tuple(sorted(item.finding_id for item in items)),
            )
        )
    return tuple(facts)


def _hotspot_concentration_facts(
    hotspots: Sequence[TechnicalDebtHotspot],
) -> tuple[TechnicalDebtConcentrationFact, ...]:
    production = [
        item for item in hotspots if item.source_role is TechnicalDebtSourceRole.PRODUCTION
    ]
    total_findings = sum(item.finding_count for item in production)
    if total_findings == 0 or not production:
        return ()
    ordered = list(production)  # already severity/count ordered from inventory
    top10 = ordered[:10]
    top10_count = sum(item.finding_count for item in top10)
    share = round(top10_count / total_findings, 4)
    return (
        TechnicalDebtConcentrationFact(
            fact_id=build_concentration_fact_id(
                kind="top10_hotspot_share",
                subject="production_top10_hotspots",
            ),
            kind="top10_hotspot_share",
            subject="production_top10_hotspots",
            count=top10_count,
            total=total_findings,
            share=share,
            threshold=HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE,
            exceeds_threshold=share >= HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE,
            source_role=TechnicalDebtSourceRole.PRODUCTION,
            supporting_finding_ids=tuple(
                sorted({fid for item in top10 for fid in item.finding_ids})
            ),
            supporting_hotspot_ids=tuple(item.hotspot_id for item in top10),
        ),
    )


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: TechnicalDebtConclusionKind,
    audience: TechnicalDebtConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    source_role: TechnicalDebtSourceRole,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    hotspot_ids: Sequence[str] = (),
    concentration_fact_ids: Sequence[str] = (),
    metadata: dict[str, str] | None = None,
) -> TechnicalDebtConclusion:
    support = tuple(theme_ids) + tuple(finding_ids) + tuple(hotspot_ids) + tuple(
        concentration_fact_ids
    )
    return TechnicalDebtConclusion(
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
        finding_ids=tuple(sorted(set(finding_ids))),
        hotspot_ids=tuple(sorted(set(hotspot_ids))),
        concentration_fact_ids=tuple(sorted(set(concentration_fact_ids))),
        metadata=dict(metadata or {}),
    )


def _make_recommendation(
    *,
    conclusion: TechnicalDebtConclusion,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conditional: bool = True,
) -> TechnicalDebtRecommendation:
    return TechnicalDebtRecommendation(
        recommendation_id=build_recommendation_id(
            conclusion_ids=(conclusion.conclusion_id,),
            action_key=action_key,
        ),
        title=title,
        action=action,
        rationale=rationale,
        conclusion_ids=(conclusion.conclusion_id,),
        theme_ids=conclusion.theme_ids,
        finding_ids=conclusion.finding_ids,
        hotspot_ids=conclusion.hotspot_ids,
        conditional=conditional,
        audience=conclusion.audience,
        metadata={"action_key": action_key},
    )


def synthesize_technical_debt(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: TechnicalDebtAssessmentStatus,
    finding_summaries: Sequence[TechnicalDebtFindingReference],
    hotspot_inventory: TechnicalDebtHotspotInventory,
    coverage: TechnicalDebtCoverageSummary | None = None,
    include_synthesis: bool = True,
) -> TechnicalDebtSynthesisResult:
    """Synthesize themes/conclusions/recommendations from inventory projections."""

    if not include_synthesis:
        return TechnicalDebtSynthesisResult(status=TechnicalDebtSynthesisStatus.NOT_REQUESTED)
    if not pack_enabled or section_status is TechnicalDebtAssessmentStatus.DISABLED:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=TechnicalDebtConclusionKind.DISABLED,
            audience=TechnicalDebtConclusionAudience.STATUS,
            title="Technical debt synthesis disabled",
            summary="The technical debt pack or assessment section is disabled.",
            technical_interpretation=(
                "No production-health themes, conclusions, or recommendations "
                "are generated while the pack/section gate is off."
            ),
            source_role=TechnicalDebtSourceRole.UNKNOWN,
            finding_ids=(),
            hotspot_ids=(),
            metadata={"gate": "disabled"},
        )
        return TechnicalDebtSynthesisResult(
            status=TechnicalDebtSynthesisStatus.DISABLED,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    production_refs = [
        item
        for item in finding_summaries
        if item.source_role is TechnicalDebtSourceRole.PRODUCTION
    ]
    test_refs = [
        item for item in finding_summaries if item.source_role is TechnicalDebtSourceRole.TEST
    ]
    production_hotspots = hotspot_inventory.production
    test_hotspots = hotspot_inventory.test

    production_themes = _build_themes(
        production_refs, production_hotspots, source_role=TechnicalDebtSourceRole.PRODUCTION
    )
    test_themes = _build_themes(
        test_refs, test_hotspots, source_role=TechnicalDebtSourceRole.TEST
    )
    themes = production_themes + test_themes

    package_facts = _package_concentration_facts(finding_summaries)
    hotspot_facts = _hotspot_concentration_facts(production_hotspots)
    concentration_facts = package_facts + hotspot_facts

    conclusions: list[TechnicalDebtConclusion] = []
    recommendations: list[TechnicalDebtRecommendation] = []

    # Partial coverage (coverage audience; does not invent production health claims).
    coverage_areas = coverage.areas if coverage else ()
    complexity_area = next(
        (area for area in coverage_areas if area.area_id == "complexity_coverage"),
        None,
    )
    if (
        complexity_area is not None
        and complexity_area.status is TechnicalDebtCoverageAreaStatus.PARTIAL
    ):
        conclusions.append(
            _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_PARTIAL_COVERAGE,
                kind=TechnicalDebtConclusionKind.PARTIAL_COVERAGE,
                audience=TechnicalDebtConclusionAudience.COVERAGE,
                title="Complexity coverage is partial",
                summary=(
                    "Complexity evidence coverage is partial for this repository. "
                    "Unsupported languages or parse failures may leave some units unmeasured."
                ),
                technical_interpretation=(
                    "Coverage limitations: "
                    + "; ".join(complexity_area.limitations or ("partial coverage",))
                ),
                source_role=TechnicalDebtSourceRole.UNKNOWN,
                finding_ids=(),
                hotspot_ids=(),
                metadata={"coverage_status": complexity_area.status.value},
            )
        )

    if not production_refs:
        no_prod = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_PRODUCTION,
            kind=TechnicalDebtConclusionKind.NO_PRODUCTION_FINDINGS,
            audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
            title="No production complexity-threshold findings",
            summary=(
                "Under current Technical Debt complexity rules and thresholds, no "
                "production-source findings were emitted."
            ),
            technical_interpretation=(
                "Primary production inventory is empty. This does not imply absence of "
                "all maintainability risk; it means no measured production unit exceeded "
                "configured complexity thresholds among supported languages."
            ),
            source_role=TechnicalDebtSourceRole.PRODUCTION,
            finding_ids=(),
            hotspot_ids=(),
            metadata={"production_finding_count": "0"},
        )
        conclusions.append(no_prod)
        recommendations.append(
            _make_recommendation(
                conclusion=no_prod,
                action_key="acknowledge-no-production-findings",
                title="Acknowledge empty production complexity inventory",
                action=(
                    "No production complexity-threshold findings require remediation "
                    "under the current rule pack and thresholds."
                ),
                rationale=(
                    "The production-primary inventory contains zero matching findings."
                ),
                conditional=False,
            )
        )
    else:
        prod_finding_ids = tuple(sorted(item.finding_id for item in production_refs))
        prod_hotspot_ids = tuple(item.hotspot_id for item in production_hotspots[:20])
        present = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_COMPLEXITY_PRESENT,
            kind=TechnicalDebtConclusionKind.COMPLEXITY_PRESENT,
            audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
            title="Production complexity threshold findings are present",
            summary=(
                f"{len(production_refs)} production complexity finding(s) across "
                f"{len(production_themes)} theme(s) and {len(production_hotspots)} "
                "source-unit hotspot(s)."
            ),
            technical_interpretation=(
                "Production units exceeded configured structural complexity thresholds "
                f"for rules: {', '.join(theme.rule_id for theme in production_themes)}."
            ),
            source_role=TechnicalDebtSourceRole.PRODUCTION,
            theme_ids=tuple(theme.theme_id for theme in production_themes),
            finding_ids=prod_finding_ids,
            hotspot_ids=prod_hotspot_ids,
            metadata={
                "production_finding_count": str(len(production_refs)),
                "production_hotspot_count": str(len(production_hotspots)),
            },
        )
        conclusions.append(present)
        recommendations.append(
            _make_recommendation(
                conclusion=present,
                action_key="review-production-complexity-inventory",
                title="Review production complexity inventory and hotspots",
                action=(
                    "If reducing structural complexity is a current engineering goal, "
                    "review the production-primary inventory and highest-severity "
                    "hotspots, then refactor referenced units so measured metrics fall "
                    "at or below configured thresholds."
                ),
                rationale=(
                    "Production findings and hotspots identify threshold crossings; "
                    "no composite priority score is assigned."
                ),
                conditional=True,
            )
        )

        for theme in production_themes:
            theme_conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=theme_policy_id(theme.rule_id),
                kind=TechnicalDebtConclusionKind.THEME_COMPLEXITY,
                audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
                title=f"Production theme: {theme.title}",
                summary=(
                    f"{theme.finding_count} production finding(s) for `{theme.rule_id}` "
                    f"({theme.high_severity_count} high, {theme.medium_severity_count} medium)."
                ),
                technical_interpretation=(
                    f"Theme `{theme.theme_id}` aggregates production matches for "
                    f"`{theme.rule_id}` under taxonomy `{theme.taxonomy_id}`."
                ),
                source_role=TechnicalDebtSourceRole.PRODUCTION,
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                hotspot_ids=theme.hotspot_ids[:20],
                metadata={"rule_id": theme.rule_id},
            )
            conclusions.append(theme_conclusion)
            recommendations.append(
                _make_recommendation(
                    conclusion=theme_conclusion,
                    action_key=f"remediate-{theme.rule_id}",
                    title=f"Address {theme.title.lower()} in production",
                    action=(
                        "If this complexity theme is in scope for remediation, "
                        + recommendation_for(theme.rule_id)
                    ),
                    rationale=(
                        f"Derived from {theme.finding_count} production finding(s) "
                        f"for `{theme.rule_id}`."
                    ),
                    conditional=True,
                )
            )

        concentrated_packages = [
            fact for fact in package_facts if fact.exceeds_threshold
        ]
        if concentrated_packages:
            top = concentrated_packages[0]
            pkg_conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_PACKAGE_CONCENTRATION,
                kind=TechnicalDebtConclusionKind.PACKAGE_CONCENTRATION,
                audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
                title="Production complexity findings are package-concentrated",
                summary=(
                    f"Package `{top.subject}` accounts for {top.count}/{top.total} "
                    f"production findings ({_pct(top.share)}), at or above the "
                    f"transparent threshold {_pct(PACKAGE_CONCENTRATION_MIN_SHARE)}."
                ),
                technical_interpretation=(
                    "Package concentration uses finding counts and proportions only. "
                    "Packages at/above threshold: "
                    + ", ".join(
                        f"{fact.subject}={_pct(fact.share)}"
                        for fact in concentrated_packages[:8]
                    )
                    + "."
                ),
                source_role=TechnicalDebtSourceRole.PRODUCTION,
                finding_ids=top.supporting_finding_ids,
                concentration_fact_ids=tuple(fact.fact_id for fact in concentrated_packages),
                metadata={
                    "threshold": str(PACKAGE_CONCENTRATION_MIN_SHARE),
                    "top_package": top.subject,
                    "top_share": str(top.share),
                },
            )
            conclusions.append(pkg_conclusion)
            recommendations.append(
                _make_recommendation(
                    conclusion=pkg_conclusion,
                    action_key="focus-concentrated-packages",
                    title="Focus refactoring on concentrated packages when in scope",
                    action=(
                        "If addressing complexity debt, begin with packages that "
                        "exceed the transparent concentration threshold, using the "
                        "supporting finding IDs as the review set."
                    ),
                    rationale=(
                        "Concentration facts report counts/proportions only; they do "
                        "not invent a priority score."
                    ),
                    conditional=True,
                )
            )

        if hotspot_facts and hotspot_facts[0].exceeds_threshold:
            fact = hotspot_facts[0]
            hotspot_conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_HOTSPOT_CONCENTRATION,
                kind=TechnicalDebtConclusionKind.HOTSPOT_CONCENTRATION,
                audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
                title="Production complexity findings concentrate in top hotspots",
                summary=(
                    f"Top 10 production hotspots account for {fact.count}/{fact.total} "
                    f"finding references ({_pct(fact.share)}), at or above "
                    f"{_pct(HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE)}."
                ),
                technical_interpretation=(
                    "Hotspot concentration uses inventory ordering (highest severity, "
                    "then finding count, then path/unit) without a synthetic rank score."
                ),
                source_role=TechnicalDebtSourceRole.PRODUCTION,
                finding_ids=fact.supporting_finding_ids,
                hotspot_ids=fact.supporting_hotspot_ids,
                concentration_fact_ids=(fact.fact_id,),
                metadata={
                    "threshold": str(HOTSPOT_TOP10_CONCENTRATION_MIN_SHARE),
                    "share": str(fact.share),
                },
            )
            conclusions.append(hotspot_conclusion)
            recommendations.append(
                _make_recommendation(
                    conclusion=hotspot_conclusion,
                    action_key="review-top-hotspots",
                    title="Review top production hotspots when reducing complexity",
                    action=(
                        "If reducing structural complexity is in scope, inspect the "
                        "referenced top production hotspots and apply rule-specific "
                        "refactors so metrics fall at or below thresholds."
                    ),
                    rationale=(
                        "Top hotspots are the inventory head ordered by severity and "
                        "finding count."
                    ),
                    conditional=True,
                )
            )

        multi = [item for item in production_hotspots if len(item.rule_ids) >= 2]
        if multi:
            multi_ids = tuple(item.hotspot_id for item in multi[:20])
            multi_findings = tuple(
                sorted({fid for item in multi for fid in item.finding_ids})
            )
            multi_conclusion = _make_conclusion(
                repository_id=repository_id,
                policy_id=POLICY_MULTI_RULE_HOTSPOTS,
                kind=TechnicalDebtConclusionKind.MULTI_RULE_HOTSPOTS,
                audience=TechnicalDebtConclusionAudience.PRODUCTION_HEALTH,
                title="Some production units match multiple complexity rules",
                summary=(
                    f"{len(multi)} production hotspot(s) match two or more complexity "
                    "rules on the same source unit."
                ),
                technical_interpretation=(
                    "Overlapping rules on one unit indicate multiple structural "
                    "threshold crossings (size, branching, nesting, and/or parameters) "
                    "rather than a ranked severity score."
                ),
                source_role=TechnicalDebtSourceRole.PRODUCTION,
                finding_ids=multi_findings,
                hotspot_ids=multi_ids,
                metadata={"multi_rule_hotspot_count": str(len(multi))},
            )
            conclusions.append(multi_conclusion)
            recommendations.append(
                _make_recommendation(
                    conclusion=multi_conclusion,
                    action_key="refactor-multi-rule-units",
                    title="Prefer multi-rule production units when refactoring",
                    action=(
                        "If refactoring for complexity, prefer production units that "
                        "match multiple rules so one change can address several "
                        "threshold crossings."
                    ),
                    rationale=(
                        "Multi-rule hotspots are identified by overlapping rule IDs "
                        "on a single source unit."
                    ),
                    conditional=True,
                )
            )

    # Test maintainability observation — must not affect production-health narrative.
    if test_refs:
        test_finding_ids = tuple(sorted(item.finding_id for item in test_refs))
        test_conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_TEST_MAINTAINABILITY,
            kind=TechnicalDebtConclusionKind.TEST_MAINTAINABILITY,
            audience=TechnicalDebtConclusionAudience.TEST_OBSERVATION,
            title="Test-source complexity findings observed",
            summary=(
                f"{len(test_refs)} test-source complexity finding(s) are present and "
                "exposed separately from the production-primary inventory."
            ),
            technical_interpretation=(
                "Test maintainability observation only. These findings must not be "
                "interpreted as production-health defects without separate review."
            ),
            source_role=TechnicalDebtSourceRole.TEST,
            theme_ids=tuple(theme.theme_id for theme in test_themes),
            finding_ids=test_finding_ids,
            hotspot_ids=tuple(item.hotspot_id for item in test_hotspots[:20]),
            metadata={"test_finding_count": str(len(test_refs))},
        )
        conclusions.append(test_conclusion)
        recommendations.append(
            _make_recommendation(
                conclusion=test_conclusion,
                action_key="review-test-complexity-separately",
                title="Review test complexity separately from production health",
                action=(
                    "If test maintainability is in scope, review test-role findings "
                    "separately; do not treat them as production-health conclusions."
                ),
                rationale=(
                    "Test findings are inventory-partitioned and excluded from the "
                    "primary production synthesis narrative."
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
            key=lambda item: (item.audience.value, item.title, item.recommendation_id),
        )
    )

    status = (
        TechnicalDebtSynthesisStatus.EMPTY
        if not production_refs and not test_refs
        else TechnicalDebtSynthesisStatus.SUCCEEDED
    )
    return TechnicalDebtSynthesisResult(
        status=status,
        synthesis_version=SYNTHESIS_VERSION,
        themes=themes,
        theme_ids=tuple(theme.theme_id for theme in themes),
        concentration_facts=concentration_facts,
        conclusions=linked_conclusions,
        conclusion_ids=tuple(item.conclusion_id for item in linked_conclusions),
        recommendations=ordered_recs,
        recommendation_ids=tuple(item.recommendation_id for item in ordered_recs),
        diagnostics=(),
    )
