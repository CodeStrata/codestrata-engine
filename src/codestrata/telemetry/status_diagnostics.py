"""Bounded diagnostics helpers for privacy-first telemetry status (Slice 9.7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.status_models import PrivacyFirstTelemetryStatus


@dataclass(frozen=True, slots=True)
class TelemetryStatusDiagnostics:
    """Safe status diagnostics — no paths, IDs, endpoints, or env values."""

    schema_name: str
    schema_version: str
    runtime_state: str
    transmission_available: bool
    installation_identity_used: bool
    status_side_effect_free: bool
    legacy_preference_authorizes_runtime: bool
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "installation_identity_used": self.installation_identity_used,
            "legacy_preference_authorizes_runtime": (
                self.legacy_preference_authorizes_runtime
            ),
            "limitation_codes": list(self.limitation_codes),
            "runtime_state": self.runtime_state,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "status_side_effect_free": self.status_side_effect_free,
            "transmission_available": self.transmission_available,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_status(
    status: PrivacyFirstTelemetryStatus,
) -> TelemetryStatusDiagnostics:
    return TelemetryStatusDiagnostics(
        schema_name=status.schema_name,
        schema_version=status.schema_version,
        runtime_state=status.runtime_state,
        transmission_available=status.transmission_available,
        installation_identity_used=status.installation_identity_used,
        status_side_effect_free=status.status_side_effect_free,
        legacy_preference_authorizes_runtime=status.legacy_preference_authorizes_runtime,
        limitation_codes=status.limitation_codes,
    )


__all__ = [
    "TelemetryStatusDiagnostics",
    "diagnostics_from_status",
]
