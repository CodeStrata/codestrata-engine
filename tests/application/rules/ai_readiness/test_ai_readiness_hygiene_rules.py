"""AI Readiness Hygiene SharedRule tests (Phase 4.8.3)."""

from __future__ import annotations

import random

from codestrata.application.rules.ai_readiness.helpers import (
    active_families,
    evidence_is_usable,
)
from codestrata.application.rules.ai_readiness.pack import AiReadinessRulePack
from codestrata.application.rules.ai_readiness.pack import (
    ai_readiness_rules as load_ai_readiness_rules,
)
from codestrata.application.rules.ai_readiness.registration import register_ai_readiness_pack
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
from codestrata.application.rules.finding_mapper import RuleFindingMapper
from codestrata.application.rules.registry import RuleRegistry
from codestrata.config import load_settings
from codestrata.domain.ai_readiness.ids import (
    AI_READINESS_RULE_IDS,
    DEFERRED_RULE_IDS,
    HYGIENE_RULE_IDS,
    PACK_ID,
    RULE_ALIAS_TO_ID,
    RULE_API_BOUNDARIES,
    RULE_LIMITED_FOUNDATIONS,
)
from codestrata.domain.evidence.language.provenance import EvidenceProvenance
from codestrata.domain.evidence.repository_ai_readiness.enums import (
    AiReadinessAiIntegrationKind,
    AiReadinessApiBoundaryKind,
    AiReadinessDataRetrievalKind,
    AiReadinessDocumentationKind,
    AiReadinessEvidenceFamily,
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
    AiReadinessFileCandidateEvidence,
    AiReadinessObservabilityGovernanceFactEvidence,
    AiReadinessToolMcpFactEvidence,
    AiReadinessWorkflowAgentFactEvidence,
    RepositoryAiReadinessEvidenceCoverage,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleCategory, RuleResultStatus, RuleSeverity
from codestrata.services.artifact_serialization import dumps_stable_json


def _prov() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider_id="test",
        provider_version="1.0.0",
        source_analyzer="test",
        extraction_method="test",
    )


def _api(
    *,
    kind: AiReadinessApiBoundaryKind = AiReadinessApiBoundaryKind.REST,
    path: str = "src/api.py",
    evidence_id: str | None = None,
) -> AiReadinessApiBoundaryFactEvidence:
    return AiReadinessApiBoundaryFactEvidence(
        evidence_id=evidence_id or f"api:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _docs(
    *,
    kind: AiReadinessDocumentationKind = AiReadinessDocumentationKind.README,
    path: str = "README.md",
    evidence_id: str | None = None,
) -> AiReadinessDocumentationFactEvidence:
    return AiReadinessDocumentationFactEvidence(
        evidence_id=evidence_id or f"doc:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _data(
    *,
    kind: AiReadinessDataRetrievalKind = AiReadinessDataRetrievalKind.DATABASE_REPOSITORY,
    path: str = "src/repo.py",
    evidence_id: str | None = None,
) -> AiReadinessDataRetrievalFactEvidence:
    return AiReadinessDataRetrievalFactEvidence(
        evidence_id=evidence_id or f"data:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _ai(
    *,
    kind: AiReadinessAiIntegrationKind = AiReadinessAiIntegrationKind.LLM_SDK,
    path: str = "src/llm.py",
    evidence_id: str | None = None,
) -> AiReadinessAiIntegrationFactEvidence:
    return AiReadinessAiIntegrationFactEvidence(
        evidence_id=evidence_id or f"ai:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _tool(
    *,
    kind: AiReadinessToolMcpKind = AiReadinessToolMcpKind.MCP_SERVER,
    path: str = "mcp.json",
    evidence_id: str | None = None,
) -> AiReadinessToolMcpFactEvidence:
    return AiReadinessToolMcpFactEvidence(
        evidence_id=evidence_id or f"tool:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _workflow(
    *,
    kind: AiReadinessWorkflowAgentKind = AiReadinessWorkflowAgentKind.WORKFLOW_ENGINE,
    path: str = "workflows/main.py",
    evidence_id: str | None = None,
) -> AiReadinessWorkflowAgentFactEvidence:
    return AiReadinessWorkflowAgentFactEvidence(
        evidence_id=evidence_id or f"wf:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _obs(
    *,
    kind: AiReadinessObservabilityGovernanceKind = (
        AiReadinessObservabilityGovernanceKind.LOGGING_TRACING_METRICS
    ),
    path: str = "otel.py",
    evidence_id: str | None = None,
) -> AiReadinessObservabilityGovernanceFactEvidence:
    return AiReadinessObservabilityGovernanceFactEvidence(
        evidence_id=evidence_id or f"obs:{kind.value}:{path}",
        kind=kind,
        path=path,
        confirmation_level=EvidenceConfirmationLevel.STRUCTURALLY_CONFIRMED,
        provenance=_prov(),
    )


