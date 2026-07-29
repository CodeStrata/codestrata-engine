"""Technical Debt Intelligence domain (Phase 4.3).

Phase 4.3.3 registers complexity SharedRules under ``technical_debt.core``.
Assessment synthesis and report integration remain deferred.
"""

from codestrata.domain.technical_debt.ids import (
    COMPLEXITY_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_ID_PREFIX,
    TAXONOMY_NAMESPACE,
)
from codestrata.domain.technical_debt.taxonomy import (
    TECHNICAL_DEBT_CATEGORIES,
    TechnicalDebtCategory,
)

__all__ = [
    "COMPLEXITY_RULE_IDS",
    "PACK_DESCRIPTION",
    "PACK_ID",
    "PACK_TITLE",
    "PACK_VERSION",
    "RULE_ID_PREFIX",
    "TAXONOMY_NAMESPACE",
    "TECHNICAL_DEBT_CATEGORIES",
    "TechnicalDebtCategory",
]
