"""Tests for structured repository facts models and merge behavior."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from codestrata.models import (
    AnalysisResult,
    ArchitectureFacts,
    CloudReadinessFacts,
    Repository,
    RepositoryFacts,
    SecurityFacts,
    StructureFacts,
    TechnologyFacts,
)
from codestrata.models.cicd import CicdFacts
from codestrata.models.dependency_facts import DependencyFacts
from codestrata.reporters import ConsoleReporter, JsonFileReporter, TextFileReporter
from codestrata.services.analyzers import (
    ArchitectureAnalyzer,
    CicdDiscoveryAnalyzer,
    CloudReadinessAnalyzer,
    CompositeAnalyzer,
    RepositoryMetricsAnalyzer,
    SecurityAnalyzer,
)


def test_repository_facts_default_construction() -> None:
    facts = RepositoryFacts()

    assert facts.structure is None
    assert facts.technology is None
    assert facts.build is None
    assert facts.dependencies is None
    assert facts.cicd is None
    assert facts.security is None
    assert facts.cloud is None
    assert facts.architecture is None


def test_structure_facts_defaults_avoid_mutable_shared_state() -> None:
    left = StructureFacts()
    right = StructureFacts()

    left.architecture_layers.append("api")

    assert right.architecture_layers == []


def test_merge_two_fact_objects() -> None:
    left = RepositoryFacts(
        structure=StructureFacts(
            file_count=10,
            has_tests=False,
            architecture_layers=["api"],
        ),
        security=SecurityFacts(secret_finding_count=1),
    )
    right = RepositoryFacts(
        structure=StructureFacts(
            source_file_count=4,
            has_tests=True,
            architecture_layers=["service"],
        ),
        cloud=CloudReadinessFacts(has_docker=True),
    )

    merged = left.merge(right)

    assert merged.structure is not None
    assert merged.structure.file_count == 10
    assert merged.structure.source_file_count == 4
    assert merged.structure.has_tests is True
    assert merged.structure.architecture_layers == ["api", "service"]
    assert merged.security is not None
    assert merged.security.secret_finding_count == 1
    assert merged.cloud is not None
    assert merged.cloud.has_docker is True


def test_duplicate_list_removal_and_deterministic_ordering() -> None:
    left = TechnologyFacts(
        programming_languages=["Java", "Python"],
        frameworks=["Spring"],
    )
    right = TechnologyFacts(
        programming_languages=["Python", "Go"],
        frameworks=["Spring", "React"],
    )

    merged = left.merge(right)

    assert merged.programming_languages == ["Java", "Python", "Go"]
    assert merged.frameworks == ["Spring", "React"]


def test_boolean_merge_behavior() -> None:
    left = ArchitectureFacts(
        has_api_layer=True,
        has_service_layer=False,
        is_multi_application=None,
    )
    right = ArchitectureFacts(
        has_api_layer=False,
        has_service_layer=True,
        is_multi_application=True,
    )

    merged = left.merge(right)

    assert merged.has_api_layer is True
    assert merged.has_service_layer is True
    assert merged.is_multi_application is True


def test_numeric_count_behavior() -> None:
    left = SecurityFacts(
        sensitive_file_count=2,
        secret_finding_count=None,
    )
    right = SecurityFacts(
        sensitive_file_count=5,
        secret_finding_count=3,
    )

    merged = left.merge(right)

    assert merged.sensitive_file_count == 5
    assert merged.secret_finding_count == 3


def test_missing_values_do_not_overwrite_populated_values() -> None:
    left = RepositoryFacts(
        structure=StructureFacts(file_count=42, has_tests=True),
        cloud=CloudReadinessFacts(has_docker=True, has_helm=False),
    )
    right = RepositoryFacts(
        structure=StructureFacts(),
        cloud=CloudReadinessFacts(),
    )

    merged = left.merge(right)

    assert merged.structure is not None
    assert merged.structure.file_count == 42
    assert merged.structure.has_tests is True
    assert merged.cloud is not None
    assert merged.cloud.has_docker is True
    assert merged.cloud.has_helm is False


def test_metrics_analyzer_populates_structure_facts(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_app() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=["src/app.py", "tests/test_app.py"],
    )

    result = RepositoryMetricsAnalyzer().analyze(repository, [])

    assert result.facts.structure is not None
    assert result.facts.structure.file_count == 2
    assert result.facts.structure.source_file_count == 2
    assert result.facts.structure.test_file_count == 1
    assert result.facts.structure.has_tests is True


def test_security_analyzer_populates_security_facts(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("eval(user_input)\n", encoding="utf-8")

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=[".env", "app.py"],
    )

    result = SecurityAnalyzer().analyze(repository, [])

    assert result.facts.security is not None
    assert result.facts.security.sensitive_file_count == 1
    assert result.facts.security.dangerous_execution_count is not None
    assert result.facts.security.dangerous_execution_count >= 1


def test_architecture_analyzer_populates_architecture_facts(
    tmp_path: Path,
) -> None:
    files = [
        "src/controllers/UserController.java",
        "src/services/UserService.java",
        "src/repositories/UserRepository.java",
        "src/domain/User.java",
    ]

    for relative_path in files:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=files,
    )

    result = ArchitectureAnalyzer().analyze(repository, [])

    assert result.facts.architecture is not None
    assert result.facts.architecture.has_api_layer is True
    assert result.facts.architecture.has_service_layer is True
    assert result.facts.architecture.has_persistence_layer is True
    assert result.facts.architecture.has_domain_layer is True
    assert result.facts.architecture.is_multi_application is False
    assert result.facts.structure is not None
    assert result.facts.structure.application_count == 1
    assert result.facts.structure.architecture_layers == [
        "api",
        "service",
        "persistence",
        "domain",
    ]


def test_cicd_analyzer_populates_ci_facts(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo hi\n",
        encoding="utf-8",
    )

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=[".github/workflows/ci.yml"],
    )

    result = CicdDiscoveryAnalyzer().analyze(repository, [])

    assert result.facts.cicd is not None
    assert result.facts.cicd.has_ci is True
    assert result.facts.cicd.ci_platforms == ["github-actions"]
    assert result.facts.cicd.providers == ["github-actions"]


def test_cloud_readiness_analyzer_populates_cloud_facts(
    tmp_path: Path,
) -> None:
    (tmp_path / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  app:\n    image: app\n",
        encoding="utf-8",
    )

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=["Dockerfile", "docker-compose.yml"],
    )

    result = CloudReadinessAnalyzer().analyze(repository, [])

    assert result.facts.cloud is not None
    assert result.facts.cloud.has_docker is True
    assert result.facts.cloud.has_docker_compose is True
    assert result.facts.cloud.cloud_capabilities == [
        "docker",
        "docker-compose",
    ]


def test_composite_analyzer_produces_one_consolidated_facts_object(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=abc\n", encoding="utf-8")

    repository = Repository(
        name=tmp_path.name,
        path=tmp_path,
        files=["src/app.py", "Dockerfile", ".env"],
    )

    result = CompositeAnalyzer(
        analyzers=[
            RepositoryMetricsAnalyzer(),
            SecurityAnalyzer(),
            CloudReadinessAnalyzer(),
        ]
    ).analyze(repository, [])

    assert result.facts.structure is not None
    assert result.facts.structure.file_count == 3
    assert result.facts.security is not None
    assert result.facts.security.sensitive_file_count == 1
    assert result.facts.cloud is not None
    assert result.facts.cloud.has_docker is True


def test_report_json_includes_facts(tmp_path: Path) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path,
            files=["app.py"],
        ),
        facts=RepositoryFacts(
            structure=StructureFacts(file_count=1, has_tests=False),
            cloud=CloudReadinessFacts(has_docker=True),
        ),
    )

    output_path = tmp_path / "report.json"
    JsonFileReporter().write(result=result, output_path=output_path)

    payload = output_path.read_text(encoding="utf-8")
    facts_section = payload.split('"facts"')[1].split('"findings"')[0]

    assert '"structure"' in facts_section
    assert '"file_count": 1' in facts_section
    assert '"has_docker": true' in facts_section
    assert '"files"' not in facts_section


def test_report_txt_includes_repository_facts_section(
    tmp_path: Path,
) -> None:
    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=tmp_path,
            files=["app.py"],
        ),
        facts=RepositoryFacts(
            structure=StructureFacts(
                file_count=1,
                has_tests=False,
            ),
            cicd=CicdFacts(
                has_ci=True,
                ci_platforms=["github-actions"],
            ),
            dependencies=DependencyFacts(dependency_count=2),
        ),
    )

    output_path = tmp_path / "report.txt"
    TextFileReporter().write(result=result, output_path=output_path)

    output = output_path.read_text(encoding="utf-8")

    assert "Repository Facts" in output
    assert "File count" in output
    assert "CI platforms" in output
    assert "Dependency count" in output


def test_console_reporter_includes_repository_facts() -> None:
    console = Console(record=True, width=120, force_terminal=False)

    result = AnalysisResult(
        repository=Repository(
            name="sample",
            path=Path("/tmp/sample"),
            files=["app.py"],
        ),
        facts=RepositoryFacts(
            architecture=ArchitectureFacts(has_api_layer=True),
        ),
    )

    ConsoleReporter(console=console).render_detailed(result)

    assert "Repository Facts" in console.export_text()
