"""AI Readiness Intelligence taxonomy (Phase 4.8.1).

Repository-observable AI readiness categories reserved for future rules and
assessment metadata. These values are methodology identifiers only.

This phase does not collect evidence, evaluate readiness, execute AI/LLM calls,
or emit findings for any category.
"""

from __future__ import annotations

from enum import StrEnum


class AiReadinessCategory(StrEnum):
    """Bounded AI Readiness Intelligence categories.

    Serialized values use the ``ai_readiness.<category>`` namespace (snake_case).
    """

    API_AND_SERVICE_BOUNDARIES = "ai_readiness.api_and_service_boundaries"
    DOCUMENTATION_AND_METADATA_QUALITY = "ai_readiness.documentation_and_metadata_quality"
    DATA_ACCESS_PATTERNS = "ai_readiness.data_access_patterns"
    SEARCH_AND_RETRIEVAL_READINESS = "ai_readiness.search_and_retrieval_readiness"
    RAG_ENABLING_ASSETS = "ai_readiness.rag_enabling_assets"
    TOOL_AND_MCP_INTEGRATION = "ai_readiness.tool_and_mcp_integration"
    WORKFLOW_AND_AGENT_BOUNDARIES = "ai_readiness.workflow_and_agent_boundaries"
    EXISTING_AI_LLM_INTEGRATIONS = "ai_readiness.existing_ai_llm_integrations"
    OBSERVABILITY_AND_GOVERNANCE = "ai_readiness.observability_and_governance"
    MISCELLANEOUS = "ai_readiness.miscellaneous"
    UNKNOWN = "ai_readiness.unknown"


AI_READINESS_CATEGORIES: tuple[AiReadinessCategory, ...] = tuple(AiReadinessCategory)


def coerce_ai_readiness_category(value: object) -> AiReadinessCategory:
    """Map a raw taxonomy value to a category, defaulting unknown inputs safely."""

    if isinstance(value, AiReadinessCategory):
        return value
    text = str(value or "").strip()
    if not text:
        return AiReadinessCategory.UNKNOWN
    try:
        return AiReadinessCategory(text)
    except ValueError:
        pass
    normalized = text.replace("-", "_")
    bare = (
        normalized
        if normalized.startswith("ai_readiness.")
        else f"ai_readiness.{normalized.removeprefix('ai_readiness.')}"
    )
    try:
        return AiReadinessCategory(bare)
    except ValueError:
        return AiReadinessCategory.UNKNOWN
