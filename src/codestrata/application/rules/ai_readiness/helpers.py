"""Shared helpers for AI Readiness Hygiene SharedRules (Phase 4.8.3)."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.ai_readiness.ids import (
    PACK_ID,
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
    RULE_VERSION,
    RULE_WORKFLOW_AGENT,
)
from codestrata.domain.ai_readiness.taxonomy import AiReadinessCategory
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDocumentationKind,
    AiReadinessObservabilityGovernanceKind,
    AiReadinessToolMcpKind,
    AiReadinessWorkflowAgentKind,
    EvidenceConfirmationLevel,
    RepositoryAiReadinessParseStatus,
)
from codestrata.domain.evidence.repository_ai_readiness.models import (
    AggregatedRepositoryAiReadinessEvidence,
    AiReadinessAiIntegrationFactEvidence,
    AiReadinessApiBoundaryFactEvidence,
    AiReadinessDataRetrievalFactEvidence,
    AiReadinessDocumentationFactEvidence,
    AiReadinessObservabilityGovernanceFactEvidence,
    AiReadinessToolMcpFactEvidence,
    AiReadinessWorkflowAgentFactEvidence,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    RuleCategory,
    RuleConfidence,
    RuleEvidenceKind,
    RuleIncrementalBehavior,
    RuleSeverity,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.identifiers import RuleId
from codestrata.domain.rules.metadata import RuleMetadata, RuleVersion
from codestrata.domain.rules.results import RuleMatch, SharedRuleEvaluationResult

_PROVENANCE = "aggregated_repository_ai_readiness_evidence"
_MAX_PATH_EVIDENCE = 12

_API_BOUNDARY_KINDS = frozenset(
    {
        AiReadinessApiBoundaryKind.REST,
        AiReadinessApiBoundaryKind.GRAPHQL,
        AiReadinessApiBoundaryKind.GRPC,
        AiReadinessApiBoundaryKind.CONTROLLER,
        AiReadinessApiBoundaryKind.ROUTER,
        AiReadinessApiBoundaryKind.HANDLER,
    }
)

_DOCS_ARCHITECTURE_KINDS = frozenset(
    {
        AiReadinessDocumentationKind.ARCHITECTURE,
        AiReadinessDocumentationKind.ADR,
    }
)

_DOCS_SUPPORTING_KINDS = frozenset(
    {
        AiReadinessDocumentationKind.README,
        AiReadinessDocumentationKind.ARCHITECTURE,
        AiReadinessDocumentationKind.ADR,
        AiReadinessDocumentationKind.API_DOCS,
    }
)

_SEARCH_KINDS = frozenset(
    {
        AiReadinessDataRetrievalKind.SEARCH_ENGINE,
        AiReadinessDataRetrievalKind.RETRIEVAL_INDEX,
        AiReadinessDataRetrievalKind.INGESTION,
    }
)

_VECTOR_DATA_KINDS = frozenset(
    {
        AiReadinessDataRetrievalKind.VECTOR_DB,
        AiReadinessDataRetrievalKind.EMBEDDINGS,
    }
)

_LLM_KINDS = frozenset(
    {
        AiReadinessAiIntegrationKind.LLM_SDK,
        AiReadinessAiIntegrationKind.AI_FRAMEWORK,
    }
)

AiReadinessFact = (
    AiReadinessApiBoundaryFactEvidence
    | AiReadinessDocumentationFactEvidence
    | AiReadinessDataRetrievalFactEvidence
    | AiReadinessAiIntegrationFactEvidence
    | AiReadinessToolMcpFactEvidence
    | AiReadinessWorkflowAgentFactEvidence
    | AiReadinessObservabilityGovernanceFactEvidence
)


def repository_ai_readiness_evidence(
    context: RuleExecutionContext,
) -> AggregatedRepositoryAiReadinessEvidence | None:
    raw = context.repository_ai_readiness_evidence
    if isinstance(raw, AggregatedRepositoryAiReadinessEvidence):
        return raw
    return None


def evidence_is_usable(
    evidence: AggregatedRepositoryAiReadinessEvidence | None,
) -> bool:
    if evidence is None:
        return False
    if evidence.status in {
        RepositoryAiReadinessParseStatus.NOT_APPLICABLE,
        RepositoryAiReadinessParseStatus.SKIPPED,
        RepositoryAiReadinessParseStatus.FAILED,
        RepositoryAiReadinessParseStatus.INSUFFICIENT_EVIDENCE,
    }:
        return False
    if evidence.status not in {
        RepositoryAiReadinessParseStatus.SUCCEEDED,
        RepositoryAiReadinessParseStatus.PARTIALLY_SUCCEEDED,
    }:
        return False
    return bool(
        evidence.file_candidates
        or evidence.api_boundary_facts
        or evidence.documentation_facts
        or evidence.data_retrieval_facts
        or evidence.ai_integration_facts
        or evidence.tool_mcp_facts
        or evidence.workflow_agent_facts
        or evidence.observability_governance_facts
    )


def known_api_boundary_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessApiBoundaryKind, ...]:
    values = {item.kind for item in evidence.api_boundary_facts if item.kind in _API_BOUNDARY_KINDS}
    return tuple(sorted(values, key=lambda item: item.value))


def known_openapi_facts(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessApiBoundaryFactEvidence, ...]:
    return tuple(
        sorted(
            (
                item
                for item in evidence.api_boundary_facts
                if item.kind is AiReadinessApiBoundaryKind.OPENAPI
            ),
            key=lambda item: (item.path, item.evidence_id),
        )
    )


def known_docs_architecture_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessDocumentationKind, ...]:
    values = {
        item.kind for item in evidence.documentation_facts if item.kind in _DOCS_ARCHITECTURE_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_docs_supporting_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessDocumentationKind, ...]:
    values = {
        item.kind for item in evidence.documentation_facts if item.kind in _DOCS_SUPPORTING_KINDS
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_data_access_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessDataRetrievalKind, ...]:
    values = {
        item.kind
        for item in evidence.data_retrieval_facts
        if item.kind is AiReadinessDataRetrievalKind.DATABASE_REPOSITORY
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_search_retrieval_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessDataRetrievalKind, ...]:
    values = {item.kind for item in evidence.data_retrieval_facts if item.kind in _SEARCH_KINDS}
    return tuple(sorted(values, key=lambda item: item.value))


def known_vector_embedding_signals(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[str, ...]:
    values: set[str] = set()
    for data_fact in evidence.data_retrieval_facts:
        if data_fact.kind in _VECTOR_DATA_KINDS:
            values.add(data_fact.kind.value)
    for ai_fact in evidence.ai_integration_facts:
        if ai_fact.kind is AiReadinessAiIntegrationKind.EMBEDDINGS_USAGE:
            values.add(ai_fact.kind.value)
    return tuple(sorted(values))


def known_llm_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessAiIntegrationKind, ...]:
    values = {item.kind for item in evidence.ai_integration_facts if item.kind in _LLM_KINDS}
    return tuple(sorted(values, key=lambda item: item.value))


def known_prompt_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessAiIntegrationKind, ...]:
    values = {
        item.kind
        for item in evidence.ai_integration_facts
        if item.kind is AiReadinessAiIntegrationKind.PROMPT
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_rag_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessAiIntegrationKind, ...]:
    values = {
        item.kind
        for item in evidence.ai_integration_facts
        if item.kind is AiReadinessAiIntegrationKind.RAG_PIPELINE
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_tool_mcp_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessToolMcpKind, ...]:
    values = {
        item.kind
        for item in evidence.tool_mcp_facts
        if item.kind is not AiReadinessToolMcpKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_workflow_agent_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessWorkflowAgentKind, ...]:
    values = {
        item.kind
        for item in evidence.workflow_agent_facts
        if item.kind is not AiReadinessWorkflowAgentKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def known_observability_governance_kinds(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[AiReadinessObservabilityGovernanceKind, ...]:
    values = {
        item.kind
        for item in evidence.observability_governance_facts
        if item.kind is not AiReadinessObservabilityGovernanceKind.UNKNOWN
    }
    return tuple(sorted(values, key=lambda item: item.value))


def active_families(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> tuple[str, ...]:
    families: list[str] = []
    if known_api_boundary_kinds(evidence) or known_openapi_facts(evidence):
        families.append("api_boundary")
    if any(
        item.kind is not AiReadinessDocumentationKind.UNKNOWN
        for item in evidence.documentation_facts
    ):
        families.append("documentation")
    if any(
        item.kind is not AiReadinessDataRetrievalKind.UNKNOWN
        for item in evidence.data_retrieval_facts
    ):
        families.append("data_retrieval")
    if any(
        item.kind is not AiReadinessAiIntegrationKind.UNKNOWN
        for item in evidence.ai_integration_facts
    ):
        families.append("ai_integration")
    if known_tool_mcp_kinds(evidence):
        families.append("tool_mcp")
    if known_workflow_agent_kinds(evidence):
        families.append("workflow_agent")
    if known_observability_governance_kinds(evidence):
        families.append("observability_governance")
    return tuple(sorted(families))


def ai_related_assets_present(
    evidence: AggregatedRepositoryAiReadinessEvidence,
) -> bool:
    return bool(
        any(
            item.kind is not AiReadinessAiIntegrationKind.UNKNOWN
            for item in evidence.ai_integration_facts
        )
        or known_tool_mcp_kinds(evidence)
        or known_workflow_agent_kinds(evidence)
    )


def confidence_from_levels(
    levels: Sequence[EvidenceConfirmationLevel],
) -> RuleConfidence:
    if any(level is EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED for level in levels):
        return RuleConfidence.HIGH
    if any(
        level
        in {
            EvidenceConfirmationLevel.STRUCTURALLY_INSPECTED,
            EvidenceConfirmationLevel.DECLARED,
            EvidenceConfirmationLevel.CONFIGURED,
        }
        for level in levels
    ):
        return RuleConfidence.MEDIUM
    return RuleConfidence.LOW


def observation_note(rule_id: str) -> str:
    return (
        "Observation only: review the repository AI-readiness evidence facts for "
        f"{rule_id}. This finding does not prescribe a remediation."
    )


def make_metadata(
    *,
    rule_id: str,
    title: str,
    description: str,
    severity: RuleSeverity = RuleSeverity.INFORMATIONAL,
) -> RuleMetadata:
    return RuleMetadata(
        rule_id=RuleId(rule_id),
        version=RuleVersion.parse(RULE_VERSION),
        title=title,
        description=description,
        category=RuleCategory.AI_READINESS,
        default_severity=severity,
        supported_languages=(),
        tags=("ai_readiness", PACK_ID, "hygiene", "dimension:ai_readiness"),
        remediation_summary=observation_note(rule_id),
        documentation_reference=("docs/analysis-intelligence/shared-rule-platform.md"),
        enabled_by_default=True,
        experimental=False,
        requires_enterprise_context=False,
        incremental_behaviors=(
            RuleIncrementalBehavior.AFFECTED_BY_SOURCE_CHANGES,
            RuleIncrementalBehavior.REQUIRES_FULL_CONTEXT,
        ),
    )


def match(
    *,
    rule_id: str,
    title: str,
    summary: str,
    severity: RuleSeverity,
    confidence: RuleConfidence,
    evidence: tuple[RuleEvidence, ...],
    subject_keys: tuple[str, ...],
) -> RuleMatch:
    return RuleMatch(
        rule_id=RuleId(rule_id),
        rule_version=RuleVersion.parse(RULE_VERSION),
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        evidence=evidence,
        remediation=observation_note(rule_id),
        affected_entities=subject_keys,
        provenance=PACK_ID,
        subject_keys=subject_keys,
    )


def evidence_summary(
    *,
    rule_id: str,
    message: str,
    ai_readiness_category: AiReadinessCategory,
    attributes: dict[str, str] | None = None,
) -> RuleEvidence:
    attrs = {
        "ai_readiness_category": ai_readiness_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.REPOSITORY_FACT,
        subject_reference=f"{rule_id}:summary",
        message=message,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def evidence_path(
    *,
    evidence_id: str,
    path: str,
    message: str,
    ai_readiness_category: AiReadinessCategory,
    attributes: dict[str, str] | None = None,
    line_start: int | None = None,
) -> RuleEvidence:
    attrs = {
        "evidence_id": evidence_id,
        "path": path,
        "ai_readiness_category": ai_readiness_category.value,
        **(attributes or {}),
    }
    return RuleEvidence(
        kind=RuleEvidenceKind.FILE_LOCATION,
        subject_reference=evidence_id,
        message=message,
        safe_location=path,
        line_start=line_start,
        line_end=line_start,
        attributes=attrs,
        provenance=_PROVENANCE,
    )


def path_evidence_from_facts(
    *,
    facts: Sequence[AiReadinessFact],
    ai_readiness_category: AiReadinessCategory,
    label: str,
) -> tuple[RuleEvidence, ...]:
    ordered = sorted(facts, key=lambda item: (item.path, item.evidence_id))
    items: list[RuleEvidence] = []
    for fact in ordered[:_MAX_PATH_EVIDENCE]:
        line = fact.line_hints[0] if fact.line_hints else None
        items.append(
            evidence_path(
                evidence_id=fact.evidence_id,
                path=fact.path,
                message=f"{label}; confirmation={fact.confirmation_level.value}",
                ai_readiness_category=ai_readiness_category,
                attributes={
                    "confirmation_level": fact.confirmation_level.value,
                    "detail": (fact.detail or "")[:200],
                },
                line_start=line,
            )
        )
    return tuple(items)


def enrich_finding_metadata(rule_id: str) -> dict[str, str]:
    category = category_for_rule(rule_id)
    return {
        "taxonomy_id": category.value,
        "ai_readiness_category": category.value,
        "assessment_dimensions": "ai_readiness",
        "business_impact": "unknown",
        "pack_id": PACK_ID,
        "pack_version": PACK_VERSION,
        "observation_only": "true",
    }


def category_for_rule(rule_id: str) -> AiReadinessCategory:
    mapping = {
        RULE_API_BOUNDARIES: AiReadinessCategory.API_AND_SERVICE_BOUNDARIES,
        RULE_STRUCTURED_API_SPEC: AiReadinessCategory.API_AND_SERVICE_BOUNDARIES,
        RULE_LIMITED_API_BOUNDARIES: AiReadinessCategory.API_AND_SERVICE_BOUNDARIES,
        RULE_ARCHITECTURE_DOCS: AiReadinessCategory.DOCUMENTATION_AND_METADATA_QUALITY,
        RULE_LIMITED_DOCUMENTATION: AiReadinessCategory.DOCUMENTATION_AND_METADATA_QUALITY,
        RULE_DATA_ACCESS: AiReadinessCategory.DATA_ACCESS_PATTERNS,
        RULE_SEARCH_RETRIEVAL: AiReadinessCategory.SEARCH_AND_RETRIEVAL_READINESS,
        RULE_VECTOR_EMBEDDINGS: AiReadinessCategory.RAG_ENABLING_ASSETS,
        RULE_LLM_SDK: AiReadinessCategory.EXISTING_AI_LLM_INTEGRATIONS,
        RULE_PROMPT_ASSETS: AiReadinessCategory.EXISTING_AI_LLM_INTEGRATIONS,
        RULE_RAG_PIPELINE: AiReadinessCategory.RAG_ENABLING_ASSETS,
        RULE_MCP_TOOLS: AiReadinessCategory.TOOL_AND_MCP_INTEGRATION,
        RULE_WORKFLOW_AGENT: AiReadinessCategory.WORKFLOW_AND_AGENT_BOUNDARIES,
        RULE_OBSERVABILITY_GOVERNANCE: AiReadinessCategory.OBSERVABILITY_AND_GOVERNANCE,
        RULE_AI_WITHOUT_OBSERVABILITY: AiReadinessCategory.OBSERVABILITY_AND_GOVERNANCE,
        RULE_BROAD_FOUNDATIONS: AiReadinessCategory.MISCELLANEOUS,
        RULE_LIMITED_FOUNDATIONS: AiReadinessCategory.MISCELLANEOUS,
    }
    return mapping.get(rule_id, AiReadinessCategory.UNKNOWN)


def _sorted_matches(matches: list[RuleMatch]) -> SharedRuleEvaluationResult:
    if not matches:
        return SharedRuleEvaluationResult.not_matched()
    return SharedRuleEvaluationResult.matched(
        tuple(
            sorted(
                matches,
                key=lambda item: (
                    str(item.rule_id),
                    tuple(item.subject_keys),
                    item.title,
                    item.summary,
                ),
            )
        )
    )
