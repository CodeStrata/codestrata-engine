"""Deterministic Cloud synthesis from assessment inventory (Phase 4.7.5).

Consumes Cloud Assessment inventories, Findings, and rule-execution facts only.
Does not re-read repository files, recollect evidence, or reevaluate hygiene rules.
"""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.cloud.assessment.enums import CloudAssessmentStatus
from codestrata.domain.cloud.assessment.models import (
    CloudFindingInventory,
    CloudLimitation,
    CloudRuleInventory,
    CloudTechnologyFamilyInventory,
)
from codestrata.domain.cloud.ids import (
    HYGIENE_RULE_IDS,
    RULE_CLOUD_NATIVE_INDICATORS,
    RULE_CONTAINERIZATION,
    RULE_DEPLOYMENT_PIPELINE,
    RULE_DEPLOYMENT_WITHOUT_PLATFORM,
    RULE_IAC_PRESENT,
    RULE_KUBERNETES,
    RULE_MANAGED_SERVICES,
    RULE_MULTIPLE_IAC,
    RULE_MULTIPLE_PLATFORMS,
    RULE_PLATFORM_DETECTED,
    RULE_SERVERLESS,
)
from codestrata.domain.cloud.synthesis.enums import (
    CloudConclusionAudience,
    CloudConclusionKind,
    CloudRecommendationKind,
    CloudSynthesisStatus,
    CloudThemeKind,
    CloudThemeScope,
)
from codestrata.domain.cloud.synthesis.identifiers import (
    POLICY_CONTAINERS,
    POLICY_COVERAGE,
    POLICY_DEPLOYMENT,
    POLICY_DISABLED,
    POLICY_IAC,
    POLICY_INSUFFICIENT,
    POLICY_LANDSCAPE,
    POLICY_MANAGED,
    POLICY_MULTI_CLOUD,
    POLICY_NO_FINDINGS,
    POLICY_ORCHESTRATION,
    POLICY_PLATFORM,
    POLICY_RULE_EXECUTION,
    POLICY_SERVERLESS,
    POLICY_UNSUPPORTED_SCOPE,
    POLICY_WITHOUT_PLATFORM,
    SYNTHESIS_VERSION,
    build_conclusion_id,
    build_recommendation_id,
    build_theme_id,
)
from codestrata.domain.cloud.synthesis.models import (
    CloudConclusion,
    CloudRecommendation,
    CloudSynthesisResult,
    CloudTheme,
)
from codestrata.domain.findings.models import Finding

_FINDING_REF_LIMIT = 32

_FORBIDDEN_WORDS = (
    "is cloud ready",
    "are cloud ready",
    "cloud-native ready",
    "fully portable",
    "migrate to",
    "modernize",
    "modernisation",
    "modernization path",
    "multi-cloud strategy",
    "production ready",
    "no cloud issues",
)


def _bound_ids(values: Sequence[str], limit: int) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item}))[:limit]


def _assert_safe_text(*parts: str) -> None:
    joined = " ".join(parts).lower()
    sanitized = (
        joined.replace("does not establish that the repository is cloud ready", "")
        .replace("does not mean the repository is cloud ready", "")
        .replace("does not establish cloud readiness", "")
        .replace("not cloud ready", "")
        .replace("cloud readiness", "")
        .replace("zero findings does not mean", "")
        .replace("do not establish cloud readiness", "")
        .replace("without claiming cloud readiness", "")
        .replace("does not claim cloud usage is absent", "")
    )
    for phrase in _FORBIDDEN_WORDS:
        if phrase in sanitized:
            raise ValueError(f"forbidden synthesis wording: {phrase}")


