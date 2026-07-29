"""Register Technical Debt Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.registry import RuleRegistry
from codestrata.application.rules.technical_debt.pack import (
    TechnicalDebtRulePack,
    technical_debt_rules,
)
from codestrata.config.settings import RulesSettings, TechnicalDebtRulesSettings


def register_technical_debt_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | TechnicalDebtRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> TechnicalDebtRulePack:
    """Register technical_debt.core rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = TechnicalDebtRulePack()
    debt = _technical_debt_settings(settings)
    complexity = debt.complexity
    enabled_ids = _enabled_rule_ids(debt) if for_execution else None
    if for_execution and not complexity.enabled:
        enabled_ids = frozenset()
    rules = technical_debt_rules(
        large_callable_max_lines=complexity.large_callable.max_physical_lines,
        excessive_branching_max_branch_points=(
            complexity.excessive_branching.max_branch_points
        ),
        deep_nesting_max_depth=complexity.deep_nesting.max_nesting_depth,
        excessive_parameters_max_count=complexity.excessive_parameters.max_parameters,
        oversized_type_max_lines=complexity.oversized_type.max_physical_lines,
        enabled_rule_ids=enabled_ids,
    )
    registry.register_collection(rules, production=production)
    return pack


def _technical_debt_settings(
    settings: RulesSettings | TechnicalDebtRulesSettings | None,
) -> TechnicalDebtRulesSettings:
    if settings is None:
        return TechnicalDebtRulesSettings()
    if isinstance(settings, TechnicalDebtRulesSettings):
        return settings
    return settings.technical_debt


def _enabled_rule_ids(debt: TechnicalDebtRulesSettings) -> frozenset[str]:
    complexity = debt.complexity
    mapping = {
        "technical_debt.large-callable": complexity.large_callable.enabled,
        "technical_debt.excessive-branching": complexity.excessive_branching.enabled,
        "technical_debt.deep-nesting": complexity.deep_nesting.enabled,
        "technical_debt.excessive-parameters": complexity.excessive_parameters.enabled,
        "technical_debt.oversized-type": complexity.oversized_type.enabled,
    }
    return frozenset(rule_id for rule_id, enabled in mapping.items() if enabled)
