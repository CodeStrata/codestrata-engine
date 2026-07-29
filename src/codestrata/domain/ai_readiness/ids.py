"""AI Readiness Intelligence pack identifiers (Phase 4.8.3).

``ai_readiness.core`` hygiene rules consume AggregatedRepositoryAiReadinessEvidence
only. Human aliases: AI-001 … AI-061 map to ``ai_readiness.ai-00N`` rule IDs
(Shared Rule Platform namespace.kebab form).
"""

from __future__ import annotations

PACK_ID = "ai_readiness.core"
PACK_VERSION = "1.0.0"
PACK_TITLE = "AI Readiness Intelligence Core"
PACK_DESCRIPTION = (
    "AI Readiness Intelligence SharedRule pack for repository-observable "
    "AI/agent readiness signals. Rules consume "
    "AggregatedRepositoryAiReadinessEvidence only and never re-read repository "
    "files, execute AI/LLM calls, or produce readiness scores."
)

RULE_ID_PREFIX = "ai_readiness."
RULE_VERSION = "1.0.0"

TAXONOMY_NAMESPACE = "ai_readiness"

# Machine IDs (platform-valid). Documented aliases: AI-001 … AI-061.
RULE_API_BOUNDARIES = "ai_readiness.ai-001"
RULE_STRUCTURED_API_SPEC = "ai_readiness.ai-002"
RULE_LIMITED_API_BOUNDARIES = "ai_readiness.ai-003"
RULE_ARCHITECTURE_DOCS = "ai_readiness.ai-010"
RULE_LIMITED_DOCUMENTATION = "ai_readiness.ai-011"
RULE_DATA_ACCESS = "ai_readiness.ai-020"
RULE_SEARCH_RETRIEVAL = "ai_readiness.ai-021"
RULE_VECTOR_EMBEDDINGS = "ai_readiness.ai-022"
RULE_LLM_SDK = "ai_readiness.ai-030"
RULE_PROMPT_ASSETS = "ai_readiness.ai-031"
RULE_RAG_PIPELINE = "ai_readiness.ai-032"
RULE_MCP_TOOLS = "ai_readiness.ai-040"
RULE_WORKFLOW_AGENT = "ai_readiness.ai-041"
RULE_OBSERVABILITY_GOVERNANCE = "ai_readiness.ai-050"
RULE_AI_WITHOUT_OBSERVABILITY = "ai_readiness.ai-051"
RULE_BROAD_FOUNDATIONS = "ai_readiness.ai-060"
RULE_LIMITED_FOUNDATIONS = "ai_readiness.ai-061"

HYGIENE_RULE_IDS: tuple[str, ...] = (
    RULE_API_BOUNDARIES,
    RULE_STRUCTURED_API_SPEC,
    RULE_LIMITED_API_BOUNDARIES,
    RULE_ARCHITECTURE_DOCS,
    RULE_LIMITED_DOCUMENTATION,
    RULE_DATA_ACCESS,
    RULE_SEARCH_RETRIEVAL,
    RULE_VECTOR_EMBEDDINGS,
    RULE_LLM_SDK,
    RULE_PROMPT_ASSETS,
    RULE_RAG_PIPELINE,
    RULE_MCP_TOOLS,
    RULE_WORKFLOW_AGENT,
    RULE_OBSERVABILITY_GOVERNANCE,
    RULE_AI_WITHOUT_OBSERVABILITY,
    RULE_BROAD_FOUNDATIONS,
    RULE_LIMITED_FOUNDATIONS,
)

AI_READINESS_RULE_IDS: tuple[str, ...] = HYGIENE_RULE_IDS

DEFERRED_RULE_IDS: tuple[str, ...] = ()

RULE_ALIAS_TO_ID: dict[str, str] = {
    "AI-001": RULE_API_BOUNDARIES,
    "AI-002": RULE_STRUCTURED_API_SPEC,
    "AI-003": RULE_LIMITED_API_BOUNDARIES,
    "AI-010": RULE_ARCHITECTURE_DOCS,
    "AI-011": RULE_LIMITED_DOCUMENTATION,
    "AI-020": RULE_DATA_ACCESS,
    "AI-021": RULE_SEARCH_RETRIEVAL,
    "AI-022": RULE_VECTOR_EMBEDDINGS,
    "AI-030": RULE_LLM_SDK,
    "AI-031": RULE_PROMPT_ASSETS,
    "AI-032": RULE_RAG_PIPELINE,
    "AI-040": RULE_MCP_TOOLS,
    "AI-041": RULE_WORKFLOW_AGENT,
    "AI-050": RULE_OBSERVABILITY_GOVERNANCE,
    "AI-051": RULE_AI_WITHOUT_OBSERVABILITY,
    "AI-060": RULE_BROAD_FOUNDATIONS,
    "AI-061": RULE_LIMITED_FOUNDATIONS,
}
