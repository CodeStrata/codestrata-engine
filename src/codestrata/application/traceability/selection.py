"""Primary evidence selection and finding-level traceability assembly."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.traceability import (
    EvidenceCompleteness,
    EvidenceProductionMode,
    EvidenceRef,
    dedupe_evidence_refs,
    order_evidence_refs,
)

_MODE_RANK = {
    EvidenceProductionMode.DIRECT: 0,
    EvidenceProductionMode.AGGREGATED: 1,
    EvidenceProductionMode.SYNTHESIZED: 2,
    EvidenceProductionMode.LEGACY: 3,
}


def select_primary_evidence_id(refs: Sequence[EvidenceRef]) -> str | None:
    """Select primary evidence: direct → aggregated → synthesized → legacy → sort key."""

    if not refs:
        return None
    ordered = sorted(
        refs,
        key=lambda item: (
            _MODE_RANK.get(item.production_mode, 99),
            item.sort_key(),
        ),
    )
    return ordered[0].evidence_id


def synthesize_finding_traceability(
    refs: Sequence[EvidenceRef],
    *,
    expected_count: int | None = None,
    limitations: Sequence[str] = (),
) -> tuple[
    tuple[EvidenceRef, ...],
    str | None,
    tuple[str, ...],
    EvidenceCompleteness,
    tuple[str, ...],
]:
    """Normalize refs and derive primary / synthesized / completeness."""

    unique = dedupe_evidence_refs(tuple(refs))
    ordered = order_evidence_refs(unique)
    primary = select_primary_evidence_id(ordered)
    synthesized = (
        tuple(sorted({item.evidence_id for item in ordered}))
        if len(ordered) > 1
        else ()
    )
    limits = tuple(sorted({str(item).strip() for item in limitations if str(item).strip()}))
    if not ordered:
        completeness = EvidenceCompleteness.UNAVAILABLE
    elif expected_count is not None and expected_count > len(ordered):
        completeness = EvidenceCompleteness.PARTIAL
        limits = tuple(sorted({*limits, "some_rule_evidence_unmapped"}))
    else:
        completeness = EvidenceCompleteness.COMPLETE
    return ordered, primary, synthesized, completeness, limits
