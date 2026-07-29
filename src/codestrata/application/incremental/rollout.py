"""Rollout modes for incremental assessment (Phase 2F.3)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from codestrata.application.incremental.errors import IncrementalConfigurationError


class IncrementalRolloutMode(StrEnum):
    OFF = "off"
    PLAN_ONLY = "plan_only"
    OPT_IN = "opt_in"
    DEFAULT_WITH_FALLBACK = "default_with_fallback"


class IncrementalRolloutPolicy(BaseModel):
    """Resolved rollout posture. Default remains off."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: IncrementalRolloutMode = IncrementalRolloutMode.OFF
    validate_after_execution: bool = True
    persist_execution_records: bool = True
    enable_equivalence_check: bool = False
    max_explanations: int = Field(default=500, ge=1, le=10_000)
    max_equivalence_differences: int = Field(default=100, ge=1, le=10_000)
    fallback_on_validation_failure: bool = True
    fallback_on_metric_inconsistency: bool = True

    @model_validator(mode="after")
    def enforce_hard_safety(self) -> IncrementalRolloutPolicy:
        if not self.fallback_on_validation_failure:
            raise IncrementalConfigurationError("fallback_on_validation_failure must remain true")
        if not self.fallback_on_metric_inconsistency:
            raise IncrementalConfigurationError("fallback_on_metric_inconsistency must remain true")
        return self

    @property
    def allows_planning(self) -> bool:
        return self.mode is not IncrementalRolloutMode.OFF

    @property
    def allows_execution(self) -> bool:
        return self.mode in {
            IncrementalRolloutMode.OPT_IN,
            IncrementalRolloutMode.DEFAULT_WITH_FALLBACK,
        }


def resolve_rollout_mode(
    *,
    rollout_mode: str | IncrementalRolloutMode | None,
    enabled: bool,
    execution_enabled: bool,
) -> IncrementalRolloutMode:
    """Map legacy booleans + optional rollout_mode to a single mode."""

    if rollout_mode is not None and str(rollout_mode).strip():
        mode = IncrementalRolloutMode(str(rollout_mode).strip())
        if mode is IncrementalRolloutMode.OFF and (enabled or execution_enabled):
            raise IncrementalConfigurationError(
                "Conflicting incremental settings: rollout_mode=off with "
                "enabled/execution_enabled true"
            )
        if mode is IncrementalRolloutMode.PLAN_ONLY and execution_enabled:
            raise IncrementalConfigurationError(
                "Conflicting incremental settings: plan_only with execution_enabled"
            )
        return mode
    if execution_enabled:
        return IncrementalRolloutMode.OPT_IN
    if enabled:
        return IncrementalRolloutMode.PLAN_ONLY
    return IncrementalRolloutMode.OFF


def rollout_policy_from_settings(settings: object | None) -> IncrementalRolloutPolicy:
    if settings is None:
        return IncrementalRolloutPolicy()
    section = getattr(settings, "incremental", None)
    if section is None:
        return IncrementalRolloutPolicy()
    mode = resolve_rollout_mode(
        rollout_mode=getattr(section, "rollout_mode", None),
        enabled=bool(getattr(section, "enabled", False)),
        execution_enabled=bool(getattr(section, "execution_enabled", False)),
    )
    return IncrementalRolloutPolicy(
        mode=mode,
        validate_after_execution=bool(getattr(section, "validate_after_execution", True)),
        persist_execution_records=bool(getattr(section, "persist_execution_records", True)),
        enable_equivalence_check=bool(getattr(section, "enable_equivalence_check", False)),
        max_explanations=int(getattr(section, "max_explanations", 500)),
        max_equivalence_differences=int(getattr(section, "max_equivalence_differences", 100)),
        fallback_on_validation_failure=bool(
            getattr(section, "fallback_on_validation_failure", True)
        ),
        fallback_on_metric_inconsistency=bool(
            getattr(section, "fallback_on_metric_inconsistency", True)
        ),
    )