def _make_conclusion(
    *,
    repository_id: str,
    policy_id: str,
    kind: CloudConclusionKind,
    audience: CloudConclusionAudience,
    title: str,
    summary: str,
    technical_interpretation: str,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
    confidence: str = "high",
    metadata: dict[str, str] | None = None,
) -> CloudConclusion:
    _assert_safe_text(title, summary, technical_interpretation)
    support = tuple(theme_ids) + tuple(finding_ids) + tuple(rule_ids)
    return CloudConclusion(
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
    kind: CloudRecommendationKind,
    action_key: str,
    title: str,
    action: str,
    rationale: str,
    conclusion_ids: Sequence[str],
    audience: CloudConclusionAudience,
    theme_ids: Sequence[str] = (),
    finding_ids: Sequence[str] = (),
    rule_ids: Sequence[str] = (),
) -> CloudRecommendation:
    _assert_safe_text(title, action, rationale)
    return CloudRecommendation(
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
    kind: CloudThemeKind,
    title: str,
    description: str,
    findings: Sequence[Finding],
    ordering_key: str,
) -> CloudTheme | None:
    if not findings:
        return None
    _assert_safe_text(title, description)
    finding_ids = tuple(item.id for item in findings)
    rule_ids = tuple(sorted({item.rule_id for item in findings}))
    return CloudTheme(
        theme_id=build_theme_id(
            kind=kind.value,
            scope=CloudThemeScope.HYGIENE.value,
            subject=rule_ids[0] if rule_ids else "",
        ),
        kind=kind,
        title=title,
        description=description,
        scope=CloudThemeScope.HYGIENE,
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
            f"{rules_executed} Cloud Hygiene rules executed with zero findings in "
            "the supported repository evidence scope. This summarizes technology "
            "signals only and does not establish cloud readiness."
        )
    else:
        text = (
            f"Cloud Hygiene inventory shows {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across {rules_matched} matched "
            f"rule{'s' if rules_matched != 1 else ''} of {rules_executed} executed"
            f" ({families_observed} technology famil"
            f"{'y' if families_observed == 1 else 'ies'} observed). "
            "Implications remain informational to low and do not establish "
            "cloud readiness."
        )
    _assert_safe_text(text)
    return text


def _link_recommendations(
    conclusions: list[CloudConclusion],
    recommendations: Sequence[CloudRecommendation],
) -> list[CloudConclusion]:
    by_conclusion: dict[str, list[str]] = {}
    for item in recommendations:
        for conclusion_id in item.conclusion_ids:
            by_conclusion.setdefault(conclusion_id, []).append(item.recommendation_id)
    linked: list[CloudConclusion] = []
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
    themes: list[CloudTheme],
    conclusions: list[CloudConclusion],
    recommendations: list[CloudRecommendation],
    findings: Sequence[Finding],
    theme_kind: CloudThemeKind,
    conclusion_kind: CloudConclusionKind,
    recommendation_kind: CloudRecommendationKind,
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
    audience: CloudConclusionAudience = CloudConclusionAudience.HYGIENE,
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


