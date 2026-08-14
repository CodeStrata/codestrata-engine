"""CLI consent precedence after Slice 20.9 (--telemetry-allow is not consent)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.cli_consent import select_cli_telemetry_consent
from codestrata.telemetry.consent import (
    SessionConsentError,
    allow_session_consent_from_cli_flag,
    deny_session_consent_from_cli_flag,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.persisted_consent import persist_disabled, persist_v2_yes
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


def test_allow_alone_does_not_enable_undecided(tmp_path: Path) -> None:
    """--telemetry-allow is a bridge, not consent (Slice 20.9)."""

    pref = tmp_path / "telemetry.json"
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
        preference_path=pref,
        input_func=boom,
        echo_func=lambda _m: None,
    )
    assert called == 0
    assert result.prompted is False
    assert facade.runtime.session.consent.transmission_authorized is False
    assert not pref.exists()


def test_allow_with_v2_enables_lifecycle(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        telemetry_allow=True,
        preference_path=pref,
        input_func=lambda _p: (_ for _ in ()).throw(AssertionError("no prompt")),
    )
    assert result.prompted is False
    assert result.consent.transmission_authorized is True
    assert result.decision_source == "persisted_preference"
    assert facade.runtime.session.consent.transmission_authorized is True


def test_allow_cannot_override_disabled(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_disabled(path=pref)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        telemetry_allow=True,
        preference_path=pref,
    )
    assert result.consent.transmission_authorized is False
    assert facade.is_enabled() is False


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


def test_allow_not_replaced_by_non_interactive(tmp_path: Path) -> None:
    pref = tmp_path / "telemetry.json"
    persist_v2_yes(path=pref)
    selection = select_cli_telemetry_consent(allow=True)
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        cli_selection=selection,
        preference_path=pref,
    )
    assert result.consent.transmission_authorized is True
    assert facade.runtime.session.decision is TelemetryDecision.ALLOWED_FOR_SESSION


def test_ensure_product_allow_alone_no_prompt_no_enable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODESTRATA_HOME", str(tmp_path))
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
    assert telemetry.runtime.session.consent.transmission_authorized is False