def _candidate(
    *,
    path: str = "marker.txt",
    family: AiReadinessEvidenceFamily = AiReadinessEvidenceFamily.DOCUMENTATION,
) -> AiReadinessFileCandidateEvidence:
    return AiReadinessFileCandidateEvidence(
        evidence_id=f"cand:{path}",
        path=path,
        family=family,
        confirmation_level=EvidenceConfirmationLevel.DISCOVERED_CANDIDATE,
        provenance=_prov(),
    )


def _bundle(
    *,
    api: tuple[AiReadinessApiBoundaryFactEvidence, ...] = (),
    docs: tuple[AiReadinessDocumentationFactEvidence, ...] = (),
    data: tuple[AiReadinessDataRetrievalFactEvidence, ...] = (),
    ai: tuple[AiReadinessAiIntegrationFactEvidence, ...] = (),
    tools: tuple[AiReadinessToolMcpFactEvidence, ...] = (),
    workflow: tuple[AiReadinessWorkflowAgentFactEvidence, ...] = (),
    obs: tuple[AiReadinessObservabilityGovernanceFactEvidence, ...] = (),
    candidates: tuple[AiReadinessFileCandidateEvidence, ...] = (),
    status: RepositoryAiReadinessParseStatus = RepositoryAiReadinessParseStatus.SUCCEEDED,
) -> AggregatedRepositoryAiReadinessEvidence:
    technologies = sorted(
        {
            *(item.kind.value for item in api),
            *(item.kind.value for item in docs),
            *(item.kind.value for item in data),
            *(item.kind.value for item in ai),
            *(item.kind.value for item in tools),
            *(item.kind.value for item in workflow),
            *(item.kind.value for item in obs),
        }
    )
    total = (
        len(api)
        + len(docs)
        + len(data)
        + len(ai)
        + len(tools)
        + len(workflow)
        + len(obs)
        + len(candidates)
    )
    return AggregatedRepositoryAiReadinessEvidence(
        repository_id="fixture",
        status=status,
        file_candidates=candidates,
        api_boundary_facts=api,
        documentation_facts=docs,
        data_retrieval_facts=data,
        ai_integration_facts=ai,
        tool_mcp_facts=tools,
        workflow_agent_facts=workflow,
        observability_governance_facts=obs,
        coverage=RepositoryAiReadinessEvidenceCoverage(
            candidate_files_discovered=max(1, total) if total else 0,
            candidate_files_inspected=1 if total else 0,
            api_boundary_facts=len(api),
            documentation_facts=len(docs),
            data_retrieval_facts=len(data),
            ai_integration_facts=len(ai),
            tool_mcp_facts=len(tools),
            workflow_agent_facts=len(workflow),
            observability_governance_facts=len(obs),
            technologies_represented=tuple(technologies),
        ),
        evidence_fingerprint="deadbeef",
    )


def _context(
    evidence: AggregatedRepositoryAiReadinessEvidence | None,
) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        repository_ai_readiness_evidence=evidence,
    )


