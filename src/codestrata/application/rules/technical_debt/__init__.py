"""Technical Debt Intelligence SharedRule package (Phase 4.3.3)."""

from codestrata.application.rules.technical_debt.pack import (
    TechnicalDebtRulePack,
    technical_debt_rules,
)
from codestrata.application.rules.technical_debt.registration import register_technical_debt_pack

__all__ = [
    "TechnicalDebtRulePack",
    "register_technical_debt_pack",
    "technical_debt_rules",
]
