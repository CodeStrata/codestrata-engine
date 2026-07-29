"""Tests for the repository analysis application service."""

from collections.abc import Sequence
from pathlib import Path

from codestrata.models import (
    AnalyzerResult,
    Finding,
    FindingCategory,
    FindingSource,
    Repository,
    RepositoryFacts,
    Severity,
    Technology,
    TechnologyCategory,
)
from codestrata.services.analysis_service import AnalysisService


class StubTechnologyDetector:
    """Technology detector used for service testing."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Return a predictable technology result."""

        del repository

        return [
            Technology(
                name="Java",
                category=TechnologyCategory.LANGUAGE,
                confidence=1.0,
                source="test",
            )
        ]


class StubAnalyzer:
    """Repository analyzer used for service testing."""

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Return a predictable finding."""

        del facts

        return AnalyzerResult(
            findings=[
                Finding(
                    rule_id="test.repository.file_count",
                    title="Repository file count",
                    description=f"Repository contains {len(repository.files)} file.",
                    category=FindingCategory.MAINTAINABILITY,
                    severity=Severity.INFO,
                    source=FindingSource.DETERMINISTIC,
                    affected_technologies=[technology.name for technology in technologies],
                )
            ]
        )


def test_analysis_service_creates_analysis_result() -> None:
    repository = Repository(
        name="sample",
        path=Path("/tmp/sample"),
        files=["src/main/java/Sample.java"],
        total_files=1,
    )

    service = AnalysisService(
        technology_detector=StubTechnologyDetector(),
        analyzer=StubAnalyzer(),
        analyzer_version="0.2.0",
    )

    result = service.analyze(repository)

    assert result.repository is repository

    assert len(result.technologies) == 1
    assert result.technologies[0].name == "Java"

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "test.repository.file_count"
    assert result.findings[0].source == FindingSource.DETERMINISTIC
    assert result.findings[0].affected_technologies == ["Java"]

    assert isinstance(result.recommendations, list)
    assert result.completed_at is not None
    assert result.completed_at >= result.started_at
    assert result.analyzer_version == "0.2.0"

    assert result.facts.technology is not None
    assert result.facts.technology.programming_languages == ["Java"]
    assert result.facts.technology.detected_technologies == ["Java"]
