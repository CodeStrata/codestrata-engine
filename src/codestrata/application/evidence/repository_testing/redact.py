"""Shared secret redaction for command projections."""

from __future__ import annotations

import re

_SECRET_ASSIGN = re.compile(
    r"(?i)\b(TOKEN|PASSWORD|SECRET|API_KEY)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)"
)


def redact_command_projection(command: str) -> str:
    """Redact TOKEN=/PASSWORD=/SECRET=/API_KEY= values to ***."""

    redacted = _SECRET_ASSIGN.sub(
        lambda match: f"{match.group(1)}=***",
        command.strip(),
    )
    return redacted[:400]
