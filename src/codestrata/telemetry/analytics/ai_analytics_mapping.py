"""AI analytics mapping: provider/model → bounded families (Slice 10.6).

Never echoes raw provider or model identifiers in errors.
"""

from __future__ import annotations

import re

from codestrata.telemetry.analytics.ai_analytics_catalogs import (
    APPROVED_AI_CAPABILITIES,
    APPROVED_AI_MODEL_FAMILIES,
    APPROVED_AI_PROVIDER_FAMILIES,
    _CAPABILITY_ALIASES,
    _PROVIDER_ALIASES,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode

# Exact-ID shapes that must never pass as families (synthetic public naming forms).
_RAW_MODEL_ID_MARKERS: tuple[str, ...] = (
    ":",  # Bedrock-style amazon.nova-lite-v1:0
    "/",
    "@",
    "arn:",
)

_GPT_FAMILY_RE = re.compile(r"^gpt-[0-9a-z.-]+$", re.IGNORECASE)
_NOVA_FAMILY_RE = re.compile(
    r"^amazon\.nova-[a-z0-9.-]+(:[0-9a-z.-]+)?$", re.IGNORECASE
)


def canonicalize_capability(value: str) -> str:
    key = value.strip().lower()
    mapped = _CAPABILITY_ALIASES.get(key)
    if mapped is None or mapped not in APPROVED_AI_CAPABILITIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_CAPABILITY)
    return mapped


def map_provider_to_family(provider: str) -> str:
    """Map Engine registry provider ID or family token → provider_family."""

    key = provider.strip().lower()
    if key in APPROVED_AI_PROVIDER_FAMILIES:
        return key
    mapped = _PROVIDER_ALIASES.get(key)
    if mapped is None:
        # High-cardinality / host-like values are raw identifiers.
        if any(marker in key for marker in (".", "://", "/", "@")):
            raise AnalyticsError(AnalyticsErrorCode.RAW_PROVIDER_IDENTIFIER_REJECTED)
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_FAMILY)
    return mapped


def map_model_id_to_family(model_id: str) -> str:
    """Map a known Engine default model ID shape → model_family.

    Unrecognized exact IDs are rejected (never coerced to other_supported).
    """

    raw = model_id.strip()
    key = raw.lower()
    if key in APPROVED_AI_MODEL_FAMILIES:
        return key
    if key in {"unavailable", "none", ""}:
        if key == "unavailable":
            return "unavailable"
        raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)

    if _NOVA_FAMILY_RE.match(raw):
        return "amazon_nova_family"
    if _GPT_FAMILY_RE.match(raw):
        return "gpt_family"

    # Reject ARN / deployment / dated exact IDs that are not explicitly mapped.
    if any(marker in key for marker in _RAW_MODEL_ID_MARKERS) or len(key) > 64:
        raise AnalyticsError(AnalyticsErrorCode.RAW_MODEL_IDENTIFIER_REJECTED)
    raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)


def assert_not_raw_provider_family(value: str) -> str:
    if value not in APPROVED_AI_PROVIDER_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_PROVIDER_FAMILY)
    return value


def assert_not_raw_model_family(value: str) -> str:
    if value not in APPROVED_AI_MODEL_FAMILIES:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_MODEL_FAMILY)
    return value


__all__ = [
    "assert_not_raw_model_family",
    "assert_not_raw_provider_family",
    "canonicalize_capability",
    "map_model_id_to_family",
    "map_provider_to_family",
]
