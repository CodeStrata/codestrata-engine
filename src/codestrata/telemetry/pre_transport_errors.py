"""Bounded pre-transport privacy error taxonomy (Slice 9.10).

Never carries offending values, exception text, or stack traces.
"""

from __future__ import annotations

from enum import StrEnum


class PreTransportReasonCode(StrEnum):
    """Safe reason codes for gate rejection/failure — never echo inputs."""

    ACCEPTED = "accepted"
    INVALID_EVENT_TYPE = "invalid_event_type"
    UNSUPPORTED_EVENT_SCHEMA = "unsupported_event_schema"
    UNSUPPORTED_RUNTIME_POLICY = "unsupported_runtime_policy"
    CATALOG_EVENT_MISSING = "catalog_event_missing"
    CATALOG_FIELD_MISSING = "catalog_field_missing"
    CATALOG_ENUM_MISMATCH = "catalog_enum_mismatch"
    CATALOG_MISMATCH = "catalog_mismatch"
    FORBIDDEN_FIELD_NAME = "forbidden_field_name"
    UNKNOWN_FIELD = "unknown_field"
    UNSAFE_FIELD_VALUE = "unsafe_field_value"
    INVALID_EVENT_COMBINATION = "invalid_event_combination"
    TOO_MANY_FIELDS = "too_many_fields"
    EVENT_TOO_LARGE = "event_too_large"
    NONCANONICAL_SERIALIZATION = "noncanonical_serialization"
    INTERNAL_PRIVACY_FAILURE = "internal_privacy_failure"


class PreTransportPrivacyStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INVALID_TYPE = "invalid_type"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    UNSUPPORTED_POLICY = "unsupported_policy"
    CATALOG_MISMATCH = "catalog_mismatch"
    UNSAFE_FIELD = "unsafe_field"
    UNSAFE_VALUE = "unsafe_value"
    EVENT_TOO_LARGE = "event_too_large"
    FIELD_LIMIT_EXCEEDED = "field_limit_exceeded"
    INVALID_EVENT_COMBINATION = "invalid_event_combination"
    INTERNAL_FAILURE = "internal_failure"


__all__ = [
    "PreTransportPrivacyStatus",
    "PreTransportReasonCode",
]
