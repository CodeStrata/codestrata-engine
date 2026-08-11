"""Slice 19.4 — persisted interactive telemetry consent."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.interactive_consent import (
    PROMPT_QUESTION,
    run_interactive_consent_prompt,
)
from codestrata.telemetry.persisted_consent import (
    TelemetryPreferenceState,
    persist_preference,
    preference_state,
)
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)


def test_undecided_interactive_prompt_default_enter_persists_no(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    assert preference_state(path=pref) is TelemetryPreferenceState.UNDECIDED
    echoes: list[str] = []
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "",
        echo_func=echoes.append,
        preference_path=pref,
    )
    assert result.prompted is True
    assert PROMPT_QUESTION
    assert result.consent.decision.value == "denied_for_session"
    assert preference_state(path=pref) is TelemetryPreferenceState.DISABLED


def test_yes_persists_and_skips_subsequent_prompt(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    first = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert first.consent.decision.value == "allowed_for_session"
    assert preference_state(path=pref) is TelemetryPreferenceState.ENABLED

    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        output_interactive=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert result.consent.transmission_authorized is True
    assert facade is not None


def test_existing_no_skips_prompt(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_preference(False, path=pref)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert result.consent.transmission_authorized is False
    assert facade is not None


def test_non_interactive_undecided_no_prompt_disabled(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert preference_state(path=pref) is TelemetryPreferenceState.UNDECIDED
    assert result.consent.transmission_authorized is False
    assert facade is not None


def test_enable_disable_override(tmp_path: Path, monkeypatch) -> None:
    pref = tmp_path / "telemetry.json"
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))
    # Direct preference path exercises the same store used by CLI.
    persist_preference(True, path=pref)
    assert preference_state(path=pref) is TelemetryPreferenceState.ENABLED
    persist_preference(False, path=pref)
    assert preference_state(path=pref) is TelemetryPreferenceState.DISABLED
    persist_preference(True, path=pref)
    assert preference_state(path=pref) is TelemetryPreferenceState.ENABLED
