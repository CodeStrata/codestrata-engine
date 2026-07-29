"""AI Readiness Intelligence pack metadata and rule construction (Phase 4.8.3)."""

from __future__ import annotations

from codestrata.application.rules.ai_readiness.rules import (
    AiWithoutObservabilityRule,
    ApiBoundariesDetectedRule,
    ArchitectureDocsDetectedRule,
    BroadFoundationsRule,
    DataAccessDetectedRule,
    LimitedApiBoundariesRule,
    LimitedDocumentationRule,
    LimitedFoundationsRule,
    LlmSdkDetectedRule,
    McpToolsDetectedRule,
    ObservabilityGovernanceDetectedRule,
    PromptAssetsDetectedRule,
    RagPipelineDetectedRule,
    SearchRetrievalDetectedRule,
    StructuredApiSpecDetectedRule,
    VectorEmbeddingsDetectedRule,
    WorkflowAgentDetectedRule,
)
from codestrata.domain.ai_readiness.ids import (
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_DESCRIPTION,
    PACK_ID,
    PACK_TITLE,
    PACK_VERSION,
    RULE_AI_WITHOUT_OBSERVABILITY,
    RULE_API_BOUNDARIES,
    RULE_ARCHITECTURE_DOCS,
    RULE_BROAD_FOUNDATIONS,
    RULE_DATA_ACCESS,
    RULE_LIMITED_API_BOUNDARIES,
    RULE_LIMITED_DOCUMENTATION,
    RULE_LIMITED_FOUNDATIONS,
    RULE_LLM_SDK,
    RULE_MCP_TOOLS,
    RULE_OBSERVABILITY_GOVERNANCE,
    RULE_PROMPT_ASSETS,
    RULE_RAG_PIPELINE,
    RULE_SEARCH_RETRIEVAL,
    RULE_STRUCTURED_API_SPEC,
    RULE_VECTOR_EMBEDDINGS,
    RULE_WORKFLOW_AGENT,
)
from codestrata.domain.rules.contracts import SharedRule
from codestrata.domain.rules.enums import RuleCategory


class AiReadinessRulePack:
    """First-class AI Readiness Intelligence pack descriptor."""

    pack_id: str = PACK_ID
    pack_version: str = PACK_VERSION
    title: str = PACK_TITLE
    description: str = PACK_DESCRIPTION
    category: RuleCategory = RuleCategory.AI_READINESS
    supported_languages: tuple[str, ...] = ()
    default_enabled: bool = False
    requires_enterprise_context: bool = False
    documentation_reference: str = "docs/analysis-intelligence/shared-rule-platform.md"
    configuration_requirements: tuple[str, ...] = (
        "rules.enabled=true",
        "rules.ai_readiness.enabled=true",
        "evidence.repository_ai_readiness.enabled=true",
    )
    enterprise_context_requirements: tuple[str, ...] = ()
    included_rule_ids: tuple[str, ...] = HYGIENE_RULE_IDS
    deferred_rule_ids: tuple[str, ...] = DEFERRED_RULE_IDS

    def to_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "included_rule_ids": list(self.included_rule_ids),
            "deferred_rule_ids": list(self.deferred_rule_ids),
            "supported_languages": list(self.supported_languages),
            "default_enabled": self.default_enabled,
            "requires_enterprise_context": self.requires_enterprise_context,
            "configuration_requirements": list(self.configuration_requirements),
            "enterprise_context_requirements": list(self.enterprise_context_requirements),
            "documentation_reference": self.documentation_reference,
        }


def ai_readiness_rules(
    *,
    enabled_rule_ids: frozenset[str] | None = None,
) -> tuple[SharedRule, ...]:
    candidates: list[tuple[str, SharedRule]] = [
        (RULE_API_BOUNDARIES, ApiBoundariesDetectedRule()),
        (RULE_STRUCTURED_API_SPEC, StructuredApiSpecDetectedRule()),
        (RULE_LIMITED_API_BOUNDARIES, LimitedApiBoundariesRule()),
        (RULE_ARCHITECTURE_DOCS, ArchitectureDocsDetectedRule()),
        (RULE_LIMITED_DOCUMENTATION, LimitedDocumentationRule()),
        (RULE_DATA_ACCESS, DataAccessDetectedRule()),
        (RULE_SEARCH_RETRIEVAL, SearchRetrievalDetectedRule()),
        (RULE_VECTOR_EMBEDDINGS, VectorEmbeddingsDetectedRule()),
        (RULE_LLM_SDK, LlmSdkDetectedRule()),
        (RULE_PROMPT_ASSETS, PromptAssetsDetectedRule()),
        (RULE_RAG_PIPELINE, RagPipelineDetectedRule()),
        (RULE_MCP_TOOLS, McpToolsDetectedRule()),
        (RULE_WORKFLOW_AGENT, WorkflowAgentDetectedRule()),
        (RULE_OBSERVABILITY_GOVERNANCE, ObservabilityGovernanceDetectedRule()),
        (RULE_AI_WITHOUT_OBSERVABILITY, AiWithoutObservabilityRule()),
        (RULE_BROAD_FOUNDATIONS, BroadFoundationsRule()),
        (RULE_LIMITED_FOUNDATIONS, LimitedFoundationsRule()),
    ]
    if enabled_rule_ids is None:
        return tuple(rule for _, rule in candidates)
    return tuple(rule for rule_id, rule in candidates if rule_id in enabled_rule_ids)
