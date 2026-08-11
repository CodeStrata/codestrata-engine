"""Non-interactive telemetry prompt suppression (Slice 9.5).

Fail closed: uncertainty suppresses the prompt. Suppression is not user consent
and never consumes stdin.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from codestrata.telemetry.consent import (
    TelemetrySessionConsent,
    default_session_consent,
    non_interactive_session_consent,
)
from codestrata.telemetry.non_interactive_policy import (
    COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION,
    CommunityTelemetryNonInteractivePolicy,
    default_non_interactive_policy,
)
from codestrata.telemetry.prompt_policy import ELIGIBLE_COMMANDS, EXCLUDED_COMMANDS

# Presence-only markers — values are never recorded in diagnostics.
_AUTOMATION_PRESENCE_MARKERS: frozenset[str] = frozenset(
    {
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "BUILD_BUILDID",
        "TEAMCITY_VERSION",
        "TF_BUILD",
        "CODEBUILD_BUILD_ID",
        "BUILDKITE",
        "CIRCLECI",
        "TRAVIS",
    }
)


class TelemetrySuppressionReason(StrEnum):
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
    EXPLICIT_DECISION_PRESENT = "explicit_decision_present"
    PROMPT_ALREADY_ATTEMPTED = "prompt_already_attempted"
    PROMPT_DISABLED = "prompt_disabled"
    OUTPUT_NOT_INTERACTIVE = "output_not_interactive"


# Reasons that map to non_interactive_disabled (policy suppression).
_NON_INTERACTIVE_DECISION_REASONS: frozenset[TelemetrySuppressionReason] = frozenset(
    {
        TelemetrySuppressionReason.STDIN_NOT_INTERACTIVE,
        TelemetrySuppressionReason.STDIN_UNAVAILABLE,
        TelemetrySuppressionReason.PIPED_INPUT,
        TelemetrySuppressionReason.CI_DETECTED,
        TelemetrySuppressionReason.AUTOMATION_DETECTED,
        TelemetrySuppressionReason.MACHINE_READABLE_OUTPUT,
        TelemetrySuppressionReason.QUIET_MODE,
        TelemetrySuppressionReason.OUTPUT_NOT_INTERACTIVE,
    }
)

_HELP_VERSION_COMMANDS: frozenset[str] = frozenset(
    {"help", "version", "about", "--help", "--version"}
)
_COMPLETION_COMMANDS: frozenset[str] = frozenset(
    {"completion", "install-completion", "show-completion"}
)


@dataclass(frozen=True, slots=True)
class NonInteractiveTelemetryDecision:
    """Bounded suppression result — no env values, paths, or provider names."""

    interactive_eligible: bool
    prompt_suppressed: bool
    suppression_reason: str
    decision: str
    decision_source: str
    consent: TelemetrySessionConsent
    stdin_interactive: bool
    output_mode: str
    automation_detected: bool
    non_interactive_policy_version: str = (
        COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION
    )
    limitation_codes: tuple[str, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "automation_detected": self.automation_detected,
            "consent": self.consent.to_stable_dict(),
            "decision": self.decision,
            "decision_source": self.decision_source,
            "interactive_eligible": self.interactive_eligible,
            "limitation_codes": list(self.limitation_codes),
            "non_interactive_policy_version": self.non_interactive_policy_version,
            "output_mode": self.output_mode,
            "prompt_suppressed": self.prompt_suppressed,
            "stdin_interactive": self.stdin_interactive,
            "suppression_reason": self.suppression_reason,
        }


def detect_automation(
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return True when CI/automation markers are present. Never records values."""

    try:
        env = environ if environ is not None else os.environ
        machine = str(env.get("CODESTRATA_CLI_MACHINE", "")).strip().lower()
        if machine in {"1", "true", "yes", "on"}:
            return True
        ci = str(env.get("CI", "")).strip().lower()
        if ci in {"1", "true", "yes", "on"}:
            return True
        for key in _AUTOMATION_PRESENCE_MARKERS:
            if str(env.get(key, "")).strip():
                return True
        return False
    except Exception:
        # Fail closed: treat detector failure as automation.
        return True


def probe_stdin_interactive() -> tuple[bool | None, TelemetrySuppressionReason | None]:
    """Probe stdin without reading content.

    Returns ``(interactive, early_reason)``. ``interactive`` is None when
    unavailable; ``early_reason`` is set for unavailable/closed cases.
    """

    try:
        stdin = sys.stdin
    except Exception:
        return None, TelemetrySuppressionReason.STDIN_UNAVAILABLE
    if stdin is None:
        return None, TelemetrySuppressionReason.STDIN_UNAVAILABLE
    try:
        closed = bool(getattr(stdin, "closed", False))
    except Exception:
        return None, TelemetrySuppressionReason.STDIN_UNAVAILABLE
    if closed:
        return None, TelemetrySuppressionReason.STDIN_UNAVAILABLE
    try:
        interactive = bool(getattr(stdin, "isatty", lambda: False)())
    except Exception:
        return None, TelemetrySuppressionReason.STDIN_UNAVAILABLE
    return interactive, None


def classify_output_mode(*, quiet: bool, json_output: bool) -> str:
    if json_output:
        return "machine_readable"
    if quiet:
        return "quiet"
    return "human"


