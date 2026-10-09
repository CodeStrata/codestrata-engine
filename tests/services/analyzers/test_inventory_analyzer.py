"""InventoryAnalyzer publishes compatible facts into the composite pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    Repository,
    RepositoryFacts,
    Technology,
)
from codestrata.services.analyzers import CompositeAnalyzer, InventoryAnalyzer
from codestrata.services.default_pipeline import builtin_analyzers

FIXTURES = (
    Path(__file__).resolve().parents[2] / "application" / "evidence" / "inventory" / "fixtures"
)


class RecordingAnalyzer:
    """Records facts received from earlier analyzers."""

    def __init__(self) -> None:
        self.received: RepositoryFacts | None = None

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        del repository
        del technologies
        self.received = facts
        return AnalyzerResult()


def test_inventory_analyzer_emits_no_findings_or_health_score() -> None:
    analyzer = InventoryAnalyzer()
    result = analyzer.analyze(
        repository=Repository(name="demo", path=FIXTURES / "mixed_language"),
        technologies=[],
    )
    assert result.findings == []
    assert result.facts.structure is not None
    assert result.facts.structure.source_file_count
    assert analyzer.last_envelope is not None
    assert analyzer.last_envelope.body.health_verdict == "none"
    dumped = str(result.facts.model_dump(mode="json"))
    assert "health_score" not in dumped
    assert result.facts.dependencies is not None


def test_enabled_analyzer_sees_inventory_facts_through_composite() -> None:
    recorder = RecordingAnalyzer()
    composite = CompositeAnalyzer(analyzers=[InventoryAnalyzer(), recorder])
    composite.analyze(
        repository=Repository(name="demo", path=FIXTURES / "npm_missing_lock"),
        technologies=[],
    )
    assert recorder.received is not None
    assert recorder.received.dependencies is not None
    assert recorder.received.dependencies.dependency_count >= 1
    assert recorder.received.dependencies.dependencies
    dumped = str(recorder.received.model_dump(mode="json"))
    assert "health_score" not in dumped


def test_missing_lock_is_not_projected_as_zero_dependencies() -> None:
    analyzer = InventoryAnalyzer()
    result = analyzer.analyze(
        repository=Repository(name="npm", path=FIXTURES / "npm_missing_lock"),
        technologies=[],
    )
    deps = result.facts.dependencies
    assert deps is not None
    assert deps.dependency_count >= 1
    assert all(item.unmanaged_version for item in deps.dependencies)


def test_ci_projection_does_not_claim_execution() -> None:
    analyzer = InventoryAnalyzer()
    result = analyzer.analyze(
        repository=Repository(name="ci", path=FIXTURES / "ci_direct_command"),
        technologies=[],
    )
    cicd = result.facts.cicd
    assert cicd is not None
    assert cicd.has_ci is True
    assert cicd.has_tests is True
    assert analyzer.last_envelope is not None
    assert analyzer.last_envelope.body.ci_execution_observed is False
    assert all(item.metadata.get("configuration_not_execution") is True for item in cicd.pipelines)


def test_missing_repository_path_does_not_invent_facts(tmp_path: Path) -> None:
    analyzer = InventoryAnalyzer()
    result = analyzer.analyze(
        repository=Repository(name="missing", path=tmp_path / "absent"),
        technologies=[],
    )
    assert result.facts.structure is None
    assert analyzer.last_envelope is None


def test_default_pipeline_starts_with_inventory_analyzer() -> None:
    first = builtin_analyzers()[0]
    assert isinstance(first, InventoryAnalyzer)
