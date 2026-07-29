"""Composite analyzer that executes multiple repository analyzers."""

from collections.abc import Sequence

from codestrata.models import (
    AnalyzerResult,
    Finding,
    Repository,
    RepositoryFacts,
    Technology,
)
from codestrata.services.contracts import Analyzer


class CompositeAnalyzer:
    """Run analyzers sequentially, merging facts between each step.

    Pipeline for each configured analyzer:

    1. Receive the facts accumulated so far
    2. Return new findings and newly produced facts (a delta)
    3. Merge those new facts into the accumulated result
    4. Pass the merged facts to the next analyzer
    """

    def __init__(self, analyzers: Sequence[Analyzer]) -> None:
        self._analyzers = tuple(analyzers)

    def analyze(
        self,
        repository: Repository,
        technologies: Sequence[Technology],
        facts: RepositoryFacts | None = None,
    ) -> AnalyzerResult:
        """Execute analyzers in order and accumulate findings and facts."""

        accumulated_facts = facts or RepositoryFacts()
        findings: list[Finding] = []

        for analyzer in self._analyzers:
            result = analyzer.analyze(
                repository=repository,
                technologies=technologies,
                facts=accumulated_facts,
            )

            findings.extend(result.findings)
            accumulated_facts = accumulated_facts.merge(result.facts)

        return AnalyzerResult(
            findings=findings,
            facts=accumulated_facts,
        )
