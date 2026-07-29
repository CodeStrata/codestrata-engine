"""Tests for repository metrics analysis."""

from pathlib import Path

from codestrata.models import (
    FindingCategory,
    FindingSource,
    Repository,
    Severity,
    Technology,
    TechnologyCategory,
)
from codestrata.services.analyzers import RepositoryMetricsAnalyzer


def test_repository_metrics_analyzer_collects_structural_metrics() -> None:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
        files=[
            "src/main/java/App.java",
            "src/main/java/Service.java",
            "src/test/java/AppTest.java",
            "src/main/resources/application.yml",
            "pom.xml",
            "Dockerfile",
            ".github/workflows/ci.yml",
            "k8s/deployment.yaml",
            "README.md",
        ],
    )

    technologies = [
        Technology(
            name="Java",
            category=TechnologyCategory.LANGUAGE,
            confidence=1.0,
            source="test",
        )
    ]

    analyzer = RepositoryMetricsAnalyzer()

    result = analyzer.analyze(
        repository=repository,
        technologies=technologies,
    )

    findings = result.findings
    assert len(findings) == 1

    finding = findings[0]

    assert finding.rule_id == "repository.metrics.summary"
    assert finding.title == "Repository Metrics"
    assert finding.category == FindingCategory.MAINTAINABILITY
    assert finding.severity == Severity.INFO
    assert finding.source == FindingSource.DETERMINISTIC
    assert finding.affected_technologies == ["Java"]

    assert finding.metadata == {
        "total_files": 9,
        "source_files": 3,
        "test_files": 1,
        "configuration_files": 4,
        "build_files": 1,
        "docker_files": 1,
        "github_workflows": 1,
        "kubernetes_manifests": 1,
    }

    evidence_paths = {evidence.file_path for evidence in finding.evidence}

    assert evidence_paths == {
        ".github/workflows/ci.yml",
        "Dockerfile",
        "k8s/deployment.yaml",
        "pom.xml",
    }

    assert result.facts.structure is not None
    assert result.facts.structure.file_count == 9
    assert result.facts.structure.source_file_count == 3
    assert result.facts.structure.test_file_count == 1
    assert result.facts.structure.has_tests is True


def test_repository_metrics_analyzer_returns_zero_counts() -> None:
    repository = Repository(
        name="empty",
        path=Path("/tmp/empty"),
        files=[],
    )

    analyzer = RepositoryMetricsAnalyzer()

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )
    findings = result.findings
    assert len(findings) == 1
    assert findings[0].metadata == {
        "total_files": 0,
        "source_files": 0,
        "test_files": 0,
        "configuration_files": 0,
        "build_files": 0,
        "docker_files": 0,
        "github_workflows": 0,
        "kubernetes_manifests": 0,
    }
