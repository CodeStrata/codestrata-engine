"""Immutable HTTP transport configuration (Slice 9.11).

No environment reads. Public serialization redacts secrets and endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from codestrata.telemetry.event_identity import (
    EventIdFactory,
    TelemetryTransportCredential,
    generate_transport_event_id,
)
from codestrata.telemetry.transport_policy import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAXIMUM_ATTEMPTS,
    DEFAULT_MAX_ENDPOINT_LENGTH,
    DEFAULT_READ_TIMEOUT_SECONDS,
    CommunityTelemetryTransportPolicy,
    TransportPolicyError,
    default_transport_policy,
)


class TransportConfigurationError(TransportPolicyError):
    """Raised for invalid transport configuration — never echoes secrets."""


@dataclass(frozen=True, slots=True)
class TelemetryTransportConfiguration:
    """Explicit HTTP transport configuration — construction only."""

    endpoint: str
    credential: TelemetryTransportCredential
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    client_version: str = "0.2.0"
    enabled: bool = True
    allow_http_localhost: bool = False
    event_id_factory: EventIdFactory = generate_transport_event_id
    policy: CommunityTelemetryTransportPolicy | None = None

    def __post_init__(self) -> None:
        active_policy = self.policy or default_transport_policy()
        object.__setattr__(self, "policy", active_policy)
        endpoint = self.endpoint.strip()
        if not endpoint or len(endpoint) > DEFAULT_MAX_ENDPOINT_LENGTH:
            raise TransportConfigurationError("invalid endpoint")
        parts = urlsplit(endpoint)
        if parts.username or parts.password or parts.fragment:
            raise TransportConfigurationError("invalid endpoint")
        if parts.query:
            # Reject query credentials / surprise parameters.
            raise TransportConfigurationError("invalid endpoint")
        scheme = (parts.scheme or "").lower()
        host = (parts.hostname or "").lower()
        if scheme == "https":
            pass
        elif (
            scheme == "http"
            and self.allow_http_localhost
            and host in {"localhost", "127.0.0.1", "::1"}
        ):
            pass
        else:
            raise TransportConfigurationError("https required")
        if not parts.path or parts.path == "/":
            raise TransportConfigurationError("endpoint path required")
        if self.connect_timeout_seconds <= 0 or self.read_timeout_seconds <= 0:
            raise TransportConfigurationError("invalid timeout")
        if self.maximum_attempts < 1 or self.maximum_attempts > 2:
            raise TransportConfigurationError("invalid maximum_attempts")
        version = self.client_version.strip()
        if not version or len(version) > 32 or "/" in version or "\\" in version:
            raise TransportConfigurationError("invalid client_version")
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "client_version", version)

    def to_public_dict(self) -> dict[str, Any]:
        """Stable public view — no token, no endpoint URL."""

        assert self.policy is not None
        return {
            "allow_http_localhost": self.allow_http_localhost,
            "client_version": self.client_version,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "enabled": self.enabled,
            "endpoint_configured": True,
            "maximum_attempts": self.maximum_attempts,
            "read_timeout_seconds": self.read_timeout_seconds,
            "scheme": urlsplit(self.endpoint).scheme,
            "transport_policy_version": self.policy.policy_version,
        }


__all__ = [
    "TelemetryTransportConfiguration",
    "TransportConfigurationError",
]
