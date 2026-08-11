"""Epic 3 Slice 3.8 — AI Readiness Intelligence section tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.ai_readiness.assessment.assembler import (
    AiReadinessAssessmentAssembler,
)
from codestrata.application.ai_readiness.assessment.inventory import (
    execution_facts_from_status_map,
)
from codestrata.domain.ai_readiness.ids import (
    HYGIENE_RULE_IDS,
    RULE_API_BOUNDARIES,
    RULE_LLM_SDK,
    RULE_MCP_TOOLS,
)
from codestrata.domain.findings.enums import FindingCategory, FindingSeverity
from codestrata.domain.findings.models import Finding, FindingEvidence
from codestrata.models import AnalysisResult, Repository
from codestrata.reporting.ai_readiness import (
    AiReadinessReportAdapter,
    build_ai_readiness_intelligence,
)
from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION
from codestrata.reporting.html_v2 import HtmlReportRenderer, build_html_report_view_model
from codestrata.reporting.html_v2.models import EvidenceRefView, FindingView, RecommendationView
from codestrata.reporting.modernization_models import AssessmentMode, ModernizationReportInput

_FORBIDDEN_CLAIMS = (
    "ai ready",
    "agent ready",
    "rag ready",
    "production ai ready",
    "production ready",
    "governed ai",
    "safe ai",
    "mature ai",
    "high-quality data",
    "strong ai foundation",
    "mature ai architecture",
    "no ai readiness risks",
    "no ai issues",
    "readiness score",
    "implement rag",
    "migrate to",
)


def _facts(matched: set[str]):
    return execution_facts_from_status_map(
        {
            rule_id: ("matched" if rule_id in matched else "not_matched")
            for rule_id in HYGIENE_RULE_IDS
        }
    )


def _finding(
    *,
    rule_id: str,
    path: str,
    finding_id: str,
    metadata: dict[str, str] | None = None,
) -> Finding:
    base = {
        "confidence": "high",
        "path": path,
        "evidence_id": f"ev:{path}",
    }
    if metadata:
        base.update(metadata)
    return Finding(
        id=finding_id,
        rule_id=rule_id,
        title=f"{rule_id} at {path}",
        description=f"Bounded explanation for {path}",
        severity=FindingSeverity.INFORMATIONAL,
        category=FindingCategory.AI_READINESS,
        evidence=(
            FindingEvidence(
                evidence_type="repository_ai_readiness",
                source_id=f"ev:{path}",
                path=path,
                excerpt="openapi",
            ),
        ),
        metadata=base,
    )


def _assemble(*, findings=()):
    matched = {item.rule_id for item in findings}
    return AiReadinessAssessmentAssembler().assemble(
        repository_id="repo:demo",
        findings=findings,
        rules_executed=len(HYGIENE_RULE_IDS),
        rules_matched=len(matched),
        rules_not_matched=len(HYGIENE_RULE_IDS) - len(matched),
        rule_execution_facts=_facts(matched),
        evidence_fingerprint="ai-intel-fp",
        configuration_payload="ai-intel",
    )


def _succeeded_report():
    assessment = _assemble(
        findings=(
            _finding(
                rule_id=RULE_API_BOUNDARIES,
                path="openapi.yaml",
                finding_id="api",
                metadata={"api_boundary_kinds": "openapi"},
            ),
            _finding(
                rule_id=RULE_LLM_SDK,
                path="src/llm_client.py",
                finding_id="llm",
                metadata={"llm_kinds": "openai"},
            ),
            _finding(
                rule_id=RULE_MCP_TOOLS,
                path="mcp/server.py",
                finding_id="mcp",
                metadata={"tool_mcp_kinds": "mcp"},
            ),
        )
    )
    return AiReadinessReportAdapter().adapt(assessment)


def _assert_no_forbidden(text: str) -> None:
    lowered = text.lower()
    sanitized = (
        lowered.replace("does not establish that the repository is ai ready", "")
        .replace("does not establish ai readiness", "")
        .replace("do not establish ai readiness", "")
        .replace("absence of findings does not establish ai readiness", "")
        .replace("readiness scores are not measured", "")
        .replace("no numeric ai enablement score", "")
        .replace("no numeric ai-readiness score", "")
        .replace("ai-readiness", "")
        .replace("ai readiness", "")
        .replace("not ai ready", "")
    )
    for phrase in _FORBIDDEN_CLAIMS:
        assert phrase not in sanitized, f"forbidden claim present: {phrase}"


def test_build_ai_readiness_intelligence_groups_and_excludes_others() -> None:
    report = _succeeded_report()
    api = FindingView(
        finding_id="f-api",
        rule_id=RULE_API_BOUNDARIES,
        title="API boundary signal",
        description="api observed",
        severity="informational",
        category="ai_readiness",
        affected_nodes=("openapi.yaml",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:openapi.yaml",
                kind="other",
                path="openapi.yaml",
                snippet_text="openapi: 3.0.0",
            ),
        ),
    )
    llm = FindingView(
        finding_id="f-llm",
        rule_id=RULE_LLM_SDK,
        title="LLM SDK signal",
        description="llm observed",
        severity="informational",
        category="ai_readiness",
        affected_nodes=("src/llm_client.py",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:src/llm_client.py",
                kind="other",
                path="src/llm_client.py",
                snippet_text="import openai",
            ),
        ),
    )
    security = FindingView(
        finding_id="f-sec",
        rule_id="security.private-key-material",
        title="Private key",
        description="sec",
        severity="high",
        category="security",
    )
    dependency = FindingView(
        finding_id="f-dep",
        rule_id="dependency.unresolved-version",
        title="Unresolved",
        description="dep",
        severity="medium",
        category="dependency",
    )
    architecture = FindingView(
        finding_id="f-arch",
        rule_id="architecture.dependency-cycle",
        title="Cycle",
        description="cycle",
        severity="medium",
        category="architecture",
    )
    cloud = FindingView(
        finding_id="f-cloud",
        rule_id="cloud.containerization",
        title="Container",
        description="cloud",
        severity="informational",
        category="cloud",
    )
    rec = RecommendationView(
        recommendation_id="r-ai",
        title="Review LLM integration signals",
        summary="Review observed LLM declarations",
        rationale="AI readiness",
        priority="medium",
        category="ai_readiness",
        related_finding_ids=("f-llm",),
    )
    other = RecommendationView(
        recommendation_id="r-dep",
        title="Pin versions",
        summary="Pin",
        rationale="Dependency",
        priority="high",
        category="dependency",
        related_finding_ids=("f-dep",),
    )
    intel = build_ai_readiness_intelligence(
        report,
        findings=(api, llm, security, dependency, architecture, cloud),
        recommendations=(rec, other),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-api", "f-llm"}
    assert {item.recommendation_id for item in intel.recommendations} == {"r-ai"}
    assert intel.empty_findings_message is None
    assert intel.signal_groups
    group_ids = {group.group_id for group in intel.signal_groups}
    assert (
        "api_boundaries" in group_ids
        or "ai_integrations" in group_ids
        or "tool_mcp" in group_ids
    )
    for group in intel.signal_groups:
        assert group.signals
        assert group.title
        for signal in group.signals:
            assert "were detected" in signal.label.lower()
            assert "repository-observable" in signal.label.lower()
            assert signal.path is None or not signal.path.startswith("/")
    joined = " ".join(intel.limitations).lower()
    assert "repository evidence only" in joined
    assert "no llm or model execution" in joined
    assert "no model or prompt evaluation" in joined
    assert "no runtime ai" in joined
    assert "no data, retrieval, or vector quality" in joined
    assert "no ai safety certification" in joined
    assert "no organizational readiness" in joined
    assert "no governance maturity" in joined
    assert "no numeric ai enablement score" in joined
    assert "do not prove production use" in joined
    assert "does not establish ai readiness" in joined
    assert intel.confidence_label in {
        "High confidence",
        "Moderate confidence",
        "Limited confidence",
        "Confidence unavailable",
    }
    _assert_no_forbidden(
        " ".join(
            [
                intel.status_summary,
                *(f"{f.label} {f.value} {f.note or ''}" for f in intel.overview_facts),
                *intel.limitations,
                *(s.label for g in intel.signal_groups for s in g.signals),
                *(s.note or "" for g in intel.signal_groups for s in g.signals),
            ]
        )
    )


def test_zero_findings_not_ai_ready() -> None:
    assessment = _assemble(findings=())
    report = AiReadinessReportAdapter().adapt(assessment)
    intel = build_ai_readiness_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.finding_count == 0
    assert intel.findings == ()
    assert intel.empty_findings_message is not None
    lowered = intel.empty_findings_message.lower()
    assert "absence of findings" in lowered
    assert "does not establish ai readiness" in lowered
    _assert_no_forbidden(intel.empty_findings_message)
    overview = " ".join(
        f"{fact.label} {fact.value} {fact.note or ''}" for fact in intel.overview_facts
    ).lower()
    assert "zero findings do not establish ai readiness" in overview


def test_soft_claims_scrubbed_from_status_summary() -> None:
    report = _succeeded_report()
    mutated = report.model_copy(
        update={
            "status_summary": (
                "AI ready and agent ready with RAG ready production ready "
                "posture and strong AI foundation."
            ),
            "overall_posture_summary": (
                "Governed AI safe AI mature AI architecture with no AI issues."
            ),
        }
    )
    intel = build_ai_readiness_intelligence(mutated, findings=(), recommendations=())
    assert intel is not None
    lowered = intel.status_summary.lower()
    assert "ai ready" not in lowered.replace("ai readiness", "")
    assert "agent ready" not in lowered
    assert "rag ready" not in lowered
    assert "production ready" not in lowered
    assert "repository-observable" in lowered or "repository" in lowered
    joined_limits = " ".join(intel.limitations).lower()
    assert "rag readiness" in joined_limits or "repository" in joined_limits
    _assert_no_forbidden(intel.status_summary)


def test_absolute_and_sensitive_paths_omitted() -> None:
    report = _succeeded_report()
    llm = FindingView(
        finding_id="f-llm",
        rule_id=RULE_LLM_SDK,
        title="LLM SDK signal",
        description="llm",
        severity="informational",
        category="ai_readiness",
        affected_nodes=("/Users/secret/prompts/api_key.py",),
        evidence_refs=(
            EvidenceRefView(
                evidence_id="ev:bad",
                kind="other",
                path="/Users/secret/prompts/api_key.py",
                snippet_text="OPENAI_API_KEY",
            ),
        ),
    )
    intel = build_ai_readiness_intelligence(report, findings=(llm,), recommendations=())
    assert intel is not None
    rendered_paths = " ".join(
        filter(
            None,
            [
                *(row.path for group in intel.signal_groups for row in group.signals),
                *(row.path for row in intel.findings),
            ],
        )
    )
    assert "/Users/secret" not in rendered_paths
    assert "prompts" not in rendered_paths.lower()
    assert "api_key" not in rendered_paths.lower()
    assert all(not (row.path or "").startswith("/") for row in intel.findings)
    assert all(not (row.path or "").startswith("file:") for row in intel.findings)


def test_html_ai_readiness_intelligence_section(tmp_path: Path) -> None:
    report = _succeeded_report()
    analysis = AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "sample-app",
            source_url=None,
            default_branch="main",
            files=["openapi.yaml"],
            total_files=1,
        ),
        technologies=[],
        findings=[],
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        ai_readiness_report=report,
    )
    document = build_html_report_view_model(report_input)
    assert document.ai_readiness_intelligence is not None
    html = HtmlReportRenderer().render(document)
    assert 'id="ai-readiness"' in html
    assert 'id="ai-readiness-assessment"' in html
    assert 'href="#ai-readiness"' in html
    assert "AI readiness overview" in html
    assert "Limitations" in html
    assert "Confidence" in html
    assert "Repository evidence only" in html or "repository evidence only" in html.lower()
    lowered = html.lower()
    _assert_no_forbidden(lowered)
    assert "ai ready" not in lowered.replace("ai readiness", "")
    assert "rag ready" not in lowered
    assert "agent ready" not in lowered
    assert "/Users/" not in html
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
    for anchor in (
        "technology-inventory",
        "architecture-intelligence",
        "technical-debt-intelligence",
        "dependency-intelligence",
        "security-intelligence",
        "cloud-readiness",
        "ai-readiness",
    ):
        assert f'id="{anchor}"' in html
        assert f'href="#{anchor}"' in html


def test_build_returns_none_when_report_missing() -> None:
    assert build_ai_readiness_intelligence(None) is None


def test_related_recommendation_subset_included() -> None:
    report = _succeeded_report()
    ai = FindingView(
        finding_id="f-ai",
        rule_id=RULE_LLM_SDK,
        title="LLM",
        description="x",
        severity="informational",
        category="ai_readiness",
    )
    related = RecommendationView(
        recommendation_id="r-related",
        title="Review LLM",
        summary="Review",
        rationale="AI readiness",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-ai",),
    )
    mixed = RecommendationView(
        recommendation_id="r-mixed",
        title="Mixed",
        summary="Mixed",
        rationale="Mixed",
        priority="medium",
        category="maintainability",
        related_finding_ids=("f-ai", "f-other"),
    )
    intel = build_ai_readiness_intelligence(
        report,
        findings=(ai,),
        recommendations=(related, mixed),
    )
    assert intel is not None
    assert {item.recommendation_id for item in intel.recommendations} == {"r-related"}


def test_signal_groups_omit_empty_and_use_observational_labels() -> None:
    report = _succeeded_report()
    intel = build_ai_readiness_intelligence(report, findings=(), recommendations=())
    assert intel is not None
    assert intel.signal_groups
    for group in intel.signal_groups:
        assert group.signals
        assert group.group_id in {
            "api_boundaries",
            "documentation_metadata",
            "data_retrieval",
            "ai_integrations",
            "tool_mcp",
            "workflow_agents",
            "observability_governance",
            "other",
        }
        for signal in group.signals:
            assert signal.label.lower().startswith(
                "repository-observable ai-enablement signals associated with"
            )
            assert "were detected" in signal.label.lower()
            if signal.note:
                assert "do not" in signal.note.lower() or "does not" in signal.note.lower()


def test_rule_id_prefix_variants_included() -> None:
    report = _succeeded_report()
    hyphen = FindingView(
        finding_id="f-hyphen",
        rule_id="ai-readiness.ai-001",
        title="Hyphen prefix",
        description="x",
        severity="informational",
        category="architecture",
    )
    dotted = FindingView(
        finding_id="f-dotted",
        rule_id=RULE_API_BOUNDARIES,
        title="Dotted prefix",
        description="x",
        severity="informational",
        category="maintainability",
    )
    intel = build_ai_readiness_intelligence(
        report,
        findings=(hyphen, dotted),
        recommendations=(),
    )
    assert intel is not None
    assert {item.finding_id for item in intel.findings} == {"f-hyphen", "f-dotted"}
