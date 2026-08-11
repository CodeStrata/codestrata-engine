"""Independent privacy-first telemetry transport policy (Slice 9.11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMMUNITY_TELEMETRY_TRANSPORT_POLICY_ID = "community-telemetry-transport-policy"
COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_TRANSPORT_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_TRANSPORT_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION}"
)

COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION = "1.0"

DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0
DEFAULT_READ_TIMEOUT_SECONDS = 5.0
DEFAULT_MAXIMUM_ATTEMPTS = 1
DEFAULT_MAX_ENDPOINT_LENGTH = 512
DEFAULT_MAX_BODY_BYTES = 8192

_REVIEW_STATUS = "explicit_http_transport_unavailable_by_default"

_LIMITATIONS: tuple[str, ...] = (
    "transport_disabled_by_default",
    "explicit_construction_required",
    "explicit_session_allow_required",
    "pre_transport_gate_required",
    "https_required_for_production",
    "bearer_authentication_required",
    "no_persistent_retry_queue",
    "no_filesystem_fallback",
    "no_background_thread",
    "no_batching",
    "no_redirect_following",
    "maximum_attempts_one_by_default",
    "no_payload_logging",
    "no_credential_logging",
    "installation_id_omitted",
    "event_id_request_envelope_only",
    "engine_preview_is_not_http_body",
    "cloud_mapping_independently_versioned",
    "fail_silent_runtime_behavior",
)


class TransportPolicyError(ValueError):
    """Raised when transport-policy invariants fail."""


@dataclass(frozen=True, slots=True)
class CommunityTelemetryTransportPolicy:
    """Versioned fail-silent HTTP transport product-policy contract."""

    policy_id: str = COMMUNITY_TELEMETRY_TRANSPORT_POLICY_ID
    policy_version: str = COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION
    cloud_schema_version: str = COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION
    transport_disabled_by_default: bool = True
    explicit_construction_required: bool = True
    pre_transport_gate_required: bool = True
    https_required_for_production: bool = True
    bearer_authentication_required: bool = True
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    follow_redirects: bool = False
    use_environment_proxy: bool = False
    persistent_retry_queue: bool = False
    filesystem_fallback: bool = False
    background_thread: bool = False
    batching: bool = False
    payload_logging: bool = False
    credential_logging: bool = False
    installation_id_allowed: bool = False
    review_status: str = _REVIEW_STATUS
    limitations: tuple[str, ...] = _LIMITATIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))
        self.validate()

    @property
    def policy_token(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def validate(self) -> None:
        if self.policy_id != COMMUNITY_TELEMETRY_TRANSPORT_POLICY_ID:
            raise TransportPolicyError("unsupported transport policy id")
        if self.policy_version != COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION:
            raise TransportPolicyError("unsupported transport policy version")
        if self.cloud_schema_version != COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION:
            raise TransportPolicyError("unsupported cloud schema version")
        if not self.transport_disabled_by_default:
            raise TransportPolicyError("transport_disabled_by_default must be true")
        if not self.explicit_construction_required:
            raise TransportPolicyError("explicit_construction_required must be true")
        if not self.pre_transport_gate_required:
            raise TransportPolicyError("pre_transport_gate_required must be true")
        if not self.https_required_for_production:
            raise TransportPolicyError("https_required_for_production must be true")
        if not self.bearer_authentication_required:
            raise TransportPolicyError("bearer_authentication_required must be true")
        if self.follow_redirects:
            raise TransportPolicyError("follow_redirects must be false")
        if self.use_environment_proxy:
            raise TransportPolicyError("use_environment_proxy must be false")
        if self.persistent_retry_queue or self.filesystem_fallback:
            raise TransportPolicyError("persistence must be false")
        if self.background_thread or self.batching:
            raise TransportPolicyError("background/batching must be false")
        if self.payload_logging or self.credential_logging:
            raise TransportPolicyError("logging of secrets/payloads must be false")
        if self.installation_id_allowed:
            raise TransportPolicyError("installation_id_allowed must be false")
        if self.maximum_attempts < 1 or self.maximum_attempts > 2:
            raise TransportPolicyError("maximum_attempts must be 1 or 2")
        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise TransportPolicyError("timeouts must be positive")
        if self.review_status != _REVIEW_STATUS:
            raise TransportPolicyError("unsupported review_status")

    @classmethod
    def default(cls) -> CommunityTelemetryTransportPolicy:
        return cls()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "batching": self.batching,
            "bearer_authentication_required": self.bearer_authentication_required,
            "cloud_schema_version": self.cloud_schema_version,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "credential_logging": self.credential_logging,
            "explicit_construction_required": self.explicit_construction_required,
            "filesystem_fallback": self.filesystem_fallback,
            "follow_redirects": self.follow_redirects,
            "https_required_for_production": self.https_required_for_production,
            "installation_id_allowed": self.installation_id_allowed,
            "limitations": list(self.limitations),
            "maximum_attempts": self.maximum_attempts,
            "payload_logging": self.payload_logging,
            "persistent_retry_queue": self.persistent_retry_queue,
            "policy_id": self.policy_id,
            "policy_token": self.policy_token,
            "policy_version": self.policy_version,
            "pre_transport_gate_required": self.pre_transport_gate_required,
            "read_timeout_seconds": self.read_timeout_seconds,
            "review_status": self.review_status,
            "transport_disabled_by_default": self.transport_disabled_by_default,
            "use_environment_proxy": self.use_environment_proxy,
        }


def default_transport_policy() -> CommunityTelemetryTransportPolicy:
    return CommunityTelemetryTransportPolicy.default()


__all__ = [
    "COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION",
    "COMMUNITY_TELEMETRY_TRANSPORT_POLICY_ID",
    "COMMUNITY_TELEMETRY_TRANSPORT_POLICY_URN",
    "COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION",
    "CommunityTelemetryTransportPolicy",
    "DEFAULT_CONNECT_TIMEOUT_SECONDS",
    "DEFAULT_MAXIMUM_ATTEMPTS",
    "DEFAULT_MAX_BODY_BYTES",
    "DEFAULT_MAX_ENDPOINT_LENGTH",
    "DEFAULT_READ_TIMEOUT_SECONDS",
    "TransportPolicyError",
    "default_transport_policy",
]
