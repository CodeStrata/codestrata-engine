"""Pre-transport privacy gate tests (Slice 9.10)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.pre_transport_errors import PreTransportReasonCode
from codestrata.telemetry.pre_transport_gate import validate_event_before_transport
from codestrata.telemetry.pre_transport_policy import (
    COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_URN,
    default_pre_transport_policy,
)
from codestrata.telemetry.preview_builder import build_privacy_first_telemetry_preview
from codestrata.telemetry.projection import PrivacySafeTelemetryEvent, project_runtime_event
from codestrata.telemetry.runtime import TelemetryRecordStatus
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime


def test_pre_transport_policy_defaults() -> None:
    policy = default_pre_transport_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_URN
    assert policy.only_privacy_safe_event_accepted is True
    assert policy.catalog_reconciliation_required is True


def test_accepts_projected_event() -> None:
    projected = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    result = validate_event_before_transport(projected)
    assert result.accepted is True
    assert result.accepted_event is not None
    assert result.accepted_event.to_stable_dict() == projected.to_stable_dict()
    assert result.safe_reason_code == PreTransportReasonCode.ACCEPTED.value


@pytest.mark.parametrize(
    "bad",
    [
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED),
        {"event_type": "feature_invoked"},
        "feature_invoked",
        b"{}",
        None,
    ],
)
def test_rejects_non_privacy_safe_types(bad: object) -> None:
    result = validate_event_before_transport(bad)
    assert result.accepted is False
    assert result.status == "invalid_type"
    assert result.accepted_event is None
    blob = result.to_stable_json()
    assert "password" not in blob
    assert "/Users/" not in blob


def test_rejects_forbidden_and_unknown_fields() -> None:
    base = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    ).to_stable_dict()
    for key in ("repository", "installation_id", "path", "model_id", "cost"):
        payload = dict(base)
        payload[key] = "x"
        result = validate_event_before_transport(PrivacySafeTelemetryEvent(fields=payload))
        assert result.accepted is False
        assert result.accepted_event is None
        assert key not in result.to_stable_json()


def test_rejects_wrong_schema_version() -> None:
    payload = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    ).to_stable_dict()
    payload["schema_version"] = "9.9"
    result = validate_event_before_transport(PrivacySafeTelemetryEvent(fields=payload))
    assert result.accepted is False
    assert result.safe_reason_code == PreTransportReasonCode.UNSUPPORTED_EVENT_SCHEMA.value


def test_rejects_path_like_cli_version() -> None:
    payload = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    ).to_stable_dict()
    payload["cli_version"] = "/tmp/evil"
    result = validate_event_before_transport(PrivacySafeTelemetryEvent(fields=payload))
    assert result.accepted is False
    assert "/tmp/evil" not in result.to_stable_json()


def test_rejects_oversized_event() -> None:
    payload = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    ).to_stable_dict()
    # Inflate with many tiny approved-looking heads via direct construction.
    payload["enabled_assessment_heads"] = [f"head{i:02d}" for i in range(40)]
    # Max property count may still pass; force size with long but non-path strings
    # by exceeding max_property_count via duplicated fake fields won't work (unknown).
    # Instead exceed property count by... we can't add unknown fields.
    # Use policy override via gate with tiny max.
    from codestrata.telemetry.pre_transport_policy import (
        CommunityTelemetryPreTransportPrivacyPolicy,
    )

    tiny = CommunityTelemetryPreTransportPrivacyPolicy(max_event_size_bytes=80)
    result = validate_event_before_transport(
        PrivacySafeTelemetryEvent(fields=payload),
        policy=tiny,
    )
    assert result.accepted is False
    assert result.status in {"event_too_large", "field_limit_exceeded", "unsafe_value"}


def test_allowed_consent_cannot_bypass_gate() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    bad = PrivacySafeTelemetryEvent(
        fields={
            "client_name": "codestrata_cli",
            "event_type": "feature_invoked",
            "schema_version": "1.0",
            "runtime_policy_version": "1.0",
            "repository": "acme",
        }
    )
    # Inject after projection by calling _safe_send path via monkeypatch of project
    from codestrata.telemetry import runtime as runtime_mod

    original_project = runtime_mod.project_runtime_event

    def _project(event, *, policy=None):  # noqa: ANN001
        _ = original_project(event, policy=policy)
        return bad

    with patch.object(runtime_mod, "project_runtime_event", side_effect=_project):
        result = runtime.record(
            RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
        )
    assert result.status is TelemetryRecordStatus.PRIVACY_REJECTED
    assert capture.captured == []
    assert runtime.session.counters.privacy_gate_rejected >= 1
    assert runtime.session.counters.privacy_gate_accepted == 0


def test_capture_receives_only_gated_accepted_events() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    result = runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_COMPLETED)
    )
    assert result.status is TelemetryRecordStatus.TRANSPORT_RESULT
    assert len(capture.captured) == 1
    gate = validate_event_before_transport(capture.captured[0])
    assert gate.accepted is True
    assert runtime.session.counters.privacy_gate_accepted == 1


def test_denied_session_skips_gate_and_transport() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=deny_session_consent(),
        transport=capture,
    )
    result = runtime.record(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)
    )
    assert result.status is TelemetryRecordStatus.DROPPED_DENIED
    assert capture.captured == []
    assert runtime.session.counters.privacy_gate_attempts == 0
    assert runtime.session.counters.transmission_attempts == 0


def test_preview_uses_gate_without_transport() -> None:
    with patch(
        "codestrata.telemetry.infrastructure.unavailable_transport.UnavailableTelemetryTransport.send"
    ) as send:
        preview = build_privacy_first_telemetry_preview()
        send.assert_not_called()
    assert preview.transmission_performed is False
    assert "pre_transport_privacy_gate_validated" in preview.limitations
    gate = validate_event_before_transport(
        PrivacySafeTelemetryEvent(fields=dict(preview.event or {}))
    )
    assert gate.accepted is True


def test_gate_side_effect_free(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text("{bad", encoding="utf-8")
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    projected = project_runtime_event(
        RuntimeTelemetryEvent(event_type=RuntimeEventType.OPERATION_FAILED)
    )
    with patch("codestrata.telemetry.service.get_legacy_telemetry_service") as legacy:
        with patch("codestrata.telemetry.transport.send_payload") as send:
            result = validate_event_before_transport(projected)
            assert result.accepted is True
            legacy.assert_not_called()
            send.assert_not_called()
    assert {p.name: p.read_bytes() for p in home.iterdir()} == before


def test_determinism() -> None:
    projected = project_runtime_event(
        RuntimeTelemetryEvent(
            event_type=RuntimeEventType.FEATURE_INVOKED,
            enabled_assessment_heads=("security", "architecture"),
        )
    )
    a = validate_event_before_transport(projected)
    b = validate_event_before_transport(projected)
    assert a.to_stable_json() == b.to_stable_json()
    assert a.accepted_event is not None
    assert a.accepted_event.to_stable_json() == b.accepted_event.to_stable_json()


def test_result_never_includes_payload() -> None:
    result = validate_event_before_transport({"secret": "x"})
    payload = result.to_stable_dict()
    assert "event" not in payload
    assert "accepted_event" not in payload
    assert "secret" not in result.to_stable_json()
