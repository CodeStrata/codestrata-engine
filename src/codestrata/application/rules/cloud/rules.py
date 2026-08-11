"""Cloud Hygiene SharedRules (Phase 4.7.3).

Rules consume AggregatedRepositoryCloudEvidence only. They never re-read
repository files, call cloud APIs, or invent readiness conclusions.
"""

from __future__ import annotations

from codestrata.application.rules.cloud.helpers import (
    _sorted_matches,
    active_families,
    confidence_from_levels,
    deployment_fact_is_confirmed,
    evidence_is_usable,
    evidence_summary,
    has_deployment_assets,
    known_container_kinds,
    known_deployment_systems,
    known_iac_kinds,
    known_managed_services,
    known_orchestration_kinds,
    known_platforms,
    known_serverless_kinds,
    make_metadata,
    match,
    path_evidence_from_facts,
    repository_cloud_evidence,
)
from codestrata.domain.cloud.ids import (
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
from codestrata.domain.cloud.taxonomy import CloudCategory
from codestrata.domain.evidence.repository_cloud.models import (
    CloudContainerFactEvidence,
    CloudDeploymentFactEvidence,
    CloudIaCFactEvidence,
    CloudOrchestrationFactEvidence,
    CloudServerlessFactEvidence,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleSeverity, RuleSkipReason
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult

_DeploymentAssetFact = (
    CloudContainerFactEvidence
    | CloudOrchestrationFactEvidence
    | CloudIaCFactEvidence
    | CloudServerlessFactEvidence
    | CloudDeploymentFactEvidence
)


def _cloud_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = repository_cloud_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Repository-cloud evidence unavailable",
        )
    if not evidence_is_usable(evidence):
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=f"Repository-cloud evidence status is {evidence.status.value}",
        )
    return RuleApplicability.applicable()


