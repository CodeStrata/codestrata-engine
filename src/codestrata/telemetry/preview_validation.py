"""Catalog reconciliation for privacy-first CLI preview (Slice 9.9)."""

from __future__ import annotations

from codestrata.telemetry.catalog_models import TelemetryCatalog
from codestrata.telemetry.catalog_policy import (
    PRIVACY_FIRST_TELEMETRY_CATALOG_ID,
    PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION,
)
from codestrata.telemetry.privacy import APPROVED_FIELD_NAMES, FORBIDDEN_FIELD_NAMES
from codestrata.telemetry.preview_models import PrivacyFirstTelemetryPreview
from codestrata.telemetry.preview_policy import PreviewPolicyError
from codestrata.telemetry.runtime_policy import PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION


class PreviewReconciliationError(PreviewPolicyError):
    """Raised when preview drifts from the public catalog or projection contract."""


def reconcile_preview_against_catalog(
    preview: PrivacyFirstTelemetryPreview,
    *,
    catalog: TelemetryCatalog,
) -> None:
    """Fail fast if the nested event or wrapper drifts from the catalog."""

    if preview.catalog_id != PRIVACY_FIRST_TELEMETRY_CATALOG_ID:
        raise PreviewReconciliationError("catalog_id mismatch")
    if preview.catalog_schema_version != PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION:
        raise PreviewReconciliationError("catalog_schema_version mismatch")
    if preview.event_schema_version != PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION:
        raise PreviewReconciliationError("event_schema_version mismatch")
    if preview.transmission_performed:
        raise PreviewReconciliationError("transmission_performed must be false")
    if preview.transport_status != "unavailable":
        raise PreviewReconciliationError("transport_status must be unavailable")
    if preview.installation_identity_used:
        raise PreviewReconciliationError("installation_identity_used must be false")
    if not preview.privacy_filter_required:
        raise PreviewReconciliationError("privacy_filter_required must be true")

    event_by_name = {item.name: item for item in catalog.events}
    if preview.event_name not in event_by_name:
        raise PreviewReconciliationError(f"unknown preview event: {preview.event_name}")
    catalog_event = event_by_name[preview.event_name]
    if preview.event_usage_status != catalog_event.usage_status:
        raise PreviewReconciliationError("event_usage_status mismatch")

    event_fields = set(preview.event or {})
    catalog_fields = {field.name for field in catalog.shared_fields}
    if not event_fields.issubset(catalog_fields):
        raise PreviewReconciliationError(
            f"preview event fields not in catalog: {sorted(event_fields - catalog_fields)}"
        )
    if event_fields & set(FORBIDDEN_FIELD_NAMES):
        raise PreviewReconciliationError("preview includes forbidden field names")
    if not event_fields.issubset(APPROVED_FIELD_NAMES):
        raise PreviewReconciliationError("preview includes non-approved fields")

    required = set(catalog_event.required_fields)
    if not required.issubset(event_fields):
        raise PreviewReconciliationError(
            f"missing required fields: {sorted(required - event_fields)}"
        )
    optional = set(catalog_event.optional_fields)
    expected_omitted = tuple(sorted(optional - event_fields))
    if tuple(preview.omitted_optional_fields) != expected_omitted:
        raise PreviewReconciliationError("omitted_optional_fields mismatch")

    enum_map = {
        enum.name: {value.value for value in enum.values} for enum in catalog.enums
    }
    field_enum = {
        field.name: field.enum_ref
        for field in catalog.shared_fields
        if field.enum_ref is not None
    }
    for key, value in (preview.event or {}).items():
        enum_ref = field_enum.get(key)
        if enum_ref is None:
            continue
        if not isinstance(value, str) or value not in enum_map[enum_ref]:
            raise PreviewReconciliationError(f"enum value not cataloged for {key}")


__all__ = [
    "PreviewReconciliationError",
    "reconcile_preview_against_catalog",
]
