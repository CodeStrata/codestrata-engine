"""Regression signals modeled on spring-petclinic data-quality issues."""

from __future__ import annotations

from pathlib import Path

from codestrata.models import (
    Dependency,
    DependencyFacts,
    DependencyManifest,
    Repository,
    RepositoryFacts,
    Severity,
    TechnologyFacts,
)
from codestrata.models.cicd import CicdFacts, CicdPipeline
from codestrata.services.analyzers import (
    ArchitectureAnalyzer,
    CicdDiscoveryAnalyzer,
    CloudReadinessAnalyzer,
    DependencyHealthAnalyzer,
)
from codestrata.services.analyzers.cicd_command_classifier import (
    CicdCommandCategory,
    CicdCommandClassifier,
)


def _repository(root: Path, files: dict[str, str] | list[str]) -> Repository:
    """Create a repository fixture with optional file contents."""

    if isinstance(files, list):
        file_map = {path: "" for path in files}
    else:
        file_map = files

    for relative_path, content in file_map.items():
        file_path = root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    return Repository(
        name=root.name,
        path=root,
        files=sorted(file_map),
    )


def test_gradle_maven_case_insensitive_dedupe() -> None:
    """Build tool aliases should collapse to Gradle and Maven."""

    merged = TechnologyFacts(
        build_tools=["gradle", "maven"],
    ).merge(
        TechnologyFacts(
            build_tools=["Gradle", "Maven"],
        )
    )

    assert merged.build_tools == ["Gradle", "Maven"]


def test_framework_names_separated_from_dependency_coordinates() -> None:
    """Technology frameworks should not store Maven GAV coordinates."""

    technology = TechnologyFacts(frameworks=["Spring Boot"])
    dependencies = DependencyFacts(
        framework_dependencies=[
            "org.springframework.boot:spring-boot-starter-web",
        ]
    )

    assert "org.springframework.boot:spring-boot-starter-web" not in technology.frameworks
    assert dependencies.framework_dependencies == [
        "org.springframework.boot:spring-boot-starter-web",
    ]
    assert technology.frameworks == ["Spring Boot"]


def test_spring_data_repository_classes_produce_persistence_layer(
    tmp_path: Path,
) -> None:
    """Spring Data *Repository.java classes should detect persistence."""

    repository = _repository(
        tmp_path,
        [
            "src/main/java/org/springframework/samples/petclinic/owner/OwnerRepository.java",
            "src/main/java/org/springframework/samples/petclinic/vet/VetRepository.java",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])

    assert result.facts.architecture is not None
    assert result.facts.architecture.has_persistence_layer is True
    assert any(finding.rule_id == "ARCH003" for finding in result.findings)


def test_controller_files_produce_api_evidence(tmp_path: Path) -> None:
    """*Controller.java files should produce API-layer evidence."""

    controller = "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
    repository = _repository(tmp_path, [controller])

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])
    finding = next(item for item in result.findings if item.rule_id == "ARCH002")

    assert result.facts.architecture is not None
    assert result.facts.architecture.has_api_layer is True
    assert controller in finding.metadata["sample_paths"]


def test_application_properties_do_not_produce_api_evidence(
    tmp_path: Path,
) -> None:
    """Resource configuration files must not count as API files."""

    repository = _repository(
        tmp_path,
        [
            "src/main/resources/application.properties",
            "src/main/resources/application-mysql.properties",
            "src/main/resources/messages/messages.properties",
        ],
    )

    result = ArchitectureAnalyzer().analyze(repository=repository, technologies=[])

    assert result.facts.architecture is not None
    assert result.facts.architecture.has_api_layer is not True
    assert all(finding.rule_id != "ARCH002" for finding in result.findings)


def test_gradle_build_workflow_produces_has_build_and_has_tests(
    tmp_path: Path,
) -> None:
    """Gradle build workflows should set repository has_build and has_tests."""

    repository = _repository(
        tmp_path,
        {
            ".github/workflows/gradle.yml": (
                "name: Gradle\n"
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: ./gradlew build\n"
            )
        },
    )

    result = CicdDiscoveryAnalyzer().analyze(repository=repository, technologies=[])
    cicd = result.facts.cicd

    assert cicd is not None
    assert cicd.has_build is True
    assert cicd.has_tests is True
    assert any("./gradlew build" in pipeline.build_commands for pipeline in cicd.pipelines)


