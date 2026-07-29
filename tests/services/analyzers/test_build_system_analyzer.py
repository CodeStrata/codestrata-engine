"""Tests for the build discovery analyzer."""

from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers import BuildDiscoveryAnalyzer


def test_detects_maven_build_system() -> None:
    repository = Repository(
        name="sample-maven-project",
        path=Path("/tmp/sample-maven-project"),
        files=[
            "pom.xml",
            "mvnw",
            ".mvn/wrapper/maven-wrapper.properties",
            "src/main/java/com/example/Application.java",
        ],
    )

    analyzer = BuildDiscoveryAnalyzer()

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )
    findings = result.findings

    assert len(findings) == 1
    assert result.facts.build is not None
    assert result.facts.build.build_systems == ["maven"]


def test_detects_multiple_build_systems() -> None:
    repository = Repository(
        name="full-stack-project",
        path=Path("/tmp/sample-maven-project"),
        files=[
            "backend/pom.xml",
            "backend/mvnw",
            "frontend/package.json",
            "frontend/package-lock.json",
        ],
    )

    analyzer = BuildDiscoveryAnalyzer()

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )
    findings = result.findings
    finding = findings[0]

    assert finding.metadata["build_systems"] == ["maven", "npm"]
    assert finding.metadata["build_files"] == [
        "backend/pom.xml",
        "frontend/package.json",
    ]
    assert finding.metadata["wrapper_files"] == ["backend/mvnw"]
    assert finding.metadata["lock_files"] == [
        "frontend/package-lock.json",
    ]
    assert finding.metadata["multiple_build_systems"] is True


def test_returns_empty_build_facts_when_no_build_system_is_detected() -> None:
    repository = Repository(
        name="documentation-project",
        path=Path("/tmp/sample-maven-project"),
        files=[
            "README.md",
            "docs/architecture.md",
        ],
    )

    analyzer = BuildDiscoveryAnalyzer()

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )
    findings = result.findings
    finding = findings[0]

    assert finding.metadata["build_systems"] == []
    assert finding.metadata["build_files"] == []
    assert finding.metadata["wrapper_files"] == []
    assert finding.metadata["lock_files"] == []
    assert finding.metadata["multiple_build_systems"] is False
    assert finding.evidence == []
    assert "No supported build system" in finding.description
