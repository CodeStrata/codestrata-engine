"""Execution policy for Phase 2F.2 incremental assessment."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from codestrata.application.incremental.errors import IncrementalConfigurationError
from codestrata.application.incremental.policies import IncrementalPlanningPolicy


class IncrementalExecutionPolicy(BaseModel):
    """Conservative execution bounds (planning policy fields remain separate)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    execution_enabled: bool = False
    allow_selective_scan: bool = True
    allow_graph_merge: bool = True
    allow_rule_reuse: bool = True
    allow_recommendation_reuse: bool = True
    allow_ai_reuse: bool = False
    fallback_on_step_failure: bool = True
    fallback_on_merge_conflict: bool = True
    fallback_on_validation_failure: bool = True
    max_changed_files: int = Field(default=100, ge=1, le=10_000)
    max_change_ratio: float = Field(default=0.30, gt=0.0, le=1.0)
    max_impacted_components: int = Field(default=500, ge=1, le=50_000)
    max_impacted_findings: int = Field(default=500, ge=1, le=50_000)
    max_impacted_recommendations: int = Field(default=500, ge=1, le=50_000)

    @model_validator(mode="after")
    def enforce_hard_safety(self) -> IncrementalExecutionPolicy:
        if not self.fallback_on_step_failure:
            raise IncrementalConfigurationError(
                "fallback_on_step_failure is a hard safety condition and must be true"
            )
        if not self.fallback_on_merge_conflict:
            raise IncrementalConfigurationError(
                "fallback_on_merge_conflict is a hard safety condition and must be true"
            )
        if not self.fallback_on_validation_failure:
            raise IncrementalConfigurationError(
                "fallback_on_validation_failure is a hard safety condition and must be true"
            )
        if self.allow_ai_reuse:
            raise IncrementalConfigurationError("allow_ai_reuse must remain false in Phase 2F.2")
        return self


def execution_policy_from_settings(settings: object | None) -> IncrementalExecutionPolicy:
    """Build execution policy from CodestrataSettings.incremental."""

    if settings is None:
        return IncrementalExecutionPolicy()
    section = getattr(settings, "incremental", None)
    if section is None:
        return IncrementalExecutionPolicy()
    try:
        from codestrata.application.incremental.rollout import resolve_rollout_mode

        mode = resolve_rollout_mode(
            rollout_mode=getattr(section, "rollout_mode", None),
            enabled=bool(getattr(section, "enabled", False)),
            execution_enabled=bool(getattr(section, "execution_enabled", False)),
        )
        execution_enabled = bool(getattr(section, "execution_enabled", False)) or mode.value in {
            "opt_in",
            "default_with_fallback",
        }
        enabled = bool(getattr(section, "enabled", False)) or mode.value != "off"
        return IncrementalExecutionPolicy(
            enabled=enabled,
            execution_enabled=execution_enabled,
            allow_selective_scan=bool(getattr(section, "allow_selective_scan", True)),
            allow_graph_merge=bool(getattr(section, "allow_graph_merge", True)),
            allow_rule_reuse=bool(getattr(section, "allow_rule_reuse", True)),
            allow_recommendation_reuse=bool(getattr(section, "allow_recommendation_reuse", True)),
            allow_ai_reuse=bool(getattr(section, "allow_ai_reuse", False)),
            fallback_on_step_failure=bool(getattr(section, "fallback_on_step_failure", True)),
            fallback_on_merge_conflict=bool(getattr(section, "fallback_on_merge_conflict", True)),
            fallback_on_validation_failure=bool(
                getattr(section, "fallback_on_validation_failure", True)
            ),
            max_changed_files=int(section.max_changed_files),
            max_change_ratio=float(section.max_change_ratio),
            max_impacted_components=int(section.max_impacted_components),
            max_impacted_findings=int(section.max_impacted_findings),
            max_impacted_recommendations=int(section.max_impacted_recommendations),
        )
    except (TypeError, ValueError, ValidationError, IncrementalConfigurationError) as error:
        raise IncrementalConfigurationError(
            f"Invalid incremental execution configuration: {error}"
        ) from error


def planning_policy_from_execution(
    policy: IncrementalExecutionPolicy,
) -> IncrementalPlanningPolicy:
    """Derive a planning policy snapshot from execution bounds."""

    return IncrementalPlanningPolicy(
        enabled=policy.enabled,
        max_changed_files=policy.max_changed_files,
        max_change_ratio=policy.max_change_ratio,
        max_impacted_components=policy.max_impacted_components,
        max_impacted_findings=policy.max_impacted_findings,
        max_impacted_recommendations=policy.max_impacted_recommendations,
    )
