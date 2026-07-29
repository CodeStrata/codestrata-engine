"""Analyzer that collects structural repository metrics."""

from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.models import (
    AnalyzerResult,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)
from codestrata.models.normalized_facts import StructureFacts


class RepositoryMetricsAnalyzer:
    """Collects deterministic structural metrics for a repository."""

    _SOURCE_EXTENSIONS = {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".scala",
        ".swift",
        ".ts",
        ".tsx",
    }

    _CONFIG_FILE_NAMES = {
        ".env",
        ".env.example",
        ".gitignore",
        "application.properties",
        "application.yml",
        "application.yaml",
        "config.json",
        "config.toml",
        "config.yml",
        "config.yaml",
        "settings.json",
        "settings.toml",
        "settings.yml",
        "settings.yaml",
    }

    _CONFIG_EXTENSIONS = {
        ".ini",
        ".json",
        ".properties",
        ".toml",
        ".xml",
        ".yml",
        ".yaml",
    }

    _BUILD_FILE_NAMES = {
        "build.gradle",
        "build.gradle.kts",
        "composer.json",
        "go.mod",
        "gradlew",
        "mvnw",
        "package.json",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "settings.gradle",
        "settings.gradle.kts",
    }

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Collect repository metrics and return one consolidated finding."""

        del facts

        files = [PurePosixPath(file_path) for file_path in repository.files]

        source_files = [
            file_path for file_path in files if file_path.suffix.lower() in self._SOURCE_EXTENSIONS
        ]

        test_files = [file_path for file_path in files if self._is_test_file(file_path)]

        configuration_files = [
            file_path for file_path in files if self._is_configuration_file(file_path)
        ]

        build_files = [
            file_path for file_path in files if file_path.name.lower() in self._BUILD_FILE_NAMES
        ]

        docker_files = [file_path for file_path in files if self._is_docker_file(file_path)]

        github_workflows = [file_path for file_path in files if self._is_github_workflow(file_path)]

        kubernetes_manifests = [
            file_path for file_path in files if self._is_kubernetes_manifest(file_path)
        ]

        metrics = {
            "total_files": len(files),
            "source_files": len(source_files),
            "test_files": len(test_files),
            "configuration_files": len(configuration_files),
            "build_files": len(build_files),
            "docker_files": len(docker_files),
            "github_workflows": len(github_workflows),
            "kubernetes_manifests": len(kubernetes_manifests),
        }

        evidence_paths = sorted(
            {
                *build_files,
                *docker_files,
                *github_workflows,
                *kubernetes_manifests,
            },
            key=str,
        )

        evidence = [
            Evidence(
                file_path=str(file_path),
                description="Repository artifact included in structural metrics.",
            )
            for file_path in evidence_paths
        ]

        finding = Finding(
            rule_id="repository.metrics.summary",
            title="Repository Metrics",
            description=(f"Collected structural metrics for repository '{repository.name}'."),
            category=FindingCategory.MAINTAINABILITY,
            severity=Severity.INFO,
            source=FindingSource.DETERMINISTIC,
            evidence=evidence,
            affected_technologies=[technology.name for technology in technologies],
            metadata=metrics,
        )

        return AnalyzerResult(
            findings=[finding],
            facts=RepositoryFacts(
                structure=StructureFacts(
                    file_count=len(files),
                    source_file_count=len(source_files),
                    test_file_count=len(test_files),
                    has_tests=bool(test_files),
                )
            ),
        )

    @staticmethod
    def _is_test_file(file_path: PurePosixPath) -> bool:
        """Return whether a file appears to be a test file."""

        path_parts = {part.lower() for part in file_path.parts}
        file_name = file_path.name.lower()

        return (
            "test" in path_parts
            or "tests" in path_parts
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
            or file_name.endswith("test.java")
            or file_name.endswith("tests.java")
            or file_name.endswith(".spec.js")
            or file_name.endswith(".spec.ts")
            or file_name.endswith(".test.js")
            or file_name.endswith(".test.ts")
            or file_name.endswith(".spec.jsx")
            or file_name.endswith(".spec.tsx")
            or file_name.endswith(".test.jsx")
            or file_name.endswith(".test.tsx")
        )

    def _is_configuration_file(self, file_path: PurePosixPath) -> bool:
        """Return whether a file appears to contain configuration."""

        file_name = file_path.name.lower()

        return (
            file_name in self._CONFIG_FILE_NAMES
            or file_path.suffix.lower() in self._CONFIG_EXTENSIONS
        )

    @staticmethod
    def _is_docker_file(file_path: PurePosixPath) -> bool:
        """Return whether a file is a Docker artifact."""

        file_name = file_path.name.lower()

        return (
            file_name == "dockerfile"
            or file_name.startswith("dockerfile.")
            or file_name in {"docker-compose.yml", "docker-compose.yaml"}
            or file_name.startswith("compose.")
        )

    @staticmethod
    def _is_github_workflow(file_path: PurePosixPath) -> bool:
        """Return whether a file is a GitHub Actions workflow."""

        parts = tuple(part.lower() for part in file_path.parts)

        return (
            len(parts) >= 3
            and parts[0] == ".github"
            and parts[1] == "workflows"
            and file_path.suffix.lower() in {".yml", ".yaml"}
        )

    @staticmethod
    def _is_kubernetes_manifest(file_path: PurePosixPath) -> bool:
        """Return whether a file appears to be a Kubernetes manifest."""

        lower_parts = {part.lower() for part in file_path.parts}
        file_name = file_path.name.lower()

        return file_path.suffix.lower() in {".yml", ".yaml"} and (
            "k8s" in lower_parts
            or "kubernetes" in lower_parts
            or file_name.startswith("deployment")
            or file_name.startswith("service")
            or file_name.startswith("ingress")
            or file_name.startswith("statefulset")
            or file_name.startswith("daemonset")
        )
