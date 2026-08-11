"""Preview policy, builder, catalog reconciliation, and privacy tests (Slice 9.9)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.events import RuntimeEventType
from codestrata.telemetry.preview_builder import build_privacy_first_telemetry_preview
from codestrata.telemetry.preview_diagnostics import diagnostics_from_preview
from codestrata.telemetry.preview_examples import illustrative_runtime_event
from codestrata.telemetry.preview_formatting import format_privacy_first_telemetry_preview
from codestrata.telemetry.preview_policy import (
    COMMUNITY_TELEMETRY_PREVIEW_POLICY_URN,
    PreviewPolicyError,
    default_preview_policy,
)
from codestrata.telemetry.projection import project_runtime_event


def test_preview_policy_defaults() -> None:
    policy = default_preview_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_PREVIEW_POLICY_URN
    assert policy.local_only is True
    assert policy.transmission_performed is False
    assert policy.transport_invocation_allowed is False
    assert policy.default_event_name == "feature_invoked"


def test_default_preview_is_feature_invoked() -> None:
    preview = build_privacy_first_telemetry_preview()
    assert preview.event_name == "feature_invoked"
    assert preview.preview_type == "illustrative"
    assert preview.schema_name == "privacy-first-telemetry-preview"
    assert preview.schema_version == "1.0.0"
    assert preview.transmission_performed is False
    assert preview.transport_status == "unavailable"
    assert preview.installation_identity_used is False
    assert preview.consent_persisted is False
    assert preview.privacy_filter_required is True
    diag = diagnostics_from_preview(preview)
    assert diag.transmission_performed is False


def test_all_runtime_events_previewable() -> None:
    for event_type in RuntimeEventType:
        preview = build_privacy_first_telemetry_preview(event_name=event_type.value)
        assert preview.event_name == event_type.value
        assert preview.event["event_type"] == event_type.value
        projected = project_runtime_event(
            illustrative_runtime_event(event_type.value)
        ).to_stable_dict()
        assert preview.event == projected


def test_invalid_event_rejected() -> None:
    with pytest.raises(PreviewPolicyError):
        build_privacy_first_telemetry_preview(event_name="assessment_completed")


def test_determinism() -> None:
    a = build_privacy_first_telemetry_preview(event_name="operation_failed")
    b = build_privacy_first_telemetry_preview(event_name="operation_failed")
    assert a.to_stable_json() == b.to_stable_json()
    assert format_privacy_first_telemetry_preview(a) == format_privacy_first_telemetry_preview(
        b
    )
    assert list(a.event.keys()) == sorted(a.event.keys())
    assert list(a.omitted_optional_fields) == sorted(a.omitted_optional_fields)


def test_privacy_scan() -> None:
    for event_type in RuntimeEventType:
        text = format_privacy_first_telemetry_preview(
            build_privacy_first_telemetry_preview(event_name=event_type.value)
        )
        lowered = text.lower()
        for needle in (
            "/users/",
            "https://",
            "sk-",
            "password=",
            "55555555-5555",
            "amazonaws",
            "boto3",
        ):
            assert needle not in lowered
        assert '"installation_id"' not in text
        assert '"name": "installation_id"' not in text
        assert payload_has_no_installation_id_field(text)
        assert '"transmission_performed": false' in text
        assert '"transport_status": "unavailable"' in text
        payload = json.loads(text)
        assert "timestamp" not in payload
        assert "raw_event" not in payload
        assert "installation_id" not in payload
        assert "installation_id" not in payload["event"]


def payload_has_no_installation_id_field(text: str) -> bool:
    payload = json.loads(text)
    return "installation_id" not in payload and "installation_id" not in payload.get(
        "event", {}
    )


def test_no_transport_or_legacy_side_effects(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text("{bad", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    with patch("codestrata.telemetry.service.get_legacy_telemetry_service") as legacy:
        with patch("codestrata.telemetry.transport.send_payload") as send:
            with patch(
                "codestrata.telemetry.infrastructure.unavailable_transport.UnavailableTelemetryTransport.send"
            ) as transport_send:
                preview = build_privacy_first_telemetry_preview()
                assert preview.transmission_performed is False
                legacy.assert_not_called()
                send.assert_not_called()
                transport_send.assert_not_called()
    assert {p.name: p.read_bytes() for p in home.iterdir()} == before
    home.chmod(0o000)
    try:
        build_privacy_first_telemetry_preview(event_name="feature_completed")
    finally:
        home.chmod(0o700)


def test_omitted_optional_fields_transparent() -> None:
    preview = build_privacy_first_telemetry_preview(event_name="application_started")
    assert "failure_category" in preview.omitted_optional_fields
    assert "failure_category" not in preview.event
    assert "duration_bucket" in preview.omitted_optional_fields
