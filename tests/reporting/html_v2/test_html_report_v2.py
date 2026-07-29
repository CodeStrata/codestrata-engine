"""Tests for HTML Report v2 view-model and renderer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.config import CodestrataSettings
from codestrata.domain.ai_enrichment import (
    AiEnrichmentResult,
    AiProviderMetadata,
    EnrichmentPriorityLevel,
    ExecutiveSummary,
    ModernizationPriority,
    ModernizationRisk,
    ModernizationTheme,
    SuggestedNextStep,
)
from codestrata.domain.findings import Finding as Phase3Finding
from codestrata.domain.findings import FindingCategory, FindingSeverity, RuleEvaluationResult
from codestrata.domain.recommendations import (
    Recommendation as Phase3Recommendation,
)
from codestrata.domain.recommendations import (
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationResult,
)
from codestrata.models import (
    AnalysisResult,
    Finding,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
)
from codestrata.models import (
    FindingCategory as Phase1FindingCategory,
)
from codestrata.reporters.report_paths import create_report_paths
from codestrata.reporting.html_v2 import (
    HtmlReportRenderer,
    build_html_report_view_model,
    default_report_artifacts,
)
from codestrata.reporting.modernization_models import (
    AIExecutionStatus,
    AssessmentMode,
    HighlightedVersionInput,
    ModernizationReportInput,
    ReportArtifactInput,
)
from codestrata.reporting.modernization_serialization import (
    write_modernization_assessment_reports,
)
from codestrata.services.default_pipeline import create_default_analysis_service
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.recommendations import RecommendationEngine
from codestrata.services.rule_engine import RuleEngine


def _analysis(tmp_path: Path, *, name: str = "demo-app") -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name=name,
            path=tmp_path / name,
            files=["README.md", "src/main.java"],
            total_files=2,
        ),
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
                version="17",
            )
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(file_count=2, source_file_count=1, test_file_count=0)
        ),
        findings=[
            Finding(
                rule_id="SEC001",
                title="Critical <script>alert(1)</script>",
                description="Secret exposure AKIAIOSFODNN7EXAMPLE",
                category=Phase1FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
                evidence=[],
            )
        ],
    )


def _phase3_bundle() -> tuple[RuleEvaluationResult, RecommendationResult]:
    finding = Phase3Finding.create(
        rule_id="missing-lockfile",
        title="Missing lockfile",
        description="No package-lock.json",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.DEPENDENCY,
    )
    evaluation = RuleEvaluationResult.from_findings(
        findings=[finding],
        rules_evaluated=["missing-lockfile"],
    )
    recommendation = Phase3Recommendation.create(
        provider_id="builtin:lockfile",
        title="Add a lockfile",
        summary="Commit a lockfile for reproducible installs.",
        rationale="Finding indicates missing lockfile.",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.DEPENDENCY,
        related_finding_ids=[finding.id],
        actions=[
            RecommendationAction(
                order=1,
                title="Generate lockfile",
                description="Run the package manager install command.",
            )
        ],
    )
    recommendations = RecommendationResult.from_recommendations(
        recommendations=[recommendation],
        providers_evaluated=["builtin:lockfile"],
    )
    return evaluation, recommendations


def _enrichment(*, finding_id: str, recommendation_id: str) -> AiEnrichmentResult:
    return AiEnrichmentResult(
        executive_summary=ExecutiveSummary(
            headline="Stabilize dependencies",
            narrative="Prioritize lockfile and CI before larger upgrades.",
        ),
        themes=(
            ModernizationTheme(
                title="Dependency hygiene",
                summary="Lockfile missing.",
                related_finding_ids=(finding_id,),
                related_recommendation_ids=(recommendation_id,),
            ),
        ),
        priorities=(
            ModernizationPriority(
                title="Add lockfile",
                rationale="Reproducible installs",
                priority=EnrichmentPriorityLevel.HIGH,
                related_finding_ids=(finding_id,),
                related_recommendation_ids=(recommendation_id,),
            ),
        ),
        risks=(
            ModernizationRisk(
                title="Install drift",
                summary="Installs may diverge.",
                severity=EnrichmentPriorityLevel.MEDIUM,
                related_finding_ids=(finding_id,),
            ),
        ),
        suggested_next_steps=(
            SuggestedNextStep(
                order=1,
                title="Commit lockfile",
                summary="Generate and commit lockfile.",
                related_recommendation_ids=(recommendation_id,),
            ),
        ),
        provider_metadata=AiProviderMetadata(provider="fake", model_id="m1"),
        limitations=("Fixture enrichment",),
    )


def _report_input(
    tmp_path: Path,
    *,
    with_phase3: bool = True,
    with_ai: bool = False,
    assessment_activation: dict | None = None,
) -> ModernizationReportInput:
    analysis = _analysis(tmp_path)
    evaluation = None
    recommendations = None
    enrichment = None
    if with_phase3:
        evaluation, recommendations = _phase3_bundle()
        if with_ai:
            enrichment = _enrichment(
                finding_id=evaluation.findings[0].id,
                recommendation_id=recommendations.recommendations[0].id,
            )
    activation = assessment_activation
    if activation is None:
        activation = {
            "mode": "default",
            "packs": [
                {
                    "pack_id": "security",
                    "enabled": True,
                    "decision": "enabled",
                    "reason": "Security hygiene is enabled by default",
                    "evidence": [],
                },
                {
                    "pack_id": "dependency",
                    "enabled": True,
                    "decision": "enabled",
                    "reason": "Dependency manifests detected",
                    "evidence": ["inventory:package.json"],
                },
                {
                    "pack_id": "performance",
                    "enabled": False,
                    "decision": "skipped",
                    "reason": "Performance remains opt-in under default activation",
                    "evidence": [],
                },
                {
                    "pack_id": "ai_readiness",
                    "enabled": False,
                    "decision": "skipped",
                    "reason": "No AI/ML frameworks detected",
                    "evidence": [],
                },
            ],
        }
    return ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        ai_status=AIExecutionStatus.NOT_REQUESTED,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        report_title="Engineering Assessment",
        assessment_rule_evaluation=evaluation,
        assessment_recommendation_result=recommendations,
        ai_enrichment=enrichment,
        highlighted_versions=(
            HighlightedVersionInput(label="Java language level", value="17", kind="runtime"),
        ),
        report_artifacts=default_report_artifacts(
            include_ai_enrichment=with_ai,
            include_ai_execution=with_ai,
        ),
        assessment_activation=activation,
    )


def test_view_model_construction_and_ordering(tmp_path: Path) -> None:
    view = build_html_report_view_model(_report_input(tmp_path))
    # Customer universe merges Phase-1 analysis findings with Phase-3 rule findings.
    assert view.summary.total_findings == 2
    assert view.summary.total_recommendations == 1
    severities = {item.severity for item in view.findings}
    assert "high" in severities
    assert "critical" in severities
    assert view.recommendations[0].priority == "high"
    assert view.findings[0].finding_id
    assert view.ai_enrichment is None


def test_findings_and_recommendations_render(tmp_path: Path) -> None:
    view = build_html_report_view_model(_report_input(tmp_path))
    html = HtmlReportRenderer().render(view)
    assert "Findings" in html
    assert "Priority Actions" in html
    assert view.findings[0].finding_id in html
    assert view.recommendations[0].recommendation_id in html
    assert "missing-lockfile" in html
    assert "Add a lockfile" in html


def test_customer_report_experience_hierarchy_and_metadata(tmp_path: Path) -> None:
    from codestrata.reporting.contract.constants import REPORT_HTML_VERSION
    from codestrata.reporting.html_v2 import CustomerReportDocument, build_customer_report_document

    document = build_customer_report_document(_report_input(tmp_path, with_ai=True))
    assert isinstance(document, CustomerReportDocument)
    assert 3 <= len(document.key_takeaways) <= 5
    assert document.outline
    assert document.outline[0].section_id == "executive-summary"
    outline_ids = {entry.section_id for entry in document.outline}
    assert "repository-overview" in outline_ids
    assert "assessment-summary" in outline_ids
    assert "engineering-assessment-conclusion" in outline_ids
    assert "engineering-risks" in outline_ids
    assert "executive-summary" in outline_ids
    assert "modernization-opportunities" in outline_ids
    assert "assessment-scope" not in outline_ids
    assert document.assessment_scope is not None
    assert "Security" in document.assessment_scope.assessed_packs
    assert document.metadata.report_version == REPORT_HTML_VERSION
    assert document.metadata.engine_version
    assert document.metadata.advisor_version == "1.0.0"
    assert document.metadata.repository_name
    assert document.leadership_verdict
    assert document.executive_summary is not None
    assert document.priority_actions

    html = HtmlReportRenderer().render(document)
    assert 'id="cover"' in html
    assert 'id="contents"' in html
    assert "Leadership Verdict" in html
    assert "Key Takeaways" in html
    assert "Executive Summary" in html
    assert "Should I care?" in html
    assert "Engineering Risks" in html
    assert "Modernization Opportunities" in html
    assert "Priority Actions" in html
    assert "Technical Appendix" in html
    assert 'id="assessment-scope"' in html
    assert "Assessment Scope" in html
    assert "Performance Assessment" not in html
    assert "AI Readiness Assessment" not in html
    assert "Rules evaluated" not in html
    assert "directional" not in html.lower()
    assert "Report version" in html
    assert "Engine version" not in html.split('id="cover"', 1)[1].split('id="contents"', 1)[0]
    assert "Advisor version" not in html.split('id="cover"', 1)[1].split('id="contents"', 1)[0]
    assert "@media print" in html
    # Self-contained: no external stylesheets or scripts.
    assert "<link " not in html
    assert "<script" not in html


def test_ai_enrichment_present_and_absent(tmp_path: Path) -> None:
    without = HtmlReportRenderer().render(build_html_report_view_model(_report_input(tmp_path)))
    assert 'id="modernization-advisor"' not in without
    assert 'id="ai-enrichment"' not in without

    view = build_html_report_view_model(_report_input(tmp_path, with_ai=True))
    with_ai = HtmlReportRenderer().render(view)
    assert 'id="modernization-advisor"' in with_ai
    assert "Optional AI Enhancements" in with_ai or "Modernization Advisor" in with_ai
    assert "Modernization Advisor interpretation" in with_ai
    assert "Stabilize dependencies" in with_ai
    assert "fake" in with_ai
    assert "m1" in with_ai
    assert view.ai_enrichment is not None
    assert view.ai_enrichment.advisor_version == "1.0.0"
    assert view.ai_enrichment.prompt_version == "1.1.0"
    assert "Advisor version" in with_ai
    assert "Prompt version" in with_ai
    # Leadership narrative is present; methodology jargon is not.
    assert "Leadership Verdict" in with_ai
    assert "deterministic findings" not in with_ai.lower()
    assert "deterministic recommendations" not in with_ai.lower()


def test_report_json_unchanged_shape(tmp_path: Path) -> None:
    from codestrata.reporting.assessment_json import build_assessment_json_document

    report_input = _report_input(tmp_path)
    document = build_assessment_json_document(report_input)
    assert document["schema_version"] == "1.2"
    assert "assessment" in document
    assert "findings" in document["assessment"]
    # Absent advisor: key present as null; legacy assessment.ai remains.
    assert document["assessment"]["ai_enrichment"] is None
    assert "ai" in document["assessment"]
    assert "assessment_rule_evaluation" not in document["assessment"]


def test_report_json_includes_ai_enrichment_domain_model(tmp_path: Path) -> None:
    from codestrata.reporting.assessment_json import build_assessment_json_document

    report_input = _report_input(tmp_path, with_ai=True)
    document = build_assessment_json_document(report_input)
    enrichment = document["assessment"]["ai_enrichment"]
    assert enrichment is not None
    assert enrichment["executive_summary"]["headline"] == "Stabilize dependencies"
    assert enrichment["provider_metadata"]["provider"] == "fake"
    assert enrichment["provider_metadata"]["model_id"] == "m1"
    assert enrichment["provider_metadata"]["advisor_version"] == "1.0.0"
    assert enrichment["provider_metadata"]["prompt_version"] == "1.1.0"
    # Legacy bridge block remains for older consumers.
    assert document["assessment"]["ai"]["status"] == "not_requested"


def test_html_escaping_and_no_secret_or_absolute_path_leak(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path, with_phase3=False)
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert str(tmp_path) not in html
    assert "/Users/" not in html
    # Secret-like token should be redacted in description when present.
    assert "AKIAIOSFODNN7EXAMPLE" not in html


def test_traceability_ids_visible(tmp_path: Path) -> None:
    view = build_html_report_view_model(_report_input(tmp_path, with_ai=True))
    html = HtmlReportRenderer().render(view)
    assert view.findings[0].finding_id in html
    assert view.recommendations[0].recommendation_id in html
    assert view.ai_enrichment is not None
    assert view.findings[0].finding_id in view.ai_enrichment.referenced_finding_ids or (
        view.findings[0].finding_id in html
    )


def test_stable_deterministic_html_bytes(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    renderer = HtmlReportRenderer()
    first = renderer.render(build_html_report_view_model(report_input))
    second = renderer.render(build_html_report_view_model(report_input))
    assert first == second
    assert first.endswith("\n")


def test_artifact_write_keeps_phase3_artifacts(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    paths = create_report_paths(report_input.analysis_result, tmp_path / "reports")
    # Seed placeholders; report rendering overwrites with the customer universe
    # so findings.json / recommendations.json stay aligned with report.json.
    paths.run_directory.mkdir(parents=True, exist_ok=True)
    (paths.run_directory / "findings.json").write_text('{"ok": true}\n', encoding="utf-8")
    (paths.run_directory / "recommendations.json").write_text('{"ok": true}\n', encoding="utf-8")
    write_modernization_assessment_reports(report_input, paths)
    assert paths.html_report_path.is_file()
    assert paths.json_report_path.is_file()
    findings_text = (paths.run_directory / "findings.json").read_text(encoding="utf-8")
    recommendations_text = (paths.run_directory / "recommendations.json").read_text(
        encoding="utf-8"
    )
    report_json = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    findings_payload = json.loads(findings_text)
    recommendations_payload = json.loads(recommendations_text)
    assert findings_payload["finding_count"] == report_json["assessment"]["summary"][
        "finding_count"
    ]
    assert recommendations_payload["recommendation_count"] == report_json["assessment"][
        "summary"
    ]["recommendation_count"]
    assert findings_payload["finding_count"] == len(report_json["assessment"]["findings"])
    assert recommendations_payload["recommendation_count"] == len(
        report_json["assessment"]["deterministic_recommendations"]
    )


def _sample_repo(root: Path, *, kind: str) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    if kind == "js":
        (root / "package.json").write_text(
            json.dumps(
                {
                    "name": "js-app",
                    "engines": {"node": "20.0.0"},
                    "dependencies": {"express": "4.18.0"},
                }
            ),
            encoding="utf-8",
        )
        (root / "src").mkdir()
        (root / "src" / "index.js").write_text("console.log('ok');\n", encoding="utf-8")
        files = ["package.json", "src/index.js"]
    else:
        (root / "pom.xml").write_text(
            """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo</groupId>
  <artifactId>demo</artifactId>
  <version>1.0.0</version>
  <properties><java.version>17</java.version></properties>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.7.18</version>
  </parent>
