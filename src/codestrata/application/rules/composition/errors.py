"""Typed failures for pinned RuleSet composition (E04.1)."""

from __future__ import annotations


class ResolutionError(ValueError):
    """RuleSet composition was rejected. Never a silent inherit or fetch."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
