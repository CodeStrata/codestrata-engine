"""AI Readiness Hygiene SharedRules (Phase 4.8.3).

Rules consume AggregatedRepositoryAiReadinessEvidence only. They never re-read
repository files, execute AI/LLM calls, or invent readiness conclusions.
"""

from __future__ import annotations

from codestrata.application.rules.ai_readiness.helpers import (
    AiReadinessFact,
    _sorted_matches,
    active_families,
    ai_related_assets_present,
    confidence_from_levels,
    evidence_is_usable,
    evidence_summary,
    known_api_boundary_kinds,
    known_data_access_kinds,
    known_docs_architecture_kinds,
    known_docs_supporting_kinds,
    known_llm_kinds,
    known_observability_governance_kinds,
    known_openapi_facts,
    known_prompt_kinds,
    known_rag_kinds,
    known_search_retrieval_kinds,
    known_tool_mcp_kinds,
    known_vector_embedding_signals,
    known_workflow_agent_kinds,
    make_metadata,
    match,
    path_evidence_from_facts,
    repository_ai_readiness_evidence,
)
from codestrata.domain.ai_readiness.ids import (
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
from codestrata.domain.ai_readiness.taxonomy import AiReadinessCategory
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessDataRetrievalKind,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import RuleSeverity, RuleSkipReason
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult


def _ai_readiness_applicability(context: RuleExecutionContext) -> RuleApplicability:
    evidence = repository_ai_readiness_evidence(context)
    if evidence is None:
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message="Repository AI-readiness evidence unavailable",
        )
    if not evidence_is_usable(evidence):
        return RuleApplicability.not_applicable(
            reason_code=RuleSkipReason.OTHER,
            message=f"Repository AI-readiness evidence status is {evidence.status.value}",
        )
    return RuleApplicability.applicable()


class ApiBoundariesDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_API_BOUNDARIES,
            title="API or service boundary signals detected",
            description=(
                "Detects repository-observable REST, GraphQL, gRPC, controller, "
                "router, or handler boundary signals. Does not claim AI readiness."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_api_boundary_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.api_boundary_facts if item.kind in kinds]
        category = AiReadinessCategory.API_AND_SERVICE_BOUNDARIES
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_API_BOUNDARIES,
                message=f"api_boundary_kinds={joined}",
                ai_readiness_category=category,
                attributes={"api_boundary_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="api_boundary_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_API_BOUNDARIES,
                    title="API or service boundary signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes API or service "
                        f"boundary signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_API_BOUNDARIES, "api_boundaries", joined),
                )
            ]
        )


class StructuredApiSpecDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_STRUCTURED_API_SPEC,
            title="Structured API specification detected",
            description=("Detects OpenAPI or equivalent structured API specification artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        facts = list(known_openapi_facts(evidence))
        if not facts:
            return SharedRuleEvaluationResult.not_matched()
        category = AiReadinessCategory.API_AND_SERVICE_BOUNDARIES
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_STRUCTURED_API_SPEC,
                message=f"openapi_fact_count={len(facts)}",
                ai_readiness_category=category,
                attributes={"openapi_fact_count": str(len(facts))},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="openapi_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_STRUCTURED_API_SPEC,
                    title="Structured API specification detected",
                    summary=(
                        "Repository AI-readiness evidence includes structured API "
                        "specification signals (openapi)."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_STRUCTURED_API_SPEC, "openapi", str(len(facts))),
                )
            ]
        )


class LimitedApiBoundariesRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LIMITED_API_BOUNDARIES,
            title="Limited API or service boundary evidence",
            description=(
                "Observes usable AI-readiness evidence without known API boundary "
                "or OpenAPI signals. Does not claim APIs are absent."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        if known_api_boundary_kinds(evidence) or known_openapi_facts(evidence):
            return SharedRuleEvaluationResult.not_matched()
        category = AiReadinessCategory.API_AND_SERVICE_BOUNDARIES
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_LIMITED_API_BOUNDARIES,
                message="api_boundary_kinds=0; openapi_facts=0",
                ai_readiness_category=category,
                attributes={"api_boundary_kinds": "", "openapi_fact_count": "0"},
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_LIMITED_API_BOUNDARIES,
                    title="Limited API or service boundary evidence",
                    summary=(
                        "Repository AI-readiness evidence does not include known "
                        "API boundary or OpenAPI signals among inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_LIMITED_API_BOUNDARIES, "limited_api", "0"),
                )
            ]
        )


class ArchitectureDocsDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_ARCHITECTURE_DOCS,
            title="Architecture or ADR documentation detected",
            description=(
                "Detects architecture documentation or Architecture Decision Record artifacts."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_docs_architecture_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.documentation_facts if item.kind in kinds]
        category = AiReadinessCategory.DOCUMENTATION_AND_METADATA_QUALITY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_ARCHITECTURE_DOCS,
                message=f"documentation_kinds={joined}",
                ai_readiness_category=category,
                attributes={"documentation_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="documentation_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_ARCHITECTURE_DOCS,
                    title="Architecture or ADR documentation detected",
                    summary=(
                        "Repository AI-readiness evidence includes architecture or "
                        f"ADR documentation signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_ARCHITECTURE_DOCS, "architecture_docs", joined),
                )
            ]
        )


class LimitedDocumentationRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LIMITED_DOCUMENTATION,
            title="Limited supporting documentation evidence",
            description=(
                "Observes usable AI-readiness evidence without README, architecture, "
                "ADR, or API documentation signals."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        if known_docs_supporting_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        category = AiReadinessCategory.DOCUMENTATION_AND_METADATA_QUALITY
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_LIMITED_DOCUMENTATION,
                message="supporting_documentation_kinds=0",
                ai_readiness_category=category,
                attributes={"supporting_documentation_kinds": ""},
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_LIMITED_DOCUMENTATION,
                    title="Limited supporting documentation evidence",
                    summary=(
                        "Repository AI-readiness evidence does not include README, "
                        "architecture, ADR, or API documentation signals among "
                        "inspected candidates."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_LIMITED_DOCUMENTATION, "limited_docs", "0"),
                )
            ]
        )


class DataAccessDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DATA_ACCESS,
            title="Data access repository signals detected",
            description=("Detects database repository or data-access layer artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_data_access_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [
            item
            for item in evidence.data_retrieval_facts
            if item.kind is AiReadinessDataRetrievalKind.DATABASE_REPOSITORY
        ]
        category = AiReadinessCategory.DATA_ACCESS_PATTERNS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_DATA_ACCESS,
                message=f"data_access_kinds={joined}",
                ai_readiness_category=category,
                attributes={"data_access_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="data_access_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_DATA_ACCESS,
                    title="Data access repository signals detected",
                    summary=(
                        f"Repository AI-readiness evidence includes data access signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_DATA_ACCESS, "data_access", joined),
                )
            ]
        )


class SearchRetrievalDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_SEARCH_RETRIEVAL,
            title="Search or retrieval signals detected",
            description=("Detects search engine, retrieval index, or ingestion artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_search_retrieval_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.data_retrieval_facts if item.kind in kinds]
        category = AiReadinessCategory.SEARCH_AND_RETRIEVAL_READINESS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_SEARCH_RETRIEVAL,
                message=f"search_retrieval_kinds={joined}",
                ai_readiness_category=category,
                attributes={"search_retrieval_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="search_retrieval_fact",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_SEARCH_RETRIEVAL,
                    title="Search or retrieval signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes search or "
                        f"retrieval signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_SEARCH_RETRIEVAL, "search_retrieval", joined),
                )
            ]
        )


class VectorEmbeddingsDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_VECTOR_EMBEDDINGS,
            title="Vector or embeddings signals detected",
            description=("Detects vector database, embeddings, or embeddings-usage artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        signals = known_vector_embedding_signals(evidence)
        if not signals:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(signals)
        data_kinds = {
            AiReadinessDataRetrievalKind.VECTOR_DB,
            AiReadinessDataRetrievalKind.EMBEDDINGS,
        }
        facts: list[AiReadinessFact] = [
            *[item for item in evidence.data_retrieval_facts if item.kind in data_kinds],
            *[
                item
                for item in evidence.ai_integration_facts
                if item.kind is AiReadinessAiIntegrationKind.EMBEDDINGS_USAGE
            ],
        ]
        category = AiReadinessCategory.RAG_ENABLING_ASSETS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_VECTOR_EMBEDDINGS,
                message=f"vector_embedding_signals={joined}",
                ai_readiness_category=category,
                attributes={"vector_embedding_signals": joined},
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="vector_embedding_fact",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_VECTOR_EMBEDDINGS,
                    title="Vector or embeddings signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes vector or "
                        f"embeddings signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_VECTOR_EMBEDDINGS, "vector_embeddings", joined),
                )
            ]
        )


class LlmSdkDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LLM_SDK,
            title="LLM SDK or AI framework signals detected",
            description=("Detects LLM SDK or AI framework integration artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_llm_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.ai_integration_facts if item.kind in kinds]
        category = AiReadinessCategory.EXISTING_AI_LLM_INTEGRATIONS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_LLM_SDK,
                message=f"llm_kinds={joined}",
                ai_readiness_category=category,
                attributes={"llm_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="llm_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_LLM_SDK,
                    title="LLM SDK or AI framework signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes LLM SDK or AI "
                        f"framework signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_LLM_SDK, "llm", joined),
                )
            ]
        )


class PromptAssetsDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_PROMPT_ASSETS,
            title="Prompt assets detected",
            description=("Detects prompt template or prompt asset artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_prompt_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [
            item
            for item in evidence.ai_integration_facts
            if item.kind is AiReadinessAiIntegrationKind.PROMPT
        ]
        category = AiReadinessCategory.EXISTING_AI_LLM_INTEGRATIONS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_PROMPT_ASSETS,
                message=f"prompt_kinds={joined}",
                ai_readiness_category=category,
                attributes={"prompt_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="prompt_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_PROMPT_ASSETS,
                    title="Prompt assets detected",
                    summary=(
                        "Repository AI-readiness evidence includes prompt asset "
                        f"signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_PROMPT_ASSETS, "prompts", joined),
                )
            ]
        )


class RagPipelineDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_RAG_PIPELINE,
            title="RAG pipeline signals detected",
            description=("Detects retrieval-augmented generation pipeline artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_rag_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [
            item
            for item in evidence.ai_integration_facts
            if item.kind is AiReadinessAiIntegrationKind.RAG_PIPELINE
        ]
        category = AiReadinessCategory.RAG_ENABLING_ASSETS
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_RAG_PIPELINE,
                message=f"rag_kinds={joined}",
                ai_readiness_category=category,
                attributes={"rag_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="rag_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_RAG_PIPELINE,
                    title="RAG pipeline signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes RAG pipeline "
                        f"signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_RAG_PIPELINE, "rag", joined),
                )
            ]
        )


class McpToolsDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_MCP_TOOLS,
            title="Tool or MCP integration signals detected",
            description=("Detects MCP server/client, tool definition, or plugin artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_tool_mcp_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.tool_mcp_facts if item.kind in kinds]
        category = AiReadinessCategory.TOOL_AND_MCP_INTEGRATION
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_MCP_TOOLS,
                message=f"tool_mcp_kinds={joined}",
                ai_readiness_category=category,
                attributes={"tool_mcp_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts, ai_readiness_category=category, label="tool_mcp_fact"
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_MCP_TOOLS,
                    title="Tool or MCP integration signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes tool or MCP "
                        f"integration signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_MCP_TOOLS, "tool_mcp", joined),
                )
            ]
        )


class WorkflowAgentDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_WORKFLOW_AGENT,
            title="Workflow or agent boundary signals detected",
            description=("Detects workflow engine, agent framework, or orchestration artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_workflow_agent_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.workflow_agent_facts if item.kind in kinds]
        category = AiReadinessCategory.WORKFLOW_AND_AGENT_BOUNDARIES
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_WORKFLOW_AGENT,
                message=f"workflow_agent_kinds={joined}",
                ai_readiness_category=category,
                attributes={"workflow_agent_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="workflow_agent_fact",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_WORKFLOW_AGENT,
                    title="Workflow or agent boundary signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes workflow or "
                        f"agent boundary signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_WORKFLOW_AGENT, "workflow_agent", joined),
                )
            ]
        )


class ObservabilityGovernanceDetectedRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_OBSERVABILITY_GOVERNANCE,
            title="Observability or governance signals detected",
            description=("Detects logging, tracing, metrics, audit, eval, or guardrail artifacts."),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        kinds = known_observability_governance_kinds(evidence)
        if not kinds:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(item.value for item in kinds)
        facts = [item for item in evidence.observability_governance_facts if item.kind in kinds]
        category = AiReadinessCategory.OBSERVABILITY_AND_GOVERNANCE
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_OBSERVABILITY_GOVERNANCE,
                message=f"observability_governance_kinds={joined}",
                ai_readiness_category=category,
                attributes={"observability_governance_kinds": joined},
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="observability_governance_fact",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_OBSERVABILITY_GOVERNANCE,
                    title="Observability or governance signals detected",
                    summary=(
                        "Repository AI-readiness evidence includes observability or "
                        f"governance signals ({joined})."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_OBSERVABILITY_GOVERNANCE,
                        "observability_governance",
                        joined,
                    ),
                )
            ]
        )


class AiWithoutObservabilityRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_AI_WITHOUT_OBSERVABILITY,
            title="AI-related assets without observability evidence",
            description=(
                "Observes AI integration, tool/MCP, or workflow/agent signals when "
                "no known observability or governance facts are present."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        if known_observability_governance_kinds(evidence):
            return SharedRuleEvaluationResult.not_matched()
        if not ai_related_assets_present(evidence):
            return SharedRuleEvaluationResult.not_matched()
        facts: list[AiReadinessFact] = [
            *[
                item
                for item in evidence.ai_integration_facts
                if item.kind is not AiReadinessAiIntegrationKind.UNKNOWN
            ],
            *[item for item in evidence.tool_mcp_facts if item.kind.value != "unknown"],
            *[item for item in evidence.workflow_agent_facts if item.kind.value != "unknown"],
        ]
        category = AiReadinessCategory.OBSERVABILITY_AND_GOVERNANCE
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_AI_WITHOUT_OBSERVABILITY,
                message="ai_related_assets=true; observability_governance_kinds=0",
                ai_readiness_category=category,
                attributes={
                    "ai_related_assets": "true",
                    "observability_governance_kinds": "",
                },
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="ai_related_asset",
            ),
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_AI_WITHOUT_OBSERVABILITY,
                    title="AI-related assets without observability evidence",
                    summary=(
                        "Repository AI-readiness evidence includes AI-related "
                        "assets without known observability or governance signals. "
                        "This does not claim observability is absent."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_AI_WITHOUT_OBSERVABILITY,
                        "ai_without_observability",
                        "0",
                    ),
                )
            ]
        )


class BroadFoundationsRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_BROAD_FOUNDATIONS,
            title="Broad AI-readiness evidence foundations",
            description=(
                "Detects three or more distinct AI-readiness evidence families. "
                "Does not establish AI readiness."
            ),
            severity=RuleSeverity.INFORMATIONAL,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        families = active_families(evidence)
        if len(families) < 3:
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(families)
        category = AiReadinessCategory.MISCELLANEOUS
        levels = [
            *(item.confirmation_level for item in evidence.api_boundary_facts),
            *(item.confirmation_level for item in evidence.documentation_facts),
            *(item.confirmation_level for item in evidence.data_retrieval_facts),
            *(item.confirmation_level for item in evidence.ai_integration_facts),
            *(item.confirmation_level for item in evidence.tool_mcp_facts),
            *(item.confirmation_level for item in evidence.workflow_agent_facts),
            *(item.confirmation_level for item in evidence.observability_governance_facts),
        ]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_BROAD_FOUNDATIONS,
                message=f"family_count={len(families)}; families={joined}",
                ai_readiness_category=category,
                attributes={
                    "families": joined,
                    "family_count": str(len(families)),
                    "technologies": ",".join(evidence.coverage.technologies_represented),
                },
            )
        ]
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_BROAD_FOUNDATIONS,
                    title="Broad AI-readiness evidence foundations",
                    summary=(
                        f"Observed {len(families)} AI-readiness evidence families "
                        f"({joined}). This does not establish AI readiness."
                    ),
                    severity=RuleSeverity.INFORMATIONAL,
                    confidence=confidence_from_levels(levels),
                    evidence=tuple(evidence_items),
                    subject_keys=(RULE_BROAD_FOUNDATIONS, "broad_foundations", joined),
                )
            ]
        )


class LimitedFoundationsRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LIMITED_FOUNDATIONS,
            title="Limited AI-readiness evidence foundations",
            description=(
                "Observes AI-related assets with fewer than three active evidence "
                "families. Does not claim foundations are insufficient for AI."
            ),
            severity=RuleSeverity.LOW,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return _ai_readiness_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        evidence = repository_ai_readiness_evidence(context)
        assert evidence is not None
        families = active_families(evidence)
        if len(families) >= 3:
            return SharedRuleEvaluationResult.not_matched()
        if not ai_related_assets_present(evidence):
            return SharedRuleEvaluationResult.not_matched()
        joined = ",".join(families)
        category = AiReadinessCategory.MISCELLANEOUS
        facts: list[AiReadinessFact] = [
            *[
                item
                for item in evidence.ai_integration_facts
                if item.kind is not AiReadinessAiIntegrationKind.UNKNOWN
            ],
            *[item for item in evidence.tool_mcp_facts if item.kind.value != "unknown"],
            *[item for item in evidence.workflow_agent_facts if item.kind.value != "unknown"],
        ]
        evidence_items: list[RuleEvidence] = [
            evidence_summary(
                rule_id=RULE_LIMITED_FOUNDATIONS,
                message=f"family_count={len(families)}; families={joined}",
                ai_readiness_category=category,
                attributes={
                    "families": joined,
                    "family_count": str(len(families)),
                },
            ),
            *path_evidence_from_facts(
                facts=facts,
                ai_readiness_category=category,
                label="limited_foundation_fact",
            ),
        ]
        family_word = "family" if len(families) == 1 else "families"
        suffix = f" ({joined})" if joined else ""
        return _sorted_matches(
            [
                match(
                    rule_id=RULE_LIMITED_FOUNDATIONS,
                    title="Limited AI-readiness evidence foundations",
                    summary=(
                        "Repository AI-readiness evidence includes AI-related "
                        f"assets with {len(families)} active evidence "
                        f"{family_word}{suffix}. This does not establish "
                        "readiness gaps."
                    ),
                    severity=RuleSeverity.LOW,
                    confidence=confidence_from_levels([item.confirmation_level for item in facts]),
                    evidence=tuple(evidence_items),
                    subject_keys=(
                        RULE_LIMITED_FOUNDATIONS,
                        "limited_foundations",
                        joined or "0",
                    ),
                )
            ]
        )
