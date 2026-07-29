"""Register AI Readiness Intelligence rules into a RuleRegistry."""

from __future__ import annotations

from codestrata.application.rules.ai_readiness.pack import (
    AiReadinessRulePack,
    ai_readiness_rules,
)
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config.settings import AiReadinessRulesSettings, RulesSettings
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
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


def register_ai_readiness_pack(
    registry: RuleRegistry,
    *,
    settings: RulesSettings | AiReadinessRulesSettings | None = None,
    production: bool = True,
    for_execution: bool = False,
) -> AiReadinessRulePack:
    """Register ai_readiness.core hygiene rules.

    By default registers the full pack for CLI/MCP discovery. When
    ``for_execution=True``, respects per-rule enabled flags from settings.
    """

    pack = AiReadinessRulePack()
    ai_readiness = _ai_readiness_settings(settings)
    enabled_ids = _enabled_rule_ids(ai_readiness) if for_execution else None
    rules = ai_readiness_rules(enabled_rule_ids=enabled_ids)
    registry.register_collection(rules, production=production)
    return pack


def _ai_readiness_settings(
    settings: RulesSettings | AiReadinessRulesSettings | None,
) -> AiReadinessRulesSettings:
    if settings is None:
        return AiReadinessRulesSettings()
    if isinstance(settings, AiReadinessRulesSettings):
        return settings
    return settings.ai_readiness


def _enabled_rule_ids(ai_readiness: AiReadinessRulesSettings) -> frozenset[str]:
    mapping = {
        RULE_API_BOUNDARIES: ai_readiness.ai_001.enabled,
        RULE_STRUCTURED_API_SPEC: ai_readiness.ai_002.enabled,
        RULE_LIMITED_API_BOUNDARIES: ai_readiness.ai_003.enabled,
        RULE_ARCHITECTURE_DOCS: ai_readiness.ai_010.enabled,
        RULE_LIMITED_DOCUMENTATION: ai_readiness.ai_011.enabled,
        RULE_DATA_ACCESS: ai_readiness.ai_020.enabled,
        RULE_SEARCH_RETRIEVAL: ai_readiness.ai_021.enabled,
        RULE_VECTOR_EMBEDDINGS: ai_readiness.ai_022.enabled,
        RULE_LLM_SDK: ai_readiness.ai_030.enabled,
        RULE_PROMPT_ASSETS: ai_readiness.ai_031.enabled,
        RULE_RAG_PIPELINE: ai_readiness.ai_032.enabled,
        RULE_MCP_TOOLS: ai_readiness.ai_040.enabled,
        RULE_WORKFLOW_AGENT: ai_readiness.ai_041.enabled,
        RULE_OBSERVABILITY_GOVERNANCE: ai_readiness.ai_050.enabled,
        RULE_AI_WITHOUT_OBSERVABILITY: ai_readiness.ai_051.enabled,
        RULE_BROAD_FOUNDATIONS: ai_readiness.ai_060.enabled,
        RULE_LIMITED_FOUNDATIONS: ai_readiness.ai_061.enabled,
    }
    return frozenset(rule_id for rule_id in HYGIENE_RULE_IDS if mapping.get(rule_id, True))
