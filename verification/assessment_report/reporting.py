"""Privacy-safe reporting helpers for SV.5."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ABS = re.compile(
    r"(/var/folders/[^\s\"']+|/tmp/[^\s\"']+|/Users/[^\s\"']+|/home/[^\s\"']+"
    r"|[A-Za-z]:\\[^\s\"']+)"
)


def sanitize_text(text: str, *, workspace: Path | None = None) -> str:
    cleaned = text
    if workspace is not None:
        cleaned = cleaned.replace(str(workspace), "<workspace>")
        cleaned = cleaned.replace(workspace.as_posix(), "<workspace>")
    return _ABS.sub("<path>", cleaned)


def report_contains_forbidden_leak(payload: dict[str, Any]) -> list[str]:
    blob = str(payload)
    leaks: list[str] = []
    checks = (
        ("/Users/", "abs_users"),
        ("/home/", "abs_home"),
        ("/var/folders/", "abs_var_folders"),
        ("AKIA", "aws_key_prefix"),
        ("cscc_v1_", "community_token_prefix"),
        ("sk-", "openai_key_prefix"),
        ("-----BEGIN ", "pem_header"),
    )
    for needle, code in checks:
        if needle in blob:
            leaks.append(code)
    return leaks
