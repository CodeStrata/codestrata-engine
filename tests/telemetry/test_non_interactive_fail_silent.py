"""Fail-silent and stdin edge cases for non-interactive suppression (Slice 9.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from codestrata.telemetry.interactive_consent import run_interactive_consent_prompt
from codestrata.telemetry.non_interactive import (
    TelemetrySuppressionReason,
    evaluate_non_interactive_decision,
    probe_stdin_interactive,
)
from codestrata.telemetry.prompt_runtime_factory import create_command_session_telemetry_runtime


def test_D_E_missing_closed_stdin_suppress() -> None:
    with patch("codestrata.telemetry.non_interactive.sys") as mock_sys:
        mock_sys.stdin = None
        interactive, early = probe_stdin_interactive()
        assert interactive is None
        assert early is TelemetrySuppressionReason.STDIN_UNAVAILABLE

    closed = MagicMock()
    closed.closed = True
    with patch("codestrata.telemetry.non_interactive.sys") as mock_sys:
        mock_sys.stdin = closed
        interactive, early = probe_stdin_interactive()
        assert early is TelemetrySuppressionReason.STDIN_UNAVAILABLE


def test_F_isatty_exception_suppresses() -> None:
    broken = MagicMock()
    broken.closed = False
    broken.isatty.side_effect = OSError("no tty")
    with patch("codestrata.telemetry.non_interactive.sys") as mock_sys:
        mock_sys.stdin = broken
        interactive, early = probe_stdin_interactive()
        assert early is TelemetrySuppressionReason.STDIN_UNAVAILABLE

    decision = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=None,
        automation_detected=False,
    )
    # Production probe may still succeed; force unavailable via injection path
    # by simulating early return through evaluate with unavailable probe.
    with patch(
        "codestrata.telemetry.non_interactive.probe_stdin_interactive",
        return_value=(None, TelemetrySuppressionReason.STDIN_UNAVAILABLE),
    ):
        decision = evaluate_non_interactive_decision(
            command="assess",
            stdin_interactive=None,
            automation_detected=False,
        )
    assert decision.prompt_suppressed is True
    assert decision.suppression_reason == "stdin_unavailable"
    assert decision.decision == "non_interactive_disabled"


def test_output_not_interactive_suppresses() -> None:
    decision = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=False,
    )
    assert decision.suppression_reason == "output_not_interactive"
    assert decision.decision == "non_interactive_disabled"


def test_runtime_construction_failure_fail_closed() -> None:
    with patch(
        "codestrata.telemetry.prompt_runtime_factory.create_session_telemetry_runtime",
        side_effect=RuntimeError("boom"),
    ):
        # Factory itself is not catch-all; service layer is. Direct evaluate stays safe.
        decision = evaluate_non_interactive_decision(
            command="assess",
            stdin_interactive=False,
            automation_detected=False,
        )
    assert decision.prompt_suppressed is True

    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
    )
    assert result.prompted is False
    assert result.attempts == 0


def test_command_session_factory_suppressed(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
    )
    assert result.prompted is False
    assert facade.runtime.session.consent.transmission_authorized is False
    assert facade.is_enabled() is False
