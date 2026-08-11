"""Privacy-safe reporting helpers for SV.3."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ABS = re.compile(
    r"(/var/folders/[^\s\"']+|/tmp/[^\s\"']+|/Users/[^\s\"']+|/home/[^\s\"']+"
    r"|[A-Za-z]:\\[^\s\"']+)"
)


def sanitize_text(text: str, *, workspace: Path | None = None) -> str:
    """Remove absolute/temp/user paths from captured output."""

    cleaned = text
    if workspace is not None:
        cleaned = cleaned.replace(str(workspace), "<workspace>")
        cleaned = cleaned.replace(workspace.as_posix(), "<workspace>")
    cleaned = _ABS.sub("<path>", cleaned)
    return cleaned


def classify_output(stdout: str, stderr: str, *, exit_code: int) -> dict[str, str]:
    """Semantic classification of CLI output (no raw dumps of secrets)."""

    combined = f"{stdout}\n{stderr}".lower()
    classes: dict[str, str] = {"exit": "zero" if exit_code == 0 else "nonzero"}
    if "success: configuration ready" in combined:
        classes["init"] = "success"
    if "already exists" in combined:
        classes["init"] = "existing_config_refused"
    if "failed to write" in combined or "file exists" in combined or "errno" in combined:
        classes["init"] = classes.get("init", "write_failed")
    if "all doctor checks passed" in combined:
        classes["doctor"] = "passed"
    if "[fail]" in combined and "doctor" not in classes:
        classes["doctor"] = "failed"
    if "traceback" in combined or "exception:" in combined:
        classes["safety"] = "traceback_present"
    else:
        classes["safety"] = "no_traceback"
    return classes


def command_record(
    name: str,
    argv: list[str],
    *,
    exit_code: int,
    classifications: dict[str, str],
    detail: str,
) -> dict[str, Any]:
    # Never store raw stdout/stderr bodies in the report.
    return {
        "name": name,
        "argv": [sanitize_text(part) for part in argv],
        "exit_code": exit_code,
        "classifications": dict(sorted(classifications.items())),
        "detail": sanitize_text(detail),
    }


def report_contains_forbidden_leak(payload: dict[str, Any]) -> list[str]:
    blob = str(payload)
    leaks: list[str] = []
    for needle in ("/Users/", "/home/", "/var/folders/", "AKIA", "cscc_v1_"):
        if needle in blob:
            leaks.append(needle)
    return leaks
