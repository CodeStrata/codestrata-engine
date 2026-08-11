"""Bounded AI analytics catalogs (Epic 10 Slice 10.6).

Engine-local closed vocabularies aligned conceptually with Community Cloud AI
usage catalogs. Does not import Platform runtime modules.
"""

from __future__ import annotations

AI_ANALYTICS_CAPABILITY_CATALOG_VERSION = "1.0"
AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION = "1.0"
AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION = "1.0"

APPROVED_AI_CAPABILITIES: frozenset[str] = frozenset({"modernization_advisor"})

APPROVED_AI_PROVIDER_FAMILIES: frozenset[str] = frozenset(
    {"aws_bedrock", "openai", "openrouter", "unavailable"}
)

APPROVED_AI_MODEL_FAMILIES: frozenset[str] = frozenset(
    {"amazon_nova_family", "gpt_family", "unavailable"}
)

APPROVED_AI_PROVIDER_OWNERSHIPS: frozenset[str] = frozenset(
    {"customer_managed", "codestrata_managed", "unavailable"}
)

APPROVED_AI_OUTCOMES: frozenset[str] = frozenset(
    {"success", "failure", "unavailable", "skipped"}
)

APPROVED_AI_FAILURE_CATEGORIES: frozenset[str] = frozenset(
    {
        "authentication_failed",
        "timeout",
        "rate_limited",
        "provider_unavailable",
        "invalid_configuration",
        "request_rejected",
        "response_invalid",
        "internal_failure",
        "unavailable",
    }
)

# Capability aliases → canonical (never emit aliases).
_CAPABILITY_ALIASES: dict[str, str] = {
    "modernization_advisor": "modernization_advisor",
    "modernization-advisor": "modernization_advisor",
    "ai_enrichment": "modernization_advisor",
    "assess_with_ai": "modernization_advisor",
}

# Engine provider registry IDs → provider_family (never emit raw registry IDs).
_PROVIDER_ALIASES: dict[str, str] = {
    "aws_bedrock": "aws_bedrock",
    "bedrock": "aws_bedrock",
    "openai": "openai",
    "openrouter": "openrouter",
    "unavailable": "unavailable",
}


__all__ = [
    "AI_ANALYTICS_CAPABILITY_CATALOG_VERSION",
    "AI_ANALYTICS_MODEL_FAMILY_CATALOG_VERSION",
    "AI_ANALYTICS_PROVIDER_FAMILY_CATALOG_VERSION",
    "APPROVED_AI_CAPABILITIES",
    "APPROVED_AI_FAILURE_CATEGORIES",
    "APPROVED_AI_MODEL_FAMILIES",
    "APPROVED_AI_OUTCOMES",
    "APPROVED_AI_PROVIDER_FAMILIES",
    "APPROVED_AI_PROVIDER_OWNERSHIPS",
    "_CAPABILITY_ALIASES",
    "_PROVIDER_ALIASES",
]
