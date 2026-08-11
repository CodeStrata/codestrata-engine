"""Catalog requiredness and shared-shape honesty tests (Slice 9.8)."""

from __future__ import annotations

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_models import FieldRequiredness
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.projection import project_runtime_event


def test_shared_requiredness_across_events() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    required = {
        "client_name",
        "event_type",
        "runtime_policy_version",
        "schema_version",
    }
    optional = {
        "ai_used",
        "arch_family",
        "cli_version",
        "duration_bucket",
        "enabled_assessment_heads",
        "failure_category",
        "lifecycle",
        "offline_mode",
        "operation_category",
        "os_family",
        "result",
    }
    for event in catalog.events:
        assert set(event.required_fields) == required
        assert set(event.optional_fields) == optional
        assert "shared event shape" in " ".join(event.event_specific_constraints).lower()


def test_field_requiredness_matches_metadata() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    by_name = {field.name: field for field in catalog.shared_fields}
    for name in ("event_type", "client_name", "schema_version", "runtime_policy_version"):
        assert by_name[name].requiredness == FieldRequiredness.REQUIRED.value
        assert by_name[name].omitted_when_unavailable is False
    for name in (
        "cli_version",
        "os_family",
        "arch_family",
        "lifecycle",
        "result",
        "duration_bucket",
        "operation_category",
        "enabled_assessment_heads",
        "offline_mode",
        "ai_used",
        "failure_category",
    ):
        assert by_name[name].requiredness == FieldRequiredness.OPTIONAL.value
        assert by_name[name].omitted_when_unavailable is True


def test_optional_omission_matches_serialization() -> None:
    projected = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    ).to_stable_dict()
    assert set(projected) == {
        "client_name",
        "event_type",
        "runtime_policy_version",
        "schema_version",
    }
    assert "failure_category" not in projected
    assert "duration_bucket" not in projected


def test_cross_field_rules_document_honesty() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    rule_ids = {rule.rule_id for rule in catalog.cross_field_rules}
    assert "shared_event_shape" in rule_ids
    assert "consent_cannot_expand_fields" in rule_ids
    assert catalog.consent_expands_fields is False
    assert catalog.privacy_filtering_required is True
