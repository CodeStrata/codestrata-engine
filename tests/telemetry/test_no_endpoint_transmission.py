"""CODESTRATA_TELEMETRY_ENDPOINT must not activate product transmission."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_G_H_endpoint_does_not_transmit_or_queue(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv(
        "CODESTRATA_TELEMETRY_ENDPOINT",
        "https://user:p4ssw0rd@example.invalid/v1/telemetry",
    )
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    reset_telemetry_singletons()

    with patch("codestrata.telemetry.transport.send_payload") as send:
        with patch("codestrata.telemetry.transport.configured_endpoint") as configured:
            facade = get_telemetry_service()
            assert facade.status()["endpoint_configured"] is False
            facade.record_assessment_completed(
                ai_enabled=False,
                ai_executed=False,
                success=True,
                duration_ms=1.0,
            )
            send.assert_not_called()
            configured.assert_not_called()

    assert list(home.iterdir()) == []
    diag = facade.runtime.diagnostics().to_stable_json()
    assert "p4ssw0rd" not in diag
    assert "example.invalid" not in diag
