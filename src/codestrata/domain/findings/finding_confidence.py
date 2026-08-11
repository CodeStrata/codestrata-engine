"""Finding Confidence — support strength for one Finding (Slice 5.3).

Finding Confidence is independent of severity, Rule Confidence, Match Evidence
Confidence, and Evidence Confidence. It is derived from those components via the
weakest-support principle.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class FindingConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class FindingConfidenceBasis(StrEnum):
    HIGH_RULE_CONFIDENCE = "high_rule_confidence"
    MODERATE_RULE_CONFIDENCE = "moderate_rule_confidence"
    LIMITED_RULE_CONFIDENCE = "limited_rule_confidence"
    STRONG_PRIMARY_EVIDENCE = "strong_primary_evidence"
    MULTIPLE_CONSISTENT_EVIDENCE = "multiple_consistent_evidence"
    EXACT_MATCH = "exact_match"
    EXPLICIT_CONFIGURATION = "explicit_configuration"
    DETERMINISTIC_MEASUREMENT = "deterministic_measurement"
    GRAPH_RELATIONSHIP = "graph_relationship"
    PARTIAL_EVIDENCE = "partial_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    SYNTHESIZED_EVIDENCE = "synthesized_evidence"
    MISSING_EVIDENCE_REFERENCE = "missing_evidence_reference"
    LEGACY_FINDING = "legacy_finding"
    LIMITED_MATCH_CONFIDENCE = "limited_match_confidence"


class FindingConfidenceDerivationStatus(StrEnum):
    DERIVED = "derived"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


_LEVEL_RANK: dict[FindingConfidenceLevel, int] = {
    FindingConfidenceLevel.UNAVAILABLE: 0,
    FindingConfidenceLevel.LIMITED: 1,
    FindingConfidenceLevel.MODERATE: 2,
    FindingConfidenceLevel.HIGH: 3,
}


def finding_confidence_level_rank(level: FindingConfidenceLevel) -> int:
    return _LEVEL_RANK[level]


def min_finding_confidence_level(
    levels: tuple[FindingConfidenceLevel, ...],
) -> FindingConfidenceLevel:
    if not levels:
        return FindingConfidenceLevel.UNAVAILABLE
    return min(levels, key=finding_confidence_level_rank)


class FindingConfidenceComponents(BaseModel):
    """Explainable component snapshot used during derivation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_confidence_level: str | None = None
    match_evidence_confidence: str | None = None
    primary_evidence_confidence: str | None = None
    weakest_evidence_confidence: str | None = None
    evidence_count: int = Field(default=0, ge=0)
    evidence_completeness: str | None = None
    traceability_complete: bool = False

    @field_validator(
        "rule_confidence_level",
        "match_evidence_confidence",
        "primary_evidence_confidence",
        "weakest_evidence_confidence",
        "evidence_completeness",
        mode="before",
    )
    @classmethod
    def normalize_optional(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class FindingConfidence(BaseModel):
    """Canonical finding-support reliability contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: FindingConfidenceLevel
    basis: tuple[FindingConfidenceBasis, ...]
    limitations: tuple[str, ...] = ()
    derivation_status: FindingConfidenceDerivationStatus
    component_summary: FindingConfidenceComponents = Field(
        default_factory=FindingConfidenceComponents
    )

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[FindingConfidenceBasis, ...]:
        basis = tuple(FindingConfidenceBasis(item) for item in as_tuple(value))
        if not basis:
            raise ValueError("basis must contain at least one confidence basis")
        return tuple(sorted(set(basis), key=lambda item: item.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="finding confidence limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_policy(self) -> FindingConfidence:
        if FindingConfidenceBasis.LEGACY_FINDING in self.basis:
            if self.level is not FindingConfidenceLevel.UNAVAILABLE:
                raise ValueError("legacy_finding must be UNAVAILABLE")
            if (
                self.derivation_status
                is not FindingConfidenceDerivationStatus.UNAVAILABLE
            ):
                raise ValueError("legacy_finding requires unavailable derivation_status")
        if (
            self.level is FindingConfidenceLevel.HIGH
            and not self.component_summary.traceability_complete
        ):
            raise ValueError("HIGH finding confidence requires complete traceability")
        if (
            self.level is FindingConfidenceLevel.HIGH
            and FindingConfidenceBasis.PARTIAL_EVIDENCE in self.basis
        ):
            raise ValueError("partial_evidence cannot produce HIGH finding confidence")
        if (
            self.level is FindingConfidenceLevel.HIGH
            and FindingConfidenceBasis.MISSING_EVIDENCE_REFERENCE in self.basis
        ):
            raise ValueError(
                "missing_evidence_reference cannot produce HIGH finding confidence"
            )
        return self

    @classmethod
    def unavailable(
        cls,
        *,
        limitations: tuple[str, ...] = ("Finding confidence could not be derived.",),
        basis: tuple[FindingConfidenceBasis, ...] = (
            FindingConfidenceBasis.LEGACY_FINDING,
        ),
        component_summary: FindingConfidenceComponents | None = None,
    ) -> FindingConfidence:
        return cls(
            level=FindingConfidenceLevel.UNAVAILABLE,
            basis=basis,
            limitations=limitations,
            derivation_status=FindingConfidenceDerivationStatus.UNAVAILABLE,
            component_summary=component_summary or FindingConfidenceComponents(),
        )


def finding_confidence_to_json(confidence: FindingConfidence) -> dict[str, Any]:
    """Return a deterministic JSON-compatible report projection."""

    payload = confidence.model_dump(mode="json")
    return json.loads(json.dumps(payload, sort_keys=True))
