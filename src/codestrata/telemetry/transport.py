"""Telemetry transport surfaces.

Legacy Phase 14.3 helpers (``configured_endpoint`` / ``send_payload``) remain for
``TelemetryService`` compatibility. Slice 9.1 adds a narrow runtime transport
port that is independent from HTTP and is unavailable by default.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from codestrata.telemetry.constants import ENDPOINT_ENV
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent

# ---------------------------------------------------------------------------
# Slice 9.1 runtime transport port
# ---------------------------------------------------------------------------


class TelemetryTransportResultKind(StrEnum):
    SENT = "sent"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    FAILED_SILENTLY = "failed_silently"


@dataclass(frozen=True, slots=True)
class TelemetryTransportResult:
    """Bounded transport outcome — never includes payloads, IDs, or credentials."""

    kind: TelemetryTransportResultKind
    sent: bool | None = None
    acknowledged: bool | None = None
    attempt_count: int | None = None
    failure_category: str | None = None
    transport_policy_version: str | None = None
    cloud_schema_version: str | None = None
    privacy_policy_version: str | None = None

    def to_stable_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"kind": self.kind.value}
        if self.sent is not None:
            payload["sent"] = self.sent
        if self.acknowledged is not None:
            payload["acknowledged"] = self.acknowledged
        if self.attempt_count is not None:
            payload["attempt_count"] = self.attempt_count
        if self.failure_category is not None:
            payload["failure_category"] = self.failure_category
        if self.transport_policy_version is not None:
            payload["transport_policy_version"] = self.transport_policy_version
        if self.cloud_schema_version is not None:
            payload["cloud_schema_version"] = self.cloud_schema_version
        if self.privacy_policy_version is not None:
            payload["privacy_policy_version"] = self.privacy_policy_version
        return {key: payload[key] for key in sorted(payload)}


@runtime_checkable
class TelemetryTransport(Protocol):
    """Narrow transport port — privacy-safe events only, no HTTP surface."""

    @property
    def transport_category(self) -> str:
        """Bounded category label for diagnostics (e.g. unavailable, capture)."""

    def send(self, event: PrivacySafeTelemetryEvent) -> TelemetryTransportResult:
        """Attempt to send a privacy-safe event. Must not raise to callers."""


# ---------------------------------------------------------------------------
# Legacy TelemetryService HTTP helpers (compatibility; not Slice 9.1 default)
# ---------------------------------------------------------------------------


def configured_endpoint() -> str | None:
    """Return explicit legacy HTTP endpoint if set.

    Product transmission remains off by default. When operators explicitly set
    ``CODESTRATA_TELEMETRY_ENDPOINT`` for production Community Cloud, use
    ``https://api.codestrata.ai/api/v1/telemetry`` (see
    ``codestrata.community_cloud.production_telemetry_ingest_url``). The raw
    execute-api hostname is not the public authority.
    """

    value = os.environ.get(ENDPOINT_ENV, "").strip()
    return value or None


def send_payload(
    payload: dict[str, Any],
    *,
    endpoint: str | None = None,
    timeout: float = 2.0,
) -> bool:
    """POST JSON payload. Return True on HTTP success; False otherwise."""

    url = endpoint if endpoint is not None else configured_endpoint()
    if not url:
        return False
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "codestrata-telemetry/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return 200 <= int(getattr(response, "status", 200)) < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


__all__ = [
    "TelemetryTransport",
    "TelemetryTransportResult",
    "TelemetryTransportResultKind",
    "configured_endpoint",
    "send_payload",
]
