"""Report / open telemetry hooks remain disabled."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_report_opened_no_side_effects(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    reset_telemetry_singletons()
    with patch("codestrata.telemetry.transport.send_payload") as send:
        get_telemetry_service().record_report_opened()
        send.assert_not_called()
    assert list(home.iterdir()) == []
