"""Register Test Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.testing.pack import TestingRulePack, testing_rules
from codestrata.config.settings import RulesSettings, TestingRulesSettings
from codestrata.domain.testing.ids import (
    HYGIENE_RULE_IDS,
    RULE_COVERAGE_WITHOUT_CI_INVOCATION,
    RULE_DECLARED_WITHOUT_OBSERVATION,
    RULE_DISABLED_OR_SKIPPED,
    RULE_UNCONFIRMED_CANDIDATES,
)


def register_testing_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | TestingRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> TestingRulePack:
    """Register testing.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = TestingRulePack()
    testing = _testing_settings(settings)
    enabled_ids = _enabled_rule_ids(testing) if for_execution else None
    rules = testing_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _testing_settings(
    settings: RulesSettings | TestingRulesSettings | None,
) -> TestingRulesSettings:
    if settings is None:
        return TestingRulesSettings()
    if isinstance(settings, TestingRulesSettings):
        return settings
    return settings.testing


def _enabled_rule_ids(testing: TestingRulesSettings) -> frozenset[str]:
    mapping = {
        RULE_DISABLED_OR_SKIPPED: testing.test_001.enabled,
        RULE_UNCONFIRMED_CANDIDATES: testing.test_002.enabled,
        RULE_DECLARED_WITHOUT_OBSERVATION: testing.test_003.enabled,
        RULE_COVERAGE_WITHOUT_CI_INVOCATION: testing.test_005.enabled,
    }
    # Preserve catalog order for deterministic registration.
    return frozenset(
        rule_id for rule_id in HYGIENE_RULE_IDS if mapping.get(rule_id, True)
    )
