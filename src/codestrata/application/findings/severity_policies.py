"""Explicit Finding severity policy catalog (Epic 5 Slice 5.13).

Every registered Shared Rule has a deterministic policy. Title matching and
category-only production fallbacks are prohibited.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.ai_readiness.ids import HYGIENE_RULE_IDS as AI_RULE_IDS
from codestrata.domain.cloud.ids import HYGIENE_RULE_IDS as CLOUD_RULE_IDS
from codestrata.domain.dependency.ids import HYGIENE_RULE_IDS as DEPENDENCY_RULE_IDS
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.findings.severity import (
    FindingSeverityBasis,
    RepositoryContextClass,
    SeverityCalibrationStatus,
    normalize_severity_token,
    severity_rank,
)
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.performance.ids import HYGIENE_RULE_IDS as PERFORMANCE_RULE_IDS
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.security.ids import HYGIENE_RULE_IDS as SECURITY_RULE_IDS
from codestrata.domain.technical_debt.ids import COMPLEXITY_RULE_IDS
from codestrata.domain.testing.ids import HYGIENE_RULE_IDS as TESTING_RULE_IDS
from codestrata.domain.traceability.validators import normalize_limitations


class MeasurementSeverityBand(BaseModel):
    """Inclusive lower exclusive upper bands over threshold_ratio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_ratio_exclusive: str  # Decimal string; apply when ratio > this
    max_ratio_inclusive: str | None = None  # None = unbounded
    severity: FindingSeverity

    @field_validator("min_ratio_exclusive", "max_ratio_inclusive", mode="before")
    @classmethod
    def normalize_ratio(cls, value: object) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class FindingSeverityPolicy(BaseModel):
    """One reviewed severity policy for a Shared Rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    rule_id: str
    base_severity: FindingSeverity
    context_caps: dict[str, FindingSeverity] = Field(default_factory=dict)
    measurement_bands: tuple[MeasurementSeverityBand, ...] = ()
    allowed_severities: tuple[FindingSeverity, ...] = ()
    scope_escalation: bool = False
    default_bases: tuple[FindingSeverityBasis, ...] = ()
    limitations: tuple[str, ...] = ()
    calibration_status: SeverityCalibrationStatus = SeverityCalibrationStatus.CALIBRATED

    @field_validator("policy_id", "rule_id", mode="before")
    @classmethod
    def require_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="severity policy id")

    @field_validator("context_caps", mode="before")
    @classmethod
    def normalize_caps(cls, value: object) -> dict[str, FindingSeverity]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("context_caps must be a mapping")
        out: dict[str, FindingSeverity] = {}
        for key, item in value.items():
            out[str(key).strip().lower()] = normalize_severity_token(item)
        return dict(sorted(out.items()))

    @field_validator("measurement_bands", "allowed_severities", "default_bases", mode="before")
    @classmethod
    def normalize_tuples(cls, value: object) -> tuple[Any, ...]:
        return tuple(as_tuple(value))

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @model_validator(mode="after")
    def validate_policy(self) -> FindingSeverityPolicy:
        allowed = self.allowed_severities or (
            FindingSeverity.INFORMATIONAL,
            FindingSeverity.LOW,
            FindingSeverity.MEDIUM,
            FindingSeverity.HIGH,
            FindingSeverity.CRITICAL,
        )
        if self.base_severity not in allowed:
            raise ValueError(
                f"base_severity {self.base_severity.value} not in allowed_severities "
                f"for {self.policy_id}"
            )
        for cap in self.context_caps.values():
            if cap not in allowed:
                raise ValueError(
                    f"context cap {cap.value} not in allowed_severities for {self.policy_id}"
                )
        # Non-overlapping bands: sorted by min_ratio.
        previous_max: float | None = None
        for band in sorted(
            self.measurement_bands,
            key=lambda item: float(item.min_ratio_exclusive),
        ):
            lo = float(band.min_ratio_exclusive)
            if previous_max is not None and lo < previous_max:
                raise ValueError(f"overlapping measurement bands in {self.policy_id}")
            previous_max = (
                float(band.max_ratio_inclusive)
                if band.max_ratio_inclusive is not None
                else None
            )
            if band.severity not in allowed:
                raise ValueError(
                    f"band severity {band.severity.value} not allowed in {self.policy_id}"
                )
        object.__setattr__(self, "allowed_severities", tuple(allowed))
        return self


def _caps(
    *,
    test: FindingSeverity = FindingSeverity.LOW,
    fixture: FindingSeverity = FindingSeverity.INFORMATIONAL,
    documentation: FindingSeverity = FindingSeverity.INFORMATIONAL,
    example: FindingSeverity = FindingSeverity.INFORMATIONAL,
    generated: FindingSeverity = FindingSeverity.INFORMATIONAL,
    vendor: FindingSeverity = FindingSeverity.INFORMATIONAL,
    ci: FindingSeverity | None = None,
    unknown: FindingSeverity | None = None,
) -> dict[str, FindingSeverity]:
    out: dict[str, FindingSeverity] = {
        RepositoryContextClass.TEST.value: test,
        RepositoryContextClass.FIXTURE.value: fixture,
        RepositoryContextClass.DOCUMENTATION.value: documentation,
        RepositoryContextClass.EXAMPLE.value: example,
        RepositoryContextClass.GENERATED.value: generated,
        RepositoryContextClass.VENDOR.value: vendor,
    }
    if ci is not None:
        out[RepositoryContextClass.CI.value] = ci
    if unknown is not None:
        out[RepositoryContextClass.UNKNOWN.value] = unknown
    return out


def _policy(
    rule_id: str,
    base: FindingSeverity,
    *bases: FindingSeverityBasis,
    allowed: tuple[FindingSeverity, ...] | None = None,
    context_caps: dict[str, FindingSeverity] | None = None,
    bands: tuple[MeasurementSeverityBand, ...] = (),
    scope_escalation: bool = False,
    limitations: tuple[str, ...] = (),
    status: SeverityCalibrationStatus = SeverityCalibrationStatus.CALIBRATED,
) -> FindingSeverityPolicy:
    return FindingSeverityPolicy(
        policy_id=f"severity.{rule_id}",
        rule_id=rule_id,
        base_severity=base,
        context_caps=context_caps or {},
        measurement_bands=bands,
        allowed_severities=allowed
        or (
            FindingSeverity.INFORMATIONAL,
            FindingSeverity.LOW,
            FindingSeverity.MEDIUM,
            FindingSeverity.HIGH,
        ),
        scope_escalation=scope_escalation,
        default_bases=(FindingSeverityBasis.EXPLICIT_RULE_POLICY, *bases),
        limitations=limitations,
        calibration_status=status,
    )


_TD_BANDS = (
    MeasurementSeverityBand(
        min_ratio_exclusive="1",
        max_ratio_inclusive="2",
        severity=FindingSeverity.MEDIUM,
    ),
    MeasurementSeverityBand(
        min_ratio_exclusive="2",
        max_ratio_inclusive=None,
        severity=FindingSeverity.HIGH,
    ),
)

_READINESS_ALLOWED = (
    FindingSeverity.INFORMATIONAL,
    FindingSeverity.LOW,
    FindingSeverity.MEDIUM,
)

_SECURITY_CONTEXT = _caps(
    test=FindingSeverity.LOW,
    fixture=FindingSeverity.INFORMATIONAL,
    documentation=FindingSeverity.INFORMATIONAL,
    example=FindingSeverity.INFORMATIONAL,
    generated=FindingSeverity.INFORMATIONAL,
    vendor=FindingSeverity.INFORMATIONAL,
    ci=FindingSeverity.INFORMATIONAL,
    unknown=FindingSeverity.MEDIUM,
)


def _build_catalog() -> tuple[FindingSeverityPolicy, ...]:
    policies: list[FindingSeverityPolicy] = []

    # Security
    security_map: dict[str, tuple[FindingSeverity, tuple[FindingSeverityBasis, ...], tuple[FindingSeverity, ...], tuple[str, ...]]] = {
        "security.private-key-material": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.DIRECT_SECRET_EXPOSURE,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            ),
            ("Private-key signatures; raw key material never emitted.",),
        ),
        "security.credential-literal": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.DIRECT_SECRET_EXPOSURE,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            ("Static credential literals; usability/exploitability unverified.",),
        ),
        "security.placeholder-credential": (
            FindingSeverity.LOW,
            (FindingSeverityBasis.EXPLOITABLE_CONFIGURATION_PATTERN,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
            ),
            ("Placeholder credentials must not equal production credential severity.",),
        ),
        "security.tls-verification-disabled": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.EXPLICIT_SECURITY_CONTROL_DISABLED,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            ("Runtime exploitability unverified.",),
        ),
        "security.hostname-verification-disabled": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.EXPLICIT_SECURITY_CONTROL_DISABLED,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            ("Runtime exploitability unverified.",),
        ),
        "security.authentication-disabled": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.EXPLICIT_SECURITY_CONTROL_DISABLED,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            (),
        ),
        "security.permissive-cors-origin": (
            FindingSeverity.MEDIUM,
            (FindingSeverityBasis.EXPLOITABLE_CONFIGURATION_PATTERN,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            ("Does not imply an exploitable production service automatically.",),
        ),
        "security.debug-enabled": (
            FindingSeverity.MEDIUM,
            (FindingSeverityBasis.EXPLOITABLE_CONFIGURATION_PATTERN,),
            (
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            (),
        ),
    }
    for rule_id in SECURITY_RULE_IDS:
        base, bases, allowed, limits = security_map[rule_id]
        policies.append(
            _policy(
                rule_id,
                base,
                *bases,
                FindingSeverityBasis.RUNTIME_IMPACT_UNVERIFIED,
                allowed=allowed,
                context_caps=_SECURITY_CONTEXT,
                limitations=limits,
            )
        )

    # Dependency
    dep_map: dict[str, tuple[FindingSeverity, tuple[FindingSeverityBasis, ...]]] = {
        "dependency.unresolved-version": (
            FindingSeverity.MEDIUM,
            (FindingSeverityBasis.DEPENDENCY_DECLARATION_INSTABILITY,),
        ),
        "dependency.mutable-version": (
            FindingSeverity.MEDIUM,
            (FindingSeverityBasis.DEPENDENCY_DECLARATION_INSTABILITY,),
        ),
        "dependency.unbounded-requirement": (
            FindingSeverity.MEDIUM,
            (FindingSeverityBasis.DEPENDENCY_DECLARATION_INSTABILITY,),
        ),
        "dependency.conflicting-exact-versions": (
            FindingSeverity.HIGH,
            (FindingSeverityBasis.DEPENDENCY_DECLARATION_INSTABILITY,),
        ),
        "dependency.duplicate-declaration": (
            FindingSeverity.LOW,
            (FindingSeverityBasis.DEPENDENCY_DECLARATION_INSTABILITY,),
        ),
    }
    for rule_id in DEPENDENCY_RULE_IDS:
        base, bases = dep_map[rule_id]
        policies.append(
            _policy(
                rule_id,
                base,
                *bases,
                FindingSeverityBasis.BUSINESS_IMPACT_UNVERIFIED,
                allowed=(
                    FindingSeverity.INFORMATIONAL,
                    FindingSeverity.LOW,
                    FindingSeverity.MEDIUM,
                    FindingSeverity.HIGH,
                ),
                limitations=(
                    "Declaration semantics only; no vulnerability or exploit inference.",
                ),
            )
        )

    # Architecture
    arch_specs: dict[str, FindingSeverityPolicy] = {
        RULE_DEPENDENCY_CYCLE: _policy(
            RULE_DEPENDENCY_CYCLE,
            FindingSeverity.HIGH,
            FindingSeverityBasis.ARCHITECTURAL_CYCLE,
            FindingSeverityBasis.REPOSITORY_SCOPE,
            allowed=(
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
            ),
            scope_escalation=True,
            limitations=("Structural significance only; no runtime outage inference.",),
        ),
        RULE_INVALID_DEPENDENCY_DIRECTION: _policy(
            RULE_INVALID_DEPENDENCY_DIRECTION,
            FindingSeverity.MEDIUM,
            FindingSeverityBasis.ARCHITECTURAL_BOUNDARY_VIOLATION,
            allowed=(FindingSeverity.LOW, FindingSeverity.MEDIUM, FindingSeverity.HIGH),
        ),
        RULE_LAYER_BOUNDARY_VIOLATION: _policy(
            RULE_LAYER_BOUNDARY_VIOLATION,
            FindingSeverity.HIGH,
            FindingSeverityBasis.ARCHITECTURAL_BOUNDARY_VIOLATION,
            allowed=(FindingSeverity.MEDIUM, FindingSeverity.HIGH),
        ),
        RULE_EXCESSIVE_CROSS_MODULE_COUPLING: _policy(
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            FindingSeverity.MEDIUM,
            FindingSeverityBasis.DETERMINISTIC_THRESHOLD_EXCEEDANCE,
            FindingSeverityBasis.THRESHOLD_MAGNITUDE,
            allowed=(FindingSeverity.MEDIUM, FindingSeverity.HIGH),
            scope_escalation=True,
        ),
        RULE_COMPONENT_CONCENTRATION: _policy(
            RULE_COMPONENT_CONCENTRATION,
            FindingSeverity.MEDIUM,
            FindingSeverityBasis.DETERMINISTIC_THRESHOLD_EXCEEDANCE,
            allowed=(FindingSeverity.MEDIUM, FindingSeverity.HIGH),
            limitations=("Concentration heuristics are not Critical.",),
        ),
        RULE_FRAMEWORK_LEAKAGE: _policy(
            RULE_FRAMEWORK_LEAKAGE,
            FindingSeverity.MEDIUM,
            FindingSeverityBasis.ARCHITECTURAL_BOUNDARY_VIOLATION,
            allowed=(FindingSeverity.LOW, FindingSeverity.MEDIUM, FindingSeverity.HIGH),
        ),
        RULE_ENTERPRISE_STANDARD_MISMATCH: _policy(
            RULE_ENTERPRISE_STANDARD_MISMATCH,
            FindingSeverity.LOW,
            FindingSeverityBasis.STATIC_SIGNAL_ONLY,
            allowed=(
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
            ),
            limitations=(
                "Enterprise mismatch remains Low/Informational unless directly supported.",
            ),
            status=SeverityCalibrationStatus.PROVISIONAL,
        ),
    }
    policies.extend(arch_specs.values())

    # Technical Debt — measurement bands; never Critical
    for rule_id in COMPLEXITY_RULE_IDS:
        policies.append(
            _policy(
                rule_id,
                FindingSeverity.MEDIUM,
                FindingSeverityBasis.DETERMINISTIC_THRESHOLD_EXCEEDANCE,
                FindingSeverityBasis.MEASUREMENT_BAND,
                FindingSeverityBasis.THRESHOLD_MAGNITUDE,
                allowed=(
                    FindingSeverity.INFORMATIONAL,
                    FindingSeverity.LOW,
                    FindingSeverity.MEDIUM,
                    FindingSeverity.HIGH,
                ),
                context_caps=_caps(
                    test=FindingSeverity.INFORMATIONAL,
                    fixture=FindingSeverity.INFORMATIONAL,
                    documentation=FindingSeverity.INFORMATIONAL,
                    example=FindingSeverity.INFORMATIONAL,
                    generated=FindingSeverity.INFORMATIONAL,
                    vendor=FindingSeverity.INFORMATIONAL,
                ),
                bands=_TD_BANDS,
                limitations=(
                    "Typed measurement bands only; no rewrite/productivity inference.",
                    "Critical severity is not used for complexity metrics.",
                ),
            )
        )

    # Testing — absence not automatically High
    testing_map = {
        "testing.test-001": FindingSeverity.LOW,
        "testing.test-002": FindingSeverity.LOW,
        "testing.test-003": FindingSeverity.LOW,
        "testing.test-005": FindingSeverity.INFORMATIONAL,
    }
    for rule_id in TESTING_RULE_IDS:
        base = testing_map[rule_id]
        policies.append(
            _policy(
                rule_id,
                base,
                FindingSeverityBasis.STATIC_SIGNAL_ONLY,
                FindingSeverityBasis.RUNTIME_IMPACT_UNVERIFIED,
                allowed=_READINESS_ALLOWED
                if base is FindingSeverity.INFORMATIONAL
                else (
                    FindingSeverity.INFORMATIONAL,
                    FindingSeverity.LOW,
                    FindingSeverity.MEDIUM,
                ),
                limitations=("Tests are not executed; absence is not production quality.",),
            )
        )

    # Cloud — repository signals, not live posture; never High/Critical by default
    cloud_low = {
        "cloud.cloud-001",
        "cloud.cloud-021",
        "cloud.cloud-061",
    }
    for rule_id in CLOUD_RULE_IDS:
        base = (
            FindingSeverity.LOW if rule_id in cloud_low else FindingSeverity.INFORMATIONAL
        )
        policies.append(
            _policy(
                rule_id,
                base,
                FindingSeverityBasis.READINESS_INVENTORY_SIGNAL,
                FindingSeverityBasis.STATIC_SIGNAL_ONLY,
                FindingSeverityBasis.RUNTIME_IMPACT_UNVERIFIED,
                allowed=_READINESS_ALLOWED,
                limitations=(
                    "Repository cloud signals only; no live provider/runtime posture.",
                    "Static absence/presence must not become High/Critical readiness risk.",
                ),
            )
        )

    # AI Readiness
    ai_low = {
        "ai_readiness.ai-003",
        "ai_readiness.ai-011",
        "ai_readiness.ai-051",
        "ai_readiness.ai-061",
    }
    for rule_id in AI_RULE_IDS:
        base = FindingSeverity.LOW if rule_id in ai_low else FindingSeverity.INFORMATIONAL
        policies.append(
            _policy(
                rule_id,
                base,
                FindingSeverityBasis.READINESS_INVENTORY_SIGNAL,
                FindingSeverityBasis.STATIC_SIGNAL_ONLY,
                FindingSeverityBasis.BUSINESS_IMPACT_UNVERIFIED,
                allowed=_READINESS_ALLOWED,
                limitations=(
                    "Static AI readiness observations only; no org/model/safety inference.",
                    "Missing AI integration must not become High/Critical.",
                ),
            )
        )

    # Performance
    perf_low = {
        "performance.perf-003",
        "performance.perf-021",
        "performance.perf-032",
        "performance.perf-041",
        "performance.perf-052",
        "performance.perf-061",
        "performance.perf-072",
    }
    for rule_id in PERFORMANCE_RULE_IDS:
        base = (
            FindingSeverity.LOW if rule_id in perf_low else FindingSeverity.INFORMATIONAL
        )
        policies.append(
            _policy(
                rule_id,
                base,
                FindingSeverityBasis.STATIC_SIGNAL_ONLY,
                FindingSeverityBasis.RUNTIME_IMPACT_UNVERIFIED,
                allowed=_READINESS_ALLOWED,
                limitations=(
                    "Static performance signals cannot establish runtime performance.",
                ),
            )
        )

    return tuple(sorted(policies, key=lambda item: item.rule_id))


SEVERITY_POLICIES: tuple[FindingSeverityPolicy, ...] = _build_catalog()
_POLICY_BY_RULE: dict[str, FindingSeverityPolicy] = {
    item.rule_id: item for item in SEVERITY_POLICIES
}


def all_severity_policies() -> tuple[FindingSeverityPolicy, ...]:
    return SEVERITY_POLICIES


def severity_policy_for_rule(rule_id: str) -> FindingSeverityPolicy | None:
    return _POLICY_BY_RULE.get(str(rule_id).strip())


def registered_shared_rule_ids() -> tuple[str, ...]:
    return tuple(sorted(_POLICY_BY_RULE))


def assert_catalog_covers_registered_rules() -> None:
    """Fail closed when a Shared Rule lacks a severity policy."""

    expected = set(SECURITY_RULE_IDS)
    expected.update(DEPENDENCY_RULE_IDS)
    expected.update(
        {
            RULE_DEPENDENCY_CYCLE,
            RULE_INVALID_DEPENDENCY_DIRECTION,
            RULE_LAYER_BOUNDARY_VIOLATION,
            RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            RULE_COMPONENT_CONCENTRATION,
            RULE_FRAMEWORK_LEAKAGE,
            RULE_ENTERPRISE_STANDARD_MISMATCH,
        }
    )
    expected.update(COMPLEXITY_RULE_IDS)
    expected.update(TESTING_RULE_IDS)
    expected.update(CLOUD_RULE_IDS)
    expected.update(AI_RULE_IDS)
    expected.update(PERFORMANCE_RULE_IDS)
    missing = sorted(expected - set(_POLICY_BY_RULE))
    if missing:
        raise AssertionError(f"Shared Rules missing severity policies: {missing}")
    duplicates = len(SEVERITY_POLICIES) - len(_POLICY_BY_RULE)
    if duplicates:
        raise AssertionError("severity policy catalog has duplicate rule_ids")


assert_catalog_covers_registered_rules()


def clamp_to_allowed(
    severity: FindingSeverity,
    allowed: tuple[FindingSeverity, ...],
) -> FindingSeverity:
    if severity in allowed:
        return severity
    # Choose nearest lower allowed severity.
    candidates = [item for item in allowed if severity_rank(item) <= severity_rank(severity)]
    if candidates:
        return max(candidates, key=severity_rank)
    return min(allowed, key=severity_rank)
