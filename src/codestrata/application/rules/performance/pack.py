"""Performance Intelligence pack metadata and rule construction (Phase 4.9.3)."""

from __future__ import annotations

from codestrata.application.rules.performance.rules import (
    BlockingSleepDetectedRule,
    BroadFoundationsRule,
    CachingDetectedRule,
    ConcurrencyDetectedRule,
    ConcurrencyWithoutConfigRule,
    ConfigControlsDetectedRule,
    DataAccessDetectedRule,
    DataAccessWithoutBatchingRule,
    DataWithoutCachingRule,
    ExecutorConfigDetectedRule,
    FrontendBundleDetectedRule,
    FrontendLazyDetectedRule,
    FrontendLimitedRule,
    LimitedControlsRule,
    MultipleDataAccessDetectedRule,
    ObservabilityDetectedRule,
    ResourceManagementDetectedRule,
    ResourcesWithoutManagementRule,
    SyncIoDetectedRule,
    WithoutObservabilityRule,
)
from codestrata.domain.performance.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
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
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory


class PerformanceRulePack:
    """First-class Performance Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.PERFORMANCE
    supported_languages: tuple[str, ...] = ()
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = "docs/analysis-intelligence/shared-rule-platform.md"
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.performance.enabled=true",
        "evidence.repository_performance.enabled=true",
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


def performance_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    candidates: list[tuple[str, SharedRule]] = [
        (RULE_DATA_ACCESS, DataAccessDetectedRule()),
        (RULE_MULTIPLE_DATA_ACCESS, MultipleDataAccessDetectedRule()),
        (RULE_DATA_ACCESS_WITHOUT_BATCHING, DataAccessWithoutBatchingRule()),
        (RULE_BLOCKING_SLEEP, BlockingSleepDetectedRule()),
        (RULE_SYNC_IO, SyncIoDetectedRule()),
        (RULE_CACHING, CachingDetectedRule()),
        (RULE_DATA_WITHOUT_CACHING, DataWithoutCachingRule()),
        (RULE_CONCURRENCY, ConcurrencyDetectedRule()),
        (RULE_EXECUTOR_CONFIG, ExecutorConfigDetectedRule()),
        (RULE_CONCURRENCY_WITHOUT_CONFIG, ConcurrencyWithoutConfigRule()),
        (RULE_RESOURCE_MGMT, ResourceManagementDetectedRule()),
        (RULE_RESOURCES_WITHOUT_MGMT, ResourcesWithoutManagementRule()),
        (RULE_FRONTEND_BUNDLE, FrontendBundleDetectedRule()),
        (RULE_FRONTEND_LAZY, FrontendLazyDetectedRule()),
        (RULE_FRONTEND_LIMITED, FrontendLimitedRule()),
        (RULE_OBSERVABILITY, ObservabilityDetectedRule()),
        (RULE_WITHOUT_OBSERVABILITY, WithoutObservabilityRule()),
        (RULE_CONFIG_CONTROLS, ConfigControlsDetectedRule()),
        (RULE_BROAD_FOUNDATIONS, BroadFoundationsRule()),
        (RULE_LIMITED_CONTROLS, LimitedControlsRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
