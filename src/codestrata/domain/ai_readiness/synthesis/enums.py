"""AI Readiness synthesis enums (Phase 4.8.5)."""

from __future__ import annotations

from enum import StrEnum


class AiReadinessThemeKind(StrEnum):
    """Bounded theme kinds derived from AI Readiness assessment inventory."""

    AI_READINESS_HYGIENE_LANDSCAPE = "ai_readiness_hygiene_landscape"
    RULE_EXECUTION_COVERAGE = "rule_execution_coverage"
    API_AND_SERVICE_BOUNDARIES = "api_and_service_boundaries"
    DOCUMENTATION_MATURITY = "documentation_maturity"
    DATA_AND_RETRIEVAL_FOUNDATIONS = "data_and_retrieval_foundations"
    AI_INTEGRATION_MATURITY = "ai_integration_maturity"
    MCP_AND_TOOL_ECOSYSTEM = "mcp_and_tool_ecosystem"
    WORKFLOW_AND_AGENT_FOUNDATIONS = "workflow_and_agent_foundations"
    OBSERVABILITY_AND_GOVERNANCE = "observability_and_governance"
    BROAD_AI_ENABLEMENT = "broad_ai_enablement"
    LIMITED_SUPPORTING_FOUNDATIONS = "limited_supporting_foundations"
    NO_HYGIENE_FINDINGS = "no_hygiene_findings"
    UNSUPPORTED_ANALYSIS_SCOPE = "unsupported_analysis_scope"


class AiReadinessThemeScope(StrEnum):
    REPOSITORY = "repository"
    COVERAGE = "coverage"
    HYGIENE = "hygiene"
    STATUS = "status"


class AiReadinessConclusionKind(StrEnum):
    """Bounded deterministic conclusion kinds."""

    AI_READINESS_HYGIENE_LANDSCAPE_IDENTIFIED = "ai_readiness_hygiene_landscape_identified"
    RULE_EXECUTION_SUMMARY = "rule_execution_summary"
    API_AND_SERVICE_BOUNDARIES_OBSERVED = "api_and_service_boundaries_observed"
    DOCUMENTATION_MATURITY_OBSERVED = "documentation_maturity_observed"
    DATA_AND_RETRIEVAL_FOUNDATIONS_OBSERVED = "data_and_retrieval_foundations_observed"
    AI_INTEGRATION_MATURITY_OBSERVED = "ai_integration_maturity_observed"
    MCP_AND_TOOL_ECOSYSTEM_OBSERVED = "mcp_and_tool_ecosystem_observed"
    WORKFLOW_AND_AGENT_FOUNDATIONS_OBSERVED = "workflow_and_agent_foundations_observed"
    OBSERVABILITY_AND_GOVERNANCE_OBSERVED = "observability_and_governance_observed"
    BROAD_AI_ENABLEMENT_OBSERVED = "broad_ai_enablement_observed"
    LIMITED_SUPPORTING_FOUNDATIONS_OBSERVED = "limited_supporting_foundations_observed"
    NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = "no_hygiene_findings_in_supported_scope"
    UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE = "unsupported_ai_readiness_analysis_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SYNTHESIS_DISABLED = "synthesis_disabled"


class AiReadinessConclusionAudience(StrEnum):
    REPOSITORY = "repository"
    HYGIENE = "hygiene"
    COVERAGE = "coverage"
    STATUS = "status"


class AiReadinessRecommendationKind(StrEnum):
    """Bounded observation-oriented recommendation kinds."""

    REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS = "review_api_and_service_boundary_signals"
    REVIEW_DOCUMENTATION_MATURITY_SIGNALS = "review_documentation_maturity_signals"
    REVIEW_DATA_AND_RETRIEVAL_SIGNALS = "review_data_and_retrieval_signals"
    REVIEW_AI_INTEGRATION_SIGNALS = "review_ai_integration_signals"
    REVIEW_MCP_AND_TOOL_SIGNALS = "review_mcp_and_tool_signals"
    REVIEW_WORKFLOW_AND_AGENT_SIGNALS = "review_workflow_and_agent_signals"
    REVIEW_OBSERVABILITY_AND_GOVERNANCE_SIGNALS = "review_observability_and_governance_signals"
    REVIEW_BROAD_AI_ENABLEMENT = "review_broad_ai_enablement"
    REVIEW_LIMITED_SUPPORTING_FOUNDATIONS = "review_limited_supporting_foundations"
    ACKNOWLEDGE_NO_HYGIENE_FINDINGS_IN_SUPPORTED_SCOPE = (
        "acknowledge_no_hygiene_findings_in_supported_scope"
    )
    ACKNOWLEDGE_UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE = (
        "acknowledge_unsupported_ai_readiness_analysis_scope"
    )


class AiReadinessSynthesisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    DISABLED = "disabled"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    FAILED = "failed"
