"""Result produced by a repository analyzer."""

from pydantic import BaseModel, Field

from codestrata.models.finding import Finding
from codestrata.models.repository_facts import RepositoryFacts


class AnalyzerResult(BaseModel):
    """Findings and newly produced facts from a single analyzer step.

    ``facts`` should contain only facts contributed by this analyzer.
    CompositeAnalyzer merges them into the accumulated repository facts
    before calling the next analyzer.
    """

    findings: list[Finding] = Field(default_factory=list)
    facts: RepositoryFacts = Field(default_factory=RepositoryFacts)
