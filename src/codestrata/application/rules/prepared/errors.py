"""Rejections for reviewed customer-package preparation and execution."""

from __future__ import annotations


class PreparedPackageError(ValueError):
    """Preparation or execution was rejected. Never a silent pass or a skipped package."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