def test_pack_registration_and_catalog() -> None:
    registry = RuleRegistry()
    pack = register_ai_readiness_pack(registry)
    assert pack.pack_id == PACK_ID
    assert len(load_ai_readiness_rules()) == 17
    assert len(load_ai_readiness_rules()) == len(HYGIENE_RULE_IDS)
    assert AI_READINESS_RULE_IDS == HYGIENE_RULE_IDS
    assert DEFERRED_RULE_IDS == ()
    assert registry.size == len(HYGIENE_RULE_IDS)
    rule_ids = [str(rule.metadata.rule_id) for rule in load_ai_readiness_rules()]
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids) == set(HYGIENE_RULE_IDS)
    assert RULE_ALIAS_TO_ID["AI-001"] == RULE_API_BOUNDARIES
    assert RULE_ALIAS_TO_ID["AI-061"] == RULE_LIMITED_FOUNDATIONS
    assert AiReadinessRulePack().included_rule_ids == HYGIENE_RULE_IDS

    mapper = RuleFindingMapper()
    evidence = _bundle(api=(_api(),))
    context = _context(evidence)
    matches = []
    for rule in load_ai_readiness_rules():
        if rule.evaluate_applicability(context).is_applicable:
            matches.extend(rule.evaluate(context).matches)
    findings = mapper.map_matches(
        tuple(matches),
        category_by_rule={rid: RuleCategory.AI_READINESS for rid in HYGIENE_RULE_IDS},
    )
    assert findings
    assert all(item.category is FindingCategory.AI_READINESS for item in findings)
    assert all(
        item.severity in {FindingSeverity.INFORMATIONAL, FindingSeverity.LOW} for item in findings
    )


