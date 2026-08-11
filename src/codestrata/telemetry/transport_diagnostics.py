"""Safe HTTP transport diagnostics (Slice 9.11) — never includes secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from codestrata.telemetry.transport_policy import (
    COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION,
    COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION,
)


@dataclass
class TelemetryTransportDiagnostics:
    """Mutable process-local counters for an HTTP transport instance."""

    transport_policy_version: str = COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION
    transport_type: str = "http"
    configured: bool = True
    cloud_schema_version: str = COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION
    attempts: int = 0
    accepted_count: int = 0
    already_accepted_count: int = 0
    unavailable_count: int = 0
    rejected_count: int = 0
    timeout_count: int = 0
    last_transport_category: str | None = None
    limitation_codes: tuple[str, ...] = field(
        default_factory=lambda: (
            "no_payload_logging",
            "no_credential_logging",
            "installation_id_omitted",
            "event_id_request_envelope_only",
        )
    )

    def record(self, category: str, *, attempts: int = 1) -> None:
        self.attempts += max(1, attempts)
        self.last_transport_category = category
        if category == "accepted":
            self.accepted_count += 1
        elif category == "already_accepted":
            self.already_accepted_count += 1
        elif category in {"unavailable", "disabled", "connection_failed", "server_unavailable"}:
            self.unavailable_count += 1
        elif category == "timeout":
            self.timeout_count += 1
        else:
            self.rejected_count += 1

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "accepted_count": self.accepted_count,
            "already_accepted_count": self.already_accepted_count,
            "attempts": self.attempts,
            "cloud_schema_version": self.cloud_schema_version,
            "configured": self.configured,
            "last_transport_category": self.last_transport_category,
            "limitation_codes": list(sorted(self.limitation_codes)),
            "rejected_count": self.rejected_count,
            "timeout_count": self.timeout_count,
            "transport_policy_version": self.transport_policy_version,
            "transport_type": self.transport_type,
            "unavailable_count": self.unavailable_count,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


__all__ = ["TelemetryTransportDiagnostics"]
