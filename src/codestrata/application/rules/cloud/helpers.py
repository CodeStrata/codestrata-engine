"""Shared helpers for Cloud Hygiene SharedRules (Phase 4.7.3)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.application.rules.confidence_catalog import confidence_for_rule
from codestrata.domain.cloud.ids import (
    PACK_ID,
    PACK_VERSION,
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
    RULE_VERSION,
)
from codestrata.domain.cloud.taxonomy import CloudCategory
from codestrata.domain.evidence.repository_cloud.enums import (
    CloudContainerKind,
    CloudDeploymentSystem,
    CloudIaCKind,
    CloudManagedServiceKind,
    CloudOrchestrationKind,
    CloudPlatformKind,
    CloudServerlessKind,
    EvidenceConfirmationLevel,
    RepositoryCloudParseStatus,
)
from codestrata.domain.evidence.repository_cloud.models import (
    AggregatedRepositoryCloudEvidence,
    CloudContainerFactEvidence,
    CloudDeploymentFactEvidence,
    CloudIaCFactEvidence,
    CloudManagedServiceFactEvidence,
    CloudOrchestrationFactEvidence,
    CloudPlatformFactEvidence,
    CloudServerlessFactEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    MatchEvidenceConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.rule_confidence import RuleConfidence
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult

_PROVENANCE = "aggregated_repository_cloud_evidence"
_MAX_PATH_EVIDENCE = 12

_ORCHESTRATION_KINDS = frozenset(
    {
        CloudOrchestrationKind.KUBERNETES,
        CloudOrchestrationKind.HELM,
        CloudOrchestrationKind.OPENSHIFT,
    }
)


def repository_cloud_evidence(
    context: RuleExecutionContext,
) -> AggregatedRepositoryCloudEvidence | None:
    raw = context.repository_cloud_evidence
    if isinstance(raw, AggregatedRepositoryCloudEvidence):
        return raw
    return None


def evidence_is_usable(
    evidence: AggregatedRepositoryCloudEvidence | None,
) -> bool:
    if evidence is None:
        return False
    if evidence.status in {
        RepositoryCloudParseStatus.NOT_APPLICABLE,
        RepositoryCloudParseStatus.SKIPPED,
        RepositoryCloudParseStatus.FAILED,
        RepositoryCloudParseStatus.INSUFFICIENT_EVIDENCE,
    }:
        return False
    if evidence.status not in {
        RepositoryCloudParseStatus.SUCCEEDED,
        RepositoryCloudParseStatus.PARTIALLY_SUCCEEDED,
    }:
        return False
    return bool(
        evidence.file_candidates
        or evidence.platform_facts
        or evidence.container_facts
        or evidence.orchestration_facts
        or evidence.iac_facts
        or evidence.serverless_facts
        or evidence.managed_service_facts
        or evidence.deployment_facts
    )


def known_platforms(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudPlatformKind, ...]:
    values = {
        item.platform
        for item in evidence.platform_facts
        if item.platform is not CloudPlatformKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_container_kinds(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudContainerKind, ...]:
    values = {
        item.kind
        for item in evidence.container_facts
        if item.kind is not CloudContainerKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_orchestration_kinds(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudOrchestrationKind, ...]:
    values = {
        item.kind for item in evidence.orchestration_facts if item.kind in _ORCHESTRATION_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_iac_kinds(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudIaCKind, ...]:
    values = {item.kind for item in evidence.iac_facts if item.kind is not CloudIaCKind.UNKNOWN}
    return tuple(sorted(values, key=lambda item: item.value))


def known_serverless_kinds(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudServerlessKind, ...]:
    values = {
        item.kind
        for item in evidence.serverless_facts
        if item.kind is not CloudServerlessKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def deployment_fact_is_confirmed(item: CloudDeploymentFactEvidence) -> bool:
    """True when a CI/CD artifact has confirmed cloud-deploy steps.

    Path discovery may classify every workflow as a deployment candidate.
    Build-only / echo-only workflows remain ``structurally_inspected`` and must
    not count as deployment-pipeline findings or the deployment signal family.
    """

    return item.confirmation_level in {
        EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        EvidenceConfirmationLevel.DECLARED,
        EvidenceConfirmationLevel.CONFIGURED,
    }


def known_deployment_systems(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudDeploymentSystem, ...]:
    values = {
        item.system
        for item in evidence.deployment_facts
        if item.system is not CloudDeploymentSystem.UNKNOWN
        and deployment_fact_is_confirmed(item)
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_managed_services(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[CloudManagedServiceKind, ...]:
    values = {
        item.service
        for item in evidence.managed_service_facts
        if item.service is not CloudManagedServiceKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def active_families(
    evidence: AggregatedRepositoryCloudEvidence,
) -> tuple[str, ...]:
    families: list[str] = []
    if known_platforms(evidence):
        families.append("platform")
    if known_container_kinds(evidence):
        families.append("container")
    if known_orchestration_kinds(evidence):
        families.append("orchestration")
    if known_iac_kinds(evidence):
        families.append("iac")
    if known_serverless_kinds(evidence):
        families.append("serverless")
    if known_managed_services(evidence):
        families.append("managed_service")
    if known_deployment_systems(evidence):
        families.append("deployment")
    return tuple(sorted(families))


def has_deployment_assets(evidence: AggregatedRepositoryCloudEvidence) -> bool:
    return bool(
        known_container_kinds(evidence)
        or known_orchestration_kinds(evidence)
        or known_deployment_systems(evidence)
        or known_serverless_kinds(evidence)
        or known_iac_kinds(evidence)
    )


def confidence_from_levels(
    levels: Sequence[EvidenceConfirmationLevel],
) -> MatchEvidenceConfidence:
    if any(level is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED for level in levels):
        return MatchEvidenceConfidence.HIGH
    if any(
        level
        in {
            EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            EvidenceConfirmationLevel.DECLARED,
            EvidenceConfirmationLevel.CONFIGURED,
        }
        for level in levels
    ):
        return MatchEvidenceConfidence.MEDIUM
    return MatchEvidenceConfidence.LOW


def observation_note(rule_id: str) -> str:
    return (
        "Observation only: review the repository-cloud evidence facts for "
        f"{rule_id}. This finding does not prescribe a remediation."
    )


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    severity: RuleSeverity = RuleSeverity.INFORMATIONAL,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.CLOUD,
        default_severity=severity,
        confidence=confidence_for_rule(rule_id),
        supported_languages=(),
        tags=("cloud", PACK_ID, "hygiene", "dimension:cloud"),
        remediation_summary=observation_note(rule_id),
        documentation_reference=("docs/analysis-intelligence/shared-rule-platform.md"),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: MatchEvidenceConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
    rule_confidence: RuleConfidence | None = None,
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        rule_confidence=rule_confidence or confidence_for_rule(rule_id),
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=observation_note(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_summary(
    *,
    rule_id: str,
    message: str,
    cloud_category: CloudCategory,
    attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    attrs = {
        "cloud_category": cloud_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.REPOSITORY_FACT,
        subject_reference=f"{rule_id}:summary",
        message=message,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def evidence_path(
    *,
    evidence_id: str,
    path: str,
    message: str,
    cloud_category: CloudCategory,
    attributes: dict[str, str] | None = None,
    line_start: int | None = None,
) -> RuleEvidence:
    attrs = {
        "evidence_id": evidence_id,
        "path": path,
        "cloud_category": cloud_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=evidence_id,
        message=message,
        safe_location=path,
        line_start=line_start,
        line_end=line_start,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def path_evidence_from_facts(
    *,
    facts: Sequence[
        CloudPlatformFactEvidence
        | CloudContainerFactEvidence
        | CloudOrchestrationFactEvidence
        | CloudIaCFactEvidence
        | CloudServerlessFactEvidence
        | CloudManagedServiceFactEvidence
        | CloudDeploymentFactEvidence
    ],
    cloud_category: CloudCategory,
    label: str,
) -> tuple[RuleEvidence, ...]:
    ordered = sorted(facts, key=lambda item: (item.path, item.evidence_id))
    items: list[RuleEvidence] = []
    for fact in ordered[:_MAX_PATH_EVIDENCE]:
        line = fact.line_hints[0] if fact.line_hints else None
        items.append(
            evidence_path(
                evidence_id=fact.evidence_id,
                path=fact.path,
                message=f"{label}; confirmation={fact.confirmation_level.value}",
                cloud_category=cloud_category,
                attributes={
                    "confirmation_level": fact.confirmation_level.value,
                    "detail": (fact.detail or "")[:200],
                },
                line_start=line,
            )
        )
    return tuple(items)


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    category = category_for_rule(rule_id)
    return {
        "taxonomy_id": category.value,
        "cloud_category": category.value,
        "assessment_dimensions": "cloud",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "observation_only": "true",
    }


def category_for_rule(rule_id: str) -> CloudCategory:
    mapping = {
        RULE_MULTIPLE_PLATFORMS: CloudCategory.PORTABILITY,
        RULE_PLATFORM_DETECTED: CloudCategory.RUNTIME,
        RULE_CONTAINERIZATION: CloudCategory.CONTAINER_READINESS,
        RULE_KUBERNETES: CloudCategory.CONTAINER_READINESS,
        RULE_IAC_PRESENT: CloudCategory.CONFIGURATION,
        RULE_MULTIPLE_IAC: CloudCategory.PORTABILITY,
        RULE_SERVERLESS: CloudCategory.RUNTIME,
        RULE_DEPLOYMENT_PIPELINE: CloudCategory.DEPLOYMENT_AUTOMATION,
        RULE_MANAGED_SERVICES: CloudCategory.MANAGED_SERVICE_COMPATIBILITY,
        RULE_CLOUD_NATIVE_INDICATORS: CloudCategory.MISCELLANEOUS,
        RULE_DEPLOYMENT_WITHOUT_PLATFORM: CloudCategory.CONFIGURATION,
    }
    return mapping.get(rule_id, CloudCategory.UNKNOWN)


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    str(item.rule_id),
                    tuple(item.subject_keys),
                    item.title,
                    item.summary,
                ),
            )
        )
    )
