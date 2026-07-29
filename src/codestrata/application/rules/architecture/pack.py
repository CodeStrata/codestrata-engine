"""Architecture Intelligence pack metadata and rule construction (Phase 4.2.1)."""

from __future__ import annotations

from codestrata.application.rules.architecture.rules import (
    ComponentConcentrationRule,
    DependencyCycleRule,
    EnterpriseStandardMismatchRule,
    ExcessiveCrossModuleCouplingRule,
    FrameworkLeakageRule,
    InvalidDependencyDirectionRule,
    LayerBoundaryViolationRule,
)
from codestrata.domain.rules.architecture.ids import (
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory


class ArchitectureRulePack:
    """First-class Architecture Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.ARCHITECTURE
    supported_languages: tuple[str, ...] = (
        "java",
        "python",
        "javascript",
        "typescript",
        "php",
        "csharp",
    )
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = "docs/analysis-intelligence/architecture/rule-pack.md"
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.architecture.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = (
        "architecture.enterprise-standard-mismatch requires enterprise context",
    )
    included_rule_ids: tuple[str, ...] = (
        RULE_DEPENDENCY_CYCLE,
        RULE_INVALID_DEPENDENCY_DIRECTION,
        RULE_LAYER_BOUNDARY_VIOLATION,
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
        RULE_COMPONENT_CONCENTRATION,
        RULE_FRAMEWORK_LEAKAGE,
        RULE_ENTERPRISE_STANDARD_MISMATCH,
    )
    deferred_rule_ids: tuple[str, ...] = (
        # Distinct higher-level service graph is not yet available from Repository Graph.
        "architecture.service-dependency-cycle",
    )

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


def architecture_rules(
    *,
    outgoing_module_threshold: int = 8,
    minimum_module_count: int = 5,
    relative_multiplier: float = 2.0,
    exclude_composition_roots: bool = True,
    incident_edge_share_threshold: float = 0.30,
    minimum_component_count: int = 5,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    """Construct production Architecture Intelligence SharedRules."""

    candidates: list[tuple[str, SharedRule]] = [
        (RULE_DEPENDENCY_CYCLE, DependencyCycleRule()),
        (RULE_INVALID_DEPENDENCY_DIRECTION, InvalidDependencyDirectionRule()),
        (RULE_LAYER_BOUNDARY_VIOLATION, LayerBoundaryViolationRule()),
        (
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            ExcessiveCrossModuleCouplingRule(
                outgoing_threshold=outgoing_module_threshold,
                minimum_modules=minimum_module_count,
                relative_multiplier=relative_multiplier,
                exclude_composition_roots=exclude_composition_roots,
            ),
        ),
        (
            RULE_COMPONENT_CONCENTRATION,
            ComponentConcentrationRule(
                edge_share_threshold=incident_edge_share_threshold,
                minimum_components=minimum_component_count,
            ),
        ),
        (RULE_FRAMEWORK_LEAKAGE, FrameworkLeakageRule()),
        (RULE_ENTERPRISE_STANDARD_MISMATCH, EnterpriseStandardMismatchRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
