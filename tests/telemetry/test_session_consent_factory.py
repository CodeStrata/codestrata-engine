"""Session runtime factory tests (Slice 9.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.consent import allow_session_consent, deny_session_consent
from codestrata.telemetry.decisions import TelemetryDecision
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.infrastructure.unavailable_transport import (
    UnavailableTelemetryTransport,
)
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)


def test_default_factory_disabled_unavailable() -> None:
    runtime = create_default_telemetry_runtime()
    assert runtime.session.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert isinstance(runtime.session.transport, UnavailableTelemetryTransport)


def test_session_factory_allow_and_deny() -> None:
    allowed = create_session_telemetry_runtime(consent=allow_session_consent())
    denied = create_session_telemetry_runtime(consent=deny_session_consent())
    assert allowed.session.transmission_authorized is True
    assert denied.session.transmission_authorized is False
    assert isinstance(allowed.session.transport, UnavailableTelemetryTransport)


def test_V_capture_not_selected_by_default_factory() -> None:
    runtime = create_session_telemetry_runtime(consent=allow_session_consent())
    assert not isinstance(runtime.session.transport, CaptureTelemetryTransport)


def test_factory_no_preference_or_endpoint_lookup(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "telemetry.json").write_text(
        '{"enabled": true, "decision_made": true}', encoding="utf-8"
    )
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    with patch("codestrata.telemetry.preferences.load_preferences") as load:
        with patch("codestrata.telemetry.transport.configured_endpoint") as configured:
            create_session_telemetry_runtime(consent=allow_session_consent())
            create_default_telemetry_runtime()
            load.assert_not_called()
            configured.assert_not_called()
    assert (home / "installation_id").exists() is False
