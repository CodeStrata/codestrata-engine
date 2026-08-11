"""Privacy-safe projection of runtime telemetry events (Slice 9.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode
from codestrata.telemetry.events import (
    APPROVED_RUNTIME_EVENT_TYPES,
    ArchFamily,
    DurationBucket,
    FailureCategory,
    Lifecycle,
    OperationCategory,
    OsFamily,
    ResultCategory,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.privacy import (
    APPROVED_FIELD_NAMES,
    assert_field_name_allowed,
    looks_like_path_or_secret_value,
)
from codestrata.telemetry.runtime_policy import (
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    CommunityTelemetryRuntimePolicy,
    default_runtime_policy,
)

_ENUM_FIELDS: dict[str, frozenset[str]] = {
    "event_type": APPROVED_RUNTIME_EVENT_TYPES,
    "os_family": frozenset(item.value for item in OsFamily),
    "arch_family": frozenset(item.value for item in ArchFamily),
    "lifecycle": frozenset(item.value for item in Lifecycle),
    "result": frozenset(item.value for item in ResultCategory),
    "duration_bucket": frozenset(item.value for item in DurationBucket),
    "operation_category": frozenset(item.value for item in OperationCategory),
    "failure_category": frozenset(item.value for item in FailureCategory),
}

_BOOL_FIELDS = frozenset({"offline_mode", "ai_used"})
_STRING_FIELDS = frozenset({"client_name", "cli_version"})
_LIST_FIELDS = frozenset({"enabled_assessment_heads"})


@dataclass(frozen=True, slots=True)
class PrivacySafeTelemetryEvent:
    """Allowlisted, deterministic privacy-safe event ready for future transport."""

    fields: dict[str, Any]

    def to_stable_dict(self) -> dict[str, Any]:
        return {key: self.fields[key] for key in sorted(self.fields)}

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def project_runtime_event(
    event: RuntimeTelemetryEvent,
    *,
    policy: CommunityTelemetryRuntimePolicy | None = None,
) -> PrivacySafeTelemetryEvent:
    """Project a typed runtime event into a privacy-safe allowlisted payload."""

    active = policy or default_runtime_policy()
    intake = event.to_intake_dict()
    projected: dict[str, Any] = {
        "runtime_policy_version": active.policy_version,
        "schema_version": PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    }

    for key, value in intake.items():
        assert_field_name_allowed(key)
        projected[key] = _normalize_value(key, value, active)

    if len(projected) > active.max_property_count:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.EVENT_TOO_LARGE)

    encoded = json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(encoded.encode("utf-8")) > active.max_event_size_bytes:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.EVENT_TOO_LARGE)

    # Reject unknown keys if someone mutated intake incorrectly.
    for key in projected:
        if key not in APPROVED_FIELD_NAMES:
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNKNOWN_FIELD)

    return PrivacySafeTelemetryEvent(
        fields={key: projected[key] for key in sorted(projected)}
    )


def project_from_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityTelemetryRuntimePolicy | None = None,
) -> PrivacySafeTelemetryEvent:
    """Project an untrusted dict — reject unknown/forbidden fields strictly."""

    active = policy or default_runtime_policy()
    projected: dict[str, Any] = {
        "runtime_policy_version": active.policy_version,
        "schema_version": PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    }
    for key, value in payload.items():
        assert_field_name_allowed(key)
        if key in {"schema_version", "runtime_policy_version"}:
            continue
        projected[key] = _normalize_value(key, value, active)
    if "event_type" not in projected:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.VALIDATION_FAILED)
    if "client_name" not in projected:
        projected["client_name"] = "codestrata_cli"
    if len(projected) > active.max_property_count:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.EVENT_TOO_LARGE)
    encoded = json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(encoded.encode("utf-8")) > active.max_event_size_bytes:
        raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.EVENT_TOO_LARGE)
    return PrivacySafeTelemetryEvent(
        fields={key: projected[key] for key in sorted(projected)}
    )


def _normalize_value(
    key: str,
    value: Any,
    policy: CommunityTelemetryRuntimePolicy,
) -> Any:
    if key in _ENUM_FIELDS:
        if not isinstance(value, str):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        if value not in _ENUM_FIELDS[key]:
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        return value
    if key in _BOOL_FIELDS:
        if not isinstance(value, bool):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        return value
    if key in _STRING_FIELDS:
        if not isinstance(value, str):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        if len(value) > policy.max_string_length:
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        if looks_like_path_or_secret_value(value):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        if key == "client_name" and value != "codestrata_cli":
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        return value
    if key in _LIST_FIELDS:
        if not isinstance(value, (list, tuple)):
            raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
            if len(item) > policy.max_string_length:
                raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
            if looks_like_path_or_secret_value(item):
                raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNSAFE_VALUE)
            items.append(item)
        return sorted(set(items))
    raise TelemetryRuntimeError(TelemetryRuntimeErrorCode.UNKNOWN_FIELD)


__all__ = [
    "PrivacySafeTelemetryEvent",
    "project_from_mapping",
    "project_runtime_event",
]
