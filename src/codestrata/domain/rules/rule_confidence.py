"""Inherent reliability metadata for Shared Rules."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.graph.validation import as_tuple, require_nonblank


class RuleConfidenceLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


class RuleConfidenceBasis(StrEnum):
    EXACT_SIGNATURE = "exact_signature"
    EXPLICIT_CONFIGURATION = "explicit_configuration"
    DETERMINISTIC_THRESHOLD = "deterministic_threshold"
    STRUCTURAL_GRAPH_RELATIONSHIP = "structural_graph_relationship"
    MANIFEST_DECLARATION = "manifest_declaration"
    STATIC_PATTERN = "static_pattern"
    INFERRED_CLASSIFICATION = "inferred_classification"
    PARTIAL_EXTRACTION = "partial_extraction"
    LEGACY_RULE = "legacy_rule"


class RuleConfidenceCalibrationStatus(StrEnum):
    DEFINED = "defined"
    VALIDATION_SUPPORTED = "validation_supported"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"


def compute_precision_recall(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> tuple[float | None, float | None]:
    """Compute precision and recall, preserving unknown zero-denominator metrics.

    Both values delegate to canonical quality-metrics helpers (Slices 5.7–5.8).
    """

    from codestrata.domain.quality_metrics.precision import precision_ratio_as_float
    from codestrata.domain.quality_metrics.recall import recall_ratio_as_float

    precision = precision_ratio_as_float(true_positives, false_positives)
    recall = recall_ratio_as_float(true_positives, false_negatives)
    return precision, recall


class RuleValidationSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    validation_set_id: str
    repositories_evaluated: int = Field(default=0, ge=0)
    true_positives: int = Field(default=0, ge=0)
    false_positives: int = Field(default=0, ge=0)
    false_negatives: int = Field(default=0, ge=0)
    precision: float | None = Field(default=None, ge=0.0, le=1.0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)
    limitations: tuple[str, ...] = ()

    @field_validator("validation_set_id", mode="before")
    @classmethod
    def normalize_validation_set_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="validation_set_id")

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="validation limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_metrics(self) -> RuleValidationSupport:
        expected_precision, expected_recall = compute_precision_recall(
            self.true_positives,
            self.false_positives,
            self.false_negatives,
        )
        for name, actual, expected in (
            ("precision", self.precision, expected_precision),
            ("recall", self.recall, expected_recall),
        ):
            if actual is None:
                continue
            if expected is None or abs(actual - expected) > 1e-12:
                raise ValueError(f"{name} must match the validation counts")
        return self


_STRONG_BASES = frozenset(
    {
        RuleConfidenceBasis.EXACT_SIGNATURE,
        RuleConfidenceBasis.EXPLICIT_CONFIGURATION,
        RuleConfidenceBasis.DETERMINISTIC_THRESHOLD,
        RuleConfidenceBasis.STRUCTURAL_GRAPH_RELATIONSHIP,
        RuleConfidenceBasis.MANIFEST_DECLARATION,
    }
)


class RuleConfidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: RuleConfidenceLevel
    basis: tuple[RuleConfidenceBasis, ...]
    limitations: tuple[str, ...] = ()
    calibration_status: RuleConfidenceCalibrationStatus
    validation_support: RuleValidationSupport | None = None

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[RuleConfidenceBasis, ...]:
        basis = tuple(RuleConfidenceBasis(item) for item in as_tuple(value))
        if not basis:
            raise ValueError("basis must contain at least one confidence basis")
        return tuple(sorted(set(basis), key=lambda item: item.value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limitations(cls, value: object) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    require_nonblank(str(item), label="rule confidence limitation")
                    for item in as_tuple(value)
                }
            )
        )

    @model_validator(mode="after")
    def validate_policy(self) -> RuleConfidence:
        if self.level is RuleConfidenceLevel.HIGH:
            if not _STRONG_BASES.intersection(self.basis):
                raise ValueError("HIGH confidence requires at least one strong basis")
            if {
                RuleConfidenceBasis.PARTIAL_EXTRACTION,
                RuleConfidenceBasis.LEGACY_RULE,
            }.intersection(self.basis):
                raise ValueError("PARTIAL_EXTRACTION and LEGACY_RULE cannot be HIGH")
        if (
            self.calibration_status
            is RuleConfidenceCalibrationStatus.VALIDATION_SUPPORTED
        ):
            if self.validation_support is None:
                raise ValueError("VALIDATION_SUPPORTED requires validation_support")
            if self.validation_support.true_positives < 1:
                raise ValueError(
                    "VALIDATION_SUPPORTED requires at least one true positive"
                )
        if self.validation_support is not None and not self.validation_support.limitations:
            raise ValueError("validation_support requires explicit limitations")
        return self


def rule_confidence_to_json(rule_confidence: RuleConfidence) -> dict[str, Any]:
    """Return a deterministic JSON-compatible report projection."""

    payload = rule_confidence.model_dump(mode="json")
    return json.loads(json.dumps(payload, sort_keys=True))
