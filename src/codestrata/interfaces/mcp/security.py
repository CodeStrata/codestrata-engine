"""Sanitize MCP inputs and redact sensitive values from responses."""

from __future__ import annotations

import re
from typing import Any

from codestrata.ai.providers.parsing import sanitize_provider_text

_MAX_IDENTIFIER_LENGTH = 512
_MAX_FILTER_LENGTH = 128
_CREDENTIAL_URL = re.compile(r"(https?://)[^/@\s]+@", re.IGNORECASE)


def require_nonblank(value: str, *, label: str) -> str:
    compact = value.strip()
    if not compact:
        raise ValueError(f"{label} must be a nonempty string")
    if len(compact) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{label} exceeds maximum length {_MAX_IDENTIFIER_LENGTH}")
    return compact


def optional_filter(value: str | None, *, label: str) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if not compact:
        return None
    if len(compact) > _MAX_FILTER_LENGTH:
        raise ValueError(f"{label} exceeds maximum length {_MAX_FILTER_LENGTH}")
    return compact


def sanitize_error_message(message: str) -> str:
    """Bound and redact credentials/paths from error text."""

    text = sanitize_provider_text(message)
    text = _CREDENTIAL_URL.sub(r"\1***@", text)
    if len(text) > 500:
        text = text[:497] + "..."
    return text


def redact_mapping(payload: Any) -> Any:
    """Recursively drop keys that look like secrets or absolute paths."""

    blocked = {
        "blob_ref",
        "manifest_blob_ref",
        "absolute_path",
        "local_path",
        "filesystem_path",
        "aws_access_key_id",
        "aws_secret_access_key",
        "token",
        "password",
        "authorization",
    }
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if key in blocked or key.endswith("_blob_ref") or key.endswith("_blob_hash"):
                continue
            if isinstance(value, str) and _looks_like_absolute_path(value):
                if key in {"output_reference", "path", "excerpt"}:
                    result[key] = value
                continue
            result[key] = redact_mapping(value)
        return result
    if isinstance(payload, list):
        return [redact_mapping(item) for item in payload]
    if isinstance(payload, tuple):
        return [redact_mapping(item) for item in payload]
    return payload


def _looks_like_absolute_path(value: str) -> bool:
    if value.startswith("/") and not value.startswith("//") and "://" not in value:
        return True
    if len(value) > 2 and value[1] == ":" and value[0].isalpha():
        return True
    return False
