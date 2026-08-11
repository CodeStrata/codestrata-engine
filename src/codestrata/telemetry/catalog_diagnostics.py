"""Bounded diagnostics for the public telemetry catalog (Slice 9.8)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.catalog_models import TelemetryCatalog


@dataclass(frozen=True, slots=True)
class TelemetryCatalogDiagnostics:
    schema_name: str
    schema_version: str
    event_count: int
    field_count: int
    enum_count: int
    transmission_status: str
    installation_identity_status: str
    client_name: str

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "client_name": self.client_name,
            "enum_count": self.enum_count,
            "event_count": self.event_count,
            "field_count": self.field_count,
            "installation_identity_status": self.installation_identity_status,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "transmission_status": self.transmission_status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_catalog(catalog: TelemetryCatalog) -> TelemetryCatalogDiagnostics:
    return TelemetryCatalogDiagnostics(
        schema_name=catalog.schema_name,
        schema_version=catalog.schema_version,
        event_count=len(catalog.events),
        field_count=len(catalog.shared_fields),
        enum_count=len(catalog.enums),
        transmission_status=catalog.transmission_status,
        installation_identity_status=catalog.installation_identity_status,
        client_name=catalog.client_name,
    )


__all__ = [
    "TelemetryCatalogDiagnostics",
    "diagnostics_from_catalog",
]
