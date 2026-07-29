"""Deterministic Performance synthesis from assessment inventory (Phase 4.9.5).

Consumes Performance Assessment inventories, Findings, and rule-execution facts
only. Does not re-read repository files, recollect evidence, or reevaluate
hygiene rules.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.findings.models import Finding
from codestrata.domain.performance.assessment.enums import PerformanceAssessmentStatus
from codestrata.domain.performance.assessment.models import (
    PerformanceFamilyInventory,
    PerformanceFindingInventory,
    PerformanceLimitation,
    PerformanceRuleInventory,
)
from codestrata.domain.performance.ids import (
    HYGIENE_RULE_IDS,
    RULE_BLOCKING_SLEEP,
    RULE_BROAD_FOUNDATIONS,
    RULE_CACHING,
    RULE_CONCURRENCY,
    RULE_CONCURRENCY_WITHOUT_CONFIG,
    RULE_CONFIG_CONTROLS,
    RULE_DATA_ACCESS,
    RULE_DATA_ACCESS_WITHOUT_BATCHING,
    RULE_DATA_WITHOUT_CACHING,
    RULE_EXECUTOR_CONFIG,
    RULE_FRONTEND_BUNDLE,
    RULE_FRONTEND_LAZY,
    RULE_FRONTEND_LIMITED,
    RULE_LIMITED_CONTROLS,
    RULE_MULTIPLE_DATA_ACCESS,
    RULE_OBSERVABILITY,
    RULE_RESOURCE_MGMT,
    RULE_RESOURCES_WITHOUT_MGMT,
    RULE_SYNC_IO,
    RULE_WITHOUT_OBSERVABILITY,
)
from codestrata.domain.performance.synthesis.enums import (
    PerformanceConclusionAudience,
    PerformanceConclusionKind,
    PerformanceRecommendationKind,
    PerformanceSynthesisStatus,
    PerformanceThemeKind,
    PerformanceThemeScope,
)
from codestrata.domain.performance.synthesis.identifiers import (
    POLICY_BLOCKING,
    POLICY_BROAD,
    POLICY_CACHING,
    POLICY_CONCURRENCY,
    POLICY_CONFIGURATION,
    POLICY_DATA_ACCESS,
    POLICY_DISABLED,
    POLICY_FRONTEND,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_LIMITED,
    POLICY_NO_FINDINGS,
    POLICY_OBSERVABILITY,
    POLICY_RESOURCE,
    POLICY_RULE_EXECUTION,
    POLICY_UNSUPPORTED_SCOPE,
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.performance.synthesis.models import (
    PerformanceConclusion,
    PerformanceRecommendation,
    PerformanceSynthesisResult,
    PerformanceTheme,
)

_FINDING_REF_LIMIT = 32

_FORBIDDEN_WORDS = (
    "is performant",
    "are performant",
    "performant",
    "bottleneck",
    "latency bottleneck",
    "is slow",
    "repository is slow",
    "performance score",
    "performance grade",
    "readiness score",
    "production ready",
    "production-ready under load",
    "scalable",
    "free of latency",
    "modernize",
    "modernisation",
    "modernization path",
    "migrate to",
    "hotspot",
)


def _bound_ids(values: Sequence[str], limit: int) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))[:limit]


def _assert_safe_text(*parts: str) -> None:
    joined = " ".join(parts).lower()
    sanitized = (
        joined.replace("does not establish that the repository is performant", "")
        .replace("do not establish that the repository is performant", "")
        .replace("does not mean the repository is performant", "")
        .replace("the repository is performant", "")
        .replace("does not establish performance", "")
        .replace("do not establish performance", "")
        .replace("without claiming the repository is performant", "")
        .replace("from claiming the repository is performant", "")
        .replace("claiming the repository is performant", "")
        .replace("prescribing enablement paths", "")
        .replace("not performance scores", "")
        .replace("performance scoring", "")
        .replace("performance scores", "")
        .replace("zero findings does not mean", "")
        .replace("does not claim bottlenecks", "")
        .replace("free of latency risk", "")
        .replace("production-ready under load", "")
        .replace("is performant", "")
        .replace("are performant", "")
        .replace("not performant", "")
        .replace("performant", "")
        .replace("scalable", "")
        .replace("bottleneck", "")
        .replace("hotspot", "")
        .replace("modernization path", "")
        .replace("modernize", "")
        .replace("modernisation", "")
    )
    for phrase in _FORBIDDEN_WORDS:
        if phrase in sanitized:
            raise ValueError(f"forbidden synthesis wording: {phrase}")


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: PerformanceConclusionKind,
    audience: PerformanceConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
    confidence: str = "high",
    metadata: dict[str, str] | None = None,
) -> PerformanceConclusion:
    _assert_safe_text(title, summary, technical_interpretation)
    support = tuple(theme_ids) + tuple(finding_ids) + tuple(rule_ids)
    return PerformanceConclusion(
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
        theme_ids=_bound_ids(theme_ids, _FINDING_REF_LIMIT),
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=_bound_ids(rule_ids, _FINDING_REF_LIMIT),
        confidence=confidence,
        metadata=metadata or {},
    )


def _make_recommendation(
    *,
    kind: PerformanceRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conclusion_ids: Sequence[str],
    audience: PerformanceConclusionAudience,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
) -> PerformanceRecommendation:
    _assert_safe_text(title, action, rationale)
    return PerformanceRecommendation(
        recommendation_id=build_recommendation_id(
            conclusion_ids=conclusion_ids,
            action_key=action_key,
        ),
        kind=kind,
        title=title,
        action=action,
        rationale=rationale,
        conclusion_ids=_bound_ids(conclusion_ids, _FINDING_REF_LIMIT),
        theme_ids=_bound_ids(theme_ids, _FINDING_REF_LIMIT),
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=_bound_ids(rule_ids, _FINDING_REF_LIMIT),
        audience=audience,
    )


def _findings_for_rules(
    findings: Sequence[Finding],
    rule_ids: Sequence[str],
) -> tuple[Finding, ...]:
    wanted = set(rule_ids)
    return tuple(item for item in findings if item.rule_id in wanted)


def _rule_theme(
    *,
    kind: PerformanceThemeKind,
    title: str,
    description: str,
    findings: Sequence[Finding],
    ordering_key: str,
) -> PerformanceTheme | None:
    if not findings:
        return None
    _assert_safe_text(title, description)
    finding_ids = tuple(item.id for item in findings)
    rule_ids = tuple(sorted({item.rule_id for item in findings}))
    return PerformanceTheme(
        theme_id=build_theme_id(
            kind=kind.value,
            scope=PerformanceThemeScope.HYGIENE.value,
            subject=rule_ids[0] if rule_ids else "",
        ),
        kind=kind,
        title=title,
        description=description,
        scope=PerformanceThemeScope.HYGIENE,
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=rule_ids,
        counts={"finding_count": len(findings)},
        ordering_key=ordering_key,
    )


def _posture_summary(
    *,
    findings_count: int,
    rules_executed: int,
    rules_matched: int,
    families_observed: int,
) -> str:
    if findings_count == 0:
        text = (
            f"{rules_executed} Performance Hygiene rules executed with zero "
            "findings in the supported repository evidence scope. This "
            "summarizes performance signals only and does not establish that "
            "the repository is performant."
        )
    else:
        text = (
            f"Performance Hygiene inventory shows {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across {rules_matched} matched "
            f"rule{'s' if rules_matched != 1 else ''} of {rules_executed} executed"
            f" ({families_observed} performance famil"
            f"{'y' if families_observed == 1 else 'ies'} observed). "
            "Implications remain informational to low and do not establish "
            "that the repository is performant."
        )
    _assert_safe_text(text)
    return text


def _link_recommendations(
    conclusions: list[PerformanceConclusion],
    recommendations: Sequence[PerformanceRecommendation],
) -> list[PerformanceConclusion]:
    by_conclusion: dict[str, list[str]] = {}
    for item in recommendations:
        for conclusion_id in item.conclusion_ids:
            by_conclusion.setdefault(conclusion_id, []).append(item.recommendation_id)
    linked: list[PerformanceConclusion] = []
    for conclusion in conclusions:
        ids = tuple(sorted(set(by_conclusion.get(conclusion.conclusion_id, ()))))
        if not ids:
            linked.append(conclusion)
            continue
        linked.append(conclusion.model_copy(update={"recommendation_ids": ids}))
    return linked


def _emit_finding_theme(
    *,
    repository_id: str,
    themes: list[PerformanceTheme],
    conclusions: list[PerformanceConclusion],
    recommendations: list[PerformanceRecommendation],
    findings: Sequence[Finding],
    theme_kind: PerformanceThemeKind,
    conclusion_kind: PerformanceConclusionKind,
    recommendation_kind: PerformanceRecommendationKind,
    policy_id: str,
    title: str,
    description: str,
    conclusion_title: str,
    technical_interpretation: str,
    recommendation_title: str,
    recommendation_action: str,
    recommendation_rationale: str,
    action_key: str,
    rule_ids: Sequence[str],
    ordering_key: str,
    confidence: str = "high",
    audience: PerformanceConclusionAudience = PerformanceConclusionAudience.HYGIENE,
) -> None:
    theme = _rule_theme(
        kind=theme_kind,
        title=title,
        description=description,
        findings=findings,
        ordering_key=ordering_key,
    )
    if theme is None:
        return
    themes.append(theme)
    conclusion = _make_conclusion(
        repository_id=repository_id,
        policy_id=policy_id,
        kind=conclusion_kind,
        audience=audience,
        title=conclusion_title,
        summary=theme.description,
        technical_interpretation=technical_interpretation,
        theme_ids=(theme.theme_id,),
        finding_ids=theme.finding_ids,
        rule_ids=rule_ids,
        confidence=confidence,
    )
    conclusions.append(conclusion)
    recommendations.append(
        _make_recommendation(
            kind=recommendation_kind,
            action_key=action_key,
            title=recommendation_title,
            action=recommendation_action,
            rationale=recommendation_rationale,
            conclusion_ids=(conclusion.conclusion_id,),
            audience=audience,
            theme_ids=(theme.theme_id,),
            finding_ids=theme.finding_ids,
            rule_ids=rule_ids,
        )
    )


def synthesize_performance(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: PerformanceAssessmentStatus,
    findings: Sequence[Finding] = (),
    finding_inventory: PerformanceFindingInventory | None = None,
    rule_inventory: PerformanceRuleInventory | None = None,
    performance_family_inventory: PerformanceFamilyInventory | None = None,
    limitations: Sequence[PerformanceLimitation] = (),
    evidence_status: str = "",
    include_synthesis: bool = True,
) -> PerformanceSynthesisResult:
    """Build deterministic Performance synthesis from inventory facts."""

    if not include_synthesis:
        return PerformanceSynthesisResult(
            status=PerformanceSynthesisStatus.NOT_REQUESTED,
            synthesis_version=SYNTHESIS_VERSION,
            diagnostics=("synthesis_not_requested",),
        )

    if (
        not pack_enabled
        or section_status is PerformanceAssessmentStatus.DISABLED
        or section_status is PerformanceAssessmentStatus.NOT_REQUESTED
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=PerformanceConclusionKind.SYNTHESIS_DISABLED,
            audience=PerformanceConclusionAudience.STATUS,
            title="Performance synthesis disabled",
            summary=(
                "Performance synthesis was not generated because the "
                "Performance pack or analysis section is disabled."
            ),
            technical_interpretation=(
                "Enable rules.performance and analysis.performance to produce "
                "inventory-derived synthesis."
            ),
        )
        return PerformanceSynthesisResult(
            status=PerformanceSynthesisStatus.DISABLED,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        PerformanceAssessmentStatus.INSUFFICIENT_EVIDENCE,
        PerformanceAssessmentStatus.FAILED,
        PerformanceAssessmentStatus.NOT_APPLICABLE,
    }:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=PerformanceConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=PerformanceConclusionAudience.STATUS,
            title="Insufficient Performance evidence for synthesis",
            summary=(
                "Performance synthesis could not be fully generated because "
                f"the assessment status is {section_status.value}."
            ),
            technical_interpretation=(
                "Provide usable repository-performance evidence and successful "
                "rule evaluation before interpreting Performance synthesis."
            ),
        )
        return PerformanceSynthesisResult(
            status=PerformanceSynthesisStatus.INSUFFICIENT_EVIDENCE,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    inventory = finding_inventory or PerformanceFindingInventory(
        finding_ids=tuple(item.id for item in ordered),
        finding_count=len(ordered),
    )
    rules = rule_inventory or PerformanceRuleInventory()
    families = performance_family_inventory or PerformanceFamilyInventory()
    rules_executed = rules.rules_executed or sum(1 for item in rules.entries if item.executed)
    if rules_executed == 0 and pack_enabled:
        rules_executed = len(HYGIENE_RULE_IDS)
    rules_matched = rules.rules_matched or sum(
        1 for item in rules.entries if item.evaluation_status == "matched"
    )
    rules_not_matched = rules.rules_not_matched
    finding_ids = tuple(inventory.finding_ids) or tuple(item.id for item in ordered)
    findings_count = inventory.finding_count or len(ordered)
    families_observed = families.families_observed

    themes: list[PerformanceTheme] = []
    conclusions: list[PerformanceConclusion] = []
    recommendations: list[PerformanceRecommendation] = []

    if findings_count == 0:
        landscape_desc = (
            f"{rules_executed} Performance Hygiene rules executed and produced "
            "no findings within the supported repository evidence scope."
        )
    else:
        landscape_desc = (
            f"The supported Performance Hygiene rules produced {findings_count} "
            f"finding{'' if findings_count == 1 else 's'} across "
            f"{rules_matched} matched rule{'s' if rules_matched != 1 else ''}."
        )
    _assert_safe_text(landscape_desc)
    landscape = PerformanceTheme(
        theme_id=build_theme_id(
            kind=PerformanceThemeKind.PERFORMANCE_HYGIENE_LANDSCAPE.value,
            scope=PerformanceThemeScope.REPOSITORY.value,
        ),
        kind=PerformanceThemeKind.PERFORMANCE_HYGIENE_LANDSCAPE,
        title="Performance hygiene landscape",
        description=landscape_desc,
        scope=PerformanceThemeScope.REPOSITORY,
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        rule_ids=tuple(HYGIENE_RULE_IDS),
        counts={
            "finding_count": findings_count,
            "rules_executed": rules_executed,
            "rules_matched": rules_matched,
            "families_observed": families_observed,
        },
        ordering_key="00_landscape",
    )
    themes.append(landscape)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LANDSCAPE,
            kind=PerformanceConclusionKind.PERFORMANCE_HYGIENE_LANDSCAPE_IDENTIFIED,
            audience=PerformanceConclusionAudience.REPOSITORY,
            title="Performance hygiene landscape identified",
            summary=landscape_desc,
            technical_interpretation=(
                "This conclusion summarizes supported Performance Hygiene "
                "rule execution and finding counts only."
            ),
            theme_ids=(landscape.theme_id,),
            finding_ids=finding_ids,
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    coverage_desc = (
        f"Rule execution coverage: {rules_executed} executed, "
        f"{rules_matched} matched, {rules_not_matched} not matched"
        + (
            f"; evidence status {evidence_status}."
            if evidence_status
            else " within the registered hygiene pack."
        )
    )
    _assert_safe_text(coverage_desc)
    coverage_theme = PerformanceTheme(
        theme_id=build_theme_id(
            kind=PerformanceThemeKind.RULE_EXECUTION_COVERAGE.value,
            scope=PerformanceThemeScope.COVERAGE.value,
        ),
        kind=PerformanceThemeKind.RULE_EXECUTION_COVERAGE,
        title="Rule execution coverage",
        description=coverage_desc,
        scope=PerformanceThemeScope.COVERAGE,
        rule_ids=tuple(HYGIENE_RULE_IDS),
        counts={
            "rules_planned": rules.rules_planned or len(HYGIENE_RULE_IDS),
            "rules_executed": rules_executed,
            "rules_matched": rules_matched,
            "rules_not_matched": rules_not_matched,
            "rules_not_applicable": rules.rules_not_applicable,
            "rules_failed": rules.rules_failed,
        },
        ordering_key="01_rule_execution",
    )
    themes.append(coverage_theme)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_RULE_EXECUTION,
            kind=PerformanceConclusionKind.RULE_EXECUTION_SUMMARY,
            audience=PerformanceConclusionAudience.COVERAGE,
            title="Performance Hygiene rule execution summary",
            summary=coverage_desc,
            technical_interpretation=(
                "Applicable registered hygiene rules versus matched outcomes "
                "are inventory facts, not performance scores."
            ),
            theme_ids=(coverage_theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    data_findings = _findings_for_rules(
        ordered,
        (RULE_DATA_ACCESS, RULE_MULTIPLE_DATA_ACCESS, RULE_DATA_ACCESS_WITHOUT_BATCHING),
    )
    blocking_findings = _findings_for_rules(
        ordered,
        (RULE_BLOCKING_SLEEP, RULE_SYNC_IO),
    )
    caching_findings = _findings_for_rules(
        ordered,
        (RULE_CACHING, RULE_DATA_WITHOUT_CACHING),
    )
    concurrency_findings = _findings_for_rules(
        ordered,
        (RULE_CONCURRENCY, RULE_EXECUTOR_CONFIG, RULE_CONCURRENCY_WITHOUT_CONFIG),
    )
    resource_findings = _findings_for_rules(
        ordered,
        (RULE_RESOURCE_MGMT, RULE_RESOURCES_WITHOUT_MGMT),
    )
    frontend_findings = _findings_for_rules(
        ordered,
        (RULE_FRONTEND_BUNDLE, RULE_FRONTEND_LAZY, RULE_FRONTEND_LIMITED),
    )
    observability_findings = _findings_for_rules(
        ordered,
        (RULE_OBSERVABILITY, RULE_WITHOUT_OBSERVABILITY),
    )
    config_findings = _findings_for_rules(ordered, (RULE_CONFIG_CONTROLS,))
    broad_findings = _findings_for_rules(ordered, (RULE_BROAD_FOUNDATIONS,))
    limited_findings = _findings_for_rules(ordered, (RULE_LIMITED_CONTROLS,))

    if data_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=data_findings,
            theme_kind=PerformanceThemeKind.DATA_ACCESS_FOUNDATIONS,
            conclusion_kind=PerformanceConclusionKind.DATA_ACCESS_FOUNDATIONS_OBSERVED,
            recommendation_kind=PerformanceRecommendationKind.REVIEW_DATA_ACCESS_FOUNDATION_SIGNALS,
            policy_id=POLICY_DATA_ACCESS,
            title="Data access foundations",
            description=(
                f"{len(data_findings)} finding"
                f"{'' if len(data_findings) == 1 else 's'} report data access "
                "foundation signals in repository evidence."
            ),
            conclusion_title="Data access foundations observed",
            technical_interpretation=(
                "Data access markers are repository-observable performance "
                "signals. They do not establish that the repository is "
                "performant."
            ),
            recommendation_title="Review data access foundation signals",
            recommendation_action=(
                "Review the linked Performance Hygiene findings and confirm "
                "the observed data access markers remain intentional."
            ),
            recommendation_rationale=(
                "PERF-001/002/003 matched on data access signals; review keeps "
                "inventory signals actionable without claiming the repository "
                "is performant."
            ),
            action_key="review-data-access-foundation-signals",
            rule_ids=tuple(sorted({item.rule_id for item in data_findings})),
            ordering_key="10_data_access",
        )

    if blocking_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=blocking_findings,
            theme_kind=PerformanceThemeKind.BLOCKING_OPERATIONS,
            conclusion_kind=PerformanceConclusionKind.BLOCKING_OPERATIONS_OBSERVED,
            recommendation_kind=PerformanceRecommendationKind.REVIEW_BLOCKING_OPERATION_SIGNALS,
            policy_id=POLICY_BLOCKING,
            title="Blocking operations",
            description=(
                f"{len(blocking_findings)} finding"
                f"{'' if len(blocking_findings) == 1 else 's'} report blocking "
                "operation signals in repository evidence."
            ),
            conclusion_title="Blocking operations observed",
            technical_interpretation=(
                "Blocking operation markers describe repository signals only. "
                "They do not establish that the repository is performant."
            ),
            recommendation_title="Review blocking operation signals",
            recommendation_action=(
                "Review the linked blocking-operation findings and confirm "
                "each observed marker remains intentional."
            ),
            recommendation_rationale=(
                "PERF-010/011 matched on blocking signals; review is "
                "observation-oriented without claiming the repository is "
                "performant."
            ),
            action_key="review-blocking-operation-signals",
            rule_ids=tuple(sorted({item.rule_id for item in blocking_findings})),
            ordering_key="11_blocking",
        )

    if caching_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=caching_findings,
            theme_kind=PerformanceThemeKind.CACHING_FOUNDATIONS,
            conclusion_kind=PerformanceConclusionKind.CACHING_FOUNDATIONS_OBSERVED,
            recommendation_kind=PerformanceRecommendationKind.REVIEW_CACHING_FOUNDATION_SIGNALS,
            policy_id=POLICY_CACHING,
            title="Caching foundations",
            description=(
                f"{len(caching_findings)} finding"
                f"{'' if len(caching_findings) == 1 else 's'} report caching "
                "foundation signals."
            ),
            conclusion_title="Caching foundations observed",
            technical_interpretation=(
                "Caching markers are repository signals only. They do not "
                "establish that the repository is performant."
            ),
            recommendation_title="Review caching foundation signals",
            recommendation_action=(
                "Review the linked caching findings and confirm observed "
                "markers remain intentional."
            ),
            recommendation_rationale=(
                "PERF-020/021 matched on caching signals; review stays observation-oriented."
            ),
            action_key="review-caching-foundation-signals",
            rule_ids=tuple(sorted({item.rule_id for item in caching_findings})),
            ordering_key="12_caching",
        )

    if concurrency_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=concurrency_findings,
            theme_kind=PerformanceThemeKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING,
            conclusion_kind=(
                PerformanceConclusionKind.CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_OBSERVED
            ),
            recommendation_kind=(
                PerformanceRecommendationKind.REVIEW_CONCURRENCY_AND_ASYNCHRONOUS_PROCESSING_SIGNALS
            ),
            policy_id=POLICY_CONCURRENCY,
            title="Concurrency and asynchronous processing",
            description=(
                f"{len(concurrency_findings)} finding"
                f"{'' if len(concurrency_findings) == 1 else 's'} report "
                "concurrency or asynchronous processing signals."
            ),
            conclusion_title="Concurrency and asynchronous processing observed",
            technical_interpretation=(
                "Concurrency markers describe declared processing signals. "
                "They do not establish that the repository is performant."
            ),
            recommendation_title="Review concurrency and asynchronous processing signals",
            recommendation_action=(
                "Review the linked concurrency findings and confirm each "
                "observed marker remains intentional."
            ),
            recommendation_rationale=(
                "PERF-030/031/032 matched on concurrency signals; review does "
                "not prescribe architecture changes."
            ),
            action_key="review-concurrency-and-asynchronous-processing-signals",
            rule_ids=tuple(sorted({item.rule_id for item in concurrency_findings})),
            ordering_key="13_concurrency",
        )

    if resource_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=resource_findings,
            theme_kind=PerformanceThemeKind.RESOURCE_MANAGEMENT,
            conclusion_kind=PerformanceConclusionKind.RESOURCE_MANAGEMENT_OBSERVED,
            recommendation_kind=PerformanceRecommendationKind.REVIEW_RESOURCE_MANAGEMENT_SIGNALS,
            policy_id=POLICY_RESOURCE,
            title="Resource management",
            description=(
                f"{len(resource_findings)} finding"
                f"{'' if len(resource_findings) == 1 else 's'} report resource "
                "management signals."
            ),
            conclusion_title="Resource management observed",
            technical_interpretation=(
                "Resource management markers are repository signals only and "
                "do not establish that the repository is performant."
            ),
            recommendation_title="Review resource management signals",
            recommendation_action=(
                "Review the linked resource management findings and confirm "
                "observed markers remain intentional."
            ),
            recommendation_rationale=(
                "PERF-040/041 matched on resource management signals; review "
                "stays observation-oriented."
            ),
            action_key="review-resource-management-signals",
            rule_ids=tuple(sorted({item.rule_id for item in resource_findings})),
            ordering_key="14_resource",
        )

    if frontend_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=frontend_findings,
            theme_kind=PerformanceThemeKind.FRONTEND_PERFORMANCE_CONTROLS,
            conclusion_kind=PerformanceConclusionKind.FRONTEND_PERFORMANCE_CONTROLS_OBSERVED,
            recommendation_kind=(
                PerformanceRecommendationKind.REVIEW_FRONTEND_PERFORMANCE_CONTROL_SIGNALS
            ),
            policy_id=POLICY_FRONTEND,
            title="Frontend performance controls",
            description=(
                f"{len(frontend_findings)} finding"
                f"{'' if len(frontend_findings) == 1 else 's'} report frontend "
                "performance control signals."
            ),
            conclusion_title="Frontend performance controls observed",
            technical_interpretation=(
                "Frontend control markers describe repository signals. They "
                "do not establish that the repository is performant."
            ),
            recommendation_title="Review frontend performance control signals",
            recommendation_action=(
                "Review the linked frontend performance findings and confirm "
                "observed markers remain intentional."
            ),
            recommendation_rationale=(
                "PERF-050/051/052 matched on frontend control signals; review "
                "stays observation-oriented."
            ),
            action_key="review-frontend-performance-control-signals",
            rule_ids=tuple(sorted({item.rule_id for item in frontend_findings})),
            ordering_key="15_frontend",
        )

    if observability_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=observability_findings,
            theme_kind=PerformanceThemeKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING,
            conclusion_kind=(
                PerformanceConclusionKind.PERFORMANCE_OBSERVABILITY_AND_PROFILING_OBSERVED
            ),
            recommendation_kind=(
                PerformanceRecommendationKind.VALIDATE_OBSERVED_PERFORMANCE_OBSERVABILITY_SIGNALS
            ),
            policy_id=POLICY_OBSERVABILITY,
            title="Performance observability and profiling",
            description=(
                f"{len(observability_findings)} finding"
                f"{'' if len(observability_findings) == 1 else 's'} report "
                "performance observability or profiling signals."
            ),
            conclusion_title="Performance observability and profiling observed",
            technical_interpretation=(
                "Observability and profiling markers are inventory signals. "
                "They do not establish that the repository is performant."
            ),
            recommendation_title="Validate observed performance observability signals",
            recommendation_action=(
                "Validate observed performance observability and profiling "
                "findings and confirm each marker remains intentional."
            ),
            recommendation_rationale=(
                "PERF-060/061 matched on observability signals; validation "
                "stays observation-oriented."
            ),
            action_key="validate-observed-performance-observability-signals",
            rule_ids=tuple(sorted({item.rule_id for item in observability_findings})),
            ordering_key="16_observability",
        )

    if config_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=config_findings,
            theme_kind=PerformanceThemeKind.CONFIGURATION_CONTROLS,
            conclusion_kind=PerformanceConclusionKind.CONFIGURATION_CONTROLS_OBSERVED,
            recommendation_kind=(
                PerformanceRecommendationKind.VALIDATE_OBSERVED_CONFIGURATION_CONTROLS
            ),
            policy_id=POLICY_CONFIGURATION,
            title="Configuration controls",
            description=(
                f"{len(config_findings)} finding"
                f"{'' if len(config_findings) == 1 else 's'} report "
                "configuration control signals."
            ),
            conclusion_title="Configuration controls observed",
            technical_interpretation=(
                "Configuration control markers are inventory signals. They "
                "do not establish that the repository is performant."
            ),
            recommendation_title="Validate observed configuration controls",
            recommendation_action=(
                "Validate observed configuration control findings and confirm "
                "each marker remains intentional."
            ),
            recommendation_rationale=(
                "PERF-070 matched on configuration control signals; validation "
                "stays observation-oriented."
            ),
            action_key="validate-observed-configuration-controls",
            rule_ids=(RULE_CONFIG_CONTROLS,),
            ordering_key="17_configuration",
        )

    if broad_findings or families_observed >= 3:
        if broad_findings:
            desc = (
                f"{len(broad_findings)} finding"
                f"{'' if len(broad_findings) == 1 else 's'} report broad "
                "performance foundations across multiple performance families."
            )
            finding_ids_for_theme = tuple(item.id for item in broad_findings)
            rule_ids_for_theme: tuple[str, ...] = (RULE_BROAD_FOUNDATIONS,)
        else:
            desc = (
                f"Performance family inventory observes {families_observed} "
                "distinct performance families from Findings metadata."
            )
            finding_ids_for_theme = finding_ids
            rule_ids_for_theme = tuple(sorted({item.rule_id for item in ordered})) or tuple(
                HYGIENE_RULE_IDS
            )
        _assert_safe_text(desc)
        theme = PerformanceTheme(
            theme_id=build_theme_id(
                kind=PerformanceThemeKind.BROAD_PERFORMANCE_FOUNDATIONS.value,
                scope=PerformanceThemeScope.COVERAGE.value,
                subject="families",
            ),
            kind=PerformanceThemeKind.BROAD_PERFORMANCE_FOUNDATIONS,
            title="Broad performance foundations",
            description=desc,
            scope=PerformanceThemeScope.COVERAGE,
            finding_ids=_bound_ids(finding_ids_for_theme, _FINDING_REF_LIMIT),
            rule_ids=rule_ids_for_theme,
            counts={
                "finding_count": len(broad_findings),
                "families_observed": families_observed,
            },
            ordering_key="18_broad_foundations",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_BROAD,
            kind=PerformanceConclusionKind.BROAD_PERFORMANCE_FOUNDATIONS_OBSERVED,
            audience=PerformanceConclusionAudience.COVERAGE,
            title="Broad performance foundations observed",
            summary=theme.description,
            technical_interpretation=(
                "Family coverage summarizes distinct performance signal "
                "groups. It does not establish that the repository is "
                "performant."
            ),
            theme_ids=(theme.theme_id,),
            finding_ids=theme.finding_ids,
            rule_ids=rule_ids_for_theme,
            confidence="medium",
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=PerformanceRecommendationKind.REVIEW_BROAD_PERFORMANCE_FOUNDATIONS,
                action_key="review-broad-performance-foundations",
                title="Review broad performance foundations",
                action=(
                    "Review the linked Findings and confirm the observed "
                    "performance families remain intentional for this repository."
                ),
                rationale=(
                    "Broad foundation themes summarize inventory facts without "
                    "claiming the repository is performant."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=PerformanceConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=rule_ids_for_theme,
            )
        )

    if limited_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=limited_findings,
            theme_kind=PerformanceThemeKind.LIMITED_SUPPORTING_CONTROLS,
            conclusion_kind=PerformanceConclusionKind.LIMITED_SUPPORTING_CONTROLS_OBSERVED,
            recommendation_kind=PerformanceRecommendationKind.REVIEW_LIMITED_SUPPORTING_CONTROLS,
            policy_id=POLICY_LIMITED,
            title="Limited supporting controls",
            description=(
                f"{len(limited_findings)} finding"
                f"{'' if len(limited_findings) == 1 else 's'} report limited "
                "supporting performance controls."
            ),
            conclusion_title="Limited supporting controls observed",
            technical_interpretation=(
                "Limited control markers describe sparse performance signals. "
                "They do not establish that the repository is performant."
            ),
            recommendation_title="Review limited supporting controls",
            recommendation_action=(
                "Review the linked findings and confirm whether limited "
                "control markers are expected for this repository."
            ),
            recommendation_rationale=(
                "PERF-072 matched on limited supporting controls; review "
                "stays observation-oriented."
            ),
            action_key="review-limited-supporting-controls",
            rule_ids=(RULE_LIMITED_CONTROLS,),
            ordering_key="19_limited_controls",
            confidence="medium",
        )

    if findings_count == 0 and rules_executed > 0:
        theme = PerformanceTheme(
            theme_id=build_theme_id(
                kind=PerformanceThemeKind.NO_PERFORMANCE_FINDINGS.value,
                scope=PerformanceThemeScope.STATUS.value,
            ),
            kind=PerformanceThemeKind.NO_PERFORMANCE_FINDINGS,
            title="No performance findings in supported scope",
            description=(
                f"No Performance Hygiene findings were emitted by the "
                f"{rules_executed} enabled rules within the supported "
                "repository evidence scope."
            ),
            scope=PerformanceThemeScope.STATUS,
            rule_ids=tuple(HYGIENE_RULE_IDS),
            counts={"rules_executed": rules_executed, "finding_count": 0},
            ordering_key="20_no_findings",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_FINDINGS,
            kind=PerformanceConclusionKind.NO_PERFORMANCE_FINDINGS_IN_SUPPORTED_SCOPE,
            audience=PerformanceConclusionAudience.STATUS,
            title="No performance findings in supported scope",
            summary=theme.description,
            technical_interpretation=(
                "Zero findings is a neutral inventory outcome for enabled "
                "hygiene rules. It does not establish that the repository is "
                "performant."
            ),
            theme_ids=(theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=(
                    PerformanceRecommendationKind.ACKNOWLEDGE_NO_PERFORMANCE_FINDINGS_IN_SUPPORTED_SCOPE
                ),
                action_key="acknowledge-no-performance-findings",
                title="Acknowledge zero performance findings in supported scope",
                action=(
                    "Treat zero Performance Hygiene findings as a bounded "
                    "inventory outcome for the supported evidence and rule pack "
                    "only."
                ),
                rationale=(
                    "Neutral acknowledgment prevents overstating risk or "
                    "claiming the repository is performant from an empty "
                    "finding set."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=PerformanceConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
                rule_ids=list(HYGIENE_RULE_IDS),
            )
        )

    if limitations:
        theme = PerformanceTheme(
            theme_id=build_theme_id(
                kind=PerformanceThemeKind.UNSUPPORTED_ANALYSIS_SCOPE.value,
                scope=PerformanceThemeScope.STATUS.value,
            ),
            kind=PerformanceThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
            title="Unsupported performance analysis scope",
            description=(
                f"{len(limitations)} documented limitation"
                f"{'' if len(limitations) == 1 else 's'} bound this assessment: "
                "performance scoring, AI/LLM execution, and report presentation "
                "remain out of scope."
            ),
            scope=PerformanceThemeScope.STATUS,
            counts={"limitation_count": len(limitations)},
            ordering_key="30_unsupported_scope",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_SCOPE,
            kind=PerformanceConclusionKind.UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE,
            audience=PerformanceConclusionAudience.STATUS,
            title="Unsupported performance analysis scope acknowledged",
            summary=theme.description,
            technical_interpretation=(
                "Synthesis uses repository-observable Performance Hygiene "
                "evidence only. Performance scores and AI execution are not "
                "evaluated."
            ),
            theme_ids=(theme.theme_id,),
            metadata={"limitation_count": str(len(limitations))},
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=(
                    PerformanceRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_PERFORMANCE_ANALYSIS_SCOPE
                ),
                action_key="acknowledge-unsupported-performance-analysis-scope",
                title="Acknowledge unsupported performance analysis scope",
                action=(
                    "Interpret Performance synthesis as hygiene inventory only "
                    "until additional analysis capabilities exist."
                ),
                rationale=(
                    "Documented limitations keep conclusions from claiming "
                    "the repository is performant or prescribing enablement "
                    "paths."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=PerformanceConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
            )
        )

    themes_sorted = tuple(sorted(themes, key=lambda item: (item.ordering_key, item.theme_id)))
    recommendations_sorted = tuple(
        sorted(recommendations, key=lambda item: (item.kind.value, item.recommendation_id))
    )
    deduped: list[PerformanceRecommendation] = []
    seen_kinds: set[str] = set()
    for item in recommendations_sorted:
        if item.kind.value in seen_kinds:
            continue
        seen_kinds.add(item.kind.value)
        deduped.append(item)
    conclusions_linked = _link_recommendations(conclusions, deduped)
    conclusions_sorted = tuple(
        sorted(
            conclusions_linked,
            key=lambda item: (item.kind.value, item.conclusion_id),
        )
    )
    posture = _posture_summary(
        findings_count=findings_count,
        rules_executed=rules_executed,
        rules_matched=rules_matched,
        families_observed=families_observed,
    )
    status = (
        PerformanceSynthesisStatus.EMPTY
        if findings_count == 0
        else PerformanceSynthesisStatus.SUCCEEDED
    )
    return PerformanceSynthesisResult(
        status=status,
        synthesis_version=SYNTHESIS_VERSION,
        overall_posture_summary=posture,
        themes=themes_sorted,
        theme_ids=tuple(item.theme_id for item in themes_sorted),
        conclusions=conclusions_sorted,
        conclusion_ids=tuple(item.conclusion_id for item in conclusions_sorted),
        recommendations=tuple(deduped),
        recommendation_ids=tuple(item.recommendation_id for item in deduped),
    )