def test_rules_ai_readiness_gate_defaults(tmp_path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.rules.ai_readiness.enabled is False
    assert settings.rules.ai_readiness.ai_001.enabled is True
    assert settings.analysis.ai_readiness.enabled is False

    config.write_text(
        """
        [repository]
        path = "."

        [rules]
        enabled = true

        [rules.ai_readiness]
        enabled = true
        """,
        encoding="utf-8",
    )
    enabled = load_settings(config)
    assert enabled.rules.ai_readiness.enabled is True
    assert enabled.analysis.ai_readiness.enabled is False


def test_unusable_and_empty_evidence_not_applicable() -> None:
    rule = ApiBoundariesDetectedRule()
    assert not rule.evaluate_applicability(_context(None)).is_applicable

    insufficient = _bundle(
        api=(_api(),),
        status=RepositoryAiReadinessParseStatus.INSUFFICIENT_EVIDENCE,
    )
    assert not evidence_is_usable(insufficient)
    assert not rule.evaluate_applicability(_context(insufficient)).is_applicable

    empty = _bundle()
    assert not evidence_is_usable(empty)
    assert not rule.evaluate_applicability(_context(empty)).is_applicable
    assert not LimitedApiBoundariesRule().evaluate_applicability(_context(empty)).is_applicable


def test_ai001_api_boundaries() -> None:
    rule = ApiBoundariesDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(api=(_api(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL
    assert "rest" in result.matches[0].summary


def test_ai002_structured_api_spec() -> None:
    rule = StructuredApiSpecDetectedRule()
    assert rule.evaluate(_context(_bundle(api=(_api(),)))).status is (RuleResultStatus.NOT_MATCHED)
    result = rule.evaluate(_context(_bundle(api=(_api(kind=AiReadinessApiBoundaryKind.OPENAPI),))))
    assert result.status is RuleResultStatus.MATCHED
    assert "openapi" in result.matches[0].summary.lower()


def test_ai003_limited_api_suppressed_by_001_or_002() -> None:
    rule = LimitedApiBoundariesRule()
    usable_empty_api = _bundle(candidates=(_candidate(),))
    result = rule.evaluate(_context(usable_empty_api))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW

    with_api = _bundle(api=(_api(),))
    assert rule.evaluate(_context(with_api)).status is RuleResultStatus.NOT_MATCHED

    with_openapi = _bundle(api=(_api(kind=AiReadinessApiBoundaryKind.OPENAPI),))
    assert rule.evaluate(_context(with_openapi)).status is RuleResultStatus.NOT_MATCHED


def test_ai010_architecture_docs() -> None:
    rule = ArchitectureDocsDetectedRule()
    assert rule.evaluate(_context(_bundle(docs=(_docs(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(
        _context(
            _bundle(docs=(_docs(kind=AiReadinessDocumentationKind.ARCHITECTURE, path="ARCH.md"),))
        )
    )
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_ai011_limited_docs_suppressed() -> None:
    rule = LimitedDocumentationRule()
    usable = _bundle(candidates=(_candidate(),))
    assert rule.evaluate(_context(usable)).status is RuleResultStatus.MATCHED
    assert rule.evaluate(_context(usable)).matches[0].severity is RuleSeverity.LOW

    with_readme = _bundle(docs=(_docs(),))
    assert rule.evaluate(_context(with_readme)).status is RuleResultStatus.NOT_MATCHED

    with_arch = _bundle(docs=(_docs(kind=AiReadinessDocumentationKind.ARCHITECTURE, path="a.md"),))
    assert rule.evaluate(_context(with_arch)).status is RuleResultStatus.NOT_MATCHED


def test_ai020_data_access() -> None:
    rule = DataAccessDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(data=(_data(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_ai021_search_retrieval() -> None:
    rule = SearchRetrievalDetectedRule()
    assert rule.evaluate(_context(_bundle(data=(_data(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(
        _context(
            _bundle(data=(_data(kind=AiReadinessDataRetrievalKind.SEARCH_ENGINE, path="es.yml"),))
        )
    )
    assert result.status is RuleResultStatus.MATCHED


def test_ai022_vector_embeddings() -> None:
    rule = VectorEmbeddingsDetectedRule()
    from_data = rule.evaluate(
        _context(_bundle(data=(_data(kind=AiReadinessDataRetrievalKind.VECTOR_DB, path="vdb.py"),)))
    )
    assert from_data.status is RuleResultStatus.MATCHED

    from_ai = rule.evaluate(
        _context(
            _bundle(ai=(_ai(kind=AiReadinessAiIntegrationKind.EMBEDDINGS_USAGE, path="emb.py"),))
        )
    )
    assert from_ai.status is RuleResultStatus.MATCHED
    assert rule.evaluate(_context(_bundle(ai=(_ai(),)))).status is (RuleResultStatus.NOT_MATCHED)


def test_ai030_llm_sdk() -> None:
    rule = LlmSdkDetectedRule()
    assert rule.evaluate(_context(_bundle(candidates=(_candidate(),)))).status is (
        RuleResultStatus.NOT_MATCHED
    )
    result = rule.evaluate(_context(_bundle(ai=(_ai(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_ai031_prompt_assets() -> None:
    rule = PromptAssetsDetectedRule()
    result = rule.evaluate(
        _context(_bundle(ai=(_ai(kind=AiReadinessAiIntegrationKind.PROMPT, path="p.txt"),)))
    )
    assert result.status is RuleResultStatus.MATCHED


def test_ai032_rag_pipeline() -> None:
    rule = RagPipelineDetectedRule()
    result = rule.evaluate(
        _context(_bundle(ai=(_ai(kind=AiReadinessAiIntegrationKind.RAG_PIPELINE, path="rag.py"),)))
    )
    assert result.status is RuleResultStatus.MATCHED


def test_ai040_mcp_tools() -> None:
    rule = McpToolsDetectedRule()
    result = rule.evaluate(_context(_bundle(tools=(_tool(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_ai041_workflow_agent() -> None:
    rule = WorkflowAgentDetectedRule()
    result = rule.evaluate(_context(_bundle(workflow=(_workflow(),))))
    assert result.status is RuleResultStatus.MATCHED


def test_ai050_observability() -> None:
    rule = ObservabilityGovernanceDetectedRule()
    result = rule.evaluate(_context(_bundle(obs=(_obs(),))))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.INFORMATIONAL


def test_ai051_ai_without_observability_suppressed() -> None:
    rule = AiWithoutObservabilityRule()
    with_obs = _bundle(ai=(_ai(),), obs=(_obs(),))
    assert rule.evaluate(_context(with_obs)).status is RuleResultStatus.NOT_MATCHED

    no_ai = _bundle(docs=(_docs(),))
    assert rule.evaluate(_context(no_ai)).status is RuleResultStatus.NOT_MATCHED

    gap = _bundle(ai=(_ai(),))
    result = rule.evaluate(_context(gap))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_ai060_broad_foundations() -> None:
    rule = BroadFoundationsRule()
    two = _bundle(docs=(_docs(),), ai=(_ai(),))
    assert len(active_families(two)) == 2
    assert rule.evaluate(_context(two)).status is RuleResultStatus.NOT_MATCHED

    three = _bundle(docs=(_docs(),), ai=(_ai(),), tools=(_tool(),))
    assert len(active_families(three)) == 3
    result = rule.evaluate(_context(three))
    assert result.status is RuleResultStatus.MATCHED
    assert "does not establish ai readiness" in result.matches[0].summary.lower()


def test_ai061_limited_foundations_suppressed() -> None:
    rule = LimitedFoundationsRule()
    broad = _bundle(docs=(_docs(),), ai=(_ai(),), tools=(_tool(),))
    assert rule.evaluate(_context(broad)).status is RuleResultStatus.NOT_MATCHED

    no_ai = _bundle(docs=(_docs(),), data=(_data(),))
    assert rule.evaluate(_context(no_ai)).status is RuleResultStatus.NOT_MATCHED

    limited = _bundle(ai=(_ai(),), docs=(_docs(),))
    result = rule.evaluate(_context(limited))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.LOW


def test_partial_docs_only_behavior() -> None:
    docs_only = _bundle(docs=(_docs(),))
    assert LimitedDocumentationRule().evaluate(_context(docs_only)).status is (
        RuleResultStatus.NOT_MATCHED
    )
    assert LimitedApiBoundariesRule().evaluate(_context(docs_only)).status is (
        RuleResultStatus.MATCHED
    )


def test_determinism_stable_finding_ids() -> None:
    facts = [_api(path=f"api_{i}.py", evidence_id=f"a{i}") for i in range(5)]
    shuffled = list(facts)
    random.Random(7).shuffle(shuffled)
    left = ApiBoundariesDetectedRule().evaluate(_context(_bundle(api=tuple(facts))))
    right = ApiBoundariesDetectedRule().evaluate(_context(_bundle(api=tuple(shuffled))))
    assert left.matches[0].subject_keys == right.matches[0].subject_keys

    mapper = RuleFindingMapper()
    findings_left = mapper.map_matches(
        left.matches,
        category_by_rule={RULE_API_BOUNDARIES: RuleCategory.AI_READINESS},
    )
    findings_right = mapper.map_matches(
        right.matches,
        category_by_rule={RULE_API_BOUNDARIES: RuleCategory.AI_READINESS},
    )
    assert findings_left[0].id == findings_right[0].id
    left_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_left])
    right_bytes = dumps_stable_json([item.model_dump(mode="json") for item in findings_right])
    assert left_bytes == right_bytes


def test_no_remediation_or_advice() -> None:
    result = LimitedApiBoundariesRule().evaluate(_context(_bundle(candidates=(_candidate(),))))
    assert result.matches[0].remediation.startswith("Observation only:")
    text = dumps_stable_json([item.model_dump(mode="json") for item in result.matches])
    assert "modernize" not in text.lower()
    assert "should" not in text.lower()
    assert "ai ready" not in text.lower()
    assert "/Users/" not in text
