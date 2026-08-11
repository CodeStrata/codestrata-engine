"""Anonymous installation identity errors (Epic 10 Slice 10.2)."""

from __future__ import annotations

from enum import StrEnum


class InstallationIdentityErrorCode(StrEnum):
    """Bounded safe error codes — never paths, IDs, or exception text."""

    VALIDATION_FAILED = "validation_failed"
    CORRUPT_RECORD = "corrupt_record"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    UNSUPPORTED_POLICY = "unsupported_policy"
    INVALID_IDENTIFIER = "invalid_identifier"
    PERSISTENCE_FAILED = "persistence_failed"
    RECOVERY_DISABLED = "recovery_disabled"
    INTERNAL = "internal"


class InstallationIdentityError(Exception):
    """Bounded identity failure carrying a safe code only."""

    def __init__(self, code: InstallationIdentityErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


__all__ = ["InstallationIdentityError", "InstallationIdentityErrorCode"]
