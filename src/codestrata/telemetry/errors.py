"""Telemetry runtime error taxonomy (Slice 9.1)."""

from __future__ import annotations

from enum import StrEnum


class TelemetryRuntimeErrorCode(StrEnum):
    """Bounded safe error codes — never exception text."""

    VALIDATION_FAILED = "validation_failed"
    PRIVACY_REJECTED = "privacy_rejected"
    EVENT_TOO_LARGE = "event_too_large"
    UNKNOWN_FIELD = "unknown_field"
    UNSAFE_FIELD = "unsafe_field"
    UNSAFE_VALUE = "unsafe_value"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    DISABLED = "disabled"
    INTERNAL = "internal"


class TelemetryRuntimeError(Exception):
    """Bounded telemetry runtime failure carrying a safe code only."""

    def __init__(self, code: TelemetryRuntimeErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


__all__ = ["TelemetryRuntimeError", "TelemetryRuntimeErrorCode"]
