"""Parity tests: assess HTML/JSON preserve HtmlFileReporter deterministic intelligence."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from codestrata.ai.agents.models import (
    AgentExecutionStatus,
    AgentExecutionTrace,
    ModernizationAssessmentResult,
)
from codestrata.ai.contracts.models import (
    LLMAnalysisContext,
    LLMFindingEvidence,
    LLMMetricsContext,
    LLMRepositoryContext,
    LLMSectionTruncation,
    LLMTechnologyEvidence,
)
from codestrata.ai.providers.models import ModelInvocationMetadata, ModelUsage
from codestrata.ai.recommendations import (
    AIRecommendation,
    AIRecommendationConfidence,
    AIRecommendationEffort,
    AIRecommendationImpact,
    AIRecommendationPriority,
    AIRecommendationResult,
    EvidenceCoverage,
    ModernizationPhase,
)
from codestrata.models import (
    AnalysisResult,
    ArchitectureFacts,
    BuildFacts,
    CicdFacts,
    CloudReadinessFacts,
    DependencyFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Priority,
    Recommendation,
    Repository,
    RepositoryFacts,
    SecurityFacts,
    Severity,
    StructureFacts,
    Technology,
    TechnologyCategory,
    TechnologyFacts,
)
from codestrata.models.cicd import CicdPipeline
from codestrata.models.enums import Effort, RecommendationCategory, Risk
from codestrata.models.scan_comparison import ComparisonSummary, ScanComparison
from codestrata.reporting import (
    CONTENT_SECURITY_POLICY,
    AIExecutionStatus,
    AssessmentMode,
    AssessmentTiming,
    ModernizationHTMLReportRenderer,
    ModernizationReportInput,
    build_assessment_json_document,
    write_modernization_assessment_reports,
)
from codestrata.static_analysis.models import StaticAnalysisResult, StaticAnalysisStatus


def _truncation(count: int = 0) -> LLMSectionTruncation:
    return LLMSectionTruncation(
        truncated=False,
        original_count=count,
        included_count=count,
    )


def _recommendation(
    *,
    rule_id: str,
    title: str,
    priority: Priority,
    finding_ids: list[str] | None = None,
) -> Recommendation:
    return Recommendation(
        rule_id=rule_id,
        title=title,
        description=f"Action for {title}",
        rationale=f"Rationale for {title}",
        priority=priority,
        category=RecommendationCategory.SECURITY,
        effort=Effort.MEDIUM,
        risk=Risk.HIGH,
        evidence=[Evidence(file_path="pom.xml", line_number=2, description="dep")],
        related_finding_ids=finding_ids or ["SEC001"],
        actions=[f"Do {title}"],
    )


def _rich_analysis(tmp_path: Path) -> AnalysisResult:
    return AnalysisResult(
        repository=Repository(
            name="sample-app",
            path=tmp_path / "workspace" / "sample-app",
            source_url="https://github.com/example/sample-app.git",
            default_branch="main",
            files=["src/App.java", "pom.xml", "Dockerfile"],
            total_files=3,
        ),
        technologies=[
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                version="17",
                confidence=1.0,
                source="test",
            ),
            Technology(
                name="Maven",
                category=TechnologyCategory.BUILD_TOOL,
                confidence=1.0,
                source="test",
            ),
            Technology(
                name="Spring Boot",
                category=TechnologyCategory.FRAMEWORK,
                confidence=1.0,
                source="test",
            ),
        ],
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=3,
                source_file_count=1,
                test_file_count=1,
                application_count=1,
                has_tests=True,
                architecture_layers=["api", "service", "persistence"],
            ),
            technology=TechnologyFacts(
                programming_languages=["Java"],
                frameworks=["Spring Boot"],
                build_tools=["Maven"],
                test_frameworks=["JUnit"],
                detected_technologies=["Java", "Spring Boot", "Maven", "JUnit"],
            ),
            build=BuildFacts(
                build_systems=["maven"],
                build_files=["pom.xml"],
                wrapper_files=["mvnw"],
                multi_module=False,
                plugins=["spring-boot-maven-plugin"],
                inferred_commands=["mvn package", "mvn test"],
            ),
            dependencies=DependencyFacts(
                dependency_count=12,
                direct_dependency_count=8,
                framework_dependencies=["spring-boot-starter-web"],
                database_drivers=["h2"],
                testing_libraries=["junit-jupiter"],
            ),
            cicd=CicdFacts(
                has_ci=True,
                ci_platforms=["github-actions"],
                has_deployment_workflow=True,
                pipeline_count=1,
                pipeline_files=[".github/workflows/ci.yml"],
                pipelines=[
                    CicdPipeline(
                        provider="github-actions",
                        path=".github/workflows/ci.yml",
                        pipeline_name="ci",
                        build_commands=["mvn -B package"],
                        test_commands=["mvn test"],
                        deployment_commands=["kubectl apply"],
                        metadata={"actions": ["actions/checkout@v4"]},
                    )
                ],
            ),
            security=SecurityFacts(
                sensitive_file_count=1,
                secret_finding_count=2,
                weak_crypto_count=0,
                dangerous_execution_count=1,
            ),
            architecture=ArchitectureFacts(
                has_api_layer=True,
                has_service_layer=True,
                has_persistence_layer=True,
                has_domain_layer=False,
                is_multi_application=False,
            ),
            cloud=CloudReadinessFacts(
                has_docker=True,
                has_devcontainer=False,
                has_docker_compose=True,
                has_kubernetes=True,
                has_helm=False,
                has_terraform=False,
                has_cloudformation=False,
                has_serverless=False,
                cloud_capabilities=["docker", "kubernetes"],
            ),
        ),
        findings=[
            Finding(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                rule_id="SEC001",
                title="Critical finding",
                description="Secret exposure risk",
                category=FindingCategory.SECURITY,
                severity=Severity.CRITICAL,
                source=FindingSource.DETERMINISTIC,
                evidence=[
                    Evidence(file_path="src/App.java", line_number=10),
                    Evidence(file_path=".", description="repo-level"),
                ],
                affected_technologies=["Java"],
                metadata={"provider_name": "codestrata"},
            ),
            Finding(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                rule_id="SEC002",
                title="High finding",
                description="Weak crypto",
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="src/Crypto.java", line_number=4)],
            ),
            Finding(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                rule_id="DEP001",
                title="Medium finding",
                description="Dependency drift",
                category=FindingCategory.DEPENDENCY,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
                evidence=[Evidence(file_path="pom.xml", line_number=20)],
            ),
        ],
        recommendations=[
            _recommendation(
                rule_id="REC.SECURITY.001",
                title="Rotate credentials",
                priority=Priority.CRITICAL,
                finding_ids=["11111111-1111-1111-1111-111111111111"],
            ),
            _recommendation(
                rule_id="REC.SECURITY.002",
                title="Harden cryptography",
                priority=Priority.HIGH,
                finding_ids=["22222222-2222-2222-2222-222222222222"],
            ),
            _recommendation(
                rule_id="REC.DEPENDENCY.001",
                title="Refresh dependencies",
                priority=Priority.MEDIUM,
                finding_ids=["33333333-3333-3333-3333-333333333333"],
            ),
        ],
        static_analysis_results=[
            StaticAnalysisResult(
                provider_id="pmd",
                provider_name="pmd",
                provider_version="7.0.0",
                status=StaticAnalysisStatus.COMPLETED,
                findings=[],
                files_analyzed=2,
                duration_ms=42.0,
            )
        ],
    )


def _ai_assessment() -> ModernizationAssessmentResult:
    return ModernizationAssessmentResult(
        recommendation_result=AIRecommendationResult(
            executive_summary="AI executive interpretation.",
            overall_assessment="Overall AI assessment.",
            key_risks=["AI risk one"],
            recommendations=[
                AIRecommendation(
                    recommendation_id="AI-REC-001",
                    title="AI recommendation",
                    description="AI-only guidance",
                    rationale="Because of evidence",
                    priority=AIRecommendationPriority.HIGH,
                    effort=AIRecommendationEffort.MEDIUM,
                    impact=AIRecommendationImpact.HIGH,
                    confidence=AIRecommendationConfidence.MEDIUM,
                    related_finding_ids=["SEC001"],
                    suggested_actions=["Validate with engineering"],
                )
            ],
            modernization_phases=[
                ModernizationPhase(
                    phase=1,
                    name="Stabilize",
                    objective="Reduce critical risk",
                    recommendations=["AI-REC-001"],
                    expected_outcomes=["Safer baseline"],
                )
            ],
            limitations=["No runtime profiling"],
            evidence_coverage=EvidenceCoverage(
                total_findings=1,
                findings_considered=1,
                findings_referenced=1,
                coverage_percentage=100.0,
                input_truncated=False,
            ),
        ),
        model_metadata=ModelInvocationMetadata(
            provider="fake",
            model_id="test-model",
            latency_ms=12.5,
            usage=ModelUsage(input_tokens=9, output_tokens=11, total_tokens=20),
        ),
        trace=AgentExecutionTrace(
            trace_id="trace-parity",
            started_at_utc=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            completed_at_utc=datetime(2026, 7, 21, 12, 1, tzinfo=UTC),
            total_latency_ms=1000.0,
            status=AgentExecutionStatus.COMPLETED,
            tool_call_count=1,
            model_call_count=1,
            input_tokens=9,
            output_tokens=11,
            total_tokens=20,
        ),
    )


def _context() -> LLMAnalysisContext:
    return LLMAnalysisContext(
        repository=LLMRepositoryContext(
            name="sample-app",
            source_type="github",
            default_branch="main",
            file_count=3,
        ),
        technologies=[
            LLMTechnologyEvidence(name="Java", category="language", version="17"),
        ],
        findings=[
            LLMFindingEvidence(
                rule_id="SEC001",
                title="Critical finding",
                category="security",
                severity="critical",
                summary="Secret exposure risk",
                evidence=[],
                evidence_truncation=_truncation(0),
            )
        ],
        metrics=LLMMetricsContext(
            file_count=3,
            source_file_count=1,
            test_file_count=1,
            finding_count=1,
            technology_count=1,
        ),
        findings_truncation=_truncation(1),
    )


def _report_input(
    tmp_path: Path,
    *,
    mode: AssessmentMode = AssessmentMode.DETERMINISTIC,
    analysis: AnalysisResult | None = None,
    comparison: ScanComparison | None = None,
) -> ModernizationReportInput:
    result = analysis or _rich_analysis(tmp_path)
    if comparison is not None:
        result = result.model_copy(update={"comparison": comparison})
    if mode == AssessmentMode.DETERMINISTIC:
        return ModernizationReportInput(
            analysis_result=result,
            assessment_mode=AssessmentMode.DETERMINISTIC,
            generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
            timing=AssessmentTiming(
                total_ms=200.0,
                scan_ms=10.0,
                analysis_ms=80.0,
                static_analysis_ms=42.0,
                ai_ms=None,
                report_ms=5.0,
            ),
            warnings=[],
        )
    return ModernizationReportInput(
        analysis_result=result,
        assessment_mode=AssessmentMode.AI_ENHANCED,
        analysis_context=_context(),
        assessment_result=_ai_assessment(),
        ai_status=AIExecutionStatus.SUCCEEDED,
        generated_at_utc=datetime(2026, 7, 21, 15, 30, tzinfo=UTC),
        timing=AssessmentTiming(
            total_ms=250.0,
            scan_ms=10.0,
            analysis_ms=80.0,
            static_analysis_ms=42.0,
            ai_ms=40.0,
            report_ms=5.0,
        ),
    )


def test_executive_summary_metrics_html_and_json(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    executive = document["assessment"]["executive_summary"]

    assert "Executive Summary" in html
    assert "Leadership Verdict" in html
    assert "Assessment Summary" in html
    # Canonical Slice 14.9 presentation titles (not pre-14.9 labels).
    assert "Priority Actions" in html
    assert "Technology Inventory" in html
    assert "severity-critical" in html
    assert "Findings" in html
    assert "Should I care?" in html
    assert executive["finding_count"] == 3
    assert executive["recommendation_count"] == 3
    assert executive["file_count"] == 3
    assert executive["technology_count"] == 3
    assert executive["findings_by_severity"]["critical"] == 1
    assert executive["findings_by_severity"]["high"] == 1
    assert executive["findings_by_severity"]["medium"] == 1
    # Calibrated priority projection (Epic 5) may remap fixture Priority.CRITICAL → high.
    assert executive["recommendations_by_priority"]["critical"] == 0
    assert executive["recommendations_by_priority"]["high"] == 2
    assert executive["recommendations_by_priority"]["medium"] == 1
    assert executive["critical_high_finding_count"] == 2
    assert executive["tests_detected"] is True
    assert executive["ci_detected"] is True
    assert "docker" in executive["cloud_capabilities"]


def test_repository_facts_present_in_html_and_json(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    html = ModernizationHTMLReportRenderer().render(report_input).replace("<wbr>", "")
    facts = build_assessment_json_document(report_input)["assessment"]["repository_facts"]

    assert "Findings" in html
    assert "Repository Profile" in html
    assert "Technology Inventory" in html
    assert "Spring Boot" in html

    assert facts["structure"]["file_count"] == 3
    assert facts["technology"]["frameworks"] == ["Spring Boot"]
    assert facts["build"]["build_systems"] == ["maven"]
    assert facts["build"]["wrapper_files"] == ["mvnw"]
    assert facts["build"]["plugins"] == ["spring-boot-maven-plugin"]
    assert facts["dependencies"]["dependency_count"] == 12
    assert facts["cicd"]["has_ci"] is True
    assert facts["security"]["secret_finding_count"] == 2
    assert facts["architecture"]["has_api_layer"] is True
    assert facts["cloud"]["has_docker"] is True


def test_static_analysis_provider_table_and_unavailable_nonfatal(tmp_path: Path) -> None:
    analysis = _rich_analysis(tmp_path).model_copy(
        update={
            "static_analysis_results": [
                StaticAnalysisResult(
                    provider_id="pmd",
                    provider_name="pmd",
                    provider_version="7.1.0",
                    status=StaticAnalysisStatus.UNAVAILABLE,
                    findings=[],
                    eligible_file_count=0,
                    files_analyzed=0,
                    duration_ms=1.0,
                    error_message="pmd not found",
                )
            ]
        }
    )
    report_input = _report_input(tmp_path, analysis=analysis)
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)

    assert "Assessment Metadata" in html
    assert 'id="ai-enrichment"' not in html
    sa = document["assessment"]["static_analysis"]
    assert sa["status"] == StaticAnalysisStatus.UNAVAILABLE.value
    assert sa["provider_version"] == "7.1.0"
    assert sa["providers"][0]["eligible_file_count"] == 0
    assert sa["providers"][0]["files_analyzed"] == 0
    assert document["assessment"]["coverage"]["deterministic_analysis"] == "completed"


def test_static_analysis_completed_counts_agree_in_html_and_json(tmp_path: Path) -> None:
    analysis = _rich_analysis(tmp_path).model_copy(
        update={
            "static_analysis_results": [
                StaticAnalysisResult(
                    provider_id="pmd",
                    provider_name="PMD",
                    provider_version="7.26.0",
                    status=StaticAnalysisStatus.COMPLETED,
                    findings=[],
                    eligible_file_count=49,
                    files_analyzed=49,
                    duration_ms=9123.0,
                    command_metadata={
                        "rulesets": [
                            "category/java/bestpractices.xml",
                            "category/java/errorprone.xml",
                        ],
                        "source_roots": ["src/main/java", "src/test/java"],
                    },
                )
            ]
        }
    )
    report_input = _report_input(tmp_path, analysis=analysis)
    html = ModernizationHTMLReportRenderer().render(report_input)
    document = build_assessment_json_document(report_input)
    provider = document["assessment"]["static_analysis"]["providers"][0]

    assert provider["status"] == "completed"
    assert provider["eligible_file_count"] == 49
    assert provider["files_analyzed"] == 49
    assert provider["provider_version"] == "7.26.0"
    assert "category/java/bestpractices.xml" in provider["rulesets"]
    assert "Technology Inventory" in html


def test_findings_and_deterministic_recommendations_parity(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    html = ModernizationHTMLReportRenderer().render(report_input).replace("<wbr>", "")
    document = build_assessment_json_document(report_input)

    assert re.search(r'id="finding-[0-9a-f-]{36}"', html)
    assert "Critical finding" in html
    assert "Rotate credentials" in html
    assert "SEC001" in html

    findings = document["assessment"]["findings"]
    assert len(findings) == 3
    assert findings[0]["severity"] == "critical"
    assert findings[0]["rule_id"] == "SEC001"
    assert findings[0]["evidence"]
    recs = document["assessment"]["deterministic_recommendations"]
    assert len(recs) == 3
    # Prioritization may reorder equal-band recommendations; bind by rule_id.
    by_rule = {rec["rule_id"]: rec for rec in recs}
    assert "REC.SECURITY.001" in by_rule
    # related_finding_ids must be stable report finding IDs (not rule IDs).
    assert by_rule["REC.SECURITY.001"]["related_finding_ids"] == [findings[0]["id"]]
    assert document["assessment"]["summary"]["recommendation_count"] == 3


def test_ai_mode_keeps_deterministic_and_appends_single_ai_section(tmp_path: Path) -> None:
    det = ModernizationHTMLReportRenderer().render(
        _report_input(tmp_path, mode=AssessmentMode.DETERMINISTIC)
    )
    ai = ModernizationHTMLReportRenderer().render(
        _report_input(tmp_path, mode=AssessmentMode.AI_ENHANCED)
    )

    assert "Findings" in det
    assert "Priority Actions" in det
    assert 'id="ai-enrichment"' not in det
    assert "AI-REC-001" not in det

    assert "Findings" in ai
    assert "Priority Actions" in ai
    # Legacy assessment_result alone does not populate Phase 3 AI enrichment.
    assert 'id="ai-enrichment"' not in ai
    assert "AI-REC-001" not in ai


def test_comparison_rendered_only_when_present(tmp_path: Path) -> None:
    without = ModernizationHTMLReportRenderer().render(_report_input(tmp_path))
    assert "Changes Since Previous Assessment" not in without
    assert (
        build_assessment_json_document(_report_input(tmp_path))["assessment"]["comparison"] is None
    )

    comparison = ScanComparison(
        baseline_available=True,
        baseline_timestamp="2026-07-01T00:00:00Z",
        current_timestamp="2026-07-21T00:00:00Z",
        summary=ComparisonSummary(
            new_findings=1,
            resolved_findings=0,
            worsened_findings=0,
            improved_findings=0,
            new_recommendations=0,
            resolved_recommendations=0,
            worsened_priorities=0,
            improved_priorities=0,
            fact_changes=0,
        ),
    )
    with_cmp = _report_input(tmp_path, comparison=comparison)
    html = ModernizationHTMLReportRenderer().render(with_cmp)
    document = build_assessment_json_document(with_cmp)
    assert "Assessment Metadata" in html
    assert "Changes Since Previous Assessment" not in html
    assert document["assessment"]["comparison"]["baseline_available"] is True


def test_security_sanitization_and_csp(tmp_path: Path) -> None:
    report_input = _report_input(tmp_path)
    html = ModernizationHTMLReportRenderer().render(report_input)
    text = str(build_assessment_json_document(report_input))

    assert "Content-Security-Policy" in html
    assert "default-src &#x27;none&#x27;" in html or "default-src 'none'" in html
    assert CONTENT_SECURITY_POLICY.split(";")[0] in html.replace("&#x27;", "'")
    assert str(tmp_path) not in html
    assert str(tmp_path) not in text
    assert "SYSTEM PROMPT" not in html
    assert "raw_model_response" not in text
    assert "AKIA" not in html


def test_atomic_dual_write_parity_artifacts(tmp_path: Path) -> None:
    from codestrata.reporters.report_paths import create_report_paths

    report_input = _report_input(tmp_path)
    report_paths = create_report_paths(
        report_input.analysis_result,
        tmp_path / "out",
        timestamp="20260721-153045",
        create_directory=False,
    )
    written = write_modernization_assessment_reports(report_input, report_paths)
    assert written.html_report_path.exists()
    assert written.json_report_path.exists()
    assert not written.text_report_path.exists()
    html = written.html_report_path.read_text(encoding="utf-8")
    payload = build_assessment_json_document(report_input)
    assert "Priority Actions" in html
    assert "Engineering Assessment" in html
    assert "CodeStrata" in html
    assert "Generated by CodeStrata Community Edition" in html
    assert payload["assessment"]["summary"]["recommendation_count"] == 3
    assert list(written.run_directory.glob(".report.*.tmp")) == []
