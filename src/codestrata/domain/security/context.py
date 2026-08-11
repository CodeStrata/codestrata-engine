"""Security evidence context classification (precision layer).

Classifies *where* secret-like evidence originates so reporting can demote
non-actionable findings without suppressing detector matches.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SecurityEvidenceContext(StrEnum):
    """Repository context for security evidence and findings."""

    PRODUCTION = "production"
    TEST = "test"
    TEST_FIXTURE = "test_fixture"
    DOCUMENTATION = "documentation"
    SAMPLE = "sample"
    GENERATED = "generated"
    DEPENDENCY_METADATA = "dependency_metadata"
    BUILD_ARTIFACT = "build_artifact"
    CONFIGURATION_SCHEMA = "configuration_schema"
    CI_EXPRESSION = "ci_expression"
    MOCK_CREDENTIAL = "mock_credential"
    UNKNOWN = "unknown"


class SecurityContextDecision(BaseModel):
    """Outcome of classifying one path/value for security reporting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    context: SecurityEvidenceContext
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    path_role: str | None = None

    @property
    def is_actionable_production(self) -> bool:
        return self.context is SecurityEvidenceContext.PRODUCTION


# Contexts that must not surface as high-severity leadership security risks.
NON_ACTIONABLE_CONTEXTS: frozenset[SecurityEvidenceContext] = frozenset(
    {
        SecurityEvidenceContext.TEST,
        SecurityEvidenceContext.TEST_FIXTURE,
        SecurityEvidenceContext.DOCUMENTATION,
        SecurityEvidenceContext.SAMPLE,
        SecurityEvidenceContext.GENERATED,
        SecurityEvidenceContext.DEPENDENCY_METADATA,
        SecurityEvidenceContext.BUILD_ARTIFACT,
        SecurityEvidenceContext.CONFIGURATION_SCHEMA,
        SecurityEvidenceContext.CI_EXPRESSION,
        SecurityEvidenceContext.MOCK_CREDENTIAL,
    }
)

CONTEXT_LABELS: dict[SecurityEvidenceContext, str] = {
    SecurityEvidenceContext.PRODUCTION: "Production source",
    SecurityEvidenceContext.TEST: "Test code",
    SecurityEvidenceContext.TEST_FIXTURE: "Test fixture",
    SecurityEvidenceContext.DOCUMENTATION: "Documentation",
    SecurityEvidenceContext.SAMPLE: "Sample/example project",
    SecurityEvidenceContext.GENERATED: "Generated file",
    SecurityEvidenceContext.DEPENDENCY_METADATA: "Dependency metadata",
    SecurityEvidenceContext.BUILD_ARTIFACT: "Build artifact",
    SecurityEvidenceContext.CONFIGURATION_SCHEMA: "Configuration schema",
    SecurityEvidenceContext.CI_EXPRESSION: "CI secret reference",
    SecurityEvidenceContext.MOCK_CREDENTIAL: "Mock credential",
    SecurityEvidenceContext.UNKNOWN: "Unknown context",
}


__all__ = [
    "CONTEXT_LABELS",
    "NON_ACTIONABLE_CONTEXTS",
    "SecurityContextDecision",
    "SecurityEvidenceContext",
]
