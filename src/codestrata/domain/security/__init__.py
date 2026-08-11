"""Security Intelligence domain (Phase 4.5.1+).

Taxonomy, pack identity, and assessment section contracts. Hygiene rules live
under ``application.rules.security`` and consume repository-sensitive evidence.
"""

from codestrata.domain.security.context import (
    CONTEXT_LABELS,
    NON_ACTIONABLE_CONTEXTS,
    SecurityContextDecision,
    SecurityEvidenceContext,
)
from codestrata.domain.security.ids import (
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_ID_PREFIX,
    TAXONOMY_NAMESPACE,
)
from codestrata.domain.security.taxonomy import (
    SECURITY_CATEGORIES,
    SecurityCategory,
    coerce_security_category,
)

__all__ = [
    "CONTEXT_LABELS",
    "NON_ACTIONABLE_CONTEXTS",
    "PACK_DESCRIPTION",
    "PACK_ID",
    "PACK_TITLE",
    "PACK_VERSION",
    "RULE_ID_PREFIX",
    "SECURITY_CATEGORIES",
    "TAXONOMY_NAMESPACE",
    "SecurityCategory",
    "SecurityContextDecision",
    "SecurityEvidenceContext",
    "coerce_security_category",
]
