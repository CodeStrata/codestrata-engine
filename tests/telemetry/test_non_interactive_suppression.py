"""Non-interactive telemetry prompt suppression tests (Slice 9.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.consent import (
    SessionConsentError,
    allow_session_consent,
    deny_session_consent,
    non_interactive_session_consent,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.interactive_consent import run_interactive_consent_prompt
from codestrata.telemetry.non_interactive import (
    TelemetrySuppressionReason,
    detect_automation,
    evaluate_non_interactive_decision,
)
from codestrata.telemetry.non_interactive_diagnostics import (
    diagnostics_from_non_interactive,
)
from codestrata.telemetry.non_interactive_policy import (
    COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_URN,
    CommunityTelemetryNonInteractivePolicy,
    NonInteractivePolicyError,
    default_non_interactive_policy,
)
from codestrata.telemetry.prompt_runtime_factory import (
    create_command_session_telemetry_runtime,
    create_interactive_session_telemetry,
)
from codestrata.telemetry.service import (
    ensure_interactive_product_telemetry,
    reset_telemetry_singletons,
)


def test_non_interactive_policy_defaults() -> None:
    policy = default_non_interactive_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_URN
    assert policy.default_decision_when_suppressed == "non_interactive_disabled"
    assert policy.persistence_allowed is False
    assert policy.transmission_allowed is False


def test_policy_rejects_transmission() -> None:
    with pytest.raises(NonInteractivePolicyError):
        CommunityTelemetryNonInteractivePolicy(transmission_allowed=True)


def test_A_ci_never_prompts(monkeypatch) -> None:
    monkeypatch.setenv("CI", "true")
    called = 0

    def reader(_p: str) -> str:
        nonlocal called
        called += 1
        return "y"

    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        input_func=reader,
        echo_func=lambda _m: None,
    )
    assert called == 0
    assert result.prompted is False
    assert result.attempts == 0
    assert result.decision == "non_interactive_disabled"
    assert result.eligibility_reason == "ci_detected"


def test_X_stdin_override_does_not_bypass_automation() -> None:
    result = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=True,
        automation_detected=True,
    )
    assert result.prompt_suppressed is True
    assert result.interactive_eligible is False
    assert result.decision == "non_interactive_disabled"
    assert result.suppression_reason in {
        TelemetrySuppressionReason.CI_DETECTED.value,
        TelemetrySuppressionReason.AUTOMATION_DETECTED.value,
    }


def test_B_non_tty_never_prompts() -> None:
    result = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
    )
    assert result.suppression_reason == "stdin_not_interactive"
    assert result.decision == "non_interactive_disabled"


def test_C_piped_y_does_not_allow() -> None:
    reads = 0

    def reader(_p: str) -> str:
        nonlocal reads
        reads += 1
        return "y"

    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
        input_func=reader,
        echo_func=lambda _m: None,
    )
    assert reads == 0
    assert result.decision == "non_interactive_disabled"
    assert result.prompted is False


def test_G_H_machine_quiet_suppress() -> None:
    quiet = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        quiet=True,
    )
    assert quiet.suppression_reason == "quiet_mode"
    assert quiet.decision == "non_interactive_disabled"

    machine = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        json_output=True,
    )
    assert machine.suppression_reason == "machine_readable_output"
    assert machine.output_mode == "machine_readable"


def test_I_J_K_L_exclusions_not_non_interactive_disabled() -> None:
    for command, reason in (
        ("help", "help_or_version"),
        ("version", "help_or_version"),
        ("completion", "shell_completion"),
        ("telemetry status", "command_excluded"),
    ):
        decision = evaluate_non_interactive_decision(
            command=command,
            stdin_interactive=True,
            automation_detected=False,
        )
        assert decision.prompt_suppressed is True
        assert decision.suppression_reason == reason
        assert decision.decision == "disabled_by_default"
        assert decision.decision_source == "default"


def test_T_explicit_decision_precedence() -> None:
    allow = allow_session_consent()
    facade, result = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        quiet=True,
        explicit_consent=allow,
    )
    assert result.prompted is False
    assert result.decision == "allowed_for_session"
    assert result.decision_source == "explicit_session_allow"
    assert facade.runtime.session.consent.explicit is True
    assert result.eligibility_reason == "decision_already_explicit"

    deny = deny_session_consent()
    _, denied = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        explicit_consent=deny,
    )
    assert denied.decision == "denied_for_session"


def test_U_V_suppression_not_prompt_attempt() -> None:
    decision = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
    )
    diag = diagnostics_from_non_interactive(decision)
    assert diag.prompted is False
    assert diag.attempts == 0
    assert diag.prompt_suppressed is True
    assert diag.transmission_authorized is False
    blob = diag.to_stable_json()
    for needle in ("GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "/Users/"):
        assert needle not in blob


def test_M_N_diagnostics_no_provider_or_job() -> None:
    decision = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=True,
        automation_detected=True,
    )
    payload = diagnostics_from_non_interactive(decision).to_stable_dict()
    text = str(payload)
    for needle in (
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "BUILD_BUILDID",
        "job_id",
        "runner",
        "/home/",
        "hostname",
    ):
        assert needle not in text


def test_detect_automation_presence_only() -> None:
    assert detect_automation(environ={}) is False
    assert detect_automation(environ={"CI": "true"}) is True
    assert detect_automation(environ={"GITHUB_ACTIONS": "true"}) is True
    assert detect_automation(environ={"CODESTRATA_CLI_MACHINE": "1"}) is True
    assert detect_automation(environ={"CI": "false"}) is False


def test_W_detector_failure_suppresses() -> None:
    with patch(
        "codestrata.telemetry.non_interactive.detect_automation",
        side_effect=RuntimeError("boom"),
    ):
        decision = evaluate_non_interactive_decision(
            command="assess",
            stdin_interactive=True,
            automation_detected=None,
        )
    # evaluate wraps detector; when injection is None and detect raises inside
    # detect_automation itself returns True. Patching detect raises at call site
    # is caught and treated as automation=True.
    assert decision.prompt_suppressed is True
    assert decision.interactive_eligible is False


def test_consent_consistency_non_interactive() -> None:
    consent = non_interactive_session_consent()
    assert consent.decision is TelemetryDecision.NON_INTERACTIVE_DISABLED
    assert consent.source is TelemetryDecisionSource.NON_INTERACTIVE_POLICY
    assert consent.explicit is False
    assert consent.persisted is False
    assert consent.transmission_authorized is False
    with pytest.raises(SessionConsentError):
        type(consent)(
            decision=TelemetryDecision.NON_INTERACTIVE_DISABLED,
            source=TelemetryDecisionSource.INTERACTIVE_PROMPT,
            explicit=False,
            transmission_authorized=False,
        )
    with pytest.raises(SessionConsentError):
        type(consent)(
            decision=TelemetryDecision.NON_INTERACTIVE_DISABLED,
            source=TelemetryDecisionSource.NON_INTERACTIVE_POLICY,
            explicit=True,
            transmission_authorized=False,
        )


def test_interactive_still_works_with_full_overrides() -> None:
    result = run_interactive_consent_prompt(
        command="assess",
        stdin_interactive=True,
        automation_detected=False,
        input_func=lambda _p: "y",
        echo_func=lambda _m: None,
    )
    assert result.prompted is True
    assert result.attempts == 1
    assert result.decision == "allowed_for_session"


def test_determinism_equivalent_contexts() -> None:
    a = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        quiet=False,
    )
    b = evaluate_non_interactive_decision(
        command="assess",
        stdin_interactive=False,
        automation_detected=True,
        quiet=False,
    )
    assert a.to_stable_dict() == b.to_stable_dict()
    assert diagnostics_from_non_interactive(a).to_stable_json() == (
        diagnostics_from_non_interactive(b).to_stable_json()
    )


def test_no_filesystem_on_suppression(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    reset_telemetry_singletons()
    with patch("codestrata.telemetry.transport.send_payload") as send:
        telemetry = ensure_interactive_product_telemetry(
            command="assess",
            stdin_interactive=False,
            automation_detected=True,
            input_func=lambda _p: "y",
            echo_func=lambda _m: None,
        )
        telemetry.record_assessment_started(ai_enabled=False)
        send.assert_not_called()
    assert list(home.iterdir()) == []
    assert telemetry.runtime.session.decision is TelemetryDecision.NON_INTERACTIVE_DISABLED


def test_factory_alias(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    a, ra = create_interactive_session_telemetry(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
    )
    b, rb = create_command_session_telemetry_runtime(
        command="assess",
        stdin_interactive=False,
        automation_detected=False,
    )
    assert ra.decision == rb.decision == "non_interactive_disabled"
    assert a.runtime.session.decision is b.runtime.session.decision
