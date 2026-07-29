"""Dependency Intelligence pack metadata and rule construction (Phase 4.4.3)."""

from __future__ import annotations

from codestrata.application.rules.dependency.rules import (
    ConflictingExactVersionsRule,
    DuplicateDeclarationRule,
    MutableVersionRule,
    UnboundedRequirementRule,
    UnresolvedVersionRule,
)
from codestrata.domain.dependency.ids import (
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_CONFLICTING_EXACT_VERSIONS,
    RULE_DUPLICATE_DECLARATION,
    RULE_MUTABLE_VERSION,
    RULE_UNBOUNDED_REQUIREMENT,
    RULE_UNRESOLVED_VERSION,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory


class DependencyRulePack:
    """First-class Dependency Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.DEPENDENCY
    supported_languages: tuple[str, ...] = ("java", "python", "php", "csharp")
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = (
        "docs/analysis-intelligence/shared-rule-platform.md"
    )
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.dependency.enabled=true",
        "evidence.dependency.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = HYGIENE_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = (
        "dependency.outdated-version",
        "dependency.unused-declaration",
        "dependency.transitive-conflict",
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
            "enterprise_context_requirements": list(
                self.enterprise_context_requirements
            ),
            "documentation_reference": self.documentation_reference,
        }


def dependency_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    """Construct production Dependency hygiene SharedRules."""

    candidates: list[tuple[str, SharedRule]] = [
        (RULE_UNRESOLVED_VERSION, UnresolvedVersionRule()),
        (RULE_MUTABLE_VERSION, MutableVersionRule()),
        (RULE_UNBOUNDED_REQUIREMENT, UnboundedRequirementRule()),
        (RULE_CONFLICTING_EXACT_VERSIONS, ConflictingExactVersionsRule()),
        (RULE_DUPLICATE_DECLARATION, DuplicateDeclarationRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
