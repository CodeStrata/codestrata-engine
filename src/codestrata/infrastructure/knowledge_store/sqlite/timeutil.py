"""Shared timestamp helpers for SQLite knowledge adapters."""

from __future__ import annotations

from datetime import UTC, datetime


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_branch_key(branch: str | None) -> str:
    """Normalize branch for uniqueness; empty string represents null branch."""

    if branch is None:
        return ""
    return branch.strip()
