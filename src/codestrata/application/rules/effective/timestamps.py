"""ISO-8601 timestamps for exception/package validity. Clock stays in execution context."""

from __future__ import annotations

from datetime import UTC, datetime

from codestrata.application.rules.effective.errors import EffectiveSealError


def parse_utc(value: str, *, label: str) -> datetime:
    text = value.strip()
    if not text:
        raise EffectiveSealError("invalid_timestamp", f"{label} must not be blank")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise EffectiveSealError(
            "invalid_timestamp",
            f"{label} must be an ISO-8601 timestamp",
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def not_after_exceeds(candidate: str, limit: str) -> bool:
    return parse_utc(candidate, label="expiry") > parse_utc(limit, label="exception validity")
