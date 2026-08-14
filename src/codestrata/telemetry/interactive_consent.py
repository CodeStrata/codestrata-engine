"""Interactive telemetry consent prompts (Slices 19.4 / 20.9).

Fresh users receive a single v2 consent question.
Legacy V1 users may receive a one-time upgrade prompt (unless declined).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import TextIO

from codestrata.telemetry.consent import (
    TelemetrySessionConsent,
    allow_session_consent_from_interactive_prompt,
    default_session_consent,
    deny_session_consent_from_interactive_prompt,
)
from codestrata.telemetry.persisted_consent import (
    decline_v2_upgrade,
    persist_disabled,
    persist_v2_yes,
)
from codestrata.telemetry.prompt_eligibility import (
    PromptEligibilityReason,
    evaluate_prompt_eligibility,
)
from codestrata.telemetry.prompt_policy import (
    CommunityTelemetryInteractiveConsentPolicy,
    default_interactive_consent_policy,
)
from codestrata.telemetry.prompt_result import (
    InteractiveConsentPromptResult,
    default_skipped_prompt_result,
)

# Fresh-user v2 prompt (Slice 20.9).
PROMPT_INTRO = """\
Help improve CodeStrata?

Share anonymous usage and privacy-safe assessment insights.
Source code and repository identity stay local. This does not publish reports.
"""

PROMPT_QUESTION = "Help improve CodeStrata? [y/N]: "

# Legacy V1 → V2 upgrade (one-time unless declined).
UPGRADE_INTRO = """\
CodeStrata can also share privacy-safe assessment insights
(still no source code or repository identity; does not publish reports).
"""

UPGRADE_QUESTION = "Enable assessment insights? [y/N]: "

ALLOW_ANSWERS: frozenset[str] = frozenset({"y", "yes"})
DENY_ANSWERS: frozenset[str] = frozenset({"n", "no", ""})


class PromptAnswer(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    INVALID = "invalid"


def parse_prompt_answer(raw: str | None) -> PromptAnswer:
    """Parse a bounded answer. Only y/yes allow; empty/n/no deny; else invalid."""

    if raw is None:
        return PromptAnswer.DENY
    text = str(raw).strip().lower()
    if text in ALLOW_ANSWERS:
        return PromptAnswer.ALLOW
    if text in DENY_ANSWERS:
        return PromptAnswer.DENY
    return PromptAnswer.INVALID


def _read_line(input_func: Callable[[str], str], prompt: str) -> str:
    return input_func(prompt)


def _echo_factory(
    echo_func: Callable[[str], None] | None,
    stream: TextIO | None,
) -> Callable[[str], None]:
    if echo_func is not None:
        return echo_func

    def echo(message: str) -> None:
        target = stream
        if target is None:
            import sys

            target = sys.stderr
        try:
            target.write(message if message.endswith("\n") else message + "\n")
            target.flush()
        except Exception:
            return

    return echo


def run_interactive_consent_prompt(
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
    input_func: Callable[[str], str] | None = None,
    echo_func: Callable[[str], None] | None = None,
    stream: TextIO | None = None,
    preference_path: Path | None = None,
    persist: bool = True,
) -> InteractiveConsentPromptResult:
    """Evaluate eligibility and optionally prompt once for fresh v2 consent."""

    active = policy or default_interactive_consent_policy()
    eligibility = evaluate_prompt_eligibility(
        command=command,
        quiet=quiet,
        json_output=json_output,
        decision_already_explicit=decision_already_explicit,
        prompt_already_attempted=prompt_already_attempted,
        policy=active,
        stdin_interactive=stdin_interactive,
        automation_detected=automation_detected,
        output_interactive=output_interactive,
    )
    if not eligibility.eligible:
        ni = eligibility.non_interactive
        consent = ni.consent if ni is not None else default_session_consent()
        limitations = tuple(active.limitations)
        if ni is not None:
            limitations = tuple(sorted(set(limitations) | set(ni.limitation_codes)))
        return default_skipped_prompt_result(
            reason=eligibility.reason,
            limitations=limitations,
            consent=consent,
        )

    reader = input_func or input
    echo = _echo_factory(echo_func, stream)

    try:
        echo("")
        echo(PROMPT_INTRO.rstrip("\n"))
        echo("")
        raw = _read_line(reader, PROMPT_QUESTION)
    except EOFError:
        # Dismiss: no collection, leave preference UNDECIDED (do not persist No).
        consent = deny_session_consent_from_interactive_prompt(persisted=False)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="eof_dismissed",
            limitation_codes=active.limitations,
        )
    except KeyboardInterrupt:
        consent = deny_session_consent_from_interactive_prompt(persisted=False)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="interrupted_dismissed",
            limitation_codes=active.limitations,
        )
    except Exception:
        consent = default_session_consent()
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="prompt_failed_disabled",
            limitation_codes=active.limitations,
        )

    answer = parse_prompt_answer(raw)
    if answer is PromptAnswer.ALLOW:
        consent = allow_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            try:
                persist_v2_yes(path=preference_path)
            except Exception:
                pass
        outcome = "allowed_v2"
    elif answer is PromptAnswer.DENY:
        consent = deny_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            try:
                persist_disabled(path=preference_path)
            except Exception:
                pass
        outcome = "denied"
    else:
        # Invalid input: no accidental Yes; leave UNDECIDED (unconsented).
        consent = deny_session_consent_from_interactive_prompt(persisted=False)
        outcome = "invalid_dismissed"

    return InteractiveConsentPromptResult(
        eligibility=True,
        eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
        prompted=True,
        attempts=1,
        decision=consent.decision.value,
        decision_source=consent.source.value,
        consent=consent,
        safe_outcome=outcome,
        limitation_codes=active.limitations,
    )


def run_v2_upgrade_prompt(
    *,
    input_func: Callable[[str], str] | None = None,
    echo_func: Callable[[str], None] | None = None,
    stream: TextIO | None = None,
    preference_path: Path | None = None,
    persist: bool = True,
) -> InteractiveConsentPromptResult:
    """One-time V1→V2 upgrade prompt. Decline keeps V1_YES and stops nagging."""

    active = default_interactive_consent_policy()
    reader = input_func or input
    echo = _echo_factory(echo_func, stream)
    try:
        echo("")
        echo(UPGRADE_INTRO.rstrip("\n"))
        echo("")
        raw = _read_line(reader, UPGRADE_QUESTION)
    except (EOFError, KeyboardInterrupt):
        if persist:
            try:
                decline_v2_upgrade(path=preference_path)
            except Exception:
                pass
        consent = allow_session_consent_from_interactive_prompt(persisted=True)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="upgrade_declined",
            limitation_codes=active.limitations,
        )
    except Exception:
        consent = allow_session_consent_from_interactive_prompt(persisted=True)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="upgrade_prompt_failed_keep_v1",
            limitation_codes=active.limitations,
        )

    answer = parse_prompt_answer(raw)
    if answer is PromptAnswer.ALLOW:
        if persist:
            try:
                persist_v2_yes(path=preference_path)
            except Exception:
                pass
        consent = allow_session_consent_from_interactive_prompt(persisted=True)
        outcome = "upgrade_accepted_v2"
    else:
        if persist:
            try:
                decline_v2_upgrade(path=preference_path)
            except Exception:
                pass
        consent = allow_session_consent_from_interactive_prompt(persisted=True)
        outcome = "upgrade_declined"

    return InteractiveConsentPromptResult(
        eligibility=True,
        eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
        prompted=True,
        attempts=1,
        decision=consent.decision.value,
        decision_source=consent.source.value,
        consent=consent,
        safe_outcome=outcome,
        limitation_codes=active.limitations,
    )


__all__ = [
    "ALLOW_ANSWERS",
    "DENY_ANSWERS",
    "PROMPT_INTRO",
    "PROMPT_QUESTION",
    "UPGRADE_INTRO",
    "UPGRADE_QUESTION",
    "PromptAnswer",
    "parse_prompt_answer",
    "run_interactive_consent_prompt",
    "run_v2_upgrade_prompt",
]
