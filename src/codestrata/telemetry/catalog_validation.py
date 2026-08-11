"""Catalog reconciliation helpers (Slice 9.8)."""

from __future__ import annotations

from codestrata.telemetry.catalog_metadata import ENUM_MEANINGS, EVENT_PURPOSE, FIELD_META
from codestrata.telemetry.catalog_models import TelemetryCatalog
from codestrata.telemetry.events import (
    ArchFamily,
    DurationBucket,
    FailureCategory,
    Lifecycle,
    OperationCategory,
    OsFamily,
    ResultCategory,
    RuntimeEventType,
)
from codestrata.telemetry.privacy import APPROVED_FIELD_NAMES, FORBIDDEN_FIELD_NAMES


class CatalogReconciliationError(ValueError):
    """Raised when catalog drift is detected."""


def reconcile_catalog_against_runtime(catalog: TelemetryCatalog) -> None:
    """Fail fast if catalog drifts from typed runtime contracts."""

    event_names = {event.name for event in catalog.events}
    enum_event_values = {item.value for item in RuntimeEventType}
    if event_names != enum_event_values:
        raise CatalogReconciliationError(
            f"event drift: catalog={sorted(event_names)} code={sorted(enum_event_values)}"
        )
    if set(EVENT_PURPOSE) != enum_event_values:
        raise CatalogReconciliationError("EVENT_PURPOSE metadata incomplete")

    field_names = {field.name for field in catalog.shared_fields}
    if field_names != set(APPROVED_FIELD_NAMES):
        raise CatalogReconciliationError(
            f"field drift: catalog={sorted(field_names)} code={sorted(APPROVED_FIELD_NAMES)}"
        )
    if set(FIELD_META) != set(APPROVED_FIELD_NAMES):
        raise CatalogReconciliationError("FIELD_META incomplete")
    if field_names & set(FORBIDDEN_FIELD_NAMES):
        raise CatalogReconciliationError("catalog includes forbidden field names")

    enum_map = {enum.name: {value.value for value in enum.values} for enum in catalog.enums}
    expected_enums = {
        "event_type": {item.value for item in RuntimeEventType},
        "os_family": {item.value for item in OsFamily},
        "arch_family": {item.value for item in ArchFamily},
        "lifecycle": {item.value for item in Lifecycle},
        "result": {item.value for item in ResultCategory},
        "duration_bucket": {item.value for item in DurationBucket},
        "operation_category": {item.value for item in OperationCategory},
        "failure_category": {item.value for item in FailureCategory},
    }
    if set(enum_map) != set(expected_enums):
        raise CatalogReconciliationError("enum set drift")
    for name, values in expected_enums.items():
        if enum_map[name] != values:
            raise CatalogReconciliationError(f"enum value drift for {name}")
        if set(ENUM_MEANINGS[name]) != values:
            raise CatalogReconciliationError(f"ENUM_MEANINGS incomplete for {name}")

    if catalog.transmission_status != "not_operational":
        raise CatalogReconciliationError("transmission must be not_operational")
    if catalog.installation_identity_status != "not_used":
        raise CatalogReconciliationError("installation identity must be not_used")
    if catalog.consent_expands_fields:
        raise CatalogReconciliationError("consent must not expand fields")
    if catalog.client_name != "codestrata_cli":
        raise CatalogReconciliationError("client_name must be codestrata_cli")


__all__ = [
    "CatalogReconciliationError",
    "reconcile_catalog_against_runtime",
]
