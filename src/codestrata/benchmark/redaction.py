"""AI metric redaction helpers — never retain prompts, responses, or secrets."""

from __future__ import annotations

from typing import Any

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "authorization",
        "aws_secret_access_key",
        "aws_session_token",
        "prompt",
        "response",
        "messages",
        "content",
    }
)


def redact_ai_metrics(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of AI metrics with secret-bearing keys removed."""

    if not raw:
        return {
            "enabled": False,
            "unavailable": True,
            "reason": "not_requested",
        }
    cleaned: dict[str, Any] = {}
    for key, value in raw.items():
        lowered = key.lower()
        if lowered in _SECRET_KEYS or any(part in lowered for part in _SECRET_KEYS):
            continue
        if isinstance(value, dict):
            cleaned[key] = redact_ai_metrics(value)
        else:
            cleaned[key] = value
    return cleaned
