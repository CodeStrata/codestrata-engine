"""AI-related telemetry fields do not enable transmission."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons


def test_ai_hooks_remain_disabled(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    with patch("codestrata.telemetry.transport.send_payload") as send:
        telemetry = get_telemetry_service()
        telemetry.record_assessment_completed(
            ai_enabled=True,
            ai_executed=True,
            success=True,
            duration_ms=50.0,
        )
        send.assert_not_called()
    assert telemetry.runtime.session.counters.events_dropped >= 1
    assert list(home.iterdir()) == []
