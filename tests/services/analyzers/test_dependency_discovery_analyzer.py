from pathlib import Path

from codestrata.models import Repository
from codestrata.services.analyzers import DependencyDiscoveryAnalyzer


def test_discovers_dependency_manifests_and_lockfiles(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[
            "pom.xml",
            "package.json",
            "package-lock.json",
            "frontend/pnpm-lock.yaml",
            "src/main/java/Application.java",
        ],
    )

    result = DependencyDiscoveryAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    assert result.facts.dependencies is not None

    manifests = result.facts.dependencies.manifests

    assert [manifest.path for manifest in manifests] == [
        "frontend/pnpm-lock.yaml",
        "package-lock.json",
        "package.json",
        "pom.xml",
    ]

    assert [manifest.ecosystem for manifest in manifests] == [
        "pnpm",
        "npm",
        "npm",
        "maven",
    ]

    assert [manifest.lockfile for manifest in manifests] == [
        True,
        True,
        False,
        False,
    ]


def test_returns_empty_dependency_facts_when_no_manifests_exist(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[
            "README.md",
            "src/main/java/Application.java",
        ],
    )

    result = DependencyDiscoveryAnalyzer().analyze(
        repository=repository,
        technologies=[],
    )

    assert result.facts.dependencies is not None
    assert result.facts.dependencies.manifests == []
    assert result.facts.dependencies.dependencies == []
    assert result.findings == []
