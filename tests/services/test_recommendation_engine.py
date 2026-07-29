"""Tests for the deterministic modernization recommendation engine."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    AnalyzerResult,
    ArchitectureFacts,
    CicdFacts,
    CloudReadinessFacts,
    DependencyFacts,
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
)
from codestrata.models.enums import Effort, RecommendationCategory, Risk
from codestrata.reporters import ConsoleReporter, JsonFileReporter, TextFileReporter
from codestrata.services.analysis_service import AnalysisService
from codestrata.services.recommendation_engine import ModernizationRecommendationEngine


def _engine() -> ModernizationRecommendationEngine:
    return ModernizationRecommendationEngine()


def _rule_ids(recommendations: list[Recommendation]) -> list[str]:
    return [recommendation.rule_id for recommendation in recommendations]


def test_no_tests_recommendation() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(has_tests=False, test_file_count=0),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.TESTING.001"]
    recommendation = recommendations[0]
    assert recommendation.priority == Priority.HIGH
    assert recommendation.effort == Effort.MEDIUM
    assert recommendation.risk == Risk.HIGH
    assert recommendation.category == RecommendationCategory.TESTING
    assert recommendation.evidence


def test_low_test_ratio_recommendation() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(
            has_tests=True,
            source_file_count=20,
            test_file_count=1,
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.TESTING.002"]
    assert recommendations[0].priority == Priority.MEDIUM


def test_no_recommendation_when_test_ratio_is_adequate() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(
            has_tests=True,
            source_file_count=10,
            test_file_count=2,
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert "REC.TESTING.002" not in _rule_ids(recommendations)


def test_secret_recommendation() -> None:
    finding = Finding(
        rule_id="SEC003",
        title="Secret detected",
        description="Secret found",
        category=FindingCategory.SECURITY,
        severity=Severity.CRITICAL,
        source=FindingSource.STATIC_ANALYSIS,
    )
    facts = RepositoryFacts(
        security=SecurityFacts(secret_finding_count=2),
    )

    recommendations = _engine().generate(facts, [finding], [])

    assert _rule_ids(recommendations) == ["REC.SECURITY.001"]
    recommendation = recommendations[0]
    assert recommendation.priority == Priority.CRITICAL
    assert recommendation.effort == Effort.SMALL
    assert recommendation.risk == Risk.HIGH
    assert str(finding.id) in recommendation.related_finding_ids


def test_weak_crypto_recommendation() -> None:
    facts = RepositoryFacts(security=SecurityFacts(weak_crypto_count=1))

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.SECURITY.002"]
    assert recommendations[0].priority == Priority.HIGH
    assert recommendations[0].effort == Effort.MEDIUM
    assert recommendations[0].risk == Risk.HIGH


def test_dangerous_execution_recommendation() -> None:
    facts = RepositoryFacts(
        security=SecurityFacts(dangerous_execution_count=3),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.SECURITY.003"]
    assert recommendations[0].priority == Priority.HIGH


def test_no_cloud_deployment_baseline() -> None:
    facts = RepositoryFacts(
        cloud=CloudReadinessFacts(
            has_docker=False,
            has_kubernetes=False,
            has_terraform=False,
            has_cloudformation=False,
            has_serverless=False,
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.CLOUD.001"]
    assert recommendations[0].priority == Priority.MEDIUM
    assert "Kubernetes" not in recommendations[0].description or (
        "does not require" in recommendations[0].description.lower()
    )


def test_docker_without_deployment_workflow() -> None:
    facts = RepositoryFacts(
        cloud=CloudReadinessFacts(has_docker=True),
        cicd=CicdFacts(has_deployment_workflow=False),
    )

    recommendations = _engine().generate(facts, [], [])

    assert "REC.CLOUD.002" in _rule_ids(recommendations)


def test_kubernetes_without_helm() -> None:
    facts = RepositoryFacts(
        cloud=CloudReadinessFacts(
            has_docker=True,
            has_kubernetes=True,
            has_helm=False,
            has_terraform=False,
            has_cloudformation=False,
            has_serverless=False,
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert "REC.CLOUD.003" in _rule_ids(recommendations)
    assert (
        recommendations[_rule_ids(recommendations).index("REC.CLOUD.003")].priority == Priority.LOW
    )
    assert (
        "mandatory"
        in recommendations[_rule_ids(recommendations).index("REC.CLOUD.003")].description.lower()
        or "optional"
        in recommendations[_rule_ids(recommendations).index("REC.CLOUD.003")].description.lower()
    )


def test_no_ci_recommendation() -> None:
    facts = RepositoryFacts(cicd=CicdFacts(has_ci=False))

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.CICD.001"]
    assert recommendations[0].priority == Priority.HIGH


def test_ci_without_deployment_workflow() -> None:
    facts = RepositoryFacts(
        cicd=CicdFacts(
            has_ci=True,
            has_deployment_workflow=False,
            ci_platforms=["github-actions"],
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.CICD.002"]
    assert recommendations[0].priority == Priority.MEDIUM


def test_architecture_separation_recommendation() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(source_file_count=12),
        architecture=ArchitectureFacts(
            has_api_layer=False,
            has_service_layer=False,
            has_persistence_layer=False,
        ),
    )

    recommendations = _engine().generate(facts, [], [])

    assert "REC.ARCHITECTURE.001" in _rule_ids(recommendations)
    recommendation = recommendations[_rule_ids(recommendations).index("REC.ARCHITECTURE.001")]
    assert recommendation.priority == Priority.MEDIUM
    assert recommendation.effort == Effort.LARGE


def test_multi_application_recommendation() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(application_count=3),
        architecture=ArchitectureFacts(is_multi_application=True),
    )

    recommendations = _engine().generate(facts, [], [])

    assert _rule_ids(recommendations) == ["REC.ARCHITECTURE.002"]
    assert recommendations[0].priority == Priority.LOW
    assert "microservice" not in recommendations[0].description.lower() or (
        "does not require" in recommendations[0].description.lower()
    )


def test_outdated_dependency_effort_thresholds() -> None:
    engine = _engine()

    small = engine.generate(
        RepositoryFacts(
            dependencies=DependencyFacts(
                outdated_dependencies=["a"],
            )
        ),
        [],
        [],
    )
    assert small[0].effort == Effort.SMALL

    medium = engine.generate(
        RepositoryFacts(
            dependencies=DependencyFacts(
                outdated_dependencies=[f"dep-{index}" for index in range(6)],
            )
        ),
        [],
        [],
    )
    assert medium[0].effort == Effort.MEDIUM

    large = engine.generate(
        RepositoryFacts(
            dependencies=DependencyFacts(
                outdated_dependencies=[f"dep-{index}" for index in range(21)],
            )
        ),
        [],
        [],
    )
    assert large[0].effort == Effort.LARGE
    assert large[0].priority == Priority.HIGH


def test_no_recommendation_when_triggering_fact_absent() -> None:
    recommendations = _engine().generate(RepositoryFacts(), [], [])

    assert recommendations == []


def test_no_duplicate_rule_ids() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(has_tests=False, test_file_count=0),
        security=SecurityFacts(
            secret_finding_count=1,
            weak_crypto_count=1,
            dangerous_execution_count=1,
        ),
        cicd=CicdFacts(has_ci=False),
    )

    recommendations = _engine().generate(facts, [], [])
    rule_ids = _rule_ids(recommendations)

    assert len(rule_ids) == len(set(rule_ids))


def test_deterministic_ordering() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(has_tests=False, test_file_count=0),
        security=SecurityFacts(secret_finding_count=1, weak_crypto_count=1),
        cicd=CicdFacts(has_ci=False),
        architecture=ArchitectureFacts(is_multi_application=True),
    )

    first = _rule_ids(_engine().generate(facts, [], []))
    second = _rule_ids(_engine().generate(facts, [], []))

    assert first == second
    assert first[0] == "REC.SECURITY.001"

    priorities = [recommendation.priority for recommendation in _engine().generate(facts, [], [])]
    assert priorities == sorted(
        priorities,
        key=lambda priority: {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }[priority],
    )


def test_every_recommendation_has_evidence() -> None:
    facts = RepositoryFacts(
        structure=StructureFacts(
            has_tests=False,
            test_file_count=0,
            source_file_count=5,
        ),
        security=SecurityFacts(secret_finding_count=1),
        cloud=CloudReadinessFacts(
            has_docker=False,
            has_kubernetes=False,
            has_terraform=False,
            has_cloudformation=False,
            has_serverless=False,
        ),
        cicd=CicdFacts(has_ci=False),
        architecture=ArchitectureFacts(
            has_api_layer=False,
            has_service_layer=False,
            has_persistence_layer=False,
            is_multi_application=True,
        ),
        dependencies=DependencyFacts(outdated_dependencies=["left-pad"]),
    )

    recommendations = _engine().generate(facts, [], [])

    assert recommendations
    assert all(recommendation.evidence for recommendation in recommendations)


def test_analysis_service_integration() -> None:
    class StubTechnologyDetector:
        def detect(self, repository: Repository) -> list[Technology]:
            del repository
            return [
                Technology(
                    name="Java",
                    category=TechnologyCategory.LANGUAGE,
                    confidence=1.0,
                    source="test",
                )
            ]

    class StubAnalyzer:
        def analyze(
            self,
            repository: Repository,
            technologies: Sequence[Technology],
            facts: RepositoryFacts | None = None,
        ) -> AnalyzerResult:
            del repository
            del technologies
            del facts
            return AnalyzerResult(
                findings=[],
                facts=RepositoryFacts(
                    structure=StructureFacts(has_tests=False, test_file_count=0),
                    security=SecurityFacts(secret_finding_count=1),
                ),
            )

    service = AnalysisService(
        technology_detector=StubTechnologyDetector(),
        analyzer=StubAnalyzer(),
        analyzer_version="0.3.0",
    )

    result = service.analyze(
        Repository(
            name="sample",
            path=Path("/tmp/sample"),
            files=["src/App.java"],
        )
    )

    assert result.recommendations
    assert "REC.SECURITY.001" in _rule_ids(result.recommendations)
    assert "REC.TESTING.001" in _rule_ids(result.recommendations)


def test_json_report_includes_recommendations(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path,
            files=["app.py"],
        ),
        recommendations=_engine().generate(
            RepositoryFacts(
                structure=StructureFacts(has_tests=False, test_file_count=0),
            ),
            [],
            [],
        ),
    )

    output_path = tmp_path / "report.json"
    JsonFileReporter().write(result=result, output_path=output_path)
    payload = output_path.read_text(encoding="utf-8")

    assert '"recommendations"' in payload
    assert "REC.TESTING.001" in payload
    assert '"priority": "high"' in payload


def test_text_report_includes_recommendations_and_roadmap(
    tmp_path: Path,
) -> None:
    recommendations = _engine().generate(
        RepositoryFacts(
            structure=StructureFacts(has_tests=False, test_file_count=0),
            security=SecurityFacts(secret_finding_count=1),
            architecture=ArchitectureFacts(is_multi_application=True),
        ),
        [],
        [],
    )

    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path,
            files=["app.py"],
        ),
        recommendations=recommendations,
    )

    output_path = tmp_path / "report.txt"
    TextFileReporter().write(result=result, output_path=output_path)
    output = output_path.read_text(encoding="utf-8")

    assert "Modernization Recommendations" in output
    assert "Prioritized Roadmap" in output
    assert "Immediate" in output
    assert "Near term" in output
    assert "Later" in output
    assert "REC.SECURITY.001" in output
    assert "Rationale:" in output
    assert "Proposed action:" in output


def test_console_summary_shows_recommendation_counts() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=Path("/tmp/sample"),
            files=["app.py"],
        ),
        recommendations=_engine().generate(
            RepositoryFacts(
                structure=StructureFacts(has_tests=False),
                security=SecurityFacts(secret_finding_count=1),
            ),
            [],
            [],
        ),
    )

    ConsoleReporter(console=console).render_summary(result)

    output = console.export_text()
    assert "Top Recommendations" in output
    assert "CRITICAL" in output
    assert "REC.SECURITY.001" in output
    assert "REC.TESTING.001" in output
