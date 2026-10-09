"""Graceful and hard-stop supervision for local release/container runs."""

from __future__ import annotations

import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from codestrata.application.release.standalone.policy import load_headless_runtime_limits


@dataclass(frozen=True, slots=True)
class SupervisedRunOutcome:
    exit_code: int | None
    terminated_by: str | None
    grace_elapsed_seconds: float | None
    cleaned_up: bool


def _grace_seconds() -> float:
    limits = load_headless_runtime_limits().get("cancellation")
    if isinstance(limits, dict):
        return float(limits.get("grace_seconds") or 2)
    return 2.0


def run_with_signal_supervision(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    send_signal: int = signal.SIGTERM,
    wait_before_signal: float = 0.05,
) -> SupervisedRunOutcome:
    """Start ``command``, deliver ``send_signal``, then hard-kill after grace."""

    grace = _grace_seconds()
    proc = subprocess.Popen(  # noqa: S603
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(wait_before_signal)
    if proc.poll() is not None:
        return SupervisedRunOutcome(
            exit_code=proc.returncode,
            terminated_by=None,
            grace_elapsed_seconds=None,
            cleaned_up=True,
        )
    proc.send_signal(send_signal)
    started = time.monotonic()
    try:
        proc.wait(timeout=grace)
        elapsed = time.monotonic() - started
        return SupervisedRunOutcome(
            exit_code=proc.returncode,
            terminated_by=signal.Signals(send_signal).name,
            grace_elapsed_seconds=elapsed,
            cleaned_up=True,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1.0)
        elapsed = time.monotonic() - started
        return SupervisedRunOutcome(
            exit_code=proc.returncode,
            terminated_by="hard_kill",
            grace_elapsed_seconds=elapsed,
            cleaned_up=True,
        )