def test_maven_verify_produces_has_build_and_has_tests(
    tmp_path: Path,
) -> None:
    """Maven wrapper verify should classify as build and tests."""

    repository = _repository(
        tmp_path,
        {
            ".github/workflows/maven.yml": (
                "name: Maven\n"
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: ./mvnw -B verify\n"
            )
        },
    )

    result = CicdDiscoveryAnalyzer().analyze(repository=repository, technologies=[])
    cicd = result.facts.cicd
    classifier = CicdCommandClassifier()

    assert cicd is not None
    assert cicd.has_build is True
    assert cicd.has_tests is True
    assert CicdCommandCategory.BUILD in classifier.classify("./mvnw -B verify")
    assert CicdCommandCategory.TEST in classifier.classify("./mvnw -B verify")


def test_pipeline_matrix_caching_flags_aggregate_correctly() -> None:
    """Repository CI flags should OR matrix and caching across pipelines."""

    aggregated = CicdFacts(
        pipelines=[
            CicdPipeline(
                provider="github-actions",
                path=".github/workflows/gradle.yml",
                uses_matrix_builds=True,
                uses_caching=True,
            ),
            CicdPipeline(
                provider="github-actions",
                path=".github/workflows/maven.yml",
                uses_matrix_builds=False,
                uses_caching=False,
            ),
        ],
        uses_matrix_builds=True,
        uses_caching=True,
    ).merge(
        CicdFacts(
            pipelines=[],
            uses_matrix_builds=False,
            uses_caching=False,
        )
    )

    assert aggregated.uses_matrix_builds is True
    assert aggregated.uses_caching is True


def test_pipeline_matrix_caching_discovered_from_workflows(
    tmp_path: Path,
) -> None:
    """Discovery should roll pipeline matrix/caching up to repository facts."""

    repository = _repository(
        tmp_path,
        {
            ".github/workflows/gradle.yml": (
                "name: Gradle\n"
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    strategy:\n"
                "      matrix:\n"
                "        java: [17, 21]\n"
                "    steps:\n"
                "      - uses: actions/setup-java@v4\n"
                "        with:\n"
                "          cache: gradle\n"
                "      - run: ./gradlew build\n"
            ),
            ".github/workflows/maven.yml": (
                "name: Maven\n"
                "on: [push]\n"
                "jobs:\n"
                "  build:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: ./mvnw -B verify\n"
            ),
        },
    )

    result = CicdDiscoveryAnalyzer().analyze(repository=repository, technologies=[])
    cicd = result.facts.cicd

    assert cicd is not None
    assert cicd.uses_matrix_builds is True
    assert cicd.uses_caching is True
    assert cicd.has_build is True
    assert cicd.has_tests is True


def test_devcontainer_dockerfile_is_not_application_containerization(
    tmp_path: Path,
) -> None:
    """A .devcontainer Dockerfile alone must not set application has_docker."""

    repository = _repository(
        tmp_path,
        [
            ".devcontainer/Dockerfile",
            "docker-compose.yml",
        ],
    )

    result = CloudReadinessAnalyzer().analyze(repository=repository, technologies=[])
    cloud = result.facts.cloud

    assert cloud is not None
    assert cloud.has_docker is False
    assert cloud.has_devcontainer is True
    assert cloud.has_docker_compose is True
    assert "CLOUD001" not in {
        finding.rule_id for finding in result.findings if finding.rule_id is not None
    }
    assert "CLOUD002" in {
        finding.rule_id for finding in result.findings if finding.rule_id is not None
    }


def test_gradle_without_locking_and_without_risky_versions_is_not_medium(
    tmp_path: Path,
) -> None:
    """Gradle without locking should be LOW when no dependency risks exist."""

    repository = Repository(name="sample", path=tmp_path, files=["build.gradle"])
    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="build.gradle",
                    ecosystem="gradle",
                    manifest_type="manifest",
                    lockfile=False,
                )
            ],
            dependencies=[
                Dependency(
                    name="org.springframework.boot:spring-boot-starter",
                    version="3.3.0",
                    ecosystem="gradle",
                    scope="runtime",
                    manifest_path="build.gradle",
                    dynamic_version=False,
                    unmanaged_version=False,
                )
            ],
        )
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=facts,
    )

    dep003 = [finding for finding in result.findings if finding.rule_id == "DEP003"]
    assert len(dep003) == 1
    assert dep003[0].severity == Severity.LOW
    assert "locking is not configured" in dep003[0].description


def test_maven_without_lockfile_does_not_produce_dep003(
    tmp_path: Path,
) -> None:
    """Maven should not be treated as missing a conventional lockfile."""

    repository = Repository(name="sample", path=tmp_path, files=["pom.xml"])
    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="pom.xml",
                    ecosystem="maven",
                    manifest_type="manifest",
                    lockfile=False,
                )
            ]
        )
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=facts,
    )

    assert all(finding.rule_id != "DEP003" for finding in result.findings)
