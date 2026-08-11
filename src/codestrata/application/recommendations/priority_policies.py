"""Explicit Recommendation priority policy catalog (Slice 5.14).

Every builtin deterministic Recommendation provider resolves to one policy.
No title matching. No Precision/Recall/FP/FN inputs.
"""

from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.recommendations.enums import RecommendationPriority
from codestrata.domain.recommendations.priority import (
    BAND_HIGH_MIN,
    BAND_IMMEDIATE_MIN,
    BAND_MEDIUM_MIN,
    PRIORITY_SCORE_MAX,
    PRIORITY_SCORE_MIN,
    PriorityCalibrationStatus,
)
from codestrata.domain.traceability.validators import normalize_limitations

# Severity contribution bounds (additive points, not severity copy).
SEVERITY_POINTS: Mapping[FindingSeverity, int] = {
    FindingSeverity.CRITICAL: 30,
    FindingSeverity.HIGH: 22,
    FindingSeverity.MEDIUM: 12,
    FindingSeverity.LOW: 4,
    FindingSeverity.INFORMATIONAL: 0,
}


class RecommendationPriorityPolicy(BaseModel):
    """Deterministic, reviewable priority policy for one provider/action family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    provider_id: str
    supported_rule_ids: tuple[str, ...] = ()
    base_score: int = Field(ge=PRIORITY_SCORE_MIN, le=PRIORITY_SCORE_MAX)
    severity_weight_enabled: bool = True
    max_severity_points: int = Field(default=30, ge=0, le=40)
    scope_adjustment_max: int = Field(default=0, ge=0, le=10)
    correlation_adjustment_max: int = Field(default=0, ge=0, le=10)
    allows_immediate: bool = False
    allows_direct_security_exposure: bool = False
    correlation_aware: bool = False
    # Max priority after Moderate Recommendation Confidence (unless exposure policy).
    moderate_confidence_max_priority: RecommendationPriority = RecommendationPriority.HIGH
    limited_confidence_max_priority: RecommendationPriority = RecommendationPriority.MEDIUM
    unavailable_confidence_max_priority: RecommendationPriority = RecommendationPriority.MEDIUM
    allowed_priorities: tuple[RecommendationPriority, ...] = (
        RecommendationPriority.LOW,
        RecommendationPriority.MEDIUM,
        RecommendationPriority.HIGH,
        RecommendationPriority.IMMEDIATE,
    )
    limitations: tuple[str, ...] = ()
    calibration_status: PriorityCalibrationStatus = PriorityCalibrationStatus.CALIBRATED
    # Explicit phase preference for roadmap (not an input to score).
    preferred_phase: str | None = None

    @field_validator("policy_id", "provider_id", mode="before")
    @classmethod
    def normalize_ids(cls, value: object) -> str:
        return require_nonblank(str(value), label="policy_id").strip()

    @field_validator("supported_rule_ids", mode="before")
    @classmethod
    def normalize_rules(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({require_nonblank(str(item), label="rule_id") for item in as_tuple(value)}))

    @field_validator("allowed_priorities", mode="before")
    @classmethod
    def normalize_allowed(cls, value: object) -> tuple[RecommendationPriority, ...]:
        items = tuple(RecommendationPriority(str(item)) for item in as_tuple(value))
        if not items:
            raise ValueError("allowed_priorities must not be empty")
        return items

    @field_validator("limitations", mode="before")
    @classmethod
    def normalize_limits(cls, value: object) -> tuple[str, ...]:
        return normalize_limitations(value)

    @model_validator(mode="after")
    def validate_policy(self) -> RecommendationPriorityPolicy:
        if self.allows_immediate and RecommendationPriority.IMMEDIATE not in self.allowed_priorities:
            raise ValueError(f"{self.policy_id}: allows_immediate requires IMMEDIATE in allowed_priorities")
        if self.correlation_aware and self.correlation_adjustment_max <= 0:
            raise ValueError(f"{self.policy_id}: correlation-aware policy needs positive correlation_adjustment_max")
        if not self.allows_immediate and RecommendationPriority.IMMEDIATE in self.allowed_priorities:
            # Strip Immediate from allowed when policy forbids it.
            object.__setattr__(
                self,
                "allowed_priorities",
                tuple(p for p in self.allowed_priorities if p is not RecommendationPriority.IMMEDIATE),
            )
        return self


def _policy(
    *,
    policy_id: str,
    provider_id: str,
    base_score: int,
    supported_rule_ids: tuple[str, ...] = (),
    allows_immediate: bool = False,
    allows_direct_security_exposure: bool = False,
    correlation_aware: bool = False,
    correlation_adjustment_max: int = 0,
    scope_adjustment_max: int = 0,
    severity_weight_enabled: bool = True,
    limited_confidence_max_priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    unavailable_confidence_max_priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    allowed_priorities: tuple[RecommendationPriority, ...] | None = None,
    limitations: tuple[str, ...] = (),
    calibration_status: PriorityCalibrationStatus = PriorityCalibrationStatus.CALIBRATED,
    preferred_phase: str | None = None,
) -> RecommendationPriorityPolicy:
    if allowed_priorities is None:
        if allows_immediate:
            allowed_priorities = (
                RecommendationPriority.LOW,
                RecommendationPriority.MEDIUM,
                RecommendationPriority.HIGH,
                RecommendationPriority.IMMEDIATE,
            )
        else:
            allowed_priorities = (
                RecommendationPriority.LOW,
                RecommendationPriority.MEDIUM,
                RecommendationPriority.HIGH,
            )
    return RecommendationPriorityPolicy(
        policy_id=policy_id,
        provider_id=provider_id,
        supported_rule_ids=supported_rule_ids,
        base_score=base_score,
        severity_weight_enabled=severity_weight_enabled,
        scope_adjustment_max=scope_adjustment_max,
        correlation_adjustment_max=correlation_adjustment_max,
        allows_immediate=allows_immediate,
        allows_direct_security_exposure=allows_direct_security_exposure,
        correlation_aware=correlation_aware,
        limited_confidence_max_priority=limited_confidence_max_priority,
        unavailable_confidence_max_priority=unavailable_confidence_max_priority,
        allowed_priorities=allowed_priorities,
        limitations=limitations,
        calibration_status=calibration_status,
        preferred_phase=preferred_phase,
    )


_BUILTIN_POLICIES: tuple[RecommendationPriorityPolicy, ...] = (
    _policy(
        policy_id="priority.governance.missing-readme",
        provider_id="codestrata-rec-missing-readme",
        base_score=32,
        allowed_priorities=(RecommendationPriority.LOW, RecommendationPriority.MEDIUM),
        limited_confidence_max_priority=RecommendationPriority.LOW,
        preferred_phase="stabilize",
        limitations=("Documentation hygiene; not production security urgency.",),
    ),
    _policy(
        policy_id="priority.governance.missing-license",
        provider_id="codestrata-rec-missing-license",
        base_score=58,
        allowed_priorities=(
            RecommendationPriority.LOW,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.HIGH,
        ),
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="stabilize",
    ),
    _policy(
        policy_id="priority.testing.missing-tests",
        provider_id="codestrata-rec-missing-tests",
        base_score=60,
        allowed_priorities=(
            RecommendationPriority.LOW,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.HIGH,
        ),
        # Stabilize-foundation action may be High when Findings support it;
        # still cannot be Immediate (no allows_immediate).
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="stabilize",
        limitations=(
            "Absence-based testing action; static inventory may be incomplete.",
        ),
    ),
    _policy(
        policy_id="priority.build.missing-ci",
        provider_id="codestrata-rec-missing-ci-workflow",
        base_score=40,
        allowed_priorities=(RecommendationPriority.LOW, RecommendationPriority.MEDIUM),
        preferred_phase="stabilize",
    ),
    _policy(
        policy_id="priority.build.missing-maven-wrapper",
        provider_id="codestrata-rec-maven-wrapper-missing",
        base_score=45,
        allowed_priorities=(
            RecommendationPriority.LOW,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.HIGH,
        ),
        preferred_phase="stabilize",
        limitations=("Build reproducibility hygiene; not a vulnerability claim.",),
    ),
    _policy(
        policy_id="priority.dependency.missing-npm-lockfile",
        provider_id="codestrata-rec-npm-lockfile-missing",
        base_score=58,
        allowed_priorities=(
            RecommendationPriority.LOW,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.HIGH,
        ),
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="stabilize",
        limitations=("Dependency hygiene; not vulnerability urgency.",),
    ),
    _policy(
        policy_id="priority.architecture.unsupported-spring-boot",
        provider_id="codestrata-rec-unsupported-spring-boot",
        base_score=68,
        allowed_priorities=(RecommendationPriority.MEDIUM, RecommendationPriority.HIGH),
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="modernize",
        limitations=("Framework support risk; not assumed outage urgency.",),
    ),
    _policy(
        policy_id="priority.architecture.java-language-level",
        provider_id="codestrata-rec-java-language-level",
        base_score=55,
        allowed_priorities=(
            RecommendationPriority.LOW,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.HIGH,
        ),
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="modernize",
    ),
    _policy(
        policy_id="priority.build.missing-node-engine",
        provider_id="codestrata-rec-missing-node-engine",
        base_score=40,
        allowed_priorities=(RecommendationPriority.LOW, RecommendationPriority.MEDIUM),
        preferred_phase="stabilize",
    ),
    _policy(
        policy_id="priority.technical_debt.large-repository",
        provider_id="codestrata-rec-large-repository",
        base_score=28,
        severity_weight_enabled=False,
        allowed_priorities=(RecommendationPriority.LOW,),
        limited_confidence_max_priority=RecommendationPriority.LOW,
        unavailable_confidence_max_priority=RecommendationPriority.LOW,
        preferred_phase="optimize",
        limitations=("Repository size observation; not rewrite urgency.",),
    ),
    _policy(
        policy_id="priority.security.transport-verification",
        provider_id="codestrata-rec-correlation-transport-verification",
        base_score=68,
        supported_rule_ids=(
            "security.tls-verification-disabled",
            "security.hostname-verification-disabled",
        ),
        allows_immediate=True,
        allows_direct_security_exposure=True,
        correlation_aware=True,
        correlation_adjustment_max=5,
        scope_adjustment_max=3,
        preferred_phase="secure",
        limitations=("Static configuration remediation; runtime effect not validated.",),
    ),
    _policy(
        policy_id="priority.dependency.normalize-conflict-duplicate",
        provider_id="codestrata-rec-correlation-dependency-normalization",
        base_score=55,
        supported_rule_ids=(
            "dependency.duplicate-declaration",
            "dependency.conflicting-exact-versions",
        ),
        correlation_aware=True,
        correlation_adjustment_max=5,
        scope_adjustment_max=3,
        preferred_phase="stabilize",
        limitations=("Dependency normalization; not vulnerability urgency.",),
    ),
    _policy(
        policy_id="priority.finding_backed.compatibility",
        provider_id="finding-backed-compatibility",
        base_score=50,
        allows_immediate=True,
        allows_direct_security_exposure=True,
        scope_adjustment_max=3,
        # Limited support may still be High for direct-exposure actions; Immediate
        # requires stronger Recommendation Confidence (or Critical + High confidence).
        limited_confidence_max_priority=RecommendationPriority.HIGH,
        preferred_phase="stabilize",
        calibration_status=PriorityCalibrationStatus.PROVISIONAL,
        limitations=(
            "Finding-backed compatibility policy; no dedicated provider policy.",
        ),
    ),
    _policy(
        policy_id="priority.legacy.compatibility",
        provider_id="legacy",
        base_score=40,
        severity_weight_enabled=False,
        allowed_priorities=(RecommendationPriority.LOW, RecommendationPriority.MEDIUM),
        unavailable_confidence_max_priority=RecommendationPriority.MEDIUM,
        limited_confidence_max_priority=RecommendationPriority.MEDIUM,
        calibration_status=PriorityCalibrationStatus.LEGACY,
        limitations=("Legacy Recommendation; priority bounded conservatively.",),
        preferred_phase="stabilize",
    ),
)


_POLICY_BY_ID: dict[str, RecommendationPriorityPolicy] = {
    item.policy_id: item for item in _BUILTIN_POLICIES
}
_POLICY_BY_PROVIDER: dict[str, RecommendationPriorityPolicy] = {
    item.provider_id: item for item in _BUILTIN_POLICIES if item.provider_id != "legacy"
}


def all_priority_policies() -> tuple[RecommendationPriorityPolicy, ...]:
    return _BUILTIN_POLICIES


def priority_policy_by_id(policy_id: str) -> RecommendationPriorityPolicy | None:
    return _POLICY_BY_ID.get(policy_id)


def resolve_priority_policy(
    provider_id: str | None,
    *,
    recommendation_type: str | None = None,
    has_supporting_findings: bool = False,
) -> RecommendationPriorityPolicy:
    """Resolve policy for a provider.

    Unknown providers with supporting Findings use finding-backed compatibility.
    True legacy (no support) uses the conservative legacy policy.
    """

    if provider_id and provider_id in _POLICY_BY_PROVIDER:
        return _POLICY_BY_PROVIDER[provider_id]
    rec_type = str(recommendation_type or "").strip().lower()
    if has_supporting_findings or rec_type in {"finding_backed", "merged"}:
        return _POLICY_BY_ID["priority.finding_backed.compatibility"]
    return _POLICY_BY_ID["priority.legacy.compatibility"]


def assert_builtin_providers_covered(provider_ids: set[str]) -> None:
    missing = sorted(provider_ids - set(_POLICY_BY_PROVIDER))
    if missing:
        raise AssertionError(
            "Recommendation priority catalog missing providers: " + ", ".join(missing)
        )


# Import-time coverage for known builtin provider IDs.
from codestrata.services.recommendations.providers.builtin import (  # noqa: E402
    builtin_recommendation_providers,
)

assert_builtin_providers_covered({p.id() for p in builtin_recommendation_providers()})

# Score band helpers re-exported for diagnostics.
__all__ = [
    "BAND_HIGH_MIN",
    "BAND_IMMEDIATE_MIN",
    "BAND_MEDIUM_MIN",
    "RecommendationPriorityPolicy",
    "SEVERITY_POINTS",
    "all_priority_policies",
    "assert_builtin_providers_covered",
    "priority_policy_by_id",
    "resolve_priority_policy",
]
