"""Technical debt evidence consumers (projections only; Phase 4.3.2)."""

from codestrata.application.technical_debt.evidence.complexity_projection import (
    complexity_evidence_for_debt,
    complexity_taxonomy_category,
)

__all__ = [
    "complexity_evidence_for_debt",
    "complexity_taxonomy_category",
]
