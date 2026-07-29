"""Register Performance Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.performance.pack import (
    PerformanceRulePack,
    performance_rules,
)
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import PerformanceRulesSettings, RulesSettings
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


def register_performance_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | PerformanceRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> PerformanceRulePack:
    """Register performance.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = PerformanceRulePack()
    performance = _performance_settings(settings)
    enabled_ids = _enabled_rule_ids(performance) if for_execution else None
    rules = performance_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _performance_settings(
    settings: RulesSettings | PerformanceRulesSettings | None,
) -> PerformanceRulesSettings:
    if settings is None:
        return PerformanceRulesSettings()
    if isinstance(settings, PerformanceRulesSettings):
        return settings
    return settings.performance


def _enabled_rule_ids(performance: PerformanceRulesSettings) -> frozenset[str]:
    mapping = {
        RULE_DATA_ACCESS: performance.perf_001.enabled,
        RULE_MULTIPLE_DATA_ACCESS: performance.perf_002.enabled,
        RULE_DATA_ACCESS_WITHOUT_BATCHING: performance.perf_003.enabled,
        RULE_BLOCKING_SLEEP: performance.perf_010.enabled,
        RULE_SYNC_IO: performance.perf_011.enabled,
        RULE_CACHING: performance.perf_020.enabled,
        RULE_DATA_WITHOUT_CACHING: performance.perf_021.enabled,
        RULE_CONCURRENCY: performance.perf_030.enabled,
        RULE_EXECUTOR_CONFIG: performance.perf_031.enabled,
        RULE_CONCURRENCY_WITHOUT_CONFIG: performance.perf_032.enabled,
        RULE_RESOURCE_MGMT: performance.perf_040.enabled,
        RULE_RESOURCES_WITHOUT_MGMT: performance.perf_041.enabled,
        RULE_FRONTEND_BUNDLE: performance.perf_050.enabled,
        RULE_FRONTEND_LAZY: performance.perf_051.enabled,
        RULE_FRONTEND_LIMITED: performance.perf_052.enabled,
        RULE_OBSERVABILITY: performance.perf_060.enabled,
        RULE_WITHOUT_OBSERVABILITY: performance.perf_061.enabled,
        RULE_CONFIG_CONTROLS: performance.perf_070.enabled,
        RULE_BROAD_FOUNDATIONS: performance.perf_071.enabled,
        RULE_LIMITED_CONTROLS: performance.perf_072.enabled,
    }
    return frozenset(rule_id for rule_id in HYGIENE_RULE_IDS if mapping.get(rule_id, True))
