"""Shared helpers for graph-domain string and property validation."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def require_nonblank(value: str, *, label: str) -> str:
    """Return a stripped nonempty string or raise ``ValueError``."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    compact = value.strip()
    if not compact:
        raise ValueError(f"{label} must not be blank")
    return compact


def optional_nonblank(value: str | None, *, label: str) -> str | None:
    """Normalize an optional string; reject blank when provided."""

    if value is None:
        return None
    return require_nonblank(value, label=label)


def normalize_properties(value: object, *, label: str = "properties") -> Mapping[str, Any]:
    """Validate a JSON-compatible property mapping with nonempty keys."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} keys must be strings")
        compact = key.strip()
        if not compact:
            raise ValueError(f"{label} keys must not be blank")
        cleaned[compact] = item
    return MappingProxyType(cleaned)


def as_tuple(value: object) -> tuple[Any, ...]:
    """Coerce a sequence-like value to a tuple."""

    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError("expected a list or tuple")
