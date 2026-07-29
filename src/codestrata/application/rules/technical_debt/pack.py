"""Technical Debt Intelligence pack metadata and rule construction (Phase 4.3.3)."""

from __future__ import annotations

from codestrata.application.rules.technical_debt.rules import (
    DeepNestingRule,
    ExcessiveBranchingRule,
    ExcessiveParametersRule,
    LargeCallableRule,
    OversizedTypeRule,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory
from codestrata.domain.technical_debt.ids import (
    COMPLEXITY_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_DEEP_NESTING,
    RULE_EXCESSIVE_BRANCHING,
    RULE_EXCESSIVE_PARAMETERS,
    RULE_LARGE_CALLABLE,
    RULE_OVERSIZED_TYPE,
)


class TechnicalDebtRulePack:
    """First-class Technical Debt Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.TECHNICAL_DEBT
    supported_languages: tuple[str, ...] = ("java", "python", "php", "csharp")
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = (
        "docs/analysis-intelligence/shared-rule-platform.md"
    )
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.technical_debt.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = COMPLEXITY_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = (
        "technical_debt.duplication",
        "technical_debt.code-smell",
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


def technical_debt_rules(
    *,
    large_callable_max_lines: int = 50,
    excessive_branching_max_branch_points: int = 10,
    deep_nesting_max_depth: int = 4,
    excessive_parameters_max_count: int = 5,
    oversized_type_max_lines: int = 300,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    """Construct production Technical Debt complexity SharedRules."""

    candidates: list[tuple[str, SharedRule]] = [
        (
            RULE_LARGE_CALLABLE,
            LargeCallableRule(max_physical_lines=large_callable_max_lines),
        ),
        (
            RULE_EXCESSIVE_BRANCHING,
            ExcessiveBranchingRule(
                max_branch_points=excessive_branching_max_branch_points
            ),
        ),
        (
            RULE_DEEP_NESTING,
            DeepNestingRule(max_nesting_depth=deep_nesting_max_depth),
        ),
        (
            RULE_EXCESSIVE_PARAMETERS,
            ExcessiveParametersRule(max_parameters=excessive_parameters_max_count),
        ),
        (
            RULE_OVERSIZED_TYPE,
            OversizedTypeRule(max_physical_lines=oversized_type_max_lines),
        ),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
