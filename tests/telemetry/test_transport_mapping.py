"""Event identity and mapping tests (Slice 9.11)."""

from __future__ import annotations

import json

import pytest

from codestrata.telemetry.event_identity import (
    generate_transport_event_id,
    validate_transport_event_id,
)
from codestrata.telemetry.events import (
    DurationBucket,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent, project_runtime_event
from codestrata.telemetry.transport_mapping import (
    OMITTED_ENGINE_FIELDS,
    TransportMappingError,
    map_privacy_safe_event_to_cloud_request,
)
from codestrata.telemetry.transport_models import CommunityCloudTelemetryWireRequest
from tests.telemetry.transport_test_helpers import FIXED_EVENT_ID, gated_event


def test_event_id_format() -> None:
    event_id = generate_transport_event_id()
    assert validate_transport_event_id(event_id) == event_id
    assert len(event_id) >= 8


def test_mapping_produces_cloud_wire_without_installation_id() -> None:
    wire = map_privacy_safe_event_to_cloud_request(
        gated_event(), event_id=FIXED_EVENT_ID
    )
    payload = wire.to_stable_dict()
    assert payload["schema_version"] == "1.0"
    assert payload["event_type"] == "feature_completed"
    assert payload["client"]["name"] == "codestrata_cli"
    assert payload["client"]["platform"] == "linux"
    assert payload["properties"]["outcome"] == "succeeded"
    assert "offline" in payload["properties"]["flags"]
    assert "installation_id" not in payload
    assert "occurred_at" not in payload
    assert list(payload.keys()) == sorted(payload.keys())


def test_duration_bucket_only_exact_map() -> None:
    projected = project_runtime_event(
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.APPLICATION_COMPLETED,
            cli_version="0.2.0",
            duration_bucket=DurationBucket.LT_1S,
        )
    )
    wire = map_privacy_safe_event_to_cloud_request(projected, event_id=FIXED_EVENT_ID)
    assert wire.properties is not None
    assert wire.properties["duration_bucket"] == "under_1s"

    projected2 = project_runtime_event(
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.APPLICATION_COMPLETED,
            cli_version="0.2.0",
            duration_bucket=DurationBucket.S_1_10,
        )
    )
    wire2 = map_privacy_safe_event_to_cloud_request(projected2, event_id=FIXED_EVENT_ID)
    assert wire2.properties is None or "duration_bucket" not in (wire2.properties or {})


def test_mapping_rejects_raw_dict_and_runtime_event() -> None:
    with pytest.raises(TransportMappingError):
        map_privacy_safe_event_to_cloud_request(  # type: ignore[arg-type]
            {"event_type": "application_started"},
            event_id=FIXED_EVENT_ID,
        )
    with pytest.raises(TransportMappingError):
        map_privacy_safe_event_to_cloud_request(  # type: ignore[arg-type]
            RuntimeTelemetryEvent(event_type=RuntimeEventType.APPLICATION_STARTED),
            event_id=FIXED_EVENT_ID,
        )


def test_omitted_fields_documented() -> None:
    fields = gated_event().to_stable_dict()
    wire = map_privacy_safe_event_to_cloud_request(
        PrivacySafeTelemetryEvent(fields=fields), event_id=FIXED_EVENT_ID
    )
    payload = wire.to_stable_dict()
    props = payload.get("properties") or {}
    for name in OMITTED_ENGINE_FIELDS - {"schema_version"}:
        assert name not in payload
        assert name not in props
    assert payload["schema_version"] == "1.0"
    assert "runtime_policy_version" not in payload
    assert "runtime_policy_version" not in props
    assert "arch_family" not in props
    assert "lifecycle" not in props
    assert "failure_category" not in props


def test_wire_serialization_deterministic() -> None:
    wire = CommunityCloudTelemetryWireRequest(
        event_id=FIXED_EVENT_ID,
        event_type="application_started",
        client_name="codestrata_cli",
        client_version="0.2.0",
        client_platform="linux",
        properties={"outcome": "succeeded", "flags": ["offline"]},
    )
    assert wire.to_canonical_bytes() == wire.to_canonical_bytes()
    assert b" " not in wire.to_canonical_bytes()
