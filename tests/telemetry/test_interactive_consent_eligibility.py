"""Prompt eligibility tests (Slices 9.4–9.5)."""

from __future__ import annotations

from codestrata.telemetry.prompt_eligibility import (
    PromptEligibilityReason,
    evaluate_prompt_eligibility,
)


def test_eligible_assess_interactive() -> None:
    result = evaluate_prompt_eligibility(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        quiet=False,
        json_output=False,
    )
    assert result.eligible is True
    assert result.reason is PromptEligibilityReason.ELIGIBLE


def test_J_K_L_excluded_commands() -> None:
    for command in ("version", "help", "telemetry status", "telemetry", "welcome"):
        result = evaluate_prompt_eligibility(
            command=command,
            stdin_interactive=True,
            automation_detected=False,
        )
        assert result.eligible is False
        assert result.reason in {
            PromptEligibilityReason.COMMAND_EXCLUDED,
            PromptEligibilityReason.COMMAND_NOT_ELIGIBLE,
            PromptEligibilityReason.HELP_OR_VERSION,
        }


def test_T_non_tty_no_prompt() -> None:
    result = evaluate_prompt_eligibility(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
    )
    assert result.eligible is False
    assert result.reason is PromptEligibilityReason.STDIN_NOT_INTERACTIVE
    assert result.non_interactive.decision == "non_interactive_disabled"


def test_quiet_json_ci_incompatible(monkeypatch) -> None:
    assert (
        evaluate_prompt_eligibility(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            quiet=True,
        ).eligible
        is False
    )
    assert (
        evaluate_prompt_eligibility(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            json_output=True,
        ).eligible
        is False
    )
    monkeypatch.setenv("CI", "true")
    # Auto-detect path (stdin_interactive=None) respects CI.
    assert (
        evaluate_prompt_eligibility(command="assess", stdin_interactive=None).eligible
        is False
    )
    # stdin_interactive alone must not bypass automation (Slice 9.5).
    assert (
        evaluate_prompt_eligibility(
            command="assess",
            stdin_interactive=True,
        ).eligible
        is False
    )


def test_already_attempted_or_explicit() -> None:
    assert (
        evaluate_prompt_eligibility(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            prompt_already_attempted=True,
        ).reason
        is PromptEligibilityReason.PROMPT_ALREADY_ATTEMPTED
    )
    assert (
        evaluate_prompt_eligibility(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            decision_already_explicit=True,
        ).reason
        is PromptEligibilityReason.DECISION_ALREADY_EXPLICIT
    )
