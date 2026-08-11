"""Bounded diagnostics for privacy-first telemetry preview (Slice 9.9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.preview_models import PrivacyFirstTelemetryPreview


@dataclass(frozen=True, slots=True)
class TelemetryPreviewDiagnostics:
    schema_name: str
    schema_version: str
    event_name: str
    transmission_performed: bool
    transport_status: str
    installation_identity_used: bool
    field_count: int

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "event_name": self.event_name,
            "field_count": self.field_count,
            "installation_identity_used": self.installation_identity_used,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "transmission_performed": self.transmission_performed,
            "transport_status": self.transport_status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_preview(
    preview: PrivacyFirstTelemetryPreview,
) -> TelemetryPreviewDiagnostics:
    return TelemetryPreviewDiagnostics(
        schema_name=preview.schema_name,
        schema_version=preview.schema_version,
        event_name=preview.event_name,
        transmission_performed=preview.transmission_performed,
        transport_status=preview.transport_status,
        installation_identity_used=preview.installation_identity_used,
        field_count=len(preview.event or {}),
    )


__all__ = [
    "TelemetryPreviewDiagnostics",
    "diagnostics_from_preview",
]
