"""Deterministic Assessment-Head Confidence derivation (Slice 5.4).

Weakest-support principle: head confidence never exceeds the weakest material
Finding Confidence and is further capped by coverage/support status.
Zero findings never imply High confidence or repository health.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from codestrata.domain.assessment_heads.assessment_head_confidence import (
    AssessmentHeadConfidence,
    AssessmentHeadConfidenceBasis,
    AssessmentHeadConfidenceComponents,
    AssessmentHeadConfidenceDerivationStatus,
    AssessmentHeadConfidenceLevel,
    assessment_head_confidence_level_rank,
    min_assessment_head_confidence_level,
)
from codestrata.domain.findings.finding_confidence import FindingConfidenceLevel


_FINDING_LEVELS = {
    "high": FindingConfidenceLevel.HIGH,
    "moderate": FindingConfidenceLevel.MODERATE,
    "limited": FindingConfidenceLevel.LIMITED,
    "unavailable": FindingConfidenceLevel.UNAVAILABLE,
}

_FINDING_TO_HEAD = {
    FindingConfidenceLevel.HIGH: AssessmentHeadConfidenceLevel.HIGH,
    FindingConfidenceLevel.MODERATE: AssessmentHeadConfidenceLevel.MODERATE,
    FindingConfidenceLevel.LIMITED: AssessmentHeadConfidenceLevel.LIMITED,
    FindingConfidenceLevel.UNAVAILABLE: AssessmentHeadConfidenceLevel.UNAVAILABLE,
}


def derive_assessment_head_confidence(
    *,
    head_id: str,
    assessment_status: str | None,
    finding_confidence_levels: Sequence[str] = (),
    evidence_completeness_values: Sequence[str] = (),
    limitations: Sequence[str] = (),
    activated: bool | None = None,
    coverage_state: str | None = None,
    pack_assessment_status: str | None = None,
    synthesized: bool = False,
    contributing_head_levels: Sequence[str] = (),
    inventory_confidence: str | None = None,
    assessment_coverage: Any | None = None,
) -> AssessmentHeadConfidence:
    """Derive Assessment-Head Confidence for one head in one repository run."""

    status = (assessment_status or "").strip().lower()
    pack_status = (pack_assessment_status or "").strip().lower()
    # Slice 5.6 — prefer canonical AssessmentCoverage over free-form guesses.
    coverage_from_model = None
    if assessment_coverage is not None:
        from codestrata.domain.assessment_heads.assessment_coverage import (
            AssessmentCoverage,
            coverage_status_to_confidence_coverage_state,
        )

        if isinstance(assessment_coverage, AssessmentCoverage):
            coverage_from_model = coverage_status_to_confidence_coverage_state(
                assessment_coverage.status
            )
        elif isinstance(assessment_coverage, Mapping):
            raw_status = str(assessment_coverage.get("status") or "").strip().lower()
            if raw_status:
                from codestrata.domain.assessment_heads.assessment_coverage import (
                    CoverageStatus,
                    coverage_status_to_confidence_coverage_state,
                )

                try:
                    coverage_from_model = coverage_status_to_confidence_coverage_state(
                        CoverageStatus(raw_status)
                    )
                except ValueError:
                    coverage_from_model = raw_status
    coverage = _normalize_coverage(
        coverage_state=coverage_from_model or coverage_state,
        assessment_status=status,
        pack_assessment_status=pack_status,
        evidence_completeness_values=evidence_completeness_values,
    )
    levels = _normalize_finding_levels(finding_confidence_levels)
    limit_set = {str(item).strip() for item in limitations if str(item).strip()}
    counts = _count_levels(levels)
    weakest = min(levels, key=lambda item: assessment_head_confidence_level_rank(
        _FINDING_TO_HEAD[item]
    )) if levels else None

    components = AssessmentHeadConfidenceComponents(
        finding_count=len(levels),
        high_finding_count=counts[FindingConfidenceLevel.HIGH],
        moderate_finding_count=counts[FindingConfidenceLevel.MODERATE],
        limited_finding_count=counts[FindingConfidenceLevel.LIMITED],
        unavailable_finding_count=counts[FindingConfidenceLevel.UNAVAILABLE],
        weakest_material_finding_confidence=(
            weakest.value if weakest is not None else None
        ),
        coverage_state=coverage,
        evidence_completeness=_aggregate_completeness(evidence_completeness_values),
        assessment_status=status or None,
        activated=bool(activated) if activated is not None else status not in {
            "not_enabled",
            "not_available",
            "",
        },
        limitations_count=len(limit_set),
    )

    # Disabled / unavailable heads
    if status == "not_enabled" or pack_status == "disabled":
        return AssessmentHeadConfidence.unavailable(
            basis=(AssessmentHeadConfidenceBasis.DISABLED_HEAD,),
            limitations=(
                "This assessment head was not enabled.",
                *sorted(limit_set),
            ),
            component_summary=components,
        )
    if status in {"not_available"} or pack_status in {
        "failed",
        "not_requested",
        "not_applicable",
    }:
        return AssessmentHeadConfidence.unavailable(
            basis=(
                AssessmentHeadConfidenceBasis.UNAVAILABLE_HEAD,
                AssessmentHeadConfidenceBasis.UNSUPPORTED_CAPABILITY,
            ),
            limitations=(
                "This assessment head is unavailable for the repository run.",
                *sorted(limit_set),
            ),
            component_summary=components,
        )

    # Modernization / synthesized head bounded by contributors
    if synthesized or head_id == "modernization_assessment":
        return _synthesize_head_confidence(
            contributing_head_levels=contributing_head_levels,
            components=components,
            limitations=limit_set,
            coverage=coverage,
            status=status,
        )

    # Technology inventory: factual inventory path when no findings
    if head_id == "technology_inventory" and not levels:
        return _inventory_confidence(
            inventory_confidence=inventory_confidence,
            coverage=coverage,
            status=status,
            components=components,
            limitations=limit_set,
        )

    bases: list[AssessmentHeadConfidenceBasis] = []
    caps: list[AssessmentHeadConfidenceLevel] = []
    out_limits = list(sorted(limit_set))

    if coverage == "complete":
        bases.append(AssessmentHeadConfidenceBasis.COMPLETE_ASSESSMENT_COVERAGE)
    elif coverage == "partial":
        bases.append(AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE)
        caps.append(AssessmentHeadConfidenceLevel.MODERATE)
    elif coverage == "insufficient":
        bases.append(AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE)
        caps.append(AssessmentHeadConfidenceLevel.LIMITED)
    else:
        bases.append(AssessmentHeadConfidenceBasis.UNAVAILABLE_HEAD)
        caps.append(AssessmentHeadConfidenceLevel.UNAVAILABLE)

    if status == "legacy_assessment" or coverage == "legacy":
        bases.append(AssessmentHeadConfidenceBasis.LEGACY_FINDINGS)
        caps.append(AssessmentHeadConfidenceLevel.UNAVAILABLE)

    if pack_status == "insufficient_evidence":
        bases.append(AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE)
        caps.append(AssessmentHeadConfidenceLevel.LIMITED)

    if status == "partially_assessed":
        caps.append(AssessmentHeadConfidenceLevel.MODERATE)

    # Zero-finding policy
    if not levels:
        if coverage == "insufficient" or pack_status == "insufficient_evidence":
            bases.append(AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE)
            return AssessmentHeadConfidence.unavailable(
                basis=tuple(sorted(set(bases), key=lambda item: item.value))
                or (AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE,),
                limitations=tuple(
                    sorted(
                        {
                            *out_limits,
                            "Zero findings with insufficient evidence cannot "
                            "support Assessment-Head Confidence.",
                        }
                    )
                ),
                component_summary=components,
            )
        if coverage == "complete" and status == "assessed":
            bases.append(AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_COMPLETE_COVERAGE)
            level = AssessmentHeadConfidenceLevel.MODERATE
            caps.append(level)
            out_limits.append(
                "No findings were produced within the assessed scope; "
                "this is not a health certification."
            )
            level = min_assessment_head_confidence_level(tuple(caps) or (level,))
            return AssessmentHeadConfidence(
                level=level,
                basis=tuple(sorted(set(bases), key=lambda item: item.value)),
                limitations=tuple(sorted(set(out_limits))),
                derivation_status=AssessmentHeadConfidenceDerivationStatus.DERIVED,
                component_summary=components,
            )
        if coverage == "partial" or status == "partially_assessed":
            bases.append(AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_PARTIAL_COVERAGE)
            return AssessmentHeadConfidence(
                level=AssessmentHeadConfidenceLevel.LIMITED,
                basis=tuple(sorted(set(bases), key=lambda item: item.value)),
                limitations=tuple(
                    sorted(
                        {
                            *out_limits,
                            "Zero findings with partial coverage cannot support "
                            "High or Moderate Assessment-Head Confidence.",
                        }
                    )
                ),
                derivation_status=AssessmentHeadConfidenceDerivationStatus.PROVISIONAL,
                component_summary=components,
            )
        bases.append(AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE)
        return AssessmentHeadConfidence.unavailable(
            basis=tuple(sorted(set(bases), key=lambda item: item.value))
            or (AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE,),
            limitations=tuple(
                sorted(
                    {
                        *out_limits,
                        "Zero findings without sufficient assessed coverage.",
                    }
                )
            ),
            component_summary=components,
        )

    # Findings present — weakest Finding Confidence caps the head.
    finding_caps = tuple(_FINDING_TO_HEAD[item] for item in levels)
    caps.extend(finding_caps)
    unique_finding_levels = set(levels)
    if unique_finding_levels == {FindingConfidenceLevel.HIGH}:
        bases.append(AssessmentHeadConfidenceBasis.ALL_MATERIAL_FINDINGS_HIGH)
    elif FindingConfidenceLevel.LIMITED in unique_finding_levels:
        bases.append(AssessmentHeadConfidenceBasis.LIMITED_FINDING_CONFIDENCE)
    elif len(unique_finding_levels) > 1:
        bases.append(AssessmentHeadConfidenceBasis.MIXED_FINDING_CONFIDENCE)
    if FindingConfidenceLevel.UNAVAILABLE in unique_finding_levels:
        bases.append(AssessmentHeadConfidenceBasis.LEGACY_FINDINGS)
        caps.append(AssessmentHeadConfidenceLevel.LIMITED)
        out_limits.append(
            "One or more material findings have Unavailable Finding Confidence."
        )
        # Deferred EvidenceRef packs often land here — stay honest.
        if any(
            "deferred" in item.lower() or "legacy" in item.lower()
            for item in limit_set
        ):
            caps.append(AssessmentHeadConfidenceLevel.UNAVAILABLE)

    level = min_assessment_head_confidence_level(tuple(caps))
    if (
        level is AssessmentHeadConfidenceLevel.HIGH
        and AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE in bases
    ):
        level = AssessmentHeadConfidenceLevel.MODERATE
    if level is AssessmentHeadConfidenceLevel.HIGH and (
        AssessmentHeadConfidenceBasis.LEGACY_FINDINGS in bases
        or FindingConfidenceLevel.UNAVAILABLE in unique_finding_levels
    ):
        level = AssessmentHeadConfidenceLevel.LIMITED

    status_flag = AssessmentHeadConfidenceDerivationStatus.DERIVED
    if level in {
        AssessmentHeadConfidenceLevel.LIMITED,
        AssessmentHeadConfidenceLevel.UNAVAILABLE,
    } or coverage != "complete":
        status_flag = (
            AssessmentHeadConfidenceDerivationStatus.UNAVAILABLE
            if level is AssessmentHeadConfidenceLevel.UNAVAILABLE
            else AssessmentHeadConfidenceDerivationStatus.PROVISIONAL
        )

    return AssessmentHeadConfidence(
        level=level,
        basis=tuple(sorted(set(bases), key=lambda item: item.value)),
        limitations=tuple(sorted(set(out_limits))),
        derivation_status=status_flag,
        component_summary=components,
    )


def confidence_label_from_head_confidence(
    confidence: AssessmentHeadConfidence,
) -> tuple[str, str]:
    """Map canonical head confidence to legacy confidence / confidence_label fields."""

    level = confidence.level.value
    label = {
        "high": "High confidence",
        "moderate": "Moderate confidence",
        "limited": "Limited confidence",
        "unavailable": "Confidence unavailable",
    }.get(level, "Confidence unavailable")
    return level, label


def apply_canonical_head_confidence(
    section: Any,
    *,
    pack_assessment_status: str | None = None,
    coverage_state: str | None = None,
    inventory_confidence: str | None = None,
    contributing_head_levels: Sequence[str] = (),
    assessment_coverage: Any | None = None,
) -> Any:
    """Recompute Assessment-Head Confidence on an AssessmentHeadSectionView."""

    from codestrata.domain.assessment_heads import assessment_head_confidence_to_json
    from codestrata.domain.assessment_heads.assessment_coverage import (
        assessment_coverage_to_json,
    )

    coverage_payload = assessment_coverage
    if coverage_payload is None:
        coverage_payload = getattr(section, "assessment_coverage", None)

    findings = tuple(getattr(section, "findings", ()) or ())
    head_confidence = derive_assessment_head_confidence(
        head_id=str(getattr(section, "head", "")),
        assessment_status=str(getattr(section, "status", "") or ""),
        finding_confidence_levels=tuple(
            getattr(item, "finding_confidence_level", None) or "unavailable"
            for item in findings
        ),
        evidence_completeness_values=tuple(
            getattr(item, "evidence_completeness", "") or ""
            for item in findings
        ),
        limitations=tuple(getattr(section, "limitations", ()) or ()),
        activated=bool(getattr(section, "pack_content_available", False)),
        coverage_state=coverage_state,
        pack_assessment_status=pack_assessment_status,
        synthesized=str(getattr(section, "head", "")) == "modernization_assessment",
        contributing_head_levels=contributing_head_levels,
        inventory_confidence=inventory_confidence,
        assessment_coverage=coverage_payload,
    )
    confidence, confidence_label = confidence_label_from_head_confidence(head_confidence)
    updates: dict[str, Any] = {
        "confidence": confidence,
        "confidence_label": confidence_label,
        "assessment_head_confidence": assessment_head_confidence_to_json(
            head_confidence
        ),
    }
    if coverage_payload is not None and not isinstance(coverage_payload, dict):
        updates["assessment_coverage"] = assessment_coverage_to_json(coverage_payload)
    elif isinstance(coverage_payload, dict):
        updates["assessment_coverage"] = coverage_payload
    return section.model_copy(update=updates)


def _synthesize_head_confidence(
    *,
    contributing_head_levels: Sequence[str],
    components: AssessmentHeadConfidenceComponents,
    limitations: set[str],
    coverage: str,
    status: str,
) -> AssessmentHeadConfidence:
    bases = [AssessmentHeadConfidenceBasis.SYNTHESIZED_HEAD]
    out_limits = list(sorted(limitations))
    out_limits.append(
        "Modernization Assessment confidence cannot exceed contributing heads."
    )
    contributors = [
        AssessmentHeadConfidenceLevel(item.strip().lower())
        for item in contributing_head_levels
        if str(item or "").strip().lower()
        in {level.value for level in AssessmentHeadConfidenceLevel}
    ]
    if not contributors:
        return AssessmentHeadConfidence.unavailable(
            basis=(
                AssessmentHeadConfidenceBasis.SYNTHESIZED_HEAD,
                AssessmentHeadConfidenceBasis.UNAVAILABLE_HEAD,
            ),
            limitations=tuple(
                sorted({*out_limits, "No contributing assessment heads were available."})
            ),
            component_summary=components,
        )
    level = min_assessment_head_confidence_level(tuple(contributors))
    if coverage == "partial" or status == "partially_assessed":
        bases.append(AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE)
        if assessment_head_confidence_level_rank(level) > assessment_head_confidence_level_rank(
            AssessmentHeadConfidenceLevel.MODERATE
        ):
            level = AssessmentHeadConfidenceLevel.MODERATE
    if coverage == "legacy":
        bases.append(AssessmentHeadConfidenceBasis.LEGACY_FINDINGS)
        level = AssessmentHeadConfidenceLevel.UNAVAILABLE
    return AssessmentHeadConfidence(
        level=level,
        basis=tuple(sorted(set(bases), key=lambda item: item.value)),
        limitations=tuple(sorted(set(out_limits))),
        derivation_status=(
            AssessmentHeadConfidenceDerivationStatus.UNAVAILABLE
            if level is AssessmentHeadConfidenceLevel.UNAVAILABLE
            else AssessmentHeadConfidenceDerivationStatus.DERIVED
        ),
        component_summary=components,
    )


def _inventory_confidence(
    *,
    inventory_confidence: str | None,
    coverage: str,
    status: str,
    components: AssessmentHeadConfidenceComponents,
    limitations: set[str],
) -> AssessmentHeadConfidence:
    bases: list[AssessmentHeadConfidenceBasis] = []
    out_limits = list(sorted(limitations))
    token = (inventory_confidence or "").strip().lower()
    if status in {"not_available", "legacy_assessment"} or coverage in {
        "unavailable",
        "legacy",
    }:
        return AssessmentHeadConfidence.unavailable(
            basis=(
                AssessmentHeadConfidenceBasis.UNAVAILABLE_HEAD,
                AssessmentHeadConfidenceBasis.LEGACY_FINDINGS
                if coverage == "legacy" or status == "legacy_assessment"
                else AssessmentHeadConfidenceBasis.UNSUPPORTED_CAPABILITY,
            ),
            limitations=tuple(
                sorted({*out_limits, "Technology inventory evidence is unavailable."})
            ),
            component_summary=components,
        )
    if coverage == "partial" or status == "partially_assessed" or token in {
        "limited",
        "low",
    }:
        bases.append(AssessmentHeadConfidenceBasis.PARTIAL_ASSESSMENT_COVERAGE)
        bases.append(AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_PARTIAL_COVERAGE)
        return AssessmentHeadConfidence(
            level=AssessmentHeadConfidenceLevel.LIMITED,
            basis=tuple(sorted(set(bases), key=lambda item: item.value)),
            limitations=tuple(
                sorted(
                    {
                        *out_limits,
                        "Technology inventory coverage is partial.",
                    }
                )
            ),
            derivation_status=AssessmentHeadConfidenceDerivationStatus.PROVISIONAL,
            component_summary=components,
        )
    if token in {"high", "moderate"} or coverage == "complete":
        bases.append(AssessmentHeadConfidenceBasis.COMPLETE_ASSESSMENT_COVERAGE)
        bases.append(AssessmentHeadConfidenceBasis.NO_FINDINGS_WITH_COMPLETE_COVERAGE)
        # Inventory is factual; scoped Moderate even when detector confidence is high.
        level = AssessmentHeadConfidenceLevel.MODERATE
        if token in {"limited", "unavailable", "low"}:
            level = AssessmentHeadConfidenceLevel.LIMITED
        out_limits.append(
            "Technology Inventory confidence reflects inventory evidence quality, "
            "not repository health."
        )
        return AssessmentHeadConfidence(
            level=level,
            basis=tuple(sorted(set(bases), key=lambda item: item.value)),
            limitations=tuple(sorted(set(out_limits))),
            derivation_status=AssessmentHeadConfidenceDerivationStatus.DERIVED,
            component_summary=components,
        )
    return AssessmentHeadConfidence.unavailable(
        basis=(AssessmentHeadConfidenceBasis.INSUFFICIENT_EVIDENCE,),
        limitations=tuple(sorted({*out_limits, "Technology inventory confidence unavailable."})),
        component_summary=components,
    )


def _normalize_finding_levels(
    values: Sequence[str],
) -> tuple[FindingConfidenceLevel, ...]:
    out: list[FindingConfidenceLevel] = []
    for item in values:
        key = str(item or "").strip().lower()
        level = _FINDING_LEVELS.get(key)
        if level is not None:
            out.append(level)
        else:
            # Missing Finding Confidence is treated as unavailable, not inventable.
            out.append(FindingConfidenceLevel.UNAVAILABLE)
    return tuple(out)


def _count_levels(
    levels: Sequence[FindingConfidenceLevel],
) -> dict[FindingConfidenceLevel, int]:
    counts = {level: 0 for level in FindingConfidenceLevel}
    for item in levels:
        counts[item] += 1
    return counts


def _normalize_coverage(
    *,
    coverage_state: str | None,
    assessment_status: str,
    pack_assessment_status: str,
    evidence_completeness_values: Sequence[str],
) -> str:
    explicit = (coverage_state or "").strip().lower()
    if explicit in {
        "complete",
        "partial",
        "insufficient",
        "unavailable",
        "unsupported",
        "legacy",
    }:
        return explicit
    if pack_assessment_status == "succeeded" and assessment_status == "assessed":
        completeness = [
            str(item or "").strip().lower()
            for item in evidence_completeness_values
            if str(item or "").strip()
        ]
        if completeness and all(item == "complete" for item in completeness):
            return "complete"
        if any(item in {"partial", "incomplete", "truncated"} for item in completeness):
            return "partial"
        if any(item == "legacy" for item in completeness):
            return "legacy"
        return "complete"
    if pack_assessment_status in {"partially_succeeded", "insufficient_evidence"}:
        return "insufficient" if pack_assessment_status == "insufficient_evidence" else "partial"
    if assessment_status == "assessed":
        completeness = [
            str(item or "").strip().lower()
            for item in evidence_completeness_values
            if str(item or "").strip()
        ]
        if not completeness:
            return "complete"
        if all(item == "complete" for item in completeness):
            return "complete"
        if any(item in {"partial", "incomplete", "truncated"} for item in completeness):
            return "partial"
        if any(item == "legacy" for item in completeness):
            return "legacy"
        return "partial"
    if assessment_status == "partially_assessed":
        return "partial"
    if assessment_status == "legacy_assessment":
        return "legacy"
    return "unavailable"


def _aggregate_completeness(values: Sequence[str]) -> str | None:
    normalized = [
        str(item or "").strip().lower()
        for item in values
        if str(item or "").strip()
    ]
    if not normalized:
        return None
    if all(item == "complete" for item in normalized):
        return "complete"
    if any(item in {"partial", "incomplete", "truncated"} for item in normalized):
        return "partial"
    if any(item == "legacy" for item in normalized):
        return "legacy"
    if any(item == "unavailable" for item in normalized):
        return "unavailable"
    return "partial"
