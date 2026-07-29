"""Errors for incremental assessment planning and execution."""

from __future__ import annotations


class IncrementalPlanningError(Exception):
    """Base error for Phase 2F.1 incremental planning."""


class IncrementalConfigurationError(IncrementalPlanningError):
    """Invalid planning policy or configuration."""


class IncrementalEligibilityError(IncrementalPlanningError):
    """Previous run is not eligible as an incremental base."""


class IncrementalCompatibilityError(IncrementalPlanningError):
    """Engine or artifact compatibility cannot be established."""


class IncrementalManifestError(IncrementalPlanningError):
    """Candidate or previous manifest cannot be used for planning."""


class IncrementalDependencyError(IncrementalPlanningError):
    """Required planning dependency is unavailable."""


class IncrementalExecutionError(IncrementalPlanningError):
    """Base error for Phase 2F.2 incremental execution."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        execution_id: str | None = None,
        plan_id: str | None = None,
        failed_step: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.execution_id = execution_id
        self.plan_id = plan_id
        self.failed_step = failed_step


class IncrementalPlanRejectedError(IncrementalExecutionError):
    """Plan cannot be executed selectively."""


class SelectiveScanError(IncrementalExecutionError):
    """Selective scan failed or is incomplete."""


class IncrementalGraphMergeError(IncrementalExecutionError):
    """Graph rebuild/merge failed."""


class IncrementalRuleExecutionError(IncrementalExecutionError):
    """Incremental rule execution failed."""


class IncrementalRecommendationError(IncrementalExecutionError):
    """Incremental recommendation execution failed."""


class IncrementalArtifactMergeError(IncrementalExecutionError):
    """Artifact merger failed."""


class IncrementalMergeValidationError(IncrementalExecutionError):
    """Pre-persistence merge validation failed."""


class IncrementalFallbackError(IncrementalExecutionError):
    """Fallback to full assessment was required but could not complete."""


class IncrementalValidationError(IncrementalExecutionError):
    """Post-execution incremental validation failed."""


class IncrementalEquivalenceError(IncrementalExecutionError):
    """Semantic equivalence comparison failed or is unavailable."""


class IncrementalMetricsError(IncrementalExecutionError):
    """Metrics calculation failed or detected an inconsistency policy violation."""


class IncrementalExplanationError(IncrementalExecutionError):
    """Explainability generation failed."""


class IncrementalExecutionRecordNotFoundError(IncrementalExecutionError):
    """Persisted incremental execution record was not found."""


class IncrementalRolloutDisabledError(IncrementalExecutionError):
    """Incremental planning or execution is disabled by rollout mode."""


class IncrementalInspectionError(IncrementalExecutionError):
    """Inspection of incremental execution records failed."""
