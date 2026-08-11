"""Fail-silent product enforcement under malformed inputs."""

from __future__ import annotations

from unittest.mock import patch

from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.runtime import run_with_isolated_telemetry


def test_Q_telemetry_exception_does_not_change_primary_result() -> None:
    facade = DisabledTelemetryFacade()

    def primary() -> str:
        with patch(
            "codestrata.telemetry.disabled_service.record_telemetry_safely",
            side_effect=RuntimeError("telemetry boom"),
        ):
            facade.record_assessment_started(ai_enabled=False)
        return "ok"

    assert run_with_isolated_telemetry(primary) == "ok"


def test_malformed_legacy_emit_fails_silently() -> None:
    facade = DisabledTelemetryFacade()
    assert facade.emit("not-a-real-thing", **{"repository_url": "x"}) is None
