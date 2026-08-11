"""Immutable privacy-first telemetry preview reporting model (Slice 9.9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.preview_policy import (
    PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME,
    PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION,
)


class PreviewType(StrEnum):
    ILLUSTRATIVE = "illustrative"


class PreviewTransportStatus(StrEnum):
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PrivacyFirstTelemetryPreview:
    """CLI transparency wrapper around a privacy-safe projected event."""

    schema_name: str = PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_NAME
    schema_version: str = PRIVACY_FIRST_TELEMETRY_PREVIEW_SCHEMA_VERSION
    preview_type: str = PreviewType.ILLUSTRATIVE.value
    event_name: str = "feature_invoked"
    event_usage_status: str = "emitted_by_current_runtime"
    event_schema_version: str = "1.0"
    runtime_policy_version: str = "1.0"
    preview_policy_version: str = "1.0"
    catalog_schema_version: str = "1.0.0"
    catalog_id: str = "codestrata-privacy-first-telemetry-catalog"
    transmission_performed: bool = False
    transport_status: str = PreviewTransportStatus.UNAVAILABLE.value
    consent_required_for_transmission: bool = True
    consent_scope: str = "session"
    consent_persisted: bool = False
    installation_identity_used: bool = False
    privacy_filter_required: bool = True
    event: dict[str, Any] | None = None
    omitted_optional_fields: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        event_payload = dict(self.event or {})
        object.__setattr__(
            self,
            "event",
            {key: event_payload[key] for key in sorted(event_payload)},
        )
        object.__setattr__(
            self,
            "omitted_optional_fields",
            tuple(sorted(set(self.omitted_optional_fields))),
        )
        object.__setattr__(
            self, "limitations", tuple(sorted(set(self.limitations)))
        )

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_schema_version": self.catalog_schema_version,
            "consent_persisted": self.consent_persisted,
            "consent_required_for_transmission": self.consent_required_for_transmission,
            "consent_scope": self.consent_scope,
            "event": dict(self.event or {}),
            "event_name": self.event_name,
            "event_schema_version": self.event_schema_version,
            "event_usage_status": self.event_usage_status,
            "installation_identity_used": self.installation_identity_used,
            "limitations": list(self.limitations),
            "omitted_optional_fields": list(self.omitted_optional_fields),
            "preview_policy_version": self.preview_policy_version,
            "preview_type": self.preview_type,
            "privacy_filter_required": self.privacy_filter_required,
            "runtime_policy_version": self.runtime_policy_version,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "transmission_performed": self.transmission_performed,
            "transport_status": self.transport_status,
        }

    def to_stable_json(self, *, indent: int | None = 2) -> str:
        text = json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
        )
        if indent is not None and not text.endswith("\n"):
            text += "\n"
        return text


__all__ = [
    "PreviewTransportStatus",
    "PreviewType",
    "PrivacyFirstTelemetryPreview",
]
