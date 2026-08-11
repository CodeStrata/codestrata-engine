"""Anonymous analytics error taxonomy (Epic 10 Slice 10.1)."""

from __future__ import annotations

from enum import StrEnum


class AnalyticsErrorCode(StrEnum):
    """Bounded safe error codes — never exception text or payloads."""

    VALIDATION_FAILED = "validation_failed"
    UNKNOWN_FIELD = "unknown_field"
    UNSAFE_FIELD = "unsafe_field"
    UNSAFE_VALUE = "unsafe_value"
    UNKNOWN_CATEGORY = "unknown_category"
    EVENT_TOO_LARGE = "event_too_large"
    INCOMPATIBLE_SCHEMA = "incompatible_schema"
    PRIVACY_REQUIRED = "privacy_required"
    PRIVACY_REJECTED = "privacy_rejected"
    COLLECTION_DISABLED = "collection_disabled"
    PERSISTENCE_DISABLED = "persistence_disabled"
    TRANSMISSION_DISABLED = "transmission_disabled"
    INVALID_COMMAND_CATEGORY = "invalid_command_category"
    INVALID_DURATION_BUCKET = "invalid_duration_bucket"
    INVALID_OUTCOME = "invalid_outcome"
    INVALID_FAILURE_CATEGORY = "invalid_failure_category"
    INVALID_HEAD = "invalid_head"
    TOO_MANY_HEADS = "too_many_heads"
    OUTCOME_FAILURE_MISMATCH = "outcome_failure_mismatch"
    IDENTITY_UNAVAILABLE = "identity_unavailable"
    INVALID_LANGUAGE_GROUP = "invalid_language_group"
    DUPLICATE_LANGUAGE_GROUP = "duplicate_language_group"
    INVALID_LANGUAGE_COUNT = "invalid_language_count"
    LANGUAGE_COUNT_EXCEEDED = "language_count_exceeded"
    INVALID_RULE_COUNT = "invalid_rule_count"
    INCONSISTENT_RULE_COUNTS = "inconsistent_rule_counts"
    DUPLICATE_HEAD = "duplicate_head"
    INVALID_CAPABILITY = "invalid_capability"
    INVALID_PROVIDER_FAMILY = "invalid_provider_family"
    INVALID_MODEL_FAMILY = "invalid_model_family"
    INVALID_PROVIDER_OWNERSHIP = "invalid_provider_ownership"
    INVALID_TOKEN_BUCKET = "invalid_token_bucket"
    INVALID_TOOL_USAGE = "invalid_tool_usage"
    RAW_MODEL_IDENTIFIER_REJECTED = "raw_model_identifier_rejected"
    RAW_PROVIDER_IDENTIFIER_REJECTED = "raw_provider_identifier_rejected"
    INCOMPATIBLE_CATALOG = "incompatible_catalog"
    INTERNAL = "internal"


class AnalyticsError(Exception):
    """Bounded analytics contract failure carrying a safe code only."""

    def __init__(self, code: AnalyticsErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


__all__ = ["AnalyticsError", "AnalyticsErrorCode"]
