"""Answer parsing and consent mapping (Slice 9.4 / 19.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.interactive_consent import (
    PromptAnswer,
    parse_prompt_answer,
    run_interactive_consent_prompt,
)


def test_parse_allow_deny_invalid() -> None:
    assert parse_prompt_answer("y") is PromptAnswer.ALLOW
    assert parse_prompt_answer(" YES ") is PromptAnswer.ALLOW
    assert parse_prompt_answer("n") is PromptAnswer.DENY
    assert parse_prompt_answer("") is PromptAnswer.DENY
    assert parse_prompt_answer(None) is PromptAnswer.DENY
    assert parse_prompt_answer("true") is PromptAnswer.INVALID
    assert parse_prompt_answer("1") is PromptAnswer.INVALID
    assert parse_prompt_answer("enable") is PromptAnswer.INVALID


def test_B_C_empty_and_invalid_never_allow(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    empty = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "",
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert empty.decision == TelemetryDecision.DENIED_FOR_SESSION.value
    assert empty.decision_source == TelemetryDecisionSource.INTERACTIVE_PROMPT.value
    assert empty.consent.transmission_authorized is False

    pref2 = tmp_path / "telemetry-invalid.json"
    invalid = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "true",
        echo_func=lambda _m: None,
        preference_path=pref2,
    )
    assert invalid.decision == TelemetryDecision.DENIED_FOR_SESSION.value
    assert invalid.safe_outcome == "invalid_dismissed"
    assert not pref2.exists()


def test_yes_maps_to_allowed_interactive(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
        preference_path=pref,
    )
    assert result.prompted is True
    assert result.decision == TelemetryDecision.ALLOWED_FOR_SESSION.value
    assert result.decision_source == TelemetryDecisionSource.INTERACTIVE_PROMPT.value
    assert result.consent.persisted is True
    assert pref.is_file()
    payload = result.to_stable_dict()
    assert "raw_answer" not in payload
    assert "answer" not in payload
    assert "response" not in payload
    assert "yes" not in payload.get("safe_outcome", "")
