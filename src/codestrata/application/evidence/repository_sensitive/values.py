"""Sensitive-value redaction and placeholder classification."""

from __future__ import annotations

import re

from codestrata.domain.evidence.repository_sensitive.enums import (
    PlaceholderStatus,
    ValueKind,
)
from codestrata.domain.evidence.repository_sensitive.identifiers import fingerprint_value

REDACTED_PREVIEW = "[REDACTED]"

_PLACEHOLDER_LITERALS = frozenset(
    {
        "changeme",
        "password",
        "secret",
        "example",
        "sample",
        "dummy",
        "test",
        "your_api_key",
        "replace_me",
        "<replace-me>",
        "xxx",
        "todo",
        "fixme",
        "none",
        "null",
        "n/a",
    }
)

_ENV_INTERPOLATION = re.compile(
    r"^\$\{[A-Za-z_][A-Za-z0-9_]*(?::[^}]*)?\}$|^\$[A-Za-z_][A-Za-z0-9_]*$"
)
_URL_LIKE = re.compile(r"(?i)^(https?|jdbc|amqp|mongodb|redis)://")
# GitHub Actions / Azure DevOps secret *references* — not secret bodies.
_CI_SECRET_EXPRESSION = re.compile(
    r"^\$\{\{\s*(secrets\.|steps\.[^}]+\.outputs\.)[^}]*\}\}$|"
    r"^\$\([\w.-]*(password|token|secret|key)[\w.-]*\)$",
    re.IGNORECASE,
)


def is_ci_secret_expression(value: str) -> bool:
    """Return True when value is a CI vault/OIDC expression, not a secret body."""

    return bool(_CI_SECRET_EXPRESSION.match(value.strip()))


def classify_placeholder(value: str) -> tuple[PlaceholderStatus, str | None, ValueKind]:
    text = value.strip()
    if not text:
        return PlaceholderStatus.EMPTY, "empty", ValueKind.EMPTY
    lower = text.lower()
    if _ENV_INTERPOLATION.match(text):
        return (
            PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
            "environment_variable",
            ValueKind.ENVIRONMENT_REFERENCE,
        )
    # CI vault/OIDC expressions reference secrets by name — not secret bodies.
    if is_ci_secret_expression(text):
        return (
            PlaceholderStatus.ENVIRONMENT_INTERPOLATION,
            "ci_secret_expression",
            ValueKind.ENVIRONMENT_REFERENCE,
        )
    if lower in _PLACEHOLDER_LITERALS or lower.startswith("your_"):
        return PlaceholderStatus.PLACEHOLDER_LITERAL, lower, ValueKind.PLACEHOLDER
    if text.startswith("<") and text.endswith(">"):
        return PlaceholderStatus.PLACEHOLDER_LITERAL, "angle_bracket", ValueKind.PLACEHOLDER
    if lower in {"true", "false", "yes", "no", "on", "off"}:
        return PlaceholderStatus.NOT_APPLICABLE, None, ValueKind.BOOLEAN
    if _URL_LIKE.match(text):
        return PlaceholderStatus.NOT_APPLICABLE, None, ValueKind.URL
    return PlaceholderStatus.NOT_APPLICABLE, None, ValueKind.LITERAL


def redact_preview(value: str, *, sensitive: bool = True) -> str:
    """Return a safe preview. Never returns the complete sensitive value.

    Always returns a nonempty token so evidence models that require
    ``redacted_preview`` can accept empty configuration literals.

    CI secret *expressions* (``${{ secrets.* }}``, pipeline macros) are not
    secret bodies — preserve them so downstream context classification can
    demote severity without weakening detectors.
    """

    if not value.strip():
        return "[EMPTY]"
    if is_ci_secret_expression(value):
        compact = value.strip()
        if len(compact) <= 96:
            return compact
        return f"{compact[:40]}…{compact[-12:]}"
    if not sensitive:
        # Still bound length for non-sensitive flags/URLs.
        compact = value.strip()
        if len(compact) <= 64:
            return compact
        return f"{compact[:20]}…{compact[-8:]}"
    return REDACTED_PREVIEW


def value_facts(value: str, *, sensitive: bool = True) -> dict[str, object]:
    """Return redacted facts for a literal value (never the raw value)."""

    placeholder_status, placeholder_kind, value_kind = classify_placeholder(value)
    fingerprint = fingerprint_value(value) if value else None
    return {
        "redacted_preview": redact_preview(value, sensitive=sensitive),
        "value_fingerprint": fingerprint,
        "value_length": len(value),
        "value_kind": value_kind,
        "placeholder_status": placeholder_status,
        "placeholder_kind": placeholder_kind,
        "is_empty": not bool(value.strip()),
    }
