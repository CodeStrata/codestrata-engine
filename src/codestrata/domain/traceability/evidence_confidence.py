"""Inherent reliability of one evidence observation (Slice 5.2).

Evidence Confidence is independent of Rule Confidence, Match Evidence Confidence,
and Finding Confidence. It answers how reliable and complete a specific evidence
observation is — not how severe or how likely a repository is defective.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class EvidenceConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class EvidenceConfidenceBasis(StrEnum):
    EXACT_PARSE = "exact_parse"
    EXPLICIT_DECLARATION = "explicit_declaration"
    EXPLICIT_CONFIGURATION = "explicit_configuration"
    EXACT_SIGNATURE = "exact_signature"
    SUPPORTED_AST = "supported_ast"
    DETERMINISTIC_METRIC = "deterministic_metric"
    DIRECT_REPOSITORY_ARTIFACT = "direct_repository_artifact"
    BOUNDED_STATIC_PATTERN = "bounded_static_pattern"
    INFERRED_CLASSIFICATION = "inferred_classification"
    PARTIAL_PARSE = "partial_parse"
    FALLBACK_EXTRACTION = "fallback_extraction"
    APPROXIMATE_LOCATION = "approximate_location"
    SYNTHESIZED_FROM_EVIDENCE = "synthesized_from_evidence"
    LEGACY_EVIDENCE = "legacy_evidence"
    REDACTED_OBSERVATION = "redacted_observation"


class EvidenceConfidenceDerivationStatus(StrEnum):
    DERIVED = "derived"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


_STRONG_BASES = frozenset(
    {
        EvidenceConfidenceBasis.EXACT_PARSE,
        EvidenceConfidenceBasis.EXPLICIT_DECLARATION,
        EvidenceConfidenceBasis.EXPLICIT_CONFIGURATION,
        EvidenceConfidenceBasis.EXACT_SIGNATURE,
        EvidenceConfidenceBasis.SUPPORTED_AST,
        EvidenceConfidenceBasis.DETERMINISTIC_METRIC,
        EvidenceConfidenceBasis.DIRECT_REPOSITORY_ARTIFACT,
    }
)

_FORBIDDEN_HIGH_BASES = frozenset(
    {
        EvidenceConfidenceBasis.PARTIAL_PARSE,
        EvidenceConfidenceBasis.FALLBACK_EXTRACTION,
        EvidenceConfidenceBasis.LEGACY_EVIDENCE,
        EvidenceConfidenceBasis.APPROXIMATE_LOCATION,
    }
)

_LEVEL_RANK: dict[EvidenceConfidenceLevel, int] = {
    EvidenceConfidenceLevel.UNAVAILABLE: 0,
    EvidenceConfidenceLevel.LIMITED: 1,
    EvidenceConfidenceLevel.MODERATE: 2,
    EvidenceConfidenceLevel.HIGH: 3,
}


def evidence_confidence_level_rank(level: EvidenceConfidenceLevel) -> int:
    return _LEVEL_RANK[level]


def min_evidence_confidence_level(
    levels: tuple[EvidenceConfidenceLevel, ...],
) -> EvidenceConfidenceLevel:
    if not levels:
        return EvidenceConfidenceLevel.UNAVAILABLE
    return min(levels, key=evidence_confidence_level_rank)


class EvidenceConfidence(BaseModel):
    """Canonical evidence-observation reliability contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: EvidenceConfidenceLevel
    basis: tuple[EvidenceConfidenceBasis, ...]
    limitations: tuple[str, ...] = ()
    derivation_status: EvidenceConfidenceDerivationStatus

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[EvidenceConfidenceBasis, ...]:
        basis = tuple(EvidenceConfidenceBasis(item) for item in as_tuple(value))
        if not basis:
            raise ValueError("basis must contain at least one confidence basis")
        return tuple(sorted(set(basis), key=lambda item: item.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="evidence confidence limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_policy(self) -> EvidenceConfidence:
        if EvidenceConfidenceBasis.LEGACY_EVIDENCE in self.basis:
            if self.level is not EvidenceConfidenceLevel.UNAVAILABLE:
                raise ValueError("legacy_evidence must be UNAVAILABLE")
            if (
                self.derivation_status
                is not EvidenceConfidenceDerivationStatus.UNAVAILABLE
            ):
                raise ValueError("legacy_evidence requires unavailable derivation_status")
        if self.level is EvidenceConfidenceLevel.HIGH:
            if not _STRONG_BASES.intersection(self.basis):
                raise ValueError("HIGH evidence confidence requires a strong basis")
            if _FORBIDDEN_HIGH_BASES.intersection(self.basis):
                raise ValueError(
                    "partial_parse, fallback_extraction, approximate_location, "
                    "and legacy_evidence cannot be HIGH"
                )
        return self

    @classmethod
    def unavailable(
        cls,
        *,
        limitations: tuple[str, ...] = ("Evidence confidence could not be derived.",),
        basis: tuple[EvidenceConfidenceBasis, ...] = (
            EvidenceConfidenceBasis.LEGACY_EVIDENCE,
        ),
    ) -> EvidenceConfidence:
        return cls(
            level=EvidenceConfidenceLevel.UNAVAILABLE,
            basis=basis,
            limitations=limitations,
            derivation_status=EvidenceConfidenceDerivationStatus.UNAVAILABLE,
        )


def evidence_confidence_to_json(confidence: EvidenceConfidence) -> dict[str, Any]:
    """Return a deterministic JSON-compatible report projection."""

    payload = confidence.model_dump(mode="json")
    return json.loads(json.dumps(payload, sort_keys=True))
