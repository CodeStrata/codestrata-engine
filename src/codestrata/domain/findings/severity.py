"""Finding severity calibration contracts (Epic 5 Slice 5.13).

Severity answers how significant an observed technical condition is within
assessed repository scope. It is independent of every confidence model,
Precision/Recall, Recommendation priority, and correlation/duplicate counts.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.traceability.validators import normalize_limitations


class FindingSeverityBasis(StrEnum):
    DIRECT_SECRET_EXPOSURE = "direct_secret_exposure"
    EXPLICIT_SECURITY_CONTROL_DISABLED = "explicit_security_control_disabled"
    EXPLOITABLE_CONFIGURATION_PATTERN = "exploitable_configuration_pattern"
    ARCHITECTURAL_BOUNDARY_VIOLATION = "architectural_boundary_violation"
    ARCHITECTURAL_CYCLE = "architectural_cycle"
    DEPENDENCY_DECLARATION_INSTABILITY = "dependency_declaration_instability"
    DETERMINISTIC_THRESHOLD_EXCEEDANCE = "deterministic_threshold_exceedance"
    THRESHOLD_MAGNITUDE = "threshold_magnitude"
    REPOSITORY_SCOPE = "repository_scope"
    PRODUCTION_CONTEXT = "production_context"
    TEST_OR_FIXTURE_CONTEXT = "test_or_fixture_context"
    BLAST_RADIUS = "blast_radius"
    REPEATED_AFFECTED_SUBJECTS = "repeated_affected_subjects"
    RUNTIME_IMPACT_UNVERIFIED = "runtime_impact_unverified"
    BUSINESS_IMPACT_UNVERIFIED = "business_impact_unverified"
    STATIC_SIGNAL_ONLY = "static_signal_only"
    LEGACY_RULE = "legacy_rule"
    RULE_DEFAULT = "rule_default"
    EXPLICIT_RULE_POLICY = "explicit_rule_policy"
    CONTEXT_CAP = "context_cap"
    MEASUREMENT_BAND = "measurement_band"
    READINESS_INVENTORY_SIGNAL = "readiness_inventory_signal"


class SeverityCalibrationStatus(StrEnum):
    CALIBRATED = "calibrated"
    PROVISIONAL = "provisional"
    LEGACY = "legacy"
    UNAVAILABLE = "unavailable"


class RepositoryContextClass(StrEnum):
    PRODUCTION = "production"
    TEST = "test"
    FIXTURE = "fixture"
    GENERATED = "generated"
    VENDOR = "vendor"
    EXAMPLE = "example"
    DOCUMENTATION = "documentation"
    CI = "ci"
    UNKNOWN = "unknown"


class FindingSeverityComponents(BaseModel):
    """Explainable severity component snapshot (no probabilities)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_severity: FindingSeverity | None = None
    calibrated_severity: FindingSeverity | None = None
    rule_id: str | None = None
    assessment_head: str | None = None
    production_context: str | None = None
    threshold_ratio: str | None = None
    affected_subject_count: int | None = Field(default=None, ge=0)
    affected_scope: str | None = None
    directness: str | None = None
    runtime_validation: str | None = None
    limitations_count: int = Field(default=0, ge=0)

    @field_validator("rule_id", "assessment_head", "production_context", "affected_scope", "directness", "runtime_validation", "threshold_ratio", mode="before")
    @classmethod
    def optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class FindingSeverityAssessment(BaseModel):
    """Canonical severity calibration result for one Finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: FindingSeverity
    basis: tuple[FindingSeverityBasis, ...] = ()
    calibration_status: SeverityCalibrationStatus = SeverityCalibrationStatus.CALIBRATED
    limitations: tuple[str, ...] = ()
    component_summary: FindingSeverityComponents = Field(
        default_factory=FindingSeverityComponents
    )
    policy_id: str | None = None

    @field_validator("basis", mode="before")
    @classmethod
    def normalize_basis(cls, value: object) -> tuple[Any, ...]:
        items = tuple(as_tuple(value))
        # Preserve order, unique.
        seen: set[str] = set()
        out: list[Any] = []
        for item in items:
            key = getattr(item, "value", str(item))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return tuple(out)

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @field_validator("policy_id", mode="before")
    @classmethod
    def normalize_policy(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def validate_assessment(self) -> FindingSeverityAssessment:
        if (
            self.calibration_status is SeverityCalibrationStatus.CALIBRATED
            and not self.basis
        ):
            raise ValueError("calibrated severity assessment requires at least one basis")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def unavailable(
        cls,
        *,
        severity: FindingSeverity,
        limitations: tuple[str, ...] = (),
    ) -> FindingSeverityAssessment:
        return cls(
            severity=severity,
            basis=(FindingSeverityBasis.LEGACY_RULE,),
            calibration_status=SeverityCalibrationStatus.UNAVAILABLE,
            limitations=limitations
            or ("Severity calibration unavailable for this Finding.",),
            component_summary=FindingSeverityComponents(
                base_severity=severity,
                calibrated_severity=severity,
                limitations_count=1,
            ),
        )

    @classmethod
    def legacy(
        cls,
        *,
        severity: FindingSeverity,
        limitations: tuple[str, ...] = (),
    ) -> FindingSeverityAssessment:
        return cls(
            severity=severity,
            basis=(FindingSeverityBasis.LEGACY_RULE,),
            calibration_status=SeverityCalibrationStatus.LEGACY,
            limitations=limitations
            or ("Legacy Phase-1 Finding; severity preserved without recalibration.",),
            component_summary=FindingSeverityComponents(
                base_severity=severity,
                calibrated_severity=severity,
                limitations_count=1,
            ),
        )


_SEVERITY_RANK: dict[FindingSeverity, int] = {
    FindingSeverity.INFORMATIONAL: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


def severity_rank(severity: FindingSeverity) -> int:
    return _SEVERITY_RANK[severity]


def min_severity(left: FindingSeverity, right: FindingSeverity) -> FindingSeverity:
    return left if severity_rank(left) <= severity_rank(right) else right


def max_severity(left: FindingSeverity, right: FindingSeverity) -> FindingSeverity:
    return left if severity_rank(left) >= severity_rank(right) else right


def compute_threshold_ratio(
    measured_value: object,
    threshold: object,
) -> str | None:
    """Decimal-safe measured/threshold ratio string, or None when unavailable."""

    try:
        measured = Decimal(str(measured_value))
        denom = Decimal(str(threshold))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if denom == 0:
        return None
    ratio = measured / denom
    # Normalize trailing zeros for stable serialization.
    text = format(ratio.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_severity_token(value: object) -> FindingSeverity:
    """Map legacy ``info`` and aliases onto canonical FindingSeverity."""

    text = require_nonblank(str(value), label="severity").strip().lower()
    if text in {"info", "informational"}:
        return FindingSeverity.INFORMATIONAL
    return FindingSeverity(text)


def assessment_head_for_rule(rule_id: str) -> str:
    text = rule_id.strip().lower()
    for prefix, head in (
        ("security.", "security"),
        ("dependency.", "dependency"),
        ("architecture.", "architecture"),
        ("technical_debt.", "technical_debt"),
        ("cloud.", "cloud"),
        ("ai_readiness.", "ai_readiness"),
        ("testing.", "testing"),
        ("performance.", "performance"),
        ("codestrata-rule-", "legacy"),
    ):
        if text.startswith(prefix):
            return head
    return "other"
