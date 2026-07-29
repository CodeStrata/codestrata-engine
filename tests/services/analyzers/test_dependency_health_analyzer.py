from pathlib import Path

from codestrata.models import (
    Dependency,
    DependencyFacts,
    DependencyManifest,
    Repository,
    RepositoryFacts,
)
from codestrata.services.analyzers import DependencyHealthAnalyzer


def test_finds_unmanaged_dependency_versions(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["pom.xml"],
    )

    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            dependencies=[
                Dependency(
                    name="org.postgresql:postgresql",
                    version=None,
                    ecosystem="maven",
                    scope="runtime",
                    manifest_path="pom.xml",
                    unmanaged_version=True,
                )
            ]
        )
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=facts,
    )

    assert len(result.findings) == 1

    finding = result.findings[0]

    assert finding.rule_id == "DEP001"
    assert finding.metadata["dependency"] == ("org.postgresql:postgresql")


def test_finds_dynamic_dependency_versions(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["package.json"],
    )

    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            dependencies=[
                Dependency(
                    name="react",
                    version="^19.0.0",
                    ecosystem="npm",
                    scope="runtime",
                    manifest_path="package.json",
                    dynamic_version=True,
                )
            ]
        )
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=facts,
    )

    assert len(result.findings) == 1

    finding = result.findings[0]

    assert finding.rule_id == "DEP002"
    assert finding.metadata["version"] == "^19.0.0"


def test_finds_missing_npm_lockfile(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=["package.json"],
    )

    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="package.json",
                    ecosystem="npm",
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

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "DEP003"


def test_accepts_alternative_npm_lockfile(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[
            "package.json",
            "pnpm-lock.yaml",
        ],
    )

    facts = RepositoryFacts(
        dependencies=DependencyFacts(
            manifests=[
                DependencyManifest(
                    path="package.json",
                    ecosystem="npm",
                    manifest_type="manifest",
                    lockfile=False,
                ),
                DependencyManifest(
                    path="pnpm-lock.yaml",
                    ecosystem="pnpm",
                    manifest_type="lockfile",
                    lockfile=True,
                ),
            ]
        )
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=facts,
    )

    assert result.findings == []


def test_returns_no_findings_without_dependency_facts(
    tmp_path: Path,
) -> None:
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=[],
    )

    result = DependencyHealthAnalyzer().analyze(
        repository=repository,
        technologies=[],
        facts=RepositoryFacts(),
    )

    assert result.findings == []
