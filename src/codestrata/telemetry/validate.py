"""Telemetry payload construction and privacy validation."""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from codestrata.package_metadata import get_package_version
from codestrata.telemetry.constants import (
    ALLOWED_PAYLOAD_KEYS,
    FORBIDDEN_SUBSTRINGS,
    SCHEMA_VERSION,
    EventName,
)


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def base_fields(*, installation_id: str, event: EventName | str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event": str(event),
        "installation_id": installation_id,
        "codestrata_version": get_package_version(),
        "os": platform.system(),
        "python_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "timestamp": utc_timestamp(),
    }


def build_event_payload(
    *,
    installation_id: str,
    event: EventName | str,
    command: str | None = None,
    enabled_assessment_domains: list[str] | None = None,
    language_categories: list[str] | None = None,
    repository_size_band: str | None = None,
    duration_band: str | None = None,
    ai_enabled: bool | None = None,
    success: bool | None = None,
    previous_version: str | None = None,
    queue_depth: int | None = None,
) -> dict[str, Any]:
    payload = base_fields(installation_id=installation_id, event=event)
    optional: dict[str, Any] = {
        "command": command,
        "enabled_assessment_domains": enabled_assessment_domains,
        "language_categories": language_categories,
        "repository_size_band": repository_size_band,
        "duration_band": duration_band,
        "ai_enabled": ai_enabled,
        "success": success,
        "previous_version": previous_version,
        "queue_depth": queue_depth,
    }
    for key, value in optional.items():
        if value is not None:
            payload[key] = value
    validate_payload(payload)
    return payload


def validate_payload(payload: Mapping[str, Any]) -> None:
    """Raise ValueError when payload violates privacy / schema rules."""

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    event = payload.get("event")
    if event not in {item.value for item in EventName}:
        raise ValueError(f"unknown event: {event!r}")
    for key in payload:
        if key not in ALLOWED_PAYLOAD_KEYS:
            raise ValueError(f"disallowed payload key: {key}")
        lowered = key.lower()
        for needle in FORBIDDEN_SUBSTRINGS:
            if needle in lowered and key not in ALLOWED_PAYLOAD_KEYS:
                raise ValueError(f"forbidden key pattern: {key}")
    # Nested structures must only be lists of short category tokens.
    for list_key in ("enabled_assessment_domains", "language_categories"):
        value = payload.get(list_key)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError(f"{list_key} must be a list")
        for item in value:
            if not isinstance(item, str) or not item or "/" in item or "\\" in item:
                raise ValueError(f"invalid {list_key} entry")
            if any(ch in item for ch in (".", " ", "@")):
                raise ValueError(f"invalid {list_key} entry")
    # Never allow long free-text that could leak content.
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 128 and key != "timestamp":
            raise ValueError(f"value too long for key {key}")


def redact_for_display(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable copy (already privacy-safe by construction)."""

    validate_payload(payload)
    return cast(dict[str, Any], json.loads(json.dumps(payload, sort_keys=True)))
