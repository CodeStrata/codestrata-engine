"""Construct process telemetry for a CLI command session (Slices 9.4–9.6 / 19.4)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from codestrata.telemetry.cli_consent import (
    CliTelemetryConsentSelection,
    select_cli_telemetry_consent,
)
from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade
from codestrata.telemetry.interactive_consent import run_interactive_consent_prompt
from codestrata.telemetry.persisted_consent import consent_from_persisted_preference
from codestrata.telemetry.prompt_result import InteractiveConsentPromptResult
from codestrata.telemetry.product_transport import resolve_product_telemetry_transport
from codestrata.telemetry.runtime import TelemetryRuntime
from codestrata.telemetry.runtime_factory import create_session_telemetry_runtime
from codestrata.telemetry.transport import TelemetryTransport


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
    """Prompt when undecided and eligible; reuse local preference when decided.

    Unauthorized consent keeps UnavailableTelemetryTransport. Authorized consent
    uses production Community HTTP when a client credential is available.
    Explicit Yes/No is persisted locally. ``--telemetry-allow`` / ``--telemetry-deny``
    win for the current process without changing stored preference.
    """

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
    Precedence: CLI flags → explicit_consent → persisted preference → prompt.
    """

    selection = cli_selection
    if selection is None and (telemetry_allow or telemetry_deny):
        selection = select_cli_telemetry_consent(
            allow=telemetry_allow,
            deny=telemetry_deny,
        )
    if selection is not None and selection.explicit_decision_present:
        consent = selection.consent
        assert consent is not None  # explicit_decision_present guarantees consent
        active_transport = resolve_product_telemetry_transport(
            consent, transport=transport
        )
        runtime = create_session_telemetry_runtime(
            consent=consent,
            transport=active_transport,
        )
        from codestrata.telemetry.prompt_eligibility import PromptEligibilityReason
        from codestrata.telemetry.prompt_result import default_skipped_prompt_result

        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=consent,
        )
        return DisabledTelemetryFacade(runtime=runtime), result

    if explicit_consent is not None and explicit_consent.explicit:
        active_transport = resolve_product_telemetry_transport(
            explicit_consent, transport=transport
        )
        runtime = create_session_telemetry_runtime(
            consent=explicit_consent,
            transport=active_transport,
        )
        from codestrata.telemetry.prompt_eligibility import PromptEligibilityReason
        from codestrata.telemetry.prompt_result import default_skipped_prompt_result

        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=explicit_consent,
        )
        return DisabledTelemetryFacade(runtime=runtime), result

    persisted = consent_from_persisted_preference(path=preference_path)
    if persisted is not None:
        active_transport = resolve_product_telemetry_transport(
            persisted, transport=transport
        )
        runtime = create_session_telemetry_runtime(
            consent=persisted,
            transport=active_transport,
        )
        from codestrata.telemetry.prompt_eligibility import PromptEligibilityReason
        from codestrata.telemetry.prompt_result import default_skipped_prompt_result

        result = default_skipped_prompt_result(
            reason=PromptEligibilityReason.DECISION_ALREADY_EXPLICIT,
            consent=persisted,
        )
        return DisabledTelemetryFacade(runtime=runtime), result

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
    active_transport = resolve_product_telemetry_transport(
        result.consent, transport=transport
    )
    runtime: TelemetryRuntime = create_session_telemetry_runtime(
        consent=result.consent,
        transport=active_transport,
    )
    return DisabledTelemetryFacade(runtime=runtime), result


__all__ = [
    "create_command_session_telemetry_runtime",
    "create_interactive_session_telemetry",
]
