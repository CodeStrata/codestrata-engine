"""Process-level termination. Deadlines never rest on a callback alone."""

from __future__ import annotations

import multiprocessing
import time
from collections.abc import Callable
from multiprocessing.context import SpawnProcess
from typing import Any

from codestrata.application.rules.execution.worker import (
    evaluate_payload,
    hang_worker_main,
    worker_main,
)
from codestrata.domain.contracts.enums import JobProgressState, JobTerminalState
from codestrata.domain.contracts.invocation import (
    LocalJobCancellation,
    LocalJobProgress,
    LocalJobTerminal,
)
from codestrata.domain.contracts.models import BudgetLimits
from codestrata.domain.rules.deadlines import (
    DeadlineAction,
    next_deadline_action,
    regex_timeout_seconds,
)

POLL_SECONDS = 0.05


class IsolatedOutcome:
    def __init__(
        self,
        *,
        terminal: JobTerminalState,
        result: dict[str, Any] | None = None,
        reason: str | None = None,
        diagnostics: tuple[str, ...] = (),
    ) -> None:
        self.terminal = terminal
        self.result = result
        self.reason = reason
        self.diagnostics = diagnostics


def _spawn_context() -> multiprocessing.context.SpawnContext:
    return multiprocessing.get_context("spawn")


def terminate_process(proc: SpawnProcess) -> None:
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(timeout=1.0)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=1.0)


def run_isolated_evaluation(
    payload: dict[str, Any],
    *,
    budgets: BudgetLimits,
    hard_deadline_seconds: float | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    local_job_id: str = "local-eval",
) -> IsolatedOutcome:
    """Evaluate a compiled plan in a child process with hard kill.

    ``cancel_requested`` may be cooperative, but the supervisor still kills
    after grace / hard deadline even if the child never observes it.
    """

    deadline = (
        float(budgets.rule_hard_deadline_seconds)
        if hard_deadline_seconds is None
        else hard_deadline_seconds
    )
    ctx = _spawn_context()
    queue: multiprocessing.Queue[dict[str, Any]] = ctx.Queue()
    proc = ctx.Process(target=worker_main, args=(payload, queue))
    proc.start()
    started = time.monotonic()
    cancel_at: float | None = None
    progress = LocalJobProgress(
        local_job_id=local_job_id,
        state=JobProgressState.RUNNING,
        phase="evaluate",
    )
    _ = progress
    try:
        while proc.is_alive():
            elapsed = time.monotonic() - started
            requested = bool(cancel_requested and cancel_requested())
            grace_elapsed = None if cancel_at is None else time.monotonic() - cancel_at
            action = next_deadline_action(
                elapsed_seconds=elapsed,
                hard_deadline_seconds=deadline,
                cancel_requested=requested,
                grace_elapsed_seconds=grace_elapsed,
                grace_seconds=float(budgets.cancellation_grace_seconds),
            )
            if action is DeadlineAction.ENTER_GRACE:
                cancel_at = time.monotonic()
                _ = LocalJobCancellation(
                    local_job_id=local_job_id,
                    requested=True,
                    grace_seconds=budgets.cancellation_grace_seconds,
                    process_enforced_hard_cap=True,
                )
            elif action is DeadlineAction.KILL_HARD:
                terminate_process(proc)
                _ = LocalJobTerminal(
                    local_job_id=local_job_id,
                    terminal_state=JobTerminalState.KILLED,
                    successful=False,
                    failure_code="hard_deadline_exceeded",
                )
                return IsolatedOutcome(
                    terminal=JobTerminalState.KILLED,
                    reason="hard_deadline_exceeded",
                    diagnostics=("process_terminated", "hard_deadline_exceeded"),
                )
            elif action is DeadlineAction.KILL_GRACE:
                terminate_process(proc)
                _ = LocalJobTerminal(
                    local_job_id=local_job_id,
                    terminal_state=JobTerminalState.KILLED,
                    successful=False,
                    failure_code="cancelled_grace_exceeded",
                )
                return IsolatedOutcome(
                    terminal=JobTerminalState.KILLED,
                    reason="cancelled_grace_exceeded",
                    diagnostics=("process_terminated", "cancelled_grace_exceeded"),
                )
            proc.join(timeout=POLL_SECONDS)
        raw = _drain_queue(queue)
        if raw is None or not raw.get("ok"):
            reason = "worker_failed" if raw is None else str(raw.get("reason") or "worker_failed")
            _ = LocalJobTerminal(
                local_job_id=local_job_id,
                terminal_state=JobTerminalState.FAILED,
                successful=False,
                failure_code=reason,
            )
            return IsolatedOutcome(terminal=JobTerminalState.FAILED, reason=reason)
        _ = LocalJobTerminal(
            local_job_id=local_job_id,
            terminal_state=JobTerminalState.COMPLETED,
            successful=True,
        )
        return IsolatedOutcome(terminal=JobTerminalState.COMPLETED, result=raw["result"])
    finally:
        if proc.is_alive():
            terminate_process(proc)


def run_hang_until_killed(*, budgets: BudgetLimits, local_job_id: str = "hang") -> IsolatedOutcome:
    """Prove a non-cooperative child is killed after cancellation grace."""

    ctx = _spawn_context()
    queue: multiprocessing.Queue[dict[str, Any]] = ctx.Queue()
    proc = ctx.Process(target=hang_worker_main, args=(queue,))
    proc.start()
    started = time.monotonic()
    try:
        while proc.is_alive():
            elapsed = time.monotonic() - started
            action = next_deadline_action(
                elapsed_seconds=elapsed,
                hard_deadline_seconds=float(budgets.rule_hard_deadline_seconds),
                cancel_requested=True,
                grace_elapsed_seconds=elapsed,
                grace_seconds=float(budgets.cancellation_grace_seconds),
            )
            if action in {DeadlineAction.KILL_GRACE, DeadlineAction.KILL_HARD}:
                terminate_process(proc)
                reason = (
                    "hard_deadline_exceeded"
                    if action is DeadlineAction.KILL_HARD
                    else "cancelled_grace_exceeded"
                )
                return IsolatedOutcome(
                    terminal=JobTerminalState.KILLED,
                    reason=reason,
                    diagnostics=("process_terminated", reason),
                )
            proc.join(timeout=POLL_SECONDS)
        return IsolatedOutcome(terminal=JobTerminalState.FAILED, reason="hang_exited")
    finally:
        if proc.is_alive():
            terminate_process(proc)


def regex_isolated_deadline(budgets: BudgetLimits) -> float:
    return min(float(budgets.rule_hard_deadline_seconds), regex_timeout_seconds(budgets))


def in_process_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Same operators as the worker, used only after isolation is proven.

    Preview/production parity still goes through this function's operator
    path; process isolation wraps it for catalog execution.
    """

    return evaluate_payload(payload)


def _drain_queue(queue: multiprocessing.Queue[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        return queue.get_nowait()
    except Exception:  # noqa: BLE001 — empty queue after kill
        try:
            return queue.get(timeout=0.2)
        except Exception:  # noqa: BLE001
            return None
