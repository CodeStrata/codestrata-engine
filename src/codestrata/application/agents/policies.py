"""Agent execution policies and bounds."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from codestrata.application.agents.errors import AgentConfigurationError

MAX_DEPENDENCY_DEPTH = 3
MAX_WORKFLOW_STEPS = 20


class AgentExecutionPolicy(BaseModel):
    """Conservative bounds for agent workflows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int = Field(default=10, ge=1, le=MAX_WORKFLOW_STEPS)
    stop_on_blocking_validation: bool = True
    include_ai_context: bool = True
    max_findings: int = Field(default=100, ge=1, le=500)
    max_recommendations: int = Field(default=100, ge=1, le=500)
    max_components: int = Field(default=100, ge=1, le=1000)
    dependency_depth: int = Field(default=2, ge=1, le=MAX_DEPENDENCY_DEPTH)
    fail_on_missing_required_artifact: bool = True

    @model_validator(mode="after")
    def validate_bounds(self) -> AgentExecutionPolicy:
        if self.dependency_depth > MAX_DEPENDENCY_DEPTH:
            raise AgentConfigurationError(f"dependency_depth cannot exceed {MAX_DEPENDENCY_DEPTH}")
        if self.max_steps > MAX_WORKFLOW_STEPS:
            raise AgentConfigurationError(f"max_steps cannot exceed {MAX_WORKFLOW_STEPS}")
        return self


def policy_from_settings(settings: object | None) -> AgentExecutionPolicy:
    """Build a policy from optional CodestrataSettings.agents section."""

    if settings is None:
        return AgentExecutionPolicy()
    agents = getattr(settings, "agents", None)
    if agents is None:
        return AgentExecutionPolicy()
    try:
        return AgentExecutionPolicy(
            max_steps=int(agents.max_steps),
            stop_on_blocking_validation=bool(agents.stop_on_blocking_validation),
            include_ai_context=bool(getattr(agents, "include_ai_context", True)),
            max_findings=int(agents.max_findings),
            max_recommendations=int(agents.max_recommendations),
            max_components=int(agents.max_components),
            dependency_depth=int(agents.dependency_depth),
            fail_on_missing_required_artifact=bool(
                getattr(agents, "fail_on_missing_required_artifact", True)
            ),
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise AgentConfigurationError(f"Invalid agents configuration: {error}") from error


def resolve_agent_policy(
    settings: object | None = None,
    *,
    base: AgentExecutionPolicy | None = None,
    max_findings: int | None = None,
    max_recommendations: int | None = None,
    max_components: int | None = None,
    dependency_depth: int | None = None,
    max_steps: int | None = None,
    stop_on_blocking_validation: bool | None = None,
) -> AgentExecutionPolicy:
    """Resolve policy with request overrides after settings defaults.

    Precedence: hard Field bounds → explicit overrides → ``[agents]`` / base →
    framework defaults. Overrides outside hard bounds raise
    :class:`AgentConfigurationError`.
    """

    policy = base if base is not None else policy_from_settings(settings)
    updates: dict[str, object] = {}
    if max_findings is not None:
        updates["max_findings"] = max_findings
    if max_recommendations is not None:
        updates["max_recommendations"] = max_recommendations
    if max_components is not None:
        updates["max_components"] = max_components
    if dependency_depth is not None:
        updates["dependency_depth"] = dependency_depth
    if max_steps is not None:
        updates["max_steps"] = max_steps
    if stop_on_blocking_validation is not None:
        updates["stop_on_blocking_validation"] = stop_on_blocking_validation
    if not updates:
        return policy
    try:
        return AgentExecutionPolicy(**{**policy.model_dump(), **updates})
    except (TypeError, ValueError, ValidationError) as error:
        raise AgentConfigurationError(f"Invalid agent policy override: {error}") from error
