"""AI Readiness assessment section enums (Phase 4.8.1)."""

from __future__ import annotations

from enum import StrEnum


class AiReadinessAssessmentStatus(StrEnum):
    """Explicit AI Readiness assessment section status."""

    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"


class AiReadinessCoverageAreaStatus(StrEnum):
    MEASURED = "measured"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class AiReadinessCoverageMaturity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AiReadinessLimitationCategory(StrEnum):
    """Structured limitation categories (not findings)."""

    FOUNDATION_ONLY = "foundation-only"
    AI_READINESS_ANALYSIS_NOT_IMPLEMENTED = "ai-readiness-analysis-not-implemented"
    API_BOUNDARIES_NOT_EVALUATED = "api-boundaries-not-evaluated"
    DOCUMENTATION_METADATA_NOT_EVALUATED = "documentation-metadata-not-evaluated"
    DATA_ACCESS_PATTERNS_NOT_EVALUATED = "data-access-patterns-not-evaluated"
    SEARCH_RETRIEVAL_NOT_EVALUATED = "search-retrieval-not-evaluated"
    RAG_ASSETS_NOT_EVALUATED = "rag-assets-not-evaluated"
    TOOL_MCP_INTEGRATION_NOT_EVALUATED = "tool-mcp-integration-not-evaluated"
    WORKFLOW_AGENT_BOUNDARIES_NOT_EVALUATED = "workflow-agent-boundaries-not-evaluated"
    EXISTING_AI_INTEGRATIONS_NOT_EVALUATED = "existing-ai-integrations-not-evaluated"
    OBSERVABILITY_GOVERNANCE_NOT_EVALUATED = "observability-governance-not-evaluated"
    NO_AI_READINESS_CONCLUSION = "no-ai-readiness-conclusion"
    RULES_NOT_IMPLEMENTED = "rules-not-implemented"
    OTHER = "other"


class AiReadinessTraceabilityRelation(StrEnum):
    SECTION_TO_PACK = "section_to_pack"
    SECTION_TO_FINDING = "section_to_finding"
    SECTION_TO_COVERAGE = "section_to_coverage"
    SECTION_TO_LIMITATION = "section_to_limitation"
    SECTION_TO_THEME = "section_to_theme"
    SECTION_TO_CONCLUSION = "section_to_conclusion"
    SECTION_TO_RECOMMENDATION = "section_to_recommendation"
    PACK_TO_RULE = "pack_to_rule"