def synthesize_cloud(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_status: CloudAssessmentStatus,
    findings: Sequence[Finding] = (),
    finding_inventory: CloudFindingInventory | None = None,
    rule_inventory: CloudRuleInventory | None = None,
    technology_family_inventory: CloudTechnologyFamilyInventory | None = None,
    limitations: Sequence[CloudLimitation] = (),
    evidence_status: str = "",
    include_synthesis: bool = True,
) -> CloudSynthesisResult:
    """Build deterministic Cloud synthesis from inventory facts."""

    if not include_synthesis:
        return CloudSynthesisResult(
            status=CloudSynthesisStatus.NOT_REQUESTED,
            synthesis_version=SYNTHESIS_VERSION,
            diagnostics=("synthesis_not_requested",),
        )

    if (
        not pack_enabled
        or section_status is CloudAssessmentStatus.DISABLED
        or section_status is CloudAssessmentStatus.NOT_REQUESTED
    ):
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_DISABLED,
            kind=CloudConclusionKind.SYNTHESIS_DISABLED,
            audience=CloudConclusionAudience.STATUS,
            title="Cloud synthesis disabled",
            summary=(
                "Cloud synthesis was not generated because the Cloud pack or "
                "analysis section is disabled."
            ),
            technical_interpretation=(
                "Enable rules.cloud and analysis.cloud to produce inventory-derived synthesis."
            ),
        )
        return CloudSynthesisResult(
            status=CloudSynthesisStatus.DISABLED,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_disabled",),
        )

    if section_status in {
        CloudAssessmentStatus.INSUFFICIENT_EVIDENCE,
        CloudAssessmentStatus.FAILED,
        CloudAssessmentStatus.NOT_APPLICABLE,
    }:
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_INSUFFICIENT,
            kind=CloudConclusionKind.INSUFFICIENT_EVIDENCE,
            audience=CloudConclusionAudience.STATUS,
            title="Insufficient Cloud evidence for synthesis",
            summary=(
                "Cloud synthesis could not be fully generated because the "
                f"assessment status is {section_status.value}."
            ),
            technical_interpretation=(
                "Provide usable repository-cloud evidence and successful rule "
                "evaluation before interpreting Cloud synthesis."
            ),
        )
        return CloudSynthesisResult(
            status=CloudSynthesisStatus.INSUFFICIENT_EVIDENCE,
            synthesis_version=SYNTHESIS_VERSION,
            conclusions=(conclusion,),
            conclusion_ids=(conclusion.conclusion_id,),
            diagnostics=("synthesis_insufficient_evidence",),
        )

    ordered = tuple(sorted(findings, key=lambda item: (item.rule_id, item.id, item.title)))
    inventory = finding_inventory or CloudFindingInventory(
        finding_ids=tuple(item.id for item in ordered),
        finding_count=len(ordered),
    )
    rules = rule_inventory or CloudRuleInventory()
    families = technology_family_inventory or CloudTechnologyFamilyInventory()
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

    themes: list[CloudTheme] = []
    conclusions: list[CloudConclusion] = []
    recommendations: list[CloudRecommendation] = []

    if findings_count == 0:
        landscape_desc = (
            f"{rules_executed} Cloud Hygiene rules executed and produced no "
            "findings within the supported repository evidence scope."
        )
    else:
        landscape_desc = (
            f"The supported Cloud Hygiene rules produced {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} across "
            f"{rules_matched} matched rule{'s' if rules_matched != 1 else ''}."
        )
    _assert_safe_text(landscape_desc)
    landscape = CloudTheme(
        theme_id=build_theme_id(
            kind=CloudThemeKind.CLOUD_HYGIENE_LANDSCAPE.value,
            scope=CloudThemeScope.REPOSITORY.value,
        ),
        kind=CloudThemeKind.CLOUD_HYGIENE_LANDSCAPE,
        title="Cloud hygiene landscape",
        description=landscape_desc,
        scope=CloudThemeScope.REPOSITORY,
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
            kind=CloudConclusionKind.CLOUD_HYGIENE_LANDSCAPE_IDENTIFIED,
            audience=CloudConclusionAudience.REPOSITORY,
            title="Cloud hygiene landscape identified",
            summary=landscape_desc,
            technical_interpretation=(
                "This conclusion summarizes supported Cloud Hygiene rule "
                "execution and finding counts only."
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
    coverage_theme = CloudTheme(
        theme_id=build_theme_id(
            kind=CloudThemeKind.RULE_EXECUTION_COVERAGE.value,
            scope=CloudThemeScope.COVERAGE.value,
        ),
        kind=CloudThemeKind.RULE_EXECUTION_COVERAGE,
        title="Rule execution coverage",
        description=coverage_desc,
        scope=CloudThemeScope.COVERAGE,
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
            kind=CloudConclusionKind.RULE_EXECUTION_SUMMARY,
            audience=CloudConclusionAudience.COVERAGE,
            title="Cloud Hygiene rule execution summary",
            summary=coverage_desc,
            technical_interpretation=(
                "Applicable registered hygiene rules versus matched outcomes "
                "are inventory facts, not cloud readiness scores."
            ),
            theme_ids=(coverage_theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
    )

    platform_findings = _findings_for_rules(ordered, (RULE_PLATFORM_DETECTED,))
    multi_findings = _findings_for_rules(ordered, (RULE_MULTIPLE_PLATFORMS,))
    container_findings = _findings_for_rules(ordered, (RULE_CONTAINERIZATION,))
    orch_findings = _findings_for_rules(ordered, (RULE_KUBERNETES,))
    iac_findings = _findings_for_rules(ordered, (RULE_IAC_PRESENT, RULE_MULTIPLE_IAC))
    serverless_findings = _findings_for_rules(ordered, (RULE_SERVERLESS,))
    managed_findings = _findings_for_rules(ordered, (RULE_MANAGED_SERVICES,))
    deployment_findings = _findings_for_rules(ordered, (RULE_DEPLOYMENT_PIPELINE,))
    coverage_findings = _findings_for_rules(ordered, (RULE_CLOUD_NATIVE_INDICATORS,))
    without_platform_findings = _findings_for_rules(ordered, (RULE_DEPLOYMENT_WITHOUT_PLATFORM,))

    if platform_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=platform_findings,
            theme_kind=CloudThemeKind.CLOUD_PLATFORM_ADOPTION,
            conclusion_kind=CloudConclusionKind.CLOUD_PLATFORM_ADOPTION_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_CLOUD_PLATFORM_SIGNALS,
            policy_id=POLICY_PLATFORM,
            title="Cloud platform adoption",
            description=(
                f"{len(platform_findings)} finding"
                f"{'' if len(platform_findings) == 1 else 's'} report a single "
                "observed cloud platform marker in repository evidence."
            ),
            conclusion_title="Cloud platform adoption observed",
            technical_interpretation=(
                "Platform markers are repository-observable technology signals. "
                "They do not establish that workloads run on that provider."
            ),
            recommendation_title="Review cloud platform signals",
            recommendation_action=(
                "Review the linked Cloud Hygiene findings and confirm the "
                "observed platform markers remain intentional."
            ),
            recommendation_rationale=(
                "CLOUD-002 matched on a single platform marker; review keeps "
                "inventory signals actionable without modernization advice."
            ),
            action_key="review-cloud-platform-signals",
            rule_ids=(RULE_PLATFORM_DETECTED,),
            ordering_key="10_platform",
        )

    if multi_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=multi_findings,
            theme_kind=CloudThemeKind.MULTI_CLOUD_PRESENCE,
            conclusion_kind=CloudConclusionKind.MULTI_CLOUD_PRESENCE_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_MULTI_CLOUD_SIGNALS,
            policy_id=POLICY_MULTI_CLOUD,
            title="Multi-cloud presence",
            description=(
                f"{len(multi_findings)} finding"
                f"{'' if len(multi_findings) == 1 else 's'} report markers for "
                "two or more cloud platforms in repository evidence."
            ),
            conclusion_title="Multi-cloud presence observed",
            technical_interpretation=(
                "Multiple platform markers describe observed technology "
                "signals only. They do not establish a multi-cloud operating model."
            ),
            recommendation_title="Review multi-cloud signals",
            recommendation_action=(
                "Review the linked findings and confirm each observed platform "
                "marker is expected for this repository."
            ),
            recommendation_rationale=(
                "CLOUD-001 matched on multiple platform markers; review is "
                "observation-oriented and does not prescribe consolidation."
            ),
            action_key="review-multi-cloud-signals",
            rule_ids=(RULE_MULTIPLE_PLATFORMS,),
            ordering_key="11_multi_cloud",
            confidence="medium",
        )

    if container_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=container_findings,
            theme_kind=CloudThemeKind.CONTAINERIZATION_MATURITY,
            conclusion_kind=CloudConclusionKind.CONTAINERIZATION_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_CONTAINERIZATION_SIGNALS,
            policy_id=POLICY_CONTAINERS,
            title="Containerization maturity",
            description=(
                f"{len(container_findings)} finding"
                f"{'' if len(container_findings) == 1 else 's'} report "
                "containerization artifacts in repository evidence."
            ),
            conclusion_title="Containerization observed",
            technical_interpretation=(
                "Container artifacts are packaging signals. They do not "
                "establish runtime orchestration maturity."
            ),
            recommendation_title="Review containerization signals",
            recommendation_action=(
                "Review the linked containerization findings and confirm "
                "Dockerfile or Compose assets remain current."
            ),
            recommendation_rationale=(
                "CLOUD-010 matched on container artifacts; review stays observation-oriented."
            ),
            action_key="review-containerization-signals",
            rule_ids=(RULE_CONTAINERIZATION,),
            ordering_key="12_containers",
        )

    if orch_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=orch_findings,
            theme_kind=CloudThemeKind.KUBERNETES_ORCHESTRATION_ADOPTION,
            conclusion_kind=CloudConclusionKind.KUBERNETES_ORCHESTRATION_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_ORCHESTRATION_SIGNALS,
            policy_id=POLICY_ORCHESTRATION,
            title="Kubernetes / orchestration adoption",
            description=(
                f"{len(orch_findings)} finding"
                f"{'' if len(orch_findings) == 1 else 's'} report Kubernetes, "
                "Helm, or OpenShift orchestration artifacts."
            ),
            conclusion_title="Kubernetes / orchestration adoption observed",
            technical_interpretation=(
                "Orchestration manifests are repository deployment signals. "
                "They do not establish cluster health or production operation."
            ),
            recommendation_title="Review orchestration signals",
            recommendation_action=(
                "Review the linked orchestration findings and confirm manifests "
                "remain intentional for this repository."
            ),
            recommendation_rationale=(
                "CLOUD-011 matched on orchestration artifacts; review does not "
                "prescribe cluster migration."
            ),
            action_key="review-orchestration-signals",
            rule_ids=(RULE_KUBERNETES,),
            ordering_key="13_orchestration",
        )

    if iac_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=iac_findings,
            theme_kind=CloudThemeKind.IAC_MATURITY,
            conclusion_kind=CloudConclusionKind.IAC_MATURITY_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_IAC_SIGNALS,
            policy_id=POLICY_IAC,
            title="Infrastructure as Code maturity",
            description=(
                f"{len(iac_findings)} finding"
                f"{'' if len(iac_findings) == 1 else 's'} report Infrastructure "
                "as Code technologies in repository evidence."
            ),
            conclusion_title="Infrastructure as Code maturity observed",
            technical_interpretation=(
                "IaC artifacts describe declared infrastructure tooling. They "
                "do not establish apply success or drift status."
            ),
            recommendation_title="Review Infrastructure as Code signals",
            recommendation_action=(
                "Review the linked IaC findings and confirm each observed "
                "tooling marker remains intentional."
            ),
            recommendation_rationale=(
                "CLOUD-020/021 matched on IaC artifacts; review stays observation-oriented."
            ),
            action_key="review-iac-signals",
            rule_ids=tuple(sorted({item.rule_id for item in iac_findings})),
            ordering_key="14_iac",
        )

    if serverless_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=serverless_findings,
            theme_kind=CloudThemeKind.SERVERLESS_ADOPTION,
            conclusion_kind=CloudConclusionKind.SERVERLESS_ADOPTION_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_SERVERLESS_SIGNALS,
            policy_id=POLICY_SERVERLESS,
            title="Serverless adoption",
            description=(
                f"{len(serverless_findings)} finding"
                f"{'' if len(serverless_findings) == 1 else 's'} report "
                "serverless deployment artifacts."
            ),
            conclusion_title="Serverless adoption observed",
            technical_interpretation=(
                "Serverless packaging markers are repository signals only and "
                "do not establish runtime invocation success."
            ),
            recommendation_title="Review serverless signals",
            recommendation_action=(
                "Review the linked serverless findings and confirm packaging "
                "artifacts remain intentional."
            ),
            recommendation_rationale=(
                "CLOUD-030 matched on serverless artifacts; review does not "
                "prescribe architecture changes."
            ),
            action_key="review-serverless-signals",
            rule_ids=(RULE_SERVERLESS,),
            ordering_key="15_serverless",
        )

    if managed_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=managed_findings,
            theme_kind=CloudThemeKind.MANAGED_CLOUD_SERVICE_USAGE,
            conclusion_kind=CloudConclusionKind.MANAGED_CLOUD_SERVICES_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_MANAGED_SERVICE_SIGNALS,
            policy_id=POLICY_MANAGED,
            title="Managed cloud service usage",
            description=(
                f"{len(managed_findings)} finding"
                f"{'' if len(managed_findings) == 1 else 's'} report managed "
                "cloud service markers in repository evidence."
            ),
            conclusion_title="Managed cloud services observed",
            technical_interpretation=(
                "Managed service markers describe declared resources. They do "
                "not establish provisioned capacity or cost posture."
            ),
            recommendation_title="Review managed service signals",
            recommendation_action=(
                "Review the linked managed-service findings and confirm each "
                "resource marker remains intentional."
            ),
            recommendation_rationale=(
                "CLOUD-050 matched on managed service markers; review stays observation-oriented."
            ),
            action_key="review-managed-service-signals",
            rule_ids=(RULE_MANAGED_SERVICES,),
            ordering_key="16_managed",
        )

    if deployment_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=deployment_findings,
            theme_kind=CloudThemeKind.CLOUD_DEPLOYMENT_AUTOMATION,
            conclusion_kind=CloudConclusionKind.CLOUD_DEPLOYMENT_AUTOMATION_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_DEPLOYMENT_PIPELINE_SIGNALS,
            policy_id=POLICY_DEPLOYMENT,
            title="Cloud deployment automation",
            description=(
                f"{len(deployment_findings)} finding"
                f"{'' if len(deployment_findings) == 1 else 's'} report "
                "cloud-related deployment pipeline artifacts."
            ),
            conclusion_title="Cloud deployment automation observed",
            technical_interpretation=(
                "Pipeline artifacts are automation signals. They do not "
                "establish successful production delivery."
            ),
            recommendation_title="Review deployment pipeline signals",
            recommendation_action=(
                "Review the linked deployment findings and confirm pipeline "
                "assets remain intentional."
            ),
            recommendation_rationale=(
                "CLOUD-040 matched on deployment pipeline artifacts; review "
                "does not prescribe CI/CD redesign."
            ),
            action_key="review-deployment-pipeline-signals",
            rule_ids=(RULE_DEPLOYMENT_PIPELINE,),
            ordering_key="17_deployment",
        )

    tech_coverage_findings = coverage_findings
    if tech_coverage_findings or families_observed >= 3:
        if tech_coverage_findings:
            desc = (
                f"{len(tech_coverage_findings)} finding"
                f"{'' if len(tech_coverage_findings) == 1 else 's'} report "
                "multiple cloud evidence families in one repository."
            )
            finding_ids_for_theme = tuple(item.id for item in tech_coverage_findings)
            rule_ids_for_theme: tuple[str, ...] = (RULE_CLOUD_NATIVE_INDICATORS,)
        else:
            desc = (
                f"Technology family inventory observes {families_observed} "
                "distinct cloud evidence families from Findings metadata."
            )
            finding_ids_for_theme = finding_ids
            rule_ids_for_theme = tuple(sorted({item.rule_id for item in ordered})) or tuple(
                HYGIENE_RULE_IDS
            )
        _assert_safe_text(desc)
        theme = CloudTheme(
            theme_id=build_theme_id(
                kind=CloudThemeKind.CLOUD_TECHNOLOGY_COVERAGE.value,
                scope=CloudThemeScope.COVERAGE.value,
                subject="families",
            ),
            kind=CloudThemeKind.CLOUD_TECHNOLOGY_COVERAGE,
            title="Cloud technology coverage",
            description=desc,
            scope=CloudThemeScope.COVERAGE,
            finding_ids=_bound_ids(finding_ids_for_theme, _FINDING_REF_LIMIT),
            rule_ids=rule_ids_for_theme,
            counts={
                "finding_count": len(tech_coverage_findings),
                "families_observed": families_observed,
            },
            ordering_key="18_technology_coverage",
        )
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_COVERAGE,
            kind=CloudConclusionKind.CLOUD_TECHNOLOGY_COVERAGE_OBSERVED,
            audience=CloudConclusionAudience.COVERAGE,
            title="Cloud technology coverage observed",
            summary=theme.description,
            technical_interpretation=(
                "Family coverage summarizes distinct technology signal groups. "
                "It does not establish cloud readiness."
            ),
            theme_ids=(theme.theme_id,),
            finding_ids=theme.finding_ids,
            rule_ids=rule_ids_for_theme,
            confidence="medium",
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=CloudRecommendationKind.REVIEW_CLOUD_TECHNOLOGY_COVERAGE,
                action_key="review-cloud-technology-coverage",
                title="Review cloud technology coverage",
                action=(
                    "Review the linked Findings and confirm the observed "
                    "technology families remain intentional for this repository."
                ),
                rationale=(
                    "Technology coverage themes summarize inventory facts "
                    "without readiness scoring."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=CloudConclusionAudience.COVERAGE,
                theme_ids=(theme.theme_id,),
                finding_ids=theme.finding_ids,
                rule_ids=rule_ids_for_theme,
            )
        )

    if without_platform_findings:
        _emit_finding_theme(
            repository_id=repository_id,
            themes=themes,
            conclusions=conclusions,
            recommendations=recommendations,
            findings=without_platform_findings,
            theme_kind=CloudThemeKind.DEPLOYMENT_WITHOUT_PLATFORM,
            conclusion_kind=CloudConclusionKind.DEPLOYMENT_WITHOUT_PLATFORM_OBSERVED,
            recommendation_kind=CloudRecommendationKind.REVIEW_DEPLOYMENT_WITHOUT_PLATFORM,
            policy_id=POLICY_WITHOUT_PLATFORM,
            title="Deployment assets without platform evidence",
            description=(
                f"{len(without_platform_findings)} finding"
                f"{'' if len(without_platform_findings) == 1 else 's'} report "
                "cloud deployment assets without AWS, Azure, or GCP platform "
                "markers."
            ),
            conclusion_title="Deployment assets without platform evidence observed",
            technical_interpretation=(
                "This gap describes missing platform markers alongside "
                "deployment assets. It does not claim cloud usage is absent."
            ),
            recommendation_title="Review deployment assets without platform markers",
            recommendation_action=(
                "Review the linked findings and confirm whether platform "
                "markers are intentionally absent for this repository."
            ),
            recommendation_rationale=(
                "CLOUD-061 matched on deployment assets without platform "
                "markers; review stays observation-oriented."
            ),
            action_key="review-deployment-without-platform",
            rule_ids=(RULE_DEPLOYMENT_WITHOUT_PLATFORM,),
            ordering_key="19_without_platform",
            confidence="medium",
        )

    if findings_count == 0 and rules_executed > 0:
        theme = CloudTheme(
            theme_id=build_theme_id(
                kind=CloudThemeKind.NO_HYGIENE_FINDINGS.value,
                scope=CloudThemeScope.STATUS.value,
            ),
            kind=CloudThemeKind.NO_HYGIENE_FINDINGS,
            title="No hygiene findings in supported scope",
            description=(
                f"No Cloud Hygiene findings were emitted by the {rules_executed} "
                "enabled rules within the supported repository evidence scope."
            ),
            scope=CloudThemeScope.STATUS,
            rule_ids=tuple(HYGIENE_RULE_IDS),
            counts={"rules_executed": rules_executed, "finding_count": 0},
            ordering_key="20_no_findings",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_NO_FINDINGS,
            kind=CloudConclusionKind.NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
            audience=CloudConclusionAudience.STATUS,
            title="No hygiene findings in supported scope",
            summary=theme.description,
            technical_interpretation=(
                "Zero findings is a neutral inventory outcome for enabled "
                "hygiene rules. It does not establish cloud readiness."
            ),
            theme_ids=(theme.theme_id,),
            rule_ids=list(HYGIENE_RULE_IDS),
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=CloudRecommendationKind.ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE,
                action_key="acknowledge-no-hygiene-findings",
                title="Acknowledge zero hygiene findings in supported scope",
                action=(
                    "Treat zero Cloud Hygiene findings as a bounded inventory "
                    "outcome for the supported evidence and rule pack only."
                ),
                rationale=(
                    "Neutral acknowledgment prevents overstating risk or "
                    "readiness from an empty finding set."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=CloudConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
                rule_ids=list(HYGIENE_RULE_IDS),
            )
        )

    if limitations:
        theme = CloudTheme(
            theme_id=build_theme_id(
                kind=CloudThemeKind.UNSUPPORTED_ANALYSIS_SCOPE.value,
                scope=CloudThemeScope.STATUS.value,
            ),
            kind=CloudThemeKind.UNSUPPORTED_ANALYSIS_SCOPE,
            title="Unsupported cloud analysis scope",
            description=(
                f"{len(limitations)} documented limitation"
                f"{'' if len(limitations) == 1 else 's'} bound this assessment: "
                "provider APIs, readiness scoring, and modernization advice "
                "remain out of scope."
            ),
            scope=CloudThemeScope.STATUS,
            counts={"limitation_count": len(limitations)},
            ordering_key="30_unsupported_scope",
        )
        _assert_safe_text(theme.description)
        themes.append(theme)
        conclusion = _make_conclusion(
            repository_id=repository_id,
            policy_id=POLICY_UNSUPPORTED_SCOPE,
            kind=CloudConclusionKind.UNSUPPORTED_CLOUD_ANALYSIS_SCOPE,
            audience=CloudConclusionAudience.STATUS,
            title="Unsupported cloud analysis scope acknowledged",
            summary=theme.description,
            technical_interpretation=(
                "Synthesis uses repository-observable Cloud Hygiene evidence "
                "only. Provider APIs and readiness scores are not evaluated."
            ),
            theme_ids=(theme.theme_id,),
            metadata={"limitation_count": str(len(limitations))},
        )
        conclusions.append(conclusion)
        recommendations.append(
            _make_recommendation(
                kind=CloudRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_CLOUD_ANALYSIS_SCOPE,
                action_key="acknowledge-unsupported-cloud-analysis-scope",
                title="Acknowledge unsupported cloud analysis scope",
                action=(
                    "Interpret Cloud synthesis as hygiene inventory only until "
                    "additional cloud analysis capabilities exist."
                ),
                rationale=(
                    "Documented limitations keep conclusions from overstating "
                    "cloud readiness or portability."
                ),
                conclusion_ids=(conclusion.conclusion_id,),
                audience=CloudConclusionAudience.STATUS,
                theme_ids=(theme.theme_id,),
            )
        )

    themes_sorted = tuple(sorted(themes, key=lambda item: (item.ordering_key, item.theme_id)))
    recommendations_sorted = tuple(
        sorted(recommendations, key=lambda item: (item.kind.value, item.recommendation_id))
    )
    deduped: list[CloudRecommendation] = []
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
    status = CloudSynthesisStatus.EMPTY if findings_count == 0 else CloudSynthesisStatus.SUCCEEDED
    return CloudSynthesisResult(
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
