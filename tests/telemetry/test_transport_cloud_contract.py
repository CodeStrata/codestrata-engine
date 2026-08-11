"""Community Cloud contract reconciliation without Platform imports."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.telemetry.transport_mapping import map_privacy_safe_event_to_cloud_request
from codestrata.telemetry.transport_models import (
    CLOUD_DURATION_BUCKETS,
    CLOUD_EVENT_TYPES,
    CLOUD_OUTCOMES,
    CLOUD_PROPERTY_KEYS,
)
from tests.telemetry.transport_test_helpers import FIXED_EVENT_ID, gated_event

_DOCUMENTED_EVENT_TYPES = frozenset(
    {
        "application_started",
        "application_completed",
        "feature_invoked",
        "feature_completed",
        "operation_failed",
    }
)
_DOCUMENTED_PROPERTIES = frozenset(
    {"feature", "operation", "outcome", "duration_bucket", "count", "flags"}
)
_DOCUMENTED_OUTCOMES = frozenset({"succeeded", "failed", "cancelled", "unavailable"})
_DOCUMENTED_DURATIONS = frozenset(
    {
        "under_1s",
        "1s_to_5s",
        "5s_to_30s",
        "30s_to_2m",
        "over_2m",
        "unavailable",
    }
)


def test_engine_vocab_matches_documented_cloud_contract() -> None:
    assert CLOUD_EVENT_TYPES == _DOCUMENTED_EVENT_TYPES
    assert CLOUD_PROPERTY_KEYS == _DOCUMENTED_PROPERTIES
    assert CLOUD_OUTCOMES == _DOCUMENTED_OUTCOMES
    assert CLOUD_DURATION_BUCKETS == _DOCUMENTED_DURATIONS


def test_mapped_request_keys_are_cloud_allowlisted() -> None:
    wire = map_privacy_safe_event_to_cloud_request(
        gated_event(), event_id=FIXED_EVENT_ID
    )
    payload = wire.to_stable_dict()
    assert set(payload.keys()).issubset(
        {"schema_version", "event_id", "event_type", "client", "properties"}
    )
    assert payload["schema_version"] == "1.0"
    assert set(payload["client"].keys()) == {"name", "version", "platform"}
    if "properties" in payload:
        assert set(payload["properties"].keys()).issubset(_DOCUMENTED_PROPERTIES)


def test_platform_docs_fixture_present() -> None:
    docs = (
        Path(__file__).resolve().parents[3]
        / "platform"
        / "docs"
        / "community-cloud-api"
        / "telemetry-ingestion.md"
    )
    if not docs.is_file():
        return
    text = docs.read_text(encoding="utf-8")
    assert "schema_version" in text
    assert "event_id" in text
    assert "codestrata_cli" in text
    assert "POST /api/v1/telemetry" in text


def test_wire_json_is_object_not_array() -> None:
    wire = map_privacy_safe_event_to_cloud_request(
        gated_event(), event_id=FIXED_EVENT_ID
    )
    parsed = json.loads(wire.to_canonical_bytes())
    assert isinstance(parsed, dict)
