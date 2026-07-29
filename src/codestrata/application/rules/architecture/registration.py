"""Register Architecture Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.architecture.pack import ArchitectureRulePack, architecture_rules
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import ArchitectureRulesSettings, RulesSettings


def register_architecture_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | ArchitectureRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> ArchitectureRulePack:
    """Register architecture.core rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = ArchitectureRulePack()
    arch = _architecture_settings(settings)
    enabled_ids = _enabled_rule_ids(arch) if for_execution else None
    rules = architecture_rules(
        outgoing_module_threshold=arch.excessive_cross_module_coupling.outgoing_module_threshold,
        minimum_module_count=arch.excessive_cross_module_coupling.minimum_module_count,
        relative_multiplier=arch.excessive_cross_module_coupling.relative_multiplier,
        exclude_composition_roots=(
            arch.excessive_cross_module_coupling.exclude_composition_roots
        ),
        incident_edge_share_threshold=arch.component_concentration.incident_edge_share_threshold,
        minimum_component_count=arch.component_concentration.minimum_component_count,
        enabled_rule_ids=enabled_ids,
    )
    registry.register_collection(rules, production=production)
    return pack


def _architecture_settings(
    settings: RulesSettings | ArchitectureRulesSettings | None,
) -> ArchitectureRulesSettings:
    if settings is None:
        return ArchitectureRulesSettings()
    if isinstance(settings, ArchitectureRulesSettings):
        return settings
    return settings.architecture


def _enabled_rule_ids(arch: ArchitectureRulesSettings) -> frozenset[str] | None:
    """Return None to include all pack rules; otherwise only explicitly enabled ones."""

    mapping = {
        "architecture.dependency-cycle": arch.dependency_cycle.enabled,
        "architecture.invalid-dependency-direction": arch.invalid_dependency_direction.enabled,
        "architecture.layer-boundary-violation": arch.layer_boundary_violation.enabled,
        "architecture.excessive-cross-module-coupling": (
            arch.excessive_cross_module_coupling.enabled
        ),
        "architecture.component-concentration": arch.component_concentration.enabled,
        "architecture.framework-leakage": arch.framework_leakage.enabled,
        "architecture.enterprise-standard-mismatch": arch.enterprise_standard_mismatch.enabled,
    }
    # Default: all enabled flags true within pack — still gated by pack.enabled at runtime.
    return frozenset(rule_id for rule_id, enabled in mapping.items() if enabled)
