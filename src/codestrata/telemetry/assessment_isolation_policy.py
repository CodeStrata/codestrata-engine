"""Independent assessment telemetry isolation policy (Slice 9.12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_ID = (
    "community-telemetry-assessment-isolation-policy"
)
COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION}"
)

_REVIEW_STATUS = "primary_assessment_authoritative_telemetry_optional"

_LIMITATIONS: tuple[str, ...] = (
    "primary_operation_authoritative",
    "telemetry_side_effects_optional",
    "telemetry_failures_fail_silent",
    "telemetry_success_cannot_alter_primary",
    "primary_failure_preserved",
    "telemetry_exception_never_replaces_primary",
    "report_artifacts_unaffected",
    "source_repository_unaffected",
    "no_telemetry_persistence",
    "no_telemetry_driven_assessment_retry",
    "no_telemetry_driven_cancellation",
    "no_transport_activation_by_default",
    "bounded_lifecycle_events_only",
    "vscode_cursor_integration_not_implemented",
)


class AssessmentIsolationPolicyError(ValueError):
    """Raised when isolation-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryAssessmentIsolationPolicy:
    """Versioned contract: assessment primary result always wins."""

    policy_id: str = COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION
    primary_operation_authoritative: bool = True
    telemetry_side_effects_optional: bool = True
    telemetry_failures_fail_silent: bool = True
    telemetry_success_cannot_alter_primary: bool = True
    primary_failure_preserved: bool = True
    telemetry_exception_never_replaces_primary: bool = True
    report_artifacts_unaffected: bool = True
    source_repository_unaffected: bool = True
    no_telemetry_persistence: bool = True
    no_telemetry_driven_assessment_retry: bool = True
    no_telemetry_driven_cancellation: bool = True
    no_transport_activation_by_default: bool = True
    bounded_lifecycle_events_only: bool = True
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_ID:
            raise AssessmentIsolationPolicyError("unsupported isolation policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION:
            raise AssessmentIsolationPolicyError(
                "unsupported isolation policy version"
            )
        required_true = (
            self.primary_operation_authoritative,
            self.telemetry_side_effects_optional,
            self.telemetry_failures_fail_silent,
            self.telemetry_success_cannot_alter_primary,
            self.primary_failure_preserved,
            self.telemetry_exception_never_replaces_primary,
            self.report_artifacts_unaffected,
            self.source_repository_unaffected,
            self.no_telemetry_persistence,
            self.no_telemetry_driven_assessment_retry,
            self.no_telemetry_driven_cancellation,
            self.no_transport_activation_by_default,
            self.bounded_lifecycle_events_only,
        )
        if not all(required_true):
            raise AssessmentIsolationPolicyError("isolation invariants must remain true")
        if self.review_status != _REVIEW_STATUS:
            raise AssessmentIsolationPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryAssessmentIsolationPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "bounded_lifecycle_events_only": self.bounded_lifecycle_events_only,
            "limitations": list(self.limitations),
            "no_telemetry_driven_assessment_retry": (
                self.no_telemetry_driven_assessment_retry
            ),
            "no_telemetry_driven_cancellation": self.no_telemetry_driven_cancellation,
            "no_telemetry_persistence": self.no_telemetry_persistence,
            "no_transport_activation_by_default": (
                self.no_transport_activation_by_default
            ),
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "primary_failure_preserved": self.primary_failure_preserved,
            "primary_operation_authoritative": self.primary_operation_authoritative,
            "report_artifacts_unaffected": self.report_artifacts_unaffected,
            "review_status": self.review_status,
            "source_repository_unaffected": self.source_repository_unaffected,
            "telemetry_exception_never_replaces_primary": (
                self.telemetry_exception_never_replaces_primary
            ),
            "telemetry_failures_fail_silent": self.telemetry_failures_fail_silent,
            "telemetry_side_effects_optional": self.telemetry_side_effects_optional,
            "telemetry_success_cannot_alter_primary": (
                self.telemetry_success_cannot_alter_primary
            ),
        }


def default_assessment_isolation_policy() -> CommunityTelemetryAssessmentIsolationPolicy:
    return CommunityTelemetryAssessmentIsolationPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_ID",
    "COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_URN",
    "COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION",
    "AssessmentIsolationPolicyError",
    "CommunityTelemetryAssessmentIsolationPolicy",
    "default_assessment_isolation_policy",
]
