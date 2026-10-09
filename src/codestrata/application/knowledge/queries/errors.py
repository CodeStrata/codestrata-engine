"""Application-level errors for knowledge query services."""

from __future__ import annotations


class KnowledgeQueryError(Exception):
    """Base error for knowledge query operations."""


class RepositoryQueryNotFoundError(KnowledgeQueryError):
    """Raised when a repository cannot be resolved."""


class AssessmentRunNotFoundError(KnowledgeQueryError):
    """Raised when an assessment run does not exist."""


class SnapshotNotFoundError(KnowledgeQueryError):
    """Raised when a repository snapshot does not exist."""


class ArtifactNotFoundError(KnowledgeQueryError):
    """Raised when a required knowledge artifact is missing."""


class DuplicateArtifactError(KnowledgeQueryError):
    """Raised when a run has more than one artifact of the same kind."""


class KnowledgeArtifactCorruptionError(KnowledgeQueryError):
    """Raised when an artifact fails integrity or JSON validation."""


class IncompatibleArtifactVersionError(KnowledgeQueryError):
    """Raised when an artifact schema/version cannot be loaded."""


class FindingNotFoundError(KnowledgeQueryError):
    """Raised when a Phase 3 finding ID is not present in a run."""


class RecommendationNotFoundError(KnowledgeQueryError):
    """Raised when a Phase 3 recommendation ID is not present in a run."""


class ComponentNotFoundError(KnowledgeQueryError):
    """Raised when a graph component/node ID is not present."""


class SnapshotComparisonError(KnowledgeQueryError):
    """Raised when two snapshots cannot be compared."""


class QueryLimitError(KnowledgeQueryError):
    """Raised when a collection limit is invalid or exceeds the allowed maximum."""


class QueryBudgetExceededError(QueryLimitError):
    """Raised when a query limit or result size exceeds the authorized budget."""


class ArtifactPathSecurityError(KnowledgeQueryError):
    """Raised when an artifact path escapes the authorized root or accesses unauthorized files."""


class UnknownArtifactVersionError(IncompatibleArtifactVersionError):
    """Raised when an artifact version is unknown or unsupported."""


class MetricNotFoundError(KnowledgeQueryError):
    """Raised when a requested metric is not found in the run artifacts."""


class DependencyNotFoundError(KnowledgeQueryError):
    """Raised when requested dependencies are not found in the run artifacts."""


class ChangeFactNotFoundError(KnowledgeQueryError):
    """Raised when requested change facts or deltas are not found in the run artifacts."""


class EvidenceNotFoundError(KnowledgeQueryError):
    """Raised when a requested evidence item is not found in the run artifacts."""


class LineageNotFoundError(KnowledgeQueryError):
    """Raised when requested lineage or provenance is not found in the run artifacts."""
