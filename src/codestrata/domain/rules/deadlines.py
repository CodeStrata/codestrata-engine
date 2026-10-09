"""Process-enforced deadline arithmetic from E01.1 budgets.

Elapsed-time decisions live here so a cooperative in-process callback cannot
be the only stop condition. Application code still has to terminate a process.
"""

from __future__ import annotations

from enum import StrEnum

from codestrata.domain.contracts.models import BudgetLimits


class DeadlineAction(StrEnum):
    WAIT = "wait"
    ENTER_GRACE = "enter_grace"
    KILL_GRACE = "kill_grace"
    KILL_HARD = "kill_hard"


def budgets_require_process_cap(budgets: BudgetLimits) -> None:
    if not budgets.process_enforced_hard_cap:
        raise ValueError("cancellation cannot depend solely on a cooperative callback")
    if not budgets.cooperative_callback_only_forbidden:
        raise ValueError("cooperative-callback-only deadlines are forbidden")
    if budgets.rule_hard_deadline_seconds <= 0:
        raise ValueError("rule_hard_deadline_seconds must be positive")
    if budgets.cancellation_grace_seconds < 0:
        raise ValueError("cancellation_grace_seconds must be nonnegative")


def regex_timeout_seconds(budgets: BudgetLimits) -> float:
    return budgets.regex_match_timeout_milliseconds / 1000.0


def next_deadline_action(
    *,
    elapsed_seconds: float,
    hard_deadline_seconds: float,
    cancel_requested: bool,
    grace_elapsed_seconds: float | None,
    grace_seconds: float,
) -> DeadlineAction:
    if elapsed_seconds >= hard_deadline_seconds:
        return DeadlineAction.KILL_HARD
    if cancel_requested:
        if grace_elapsed_seconds is None:
            return DeadlineAction.ENTER_GRACE
        if grace_elapsed_seconds >= grace_seconds:
            return DeadlineAction.KILL_GRACE
    return DeadlineAction.WAIT
