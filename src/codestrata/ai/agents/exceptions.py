"""Typed exceptions for the modernization assessment agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codestrata.ai.agents.models import AgentExecutionTrace


class AgentError(Exception):
    """Base error for modernization assessment agent failures."""

    def __init__(
        self,
        message: str,
        *,
        trace: AgentExecutionTrace | None = None,
    ) -> None:
        super().__init__(message)
        self.trace = trace


class AgentConfigurationError(AgentError):
    """Raised when agent options or dependencies are invalid."""


class AgentToolError(AgentError):
    """Raised when a required tool call fails."""


class AgentExecutionError(AgentError):
    """Raised when agent orchestration fails during execution."""


class AgentValidationError(AgentError):
    """Raised when recommendation validation fails at the agent boundary."""
