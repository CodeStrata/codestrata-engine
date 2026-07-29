"""Cloud Intelligence pack metadata and rule construction (Phase 4.7.3)."""

from __future__ import annotations

from codestrata.application.rules.cloud.rules import (
    CloudDeploymentPipelineDetectedRule,
    CloudNativeRepositoryIndicatorsRule,
    CloudPlatformDetectedRule,
    ContainerizationDetectedRule,
    DeploymentWithoutPlatformRule,
    InfrastructureAsCodePresentRule,
    KubernetesDeploymentDetectedRule,
    ManagedCloudServicesDetectedRule,
    MultipleCloudProvidersRule,
    MultipleIaCTechnologiesRule,
    ServerlessDeploymentDetectedRule,
)
from codestrata.domain.cloud.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
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
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory


class CloudRulePack:
    """First-class Cloud Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.CLOUD
    supported_languages: tuple[str, ...] = ()
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = "docs/analysis-intelligence/shared-rule-platform.md"
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.cloud.enabled=true",
        "evidence.repository_cloud.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = HYGIENE_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = DEFERRED_RULE_IDS

    def to_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "included_rule_ids": list(self.included_rule_ids),
            "deferred_rule_ids": list(self.deferred_rule_ids),
            "supported_languages": list(self.supported_languages),
            "default_enabled": self.default_enabled,
            "requires_enterprise_context": self.requires_enterprise_context,
            "configuration_requirements": list(self.configuration_requirements),
            "enterprise_context_requirements": list(self.enterprise_context_requirements),
            "documentation_reference": self.documentation_reference,
        }


def cloud_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    candidates: list[tuple[str, SharedRule]] = [
        (RULE_MULTIPLE_PLATFORMS, MultipleCloudProvidersRule()),
        (RULE_PLATFORM_DETECTED, CloudPlatformDetectedRule()),
        (RULE_CONTAINERIZATION, ContainerizationDetectedRule()),
        (RULE_KUBERNETES, KubernetesDeploymentDetectedRule()),
        (RULE_IAC_PRESENT, InfrastructureAsCodePresentRule()),
        (RULE_MULTIPLE_IAC, MultipleIaCTechnologiesRule()),
        (RULE_SERVERLESS, ServerlessDeploymentDetectedRule()),
        (RULE_DEPLOYMENT_PIPELINE, CloudDeploymentPipelineDetectedRule()),
        (RULE_MANAGED_SERVICES, ManagedCloudServicesDetectedRule()),
        (RULE_CLOUD_NATIVE_INDICATORS, CloudNativeRepositoryIndicatorsRule()),
        (RULE_DEPLOYMENT_WITHOUT_PLATFORM, DeploymentWithoutPlatformRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
