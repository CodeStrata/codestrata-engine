"""Catalog event/field/enum reconciliation tests (Slice 9.8)."""

from __future__ import annotations

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.privacy import APPROVED_FIELD_NAMES, FORBIDDEN_FIELD_NAMES
from codestrata.telemetry.projection import project_runtime_event


def test_every_event_enum_listed() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    names = {event.name for event in catalog.events}
    assert names == {item.value for item in RuntimeEventType}


def test_usage_status_distinguishes_emission() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    by_name = {event.name: event.usage_status for event in catalog.events}
    assert by_name["feature_invoked"] == "emitted_by_current_runtime"
    assert by_name["feature_completed"] == "emitted_by_current_runtime"
    assert by_name["operation_failed"] == "emitted_by_current_runtime"
    assert by_name["application_started"] == "supported_but_not_currently_emitted"
    assert by_name["application_completed"] == "supported_but_not_currently_emitted"


def test_every_approved_field_listed() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    names = {field.name for field in catalog.shared_fields}
    assert names == set(APPROVED_FIELD_NAMES)
    assert names.isdisjoint(FORBIDDEN_FIELD_NAMES)


def test_projected_fields_subset_of_catalog() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    catalog_fields = {field.name for field in catalog.shared_fields}
    for event_type in RuntimeEventType:
        projected = project_runtime_event(
            RuntimeTelemetryEvent(event_type=event_type)
        ).to_stable_dict()
        assert set(projected).issubset(catalog_fields)


def test_enums_complete() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    enum_names = {enum.name for enum in catalog.enums}
    assert "event_type" in enum_names
    assert "duration_bucket" in enum_names
    duration = next(e for e in catalog.enums if e.name == "duration_bucket")
    values = {item.value for item in duration.values}
    assert values == {"lt_1s", "s_1_10", "s_10_60", "m_1_5", "gt_5m"}
    assert duration.unknown_value_behavior == "rejected"


def test_never_collected_includes_core_categories() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    cats = {item.category for item in catalog.never_collected}
    for required in (
        "repository_names",
        "source_code",
        "findings",
        "credentials",
        "prompts",
        "exact_model_ids",
        "exact_token_counts",
        "exact_cost",
        "installation_identity",
        "endpoint_urls",
    ):
        assert required in cats


def test_no_legacy_or_extension_contamination() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    blob = catalog.to_stable_json()
    assert "assessment_completed" not in blob  # legacy EventName
    assert "vscode" not in blob.lower()
    assert "cursor" not in blob.lower() or "not_implemented" in blob
    assert catalog.client_name == "codestrata_cli"
    assert all(event.transmission_operational is False for event in catalog.events)
    assert all(field.transmitted_currently is False for field in catalog.shared_fields)
