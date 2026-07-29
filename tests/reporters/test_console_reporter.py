from pathlib import Path

from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    BuildFacts,
    DependencyFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
)
from codestrata.reporters import ConsoleReporter


def test_renders_repository_and_findings() -> None:
    console = Console(
        record=True,
        width=120,
        force_terminal=False,
    )

    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=Path("/tmp/sample"),
            files=["pom.xml", "src/Application.java"],
        ),
        technologies=[],
        facts=RepositoryFacts(
            build=BuildFacts(
                build_systems=["maven"],
                build_files=["pom.xml"],
                packaging_types=["jar"],
                java_source_versions=["17"],
                inferred_commands=["./mvnw test"],
            ),
            dependencies=DependencyFacts(
                direct_dependency_count=3,
                test_dependency_count=1,
                framework_dependencies=["org.springframework.boot:spring-boot-starter-web"],
            ),
        ),
        findings=[
            Finding(
                rule_id="DEP001",
                title="Dependency has no explicit version",
                description=("org.postgresql:postgresql does not declare an explicit version."),
                category=FindingCategory.DEPENDENCY,
                severity=Severity.MEDIUM,
                source=FindingSource.DETERMINISTIC,
                evidence=[
                    Evidence(
                        file_path="pom.xml",
                        description=(
                            "org.postgresql:postgresql does not declare an explicit version."
                        ),
                        detected_value="org.postgresql:postgresql",
                    )
                ],
                affected_technologies=["maven"],
                metadata={},
            )
        ],
        recommendations=[],
    )

    ConsoleReporter(console=console).render(result)

    output = console.export_text()

    assert "CodeStrata" in output
    assert "sample" in output
    assert "maven" in output
    assert "Direct dependencies" in output
    assert "DEP001" in output
    assert "MEDIUM" in output
    assert "Total" in output


def test_renders_empty_findings_message() -> None:
    console = Console(
        record=True,
        width=120,
        force_terminal=False,
    )

    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=Path("/tmp/sample"),
            files=[],
        ),
        technologies=[],
        facts=RepositoryFacts(),
        findings=[],
        recommendations=[],
    )

    ConsoleReporter(console=console).render(result)

    output = console.export_text()

    assert "No deterministic findings detected" in output
