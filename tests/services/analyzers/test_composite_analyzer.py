"""Tests for the composite repository analyzer."""

from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    BuildFacts,
    DependencyFacts,
    DependencyManifest,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
)
from codestrata.services.analyzers import CompositeAnalyzer


class StubAnalyzer:
    """Analyzer that returns one configured finding."""

    def __init__(self, rule_id: str) -> None:
        self._rule_id = rule_id

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Return one finding without contributing facts."""

        del technologies
        del facts

        return AnalyzerResult(
            findings=[
                Finding(
                    rule_id=self._rule_id,
                    title="Test finding",
                    description=f"Finding for {repository.name}.",
                    category=FindingCategory.OTHER,
                    severity=Severity.INFO,
                    source=FindingSource.DETERMINISTIC,
                )
            ]
        )


class BuildFactsAnalyzer:
    """Analyzer that contributes build facts."""

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
            facts=RepositoryFacts(
                build=BuildFacts(build_systems=["maven"]),
            )
        )


class DependencyFactsAnalyzer:
    """Analyzer that contributes dependency facts and records received facts."""

    def __init__(self) -> None:
        self.received_facts: RepositoryFacts | None = None

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        del repository
        del technologies

        self.received_facts = facts

        return AnalyzerResult(
            facts=RepositoryFacts(
                dependencies=DependencyFacts(
                    manifests=[
                        DependencyManifest(
                            path="pom.xml",
                            ecosystem="maven",
                            manifest_type="manifest",
                        )
                    ]
                )
            )
        )


class FactsAwareFindingAnalyzer:
    """Analyzer that emits a finding based on accumulated facts."""

    def __init__(self) -> None:
        self.received_facts: RepositoryFacts | None = None

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        del repository
        del technologies

        self.received_facts = facts

        build_systems = (
            facts.build.build_systems if facts is not None and facts.build is not None else []
        )
        manifest_count = (
            len(facts.dependencies.manifests)
            if facts is not None and facts.dependencies is not None
            else 0
        )

        return AnalyzerResult(
            findings=[
                Finding(
                    rule_id="test.facts.aware",
                    title="Facts-aware finding",
                    description=(
                        f"Saw build systems {build_systems} and "
                        f"{manifest_count} dependency manifests."
                    ),
                    category=FindingCategory.OTHER,
                    severity=Severity.INFO,
                    source=FindingSource.DETERMINISTIC,
                    metadata={
                        "build_systems": build_systems,
                        "manifest_count": manifest_count,
                    },
                )
            ]
        )


def test_composite_analyzer_combines_findings() -> None:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
    )

    analyzer = CompositeAnalyzer(
        analyzers=[
            StubAnalyzer("test.first"),
            StubAnalyzer("test.second"),
        ]
    )

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )
    findings = result.findings
    assert [finding.rule_id for finding in findings] == [
        "test.first",
        "test.second",
    ]


def test_composite_analyzer_returns_empty_list_when_no_analyzers_exist() -> None:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
    )

    analyzer = CompositeAnalyzer(analyzers=[])

    result = analyzer.analyze(
        repository=repository,
        technologies=[],
    )

    assert result.findings == []
    assert result.facts.build is None


def test_composite_analyzer_passes_merged_facts_to_each_next_analyzer() -> None:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
    )

    dependency_analyzer = DependencyFactsAnalyzer()
    facts_aware_analyzer = FactsAwareFindingAnalyzer()

    result = CompositeAnalyzer(
        analyzers=[
            BuildFactsAnalyzer(),
            dependency_analyzer,
            facts_aware_analyzer,
        ]
    ).analyze(
        repository=repository,
        technologies=[],
    )

    assert dependency_analyzer.received_facts is not None
    assert dependency_analyzer.received_facts.build is not None
    assert dependency_analyzer.received_facts.build.build_systems == ["maven"]
    assert dependency_analyzer.received_facts.dependencies is None

    assert facts_aware_analyzer.received_facts is not None
    assert facts_aware_analyzer.received_facts.build is not None
    assert facts_aware_analyzer.received_facts.build.build_systems == ["maven"]
    assert facts_aware_analyzer.received_facts.dependencies is not None
    assert [
        manifest.path for manifest in facts_aware_analyzer.received_facts.dependencies.manifests
    ] == ["pom.xml"]

    assert result.facts.build is not None
    assert result.facts.build.build_systems == ["maven"]
    assert result.facts.dependencies is not None
    assert [manifest.path for manifest in result.facts.dependencies.manifests] == ["pom.xml"]

    assert len(result.findings) == 1
    assert result.findings[0].metadata["build_systems"] == ["maven"]
    assert result.findings[0].metadata["manifest_count"] == 1
