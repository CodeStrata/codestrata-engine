"""Catalog and structural checks for the pre-transport privacy gate."""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_models import TelemetryCatalog
from codestrata.telemetry.catalog_policy import PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION
from codestrata.telemetry.errors import TelemetryRuntimeError, TelemetryRuntimeErrorCode
from codestrata.telemetry.events import APPROVED_RUNTIME_EVENT_TYPES
from codestrata.telemetry.pre_transport_errors import PreTransportReasonCode
from codestrata.telemetry.privacy import APPROVED_FIELD_NAMES, FORBIDDEN_FIELD_NAMES
from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
)


class PreTransportValidationFailure(Exception):
    """Internal gate failure carrying a bounded reason only."""

    def __init__(self, reason: PreTransportReasonCode) -> None:
        super().__init__(reason.value)
        self.reason = reason


def map_runtime_error(exc: TelemetryRuntimeError) -> PreTransportReasonCode:
    mapping = {
        TelemetryRuntimeErrorCode.UNKNOWN_FIELD: PreTransportReasonCode.UNKNOWN_FIELD,
        TelemetryRuntimeErrorCode.UNSAFE_FIELD: PreTransportReasonCode.FORBIDDEN_FIELD_NAME,
        TelemetryRuntimeErrorCode.UNSAFE_VALUE: PreTransportReasonCode.UNSAFE_FIELD_VALUE,
        TelemetryRuntimeErrorCode.EVENT_TOO_LARGE: PreTransportReasonCode.EVENT_TOO_LARGE,
        TelemetryRuntimeErrorCode.VALIDATION_FAILED: (
            PreTransportReasonCode.INVALID_EVENT_COMBINATION
        ),
        TelemetryRuntimeErrorCode.PRIVACY_REJECTED: PreTransportReasonCode.FORBIDDEN_FIELD_NAME,
    }
    return mapping.get(exc.code, PreTransportReasonCode.INTERNAL_PRIVACY_FAILURE)


def assert_field_names_safe(payload: dict[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_FIELD_NAMES:
            raise PreTransportValidationFailure(PreTransportReasonCode.FORBIDDEN_FIELD_NAME)
        if key not in APPROVED_FIELD_NAMES:
            raise PreTransportValidationFailure(PreTransportReasonCode.UNKNOWN_FIELD)


def assert_versions(
    payload: dict[str, Any],
    *,
    required_schema: str,
    required_policy: str,
) -> None:
    schema = payload.get("schema_version")
    policy = payload.get("runtime_policy_version")
    if schema != required_schema:
        raise PreTransportValidationFailure(PreTransportReasonCode.UNSUPPORTED_EVENT_SCHEMA)
    if policy != required_policy:
        raise PreTransportValidationFailure(PreTransportReasonCode.UNSUPPORTED_RUNTIME_POLICY)


def assert_client_and_event_type(payload: dict[str, Any]) -> str:
    client = payload.get("client_name")
    event_type = payload.get("event_type")
    if client != "codestrata_cli":
        raise PreTransportValidationFailure(PreTransportReasonCode.UNSAFE_FIELD_VALUE)
    if not isinstance(event_type, str) or event_type not in APPROVED_RUNTIME_EVENT_TYPES:
        raise PreTransportValidationFailure(PreTransportReasonCode.INVALID_EVENT_TYPE)
    return event_type


def reconcile_payload_with_catalog(
    payload: dict[str, Any],
    *,
    catalog: TelemetryCatalog | None = None,
) -> str:
    active = catalog or build_privacy_first_telemetry_catalog()
    if active.schema_version != PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION:
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)
    if active.runtime_event_schema_version != PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION:
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)
    if active.runtime_policy_version != COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION:
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)
    if active.client_name != "codestrata_cli":
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)

    event_type = payload.get("event_type")
    event_by_name = {item.name: item for item in active.events}
    if event_type not in event_by_name:
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_EVENT_MISSING)

    catalog_event = event_by_name[str(event_type)]
    catalog_fields = {field.name for field in active.shared_fields}
    payload_fields = set(payload)
    if not payload_fields.issubset(catalog_fields):
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_FIELD_MISSING)
    required = set(catalog_event.required_fields)
    if not required.issubset(payload_fields):
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)
    optional = set(catalog_event.optional_fields)
    if not (payload_fields - required).issubset(optional):
        # Present non-required fields must be cataloged as optional for this event.
        raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_MISMATCH)

    enum_map = {
        enum.name: {value.value for value in enum.values} for enum in active.enums
    }
    field_enum = {
        field.name: field.enum_ref
        for field in active.shared_fields
        if field.enum_ref is not None
    }
    for key, value in payload.items():
        enum_ref = field_enum.get(key)
        if enum_ref is None:
            continue
        if not isinstance(value, str) or value not in enum_map[enum_ref]:
            raise PreTransportValidationFailure(PreTransportReasonCode.CATALOG_ENUM_MISMATCH)

    return PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION


__all__ = [
    "PreTransportValidationFailure",
    "assert_client_and_event_type",
    "assert_field_names_safe",
    "assert_versions",
    "map_runtime_error",
    "reconcile_payload_with_catalog",
]
