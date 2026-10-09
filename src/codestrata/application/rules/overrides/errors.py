"""Typed failures for policy overrides and scoped exceptions (E04.2)."""

from __future__ import annotations


class OverrideError(ValueError):
    """Override or exception application was rejected. Never a silent merge."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
