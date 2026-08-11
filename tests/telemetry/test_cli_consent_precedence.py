"""CLI consent consistency and precedence (Slice 9.6)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from codestrata.telemetry.cli_consent import select_cli_telemetry_consent
from codestrata.telemetry.consent import (
    SessionConsentError,
    allow_session_consent_from_cli_flag,
    deny_session_consent_from_cli_flag,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
)
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    reset_telemetry_singletons,
)


def test_cli_flag_consent_helpers() -> None:
    allow = allow_session_consent_from_cli_flag()
    deny = deny_session_consent_from_cli_flag()
    assert allow.source is TelemetryDecisionSource.CLI_FLAG
    assert deny.source is TelemetryDecisionSource.CLI_FLAG
    assert allow.decision is TelemetryDecision.ALLOWED_FOR_SESSION
    assert deny.decision is TelemetryDecision.DENIED_FOR_SESSION


def test_reject_disabled_with_cli_flag() -> None:
    with pytest.raises(SessionConsentError):
        type(allow_session_consent_from_cli_flag())(
            decision=TelemetryDecision.DISABLED_BY_DEFAULT,
            source=TelemetryDecisionSource.CLI_FLAG,
            explicit=False,
            transmission_authorized=False,
        )


def test_allow_precedes_prompt_and_ci() -> None:
    called = 0

    def boom(_p: str) -> str:
        nonlocal called
        called += 1
        raise AssertionError("prompt must not run")

    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        quiet=True,
        json_output=True,
        telemetry_allow=True,
        input_func=boom,
        echo_func=lambda _m: None,
    )
    assert called == 0
    assert result.prompted is False
    assert result.attempts == 0
    assert result.decision == "allowed_for_session"
    assert result.decision_source == "cli_flag"
    assert facade.runtime.session.consent.transmission_authorized is True


def test_deny_precedes_interactive() -> None:
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("prompt must not run"),
    ):
        facade, result = create_command_session_telemetry_runtime(
            command="assess",
            stdin_interactive=True,
            automation_detected=False,
            telemetry_deny=True,
        )
    assert result.prompted is False
    assert result.decision == "denied_for_session"
    assert result.decision_source == "cli_flag"
    assert facade.is_enabled() is False


def test_allow_not_replaced_by_non_interactive() -> None:
    selection = select_cli_telemetry_consent(allow=True)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        cli_selection=selection,
    )
    assert result.decision == "allowed_for_session"
    assert facade.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION


def test_ensure_product_allow_no_prompt() -> None:
    reset_telemetry_singletons()
    with patch(
        "codestrata.telemetry.interactive_consent.run_interactive_consent_prompt",
        side_effect=AssertionError("prompt must not run"),
    ):
        telemetry = ensure_interactive_product_telemetry(
            command="assess",
            telemetry_allow=True,
            stdin_interactive=True,
            automation_detected=False,
        )
    assert telemetry.runtime.session.decision_source is TelemetryDecisionSource.CLI_FLAG
