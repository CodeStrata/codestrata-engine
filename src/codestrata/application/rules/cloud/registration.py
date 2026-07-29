"""Register Cloud Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.cloud.pack import CloudRulePack, cloud_rules
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import CloudRulesSettings, RulesSettings
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


def register_cloud_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | CloudRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> CloudRulePack:
    """Register cloud.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = CloudRulePack()
    cloud = _cloud_settings(settings)
    enabled_ids = _enabled_rule_ids(cloud) if for_execution else None
    rules = cloud_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _cloud_settings(
    settings: RulesSettings | CloudRulesSettings | None,
) -> CloudRulesSettings:
    if settings is None:
        return CloudRulesSettings()
    if isinstance(settings, CloudRulesSettings):
        return settings
    return settings.cloud


def _enabled_rule_ids(cloud: CloudRulesSettings) -> frozenset[str]:
    mapping = {
        RULE_MULTIPLE_PLATFORMS: cloud.cloud_001.enabled,
        RULE_PLATFORM_DETECTED: cloud.cloud_002.enabled,
        RULE_CONTAINERIZATION: cloud.cloud_010.enabled,
        RULE_KUBERNETES: cloud.cloud_011.enabled,
        RULE_IAC_PRESENT: cloud.cloud_020.enabled,
        RULE_MULTIPLE_IAC: cloud.cloud_021.enabled,
        RULE_SERVERLESS: cloud.cloud_030.enabled,
        RULE_DEPLOYMENT_PIPELINE: cloud.cloud_040.enabled,
        RULE_MANAGED_SERVICES: cloud.cloud_050.enabled,
        RULE_CLOUD_NATIVE_INDICATORS: cloud.cloud_060.enabled,
        RULE_DEPLOYMENT_WITHOUT_PLATFORM: cloud.cloud_061.enabled,
    }
    return frozenset(rule_id for rule_id in HYGIENE_RULE_IDS if mapping.get(rule_id, True))
