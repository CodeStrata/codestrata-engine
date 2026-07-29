"""Planning policies and configuration bounds for incremental assessment."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from codestrata.application.incremental.errors import IncrementalConfigurationError

MAX_DEPENDENCY_DEPTH = 3
MAX_CHANGE_RATIO = 1.0


class IncrementalPlanningPolicy(BaseModel):
    """Conservative bounds for incremental planning (not execution)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    max_changed_files: int = Field(default=100, ge=1, le=10_000)
    max_change_ratio: float = Field(default=0.30, gt=0.0, le=MAX_CHANGE_RATIO)
    dependency_depth: int = Field(default=2, ge=1, le=MAX_DEPENDENCY_DEPTH)
    max_impacted_components: int = Field(default=500, ge=1, le=50_000)
    max_impacted_findings: int = Field(default=500, ge=1, le=50_000)
    max_impacted_recommendations: int = Field(default=500, ge=1, le=50_000)
    allow_metadata_only_noop: bool = True
    require_complete_fingerprints: bool = True
    fallback_on_unknown_impact: bool = True
    fallback_on_unsupported_language: bool = True
    fallback_on_engine_change: bool = True

    @model_validator(mode="after")
    def enforce_hard_safety(self) -> IncrementalPlanningPolicy:
        # Hard safety conditions cannot be disabled.
        if not self.fallback_on_unknown_impact:
            raise IncrementalConfigurationError(
                "fallback_on_unknown_impact is a hard safety condition and must be true"
            )
        if not self.require_complete_fingerprints:
            raise IncrementalConfigurationError(
                "require_complete_fingerprints is a hard safety condition and must be true"
            )
        if self.dependency_depth > MAX_DEPENDENCY_DEPTH:
            raise IncrementalConfigurationError(
                f"dependency_depth cannot exceed {MAX_DEPENDENCY_DEPTH}"
            )
        return self


def policy_from_settings(settings: object | None) -> IncrementalPlanningPolicy:
    """Build a planning policy from optional CodestrataSettings.incremental section."""

    if settings is None:
        return IncrementalPlanningPolicy()
    section = getattr(settings, "incremental", None)
    if section is None:
        return IncrementalPlanningPolicy()
    try:
        return IncrementalPlanningPolicy(
            enabled=bool(section.enabled),
            max_changed_files=int(section.max_changed_files),
            max_change_ratio=float(section.max_change_ratio),
            dependency_depth=int(section.dependency_depth),
            max_impacted_components=int(section.max_impacted_components),
            max_impacted_findings=int(section.max_impacted_findings),
            max_impacted_recommendations=int(section.max_impacted_recommendations),
            allow_metadata_only_noop=bool(section.allow_metadata_only_noop),
            require_complete_fingerprints=bool(section.require_complete_fingerprints),
            fallback_on_unknown_impact=bool(section.fallback_on_unknown_impact),
            fallback_on_unsupported_language=bool(section.fallback_on_unsupported_language),
            fallback_on_engine_change=bool(section.fallback_on_engine_change),
        )
    except (TypeError, ValueError, ValidationError, IncrementalConfigurationError) as error:
        raise IncrementalConfigurationError(
            f"Invalid incremental configuration: {error}"
        ) from error
