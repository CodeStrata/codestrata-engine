"""Transport error taxonomy and result enrichment (Slice 9.11)."""

from __future__ import annotations

from enum import StrEnum


class TransportFailureCategory(StrEnum):
    """Bounded HTTP/transport failure categories — never include secrets."""

    ACCEPTED = "accepted"
    ALREADY_ACCEPTED = "already_accepted"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    INVALID_CONFIGURATION = "invalid_configuration"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_DENIED = "authorization_denied"
    RATE_LIMITED = "rate_limited"
    VALIDATION_REJECTED = "validation_rejected"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    TIMEOUT = "timeout"
    CONNECTION_FAILED = "connection_failed"
    SERVER_UNAVAILABLE = "server_unavailable"
    REDIRECT_REJECTED = "redirect_rejected"
    INVALID_RESPONSE = "invalid_response"
    PRIVACY_REJECTED = "privacy_rejected"
    INTERNAL_FAILURE = "internal_failure"


class TransportEventIdentityPolicyVersion(StrEnum):
    V1 = "1.0"


COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_ID = (
    "community-telemetry-transport-event-identity-policy"
)
COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_VERSION = "1.0"
COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_URN = (
    f"{COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_ID}:"
    f"{COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_VERSION}"
)


__all__ = [
    "COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_ID",
    "COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_URN",
    "COMMUNITY_TELEMETRY_TRANSPORT_EVENT_IDENTITY_POLICY_VERSION",
    "TransportEventIdentityPolicyVersion",
    "TransportFailureCategory",
]
