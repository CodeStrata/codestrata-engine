"""Independent pre-transport privacy policy (Slice 9.10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
    DEFAULT_MAX_EVENT_SIZE_BYTES,
    DEFAULT_MAX_PROPERTY_COUNT,
    DEFAULT_MAX_STRING_LENGTH,
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
)

COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_ID = (
    "community-telemetry-pre-transport-privacy-policy"
)
COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION}"
)

_REVIEW_STATUS = "pre_transport_gate_no_transmission"

_LIMITATIONS: tuple[str, ...] = (
    "only_privacy_safe_event_accepted",
    "schema_version_required",
    "runtime_policy_version_required",
    "catalog_reconciliation_required",
    "unknown_fields_rejected",
    "forbidden_fields_rejected",
    "unsafe_values_rejected",
    "no_raw_value_echo",
    "fail_silent_runtime_integration",
    "transport_unavailable_by_default",
    "no_http_transport_in_slice_9_10",
    "consent_cannot_bypass_gate",
)


class PreTransportPolicyError(ValueError):
    """Raised when pre-transport privacy-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryPreTransportPrivacyPolicy:
    """Versioned final privacy gate contract before the transport port."""

    policy_id: str = COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION
    only_privacy_safe_event_accepted: bool = True
    required_event_schema_version: str = PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION
    required_runtime_policy_version: str = COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION
    catalog_reconciliation_required: bool = True
    unknown_fields_rejected: bool = True
    forbidden_fields_rejected: bool = True
    unsafe_values_rejected: bool = True
    max_event_size_bytes: int = DEFAULT_MAX_EVENT_SIZE_BYTES
    max_property_count: int = DEFAULT_MAX_PROPERTY_COUNT
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH
    fail_silent_runtime_integration: bool = True
    no_raw_value_echo: bool = True
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_ID:
            raise PreTransportPolicyError("unsupported pre-transport policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION:
            raise PreTransportPolicyError("unsupported pre-transport policy version")
        if not self.only_privacy_safe_event_accepted:
            raise PreTransportPolicyError("only_privacy_safe_event_accepted must be true")
        if self.required_event_schema_version != PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION:
            raise PreTransportPolicyError("required event schema must remain 1.0")
        if self.required_runtime_policy_version != COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION:
            raise PreTransportPolicyError("required runtime policy must remain 1.0")
        if not self.catalog_reconciliation_required:
            raise PreTransportPolicyError("catalog_reconciliation_required must be true")
        if not self.unknown_fields_rejected:
            raise PreTransportPolicyError("unknown_fields_rejected must be true")
        if not self.forbidden_fields_rejected:
            raise PreTransportPolicyError("forbidden_fields_rejected must be true")
        if not self.unsafe_values_rejected:
            raise PreTransportPolicyError("unsafe_values_rejected must be true")
        if not self.fail_silent_runtime_integration:
            raise PreTransportPolicyError("fail_silent_runtime_integration must be true")
        if not self.no_raw_value_echo:
            raise PreTransportPolicyError("no_raw_value_echo must be true")
        if self.max_event_size_bytes <= 0 or self.max_property_count <= 0:
            raise PreTransportPolicyError("limits must be positive")
        if self.max_string_length <= 0:
            raise PreTransportPolicyError("max_string_length must be positive")
        if self.review_status != _REVIEW_STATUS:
            raise PreTransportPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryPreTransportPrivacyPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "catalog_reconciliation_required": self.catalog_reconciliation_required,
            "fail_silent_runtime_integration": self.fail_silent_runtime_integration,
            "forbidden_fields_rejected": self.forbidden_fields_rejected,
            "limitations": list(self.limitations),
            "max_event_size_bytes": self.max_event_size_bytes,
            "max_property_count": self.max_property_count,
            "max_string_length": self.max_string_length,
            "no_raw_value_echo": self.no_raw_value_echo,
            "only_privacy_safe_event_accepted": self.only_privacy_safe_event_accepted,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "required_event_schema_version": self.required_event_schema_version,
            "required_runtime_policy_version": self.required_runtime_policy_version,
            "review_status": self.review_status,
            "unknown_fields_rejected": self.unknown_fields_rejected,
            "unsafe_values_rejected": self.unsafe_values_rejected,
        }


def default_pre_transport_policy() -> CommunityTelemetryPreTransportPrivacyPolicy:
    return CommunityTelemetryPreTransportPrivacyPolicy.default()


__all__ = [
    "COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_ID",
    "COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_URN",
    "COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION",
    "CommunityTelemetryPreTransportPrivacyPolicy",
    "PreTransportPolicyError",
    "default_pre_transport_policy",
]
