"""Application-layer EvidenceRef builders for findings (Epic 2 Slice 2.2).

Domain ``traceability`` stays pack-agnostic. Conversion from RuleEvidence /
Phase-1 evidence lives here so analyzer packs do not leak into the domain.

Slice 2.2 pack coverage:
- Fully wired: security, dependency, technical_debt
- Deferred (empty evidence_refs + legacy completeness): architecture, testing,
  cloud, ai_readiness, performance, and other packs — map in later slices
  without fabricating EvidenceRefs here.

Slice 2.3 adds Recommendation → Finding helpers in ``recommendation.py``.
"""

from codestrata.application.traceability.merge import merge_finding_traceability
from codestrata.application.traceability.recommendation import (
    attach_recommendation_traceability,
    merge_recommendation_traceability,
    select_primary_finding_id,
    synthesize_recommendation_traceability,
)
from codestrata.application.traceability.rule_evidence import (
    TRACEABLE_PACK_PREFIXES,
    evidence_ref_from_rule_evidence,
    evidence_refs_from_rule_match,
    pack_is_traceable,
)
from codestrata.application.traceability.selection import (
    select_primary_evidence_id,
    synthesize_finding_traceability,
)

__all__ = [
    "TRACEABLE_PACK_PREFIXES",
    "attach_recommendation_traceability",
    "evidence_ref_from_rule_evidence",
    "evidence_refs_from_rule_match",
    "merge_finding_traceability",
    "merge_recommendation_traceability",
    "pack_is_traceable",
    "select_primary_evidence_id",
    "select_primary_finding_id",
    "synthesize_finding_traceability",
    "synthesize_recommendation_traceability",
]
