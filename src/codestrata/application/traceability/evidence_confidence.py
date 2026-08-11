"""Deterministic Evidence Confidence derivation (Slice 5.2).

Derives confidence from structured evidence properties only — never from
severity, rule confidence, titles, AI output, or Epic 4 pack precision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from codestrata.domain.rules.enums import RuleEvidenceKind
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.traceability.enums import (
    EvidenceKind,
    EvidenceProductionMode,
    LocationPrecision,
    SnippetRedactionLevel,
)
from codestrata.domain.traceability.evidence_confidence import (
    EvidenceConfidence,
    EvidenceConfidenceBasis,
    EvidenceConfidenceDerivationStatus,
    EvidenceConfidenceLevel,
    evidence_confidence_level_rank,
    min_evidence_confidence_level,
)
from codestrata.domain.traceability.evidence_ref import EvidenceRef
from codestrata.domain.traceability.location import EvidenceLocation
from codestrata.domain.traceability.snippet import RedactedSnippet


@dataclass(frozen=True, slots=True)
class EvidenceConfidenceInputs:
    """Structured inputs for family-aware confidence derivation."""

    kind: EvidenceKind = EvidenceKind.OTHER
    production_mode: EvidenceProductionMode = EvidenceProductionMode.DIRECT
    rule_evidence_kind: RuleEvidenceKind | None = None
    provenance: str = ""
    attributes: Mapping[str, str] | None = None
    location: EvidenceLocation | None = None
    snippet: RedactedSnippet | None = None
    has_measurement: bool = False
    has_graph: bool = False
    provider_id: str | None = None
    provider_version: str | None = None
    parent_evidence_ids: tuple[str, ...] = ()
    envelope_limitations: tuple[str, ...] = ()


_PARTIAL_PARSE_TOKENS = frozenset(
    {
        "partial",
        "partially_succeeded",
        "partially-succeeded",
        "incomplete",
    }
)
_FAILED_PARSE_TOKENS = frozenset({"failed", "error", "unsupported"})
_FALLBACK_TOKENS = frozenset({"fallback", "heuristic", "path_heuristic", "legacy_adapter"})
_SIGNATURE_TOKENS = frozenset(
    {
        "private_key",
        "private-key",
        "pem",
        "certificate",
        "exact_signature",
        "key_material",
    }
)


def derive_evidence_confidence(
    inputs: EvidenceConfidenceInputs,
    *,
    parent_confidence: Mapping[str, EvidenceConfidence] | None = None,
) -> EvidenceConfidence:
    """Derive Evidence Confidence for one observation envelope."""

    if inputs.production_mode is EvidenceProductionMode.LEGACY:
        return EvidenceConfidence.unavailable(
            limitations=("Legacy evidence lacks sufficient provenance metadata.",),
        )

    attrs = {str(k).lower(): str(v).strip() for k, v in (inputs.attributes or {}).items()}
    limitations = list(inputs.envelope_limitations)
    parse_status = (attrs.get("parse_status") or attrs.get("inspection_status") or "").lower()
    extraction = (attrs.get("extraction_method") or inputs.provenance or "").lower()

    if inputs.production_mode is EvidenceProductionMode.SYNTHESIZED or (
        inputs.kind is EvidenceKind.SYNTHETIC
    ):
        return _synthesize_confidence(
            inputs,
            parent_confidence=parent_confidence or {},
            limitations=limitations,
        )

    if _is_partial_parse(parse_status) or EvidenceConfidenceBasis.PARTIAL_PARSE.value in attrs.get(
        "confidence_basis", ""
    ):
        return _build(
            EvidenceConfidenceLevel.LIMITED,
            (
                EvidenceConfidenceBasis.PARTIAL_PARSE,
                EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
            ),
            limitations=(
                *limitations,
                "Observation depends on a partial parse.",
            ),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )

    if _is_fallback(extraction, attrs):
        return _build(
            EvidenceConfidenceLevel.LIMITED,
            (
                EvidenceConfidenceBasis.FALLBACK_EXTRACTION,
                EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
            ),
            limitations=(
                *limitations,
                "Observation used fallback or heuristic extraction.",
            ),
            status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
        )

    if not inputs.provider_id and not attrs.get("evidence_id") and not inputs.provenance:
        return EvidenceConfidence.unavailable(
            limitations=("Missing provider identity and provenance.",),
        )

    family = _family_confidence(inputs, attrs=attrs, limitations=limitations)
    family = _apply_location_adjustment(family, inputs.location)
    family = _apply_redaction_adjustment(family, inputs.snippet, attrs=attrs)

    if inputs.parent_evidence_ids:
        family = _cap_by_parents(
            family,
            parent_ids=inputs.parent_evidence_ids,
            parent_confidence=parent_confidence or {},
        )
    return family


def derive_evidence_confidence_for_rule_evidence(
    item: RuleEvidence,
    *,
    kind: EvidenceKind,
    production_mode: EvidenceProductionMode,
    location: EvidenceLocation | None,
    snippet: RedactedSnippet | None,
    has_measurement: bool,
    has_graph: bool,
    provider_id: str | None,
    provider_version: str | None,
    parent_evidence_ids: tuple[str, ...],
    envelope_limitations: tuple[str, ...],
    parent_confidence: Mapping[str, EvidenceConfidence] | None = None,
) -> EvidenceConfidence:
    """Convenience wrapper used by RuleEvidence → EvidenceRef mapping."""

    return derive_evidence_confidence(
        EvidenceConfidenceInputs(
            kind=kind,
            production_mode=production_mode,
            rule_evidence_kind=item.kind,
            provenance=item.provenance or "",
            attributes=dict(item.attributes),
            location=location,
            snippet=snippet,
            has_measurement=has_measurement,
            has_graph=has_graph,
            provider_id=provider_id,
            provider_version=provider_version,
            parent_evidence_ids=parent_evidence_ids,
            envelope_limitations=envelope_limitations,
        ),
        parent_confidence=parent_confidence,
    )


def apply_parent_confidence_bounds(
    refs: Sequence[EvidenceRef],
    *,
    parent_index: Mapping[str, EvidenceConfidence] | None = None,
) -> tuple[EvidenceRef, ...]:
    """Re-derive synthesized/parent-bounded confidence using an evidence index."""

    index: dict[str, EvidenceConfidence] = {
        item.evidence_id: item.evidence_confidence for item in refs
    }
    if parent_index:
        index.update(parent_index)

    updated: list[EvidenceRef] = []
    for ref in refs:
        if not ref.parent_evidence_ids and ref.production_mode is not EvidenceProductionMode.SYNTHESIZED:
            updated.append(ref)
            continue
        capped = _cap_by_parents(
            ref.evidence_confidence,
            parent_ids=ref.parent_evidence_ids,
            parent_confidence=index,
            require_parents=ref.production_mode is EvidenceProductionMode.SYNTHESIZED
            or bool(ref.parent_evidence_ids),
        )
        if capped == ref.evidence_confidence:
            updated.append(ref)
        else:
            updated.append(ref.model_copy(update={"evidence_confidence": capped}))
    return tuple(updated)


def evidence_confidence_summary(
    refs: Sequence[EvidenceRef],
    *,
    primary_evidence_id: str | None,
) -> dict[str, str]:
    """Finding metadata helpers for Slice 5.3 (not Finding Confidence)."""

    if not refs:
        return {}
    levels = sorted({item.evidence_confidence.level.value for item in refs})
    primary_level = ""
    if primary_evidence_id:
        for item in refs:
            if item.evidence_id == primary_evidence_id:
                primary_level = item.evidence_confidence.level.value
                break
    payload = {
        "evidence_confidence_summary": ",".join(levels),
    }
    if primary_level:
        payload["primary_evidence_confidence"] = primary_level
    return payload


def _family_confidence(
    inputs: EvidenceConfidenceInputs,
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
) -> EvidenceConfidence:
    provenance = (inputs.provenance or "").lower()
    kind = inputs.kind
    rule_kind = inputs.rule_evidence_kind

    # Dependency / declaration family
    if (
        kind is EvidenceKind.DECLARATION
        or rule_kind in {RuleEvidenceKind.DEPENDENCY, RuleEvidenceKind.PACKAGE}
        or "dependency" in provenance
    ):
        return _dependency_family(attrs=attrs, limitations=limitations, inputs=inputs)

    # Sensitive configuration / signatures
    if (
        kind is EvidenceKind.CONFIGURATION
        or rule_kind is RuleEvidenceKind.CONFIGURATION_KEY
        or "sensitive" in provenance
        or "security" in provenance
    ):
        return _sensitive_family(attrs=attrs, limitations=limitations, inputs=inputs)

    # Complexity / deterministic metrics
    if (
        inputs.has_measurement
        or kind is EvidenceKind.MEASUREMENT
        or "complexity" in provenance
        or rule_kind is RuleEvidenceKind.SYMBOL
    ):
        return _complexity_family(attrs=attrs, limitations=limitations, inputs=inputs)

    # Graph / architecture
    if inputs.has_graph or kind is EvidenceKind.GRAPH or "architecture" in provenance:
        return _architecture_family(attrs=attrs, limitations=limitations, inputs=inputs)

    # Repository packs (testing/cloud/AI/performance) when eventually mapped
    if any(
        token in provenance
        for token in ("testing", "cloud", "ai_readiness", "performance")
    ) or kind is EvidenceKind.REPOSITORY_FACT:
        return _repository_signal_family(
            attrs=attrs, limitations=limitations, inputs=inputs
        )

    # Language / AST
    if "language" in provenance or rule_kind is RuleEvidenceKind.MODULE:
        return _language_family(attrs=attrs, limitations=limitations, inputs=inputs)

    # Direct file location default
    if kind is EvidenceKind.FILE_LOCATION or inputs.location is not None:
        return _build(
            EvidenceConfidenceLevel.MODERATE,
            (
                EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
                EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
            ),
            limitations=(
                *limitations,
                "Repository artifact observation without stronger parse provenance.",
            ),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )

    return _build(
        EvidenceConfidenceLevel.LIMITED,
        (EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,),
        limitations=(*limitations, "Evidence family could not be classified strongly."),
        status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
    )


def _dependency_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    version_status = (attrs.get("version_resolution_status") or "").lower()
    if version_status in {"proven_unresolved", "unresolved"} and not (
        attrs.get("resolved_version_local") or attrs.get("raw_version")
    ):
        limitations = [
            *limitations,
            "Declaration version resolution is incomplete.",
        ]
        return _build(
            EvidenceConfidenceLevel.MODERATE,
            (
                EvidenceConfidenceBasis.EXPLICIT_DECLARATION,
                EvidenceConfidenceBasis.PARTIAL_PARSE,
            ),
            limitations=tuple(limitations),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    bases = [
        EvidenceConfidenceBasis.EXPLICIT_DECLARATION,
        EvidenceConfidenceBasis.EXACT_PARSE,
    ]
    if inputs.location is not None and inputs.location.path:
        bases.append(EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT)
    return _build(
        EvidenceConfidenceLevel.HIGH,
        tuple(bases),
        limitations=tuple(limitations),
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )


def _sensitive_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    classifications = (
        attrs.get("content_classifications")
        or attrs.get("kind")
        or attrs.get("classification")
        or ""
    ).lower()
    if any(token in classifications for token in _SIGNATURE_TOKENS):
        bases: list[EvidenceConfidenceBasis] = [
            EvidenceConfidenceBasis.EXACT_SIGNATURE,
            EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
        ]
        if attrs.get("redacted_preview"):
            bases.append(EvidenceConfidenceBasis.REDACTED_OBSERVATION)
            limitations = [
                *limitations,
                "Preview is redacted; raw secret material is not retained.",
            ]
        return _build(
            EvidenceConfidenceLevel.HIGH,
            tuple(bases),
            limitations=tuple(limitations),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )

    if inputs.kind is EvidenceKind.CONFIGURATION or attrs.get("normalized_key"):
        bases = [
            EvidenceConfidenceBasis.EXPLICIT_CONFIGURATION,
            EvidenceConfidenceBasis.EXACT_PARSE,
        ]
        if attrs.get("redacted_preview"):
            bases.append(EvidenceConfidenceBasis.REDACTED_OBSERVATION)
            limitations = [
                *limitations,
                "Configuration value preview is redacted.",
            ]
        return _build(
            EvidenceConfidenceLevel.HIGH,
            tuple(bases),
            limitations=tuple(limitations),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )

    return _build(
        EvidenceConfidenceLevel.MODERATE,
        (
            EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
            EvidenceConfidenceBasis.INFERRED_CLASSIFICATION,
        ),
        limitations=(
            *limitations,
            "Sensitive classification relies on bounded static patterns.",
        ),
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )


def _complexity_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    if inputs.has_measurement or attrs.get("metric"):
        bases = [
            EvidenceConfidenceBasis.DETERMINISTIC_METRIC,
            EvidenceConfidenceBasis.SUPPORTED_AST,
        ]
        if inputs.location is not None and inputs.location.precision is LocationPrecision.EXACT:
            bases.append(EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT)
        return _build(
            EvidenceConfidenceLevel.HIGH,
            tuple(bases),
            limitations=tuple(limitations),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    return _build(
        EvidenceConfidenceLevel.MODERATE,
        (EvidenceConfidenceBasis.SUPPORTED_AST,),
        limitations=(*limitations, "Metric payload incomplete for this observation."),
        status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
    )


def _architecture_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    _ = attrs
    if inputs.has_graph:
        return _build(
            EvidenceConfidenceLevel.HIGH,
            (
                EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
                EvidenceConfidenceBasis.SUPPORTED_AST,
            ),
            limitations=(
                *limitations,
                "Graph relationship confidence assumes complete extraction for cited nodes.",
            ),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    return _build(
        EvidenceConfidenceLevel.MODERATE,
        (
            EvidenceConfidenceBasis.INFERRED_CLASSIFICATION,
            EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
        ),
        limitations=(*limitations, "Architecture classification is inferred."),
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )


def _language_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    layer = (attrs.get("layer_confidence") or "").lower()
    if layer in {"low", "unknown"}:
        return _build(
            EvidenceConfidenceLevel.LIMITED,
            (
                EvidenceConfidenceBasis.INFERRED_CLASSIFICATION,
                EvidenceConfidenceBasis.PARTIAL_PARSE,
            ),
            limitations=(*limitations, "Language layer classification confidence is low."),
            status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
        )
    if inputs.location is not None and inputs.location.precision is LocationPrecision.EXACT:
        return _build(
            EvidenceConfidenceLevel.HIGH,
            (
                EvidenceConfidenceBasis.SUPPORTED_AST,
                EvidenceConfidenceBasis.EXACT_PARSE,
            ),
            limitations=tuple(limitations),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    return _build(
        EvidenceConfidenceLevel.MODERATE,
        (EvidenceConfidenceBasis.SUPPORTED_AST,),
        limitations=(*limitations, "Language symbol extraction lacks exact location span."),
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )


def _repository_signal_family(
    *,
    attrs: Mapping[str, str],
    limitations: list[str],
    inputs: EvidenceConfidenceInputs,
) -> EvidenceConfidence:
    _ = inputs
    if attrs.get("path") or attrs.get("evidence_id"):
        return _build(
            EvidenceConfidenceLevel.MODERATE,
            (
                EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,
                EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
            ),
            limitations=(
                *limitations,
                "Static repository signal does not prove runtime behavior.",
            ),
            status=EvidenceConfidenceDerivationStatus.DERIVED,
        )
    return _build(
        EvidenceConfidenceLevel.LIMITED,
        (EvidenceConfidenceBasis.BOUNDED_STATIC_PATTERN,),
        limitations=(*limitations, "Repository signal lacks direct artifact identity."),
        status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
    )


def _synthesize_confidence(
    inputs: EvidenceConfidenceInputs,
    *,
    parent_confidence: Mapping[str, EvidenceConfidence],
    limitations: list[str],
) -> EvidenceConfidence:
    base = _build(
        EvidenceConfidenceLevel.MODERATE,
        (EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE,),
        limitations=(
            *limitations,
            "Observation is synthesized from parent evidence.",
        ),
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )
    return _cap_by_parents(
        base,
        parent_ids=inputs.parent_evidence_ids,
        parent_confidence=parent_confidence,
        require_parents=True,
    )


def _cap_by_parents(
    confidence: EvidenceConfidence,
    *,
    parent_ids: tuple[str, ...],
    parent_confidence: Mapping[str, EvidenceConfidence],
    require_parents: bool = False,
) -> EvidenceConfidence:
    if not parent_ids:
        if require_parents:
            return _build(
                EvidenceConfidenceLevel.LIMITED
                if confidence.level is not EvidenceConfidenceLevel.UNAVAILABLE
                else EvidenceConfidenceLevel.UNAVAILABLE,
                (
                    *confidence.basis,
                    EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE,
                ),
                limitations=(
                    *confidence.limitations,
                    "Synthesized evidence is missing parent evidence IDs.",
                ),
                status=EvidenceConfidenceDerivationStatus.PROVISIONAL,
            )
        return confidence

    resolved: list[EvidenceConfidence] = []
    missing = 0
    for parent_id in parent_ids:
        parent = parent_confidence.get(parent_id)
        if parent is None:
            missing += 1
            continue
        resolved.append(parent)

    if missing and not resolved:
        return _build(
            EvidenceConfidenceLevel.UNAVAILABLE,
            (
                *confidence.basis,
                EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE,
            ),
            limitations=(
                *confidence.limitations,
                "Required parent evidence confidence is unavailable.",
            ),
            status=EvidenceConfidenceDerivationStatus.UNAVAILABLE,
        )

    parent_levels = tuple(item.level for item in resolved)
    weakest = min_evidence_confidence_level(parent_levels)
    if missing:
        # Missing parents must lower confidence.
        if evidence_confidence_level_rank(weakest) > evidence_confidence_level_rank(
            EvidenceConfidenceLevel.LIMITED
        ):
            weakest = EvidenceConfidenceLevel.LIMITED
        limitations = (
            *confidence.limitations,
            *(limitation for item in resolved for limitation in item.limitations),
            "One or more parent evidence IDs could not be resolved.",
        )
    else:
        limitations = (
            *confidence.limitations,
            *(limitation for item in resolved for limitation in item.limitations),
        )

    capped_level = (
        weakest
        if evidence_confidence_level_rank(confidence.level)
        > evidence_confidence_level_rank(weakest)
        else confidence.level
    )
    bases = tuple(
        sorted(
            {
                *confidence.basis,
                EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE,
                *(basis for item in resolved for basis in item.basis),
            },
            key=lambda item: item.value,
        )
    )
    # Synthesized confidence cannot become High solely through synthesis without
    # a strong non-synthesis basis retained after capping.
    if capped_level is EvidenceConfidenceLevel.HIGH and not any(
        basis
        in {
            EvidenceConfidenceBasis.EXACT_PARSE,
            EvidenceConfidenceBasis.EXPLICIT_DECLARATION,
            EvidenceConfidenceBasis.EXPLICIT_CONFIGURATION,
            EvidenceConfidenceBasis.EXACT_SIGNATURE,
            EvidenceConfidenceBasis.SUPPORTED_AST,
            EvidenceConfidenceBasis.DETERMINISTIC_METRIC,
            EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
        }
        for basis in bases
        if basis is not EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE
    ):
        capped_level = EvidenceConfidenceLevel.MODERATE

    # High cannot retain forbidden bases from parents.
    if capped_level is EvidenceConfidenceLevel.HIGH and any(
        basis
        in {
            EvidenceConfidenceBasis.PARTIAL_PARSE,
            EvidenceConfidenceBasis.FALLBACK_EXTRACTION,
            EvidenceConfidenceBasis.APPROXIMATE_LOCATION,
            EvidenceConfidenceBasis.LEGACY_EVIDENCE,
        }
        for basis in bases
    ):
        capped_level = EvidenceConfidenceLevel.MODERATE
        bases = tuple(
            basis
            for basis in bases
            if basis
            not in {
                EvidenceConfidenceBasis.PARTIAL_PARSE,
                EvidenceConfidenceBasis.FALLBACK_EXTRACTION,
                EvidenceConfidenceBasis.APPROXIMATE_LOCATION,
                EvidenceConfidenceBasis.LEGACY_EVIDENCE,
            }
        ) or (EvidenceConfidenceBasis.SYNTHESIZED_FROM_EVIDENCE,)

    return _build(
        capped_level,
        bases,
        limitations=limitations,
        status=EvidenceConfidenceDerivationStatus.DERIVED,
    )


def _apply_location_adjustment(
    confidence: EvidenceConfidence,
    location: EvidenceLocation | None,
) -> EvidenceConfidence:
    if location is None:
        return confidence
    if location.precision in {
        LocationPrecision.APPROXIMATE,
        LocationPrecision.UNKNOWN,
    }:
        if confidence.level is EvidenceConfidenceLevel.HIGH:
            return _build(
                EvidenceConfidenceLevel.MODERATE,
                (*confidence.basis, EvidenceConfidenceBasis.APPROXIMATE_LOCATION),
                limitations=(
                    *confidence.limitations,
                    "Location precision is approximate.",
                ),
                status=confidence.derivation_status,
            )
        return _build(
            confidence.level
            if confidence.level is not EvidenceConfidenceLevel.UNAVAILABLE
            else EvidenceConfidenceLevel.LIMITED,
            (*confidence.basis, EvidenceConfidenceBasis.APPROXIMATE_LOCATION),
            limitations=(
                *confidence.limitations,
                "Location precision is approximate.",
            ),
            status=confidence.derivation_status,
        )
    if location.precision is LocationPrecision.SYMBOLIC_ONLY and (
        confidence.level is EvidenceConfidenceLevel.HIGH
    ):
        return _build(
            EvidenceConfidenceLevel.MODERATE,
            (*confidence.basis, EvidenceConfidenceBasis.APPROXIMATE_LOCATION),
            limitations=(
                *confidence.limitations,
                "Location is symbolic-only.",
            ),
            status=confidence.derivation_status,
        )
    return confidence


def _apply_redaction_adjustment(
    confidence: EvidenceConfidence,
    snippet: RedactedSnippet | None,
    *,
    attrs: Mapping[str, str],
) -> EvidenceConfidence:
    level = confidence.level
    bases = list(confidence.basis)
    limitations = list(confidence.limitations)
    if snippet is not None and snippet.redaction_level in {
        SnippetRedactionLevel.FULLY_REDACTED,
        SnippetRedactionLevel.PARTIALLY_REDACTED,
    }:
        bases.append(EvidenceConfidenceBasis.REDACTED_OBSERVATION)
        if snippet.redaction_level is SnippetRedactionLevel.FULLY_REDACTED:
            limitations.append(
                "Full redaction removes important interpretation context."
            )
            if level is EvidenceConfidenceLevel.HIGH:
                level = EvidenceConfidenceLevel.MODERATE
    elif attrs.get("redacted_preview"):
        bases.append(EvidenceConfidenceBasis.REDACTED_OBSERVATION)
    if level == confidence.level and bases == list(confidence.basis) and limitations == list(
        confidence.limitations
    ):
        return confidence
    return _build(
        level,
        tuple(bases),
        limitations=tuple(limitations),
        status=confidence.derivation_status,
    )


def _is_partial_parse(parse_status: str) -> bool:
    return any(token in parse_status for token in _PARTIAL_PARSE_TOKENS)


def _is_fallback(extraction: str, attrs: Mapping[str, str]) -> bool:
    haystack = f"{extraction} {(attrs.get('origin') or '').lower()}"
    return any(token in haystack for token in _FALLBACK_TOKENS)


def _build(
    level: EvidenceConfidenceLevel,
    basis: tuple[EvidenceConfidenceBasis, ...],
    *,
    limitations: tuple[str, ...],
    status: EvidenceConfidenceDerivationStatus,
) -> EvidenceConfidence:
    # Drop forbidden bases when targeting High before model validation.
    cleaned = basis
    if level is EvidenceConfidenceLevel.HIGH:
        cleaned = tuple(
            item
            for item in basis
            if item
            not in {
                EvidenceConfidenceBasis.PARTIAL_PARSE,
                EvidenceConfidenceBasis.FALLBACK_EXTRACTION,
                EvidenceConfidenceBasis.APPROXIMATE_LOCATION,
                EvidenceConfidenceBasis.LEGACY_EVIDENCE,
            }
        )
        if not cleaned:
            cleaned = (EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,)
    return EvidenceConfidence(
        level=level,
        basis=cleaned,
        limitations=limitations,
        derivation_status=status,
    )
