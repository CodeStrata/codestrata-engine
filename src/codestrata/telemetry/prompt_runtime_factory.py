"""Construct process telemetry for a CLI command session (Slices 9.4–9.6 / 19.4 / 20.9).

Consent-v2 precedence:
  1. ``--telemetry-deny`` — session deny (does not change durable preference)
  2. Durable preference (V1_YES / V2_YES / DISABLED / UNDECIDED)
  3. ``--telemetry-allow`` — session bridge only; never creates consent;
     never overrides DISABLED; never enables UNDECIDED
  4. Interactive fresh-v2 or one-time V1→V2 upgrade prompts when eligible
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from codestrata.telemetry.cli_consent import (
    CliTelemetryConsentSelection,
    select_cli_telemetry_consent,
)
from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.consent_scope import (
    CommunityConsentState,
    resolve_consent_capabilities,
)
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.interactive_consent import (
    run_interactive_consent_prompt,
    run_v2_upgrade_prompt,
)
from codestrata.telemetry.persisted_consent import consent_from_persisted_preference
from codestrata.telemetry.prompt_eligibility import (
    PromptEligibilityReason,
    evaluate_prompt_eligibility,
)
from codestrata.telemetry.prompt_result import (
    InteractiveConsentPromptResult,
    default_skipped_prompt_result,
)
from codestrata.telemetry.product_transport import resolve_product_telemetry_transport
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransport


def _facade_for_consent(
    consent: TelemetrySessionConsent,
    *,
    transport: TelemetryTransport | None,
) -> DisabledTelemetryFacade:
    active_transport = resolve_product_telemetry_transport(consent, transport=transport)
    runtime: TelemetryRuntime = create_session_telemetry_runtime(
        consent=consent,
        transport=active_transport,
    )
    return DisabledTelemetryFacade(runtime=runtime)


def _interactive_eligible(
    *,
    command: str,
    quiet: bool,
    json_output: bool,
    decision_already_explicit: bool,
    prompt_already_attempted: bool,
    stdin_interactive: bool | None,
    automation_detected: bool | None,
    output_interactive: bool | None,
) -> bool:
    return evaluate_prompt_eligibility(
        command=command,
        quiet=quiet,
        json_output=json_output,
        decision_already_explicit=decision_already_explicit,
        prompt_already_attempted=prompt_already_attempted,
        stdin_interactive=stdin_interactive,
        automation_detected=automation_detected,
        output_interactive=output_interactive,
    ).eligible


def create_interactive_session_telemetry(
    *,
    command: str,
    quiet: bool = False,
    json_output: bool = False,
    decision_already_explicit: bool = False,
    prompt_already_attempted: bool = False,
    transport: TelemetryTransport | None = None,
    input_func: Callable[[str], str] | None = None,
    echo_func: Callable[[str], None] | None = None,
    stdin_interactive: bool | None = None,
    automation_detected: bool | None = None,
    output_interactive: bool | None = None,
    explicit_consent: TelemetrySessionConsent | None = None,
    telemetry_allow: bool = False,
    telemetry_deny: bool = False,
    cli_selection: CliTelemetryConsentSelection | None = None,
    preference_path: Path | None = None,
) -> tuple[DisabledTelemetryFacade, InteractiveConsentPromptResult]:
    """Prompt when undecided and eligible; reuse local preference when decided."""

    return create_command_session_telemetry_runtime(
        command=command,
        quiet=quiet,
        json_output=json_output,
        decision_already_explicit=decision_already_explicit
        or (explicit_consent is not None and explicit_consent.explicit),
        prompt_already_attempted=prompt_already_attempted,
        transport=transport,
        input_func=input_func,
        echo_func=echo_func,
        stdin_interactive=stdin_interactive,
        automation_detected=automation_detected,
        output_interactive=output_interactive,
        explicit_consent=explicit_consent,
        telemetry_allow=telemetry_allow,
        telemetry_deny=telemetry_deny,
        cli_selection=cli_selection,
        preference_path=preference_path,
    )


def create_command_session_telemetry_runtime(
    *,
    command: str,
    quiet: bool = False,
    json_output: bool = False,
    decision_already_explicit: bool = False,
    prompt_already_attempted: bool = False,
    transport: TelemetryTransport | None = None,
    input_func: Callable[[str], str] | None = None,
    echo_func: Callable[[str], None] | None = None,
    stdin_interactive: bool | None = None,
    automation_detected: bool | None = None,
    output_interactive: bool | None = None,
    explicit_consent: TelemetrySessionConsent | None = None,
    telemetry_allow: bool = False,
    telemetry_deny: bool = False,
    cli_selection: CliTelemetryConsentSelection | None = None,
    preference_path: Path | None = None,
) -> tuple[DisabledTelemetryFacade, InteractiveConsentPromptResult]:
    """Authoritative command-session telemetry construction (one runtime).

    Raises ``CliTelemetryConsentConflict`` when both CLI flags are set.

    Precedence (Slice 20.9):
      deny flag → durable preference → allow bridge → interactive prompt.
    ``--telemetry-allow`` never creates consent and never overrides DISABLED.
    """

    selection = cli_selection
    if selection is None and (telemetry_allow or telemetry_deny):
        selection = select_cli_telemetry_consent(
            allow=telemetry_allow,
            deny=telemetry_deny,
        )

    # 1) Session deny wins for this process (does not mutate durable preference).
    if selection is not None and selection.deny_requested and not selection.conflict:
        consent = selection.consent
        assert consent is not None
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=consent,
        )
        return _facade_for_consent(consent, transport=transport), result

    if explicit_consent is not None and explicit_consent.explicit:
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=explicit_consent,
        )
        return _facade_for_consent(explicit_consent, transport=transport), result

    caps = resolve_consent_capabilities(path=preference_path)
    allow_bridge = bool(selection is not None and selection.allow_requested)

    # 2) Durable DISABLED — allow bridge cannot override.
    if caps.state is CommunityConsentState.DISABLED:
        persisted = consent_from_persisted_preference(path=preference_path)
        assert persisted is not None
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=persisted,
        )
        return _facade_for_consent(persisted, transport=transport), result

    # 3) Durable V2_YES — lifecycle (+ amd authorized separately).
    if caps.state is CommunityConsentState.V2_YES:
        persisted = consent_from_persisted_preference(path=preference_path)
        assert persisted is not None
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=persisted,
        )
        return _facade_for_consent(persisted, transport=transport), result

    # 4) Durable V1_YES — lifecycle only; optional one-time upgrade prompt.
    if caps.state is CommunityConsentState.V1_YES:
        if (
            caps.should_prompt_v2_upgrade
            and not allow_bridge
            and _interactive_eligible(
                command=command,
                quiet=quiet,
                json_output=json_output,
                decision_already_explicit=False,
                prompt_already_attempted=prompt_already_attempted,
                stdin_interactive=stdin_interactive,
                automation_detected=automation_detected,
                output_interactive=output_interactive,
            )
        ):
            upgrade = run_v2_upgrade_prompt(
                input_func=input_func,
                echo_func=echo_func,
                preference_path=preference_path,
                persist=True,
            )
            # Re-resolve after upgrade accept/decline.
            post = consent_from_persisted_preference(path=preference_path)
            consent = post if post is not None else upgrade.consent
            return _facade_for_consent(consent, transport=transport), upgrade

        persisted = consent_from_persisted_preference(path=preference_path)
        assert persisted is not None
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=persisted,
        )
        return _facade_for_consent(persisted, transport=transport), result

    # 5) UNDECIDED — allow bridge must NOT invent consent.
    if allow_bridge:
        from codestrata.telemetry.consent import default_session_consent

        consent = default_session_consent()
        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=consent,
        )
        return _facade_for_consent(consent, transport=transport), result

    # 6) Fresh interactive v2 prompt (or non-interactive skip).
    result = run_interactive_consent_prompt(
        command=command,
        quiet=quiet,
        json_output=json_output,
        decision_already_explicit=decision_already_explicit,
        prompt_already_attempted=prompt_already_attempted,
        input_func=input_func,
        echo_func=echo_func,
        stdin_interactive=stdin_interactive,
        automation_detected=automation_detected,
        output_interactive=output_interactive,
        preference_path=preference_path,
        persist=True,
    )
    return _facade_for_consent(result.consent, transport=transport), result


__all__ = [
    "create_command_session_telemetry_runtime",
    "create_interactive_session_telemetry",
]
