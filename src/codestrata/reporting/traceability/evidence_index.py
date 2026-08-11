"""Collect and serialize assessment.evidence from canonical findings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from codestrata.domain.traceability import EvidenceRef, dedupe_evidence_refs, order_evidence_refs
from codestrata.domain.traceability.serialization import evidence_ref_to_stable_dict
from codestrata.reporting.customer_universe import CustomerFinding


def collect_assessment_evidence(
    findings: Sequence[CustomerFinding],
) -> tuple[EvidenceRef, ...]:
    """Return unique EvidenceRefs referenced by canonical findings.

    Only includes evidence attached to findings — never fabricates unreferenced
    envelopes. Contradictory duplicates raise via ``dedupe_evidence_refs``.
    """

    collected: list[EvidenceRef] = []
    for finding in findings:
        for ref in finding.evidence_refs:
            if isinstance(ref, EvidenceRef):
                collected.append(ref)
    if not collected:
        return ()
    return order_evidence_refs(dedupe_evidence_refs(tuple(collected)))


def serialize_evidence_index(refs: Sequence[EvidenceRef]) -> list[dict[str, Any]]:
    """Serialize EvidenceRef envelopes for assessment.evidence."""

    return [evidence_ref_to_stable_dict(item) for item in refs]
