"""Centralized interactive telemetry prompt eligibility (Slices 9.4–9.5).

Delegates suppression to the non-interactive policy. ``stdin_interactive=True``
alone cannot bypass automation detection — inject ``automation_detected=False``
for interactive simulation in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.non_interactive import (
    TelemetrySuppressionReason,
    evaluate_non_interactive_decision,
    probe_stdin_interactive,
)
from codestrata.telemetry.prompt_policy import (
    CommunityTelemetryInteractiveConsentPolicy,
    default_interactive_consent_policy,
)


class PromptEligibilityReason(StrEnum):
    ELIGIBLE = "eligible"
    STDIN_NOT_INTERACTIVE = "stdin_not_interactive"
    STDIN_UNAVAILABLE = "stdin_unavailable"
    PIPED_INPUT = "piped_input"
    CI_DETECTED = "ci_detected"
    AUTOMATION_DETECTED = "automation_detected"
    MACHINE_READABLE_OUTPUT = "machine_readable_output"
    QUIET_MODE = "quiet_mode"
    COMMAND_EXCLUDED = "command_excluded"
    COMMAND_NOT_ELIGIBLE = "command_not_eligible"
    SHELL_COMPLETION = "shell_completion"
    HELP_OR_VERSION = "help_or_version"
    DECISION_ALREADY_EXPLICIT = "decision_already_explicit"
    PROMPT_ALREADY_ATTEMPTED = "prompt_already_attempted"
    OUTPUT_MODE_INCOMPATIBLE = "output_mode_incompatible"
    OUTPUT_NOT_INTERACTIVE = "output_not_interactive"
    PROMPT_DISABLED = "prompt_disabled"


_REASON_MAP: dict[str, PromptEligibilityReason] = {
    TelemetrySuppressionReason.ELIGIBLE.value: PromptEligibilityReason.ELIGIBLE,
    TelemetrySuppressionReason.STDIN_NOT_INTERACTIVE.value: (
        PromptEligibilityReason.STDIN_NOT_INTERACTIVE
    ),
    TelemetrySuppressionReason.STDIN_UNAVAILABLE.value: (
        PromptEligibilityReason.STDIN_UNAVAILABLE
    ),
    TelemetrySuppressionReason.PIPED_INPUT.value: PromptEligibilityReason.PIPED_INPUT,
    TelemetrySuppressionReason.CI_DETECTED.value: PromptEligibilityReason.CI_DETECTED,
    TelemetrySuppressionReason.AUTOMATION_DETECTED.value: (
        PromptEligibilityReason.AUTOMATION_DETECTED
    ),
    TelemetrySuppressionReason.MACHINE_READABLE_OUTPUT.value: (
        PromptEligibilityReason.MACHINE_READABLE_OUTPUT
    ),
    TelemetrySuppressionReason.QUIET_MODE.value: PromptEligibilityReason.QUIET_MODE,
    TelemetrySuppressionReason.COMMAND_EXCLUDED.value: (
        PromptEligibilityReason.COMMAND_EXCLUDED
    ),
    TelemetrySuppressionReason.COMMAND_NOT_ELIGIBLE.value: (
        PromptEligibilityReason.COMMAND_NOT_ELIGIBLE
    ),
    TelemetrySuppressionReason.SHELL_COMPLETION.value: (
        PromptEligibilityReason.SHELL_COMPLETION
    ),
    TelemetrySuppressionReason.HELP_OR_VERSION.value: (
        PromptEligibilityReason.HELP_OR_VERSION
    ),
    TelemetrySuppressionReason.EXPLICIT_DECISION_PRESENT.value: (
        PromptEligibilityReason.DECISION_ALREADY_EXPLICIT
    ),
    TelemetrySuppressionReason.PROMPT_ALREADY_ATTEMPTED.value: (
        PromptEligibilityReason.PROMPT_ALREADY_ATTEMPTED
    ),
    TelemetrySuppressionReason.PROMPT_DISABLED.value: (
        PromptEligibilityReason.PROMPT_DISABLED
    ),
    TelemetrySuppressionReason.OUTPUT_NOT_INTERACTIVE.value: (
        PromptEligibilityReason.OUTPUT_NOT_INTERACTIVE
    ),
}


@dataclass(frozen=True, slots=True)
class PromptEligibility:
    eligible: bool
    reason: PromptEligibilityReason
    non_interactive: Any = None

    def to_stable_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eligible": self.eligible,
            "reason": self.reason.value,
        }
        if self.non_interactive is not None:
            payload["non_interactive"] = self.non_interactive.to_stable_dict()
        return payload


def stdin_is_interactive() -> bool:
    interactive, early = probe_stdin_interactive()
    if early is not None:
        return False
    return bool(interactive)


def evaluate_prompt_eligibility(
    *,
    command: str,
    quiet: bool = False,
    json_output: bool = False,
    decision_already_explicit: bool = False,
    prompt_already_attempted: bool = False,
    policy: CommunityTelemetryInteractiveConsentPolicy | None = None,
    stdin_interactive: bool | None = None,
    automation_detected: bool | None = None,
    output_interactive: bool | None = None,
) -> PromptEligibility:
    """Return whether an interactive consent prompt may be shown."""

    active = policy or default_interactive_consent_policy()
    decision = evaluate_non_interactive_decision(
        command=command,
        quiet=quiet,
        json_output=json_output,
        decision_already_explicit=decision_already_explicit,
        prompt_already_attempted=prompt_already_attempted,
        prompt_enabled=active.prompt_enabled_for_eligible_interactive_session,
        stdin_interactive=stdin_interactive,
        automation_detected=automation_detected,
        output_interactive=output_interactive,
    )
    if decision.interactive_eligible and not decision.prompt_suppressed:
        return PromptEligibility(
            eligible=True,
            reason=PromptEligibilityReason.ELIGIBLE,
            non_interactive=decision,
        )
    reason = _REASON_MAP.get(
        decision.suppression_reason, PromptEligibilityReason.PROMPT_DISABLED
    )
    if reason in {
        PromptEligibilityReason.QUIET_MODE,
        PromptEligibilityReason.MACHINE_READABLE_OUTPUT,
    }:
        # Alias retained for Slice 9.4 compatibility.
        reason = PromptEligibilityReason.OUTPUT_MODE_INCOMPATIBLE
    return PromptEligibility(
        eligible=False,
        reason=reason,
        non_interactive=decision,
    )


__all__ = [
    "PromptEligibility",
    "PromptEligibilityReason",
    "evaluate_prompt_eligibility",
    "stdin_is_interactive",
]
