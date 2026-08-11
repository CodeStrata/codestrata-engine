"""Compatibility facade with explicit session consent (Slice 9.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.consent import allow_session_consent
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.runtime_factory import (
    create_default_telemetry_runtime,
    create_session_telemetry_runtime,
)
from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_product_facade_remains_disabled() -> None:
    reset_telemetry_singletons()
    assert get_telemetry_service().is_enabled() is False
    assert get_telemetry_service().status()["transmission_authorized"] is False


def test_facade_reflects_allowed_injected_runtime() -> None:
    capture = CaptureTelemetryTransport()
    runtime = create_session_telemetry_runtime(
        consent=allow_session_consent(),
        transport=capture,
    )
    facade = DisabledTelemetryFacade(runtime=runtime)
    assert facade.is_enabled() is True
    assert facade.status()["transmission_authorized"] is True
    with patch("codestrata.telemetry.transport.send_payload") as send:
        facade.record_assessment_started(ai_enabled=False, domains=["security"])
        send.assert_not_called()
    assert len(capture.captured) == 1
    assert "installation_id" not in capture.captured[0].to_stable_dict()


def test_facade_no_legacy_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))
    runtime = create_default_telemetry_runtime()
    facade = DisabledTelemetryFacade(runtime=runtime)
    facade.record_report_opened()
    assert list(tmp_path.iterdir()) == [] if tmp_path.exists() else True
