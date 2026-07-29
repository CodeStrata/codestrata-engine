"""Service contracts for the CodeStrata workflow."""

from collections.abc import Sequence
from typing import Protocol

from codestrata.models import (
    AnalyzerResult,
    Finding,
    Recommendation,
    Repository,
    RepositoryFacts,
    Technology,
)


class TechnologyDetector(Protocol):
    """Detects languages, frameworks, build tools, and other technologies."""

    def detect(self, repository: Repository) -> list[Technology]:
        """Detect technologies used by the repository."""
        ...


class Analyzer(Protocol):
    """Performs deterministic analysis of a repository.

    Each analyzer receives the facts produced so far, returns new findings
    and newly produced facts, and relies on CompositeAnalyzer to merge those
    facts before invoking the next analyzer.
    """

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Analyze the repository using accumulated facts.

        Args:
            repository: Repository under analysis.
            technologies: Technologies detected for the repository.
            facts: Facts accumulated from earlier analyzers, if any.

        Returns:
            New findings and newly produced facts for this analyzer only.
            Do not return previously accumulated facts; CompositeAnalyzer
            merges the returned facts into the running total.
        """
        ...


class RecommendationEngine(Protocol):
    """Generates modernization recommendations from normalized analysis inputs."""

    def generate(
        self,
        facts: RepositoryFacts,
        findings: Sequence[Finding],
        technologies: Sequence[Technology],
    ) -> list[Recommendation]:
        """Generate deterministic recommendations."""
        ...
