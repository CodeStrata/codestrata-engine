"""Deterministic Security synthesis from assessment inventory (Phase 4.5.5).

Consumes SecurityAssessmentSection inventory projections only. Does not
re-read repository files, recollect evidence, or reevaluate hygiene rules.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from codestrata.domain.security.assessment.enums import (
    SecurityAssessmentStatus,
    SecuritySourceRole,
)
from codestrata.domain.security.assessment.models import (
    SecurityDiagnosticsSummary,
    SecurityEvidenceSummary,
    SecurityFindingInventory,
    SecurityFindingReference,
    SecurityHotspotInventory,
    SecurityLimitation,
    SecurityRuleInventory,
)
from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.domain.security.synthesis.enums import (
    SecurityConclusionAudience,
    SecurityConclusionKind,
    SecurityRecommendationKind,
    SecuritySynthesisStatus,
    SecurityThemeKind,
    SecurityThemeScope,
)
from codestrata.domain.security.synthesis.identifiers import (
    POLICY_AUTHENTICATION,
    POLICY_CONCENTRATION,
    POLICY_CORS,
    POLICY_DEBUG,
    POLICY_DISABLED,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_LITERAL_CREDENTIAL,
    POLICY_NO_PRODUCTION,
    POLICY_PARTIAL_EVIDENCE,
    POLICY_PLACEHOLDER,
    POLICY_PRIVATE_KEY,
    POLICY_PRODUCTION_PRESENT,
    POLICY_TEST_FIXTURE,
    POLICY_TRANSPORT,
    POLICY_UNKNOWN_ROLE,
    POLICY_UNSUPPORTED_SCOPE,
    SYNTHESIS_VERSION,
    build_concentration_fact_id,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.security.synthesis.models import (
    SecurityConcentrationFact,
    SecurityConclusion,
    SecurityRecommendation,
    SecuritySynthesisResult,
    SecurityTheme,
)

_FINDING_REF_LIMIT = 32
_HOTSPOT_REF_LIMIT = 12
_DIAGNOSTIC_REF_LIMIT = 16
_TOP_HOTSPOT_LIMIT = 5

_FORBIDDEN_WORDS = (
    "secure repository",
    "security passed",
    "no vulnerabilities",
    "low risk",
    "repository is secure",
    "application is secure",
    "are secure",
    "compliant",
)


def _share(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return min(1.0, max(0.0, count / total))


def _bound_ids(values: Sequence[str], limit: int) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))[:limit]


def _assert_safe_text(*parts: str) -> None:
    joined = " ".join(parts).lower()
    sanitized = (
        joined.replace("does not mean the repository is secure", "")
        .replace("not a security certification", "")
        .replace("do not prove repository security", "")
        .replace("without claiming a full security assessment", "")
    )
    for phrase in _FORBIDDEN_WORDS:
        if phrase in sanitized:
            raise ValueError(f"forbidden synthesis wording: {phrase}")


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: SecurityConclusionKind,
    audience: SecurityConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    source_role: SecuritySourceRole,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    hotspot_ids: Sequence[str] = (),
    diagnostic_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
    concentration_fact_ids: Sequence[str] = (),
    metadata: dict[str, str] | None = None,
) -> SecurityConclusion:
    _assert_safe_text(title, summary, technical_interpretation)
    support = (
        tuple(theme_ids)
        + tuple(finding_ids)
        + tuple(hotspot_ids)
        + tuple(diagnostic_ids)
        + tuple(rule_ids)
        + tuple(concentration_fact_ids)
    )
    return SecurityConclusion(
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
        theme_ids=_bound_ids(theme_ids, _FINDING_REF_LIMIT),
        finding_ids=_bound_ids(finding_ids, _FINDING_REF_LIMIT),
        hotspot_ids=_bound_ids(hotspot_ids, _HOTSPOT_REF_LIMIT),
        diagnostic_ids=_bound_ids(diagnostic_ids, _DIAGNOSTIC_REF_LIMIT),
        rule_ids=_bound_ids(rule_ids, _FINDING_REF_LIMIT),
        concentration_fact_ids=_bound_ids(concentration_fact_ids, _FINDING_REF_LIMIT),
        metadata=metadata or {},
    )


def _make_recommendation(
    *,
    kind: SecurityRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conclusion_ids: Sequence[str],
    audience: SecurityConclusionAudience,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    hotspot_ids: Sequence[str] = (),
    diagnostic_ids: Sequence[str] = (),
) -> SecurityRecommendation:
    _assert_safe_text(title, action, rationale)
    return SecurityRecommendation(
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
        hotspot_ids=_bound_ids(hotspot_ids, _HOTSPOT_REF_LIMIT),
        diagnostic_ids=_bound_ids(diagnostic_ids, _DIAGNOSTIC_REF_LIMIT),
        audience=audience,
    )


def _findings_for_rules(
    refs: Sequence[SecurityFindingReference],
    rule_ids: set[str],
) -> tuple[SecurityFindingReference, ...]:
    return tuple(item for item in refs if item.rule_id in rule_ids)


def _partition(
    refs: Sequence[SecurityFindingReference],
) -> tuple[
    tuple[SecurityFindingReference, ...],
    tuple[SecurityFindingReference, ...],
    tuple[SecurityFindingReference, ...],
]:
    production = tuple(
        item for item in refs if item.source_role is SecuritySourceRole.PRODUCTION
    )
    test = tuple(
        item for item in refs if item.source_role is SecuritySourceRole.TEST
    )
    unknown = tuple(
        item for item in refs if item.source_role is SecuritySourceRole.UNKNOWN
    )
    return production, test, unknown


def _landscape_theme(
    *,
    production: Sequence[SecurityFindingReference],
    all_refs: Sequence[SecurityFindingReference],
    rules_executed: int,
    hotspot_count: int,
    evidence_status: str,
) -> SecurityTheme:
    categories = tuple(sorted({item.security_category.value for item in all_refs}))
    roles = tuple(sorted({item.source_role.value for item in all_refs}))
    rules = tuple(sorted({item.rule_id for item in all_refs}))
    prod_n = len(production)
    all_n = len(all_refs)
    if all_n == 0:
        description = (
            f"{rules_executed} repository security hygiene rules executed and "
            "produced no findings within the supported evidence scope."
        )
    else:
        extra = all_n - prod_n
        description = (
            f"The supported repository security hygiene rules produced "
            f"{prod_n} production findings and {extra} additional test, fixture, "
            "or unknown-role observations."
        )
    _assert_safe_text(description)
    return SecurityTheme(
        theme_id=build_theme_id(
            kind=SecurityThemeKind.SECURITY_HYGIENE_LANDSCAPE.value,
            scope=SecurityThemeScope.REPOSITORY.value,
        ),
        kind=SecurityThemeKind.SECURITY_HYGIENE_LANDSCAPE,
        title="Security hygiene landscape",
        description=description,
        scope=SecurityThemeScope.REPOSITORY,
        source_role=SecuritySourceRole.PRODUCTION,
        finding_ids=_bound_ids([item.finding_id for item in all_refs], _FINDING_REF_LIMIT),
        rule_ids=rules or tuple(HYGIENE_RULE_IDS),
        category_ids=categories,
        counts={
            "production_findings": prod_n,
            "all_findings": all_n,
            "rules_executed": rules_executed,
            "hotspot_count": hotspot_count,
            "categories_represented": len(categories),
            "source_roles_represented": len(roles) if roles else 0,
        },
        ordering_key="00_landscape",
    )


def _rule_theme(
    *,
    kind: SecurityThemeKind,
    title: str,
    description: str,
    refs: Sequence[SecurityFindingReference],
    scope: SecurityThemeScope = SecurityThemeScope.PRODUCTION,
    ordering_key: str,
) -> SecurityTheme | None:
    if not refs:
        return None
    _assert_safe_text(title, description)
    return SecurityTheme(
        theme_id=build_theme_id(
            kind=kind.value,
            scope=scope.value,
            subject=refs[0].rule_id,
        ),
        kind=kind,
        title=title,
        description=description,
        scope=scope,
        source_role=refs[0].source_role,
        finding_ids=_bound_ids([item.finding_id for item in refs], _FINDING_REF_LIMIT),
        rule_ids=tuple(sorted({item.rule_id for item in refs})),
        category_ids=tuple(
            sorted({item.security_category.value for item in refs})
        ),
        counts={"finding_count": len(refs)},
        ordering_key=ordering_key,
    )


def _concentration_facts(
    *,
    all_refs: Sequence[SecurityFindingReference],
    production: Sequence[SecurityFindingReference],
    hotspots: SecurityHotspotInventory,
) -> tuple[SecurityConcentrationFact, ...]:
    facts: list[SecurityConcentrationFact] = []
    total = len(all_refs)
    by_rule: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    by_role: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = defaultdict(int)
    for item in all_refs:
        by_rule[item.rule_id] += 1
        by_category[item.security_category.value] += 1
        by_role[item.source_role.value] += 1
        by_severity[item.severity] += 1

    for rule_id, count in sorted(by_rule.items()):
        facts.append(
            SecurityConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="findings_by_rule", subject=rule_id
                ),
                kind="findings_by_rule",
                subject=rule_id,
                count=count,
                total=total,
                share=_share(count, total),
                supporting_rule_ids=(rule_id,),
            )
        )
    for category, count in sorted(by_category.items()):
        facts.append(
            SecurityConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="findings_by_category", subject=category
                ),
                kind="findings_by_category",
                subject=category,
                count=count,
                total=total,
                share=_share(count, total),
            )
        )
    for role, count in sorted(by_role.items()):
        facts.append(
            SecurityConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="findings_by_source_role", subject=role
                ),
                kind="findings_by_source_role",
                subject=role,
                count=count,
                total=total,
                share=_share(count, total),
                source_role=(
                    SecuritySourceRole.PRODUCTION
                    if role == SecuritySourceRole.PRODUCTION.value
                    else SecuritySourceRole.TEST
                    if role == SecuritySourceRole.TEST.value
                    else SecuritySourceRole.UNKNOWN
                ),
            )
        )
    for severity, count in sorted(by_severity.items()):
        facts.append(
            SecurityConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="findings_by_severity", subject=severity
                ),
                kind="findings_by_severity",
                subject=severity,
                count=count,
                total=total,
                share=_share(count, total),
            )
        )

    prod_total = len(production)
    facts.append(
        SecurityConcentrationFact(
            fact_id=build_concentration_fact_id(
                kind="production_finding_ratio", subject="production"
            ),
            kind="production_finding_ratio",
            subject="production",
            count=prod_total,
            total=total,
            share=_share(prod_total, total),
            source_role=SecuritySourceRole.PRODUCTION,
        )
    )

    multi = [item for item in hotspots.hotspots if item.total_finding_count > 1]
    if hotspots.hotspots:
        top = hotspots.hotspots[0]
        facts.append(
            SecurityConcentrationFact(
                fact_id=build_concentration_fact_id(
                    kind="top_hotspot_finding_count", subject=top.path
                ),
                kind="top_hotspot_finding_count",
                subject=top.path,
                count=top.total_finding_count,
                total=total,
                share=_share(top.total_finding_count, total),
                supporting_hotspot_ids=(top.hotspot_id,),
                supporting_finding_ids=top.finding_ids[:_FINDING_REF_LIMIT],
            )
        )
    facts.append(
        SecurityConcentrationFact(
            fact_id=build_concentration_fact_id(
                kind="locations_with_multiple_findings",
                subject="repository",
            ),
            kind="locations_with_multiple_findings",
            subject="repository",
            count=len(multi),
            total=len(hotspots.hotspots),
            share=_share(len(multi), len(hotspots.hotspots)),
            supporting_hotspot_ids=tuple(
                item.hotspot_id for item in multi[:_HOTSPOT_REF_LIMIT]
            ),
        )
    )
    return tuple(sorted(facts, key=lambda item: (item.kind, item.subject, item.fact_id)))


def synthesize_security(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: SecurityAssessmentStatus,
    finding_summaries: Sequence[SecurityFindingReference],
    finding_inventory: SecurityFindingInventory,
    hotspot_inventory: SecurityHotspotInventory,
    evidence_summary: SecurityEvidenceSummary,
    diagnostics_summary: SecurityDiagnosticsSummary,
    rule_inventory: SecurityRuleInventory,
    limitations: Sequence[SecurityLimitation] = (),
    include_synthesis: bool = True,
) -> SecuritySynthesisResult:
    """Build deterministic Security synthesis from inventory facts."""

    if not include_synthesis:
        return SecuritySynthesisResult(
            status=SecuritySynthesisStatus.NOT_REQUESTED,
            synthesis_version=SYNTHESIS_VERSION,
            diagnostics=("synthesis_not_requested",),
        )

    if (
        not pack_enabled
        or section_status is SecurityAssessmentStatus.DISABLED
        or section_status is SecurityAssessmentStatus.NOT_REQUESTED
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=SecurityConclusionKind.SYNTHESIS_DISABLED,
            audience=SecurityConclusionAudience.STATUS,
            title="Security synthesis disabled",
            summary=(
                "Security synthesis was not generated because the Security pack "
                "or assessment section is disabled."
            ),
            technical_interpretation=(
                "Enable rules.security and assessment.sections.security to produce "
                "inventory-derived synthesis."
            ),
            source_role=SecuritySourceRole.UNKNOWN,
        )
        return SecuritySynthesisResult(
            status=SecuritySynthesisStatus.DISABLED,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        SecurityAssessmentStatus.INSUFFICIENT_EVIDENCE,
        SecurityAssessmentStatus.FAILED,
        SecurityAssessmentStatus.NOT_APPLICABLE,
    }:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=SecurityConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=SecurityConclusionAudience.STATUS,
            title="Insufficient Security evidence for synthesis",
            summary=(
                "Security synthesis could not be fully generated because the "
                f"assessment status is {section_status.value}."
            ),
            technical_interpretation=(
                "Provide usable repository-sensitive evidence and successful rule "
                "evaluation before interpreting Security synthesis."
            ),
            source_role=SecuritySourceRole.UNKNOWN,
        )
        return SecuritySynthesisResult(
            status=SecuritySynthesisStatus.INSUFFICIENT_EVIDENCE,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    all_refs = tuple(
        sorted(
            finding_summaries,
            key=lambda item: (item.rule_id, item.finding_id, item.title),
        )
    )
    production, test_refs, unknown_refs = _partition(all_refs)
    rules_executed = sum(1 for item in rule_inventory.entries if item.executed)
    if rules_executed == 0:
        rules_executed = len(HYGIENE_RULE_IDS)

    themes: list[SecurityTheme] = []
    conclusions: list[SecurityConclusion] = []
    recommendations: list[SecurityRecommendation] = []

    landscape = _landscape_theme(
        production=production,
        all_refs=all_refs,
        rules_executed=rules_executed,
        hotspot_count=len(hotspot_inventory.hotspots),
        evidence_status=evidence_summary.collection_status,
    )
    themes.append(landscape)
    conclusions.append(
        _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LANDSCAPE,
            kind=SecurityConclusionKind.SECURITY_HYGIENE_LANDSCAPE_IDENTIFIED,
            audience=SecurityConclusionAudience.REPOSITORY,
            title="Security hygiene landscape identified",
            summary=landscape.description,
            technical_interpretation=(
                "This conclusion summarizes supported repository security hygiene "
                "rule execution and finding counts only."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(landscape.theme_id,),
            finding_ids=[item.finding_id for item in all_refs],
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    # Evidence coverage theme (always when generated).
    coverage_desc = (
        f"Repository-sensitive evidence collection status is "
        f"{evidence_summary.collection_status}; "
        f"{evidence_summary.candidate_artifacts_discovered} candidate artifacts "
        f"were discovered and {evidence_summary.configuration_facts_collected} "
        "configuration facts were collected within supported formats."
    )
    _assert_safe_text(coverage_desc)
    coverage_theme = SecurityTheme(
        theme_id=build_theme_id(
            kind=SecurityThemeKind.EVIDENCE_COVERAGE.value,
            scope=SecurityThemeScope.COVERAGE.value,
        ),
        kind=SecurityThemeKind.EVIDENCE_COVERAGE,
        title="Evidence coverage",
        description=coverage_desc,
        scope=SecurityThemeScope.COVERAGE,
        source_role=SecuritySourceRole.UNKNOWN,
        counts={
            "candidate_artifacts": evidence_summary.candidate_artifacts_discovered,
            "configuration_facts": evidence_summary.configuration_facts_collected,
            "evidence_diagnostics": evidence_summary.evidence_diagnostic_count,
        },
        ordering_key="01_evidence_coverage",
    )
    themes.append(coverage_theme)

    private_refs = _findings_for_rules(all_refs, {RULE_PRIVATE_KEY_MATERIAL})
    literal_refs = _findings_for_rules(all_refs, {RULE_CREDENTIAL_LITERAL})
    placeholder_refs = _findings_for_rules(all_refs, {RULE_PLACEHOLDER_CREDENTIAL})
    tls_refs = _findings_for_rules(all_refs, {RULE_TLS_VERIFICATION_DISABLED})
    hostname_refs = _findings_for_rules(
        all_refs, {RULE_HOSTNAME_VERIFICATION_DISABLED}
    )
    auth_refs = _findings_for_rules(all_refs, {RULE_AUTHENTICATION_DISABLED})
    cors_refs = _findings_for_rules(all_refs, {RULE_PERMISSIVE_CORS_ORIGIN})
    debug_refs = _findings_for_rules(all_refs, {RULE_DEBUG_ENABLED})
    credential_refs = literal_refs + placeholder_refs
    transport_refs = tls_refs + hostname_refs

    if credential_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.CREDENTIAL_AND_SECRET_HYGIENE,
            title="Credential and secret hygiene",
            description=(
                f"{len(literal_refs)} credential-literal and "
                f"{len(placeholder_refs)} placeholder-credential findings were "
                "emitted from supported configuration facts."
            ),
            refs=credential_refs,
            ordering_key="10_credential",
        )
        if theme is not None:
            themes.append(theme)

    if private_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.PRIVATE_KEY_EXPOSURE,
            title="Private-key material observations",
            description=(
                f"Supported structural signatures identified private-key material "
                f"in {len(private_refs)} repository locations."
            ),
            refs=private_refs,
            ordering_key="11_private_key",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_PRIVATE_KEY,
            kind=SecurityConclusionKind.PRIVATE_KEY_MATERIAL_DETECTED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Private-key material detected",
            summary=(
                f"Supported structural signatures identified private-key material "
                f"in {len(private_refs)} repository locations."
            ),
            technical_interpretation=(
                "This conclusion records repository-visible private-key signatures "
                "only; it does not assert key usability or exploitability."
            ),
            source_role=SecuritySourceRole.PRODUCTION
            if any(
                item.source_role is SecuritySourceRole.PRODUCTION
                for item in private_refs
            )
            else private_refs[0].source_role,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in private_refs],
            rule_ids=(RULE_PRIVATE_KEY_MATERIAL,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.REMOVE_COMMITTED_PRIVATE_KEY_MATERIAL,
                action_key="remove-committed-private-key-material",
                title="Remove committed private-key material",
                action=(
                    "Remove the committed private-key material from the repository, "
                    "revoke or rotate the associated key where operationally "
                    "applicable, and replace repository storage with an approved "
                    "secret-management mechanism."
                ),
                rationale=(
                    "Private-key material findings are repository-visible structural "
                    "observations from supported signatures."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                theme_ids=(theme.theme_id,) if theme else (),
                finding_ids=[item.finding_id for item in private_refs],
            )
        )

    if literal_refs:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_LITERAL_CREDENTIAL,
            kind=SecurityConclusionKind.LITERAL_CREDENTIALS_DETECTED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Literal credentials detected",
            summary=(
                f"{len(literal_refs)} non-placeholder credential-sensitive literals "
                "were identified in supported configuration formats."
            ),
            technical_interpretation=(
                "Literal credential findings exclude placeholder and environment "
                "reference values; validity is not verified."
            ),
            source_role=SecuritySourceRole.PRODUCTION
            if any(
                item.source_role is SecuritySourceRole.PRODUCTION
                for item in literal_refs
            )
            else literal_refs[0].source_role,
            finding_ids=[item.finding_id for item in literal_refs],
            rule_ids=(RULE_CREDENTIAL_LITERAL,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ROTATE_AND_REPLACE_LITERAL_CREDENTIALS,
                action_key="rotate-and-replace-literal-credentials",
                title="Rotate and replace literal credentials",
                action=(
                    "Replace committed credential-sensitive literals with "
                    "environment or secret-manager references and rotate the "
                    "corresponding credentials where they may have been used."
                ),
                rationale=(
                    "Credential-literal findings cite supported configuration facts "
                    "without validating secret activity."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                finding_ids=[item.finding_id for item in literal_refs],
            )
        )
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.REPLACE_LITERAL_CREDENTIALS_WITH_EXTERNAL_SECRET_REFERENCE,
                action_key="replace-literal-credentials-with-external-secret-reference",
                title="Replace literals with external secret references",
                action=(
                    "Replace committed credential-sensitive literals with "
                    "environment or secret-manager references."
                ),
                rationale=(
                    "Externalizing literals reduces repository exposure of "
                    "credential-sensitive configuration values."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                finding_ids=[item.finding_id for item in literal_refs],
            )
        )

    if placeholder_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.PLACEHOLDER_CREDENTIALS,
            title="Placeholder credentials",
            description=(
                f"{len(placeholder_refs)} placeholder-credential findings were "
                "emitted. Placeholders are not treated as active exposed secrets."
            ),
            refs=placeholder_refs,
            ordering_key="12_placeholder",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_PLACEHOLDER,
            kind=SecurityConclusionKind.PLACEHOLDER_CREDENTIALS_DETECTED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Placeholder credentials detected",
            summary=(
                f"{len(placeholder_refs)} placeholder credential values were "
                "identified in supported configuration formats."
            ),
            technical_interpretation=(
                "Placeholder findings are distinct from literal credential "
                "findings and do not assert active secret exposure."
            ),
            source_role=placeholder_refs[0].source_role,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in placeholder_refs],
            rule_ids=(RULE_PLACEHOLDER_CREDENTIAL,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.REPLACE_PLACEHOLDER_CREDENTIALS,
                action_key="replace-placeholder-credentials",
                title="Replace placeholder credentials",
                action=(
                    "Replace committed placeholder credential values with "
                    "environment references or documented non-secret test "
                    "configuration."
                ),
                rationale=(
                    "Placeholder findings identify recognized non-secret markers "
                    "that still warrant configuration hygiene."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                theme_ids=(theme.theme_id,) if theme else (),
                finding_ids=[item.finding_id for item in placeholder_refs],
            )
        )

    if transport_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.TRANSPORT_SECURITY_CONFIGURATION,
            title="Transport security configuration",
            description=(
                f"{len(tls_refs)} TLS-verification-disabled and "
                f"{len(hostname_refs)} hostname-verification-disabled findings "
                "were emitted from supported configuration facts."
            ),
            refs=transport_refs,
            ordering_key="13_transport",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_TRANSPORT,
            kind=SecurityConclusionKind.TRANSPORT_VERIFICATION_DISABLED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Transport verification disabled",
            summary=(
                f"Supported configuration facts show TLS verification disabled in "
                f"{len(tls_refs)} locations and hostname verification disabled in "
                f"{len(hostname_refs)} locations."
            ),
            technical_interpretation=(
                "Transport findings record explicit disabled verification settings; "
                "they do not claim exploitability."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in transport_refs],
            rule_ids=tuple(
                sorted(
                    {
                        *(
                            (RULE_TLS_VERIFICATION_DISABLED,)
                            if tls_refs
                            else ()
                        ),
                        *(
                            (RULE_HOSTNAME_VERIFICATION_DISABLED,)
                            if hostname_refs
                            else ()
                        ),
                    }
                )
            ),
        )
        conclusions.append(conclusion)
        if tls_refs:
            recommendations.append(
                _make_recommendation(
                    kind=SecurityRecommendationKind.ENABLE_TLS_VERIFICATION,
                    action_key="enable-tls-verification",
                    title="Enable TLS verification",
                    action=(
                        "Enable certificate verification for the identified "
                        "configuration and validate the required trust "
                        "configuration in the deployment environment."
                    ),
                    rationale=(
                        "TLS-verification-disabled findings cite explicit "
                        "configuration facts."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                    finding_ids=[item.finding_id for item in tls_refs],
                )
            )
        if hostname_refs:
            recommendations.append(
                _make_recommendation(
                    kind=SecurityRecommendationKind.ENABLE_HOSTNAME_VERIFICATION,
                    action_key="enable-hostname-verification",
                    title="Enable hostname verification",
                    action=(
                        "Enable TLS hostname verification for the identified "
                        "configuration."
                    ),
                    rationale=(
                        "Hostname-verification-disabled findings cite explicit "
                        "configuration facts."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                    finding_ids=[item.finding_id for item in hostname_refs],
                )
            )

    if auth_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.AUTHENTICATION_CONFIGURATION,
            title="Authentication configuration",
            description=(
                f"{len(auth_refs)} authentication-disabled findings were emitted "
                "from supported configuration facts."
            ),
            refs=auth_refs,
            ordering_key="14_authentication",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_AUTHENTICATION,
            kind=SecurityConclusionKind.AUTHENTICATION_EXPLICITLY_DISABLED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Authentication explicitly disabled",
            summary=(
                f"{len(auth_refs)} supported configuration facts explicitly "
                "disable authentication controls."
            ),
            technical_interpretation=(
                "This conclusion is limited to the matched authentication "
                "configuration keys and does not describe overall application "
                "authentication posture."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in auth_refs],
            rule_ids=(RULE_AUTHENTICATION_DISABLED,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ENABLE_AUTHENTICATION,
                action_key="enable-authentication",
                title="Enable authentication",
                action=(
                    "Enable the configured authentication control for the "
                    "identified configuration."
                ),
                rationale=(
                    "Authentication-disabled findings cite explicit configuration "
                    "facts."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                finding_ids=[item.finding_id for item in auth_refs],
            )
        )

    if cors_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.PERMISSIVE_CORS_CONFIGURATION,
            title="Permissive CORS configuration",
            description=(
                f"{len(cors_refs)} permissive-cors-origin findings were emitted "
                "from supported configuration facts."
            ),
            refs=cors_refs,
            ordering_key="15_cors",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_CORS,
            kind=SecurityConclusionKind.PERMISSIVE_CORS_CONFIGURED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Permissive CORS configured",
            summary=(
                f"{len(cors_refs)} supported configuration facts use permissive "
                "CORS origin settings."
            ),
            technical_interpretation=(
                "Permissive CORS findings record configuration literals only and "
                "do not claim exploitability."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in cors_refs],
            rule_ids=(RULE_PERMISSIVE_CORS_ORIGIN,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.RESTRICT_CORS_ORIGINS,
                action_key="restrict-cors-origins",
                title="Restrict CORS origins",
                action=(
                    "Replace wildcard CORS origins with an explicit allow-list for "
                    "the identified configuration."
                ),
                rationale=(
                    "Permissive CORS findings cite supported configuration facts."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                finding_ids=[item.finding_id for item in cors_refs],
            )
        )

    if debug_refs:
        theme = _rule_theme(
            kind=SecurityThemeKind.DEBUG_CONFIGURATION,
            title="Debug configuration",
            description=(
                f"{len(debug_refs)} debug-enabled findings were emitted across "
                f"{len({item.source_role.value for item in debug_refs})} source roles."
            ),
            refs=debug_refs,
            ordering_key="16_debug",
        )
        if theme is not None:
            themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DEBUG,
            kind=SecurityConclusionKind.DEBUG_ENABLED,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Debug enabled",
            summary=(
                f"{len(debug_refs)} supported configuration facts explicitly "
                "enable debug mode."
            ),
            technical_interpretation=(
                "Debug findings preserve source-role labels and do not assert "
                "runtime exposure."
            ),
            source_role=SecuritySourceRole.PRODUCTION
            if any(
                item.source_role is SecuritySourceRole.PRODUCTION
                for item in debug_refs
            )
            else debug_refs[0].source_role,
            theme_ids=(theme.theme_id,) if theme else (),
            finding_ids=[item.finding_id for item in debug_refs],
            rule_ids=(RULE_DEBUG_ENABLED,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.DISABLE_DEBUG_CONFIGURATION,
                action_key="disable-debug-configuration",
                title="Disable debug configuration",
                action=(
                    "Disable debug mode for production-facing configuration and "
                    "review remaining debug settings by source role."
                ),
                rationale="Debug-enabled findings cite explicit configuration facts.",
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                finding_ids=[item.finding_id for item in debug_refs],
            )
        )

    if test_refs and len(all_refs) > len(production):
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.TEST_FIXTURE_OBSERVATIONS.value,
                scope=SecurityThemeScope.TEST_OBSERVATION.value,
            ),
            kind=SecurityThemeKind.TEST_FIXTURE_OBSERVATIONS,
            title="Test and fixture observations",
            description=(
                f"{len(test_refs)} Security findings are labeled test/fixture and "
                "remain outside the production-primary view."
            ),
            scope=SecurityThemeScope.TEST_OBSERVATION,
            source_role=SecuritySourceRole.TEST,
            finding_ids=_bound_ids(
                [item.finding_id for item in test_refs], _FINDING_REF_LIMIT
            ),
            rule_ids=tuple(sorted({item.rule_id for item in test_refs})),
            counts={"test_findings": len(test_refs)},
            ordering_key="20_test",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_TEST_FIXTURE,
            kind=SecurityConclusionKind.TEST_OR_FIXTURE_FINDINGS_ONLY
            if not production
            else SecurityConclusionKind.TEST_OR_FIXTURE_FINDINGS_ONLY,
            audience=SecurityConclusionAudience.TEST_OBSERVATION,
            title="Test or fixture findings present",
            summary=(
                f"{len(test_refs)} Security findings are associated with "
                "test/fixture source roles and are excluded from production-primary "
                "totals."
            ),
            technical_interpretation=(
                "Test/fixture observations remain available in all-findings views."
            ),
            source_role=SecuritySourceRole.TEST,
            theme_ids=(theme.theme_id,),
            finding_ids=[item.finding_id for item in test_refs],
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.REVIEW_TEST_FIXTURE_SECURITY_OBSERVATIONS,
                action_key="review-test-fixture-security-observations",
                title="Review test fixture Security observations",
                action=(
                    "Review test/fixture Security findings separately from "
                    "production-primary hygiene conclusions."
                ),
                rationale=(
                    "Test/fixture findings are retained in all-findings inventory "
                    "and synthesis observations."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.TEST_OBSERVATION,
                theme_ids=(theme.theme_id,),
                finding_ids=[item.finding_id for item in test_refs],
            )
        )

    if unknown_refs:
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.UNKNOWN_ROLE_OBSERVATIONS.value,
                scope=SecurityThemeScope.COVERAGE.value,
            ),
            kind=SecurityThemeKind.UNKNOWN_ROLE_OBSERVATIONS,
            title="Unknown-role observations",
            description=(
                f"{len(unknown_refs)} Security findings have unknown source role "
                "and are not treated as production."
            ),
            scope=SecurityThemeScope.COVERAGE,
            source_role=SecuritySourceRole.UNKNOWN,
            finding_ids=_bound_ids(
                [item.finding_id for item in unknown_refs], _FINDING_REF_LIMIT
            ),
            rule_ids=tuple(sorted({item.rule_id for item in unknown_refs})),
            counts={"unknown_findings": len(unknown_refs)},
            ordering_key="21_unknown",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNKNOWN_ROLE,
            kind=SecurityConclusionKind.UNKNOWN_ROLE_FINDINGS_PRESENT,
            audience=SecurityConclusionAudience.COVERAGE,
            title="Unknown-role findings present",
            summary=(
                f"{len(unknown_refs)} Security findings could not be classified "
                "as production or test/fixture."
            ),
            technical_interpretation=(
                "Unknown-role findings remain explicit and never contribute to "
                "production-primary totals."
            ),
            source_role=SecuritySourceRole.UNKNOWN,
            theme_ids=(theme.theme_id,),
            finding_ids=[item.finding_id for item in unknown_refs],
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.CLASSIFY_UNKNOWN_ROLE_FILES,
                action_key="classify-unknown-role-files",
                title="Classify unknown-role files",
                action=(
                    "Classify unknown-role paths as production or test/fixture so "
                    "future assessments can partition findings correctly."
                ),
                rationale=(
                    "Unknown-role findings are retained explicitly and excluded "
                    "from production-primary views."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
                finding_ids=[item.finding_id for item in unknown_refs],
            )
        )

    if hotspot_inventory.hotspots:
        top_paths = ", ".join(
            item.path for item in hotspot_inventory.hotspots[:_TOP_HOTSPOT_LIMIT]
        )
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.FINDING_CONCENTRATION.value,
                scope=SecurityThemeScope.REPOSITORY.value,
            ),
            kind=SecurityThemeKind.FINDING_CONCENTRATION,
            title="Security finding concentration",
            description=(
                f"{len(hotspot_inventory.hotspots)} repository locations show "
                f"Security finding concentration. Top locations: {top_paths}."
            ),
            scope=SecurityThemeScope.REPOSITORY,
            source_role=SecuritySourceRole.PRODUCTION,
            finding_ids=_bound_ids(
                [
                    finding_id
                    for item in hotspot_inventory.hotspots
                    for finding_id in item.finding_ids
                ],
                _FINDING_REF_LIMIT,
            ),
            hotspot_ids=_bound_ids(
                [item.hotspot_id for item in hotspot_inventory.hotspots],
                _HOTSPOT_REF_LIMIT,
            ),
            counts={
                "hotspot_count": len(hotspot_inventory.hotspots),
                "top_hotspot_findings": hotspot_inventory.hotspots[
                    0
                ].total_finding_count,
                "production_in_top": hotspot_inventory.hotspots[
                    0
                ].production_finding_count,
            },
            ordering_key="30_concentration",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_CONCENTRATION,
            kind=SecurityConclusionKind.FINDINGS_CONCENTRATED,
            audience=SecurityConclusionAudience.REPOSITORY,
            title="Findings concentrated",
            summary=theme.description,
            technical_interpretation=(
                "Hotspots order repository locations by finding concentration for "
                "presentation only."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(theme.theme_id,),
            hotspot_ids=[item.hotspot_id for item in hotspot_inventory.hotspots],
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.REVIEW_SECURITY_FINDING_HOTSPOTS,
                action_key="review-security-finding-hotspots",
                title="Review Security finding hotspots",
                action=(
                    "Review repository locations with multiple Security findings "
                    "and remediate the supporting hygiene conditions."
                ),
                rationale=(
                    "Hotspots summarize finding concentration without asserting "
                    "risk ratings."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.REPOSITORY,
                theme_ids=(theme.theme_id,),
                hotspot_ids=[item.hotspot_id for item in hotspot_inventory.hotspots],
            )
        )

    evidence_diags = diagnostics_summary.evidence_diagnostics
    partial = (
        evidence_summary.collection_status == "partially_succeeded"
        or bool(evidence_diags)
        or evidence_summary.malformed_files > 0
    )
    if partial:
        diag_ids = _bound_ids(
            [item.diagnostic_id for item in evidence_diags], _DIAGNOSTIC_REF_LIMIT
        )
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.PARTIAL_EVIDENCE_COVERAGE.value,
                scope=SecurityThemeScope.COVERAGE.value,
            ),
            kind=SecurityThemeKind.PARTIAL_EVIDENCE_COVERAGE,
            title="Partial evidence coverage",
            description=(
                "Repository-sensitive evidence collection was partial because "
                f"{max(evidence_summary.malformed_files, len(evidence_diags))} "
                "supported input files could not be fully parsed or inspected."
            ),
            scope=SecurityThemeScope.COVERAGE,
            source_role=SecuritySourceRole.UNKNOWN,
            diagnostic_ids=diag_ids,
            counts={
                "malformed_files": evidence_summary.malformed_files,
                "evidence_diagnostics": len(evidence_diags),
                "unsupported_binaries": evidence_summary.unsupported_binaries,
                "skipped_files": evidence_summary.skipped_files,
            },
            ordering_key="40_partial",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_PARTIAL_EVIDENCE,
            kind=SecurityConclusionKind.PARTIAL_EVIDENCE_COVERAGE,
            audience=SecurityConclusionAudience.COVERAGE,
            title="Partial evidence coverage",
            summary=theme.description,
            technical_interpretation=(
                "Evidence diagnostics remain diagnostics and are not Security "
                "findings."
            ),
            source_role=SecuritySourceRole.UNKNOWN,
            theme_ids=(theme.theme_id,),
            diagnostic_ids=diag_ids,
        )
        conclusions.append(conclusion)
        if any(
            "malformed" in item.diagnostic_code.lower() for item in evidence_diags
        ) or evidence_summary.malformed_files > 0:
            recommendations.append(
                _make_recommendation(
                    kind=SecurityRecommendationKind.CORRECT_MALFORMED_CONFIGURATION,
                    action_key="correct-malformed-configuration",
                    title="Correct malformed supported configuration",
                    action=(
                        "Correct malformed supported configuration files so "
                        "repository-sensitive evidence collection can complete."
                    ),
                    rationale=(
                        "Malformed inputs reduce evidence completeness; they are "
                        "not treated as Security findings."
                    ),
                    conclusion_ids=(conclusion.conclusion_id,),
                    audience=SecurityConclusionAudience.COVERAGE,
                    theme_ids=(theme.theme_id,),
                    diagnostic_ids=diag_ids,
                )
            )
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.EXPAND_SUPPORTED_EVIDENCE_COVERAGE,
                action_key="expand-supported-evidence-coverage",
                title="Expand supported evidence coverage",
                action=(
                    "Expand supported repository-sensitive evidence coverage for "
                    "files that were skipped, unsupported, or only partially "
                    "inspected."
                ),
                rationale=(
                    "Coverage expansion improves inventory completeness without "
                    "claiming a full security assessment."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
                diagnostic_ids=diag_ids,
            )
        )

    if limitations:
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.UNSUPPORTED_ANALYSIS_SCOPE.value,
                scope=SecurityThemeScope.COVERAGE.value,
            ),
            kind=SecurityThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
            title="Unsupported analysis scope",
            description=(
                "Accepted Security assessment limitations include repository "
                "snapshot analysis only, without Git history, runtime validation, "
                "entropy analysis, certificate trust checks, keystore inspection, "
                "or external vulnerability metadata."
            ),
            scope=SecurityThemeScope.COVERAGE,
            source_role=SecuritySourceRole.UNKNOWN,
            counts={"limitation_count": len(limitations)},
            ordering_key="50_unsupported",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_SCOPE,
            kind=SecurityConclusionKind.UNSUPPORTED_SECURITY_ANALYSIS_SCOPE,
            audience=SecurityConclusionAudience.COVERAGE,
            title="Unsupported Security analysis scope",
            summary=theme.description,
            technical_interpretation=(
                "Zero findings within supported scope do not prove repository "
                "security."
            ),
            source_role=SecuritySourceRole.UNKNOWN,
            theme_ids=(theme.theme_id,),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ADD_RUNTIME_SECURITY_VALIDATION,
                action_key="add-runtime-security-validation",
                title="Add runtime security validation",
                action=(
                    "Add runtime security validation outside this repository "
                    "snapshot assessment before drawing broader conclusions."
                ),
                rationale="Runtime analysis is an accepted unsupported limitation.",
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
            )
        )
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ADD_GIT_HISTORY_SECRET_SCANNING,
                action_key="add-git-history-secret-scanning",
                title="Add Git history secret scanning",
                action=(
                    "Add Git history secret scanning outside this repository "
                    "snapshot assessment."
                ),
                rationale="Git history analysis is an accepted unsupported limitation.",
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
            )
        )
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ADD_EXTERNAL_DEPENDENCY_VULNERABILITY_ANALYSIS,
                action_key="add-external-dependency-vulnerability-analysis",
                title="Add external dependency vulnerability analysis",
                action=(
                    "Add external dependency vulnerability analysis outside this "
                    "repository-sensitive hygiene assessment."
                ),
                rationale=(
                    "External vulnerability metadata is an accepted unsupported "
                    "limitation."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
            )
        )

    if len(production) == 0 and rules_executed > 0:
        theme = SecurityTheme(
            theme_id=build_theme_id(
                kind=SecurityThemeKind.NO_PRODUCTION_FINDINGS.value,
                scope=SecurityThemeScope.PRODUCTION.value,
            ),
            kind=SecurityThemeKind.NO_PRODUCTION_FINDINGS,
            title="No production findings",
            description=(
                "No production-role findings were emitted by the supported "
                "repository security hygiene rules."
            ),
            scope=SecurityThemeScope.PRODUCTION,
            source_role=SecuritySourceRole.PRODUCTION,
            counts={
                "production_findings": 0,
                "all_findings": len(all_refs),
                "rules_executed": rules_executed,
            },
            ordering_key="60_no_production",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_PRODUCTION,
            kind=SecurityConclusionKind.NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="No production findings in supported scope",
            summary=(
                f"No production-role findings were emitted by the "
                f"{rules_executed} enabled Security hygiene rules within the "
                "supported repository evidence scope."
            ),
            technical_interpretation=(
                "This statement is limited to supported repository-sensitive "
                "evidence and hygiene rules; it does not mean the repository is "
                "secure or free of vulnerabilities."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            theme_ids=(theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=SecurityRecommendationKind.ACKNOWLEDGE_NO_PRODUCTION_FINDINGS_IN_SUPPORTED_SCOPE,
                action_key="acknowledge-no-production-findings-in-supported-scope",
                title="Acknowledge no production findings in supported scope",
                action=(
                    "Retain the current repository hygiene controls and extend "
                    "assessment coverage before drawing broader security "
                    "conclusions."
                ),
                rationale=(
                    "Zero production findings within supported scope are not a "
                    "security certification."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
                theme_ids=(theme.theme_id,),
            )
        )
    elif production:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_PRODUCTION_PRESENT,
            kind=SecurityConclusionKind.PRODUCTION_SECURITY_FINDINGS_PRESENT,
            audience=SecurityConclusionAudience.PRODUCTION_HEALTH,
            title="Production Security findings present",
            summary=(
                f"{len(production)} production-role Security hygiene findings "
                "were emitted within the supported evidence scope."
            ),
            technical_interpretation=(
                "Production-primary findings drive primary conclusions; "
                "test/fixture and unknown findings remain separately labeled."
            ),
            source_role=SecuritySourceRole.PRODUCTION,
            finding_ids=[item.finding_id for item in production],
            rule_ids=tuple(sorted({item.rule_id for item in production})),
        )
        conclusions.append(conclusion)

    facts = _concentration_facts(
        all_refs=all_refs,
        production=production,
        hotspots=hotspot_inventory,
    )

    ordered_themes = tuple(sorted(themes, key=lambda item: (item.ordering_key, item.theme_id)))
    ordered_conclusions = tuple(
        sorted(conclusions, key=lambda item: (item.kind.value, item.conclusion_id))
    )
    # Deduplicate recommendations by kind.
    rec_by_kind: dict[str, SecurityRecommendation] = {}
    for item in recommendations:
        existing = rec_by_kind.get(item.kind.value)
        if existing is None:
            rec_by_kind[item.kind.value] = item
            continue
        merged_findings = _bound_ids(
            (*existing.finding_ids, *item.finding_ids), _FINDING_REF_LIMIT
        )
        merged_conclusions = _bound_ids(
            (*existing.conclusion_ids, *item.conclusion_ids), _FINDING_REF_LIMIT
        )
        merged_themes = _bound_ids(
            (*existing.theme_ids, *item.theme_ids), _FINDING_REF_LIMIT
        )
        merged_hotspots = _bound_ids(
            (*existing.hotspot_ids, *item.hotspot_ids), _HOTSPOT_REF_LIMIT
        )
        merged_diags = _bound_ids(
            (*existing.diagnostic_ids, *item.diagnostic_ids), _DIAGNOSTIC_REF_LIMIT
        )
        rec_by_kind[item.kind.value] = existing.model_copy(
            update={
                "recommendation_id": build_recommendation_id(
                    conclusion_ids=merged_conclusions,
                    action_key=item.kind.value.replace("_", "-"),
                ),
                "conclusion_ids": merged_conclusions,
                "theme_ids": merged_themes,
                "finding_ids": merged_findings,
                "hotspot_ids": merged_hotspots,
                "diagnostic_ids": merged_diags,
            }
        )
    ordered_recommendations = tuple(
        sorted(rec_by_kind.values(), key=lambda item: (item.kind.value, item.recommendation_id))
    )

    # Link recommendation ids back onto conclusions where referenced.
    linked_conclusions: list[SecurityConclusion] = []
    for conclusion in ordered_conclusions:
        linked = tuple(
            item.recommendation_id
            for item in ordered_recommendations
            if conclusion.conclusion_id in item.conclusion_ids
        )
        linked_conclusions.append(
            conclusion.model_copy(update={"recommendation_ids": linked})
            if linked
            else conclusion
        )

    status = (
        SecuritySynthesisStatus.EMPTY
        if not all_refs and not hotspot_inventory.hotspots
        else SecuritySynthesisStatus.SUCCEEDED
    )
    return SecuritySynthesisResult(
        status=status,
        synthesis_version=SYNTHESIS_VERSION,
        themes=ordered_themes,
        theme_ids=tuple(item.theme_id for item in ordered_themes),
        concentration_facts=facts,
        conclusions=tuple(linked_conclusions),
        conclusion_ids=tuple(item.conclusion_id for item in linked_conclusions),
        recommendations=ordered_recommendations,
        recommendation_ids=tuple(
            item.recommendation_id for item in ordered_recommendations
        ),
        diagnostics=(),
    )


__all__ = ["synthesize_security"]
