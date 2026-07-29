"""AI Readiness synthesis tests (Phase 4.8.5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codestrata.application.ai_readiness.assessment.artifacts import (
    ai_readiness_assessment_payload as build_ai_readiness_assessment_payload,
)
from codestrata.application.ai_readiness.assessment.artifacts import (
    write_ai_readiness_assessment_artifact,
)
from codestrata.application.ai_readiness.assessment.assembler import AiReadinessAssessmentAssembler
from codestrata.application.ai_readiness.assessment.inventory import execution_facts_from_status_map
from codestrata.application.ai_readiness.synthesis import synthesize_ai_readiness
from codestrata.config import load_settings
from codestrata.domain.ai_readiness.assessment.enums import (
    AiReadinessAssessmentStatus,
    AiReadinessLimitationCategory,
)
from codestrata.domain.ai_readiness.assessment.identifiers import SECTION_SCHEMA_VERSION
from codestrata.domain.ai_readiness.assessment.models import (
    AiReadinessCapabilityFamilyInventory,
    AiReadinessFindingInventory,
    AiReadinessLimitation,
    AiReadinessRuleInventory,
)
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
from codestrata.domain.ai_readiness.synthesis.enums import (
    AiReadinessConclusionKind,
    AiReadinessRecommendationKind,
    AiReadinessSynthesisStatus,
    AiReadinessThemeKind,
)
from codestrata.domain.ai_readiness.synthesis.identifiers import SYNTHESIS_VERSION
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.services.artifact_serialization import dumps_stable_json


def _finding(
    *,
    rule_id: str,
    finding_id: str,
    severity: FindingSeverity = FindingSeverity.INFORMATIONAL,
    confidence: str = "high",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} finding",
        description=f"Bounded explanation for {rule_id}",
        severity=severity,
        category=FindingCategory.AI_READINESS,
        metadata={"confidence": confidence},
    )


def _facts_all_matched(matched: set[str]) -> tuple:
    status = {
        rule_id: ("matched" if rule_id in matched else "not_matched")
        for rule_id in HYGIENE_RULE_IDS
    }
    return execution_facts_from_status_map(status)


def _limitation() -> AiReadinessLimitation:
    return AiReadinessLimitation(
        limitation_id="ai-readiness-limitation:scope",
        category=AiReadinessLimitationCategory.NO_AI_READINESS_CONCLUSION,
        summary="AI readiness scoring remains out of scope for this assessment.",
        affected_capability="ai_readiness",
    )


def _rule_inventory(*, matched: int, executed: int | None = None) -> AiReadinessRuleInventory:
    executed_count = executed if executed is not None else len(HYGIENE_RULE_IDS)
    return AiReadinessRuleInventory(
        rules_planned=len(HYGIENE_RULE_IDS),
        rules_executed=executed_count,
        rules_matched=matched,
        rules_not_matched=max(executed_count - matched, 0),
    )


def _assert_no_forbidden(result: object) -> None:
    texts: list[str] = []
    overall = getattr(result, "overall_posture_summary", "") or ""
    texts.append(overall)
    for item in getattr(result, "themes", ()) or ():
        texts.extend([item.title, item.description])
    for item in getattr(result, "conclusions", ()) or ():
        texts.extend([item.title, item.summary, item.technical_interpretation])
    for item in getattr(result, "recommendations", ()) or ():
        texts.extend([item.title, item.action, item.rationale])
    joined = " ".join(texts).lower()
    sanitized = (
        joined.replace("does not establish that the repository is ai ready", "")
        .replace("do not establish that the repository is ai ready", "")
        .replace("does not mean the repository is ai ready", "")
        .replace("the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("without claiming ai readiness", "")
        .replace("from claiming ai readiness", "")
        .replace("claiming ai readiness", "")
        .replace("not readiness scores", "")
        .replace("readiness scoring", "")
        .replace("readiness scores", "")
        .replace("is ai ready", "")
        .replace("are ai ready", "")
        .replace("ai readiness", "")
        .replace("agent ready", "")
        .replace("suitable for rag", "")
    )
    for phrase in (
        "ai ready",
        "agent-ready",
        "rag ready",
        "rag-ready",
        "fully ai-enabled",
        "fully ai enabled",
        "production ready",
        "modernize",
        "modernisation",
        "modernization path",
        "readiness score",
        "readiness grade",
        "implement rag",
        "migrate to",
        "no ai issues",
    ):
        assert phrase not in sanitized, phrase


def test_schema_and_synthesis_gate(tmp_path: Path) -> None:
    assert SECTION_SCHEMA_VERSION == "1.2.0"
    assert SYNTHESIS_VERSION == "1.0.0"
    config = tmp_path / "codestrata.toml"
    config.write_text(
        """
        [repository]
        path = "."
        [rules]
        enabled = true
        [rules.ai_readiness]
        enabled = true
        [analysis.ai_readiness]
        enabled = true
        include_synthesis = false
        """,
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.analysis.ai_readiness.include_synthesis is False
    section = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:gate",
        findings=(),
        include_synthesis=False,
        rules_executed=len(HYGIENE_RULE_IDS),
        rule_execution_facts=_facts_all_matched(set()),
        evidence_fingerprint="syn-fp-1",
    )
    assert section.section_version == "1.2.0"
    assert section.synthesis.status is AiReadinessSynthesisStatus.NOT_REQUESTED
    assert section.metadata.get("assessment_milestone") == "4.8.5"
    assert section.metadata.get("synthesis_version") == SYNTHESIS_VERSION


def test_zero_findings_neutral_posture() -> None:
    result = synthesize_ai_readiness(
        repository_id="repo:empty",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=AiReadinessFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        evidence_status="succeeded",
    )
    assert result.status is AiReadinessSynthesisStatus.EMPTY
    kinds = {item.kind for item in result.themes}
    assert AiReadinessThemeKind.AI_READINESS_HYGIENE_LANDSCAPE in kinds
    assert AiReadinessThemeKind.RULE_EXECUTION_COVERAGE in kinds
    assert AiReadinessThemeKind.NO_HYGIENE_FINDINGS in kinds
    assert AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES not in kinds
    assert result.overall_posture_summary
    _assert_no_forbidden(result)


def test_each_supported_theme() -> None:
    cases = [
        (
            RULE_API_BOUNDARIES,
            AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES,
            AiReadinessConclusionKind.API_AND_SERVICE_BOUNDARIES_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS,
        ),
        (
            RULE_STRUCTURED_API_SPEC,
            AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES,
            AiReadinessConclusionKind.API_AND_SERVICE_BOUNDARIES_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS,
        ),
        (
            RULE_LIMITED_API_BOUNDARIES,
            AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES,
            AiReadinessConclusionKind.API_AND_SERVICE_BOUNDARIES_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS,
        ),
        (
            RULE_ARCHITECTURE_DOCS,
            AiReadinessThemeKind.DOCUMENTATION_MATURITY,
            AiReadinessConclusionKind.DOCUMENTATION_MATURITY_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_DOCUMENTATION_MATURITY_SIGNALS,
        ),
        (
            RULE_LIMITED_DOCUMENTATION,
            AiReadinessThemeKind.DOCUMENTATION_MATURITY,
            AiReadinessConclusionKind.DOCUMENTATION_MATURITY_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_DOCUMENTATION_MATURITY_SIGNALS,
        ),
        (
            RULE_DATA_ACCESS,
            AiReadinessThemeKind.DATA_AND_RETRIEVAL_FOUNDATIONS,
            AiReadinessConclusionKind.DATA_AND_RETRIEVAL_FOUNDATIONS_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_DATA_AND_RETRIEVAL_SIGNALS,
        ),
        (
            RULE_SEARCH_RETRIEVAL,
            AiReadinessThemeKind.DATA_AND_RETRIEVAL_FOUNDATIONS,
            AiReadinessConclusionKind.DATA_AND_RETRIEVAL_FOUNDATIONS_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_DATA_AND_RETRIEVAL_SIGNALS,
        ),
        (
            RULE_VECTOR_EMBEDDINGS,
            AiReadinessThemeKind.DATA_AND_RETRIEVAL_FOUNDATIONS,
            AiReadinessConclusionKind.DATA_AND_RETRIEVAL_FOUNDATIONS_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_DATA_AND_RETRIEVAL_SIGNALS,
        ),
        (
            RULE_LLM_SDK,
            AiReadinessThemeKind.AI_INTEGRATION_MATURITY,
            AiReadinessConclusionKind.AI_INTEGRATION_MATURITY_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS,
        ),
        (
            RULE_PROMPT_ASSETS,
            AiReadinessThemeKind.AI_INTEGRATION_MATURITY,
            AiReadinessConclusionKind.AI_INTEGRATION_MATURITY_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS,
        ),
        (
            RULE_RAG_PIPELINE,
            AiReadinessThemeKind.AI_INTEGRATION_MATURITY,
            AiReadinessConclusionKind.AI_INTEGRATION_MATURITY_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS,
        ),
        (
            RULE_MCP_TOOLS,
            AiReadinessThemeKind.MCP_AND_TOOL_ECOSYSTEM,
            AiReadinessConclusionKind.MCP_AND_TOOL_ECOSYSTEM_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_MCP_AND_TOOL_SIGNALS,
        ),
        (
            RULE_WORKFLOW_AGENT,
            AiReadinessThemeKind.WORKFLOW_AND_AGENT_FOUNDATIONS,
            AiReadinessConclusionKind.WORKFLOW_AND_AGENT_FOUNDATIONS_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_WORKFLOW_AND_AGENT_SIGNALS,
        ),
        (
            RULE_OBSERVABILITY_GOVERNANCE,
            AiReadinessThemeKind.OBSERVABILITY_AND_GOVERNANCE,
            AiReadinessConclusionKind.OBSERVABILITY_AND_GOVERNANCE_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_OBSERVABILITY_AND_GOVERNANCE_SIGNALS,
        ),
        (
            RULE_AI_WITHOUT_OBSERVABILITY,
            AiReadinessThemeKind.OBSERVABILITY_AND_GOVERNANCE,
            AiReadinessConclusionKind.OBSERVABILITY_AND_GOVERNANCE_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_OBSERVABILITY_AND_GOVERNANCE_SIGNALS,
        ),
        (
            RULE_BROAD_FOUNDATIONS,
            AiReadinessThemeKind.BROAD_AI_ENABLEMENT,
            AiReadinessConclusionKind.BROAD_AI_ENABLEMENT_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_BROAD_AI_ENABLEMENT,
        ),
        (
            RULE_LIMITED_FOUNDATIONS,
            AiReadinessThemeKind.LIMITED_SUPPORTING_FOUNDATIONS,
            AiReadinessConclusionKind.LIMITED_SUPPORTING_FOUNDATIONS_OBSERVED,
            AiReadinessRecommendationKind.REVIEW_LIMITED_SUPPORTING_FOUNDATIONS,
        ),
    ]
    for rule_id, theme_kind, conclusion_kind, recommendation_kind in cases:
        finding = _finding(rule_id=rule_id, finding_id=f"f-{rule_id}")
        result = synthesize_ai_readiness(
            repository_id="repo:themes",
            pack_enabled=True,
            section_status=AiReadinessAssessmentStatus.SUCCEEDED,
            findings=(finding,),
            finding_inventory=AiReadinessFindingInventory(
                finding_ids=(finding.id,),
                finding_count=1,
                rule_counts={rule_id: 1},
            ),
            rule_inventory=_rule_inventory(matched=1),
        )
        assert result.status is AiReadinessSynthesisStatus.SUCCEEDED
        assert theme_kind in {item.kind for item in result.themes}
        assert conclusion_kind in {item.kind for item in result.conclusions}
        assert recommendation_kind in {item.kind for item in result.recommendations}
        rec = next(item for item in result.recommendations if item.kind is recommendation_kind)
        assert finding.id in rec.finding_ids
        assert rule_id in rec.rule_ids
        assert rec.conclusion_ids
        _assert_no_forbidden(result)


def test_broad_enablement_from_families_without_ai060() -> None:
    findings = (
        _finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-api"),
        _finding(rule_id=RULE_LLM_SDK, finding_id="f-llm"),
        _finding(rule_id=RULE_MCP_TOOLS, finding_id="f-mcp"),
    )
    result = synthesize_ai_readiness(
        repository_id="repo:partial",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=AiReadinessFindingInventory(
            finding_ids=("f-api", "f-llm", "f-mcp"),
            finding_count=3,
        ),
        rule_inventory=_rule_inventory(matched=3),
        capability_family_inventory=AiReadinessCapabilityFamilyInventory(
            families_observed=3,
            families_total=7,
        ),
    )
    kinds = {item.kind for item in result.themes}
    assert AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES in kinds
    assert AiReadinessThemeKind.AI_INTEGRATION_MATURITY in kinds
    assert AiReadinessThemeKind.MCP_AND_TOOL_ECOSYSTEM in kinds
    assert AiReadinessThemeKind.BROAD_AI_ENABLEMENT in kinds
    assert AiReadinessThemeKind.LIMITED_SUPPORTING_FOUNDATIONS not in kinds


def test_limited_supporting_foundations() -> None:
    finding = _finding(rule_id=RULE_LIMITED_FOUNDATIONS, finding_id="f-lim")
    result = synthesize_ai_readiness(
        repository_id="repo:limited",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=(finding,),
        finding_inventory=AiReadinessFindingInventory(
            finding_ids=(finding.id,),
            finding_count=1,
        ),
        rule_inventory=_rule_inventory(matched=1),
        capability_family_inventory=AiReadinessCapabilityFamilyInventory(
            families_observed=1,
            families_total=7,
        ),
    )
    kinds = {item.kind for item in result.themes}
    assert AiReadinessThemeKind.LIMITED_SUPPORTING_FOUNDATIONS in kinds
    assert AiReadinessThemeKind.BROAD_AI_ENABLEMENT not in kinds


def test_unsupported_scope_theme() -> None:
    result = synthesize_ai_readiness(
        repository_id="repo:limits",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=(),
        finding_inventory=AiReadinessFindingInventory(),
        rule_inventory=_rule_inventory(matched=0),
        limitations=(_limitation(),),
    )
    kinds = {item.kind for item in result.themes}
    assert AiReadinessThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in kinds
    assert AiReadinessThemeKind.NO_HYGIENE_FINDINGS in kinds
    assert AiReadinessRecommendationKind.ACKNOWLEDGE_UNSUPPORTED_AI_READINESS_ANALYSIS_SCOPE in {
        item.kind for item in result.recommendations
    }


def test_partial_foundations_assembler(tmp_path: Path) -> None:
    findings = (
        _finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-001"),
        _finding(
            rule_id=RULE_LLM_SDK,
            finding_id="f-002",
            severity=FindingSeverity.LOW,
            confidence="medium",
        ),
    )
    section = AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:partial",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=2,
        rule_execution_facts=_facts_all_matched({RULE_API_BOUNDARIES, RULE_LLM_SDK}),
        evidence_fingerprint="syn-fp-1",
        configuration_payload="partial-config",
    )
    assert section.synthesis.status is AiReadinessSynthesisStatus.SUCCEEDED
    theme_kinds = {item.kind for item in section.themes}
    assert AiReadinessThemeKind.API_AND_SERVICE_BOUNDARIES in theme_kinds
    assert AiReadinessThemeKind.AI_INTEGRATION_MATURITY in theme_kinds
    assert AiReadinessThemeKind.UNSUPPORTED_ANALYSIS_SCOPE in theme_kinds
    assert AiReadinessThemeKind.MCP_AND_TOOL_ECOSYSTEM not in theme_kinds
    assert AiReadinessThemeKind.DATA_AND_RETRIEVAL_FOUNDATIONS not in theme_kinds
    assert section.execution_summary.theme_count == len(section.themes)
    assert section.execution_summary.conclusion_count == len(section.conclusions)
    assert section.execution_summary.recommendation_count == len(section.recommendations)
    for recommendation in section.recommendations:
        assert recommendation.conclusion_ids
        if recommendation.kind in {
            AiReadinessRecommendationKind.REVIEW_API_AND_SERVICE_BOUNDARY_SIGNALS,
            AiReadinessRecommendationKind.REVIEW_AI_INTEGRATION_SIGNALS,
        }:
            assert recommendation.finding_ids
            assert recommendation.rule_ids
    body = dumps_stable_json(build_ai_readiness_assessment_payload(section))
    assert '"themes"' in body
    assert '"conclusions"' in body
    assert '"recommendations"' in body
    assert '"overall_posture_summary"' in body
    write_ai_readiness_assessment_artifact(section, tmp_path)
    assert (tmp_path / "ai-readiness-assessment.json").read_text(encoding="utf-8") == body
    _assert_no_forbidden(section.synthesis)


def test_deterministic_ordering_and_ids() -> None:
    findings = (
        _finding(rule_id=RULE_LLM_SDK, finding_id="f-b"),
        _finding(rule_id=RULE_API_BOUNDARIES, finding_id="f-a"),
    )
    left = synthesize_ai_readiness(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=findings,
        finding_inventory=AiReadinessFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    right = synthesize_ai_readiness(
        repository_id="repo:det",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.SUCCEEDED,
        findings=tuple(reversed(findings)),
        finding_inventory=AiReadinessFindingInventory(
            finding_ids=("f-a", "f-b"),
            finding_count=2,
        ),
        rule_inventory=_rule_inventory(matched=2),
    )
    assert left.model_dump_json() == right.model_dump_json()
    assert dumps_stable_json(left.model_dump(mode="json")) == dumps_stable_json(
        right.model_dump(mode="json")
    )
    assert left.theme_ids == tuple(item.theme_id for item in left.themes)
    assert left.conclusion_ids == tuple(item.conclusion_id for item in left.conclusions)
    assert all(item.startswith("ai-readiness-theme:") for item in left.theme_ids)
    assert all(item.startswith("ai-readiness-conclusion:") for item in left.conclusion_ids)
    assert all(item.startswith("ai-readiness-recommendation:") for item in left.recommendation_ids)


def test_disabled_and_insufficient_synthesis() -> None:
    disabled = synthesize_ai_readiness(
        repository_id="repo:x",
        pack_enabled=False,
        section_status=AiReadinessAssessmentStatus.DISABLED,
    )
    assert disabled.status is AiReadinessSynthesisStatus.DISABLED
    insufficient = synthesize_ai_readiness(
        repository_id="repo:x",
        pack_enabled=True,
        section_status=AiReadinessAssessmentStatus.INSUFFICIENT_EVIDENCE,
    )
    assert insufficient.status is AiReadinessSynthesisStatus.INSUFFICIENT_EVIDENCE


def test_synthesis_failure_isolation() -> None:
    with patch(
        "codestrata.application.ai_readiness.assessment.assembler.synthesize_ai_readiness",
        side_effect=RuntimeError("boom"),
    ):
        section = AiReadinessAssessmentAssembler().assemble(
            repository_id="repo:fail",
            findings=(),
            rules_executed=len(HYGIENE_RULE_IDS),
            rule_execution_facts=_facts_all_matched(set()),
            evidence_fingerprint="syn-fp-1",
        )
    assert section.synthesis.status is AiReadinessSynthesisStatus.FAILED
    assert section.finding_inventory.finding_count == 0
    assert any("synthesis_failed" in item for item in section.diagnostics)
