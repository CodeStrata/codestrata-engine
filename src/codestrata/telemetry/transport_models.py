"""Engine-owned Community Cloud telemetry wire DTO (Slice 9.11).

Matches the independently versioned public Community Cloud telemetry schema 1.0
without importing Platform models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.event_identity import validate_transport_event_id
from codestrata.telemetry.transport_policy import COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION

CLOUD_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "application_started",
        "application_completed",
        "feature_invoked",
        "feature_completed",
        "operation_failed",
    }
)
CLOUD_OUTCOMES: frozenset[str] = frozenset(
    {"succeeded", "failed", "cancelled", "unavailable"}
)
CLOUD_DURATION_BUCKETS: frozenset[str] = frozenset(
    {
        "under_1s",
        "1s_to_5s",
        "5s_to_30s",
        "30s_to_2m",
        "over_2m",
        "unavailable",
    }
)
CLOUD_PROPERTY_KEYS: frozenset[str] = frozenset(
    {"feature", "operation", "outcome", "duration_bucket", "count", "flags"}
)
MAX_FLAGS = 8
ENGINE_CLOUD_WIRE_MAPPING_CONTRACT_VERSION = "1.0"


class CloudWireValidationError(ValueError):
    """Raised for invalid wire payloads — never echoes secrets."""


@dataclass(frozen=True, slots=True)
class CommunityCloudTelemetryWireRequest:
    """Strict cloud request envelope — occurred_at omitted; installation_id optional."""

    event_id: str
    event_type: str
    client_name: str
    client_version: str
    client_platform: str
    properties: dict[str, Any] | None = None
    installation_id: str | None = None
    schema_version: str = COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        event_id = validate_transport_event_id(self.event_id)
        if self.schema_version != COMMUNITY_CLOUD_TELEMETRY_SCHEMA_VERSION:
            raise CloudWireValidationError("unsupported schema_version")
        if self.event_type not in CLOUD_EVENT_TYPES:
            raise CloudWireValidationError("unsupported event_type")
        if self.client_name != "codestrata_cli":
            raise CloudWireValidationError("unsupported client_name")
        version = self.client_version.strip()
        platform = self.client_platform.strip()
        if not version or len(version) > 32:
            raise CloudWireValidationError("invalid client_version")
        if not platform or len(platform) > 64 or "/" in platform or "\\" in platform:
            raise CloudWireValidationError("invalid client_platform")
        iid = self.installation_id
        if iid is not None:
            text = str(iid).strip()
            if not text or len(text) > 64:
                raise CloudWireValidationError("invalid installation_id")
            # UUID v4 shape only — never path/email shaped identities.
            if "/" in text or "\\" in text or "@" in text or " " in text:
                raise CloudWireValidationError("invalid installation_id")
            object.__setattr__(self, "installation_id", text)
        props = self.properties
        if props is not None:
            if not isinstance(props, dict):
                raise CloudWireValidationError("invalid properties")
            if not set(props).issubset(CLOUD_PROPERTY_KEYS):
                raise CloudWireValidationError("unknown property")
            cleaned = _normalize_properties(props)
            object.__setattr__(self, "properties", cleaned if cleaned else None)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "client_version", version)
        object.__setattr__(self, "client_platform", platform)

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "client": {
                "name": self.client_name,
                "platform": self.client_platform,
                "version": self.client_version,
            },
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
        }
        if self.installation_id:
            payload["installation_id"] = self.installation_id
        if self.properties:
            payload["properties"] = {
                key: self.properties[key] for key in sorted(self.properties)
            }
        return {key: payload[key] for key in sorted(payload)}

    def to_canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")


def _normalize_properties(props: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in props.items():
        if value is None:
            continue
        if key in {"feature", "operation"}:
            if not isinstance(value, str) or not value or len(value) > 64:
                raise CloudWireValidationError("invalid property")
            cleaned[key] = value
        elif key == "outcome":
            if value not in CLOUD_OUTCOMES:
                raise CloudWireValidationError("invalid outcome")
            cleaned[key] = value
        elif key == "duration_bucket":
            if value not in CLOUD_DURATION_BUCKETS:
                raise CloudWireValidationError("invalid duration_bucket")
            cleaned[key] = value
        elif key == "count":
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 10_000:
                raise CloudWireValidationError("invalid count")
            cleaned[key] = value
        elif key == "flags":
            if not isinstance(value, (list, tuple)):
                raise CloudWireValidationError("invalid flags")
            flags = sorted({str(item) for item in value if item})
            if len(flags) > MAX_FLAGS:
                raise CloudWireValidationError("too many flags")
            for item in flags:
                if len(item) > 32 or "/" in item or "\\" in item:
                    raise CloudWireValidationError("invalid flag")
            cleaned[key] = flags
        else:
            raise CloudWireValidationError("unknown property")
    return cleaned


__all__ = [
    "CLOUD_DURATION_BUCKETS",
    "CLOUD_EVENT_TYPES",
    "CLOUD_OUTCOMES",
    "CLOUD_PROPERTY_KEYS",
    "CloudWireValidationError",
    "CommunityCloudTelemetryWireRequest",
    "ENGINE_CLOUD_WIRE_MAPPING_CONTRACT_VERSION",
]
