"""Analyzer that detects repository build systems and build artifacts."""

from collections.abc import Sequence
from pathlib import PurePosixPath

from codestrata.models import (
    AnalyzerResult,
    BuildFacts,
    Evidence,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)
from codestrata.models.normalized_facts import TechnologyFacts, canonical_technology_name


class BuildDiscoveryAnalyzer:
    """Detects build systems using deterministic repository artifacts."""

    _BUILD_SYSTEM_FILES: dict[str, set[str]] = {
        "maven": {
            "pom.xml",
        },
        "gradle": {
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        },
        "ant": {
            "build.xml",
        },
        "npm": {
            "package.json",
        },
        "composer": {
            "composer.json",
        },
        "python": {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
        },
        "go": {
            "go.mod",
        },
        "rust": {
            "cargo.toml",
        },
    }

    _WRAPPER_FILES: dict[str, set[str]] = {
        "maven": {
            "mvnw",
            "mvnw.cmd",
        },
        "gradle": {
            "gradlew",
            "gradlew.bat",
        },
    }

    _LOCK_FILES: dict[str, set[str]] = {
        "npm": {
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        },
        "composer": {
            "composer.lock",
        },
        "python": {
            "poetry.lock",
            "pdm.lock",
            "uv.lock",
            "pipfile.lock",
        },
        "go": {
            "go.sum",
        },
        "rust": {
            "cargo.lock",
        },
    }

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Detect build systems and return one consolidated finding."""

        del facts

        files = [PurePosixPath(file_path) for file_path in repository.files]

        detected_build_systems: set[str] = set()
        build_files: list[PurePosixPath] = []
        wrapper_files: list[PurePosixPath] = []
        lock_files: list[PurePosixPath] = []

        for file_path in files:
            file_name = file_path.name.lower()

            for build_system, known_files in self._BUILD_SYSTEM_FILES.items():
                if file_name in known_files:
                    detected_build_systems.add(build_system)
                    build_files.append(file_path)

            for build_system, known_files in self._WRAPPER_FILES.items():
                if file_name in known_files:
                    detected_build_systems.add(build_system)
                    wrapper_files.append(file_path)

            for build_system, known_files in self._LOCK_FILES.items():
                if file_name in known_files:
                    detected_build_systems.add(build_system)
                    lock_files.append(file_path)

        sorted_build_systems = sorted(detected_build_systems)
        sorted_build_files = sorted(build_files, key=str)
        sorted_wrapper_files = sorted(wrapper_files, key=str)
        sorted_lock_files = sorted(lock_files, key=str)

        evidence_paths = sorted(
            {
                *sorted_build_files,
                *sorted_wrapper_files,
                *sorted_lock_files,
            },
            key=str,
        )

        evidence = [
            Evidence(
                file_path=str(file_path),
                description="Repository artifact used to detect the build system.",
            )
            for file_path in evidence_paths
        ]

        build_facts = BuildFacts(
            build_systems=sorted_build_systems,
            build_files=[str(path) for path in sorted_build_files],
            wrapper_files=[str(path) for path in sorted_wrapper_files],
            lock_files=[str(path) for path in sorted_lock_files],
            multiple_build_systems=len(sorted_build_systems) > 1,
        )

        metadata = build_facts.model_dump()

        if build_facts.build_systems:
            description = "Detected build systems: " + ", ".join(build_facts.build_systems) + "."
        else:
            description = (
                f"No supported build system was detected in repository '{repository.name}'."
            )

        finding = Finding(
            rule_id="build.system.summary",
            title="Build System",
            description=description,
            category=FindingCategory.MAINTAINABILITY,
            severity=Severity.INFO,
            source=FindingSource.DETERMINISTIC,
            evidence=evidence,
            affected_technologies=[technology.name for technology in technologies],
            metadata=metadata,
        )

        return AnalyzerResult(
            findings=[finding],
            facts=RepositoryFacts(
                build=build_facts,
                technology=TechnologyFacts(
                    build_tools=[
                        canonical_technology_name(system) for system in build_facts.build_systems
                    ],
                ),
            ),
        )
