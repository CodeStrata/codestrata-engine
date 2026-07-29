"""Register Dependency Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.dependency.pack import DependencyRulePack, dependency_rules
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import DependencyRulesSettings, RulesSettings
from codestrata.domain.dependency.ids import (
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_UNRESOLVED_VERSION,
)


def register_dependency_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | DependencyRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> DependencyRulePack:
    """Register dependency.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = DependencyRulePack()
    dependency = _dependency_settings(settings)
    enabled_ids = _enabled_rule_ids(dependency) if for_execution else None
    rules = dependency_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _dependency_settings(
    settings: RulesSettings | DependencyRulesSettings | None,
) -> DependencyRulesSettings:
    if settings is None:
        return DependencyRulesSettings()
    if isinstance(settings, DependencyRulesSettings):
        return settings
    return settings.dependency


def _enabled_rule_ids(dependency: DependencyRulesSettings) -> frozenset[str]:
    mapping = {
        RULE_UNRESOLVED_VERSION: dependency.unresolved_version.enabled,
        RULE_MUTABLE_VERSION: dependency.mutable_version.enabled,
        RULE_UNBOUNDED_REQUIREMENT: dependency.unbounded_requirement.enabled,
        RULE_CONFLICTING_EXACT_VERSIONS: dependency.conflicting_exact_versions.enabled,
        RULE_DUPLICATE_DECLARATION: dependency.duplicate_declaration.enabled,
    }
    return frozenset(rule_id for rule_id, enabled in mapping.items() if enabled)
