"""Shared fixtures for SV.11.8 — synthetic only, no network or credentials."""

from __future__ import annotations

from typing import Any

from codestrata.config.settings import CodestrataSettings


def settings_for(provider: str) -> CodestrataSettings:
    return CodestrataSettings.model_validate(
        {"repository": {"path": "."}, "ai": {"provider": provider}}
    )


def default_settings() -> CodestrataSettings:
    return CodestrataSettings.model_validate({"repository": {"path": "."}})


def is_same_class(instance: Any, expected: type) -> bool:
    actual = type(instance)
    return (actual.__module__, actual.__name__) == (expected.__module__, expected.__name__)


__all__ = ["default_settings", "is_same_class", "settings_for"]