</project>
""",
            encoding="utf-8",
        )
        src = root / "src" / "main" / "java" / "demo"
        src.mkdir(parents=True)
        (src / "App.java").write_text("package demo; class App {}", encoding="utf-8")
        files = ["pom.xml", "src/main/java/demo/App.java"]
    return Repository(name=root.name, path=root.resolve(), files=files, total_files=len(files))


@pytest.mark.parametrize("kind", ["java", "js"])
def test_java_and_javascript_samples(tmp_path: Path, kind: str) -> None:
    repository = _sample_repo(tmp_path / f"{kind}-app", kind=kind)
    settings = CodestrataSettings.model_validate(
        {
            "repository": {"path": str(repository.path)},
            "static_analysis": {"enabled": False},
            "ai": {"bedrock": {}},
        }
    )
    analysis = create_default_analysis_service(settings, static_analysis_enabled=False).analyze(
        repository
    )
    pipeline = GraphAssessmentPipeline().run(repository)
    rules = RuleEngine().evaluate_pipeline_result(pipeline)
    recs = RecommendationEngine().evaluate_pipeline_result(
        pipeline_result=pipeline,
        evaluation=rules,
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=rules,
        assessment_recommendation_result=recs,
        highlighted_versions=(),
        report_artifacts=(ReportArtifactInput(label="Findings", relative_path="findings.json"),),
    )
    html = HtmlReportRenderer().render(build_html_report_view_model(report_input))
    assert "Executive Summary" in html
    assert "Leadership Verdict" in html
    assert "Findings" in html
    assert "Priority Actions" in html
    assert repository.name in html
    assert str(repository.path) not in html


def test_executive_dashboard_removes_unsupported_scores(tmp_path: Path) -> None:
    html = HtmlReportRenderer().render(build_html_report_view_model(_report_input(tmp_path)))
    assert "Overall Health" not in html
    assert "Modernization Readiness" not in html
    assert "Risk Level" not in html
    assert "Cloud Ready" not in html
    assert "health_score" not in html
    assert "100 - critical" not in html
    assert "Highest Finding Severity" in html
    assert "Cloud Enablement Signals" in html
    assert "CI/CD" in html
    assert "Overall Health" not in html
    # Default fixture has no cloud facts → Unknown (not a fabricated N of 7).
    view = build_html_report_view_model(_report_input(tmp_path))
    assert view.summary.metrics is not None
    assert view.summary.metrics.cloud_signals_primary == "Unknown"


def test_highest_finding_severity_none_detected_without_findings(tmp_path: Path) -> None:
    analysis = _analysis(tmp_path)
    analysis = analysis.model_copy(update={"findings": []})
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        ai_status=AIExecutionStatus.NOT_REQUESTED,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=[],
            rules_evaluated=[],
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=[],
            providers_evaluated=[],
        ),
    )
    view = build_html_report_view_model(report_input)
    html = HtmlReportRenderer().render(view)
    assert view.summary.highest_finding_severity == "None Detected"
    assert "None Detected" in html
    assert "Overall Health" not in html
    assert "Risk Level" not in html
    assert "Modernization Readiness" not in html


def test_dashboard_unknown_and_zero_test_files(tmp_path: Path) -> None:
    from codestrata.models import RepositoryFacts, StructureFacts
    from codestrata.models.cicd import CicdFacts
    from codestrata.models.normalized_facts import CloudReadinessFacts

    analysis = _analysis(tmp_path).model_copy(
        update={
            "facts": RepositoryFacts(
                structure=StructureFacts(file_count=2, test_file_count=0, has_tests=False),
                cicd=CicdFacts(has_ci=False, pipeline_count=0),
                cloud=CloudReadinessFacts(
                    has_docker=False,
                    has_kubernetes=False,
                    has_helm=False,
                    has_terraform=False,
                    has_cloudformation=False,
                    has_serverless=False,
                    has_docker_compose=False,
                ),
            ),
            "findings": [],
        }
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=RuleEvaluationResult.from_findings(
            findings=[],
            rules_evaluated=[],
        ),
        assessment_recommendation_result=RecommendationResult.from_recommendations(
            recommendations=[],
            providers_evaluated=[],
        ),
    )
    view = build_html_report_view_model(report_input)
    assert view.summary.metrics is not None
    assert view.summary.metrics.test_files_label == "0"
    assert view.summary.metrics.cicd_label == "Not detected"
    assert view.summary.metrics.cloud_signals_primary == "0 of 7"
    assert view.summary.metrics.cloud_signals_status == "Not detected"
    html = HtmlReportRenderer().render(view)
    assert "CI/CD" in html
    assert "Not detected" in html
    assert "0 of 7" in html
    # Test-file count remains in metrics/key takeaways, not as a cover KPI card.
    assert view.summary.metrics.test_files_label == "0"
    assert "tests: 0" in " ".join(view.key_takeaways).lower() or any(
        "0" in item for item in view.key_takeaways
    )

    bare = analysis.model_copy(update={"facts": RepositoryFacts()})
    bare_input = report_input.model_copy(update={"analysis_result": bare})
    bare_view = build_html_report_view_model(bare_input)
    assert bare_view.summary.metrics is not None
    assert bare_view.summary.metrics.test_files_label == "Unknown"
    assert bare_view.summary.metrics.cicd_label == "Unknown"
    assert bare_view.summary.metrics.cloud_signals_primary == "Unknown"
    bare_html = HtmlReportRenderer().render(bare_view)
    assert "Unknown" in bare_html
    assert "—" not in bare_html.split("CI/CD", 1)[1][:120]


def test_highest_severity_and_cloud_established(tmp_path: Path) -> None:
    from codestrata.models import RepositoryFacts
    from codestrata.models.normalized_facts import CloudReadinessFacts

    evaluation, recommendations = _phase3_bundle()
    analysis = _analysis(tmp_path).model_copy(
        update={
            "facts": RepositoryFacts(
                cloud=CloudReadinessFacts(has_docker=True, has_kubernetes=True),
            )
        }
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        assessment_rule_evaluation=evaluation,
        assessment_recommendation_result=recommendations,
    )
    view = build_html_report_view_model(report_input)
    assert view.summary.highest_finding_severity == "Critical"
    assert view.summary.metrics is not None
    assert view.summary.metrics.cloud_signals_primary == "2 of 7"
    assert view.summary.metrics.cloud_signals_status == "Established"
    html = HtmlReportRenderer().render(view)
    assert "2 of 7" in html
    assert "Established" in html
    assert "Highest Finding Severity" in html
    assert "Critical" in html
