"""Deterministic Finding Confidence derivation (Slice 5.3).

Weakest-support principle: Finding Confidence never exceeds the weakest
materially required component among Rule Confidence, Match Evidence Confidence,
and Evidence Confidence. Severity is never an input.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.domain.findings.finding_confidence import (
    FindingConfidence,
    FindingConfidenceBasis,
    FindingConfidenceComponents,
    FindingConfidenceDerivationStatus,
    FindingConfidenceLevel,
    finding_confidence_level_rank,
    min_finding_confidence_level,
)
from codestrata.domain.rules.enums import MatchEvidenceConfidence
from codestrata.domain.rules.rule_confidence import RuleConfidence, RuleConfidenceLevel
from codestrata.domain.traceability import EvidenceCompleteness, EvidenceRef
from codestrata.domain.traceability.evidence_confidence import (
    EvidenceConfidence,
    EvidenceConfidenceLevel,
)
from codestrata.domain.traceability.enums import EvidenceKind, EvidenceProductionMode


# MatchEvidenceConfidence → FindingConfidenceLevel support scale.
_MATCH_SUPPORT: dict[MatchEvidenceConfidence, FindingConfidenceLevel] = {
    MatchEvidenceConfidence.CERTAIN: FindingConfidenceLevel.HIGH,
    MatchEvidenceConfidence.HIGH: FindingConfidenceLevel.HIGH,
    MatchEvidenceConfidence.MEDIUM: FindingConfidenceLevel.MODERATE,
    MatchEvidenceConfidence.LOW: FindingConfidenceLevel.LIMITED,
}

_RULE_SUPPORT: dict[RuleConfidenceLevel, FindingConfidenceLevel] = {
    RuleConfidenceLevel.HIGH: FindingConfidenceLevel.HIGH,
    RuleConfidenceLevel.MODERATE: FindingConfidenceLevel.MODERATE,
    RuleConfidenceLevel.LIMITED: FindingConfidenceLevel.LIMITED,
    RuleConfidenceLevel.UNAVAILABLE: FindingConfidenceLevel.UNAVAILABLE,
}

_EVIDENCE_SUPPORT: dict[EvidenceConfidenceLevel, FindingConfidenceLevel] = {
    EvidenceConfidenceLevel.HIGH: FindingConfidenceLevel.HIGH,
    EvidenceConfidenceLevel.MODERATE: FindingConfidenceLevel.MODERATE,
    EvidenceConfidenceLevel.LIMITED: FindingConfidenceLevel.LIMITED,
    EvidenceConfidenceLevel.UNAVAILABLE: FindingConfidenceLevel.UNAVAILABLE,
}


def match_evidence_confidence_support(
    match_confidence: MatchEvidenceConfidence | str | None,
) -> FindingConfidenceLevel | None:
    """Map Match Evidence Confidence onto the Finding Confidence scale."""

    if match_confidence is None:
        return None
    if isinstance(match_confidence, MatchEvidenceConfidence):
        return _MATCH_SUPPORT[match_confidence]
    text = str(match_confidence).strip().lower()
    try:
        return _MATCH_SUPPORT[MatchEvidenceConfidence(text)]
    except ValueError:
        return None


def derive_finding_confidence(
    *,
    rule_confidence: RuleConfidence | None,
    match_evidence_confidence: MatchEvidenceConfidence | str | None,
    evidence_refs: Sequence[EvidenceRef] = (),
    primary_evidence_id: str | None = None,
    synthesized_from_evidence_ids: Sequence[str] = (),
    evidence_completeness: EvidenceCompleteness | str | None = None,
    limitations: Sequence[str] = (),
    shared_rule_platform: bool = False,
) -> FindingConfidence:
    """Derive Finding Confidence from the deterministic support chain."""

    completeness = _normalize_completeness(evidence_completeness)
    refs = tuple(evidence_refs)
    limit_set = {str(item).strip() for item in limitations if str(item).strip()}
    deferred = "evidence_ref_mapping_deferred_for_pack" in limit_set or (
        "finding_evidence_mapping_deferred_for_pack" in limit_set
    )

    material_refs = _material_evidence_refs(
        refs,
        primary_evidence_id=primary_evidence_id,
        synthesized_from_evidence_ids=tuple(synthesized_from_evidence_ids),
    )
    primary_conf = _resolve_primary_confidence(refs, primary_evidence_id)
    weakest_conf = _weakest_material_confidence(material_refs)

    components = FindingConfidenceComponents(
        rule_confidence_level=(
            rule_confidence.level.value if rule_confidence is not None else None
        ),
        match_evidence_confidence=_match_value(match_evidence_confidence),
        primary_evidence_confidence=(
            primary_conf.level.value if primary_conf is not None else None
        ),
        weakest_evidence_confidence=(
            weakest_conf.level.value if weakest_conf is not None else None
        ),
        evidence_count=len(refs),
        evidence_completeness=(
            completeness.value if completeness is not None else None
        ),
        traceability_complete=False,
    )

    # Legacy / Phase-1 / non-shared findings without rule confidence.
    if rule_confidence is None and not shared_rule_platform:
        return FindingConfidence.unavailable(
            basis=(FindingConfidenceBasis.LEGACY_FINDING,),
            limitations=(
                "Legacy finding lacks Shared Rule Confidence and Evidence Confidence.",
                *sorted(limit_set),
            ),
            component_summary=components,
        )

    if rule_confidence is None or (
        rule_confidence.level is RuleConfidenceLevel.UNAVAILABLE
    ):
        return FindingConfidence.unavailable(
            basis=(
                FindingConfidenceBasis.LEGACY_FINDING,
                FindingConfidenceBasis.LIMITED_RULE_CONFIDENCE,
            ),
            limitations=(
                "Rule Confidence is unavailable for this finding.",
                *sorted(limit_set),
            ),
            component_summary=components,
        )

    if deferred or completeness is EvidenceCompleteness.LEGACY:
        return FindingConfidence.unavailable(
            basis=(
                FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE,
                FindingConfidenceBasis.LEGACY_FINDING
                if completeness is EvidenceCompleteness.LEGACY
                else FindingConfidenceBasis.PARTIAL_EVIDENCE,
            ),
            limitations=(
                "finding_evidence_mapping_deferred_for_pack"
                if deferred
                else "Legacy evidence completeness prevents Finding Confidence derivation.",
                *sorted(limit_set),
            ),
            component_summary=components,
        )

    if not refs or completeness is EvidenceCompleteness.UNAVAILABLE:
        return FindingConfidence(
            level=FindingConfidenceLevel.UNAVAILABLE,
            basis=(FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE,),
            limitations=(
                "Finding has no resolvable EvidenceRefs.",
                *sorted(limit_set),
            ),
            derivation_status=FindingConfidenceDerivationStatus.UNAVAILABLE,
            component_summary=components,
        )

    caps: list[FindingConfidenceLevel] = []
    bases: list[FindingConfidenceBasis] = []
    out_limits: list[str] = list(sorted(limit_set))

    rule_level = _RULE_SUPPORT[rule_confidence.level]
    caps.append(rule_level)
    bases.append(_rule_basis(rule_confidence.level))
    out_limits.extend(rule_confidence.limitations)

    match_level = match_evidence_confidence_support(match_evidence_confidence)
    if match_level is None:
        caps.append(FindingConfidenceLevel.LIMITED)
        bases.append(FindingConfidenceBasis.LIMITED_MATCH_CONFIDENCE)
        out_limits.append("Match Evidence Confidence is missing or unrecognized.")
    else:
        caps.append(match_level)
        if match_level is FindingConfidenceLevel.HIGH:
            bases.append(FindingConfidenceBasis.EXACT_MATCH)
        elif match_level is FindingConfidenceLevel.LIMITED:
            bases.append(FindingConfidenceBasis.LIMITED_MATCH_CONFIDENCE)

    if primary_conf is None:
        caps.append(FindingConfidenceLevel.LIMITED)
        bases.append(FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE)
        out_limits.append("primary_evidence_id does not resolve to Evidence Confidence.")
    else:
        caps.append(_EVIDENCE_SUPPORT[primary_conf.level])
        bases.extend(_evidence_bases(primary_conf))
        out_limits.extend(primary_conf.limitations)

    if weakest_conf is not None:
        caps.append(_EVIDENCE_SUPPORT[weakest_conf.level])
        if weakest_conf.level is EvidenceConfidenceLevel.LIMITED:
            bases.append(FindingConfidenceBasis.PARTIAL_EVIDENCE)
        if weakest_conf.level is EvidenceConfidenceLevel.UNAVAILABLE:
            bases.append(FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE)
        out_limits.extend(weakest_conf.limitations)

    levels_present = {
        item.evidence_confidence.level
        for item in material_refs
        if item.evidence_confidence is not None
    }
    if len(levels_present) > 1:
        bases.append(FindingConfidenceBasis.CONFLICTING_EVIDENCE)
        out_limits.append(
            "Material EvidenceRefs report more than one Evidence Confidence level."
        )

    if any(
        item.production_mode is EvidenceProductionMode.SYNTHESIZED
        or item.kind is EvidenceKind.SYNTHETIC
        or item.parent_evidence_ids
        for item in material_refs
    ):
        bases.append(FindingConfidenceBasis.SYNTHESIZED_EVIDENCE)

    if len(material_refs) > 1 and len(levels_present) <= 1:
        bases.append(FindingConfidenceBasis.MULTIPLE_CONSISTENT_EVIDENCE)

    if completeness is EvidenceCompleteness.PARTIAL:
        caps.append(FindingConfidenceLevel.LIMITED)
        bases.append(FindingConfidenceBasis.PARTIAL_EVIDENCE)
        out_limits.append("Evidence completeness is partial.")
    elif completeness is EvidenceCompleteness.TRUNCATED:
        caps.append(FindingConfidenceLevel.LIMITED)
        bases.append(FindingConfidenceBasis.PARTIAL_EVIDENCE)
        out_limits.append("Evidence completeness is truncated.")

    primary_ok = primary_evidence_id is None or any(
        item.evidence_id == primary_evidence_id for item in refs
    )
    traceability_complete = bool(
        rule_confidence.level is not RuleConfidenceLevel.UNAVAILABLE
        and refs
        and primary_ok
        and completeness is EvidenceCompleteness.COMPLETE
        and not deferred
        and match_level is not None
        and primary_conf is not None
        and weakest_conf is not None
        and weakest_conf.level is not EvidenceConfidenceLevel.UNAVAILABLE
    )
    components = components.model_copy(
        update={"traceability_complete": traceability_complete}
    )

    if not traceability_complete:
        caps.append(FindingConfidenceLevel.LIMITED)
        out_limits.append("Traceability is incomplete for High Finding Confidence.")

    level = min_finding_confidence_level(tuple(caps))
    if level is FindingConfidenceLevel.HIGH and not traceability_complete:
        level = FindingConfidenceLevel.MODERATE
    if (
        level is FindingConfidenceLevel.HIGH
        and FindingConfidenceBasis.PARTIAL_EVIDENCE in bases
    ):
        level = FindingConfidenceLevel.LIMITED
    if primary_conf is not None and primary_conf.level is EvidenceConfidenceLevel.HIGH:
        bases.append(FindingConfidenceBasis.STRONG_PRIMARY_EVIDENCE)

    status = FindingConfidenceDerivationStatus.DERIVED
    if level is FindingConfidenceLevel.UNAVAILABLE:
        status = FindingConfidenceDerivationStatus.UNAVAILABLE
    elif not traceability_complete or FindingConfidenceBasis.PARTIAL_EVIDENCE in bases:
        status = FindingConfidenceDerivationStatus.PROVISIONAL

    # Drop HIGH-incompatible bases when capped below High is already applied.
    cleaned_bases = tuple(sorted(set(bases), key=lambda item: item.value))
    if level is FindingConfidenceLevel.HIGH and (
        FindingConfidenceBasis.PARTIAL_EVIDENCE in cleaned_bases
        or FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE in cleaned_bases
        or not traceability_complete
    ):
        level = FindingConfidenceLevel.LIMITED
        status = FindingConfidenceDerivationStatus.PROVISIONAL

    return FindingConfidence(
        level=level,
        basis=cleaned_bases or (FindingConfidenceBasis.PARTIAL_EVIDENCE,),
        limitations=tuple(sorted(set(out_limits))),
        derivation_status=status,
        component_summary=components,
    )


def derive_finding_confidence_from_finding_inputs(
    *,
    metadata: Mapping[str, object],
    evidence_refs: Sequence[EvidenceRef],
    primary_evidence_id: str | None,
    synthesized_from_evidence_ids: Sequence[str],
    evidence_completeness: EvidenceCompleteness | str,
    limitations: Sequence[str],
    rule_confidence: RuleConfidence | None = None,
) -> FindingConfidence:
    """Recompute Finding Confidence after merge using Finding fields/metadata."""

    resolved_rule = rule_confidence
    if resolved_rule is None:
        raw = metadata.get("rule_confidence")
        if isinstance(raw, RuleConfidence):
            resolved_rule = raw
        elif isinstance(raw, Mapping):
            resolved_rule = RuleConfidence.model_validate(dict(raw))
    shared = str(metadata.get("shared_rule_platform", "")).lower() in {"true", "1", "yes"}
    return derive_finding_confidence(
        rule_confidence=resolved_rule,
        match_evidence_confidence=(
            str(metadata.get("confidence")) if metadata.get("confidence") is not None else None
        ),
        evidence_refs=evidence_refs,
        primary_evidence_id=primary_evidence_id,
        synthesized_from_evidence_ids=synthesized_from_evidence_ids,
        evidence_completeness=evidence_completeness,
        limitations=limitations,
        shared_rule_platform=shared,
    )


def _material_evidence_refs(
    refs: Sequence[EvidenceRef],
    *,
    primary_evidence_id: str | None,
    synthesized_from_evidence_ids: tuple[str, ...],
) -> tuple[EvidenceRef, ...]:
    if not refs:
        return ()
    by_id = {item.evidence_id: item for item in refs}
    material_ids: set[str] = set()
    if primary_evidence_id and primary_evidence_id in by_id:
        material_ids.add(primary_evidence_id)
    for item_id in synthesized_from_evidence_ids:
        if item_id in by_id:
            material_ids.add(item_id)
    # All RuleEvidence-backed refs on the finding are material when present.
    # Prefer explicit primary/synthesized sets when non-empty; otherwise all refs.
    if not material_ids:
        material_ids = set(by_id)
    # Include resolved parents for synthesized material refs.
    for item_id in list(material_ids):
        ref = by_id[item_id]
        for parent_id in ref.parent_evidence_ids:
            if parent_id in by_id:
                material_ids.add(parent_id)
    return tuple(by_id[item_id] for item_id in sorted(material_ids))


def _resolve_primary_confidence(
    refs: Sequence[EvidenceRef],
    primary_evidence_id: str | None,
) -> EvidenceConfidence | None:
    if not refs:
        return None
    if primary_evidence_id:
        for item in refs:
            if item.evidence_id == primary_evidence_id:
                return item.evidence_confidence
        return None
    return refs[0].evidence_confidence


def _weakest_material_confidence(
    refs: Sequence[EvidenceRef],
) -> EvidenceConfidence | None:
    if not refs:
        return None
    ranked = sorted(
        refs,
        key=lambda item: finding_confidence_level_rank(
            _EVIDENCE_SUPPORT[item.evidence_confidence.level]
        ),
    )
    return ranked[0].evidence_confidence


def _normalize_completeness(
    value: EvidenceCompleteness | str | None,
) -> EvidenceCompleteness | None:
    if value is None:
        return None
    if isinstance(value, EvidenceCompleteness):
        return value
    try:
        return EvidenceCompleteness(str(value).strip().lower())
    except ValueError:
        return None


def _match_value(value: MatchEvidenceConfidence | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, MatchEvidenceConfidence):
        return value.value
    text = str(value).strip()
    return text or None


def _rule_basis(level: RuleConfidenceLevel) -> FindingConfidenceBasis:
    if level is RuleConfidenceLevel.HIGH:
        return FindingConfidenceBasis.HIGH_RULE_CONFIDENCE
    if level is RuleConfidenceLevel.MODERATE:
        return FindingConfidenceBasis.MODERATE_RULE_CONFIDENCE
    return FindingConfidenceBasis.LIMITED_RULE_CONFIDENCE


def _evidence_bases(confidence: EvidenceConfidence) -> list[FindingConfidenceBasis]:
    bases: list[FindingConfidenceBasis] = []
    values = {item.value for item in confidence.basis}
    if "explicit_configuration" in values:
        bases.append(FindingConfidenceBasis.EXPLICIT_CONFIGURATION)
    if "deterministic_metric" in values:
        bases.append(FindingConfidenceBasis.DETERMINISTIC_MEASUREMENT)
    if confidence.level is EvidenceConfidenceLevel.HIGH:
        bases.append(FindingConfidenceBasis.STRONG_PRIMARY_EVIDENCE)
    if "partial_parse" in values or confidence.level is EvidenceConfidenceLevel.LIMITED:
        bases.append(FindingConfidenceBasis.PARTIAL_EVIDENCE)
    if any("graph" in item.value or "structural" in item.value for item in confidence.basis):
        bases.append(FindingConfidenceBasis.GRAPH_RELATIONSHIP)
    return bases
