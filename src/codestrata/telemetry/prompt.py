"""Legacy telemetry prompt entry (welcome/landing).

Slice 9.4: interactive consent is handled by
``ensure_interactive_product_telemetry`` on eligible product commands (assess).
This legacy helper remains a no-op so welcome/landing never prompt.
"""

from __future__ import annotations

from typing import Any


def maybe_prompt_telemetry_opt_in(
    *,
    service: Any = None,
    quiet: bool = False,
    json_output: bool = False,
) -> None:
    """No-op — welcome/landing and non-assess paths must not prompt."""

    _ = (service, quiet, json_output)
    return


def sys_stdin_is_tty() -> bool:
    import sys

    return bool(getattr(sys.stdin, "isatty", lambda: False)())


__all__ = ["maybe_prompt_telemetry_opt_in", "sys_stdin_is_tty"]
