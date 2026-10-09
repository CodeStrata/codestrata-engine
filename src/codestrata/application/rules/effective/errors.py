"""Typed failures for Effective RuleSet sealing and candidate admission (E04.3)."""

from __future__ import annotations


class EffectiveSealError(ValueError):
    """Sealing, admission or candidate execution was rejected. Never a silent pass."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
