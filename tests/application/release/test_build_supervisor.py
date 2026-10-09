"""E14.2 signal grace and hard-stop supervision."""

from __future__ import annotations

import signal
import sys

from codestrata.application.release.standalone.supervisor import run_with_signal_supervision


def test_sigterm_grace_then_hard_kill() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    outcome = run_with_signal_supervision(
        command,
        send_signal=signal.SIGTERM,
        wait_before_signal=0.1,
    )
    assert outcome.cleaned_up is True
    assert outcome.terminated_by in {"SIGTERM", "hard_kill"}
    assert outcome.grace_elapsed_seconds is not None
