"""Versioned Engine opt-in / no-egress collection policy (E13.1).

Durable local consent is required before any Engine adapter may transmit
telemetry. Evidence and graph *live* upload stay unavailable unless an E13.2
collector advertises a supported schema and receipts. Absence of consent still
means no egress. Environment variables and CI markers never invent consent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ENGINE_OPT_IN_POLICY_ID = "engine-collection-opt-in-policy"
ENGINE_OPT_IN_POLICY_VERSION = "1.0"
ENGINE_OPT_IN_POLICY_URN = f"{ENGINE_OPT_IN_POLICY_ID}:{ENGINE_OPT_IN_POLICY_VERSION}"

_REVIEW_STATUS = "durable_opt_in_no_egress_default"

_LIMITATIONS: tuple[str, ...] = (
    "default_no_egress",
    "explicit_opt_in_required",
    "ci_never_invents_consent",
    "environment_cannot_invent_consent",
    "per_run_deny_does_not_persist",
    "disable_cancels_pending",
    "disable_survives_restart",
    "upload_failure_cannot_fail_analysis",
    "evidence_graph_upload_unavailable",
    "no_community_api_edits",
    "scoped_export_is_separate_from_telemetry_wire",
)


class OptInPolicyError(ValueError):
    """Raised when the E13.1 opt-in policy invariants fail."""


@dataclass(frozen=True, slots=True)
class EngineCollectionOptInPolicy:
    """Deterministic no-egress default with durable local opt-in."""

    policy_id: str = ENGINE_OPT_IN_POLICY_ID
    policy_version: str = ENGINE_OPT_IN_POLICY_VERSION
    disabled_by_default: bool = True
    durable_preference_allowed: bool = True
    environment_can_invent_consent: bool = False
    ci_can_invent_consent: bool = False
    per_run_deny_persists: bool = False
    disable_cancels_pending: bool = True
    evidence_transmission_available: bool = False
    graph_transmission_available: bool = False
    telemetry_requires_explicit_consent: bool = True
    fail_silent: bool = True
    upload_failure_cannot_fail_analysis: bool = True
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != ENGINE_OPT_IN_POLICY_ID:
            raise OptInPolicyError("unsupported opt-in policy id")
        if self.policy_version != ENGINE_OPT_IN_POLICY_VERSION:
            raise OptInPolicyError("unsupported opt-in policy version")
        if not self.disabled_by_default:
            raise OptInPolicyError("disabled_by_default must be true")
        if not self.durable_preference_allowed:
            raise OptInPolicyError("durable_preference_allowed must be true")
        if self.environment_can_invent_consent:
            raise OptInPolicyError("environment_can_invent_consent must be false")
        if self.ci_can_invent_consent:
            raise OptInPolicyError("ci_can_invent_consent must be false")
        if self.per_run_deny_persists:
            raise OptInPolicyError("per_run_deny_persists must be false")
        if not self.disable_cancels_pending:
            raise OptInPolicyError("disable_cancels_pending must be true")
        if self.evidence_transmission_available:
            raise OptInPolicyError("evidence_transmission_available must be false")
        if self.graph_transmission_available:
            raise OptInPolicyError("graph_transmission_available must be false")
        if not self.telemetry_requires_explicit_consent:
            raise OptInPolicyError("telemetry_requires_explicit_consent must be true")
        if not self.fail_silent:
            raise OptInPolicyError("fail_silent must be true")
        if not self.upload_failure_cannot_fail_analysis:
            raise OptInPolicyError("upload_failure_cannot_fail_analysis must be true")
        if self.review_status != _REVIEW_STATUS:
            raise OptInPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> EngineCollectionOptInPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        payload = {
            "ci_can_invent_consent": self.ci_can_invent_consent,
            "disable_cancels_pending": self.disable_cancels_pending,
            "disabled_by_default": self.disabled_by_default,
            "durable_preference_allowed": self.durable_preference_allowed,
            "environment_can_invent_consent": self.environment_can_invent_consent,
            "evidence_transmission_available": self.evidence_transmission_available,
            "fail_silent": self.fail_silent,
            "graph_transmission_available": self.graph_transmission_available,
            "limitations": list(self.limitations),
            "per_run_deny_persists": self.per_run_deny_persists,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "review_status": self.review_status,
            "telemetry_requires_explicit_consent": self.telemetry_requires_explicit_consent,
            "upload_failure_cannot_fail_analysis": self.upload_failure_cannot_fail_analysis,
        }
        return {key: payload[key] for key in sorted(payload)}


def default_opt_in_policy() -> EngineCollectionOptInPolicy:
    return EngineCollectionOptInPolicy.default()


__all__ = [
    "ENGINE_OPT_IN_POLICY_ID",
    "ENGINE_OPT_IN_POLICY_URN",
    "ENGINE_OPT_IN_POLICY_VERSION",
    "EngineCollectionOptInPolicy",
    "OptInPolicyError",
    "default_opt_in_policy",
]
