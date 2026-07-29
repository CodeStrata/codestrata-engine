"""Technical debt taxonomy categories (Phase 4.3.1).

Aligned with docs/analysis-intelligence/shared-rule-platform.md. These are methodology
identifiers for future rules and assessment metadata — not executable rules.
"""

from __future__ import annotations

from enum import StrEnum


class TechnicalDebtCategory(StrEnum):
    """Bounded technical-debt taxonomy leaves.

    Values use the methodology kebab-case IDs under ``technical-debt.*``.
    """

    DEPRECATED_TECHNOLOGY = "technical-debt.deprecated-technology"
    UNSUPPORTED_DEPENDENCIES = "technical-debt.unsupported-dependencies"
    UPGRADE_RISK = "technical-debt.upgrade-risk"
    BUILD_DEBT = "technical-debt.build-debt"
    MIGRATION_BLOCKERS = "technical-debt.migration-blockers"
    LEGACY_FRAMEWORK_USAGE = "technical-debt.legacy-framework-usage"
    COMPLEXITY = "technical-debt.complexity"
    DUPLICATION = "technical-debt.duplication"
    SIZE = "technical-debt.size"
    CODE_SMELL = "technical-debt.code-smell"
    TEST_DEBT = "technical-debt.test-debt"
    DOCUMENTATION_DEBT = "technical-debt.documentation-debt"
    OTHER = "technical-debt.other"


# Stable ordered tuple for deterministic iteration / serialization helpers.
TECHNICAL_DEBT_CATEGORIES: tuple[TechnicalDebtCategory, ...] = tuple(
    TechnicalDebtCategory
)
