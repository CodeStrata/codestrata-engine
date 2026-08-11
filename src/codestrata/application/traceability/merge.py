"""Merge Finding traceability without changing finding identity."""

from __future__ import annotations

from codestrata.application.findings.finding_confidence import (
    derive_finding_confidence_from_finding_inputs,
)
from codestrata.application.traceability.selection import synthesize_finding_traceability
from codestrata.domain.findings.models import Finding
from codestrata.domain.rules.rule_confidence import RuleConfidence
from codestrata.domain.traceability import TraceabilityValidationError, dedupe_evidence_refs


def merge_finding_traceability(preferred: Finding, other: Finding) -> Finding:
    """Union EvidenceRefs from two findings that share identity semantics.

    Does not alter ``preferred.id``. Raises when contradictory EvidenceRefs
    share an evidence_id (via ``dedupe_evidence_refs``) or when Rule Confidence
    levels contradict.
    """

    _assert_compatible_rule_confidence(preferred, other)
    combined = dedupe_evidence_refs((*preferred.evidence_refs, *other.evidence_refs))
    ordered, primary, synthesized, completeness, limits = synthesize_finding_traceability(
        combined,
        limitations=(*preferred.limitations, *other.limitations),
    )
    metadata = dict(preferred.metadata)
    if "rule_confidence" not in metadata and "rule_confidence" in other.metadata:
        metadata["rule_confidence"] = other.metadata["rule_confidence"]
    if "confidence" not in metadata and "confidence" in other.metadata:
        metadata["confidence"] = other.metadata["confidence"]
    finding_confidence = derive_finding_confidence_from_finding_inputs(
        metadata=metadata,
        evidence_refs=ordered,
        primary_evidence_id=primary,
        synthesized_from_evidence_ids=synthesized,
        evidence_completeness=completeness,
        limitations=limits,
    )
    return preferred.model_copy(
        update={
            "metadata": metadata,
            "evidence_refs": ordered,
            "primary_evidence_id": primary,
            "synthesized_from_evidence_ids": synthesized,
            "evidence_completeness": completeness,
            "limitations": limits,
            "finding_confidence": finding_confidence,
        }
    )


def _assert_compatible_rule_confidence(preferred: Finding, other: Finding) -> None:
    left = preferred.metadata.get("rule_confidence_level")
    right = other.metadata.get("rule_confidence_level")
    if left and right and str(left) != str(right):
        raise TraceabilityValidationError(
            "contradictory Rule Confidence levels for finding_id="
            f"{preferred.id!r}: {left!r} vs {right!r}"
        )
    left_block = preferred.metadata.get("rule_confidence")
    right_block = other.metadata.get("rule_confidence")
    if isinstance(left_block, dict) and isinstance(right_block, dict):
        left_model = RuleConfidence.model_validate(left_block)
        right_model = RuleConfidence.model_validate(right_block)
        if left_model.level != right_model.level:
            raise TraceabilityValidationError(
                "contradictory Rule Confidence for finding_id="
                f"{preferred.id!r}: {left_model.level.value} vs {right_model.level.value}"
            )
