"""Transport credentials and event identity (Slice 9.11).

Credentials and event IDs stay in process memory only — never logged or
serialized into diagnostics/preview/status/catalog.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

# Align with Community Cloud client credential shape (prefix + opaque body).
_CREDENTIAL_RE = re.compile(r"^cscc_v1_[A-Za-z0-9_-]{16,120}$")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class TransportCredentialError(ValueError):
    """Raised for invalid credential shape — never echoes the token."""


class TransportEventIdentityError(ValueError):
    """Raised for invalid event-id shape — never echoes contents."""


@dataclass(frozen=True, slots=True)
class TelemetryTransportCredential:
    """Bearer token held only in memory — never serialize."""

    bearer_token: str

    def __post_init__(self) -> None:
        token = self.bearer_token.strip()
        if not _CREDENTIAL_RE.fullmatch(token):
            raise TransportCredentialError("invalid credential format")
        # Community Cloud policy bounds total credential length (24–128).
        if len(token) < 24 or len(token) > 128:
            raise TransportCredentialError("invalid credential format")
        object.__setattr__(self, "bearer_token", token)

    def authorization_header_value(self) -> str:
        return f"Bearer {self.bearer_token}"

    def __repr__(self) -> str:
        return "TelemetryTransportCredential(redacted)"

    def __str__(self) -> str:
        return "TelemetryTransportCredential(redacted)"


EventIdFactory = Callable[[], str]


def generate_transport_event_id() -> str:
    """Opaque random UUID for the cloud request envelope only."""

    return str(uuid.uuid4())


def validate_transport_event_id(event_id: str) -> str:
    text = event_id.strip()
    if not _EVENT_ID_RE.fullmatch(text):
        raise TransportEventIdentityError("invalid event id format")
    return text


__all__ = [
    "EventIdFactory",
    "TelemetryTransportCredential",
    "TransportCredentialError",
    "TransportEventIdentityError",
    "generate_transport_event_id",
    "validate_transport_event_id",
]
