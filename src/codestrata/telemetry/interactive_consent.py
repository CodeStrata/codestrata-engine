"""Interactive telemetry consent prompt (Slice 19.4).

Asks once when preference is undecided. Explicit Yes/No is persisted locally.
Default Enter = No. Never prompts in CI/non-interactive contexts.
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
from codestrata.telemetry.persisted_consent import persist_preference
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

PROMPT_INTRO = """\
Help improve CodeStrata by sharing anonymous usage and assessment metadata.
No source code, repository names, file paths, findings, or credentials are sent.
"""

PROMPT_QUESTION = "Share anonymous telemetry? [y/N]: "

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


def _persist_answer(enabled: bool, *, path: Path | None) -> None:
    try:
        persist_preference(enabled, path=path)
    except Exception:
        # Preference write failures must never block assessment.
        return


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
    """Evaluate eligibility and optionally prompt once. Never raises to callers."""

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
    echo = echo_func
    if echo is None:

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

    try:
        echo("")
        echo(PROMPT_INTRO.rstrip("\n"))
        echo("")
        raw = _read_line(reader, PROMPT_QUESTION)
    except EOFError:
        consent = deny_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            _persist_answer(False, path=preference_path)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="eof_denied",
            limitation_codes=active.limitations,
        )
    except KeyboardInterrupt:
        # Telemetry is optional: treat interrupt as denial and continue product work.
        consent = deny_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            _persist_answer(False, path=preference_path)
        return InteractiveConsentPromptResult(
            eligibility=True,
            eligibility_reason=PromptEligibilityReason.ELIGIBLE.value,
            prompted=True,
            attempts=1,
            decision=consent.decision.value,
            decision_source=consent.source.value,
            consent=consent,
            safe_outcome="interrupted_denied",
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
    # One attempt only: invalid → deny (no indefinite retry).
    if answer is PromptAnswer.ALLOW:
        consent = allow_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            _persist_answer(True, path=preference_path)
        outcome = "allowed"
    else:
        consent = deny_session_consent_from_interactive_prompt(persisted=persist)
        if persist:
            _persist_answer(False, path=preference_path)
        outcome = "denied" if answer is PromptAnswer.DENY else "invalid_denied"

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
    "PromptAnswer",
    "parse_prompt_answer",
    "run_interactive_consent_prompt",
]
