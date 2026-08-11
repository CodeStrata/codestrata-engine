"""Interactive prompt failure / interrupt behavior (Slice 9.4 / 19.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.interactive_consent import run_interactive_consent_prompt
from codestrata.telemetry.runtime import run_with_isolated_telemetry
from codestrata.telemetry.prompt_runtime_factory import create_interactive_session_telemetry


def test_eof_denies(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"

    def boom(_prompt: str) -> str:
        raise EOFError

    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=boom,
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert result.safe_outcome == "eof_denied"
    assert result.decision == TelemetryDecision.DENIED_FOR_SESSION.value


def test_P_keyboard_interrupt_denies_and_primary_continues(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"

    def boom(_prompt: str) -> str:
        raise KeyboardInterrupt

    facade, result = create_interactive_session_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=boom,
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert result.safe_outcome == "interrupted_denied"
    assert result.decision_source == TelemetryDecisionSource.INTERACTIVE_PROMPT.value

    def primary() -> str:
        return "ok"

    assert run_with_isolated_telemetry(primary, runtime=facade.runtime) == "ok"


def test_O_prompt_exception_does_not_block_primary(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"

    def boom(_prompt: str) -> str:
        raise RuntimeError("prompt boom")

    facade, result = create_interactive_session_telemetry(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=boom,
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert result.safe_outcome == "prompt_failed_disabled"
    assert facade.runtime.session.decision is TelemetryDecision.DISABLED_BY_DEFAULT
    assert run_with_isolated_telemetry(lambda: 1, runtime=facade.runtime) == 1
