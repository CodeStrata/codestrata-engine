"""CLI construction uses disabled product telemetry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.service import (
    get_legacy_telemetry_service,
    get_telemetry_service,
    reset_telemetry_singletons,
)


def test_cli_product_entry_is_facade() -> None:
    reset_telemetry_singletons()
    assert isinstance(get_telemetry_service(), DisabledTelemetryFacade)


def test_K_legacy_enable_does_not_activate_product_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.delenv("CODESTRATA_TELEMETRY", raising=False)
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.service.send_payload", return_value=False):
        legacy = get_legacy_telemetry_service(home=home)
        legacy.enable(emit_events=False)
        assert legacy.is_enabled() is True

    product = get_telemetry_service()
    assert product.is_enabled() is False
    with patch("codestrata.telemetry.transport.send_payload") as send:
        product.record_assessment_started(ai_enabled=False)
        send.assert_not_called()
    assert product.runtime.session.counters.transmission_attempts == 0
