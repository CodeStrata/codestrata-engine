"""Normalize report enum-like string values (Phase 5.12)."""

from __future__ import annotations

_SEVERITY_ALIASES = {
    "info": "informational",
    "informational": "informational",
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}
_PRIORITY_ALIASES = {
    # Customer-facing critical band aliases Immediate RecommendationPriority.
    "immediate": "critical",
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}
_EFFORT_ALIASES = {
    "xs": "xs",
    "extra_small": "xs",
    "s": "s",
    "small": "s",
    "m": "m",
    "medium": "m",
    "l": "l",
    "large": "l",
    "xl": "xl",
    "extra_large": "xl",
    "unknown": "unknown",
}
_RISK_ALIASES = {"high": "high", "medium": "medium", "low": "low"}
_CONFIDENCE_ALIASES = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "none": "none",
}


def normalize_severity(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return _SEVERITY_ALIASES.get(key, key)


def normalize_priority(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return _PRIORITY_ALIASES.get(key, key)


def normalize_effort(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower().replace("-", "_").replace(" ", "_")
    return _EFFORT_ALIASES.get(key, key)


def normalize_risk(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return _RISK_ALIASES.get(key, key)


def normalize_confidence(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return _CONFIDENCE_ALIASES.get(key, key)


def normalize_status(value: object) -> str:
    return str(getattr(value, "value", value)).strip().lower()
