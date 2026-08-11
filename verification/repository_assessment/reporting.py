"""Privacy-safe reporting helpers for SV.4."""

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
    cleaned = _ABS.sub("<path>", cleaned)
    return cleaned


def report_contains_forbidden_leak(payload: dict[str, Any]) -> list[str]:
    blob = str(payload)
    leaks: list[str] = []
    # Return opaque codes only — never echo path prefixes back into the report.
    checks = (
        ("/Users/", "abs_users"),
        ("/home/", "abs_home"),
        ("/var/folders/", "abs_var_folders"),
        ("AKIA", "aws_key_prefix"),
        ("cscc_v1_", "community_token_prefix"),
        ("sk-", "openai_key_prefix"),
    )
    for needle, code in checks:
        if needle in blob:
            leaks.append(code)
    return leaks


def classify_assess_output(stdout: str, stderr: str, *, exit_code: int) -> dict[str, str]:
    combined = f"{stdout}\n{stderr}".lower()
    classes: dict[str, str] = {"exit": "zero" if exit_code == 0 else "nonzero"}
    if "traceback" in combined or "exception:" in combined:
        classes["safety"] = "traceback_present"
    else:
        classes["safety"] = "no_traceback"
    if "report.json" in combined or "assessment complete" in combined or "wrote" in combined:
        classes["assess"] = "completed_signal"
    if "configuration" in combined and ("missing" in combined or "not found" in combined):
        classes["config"] = "missing_or_invalid"
    if "permission" in combined or "read-only" in combined or "errno 13" in combined:
        classes["fs"] = "permission_denied"
    return classes