class MultipleCloudProvidersRule:
    """Flags when two or more cloud platforms are observed."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_MULTIPLE_PLATFORMS,
            title="Multiple cloud providers detected",
            description=(
                "Detects repository-observable signals for two or more cloud "
                "platforms. Does not claim multi-cloud architecture quality."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        platforms = known_platforms(evidence)
        if len(platforms) < 2:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in platforms)
        facts = [item for item in evidence.platform_facts if item.platform in platforms]
        category = CloudCategory.PORTABILITY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_MULTIPLE_PLATFORMS,
                message=f"platform_count={len(platforms)}; platforms={joined}",
                cloud_category=category,
                attributes={
                    "platform_count": str(len(platforms)),
                    "platforms": joined,
                },
            ),
            *path_evidence_from_facts(facts=facts, cloud_category=category, label="platform_fact"),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_MULTIPLE_PLATFORMS,
                    title="Multiple cloud providers detected",
                    summary=(f"Observed signals for {len(platforms)} cloud platforms ({joined})."),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_MULTIPLE_PLATFORMS, "platforms", joined),
                )
            ]
        )


class CloudPlatformDetectedRule:
    """Flags a single observed cloud platform (suppressed when CLOUD-001 matches)."""

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_PLATFORM_DETECTED,
            title="Cloud platform detected",
            description=(
                "Detects repository-observable signals for a single cloud "
                "platform. Does not claim the repository is cloud ready."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        platforms = known_platforms(evidence)
        if len(platforms) != 1:
            return SharedRuleEvaluationResult.not_matched()
        platform = platforms[0]
        facts = [item for item in evidence.platform_facts if item.platform is platform]
        category = CloudCategory.RUNTIME
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_PLATFORM_DETECTED,
                message=f"platform={platform.value}",
                cloud_category=category,
                attributes={"platforms": platform.value, "platform_count": "1"},
            ),
            *path_evidence_from_facts(facts=facts, cloud_category=category, label="platform_fact"),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_PLATFORM_DETECTED,
                    title="Cloud platform detected",
                    summary=f"Observed cloud platform signal: {platform.value}.",
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_PLATFORM_DETECTED,
                        "platform",
                        platform.value,
                    ),
                )
            ]
        )


class ContainerizationDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CONTAINERIZATION,
            title="Containerization detected",
            description=("Detects Docker, Compose, Podman, or related container artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        kinds = known_container_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.container_facts if item.kind in kinds]
        category = CloudCategory.CONTAINER_READINESS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CONTAINERIZATION,
                message=f"container_kinds={joined}",
                cloud_category=category,
                attributes={"container_kinds": joined},
            ),
            *path_evidence_from_facts(facts=facts, cloud_category=category, label="container_fact"),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CONTAINERIZATION,
                    title="Containerization detected",
                    summary=f"Observed containerization artifacts ({joined}).",
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_CONTAINERIZATION, "containers", joined),
                )
            ]
        )


class KubernetesDeploymentDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_KUBERNETES,
            title="Kubernetes deployment detected",
            description=("Detects Kubernetes, Helm, or OpenShift orchestration artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        kinds = known_orchestration_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.orchestration_facts if item.kind in kinds]
        category = CloudCategory.CONTAINER_READINESS
        severity = RuleSeverity.LOW if len(kinds) >= 2 else RuleSeverity.INFORMATIONAL
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_KUBERNETES,
                message=f"orchestration_kinds={joined}",
                cloud_category=category,
                attributes={"orchestration_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, cloud_category=category, label="orchestration_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_KUBERNETES,
                    title="Kubernetes deployment detected",
                    summary=(f"Observed container orchestration artifacts ({joined})."),
                    severity=severity,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_KUBERNETES, "orchestration", joined),
                )
            ]
        )


class InfrastructureAsCodePresentRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_IAC_PRESENT,
            title="Infrastructure as Code present",
            description=("Detects Terraform, CloudFormation, CDK, Pulumi, ARM, or Bicep."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        kinds = known_iac_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.iac_facts if item.kind in kinds]
        category = CloudCategory.CONFIGURATION
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_IAC_PRESENT,
                message=f"iac_kinds={joined}",
                cloud_category=category,
                attributes={"iac_kinds": joined},
            ),
            *path_evidence_from_facts(facts=facts, cloud_category=category, label="iac_fact"),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_IAC_PRESENT,
                    title="Infrastructure as Code present",
                    summary=f"Observed Infrastructure as Code artifacts ({joined}).",
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_IAC_PRESENT, "iac", joined),
                )
            ]
        )


class MultipleIaCTechnologiesRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_MULTIPLE_IAC,
            title="Multiple IaC technologies detected",
            description=("Detects two or more distinct Infrastructure as Code technologies."),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        kinds = known_iac_kinds(evidence)
        if len(kinds) < 2:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.iac_facts if item.kind in kinds]
        category = CloudCategory.PORTABILITY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_MULTIPLE_IAC,
                message=f"iac_kind_count={len(kinds)}; iac_kinds={joined}",
                cloud_category=category,
                attributes={
                    "iac_kinds": joined,
                    "iac_kind_count": str(len(kinds)),
                },
            ),
            *path_evidence_from_facts(facts=facts, cloud_category=category, label="iac_fact"),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_MULTIPLE_IAC,
                    title="Multiple IaC technologies detected",
                    summary=(
                        f"Observed {len(kinds)} Infrastructure as Code technologies ({joined})."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_MULTIPLE_IAC, "iac_multi", joined),
                )
            ]
        )


class ServerlessDeploymentDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_SERVERLESS,
            title="Serverless deployment detected",
            description=("Detects serverless frameworks or function packaging artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        kinds = known_serverless_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.serverless_facts if item.kind in kinds]
        category = CloudCategory.RUNTIME
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_SERVERLESS,
                message=f"serverless_kinds={joined}",
                cloud_category=category,
                attributes={"serverless_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, cloud_category=category, label="serverless_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_SERVERLESS,
                    title="Serverless deployment detected",
                    summary=f"Observed serverless artifacts ({joined}).",
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_SERVERLESS, "serverless", joined),
                )
            ]
        )


class CloudDeploymentPipelineDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DEPLOYMENT_PIPELINE,
            title="Cloud deployment pipeline detected",
            description=(
                "Detects CI/CD or GitOps deployment pipeline artifacts with cloud-related signals."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        systems = known_deployment_systems(evidence)
        if not systems:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in systems)
        facts = [
            item
            for item in evidence.deployment_facts
            if item.system in systems and deployment_fact_is_confirmed(item)
        ]
        category = CloudCategory.DEPLOYMENT_AUTOMATION
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DEPLOYMENT_PIPELINE,
                message=f"deployment_systems={joined}",
                cloud_category=category,
                attributes={"deployment_systems": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, cloud_category=category, label="deployment_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DEPLOYMENT_PIPELINE,
                    title="Cloud deployment pipeline detected",
                    summary=f"Observed cloud deployment pipeline artifacts ({joined}).",
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_DEPLOYMENT_PIPELINE, "deployment", joined),
                )
            ]
        )


class ManagedCloudServicesDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_MANAGED_SERVICES,
            title="Managed cloud services detected",
            description=("Detects managed cloud service resource markers in repository artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        services = known_managed_services(evidence)
        if not services:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in services)
        facts = [item for item in evidence.managed_service_facts if item.service in services]
        category = CloudCategory.MANAGED_SERVICE_COMPATIBILITY
        severity = RuleSeverity.LOW if len(services) >= 3 else RuleSeverity.INFORMATIONAL
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_MANAGED_SERVICES,
                message=f"managed_services={joined}",
                cloud_category=category,
                attributes={
                    "managed_services": joined,
                    "managed_service_count": str(len(services)),
                },
            ),
            *path_evidence_from_facts(
                facts=facts, cloud_category=category, label="managed_service_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_MANAGED_SERVICES,
                    title="Managed cloud services detected",
                    summary=f"Observed managed cloud service markers ({joined}).",
                    severity=severity,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_MANAGED_SERVICES, "managed_services", joined),
                )
            ]
        )


class CloudNativeRepositoryIndicatorsRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_CLOUD_NATIVE_INDICATORS,
            title="Cloud-native repository indicators",
            description=(
                "Detects multiple distinct cloud evidence families in one "
                "repository. Does not establish cloud readiness."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        families = active_families(evidence)
        if len(families) < 3:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(families)
        category = CloudCategory.MISCELLANEOUS
        levels = [
            *(item.confirmation_level for item in evidence.platform_facts),
            *(item.confirmation_level for item in evidence.container_facts),
            *(item.confirmation_level for item in evidence.orchestration_facts),
            *(item.confirmation_level for item in evidence.iac_facts),
            *(item.confirmation_level for item in evidence.serverless_facts),
            *(item.confirmation_level for item in evidence.managed_service_facts),
            *(item.confirmation_level for item in evidence.deployment_facts),
        ]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_CLOUD_NATIVE_INDICATORS,
                message=f"family_count={len(families)}; families={joined}",
                cloud_category=category,
                attributes={
                    "families": joined,
                    "family_count": str(len(families)),
                    "technologies": ",".join(evidence.coverage.technologies_represented),
                },
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_CLOUD_NATIVE_INDICATORS,
                    title="Cloud-native repository indicators",
                    summary=(
                        f"Observed {len(families)} cloud evidence families "
                        f"({joined}). This does not establish cloud readiness."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels(levels),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_CLOUD_NATIVE_INDICATORS,
                        "cloud_native",
                        joined,
                    ),
                )
            ]
        )


class DeploymentWithoutPlatformRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DEPLOYMENT_WITHOUT_PLATFORM,
            title=("Cloud deployment assets without runtime platform evidence"),
            description=(
                "Detects container, orchestration, IaC, serverless, or pipeline "
                "assets when no AWS/Azure/GCP platform marker is observed."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _cloud_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_cloud_evidence(context)
        assert evidence is not None
        if known_platforms(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if not has_deployment_assets(evidence):
            return SharedRuleEvaluationResult.not_matched()
        asset_count = (
            len(known_container_kinds(evidence))
            + len(known_orchestration_kinds(evidence))
            + len(known_iac_kinds(evidence))
            + len(known_serverless_kinds(evidence))
            + len(known_deployment_systems(evidence))
        )
        families = active_families(evidence)
        joined = ",".join(families)
        category = CloudCategory.CONFIGURATION
        sample_facts: list[_DeploymentAssetFact] = [
            *evidence.container_facts,
            *evidence.orchestration_facts,
            *evidence.iac_facts,
            *evidence.serverless_facts,
            *evidence.deployment_facts,
        ]
        levels = [item.confirmation_level for item in sample_facts]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DEPLOYMENT_WITHOUT_PLATFORM,
                message=(f"deployment_asset_kinds={asset_count}; families={joined}; platforms=0"),
                cloud_category=category,
                attributes={
                    "families": joined,
                    "platform_count": "0",
                    "deployment_asset_kinds": str(asset_count),
                },
            ),
            *path_evidence_from_facts(
                facts=sample_facts,
                cloud_category=category,
                label="deployment_asset",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DEPLOYMENT_WITHOUT_PLATFORM,
                    title=("Cloud deployment assets without runtime platform evidence"),
                    summary=(
                        "Observed cloud deployment assets without AWS, Azure, or "
                        "GCP platform markers. This does not claim cloud usage "
                        "is absent."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels(levels),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_DEPLOYMENT_WITHOUT_PLATFORM,
                        "deployment_without_platform",
                        str(asset_count),
                    ),
                )
            ]
        )