def evaluate_non_interactive_decision(
    *,
    command: str,
    quiet: bool = False,
    json_output: bool = False,
    decision_already_explicit: bool = False,
    prompt_already_attempted: bool = False,
    prompt_enabled: bool = True,
    stdin_interactive: bool | None = None,
    automation_detected: bool | None = None,
    output_interactive: bool | None = None,
    policy: CommunityTelemetryNonInteractivePolicy | None = None,
    explicit_consent: TelemetrySessionConsent | None = None,
) -> NonInteractiveTelemetryDecision:
    """Evaluate whether the interactive prompt must be suppressed.

    ``stdin_interactive`` alone cannot bypass automation detection. Tests must
    inject ``automation_detected=False`` for interactive simulation.
    """

    active = policy or default_non_interactive_policy()
    limitations = active.limitations
    normalized = " ".join(str(command or "").strip().lower().split())
    output_mode = classify_output_mode(quiet=quiet, json_output=json_output)

    try:
        automation = (
            detect_automation()
            if automation_detected is None
            else bool(automation_detected)
        )
    except Exception:
        automation = True

    if stdin_interactive is None:
        probed, early = probe_stdin_interactive()
        if early is not None:
            return _suppressed(
                reason=early,
                stdin_interactive=False,
                output_mode=output_mode,
                automation_detected=automation,
                limitations=limitations,
            )
        stdin_ok = bool(probed)
    else:
        stdin_ok = bool(stdin_interactive)

    # Explicit internal consent (future flags / test injection) skips prompting.
    if decision_already_explicit or (
        explicit_consent is not None and explicit_consent.explicit
    ):
        consent = explicit_consent or default_session_consent()
        return NonInteractiveTelemetryDecision(
            interactive_eligible=False,
            prompt_suppressed=True,
            suppression_reason=TelemetrySuppressionReason.EXPLICIT_DECISION_PRESENT.value,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitation_codes=limitations,
        )

    if not prompt_enabled:
        return _suppressed(
            reason=TelemetrySuppressionReason.PROMPT_DISABLED,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )
    if prompt_already_attempted:
        return _suppressed(
            reason=TelemetrySuppressionReason.PROMPT_ALREADY_ATTEMPTED,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )

    if normalized in _HELP_VERSION_COMMANDS:
        return _suppressed(
            reason=TelemetrySuppressionReason.HELP_OR_VERSION,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )
    if normalized in _COMPLETION_COMMANDS:
        return _suppressed(
            reason=TelemetrySuppressionReason.SHELL_COMPLETION,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )
    if normalized in EXCLUDED_COMMANDS or normalized.startswith("telemetry"):
        return _suppressed(
            reason=TelemetrySuppressionReason.COMMAND_EXCLUDED,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )
    if normalized not in ELIGIBLE_COMMANDS:
        return _suppressed(
            reason=TelemetrySuppressionReason.COMMAND_NOT_ELIGIBLE,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
            use_non_interactive_consent=False,
        )

    if json_output:
        return _suppressed(
            reason=TelemetrySuppressionReason.MACHINE_READABLE_OUTPUT,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
        )
    if quiet:
        return _suppressed(
            reason=TelemetrySuppressionReason.QUIET_MODE,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
        )

    if automation:
        # Prefer ci_detected when CI-style generic marker is set; else automation.
        reason = TelemetrySuppressionReason.AUTOMATION_DETECTED
        try:
            env = os.environ
            if str(env.get("CI", "")).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }:
                reason = TelemetrySuppressionReason.CI_DETECTED
        except Exception:
            reason = TelemetrySuppressionReason.AUTOMATION_DETECTED
        return _suppressed(
            reason=reason,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=True,
            limitations=limitations,
        )

    if not stdin_ok:
        # Non-TTY covers pipes and redirects without reading stdin content.
        if stdin_interactive is False:
            reason = TelemetrySuppressionReason.STDIN_NOT_INTERACTIVE
        else:
            reason = TelemetrySuppressionReason.PIPED_INPUT
        return _suppressed(
            reason=reason,
            stdin_interactive=False,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
        )

    if output_interactive is False:
        return _suppressed(
            reason=TelemetrySuppressionReason.OUTPUT_NOT_INTERACTIVE,
            stdin_interactive=stdin_ok,
            output_mode=output_mode,
            automation_detected=automation,
            limitations=limitations,
        )

    consent = default_session_consent()
    return NonInteractiveTelemetryDecision(
        interactive_eligible=True,
        prompt_suppressed=False,
        suppression_reason=TelemetrySuppressionReason.ELIGIBLE.value,
        decision=consent.decision.value,
        decision_source=consent.source.value,
        consent=consent,
        stdin_interactive=True,
        output_mode=output_mode,
        automation_detected=False,
        limitation_codes=limitations,
    )


def _suppressed(
    *,
    reason: TelemetrySuppressionReason,
    stdin_interactive: bool,
    output_mode: str,
    automation_detected: bool,
    limitations: tuple[str, ...],
    use_non_interactive_consent: bool | None = None,
) -> NonInteractiveTelemetryDecision:
    if use_non_interactive_consent is None:
        use_non_interactive = reason in _NON_INTERACTIVE_DECISION_REASONS
    else:
        use_non_interactive = use_non_interactive_consent
    consent = (
        non_interactive_session_consent()
        if use_non_interactive
        else default_session_consent()
    )
    return NonInteractiveTelemetryDecision(
        interactive_eligible=False,
        prompt_suppressed=True,
        suppression_reason=reason.value,
        decision=consent.decision.value,
        decision_source=consent.source.value,
        consent=consent,
        stdin_interactive=stdin_interactive,
        output_mode=output_mode,
        automation_detected=automation_detected,
        limitation_codes=limitations,
    )


__all__ = [
    "NonInteractiveTelemetryDecision",
    "TelemetrySuppressionReason",
    "classify_output_mode",
    "detect_automation",
    "evaluate_non_interactive_decision",
    "probe_stdin_interactive",
]
